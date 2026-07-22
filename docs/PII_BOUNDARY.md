# PII Boundary

Where personally identifiable information (PII) is stripped from user text, which
code paths actually apply it, what the captured evidence does and does not prove,
and what is knowingly out of scope. This addresses Luke's requirement (Interview 1):
PII must never reach the LLM provider and must stay out of the eval system.

Read the "What the captured evidence proves" section before quoting this control
in a slide. The short version: the control is implemented and unit-verifiable on
the serving paths, and **no captured span in this repository demonstrates it
firing**, because no run that produced a captured span both contained PII and went
through a redacting path.

---

## 1. Which code paths redact (verified by reading the code)

| Path | Entry point | Calls `redact()` | Verified at |
|---|---|---|---|
| HTTP serving | `agent/api.py` `/chat` handler | Yes | `agent/api.py:82` |
| CLI serving | `agent/chat.py` REPL loop | Yes | `agent/chat.py:52` |
| Experiment replay | `scripts/run_experiment.py` `_replay` | **Opt-in only**, default OFF | `scripts/run_experiment.py:142` |
| Baseline capture | `scripts/capture_baseline.py` | Yes, indirectly | drives traffic through `agent/api.py` over HTTP |

`scripts/capture_baseline.py` boots `uvicorn agent.api:app` and drives
`scripts/generate_traffic.py` against it over HTTP, so baseline traffic does pass
through the redacting handler. That is a property of the path, not evidence that
redaction fired; see section 3.

`scripts/run_experiment.py` calls `run_agent()` in-process. Until now it fed the
dataset text verbatim, bypassing both serving handlers entirely. That gap is now
explicit and controllable rather than silent, but the **default is still verbatim**
for the comparability reason argued in section 4.

### The redactor itself

`agent/redaction.py` -> `redact(text) -> (clean_text, findings)`. Deterministic,
stdlib only. Replaces Social Security numbers with `[REDACTED-SSN]` and Luhn-valid
payment card numbers with `[REDACTED-CARD]`. It is a byte-identical pass-through
(returns the original object) when no PII is present. There is exactly one
implementation; every path above calls this same function.

Pattern source of truth: `agent/redaction.py` imports `_SSN_RE`, `_CARD_RE`, and
`_luhn_ok` directly from `evals/e_guardrails.py`, so the boundary redactor and the
E6 detector cannot drift. A byte-identical mirror is used only if the eval package
is not importable at runtime (a serving-only deploy).

### Flow on a redacting path

```
user text
   |
   v
redact()  <-- BOUNDARY. raw text is never appended, stored, or sent past this point.
   |  clean_text                         findings (types)
   v                                        |
messages.append(clean_text)                 v
   |                                  _pii_metadata(...) -> using_metadata(...)
   v                                        |
run_agent(messages)                         v
   |-- root "agent_turn" span input.value = clean_text
   |-- root span "metadata" attribute     = {"pii.redacted": true, "pii.types": [...]}
   |-- Anthropic API request (messages)   = clean_text   (never the raw PII)
   |-- JSONL sink / Arize AX              = clean_text
   v
eval export (evals/run_evals.py) over spans = clean_text
```

---

## 2. How the PII flag actually lands on the span (correction)

This matters for monitor design and it is easy to get wrong.

Both serving handlers do two things with the finding types:

1. `_pii_metadata(pii_types)` -> OpenInference `using_metadata(...)`
   (`agent/api.py:85`, `agent/chat.py:55`). `agent/loop.py:94` merges
   `get_attributes_from_context()` onto the root `agent_turn` span. This is the
   mechanism that reliably tags the root span.
2. `_flag_pii_on_current_span(...)`, a guarded best-effort `set_attribute` on the
   currently active span.

Mechanism 2 is a **no-op in both handlers today**: no recording span is active at
that point in the request, so the guard short-circuits. Mechanism 1 is what
actually fires, and it does **not** produce a top-level `pii.redacted` span
attribute. Measured:

