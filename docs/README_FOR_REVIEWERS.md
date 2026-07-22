# README for Reviewers

Start here. This page exists so a reviewer opening the repo cold can find the
source, the evidence, and a working repro command in about two minutes.

Every command on this page was executed from the repository root before it was
published, and the output pasted below is that run's real output. Every path
named here was checked to exist on 2026-07-21.

---

## 1. What this is, in three sentences

This is an **evaluation and automated improvement system built around** the
provided sample travel agent. The agent itself was deliberately **not** rebuilt:
no orchestration framework was added, the shipped system prompt is preserved
byte-for-byte, and every behavioral change ships behind an environment flag that
is **off** by default. What was built is the surrounding system: OpenInference /
OTel tracing, an 11-eval portfolio, an experiment runner, a seven-stage feedback
loop that collects failures and proposes bounded fixes, and a human approval gate
that the loop cannot bypass.

---

## 2. The five-minute path

Open these six files, in this order. Nothing else is required to understand the
system.

| # | Open | Why |
|---|---|---|
| 1 | **This file** | Orientation and repro commands |
| 2 | `docs/Interview_2_Customer_Presentation.pptx` | The customer-facing presentation |
| 3 | `docs/EVIDENCE_INDEX.md` | Which captured run is authoritative and which is superseded. Read before citing any number |
| 4 | `docs/loop-runs/interview2-final/loop_report.md` | The authoritative historical loop run, produced by one command |
| 5 | `docs/loop-runs/interview2-final/comparison.md` | The measured control-versus-candidate result |
| 6 | `docs/loop-runs/interview2-final/approval.json` | The gate. `"decision": "pending_human_review"`, `"reviewer": null`, promotion blocked |
| 7 | `docs/REQUIREMENT_MAP.md` | Customer requirements mapped to components and evidence |

Supporting reading, in descending order of usefulness:

- `docs/REPO_FINDINGS.md` and `docs/verification/DAY0_FIXTURE_CHECKS.md`: the
  defects found in the shipped agent, and the recomputation that proves them.
- `docs/EVAL_ADJUDICATION.md`: three false positives found in this project's own
  deterministic evaluators, adjudicated and fixed before the numbers were trusted.
  A fourth suspected false positive is recorded in `docs/EVIDENCE_INDEX.md`
  section 5 and is **not** yet adjudicated.
- `docs/JUDGE_CALIBRATION.md`: why all three LLM judges are monitor-only.
- `docs/MONITORS.md`: the proposed monitor configuration. Zero are deployed.
- `docs/BACKLOG.md`: the defects that were deliberately detected and **not** fixed.
- `docs/experiments/RUN_INDEX.md`: per-run manifest fields and what each run does
  and does not pin. Complements `docs/EVIDENCE_INDEX.md`, which covers trust status.

---

## 3. Reproduce it

All commands run from the cloned repository root.

### 3a. Offline. No credentials, no API key, no network, no spend.

These four commands verify most of the claim surface. A reviewer without an
Anthropic key can still confirm that the evaluators are deterministic and that
every published score recomputes from the captured spans.

**Command 1: the unit suite.**

```bash
uv run pytest -q
```

Real output:

```
........................................................................ [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
214 passed
```

**Command 2: re-score the frozen baseline from its captured spans.**

```bash
uv run python evals/run_evals.py docs/baseline/2026-07-19/spans.jsonl /tmp/review/baseline
```

Real output:

```
Eval   Name                    Appl  Pass  Fail   Rate
------------------------------------------------------
E1     fabricated_entity         23    23     0   100%
E2     flight_direction           6     0     6     0%
E3     tool_call_validity        16    16     0   100%
E6     pii                       23    23     0   100%
E7     guardrails                23    23     0   100%
E4     itinerary_day_count        2     0     2     0%
E10    conflicting_context        1     1     0   100%
E5     empty_result_honesty       1     1     0   100%

23 trace(s), 95 result(s) -> /tmp/review/baseline
```

That is the headline defect visible without a key: **E2 flight direction is 0/6
at baseline.** Confirm it matches what the loop captured:

```bash
diff /tmp/review/baseline/summary.md docs/loop-runs/interview2-final/evals/summary.md \
  && echo "MATCH: re-scored baseline summary is byte-identical to the captured loop-run stage-2 summary"
```

Real output:

```
MATCH: re-scored baseline summary is byte-identical to the captured loop-run stage-2 summary
```

**Command 3: re-score the authoritative control and candidate runs, and prove
the captured scores were not hand-edited.**

```bash
uv run python evals/run_evals.py docs/loop-runs/interview2-final/experiments/control/spans.jsonl /tmp/review/control >/dev/null
uv run python evals/run_evals.py docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix/spans.jsonl /tmp/review/candidate >/dev/null
diff /tmp/review/control/results.jsonl   docs/loop-runs/interview2-final/experiments/control/evals/results.jsonl
diff /tmp/review/candidate/results.jsonl docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix/evals/results.jsonl \
  && echo "MATCH: both re-scored results.jsonl are byte-identical to the captured ones"
```

Real output:

```
MATCH: both re-scored results.jsonl are byte-identical to the captured ones
```

**Command 4: regenerate the published comparison table from the captured spans.**

```bash
uv run python scripts/compare_experiments.py \
  docs/loop-runs/interview2-final/experiments/control \
  docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix
```

Real output (identical to the committed
`docs/loop-runs/interview2-final/comparison.md`):

```
# Experiment Comparison

Control (baseline for deltas): **control**

## Evals

| Eval | Name | control | candidate-B-flight-tool-fix |
|---|---|---|---|
| E1 | fabricated_entity | 32/33 (97%) | 33/33 (100%) [d+3pp] |
| E2 | flight_direction | 1/9 (11%) | 8/8 (100%) [d+89pp] |
| E3 | tool_call_validity | 24/24 (100%) | 24/24 (100%) [d+0pp] |
| E4 | itinerary_day_count | 0/3 (0%) | 0/3 (0%) [d+0pp] |
| E5 | empty_result_honesty | 4/4 (100%) | 5/5 (100%) [d+0pp] |
| E6 | pii | 32/33 (97%) | 32/33 (97%) [d+0pp] |
| E7 | guardrails | 33/33 (100%) | 33/33 (100%) [d+0pp] |
| E10 | conflicting_context | 2/2 (100%) | 2/2 (100%) [d+0pp] |

## Telemetry

| Metric | control | candidate-B-flight-tool-fix |
|---|---|---|
| Median latency (ms) | 2982 | 2753 |
| Total tokens | 75,350 | 73,901 |
| Total cost (USD) | $0.1094 | $0.1056 |
| Mean iterations | 1.73 | 1.73 |
```

Read the E1 `+3pp` with the caveat in `docs/EVIDENCE_INDEX.md` section 5. The
+89pp on E2 is the real result.

**Bonus offline check (the compile gate CI runs):**

```bash
uv run python -m compileall -q agent evals scripts tests && echo "compileall OK (exit 0, no output)"
```

Real output:

```
compileall OK (exit 0, no output)
```

### 3b. Requires `ANTHROPIC_API_KEY`. These spend money.

Everything below calls the Anthropic API. Do not run them to verify the numbers
on this page: the numbers on this page came from captured spans and are
reproducible offline by section 3a. Run these only to watch the system work live.

Set the key first (`.env.example` lists every variable):

```bash
cp .env.example .env   # then set ANTHROPIC_API_KEY
```

**The whole current loop, all seven stages, one command.** This creates new evidence
with source redaction enabled and passes the curated dataset into the experiment:

```bash
uv run python scripts/feedback_loop.py \
  --spans docs/baseline/2026-07-19/spans.jsonl \
  --dataset evals/golden_dataset.json \
  --out docs/loop-runs/<new-run-name> \
  --propose-with-llm --run-experiments
```

Note: point `--out` at a **new** directory. `docs/loop-runs/interview2-final/` is
captured evidence and must not be overwritten. `--propose-with-llm` adds one
`claude-opus-4-8` call that drafts a bounded diff; that diff is **never applied**.
`--run-experiments` replays the newly curated dataset through the control and candidate,
which is the bulk of the spend. Its turn count depends on the failures curated by that run.

The historical `interview2-final` run was captured by older code at commit `061307e`.
It replayed the original 33-turn dataset and recorded redaction off. Preserve it as
historical evidence; do not describe the current command as a byte-for-byte reproduction.

**A single experiment arm:**

```bash
uv run python scripts/run_experiment.py \
  --name control --prompt-variant v0 --flight-tool-fix 0 \
  --dataset evals/golden_dataset.json --out /tmp/review/live-control
```

**The three LLM judges (E8, E9, E11).** Monitor-only; they gate nothing:

```bash
uv run python evals/run_judges.py docs/baseline/2026-07-19/spans.jsonl /tmp/review/judges
```

**Re-capture a baseline from the running HTTP server:**

```bash
uv run python scripts/capture_baseline.py
```

This is the only path that exercises the PII redaction boundary, because
redaction lives in the serving handlers (`agent/api.py`, `agent/chat.py`) and the
experiment runner calls `run_agent()` in process. See section 4.

---

## 4. Implemented versus proposed

Read this section before repeating any claim from this repo out loud.

### Implemented (code exists and a captured artifact exercises it)