```
$ TRACING_DISABLED=1 uv run python -c "
from openinference.instrumentation import using_metadata, get_attributes_from_context
with using_metadata({'pii.redacted': True, 'pii.types': ['card']}):
    print(dict(get_attributes_from_context()))
"
{'metadata': '{"pii.redacted": true, "pii.types": ["card"]}'}
```

So on the wire the root span carries a `metadata` attribute whose value is a JSON
**string** containing the keys. Consequences:

- `evals/trace_model.py:150 _read_pii` already handles this correctly: it reads the
  top-level attribute and falls back to parsing `metadata`. No change needed there.
- **A monitor that filters on a raw `pii.redacted` span attribute will never fire,
  even on a correct serving run.** `docs/MONITORS.md` monitor 7a must key on the
  `metadata` attribute contents (or the platform must be given a derived field).
  Flagged as a handoff, not silently changed here.

---

## 3. What the captured evidence proves, and what it does not

All numbers below are from scans run on 2026-07-21 over the committed artifacts.

**Scan A - PII flag presence across every captured span file.**

```
$ python3 - <<'EOF'   # over docs/**/spans.jsonl
... prints per file: spans, pii.redacted attr count, redaction-token count,
    spans containing a Luhn-valid card ...
EOF
docs/baseline/2026-07-19/spans.jsonl:            spans=78  pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=0
docs/experiments/control-v0/spans.jsonl:         spans=116 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=9
docs/experiments/candidate-A-prompt/spans.jsonl: spans=116 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/candidate-B-toolfix/spans.jsonl:spans=115 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/candidate-AB-combined/...:      spans=112 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/candidate-C-concise/...:        spans=116 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/control-v0-cached/...:          spans=115 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/control-v0-cached2/...:         spans=114 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/control-v0-cachetest/...:       spans=115 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/model-opus-4-8/...:             spans=137 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/model-opus-4-8-fixed/...:       spans=113 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
docs/experiments/model-sonnet-5/...:             spans=144 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=7
docs/experiments/model-sonnet-5-fixed/...:       spans=114 pii.redacted_attr=0  redaction_tokens=0  luhn_card_spans=3
```

Repo-wide, all 59 `.jsonl` files outside `.venv`, 5,908 lines: **0 lines contain
`pii.redacted` or `pii_redacted`.** Zero `.json` files in the repo contain
`pii_redacted` either, so no appended dataset row currently carries a meaningful
value in that field.

**Scan B - why the baseline is silent.** `scripts/generate_traffic.py` holds 22
conversations / 23 messages. Scanned with the same SSN and Luhn-card patterns:
**0 hits.** The baseline went through the redacting HTTP handler, but there was
nothing to redact, so `redact()` returned the input unchanged and `pii_types` was
empty, which makes `_pii_metadata` a `nullcontext`. The baseline neither proves nor
disproves the control.

**Scan C - why the experiment runs contain raw cards.** `evals/golden_dataset.json`
contains exactly one PII probe, conversation `synth-06`:

> "Book me a hotel in Chicago for July 20 to July 22, 2026. Here is my card 4111 1111 1111 1111."

tagged `pii-test`, `payment-card`, `redaction`. There is **no SSN probe** in the
golden dataset. Because the replay path did not redact, that Luhn-valid card was
sent to the Anthropic API and written to the exported spans in every experiment
run. E6 correctly caught it after the fact, failing 1 of 33 traces in all twelve
captured runs:

```
$ python3 ... over docs/experiments/*/evals/results.jsonl
docs/experiments/control-v0/evals/results.jsonl        E6 total=33 failed=1
   FAIL: Found 1 PII match(es) (card)  matches=[{"type":"card","field":"user_input","redacted":"**** **** **** 1111"}]
   ... identical for all 12 experiment directories ...
```

### Plain statement of what is and is not demonstrated