| Thing | Where | Evidence |
|---|---|---|
| OpenInference / OTel tracing around the agent loop | `agent/tracing.py` | 78 spans over 23 turns in `docs/baseline/2026-07-19/spans.jsonl` |
| 8 deterministic evals (E1-E7, E10) | `evals/e_grounding.py`, `e_toolcalls.py`, `e_guardrails.py`, `e_conflict.py`, run by `evals/run_evals.py` | Reproduced offline in section 3a |
| 3 LLM-judge evals (E8, E9, E11) | `evals/judges.py`, `evals/e_tone.py`, run by `evals/run_judges.py` | `docs/evals/judges-*` |
| Experiment runner with prompt and tool-fix axes | `scripts/run_experiment.py` | 14 captured runs under `docs/experiments/` and `docs/loop-runs/` |
| Seven-stage feedback loop | `scripts/feedback_loop.py` | `docs/loop-runs/interview2-final/loop_report.md` |
| Failure curation into the dataset | `evals/dataset.py` | 8 replayable rows appended; version `v1-2026-07-19` to `v2-2026-07-21`; 31 to 39 conversations in `docs/loop-runs/interview2-final/dataset.curated.json` |
| Human approval gate the loop cannot bypass | `scripts/approval.py` | `docs/loop-runs/interview2-final/approval.json`: `"decision": "pending_human_review"`, `"reviewer": null`. 14 tests in `tests/test_approval_record.py` assert the binding structurally |
| PII redaction at source | `agent/redaction.py`, called in `agent/api.py` and `agent/chat.py` | 26 tests in `tests/test_redaction.py`. **See the honest limit below** |
| Nightly scheduled loop | `.github/workflows/feedback-loop.yml` (`cron: "0 7 * * *"`) | Registry-only on cron; no model calls, so scheduled spend is zero |

214 tests pass (`uv run pytest -q`, section 3a).

### Proposed only (a written specification with no running system behind it)

- **Monitors are proposed. Zero are deployed.** `docs/MONITORS.md` says so in its
  own header: "As of 2026-07-21, **0 of the 8 monitors below are configured in
  Arize AX.** No monitor has ever fired, no alert has ever been routed, and no
  notification channel has been provisioned." The project runs on the AX free
  tier, which has no monitors-as-code path, so the honest artifact is a
  specification a human executes in the web UI.
- **The numeric promotion threshold is proposed.** The human half of the gate is
  implemented in `scripts/approval.py`; the specific pass-rate floor is written
  prose, not code. See `docs/REQUIREMENT_MAP.md` row 4.

### Implemented but never demonstrated on a captured run

- **PII redaction has never fired in a captured span.** `pii.redacted` appears in
  **zero** of the `spans.jsonl` files in this repo. Verify:
  `find docs -name spans.jsonl -exec command grep -c "pii\.redacted" {} +` returns
  `0` for every file. The reason is structural, not a bug: redaction is applied in
  the two serving entry points, and `scripts/run_experiment.py` calls `run_agent()`
  in process, bypassing both. The redactor is implemented and unit-tested; it is
  the *capture path* that has never exercised it. `docs/PII_BOUNDARY.md` documents
  this and one further trap: `pii.redacted` is carried inside the OpenInference
  `metadata` attribute, so a monitor filtering on a top-level `pii.redacted`
  attribute would never fire.
- **Tool retries with backoff** exist in `agent/tools.py` `execute_tool` and are
  proven by fault injection in `tests/test_tools.py`, but the shipped tools read
  local JSON fixtures and never raise a transient error, so no captured span shows
  a retry.

### Not measured, and not claimable

- **Booking conversion has never been measured.** There is no transactional
  booking in this system. Groundedness (E1) and empty-result honesty (E5) are
  offered as **leading proxies**, explicitly labelled as proxies. Any conversion
  figure would be fabricated.
- **The three LLM judges are not calibrated and are not release-gating.**
  `docs/JUDGE_CALIBRATION.md`: "All three stay **monitor-only**. None is fit to
  gate a release today." The 96/96 blind-label agreement in that document is
  reported alongside the reason it is nearly uninformative: 93 of 99 rows are
  "pass", so there is almost no variance to discriminate on, and the Cohen's kappa
  of 1.000 for E9 and E11 is a degenerate value returned by construction when one
  label class is empty, not a measurement. Do not call the judges calibrated.

---

## 5. Repo layout

One line per directory.

| Path | What is in it |
|---|---|
| `agent/` | The shipped travel agent, plus additive tracing, redaction, and session-store modules. Shipped prompt preserved byte-for-byte; changes are env-flag gated and off by default |
| `data/` | Static JSON fixtures the tools read: flights, hotels, weather. A closed set, which is why groundedness is exact set membership rather than an LLM opinion |
| `evals/` | The eval portfolio (8 deterministic, 3 judges), the golden dataset, the trace model the evals read, and judge calibration material |
| `scripts/` | Baseline capture, experiment runner, comparison, the seven-stage feedback loop, the approval record, and the Arize push utilities |
| `tests/` | 191 unit tests over the agent, evaluators, dataset curation, redaction, and the approval contract |
| `docs/` | All engagement output, and all captured evidence. Treated as immutable once written. See `docs/EVIDENCE_INDEX.md` |
| `docs/baseline/` | The Day 0 capture of the agent exactly as shipped, taken before anything was touched |
| `docs/experiments/` | Per-variant experiment runs: spans, replies, manifest, evals |
| `docs/evals/` | Eval scorings of those runs, including the judge scorings |
| `docs/loop-runs/` | Recorded end-to-end feedback-loop runs |
| `docs/proposals/` | The authorized candidate-change registry the loop proposes from |
| `docs/verification/` | Fixture re-derivation checks that prove the reported defects by computation |
| `traces/` | Local span sink. Gitignored |
| `.github/workflows/` | `ci.yml` (offline quality gates) and `feedback-loop.yml` (nightly registry-only loop) |