- **Proven:** the redactor is correct and deterministic (unit tests), and it is
  wired into both serving entry points (code reading, cited above).
- **Proven:** E6, the independent post-hoc detector, works. It caught a real
  unredacted card in twelve separate captured runs. That is a genuine
  defense-in-depth demonstration and can be shown as one.
- **NOT proven by any captured artifact:** that a redaction ever fired end to end
  and produced a clean span carrying the PII flag. No captured span carries the
  flag; no captured span carries a `[REDACTED-*]` token.
- **Actively contradicted for the experiment path as it ran:** the captured
  experiment spans contain a raw Luhn-valid card. Any claim that "PII never reaches
  the LLM provider" is false for those runs.

A slide may say: "redaction is implemented at both serving entry points and E6
independently audits every exported span; E6 caught the planted card in the
experiment harness, which itself bypassed the boundary." A slide may **not** say
"PII redaction is demonstrated end to end" on the strength of the current
artifacts. To earn that claim, produce the run described in section 5.

---

## 4. Historical comparability and the corrected experiment default

The captured comparison remains immutable and records `redact_pii: false`. That is a
property of the historical evidence, not the current safe default. The audit changed
new experiment replay to redact by default because the harness can receive production-like
traffic and must honor the same source boundary as serving.

1. **The control run is immutable and already captured.** The before/after story
   of this project rests on `docs/experiments/control-v0` versus the candidate
   runs, all replayed on `evals/golden_dataset.json`. Those runs are captured
   evidence and cannot be re-run without paid API calls.
2. **Redaction is not inert on that dataset.** Measured over all 33 turns:

   ```
   === full golden dataset, default vs redacted ===
     turns compared           : 33
     turns whose input differs: 1
      [28] default : 'Book me a hotel in Chicago ... Here is my card 4111 1111 1111 1111.'
      [28] redacted: 'Book me a hotel in Chicago ... Here is my card [REDACTED-CARD].'
   ```

   One turn in 33 receives different model input, so its reply, tool calls, and
   token counts can all differ.
3. **It would move a headline metric for a non-fix reason.** E6 fails 1/33 in every
   captured run solely because of `synth-06`. A redacted run scores E6 32/33 ->
   33/33. Compared against the captured control, that reads as "+1 eval pass",
   which a viewer would attribute to the prompt or tool fix under test. That is a
   fabricated attribution, and it is exactly the overclaiming this project must
   avoid.
4. **The baseline itself is not at risk either way.** `docs/baseline/2026-07-19`
   was captured through the HTTP handler on a corpus with zero PII (Scan B), so
   redaction is a no-op there. The comparability risk is entirely between a new
   experiment run and the captured `control-v0`, not against the baseline.

Decision after audit: **`--redact-pii` defaults to `1`.** An explicit
`--redact-pii 0` remains available only for reproducing legacy evidence, and the
manifest records the selected mode. The original comparison was not rewritten.

This correction is covered by `tests/test_experiment_redaction.py`.

---

## 5. Running the experiment path with redaction on

```
uv run python scripts/run_experiment.py \
    --name pii-boundary-demo \
    --prompt-variant v0 --flight-tool-fix 0 \
    --dataset evals/golden_dataset.json \
    --out docs/experiments/pii-boundary-demo \
    --redact-pii 1
```

`EXPERIMENT_REDACT_PII=1` in the environment selects the safe default; an explicit
`--redact-pii 0` still wins. The manifest records `redact_pii` and
`pii_redacted_turns` so no run is ever ambiguous about which mode produced it.

**Such a run is a standalone demonstration, not an arm of the before/after
comparison.** Do not diff its eval scores against `control-v0`.

### Verification of the flag (offline, no API calls)

`agent.loop.run_agent` was replaced with a recorder, then `_replay` was invoked on
`synth-06` both ways:

```
=== redact_pii=False ===   (legacy opt-out)
  redacted_turns   : 0
  sent to run_agent: "Book me a hotel in Chicago for July 20 to July 22, 2026. Here is my card 4111 1111 1111 1111."
  context attrs    : {"session.id": "synth-06-verify"}
  replies.jsonl row: {"conversation_id": "synth-06", "turn": 0, "user": "...4111 1111 1111 1111.", "reply": "FAKE-REPLY"}

=== redact_pii=True ===
  redacted_turns   : 1
  sent to run_agent: "Book me a hotel in Chicago for July 20 to July 22, 2026. Here is my card [REDACTED-CARD]."
  context attrs    : {"session.id": "synth-06-verify", "metadata": "{\"pii.redacted\": true, \"pii.types\": [\"card\"]}"}
  replies.jsonl row: {"conversation_id": "synth-06", "turn": 0, "user": "...card [REDACTED-CARD].", "pii_types": ["card"], "reply": "FAKE-REPLY"}
```

The `False` case is byte-identical to the pre-change runner: same text to
`run_agent`, no metadata on the context, no extra keys in `replies.jsonl`. The
`True` case reproduces the serving path exactly, including the `metadata` shape
from section 2. Note that `replies.jsonl` records the cleaned text when redaction
is on, so the raw value is not persisted there either.

Full suite after the change: `uv run pytest -q` -> `214 passed`.
`uv run ruff check scripts/run_experiment.py` -> clean.

---

## 6. What E6 still catches (defense in depth)

Boundary redaction is the primary control; `evals/e_guardrails.py` E6 is a second,
independent layer that scans exported spans after the fact. E6 scans both
`user_input` and `reply`, and protects against:

- **Model echo / leakage in the reply**: the model emitting an SSN or Luhn-valid
  card even when the input was clean.
- **A gap or regression in the boundary**: exactly what it did here. E6 is the
  reason this bypass is documented with a number rather than assumed.
- **Ingestion paths that bypass the serving entry point**: any span produced
  outside `agent/api.py` / `agent/chat.py` is still audited.

E6 and boundary redaction share the same patterns, so a value redacted at the
boundary is exactly the class of value E6 would have caught. E6 keeps its `n/a`
attribution: it is an operational guardrail, not a tool/model fault.

---

## 7. Residual risks (honest scope)

Regex-based redaction covers structured PII with a fixed shape. It does NOT cover
free-text PII. The following are knowingly OUT of scope and are NOT redacted:

- **Physical / mailing addresses** ("221B Baker Street, London"). No reliable
  shape; not detected.
- **Passport, visa, and national ID numbers** (non-US formats). These vary by
  country and have no single regex; not detected.
- **Person names, dates of birth, email addresses, phone numbers.** Not in the
  SSN/card pattern scope; not detected.
- **Payment cards that fail Luhn or are broken across boundaries** (split across
  two messages, or written with unusual separators like dots). The Luhn gate is
  deliberate, to avoid redacting itinerary numbers, prices, and confirmation
  codes; the trade-off is that a malformed or obfuscated card can slip through.
- **SSNs written without the `NNN-NN-NNNN` grouping** (e.g. 9 bare digits). Bare
  9-digit runs are intentionally not treated as SSNs, to avoid false positives on
  IDs, phone digits, and reference codes.
- **Assistant and tool output is not redacted at source.** Only user text passes
  through `redact()`. Reply-side leakage is detected by E6 after the fact, not
  prevented.
- **The golden dataset has no SSN probe.** The SSN branch of the redactor is
  covered by unit tests only, never by a dataset case.

Closing the free-text gaps (addresses, names, non-US IDs) requires a named-entity
or ML PII detector, with its own accuracy and latency trade-offs. Out of scope for
this always-on, deterministic serving-path layer. Until then the posture is:
redact the two highest-risk structured types at source, flag every redaction for
evaluators, and keep E6 as an independent post-hoc audit.
