# Evidence Index

Every captured run directory in this repo, what it is, when it was captured, and
whether you may cite it.

This repo holds 30 run and scoring directories across four trees: 2 under
`docs/baseline/`, 12 under `docs/experiments/`, 13 under `docs/evals/`, and 3
under `docs/loop-runs/` (the authoritative one containing 2 further experiment
arms). Several are superseded and one is invalid. Citing the wrong one is the
fastest way to lose credibility in a review, so this page exists to make the
choice unambiguous.

**Scope.** This index answers **"can I trust it?"**. For **manifest field
coverage** (which run pins which axis, what `git_dirty` was, what a manifest does
and does not record), read `docs/experiments/RUN_INDEX.md`, which is the
per-run manifest index and is not duplicated here. Where the two overlap on
status they agree, with one exception noted in section 6.

**Method.** Statuses below were determined by reading each directory: manifests,
`summary.md`, `results.jsonl`, `WHY_INVALID.txt`, and by re-running the
evaluators offline. Directory names were never trusted on their own. Timestamps
marked "manifest" come from the run's own `manifest.json`; timestamps marked
"mtime" are filesystem modification times in local time, used only where a
directory carries no manifest, and are weaker evidence.

---

## 1. The two-sentence answer

**Cite exactly one baseline: `docs/baseline/2026-07-19/`.**
**Cite exactly one candidate result: `docs/loop-runs/interview2-final/`, candidate
`candidate-B-flight-tool-fix` against its own paired `control` in the same
directory.**

Section 4 explains why, and names the one other artifact the presentation
legitimately cites for a different claim.

---

## 2. `docs/baseline/` (2 directories)

| Directory | What it is | Captured | Status |
|---|---|---|---|
| `docs/baseline/2026-07-19/` | The Day 0 capture: the agent exactly as shipped, driven over HTTP by `scripts/generate_traffic.py`. 78 spans, 23 turns, 79.6s wall, `prompt_version: v0-shipped`, `model: claude-haiku-4-5`, `git_sha: 0080b11` | 2026-07-19T15:27:57Z (manifest) | **AUTHORITATIVE.** The only baseline with data. Deliberately frozen: `spans.jsonl` is mode `-r--------`, `manifest.json` and `run_log.txt` are `-r--r--r--` |
| `docs/baseline/2026-07-19-INVALID-stale-server/` | A failed capture attempt kept as an audit trail | 2026-07-19T15:24:55Z (manifest), 3 minutes before the good one | **INVALID. Never cite.** Verified, not assumed: `spans.jsonl` is **0 bytes**, `manifest.json` records `"span_count": 0` and `"turn_count": 0`, and `server_log.txt` contains `ERROR: [Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use`. `WHY_INVALID.txt` states: "Captured against a stale pre-fix server on port 8000; spans empty. Not a baseline." Retained on purpose: a caught bad capture is evidence of discipline |

---

## 3. `docs/loop-runs/` (3 directories)

| Directory | What it is | Captured | Status |
|---|---|---|---|
| `docs/loop-runs/interview2-final/` | The **complete** seven-stage loop run: COLLECT, EVALUATE, CLUSTER, CURATE, PROPOSE, PROPOSE-LLM, EXPERIMENT, GATE. Both experiment arms captured, comparison rendered, `approval.json` written. `git_sha: 061307e` | 2026-07-22T00:45:20Z (`approval.json`) | **AUTHORITATIVE.** The only loop run that executed stages 6 and 7 |
| `docs/loop-runs/llm-propose-2026-07-19/` | An earlier partial run, added to exercise stage 5b (the LLM diff drafter) | 2026-07-19 18:59 (mtime) | **SUPERSEDED.** Its own `loop_report.md` says stage 6 was "skipped (--run-experiments not set)" and stage 7 recorded "metric deltas: not measured". No experiment, no gate record. Its CURATE stage was a no-op ("dataset version unchanged: v1-2026-07-19 (all failures already covered; no-op)") |
| `docs/loop-runs/selftest-2026-07-19/` | The first end-to-end smoke test of the loop | 2026-07-19 11:59 (mtime) | **SUPERSEDED, and do not cite its curated dataset.** Stages 5b, 6 and 7 did not run. Its `dataset.curated.json` bumped the version to `v2-2026-07-19` but contains **31** conversations, the same count as v1, of which 8 are `failure-*` rows and 8 `shipped-*` ids present in today's `evals/golden_dataset.json` are absent. Whether 8 rows were dropped or the dataset simply had 23 conversations that morning **cannot be determined from what is on disk** and is not guessed here. Either way it is superseded by the final run |

### Inside the authoritative loop run

| Path | What it is | Status |
|---|---|---|
| `.../loop_report.md` | The stage-by-stage record of the single command that produced everything else in the directory | **AUTHORITATIVE.** Start here |
| `.../evals/` | Stage 2: the baseline re-scored under the current suite. 95 results over 23 traces | **AUTHORITATIVE** scoring of the baseline. Supersedes `docs/evals/e10-scoring-baseline/`: the pass/fail rows are identical, and this copy adds `session_id` and the `trace_context` replay payload |
| `.../dataset.curated.json` | Stage 4: `v1-2026-07-19` to `v2-2026-07-21`, **31 to 39** conversations. All 31 originals preserved (verified); 8 `failure-*` rows appended, each carrying `messages`, `assistant_reply`, `tool_calls`, `tool_outputs`, `failed_eval_ids`, `failure_reasons`, `source_trace_id`, `source_session_id`, `review_status: "pending"`, `expected_behavior: null`, `pii_redacted: false`, and a `sha256:` `dedup_key`. The 8 rows split `['E2'] x 6` and `['E4'] x 2` | **AUTHORITATIVE.** `expected_behavior` is deliberately `null`: it cannot be derived from a failed trace, so it is left for a human rather than invented |
| `.../proposal.md` | Stage 5 (registry candidate B, with trace ids as evidence) and stage 5b (a bounded unified diff drafted by `claude-opus-4-8` at temperature 0) | **AUTHORITATIVE.** The drafted diff is **NEVER applied**. It sits under an explicit "NOT applied, NOT authorized" marker |
| `.../experiments/control/` | Stage 6 control arm: `prompt_variant v0`, `flight_tool_fix 0`, `claude-haiku-4-5`, 33 turns, 101.4s | **AUTHORITATIVE control** |
| `.../experiments/candidate-B-flight-tool-fix/` | Stage 6 candidate arm: `prompt_variant v0`, `flight_tool_fix 1`, same model, 33 turns, 98.1s | **AUTHORITATIVE candidate** |
| `.../comparison.md` | The rendered control-versus-candidate table | **AUTHORITATIVE.** Regenerates byte-identically offline from the captured spans (`docs/README_FOR_REVIEWERS.md` section 3a, command 4) |
| `.../approval.json` | Stage 7: `"decision": "pending_human_review"`, `"reviewer": null`, `"decision_time": null`, `"regressions": []` | **AUTHORITATIVE.** This is the deviation from the customer's stated wish, recorded in machine-readable form. The loop is structurally incapable of writing any other decision |

---

## 4. Which single baseline and which single candidate to cite

### Baseline: `docs/baseline/2026-07-19/`

It is the only baseline that captured anything (78 spans; the alternative is 0
bytes). It was taken before any code was touched, so it is the untouched-system
evidence. Score it with `docs/loop-runs/interview2-final/evals/`.

### Candidate: `docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix/`, against `.../experiments/control/`

Four reasons, in order of weight:

1. **Both arms come from one command, one run, one day, one commit** (`061307e`).
   No cross-run splicing. The control it is compared against is its own paired
   control on the same 33-turn dataset through the same in-process harness.
2. **It is the artifact the system produced.** The whole claim of this project is
   that a loop does this automatically. The loop's own output directory is the
   only honest place to point when making that claim.
3. **It carries a gate record.** `approval.json` is the only machine-readable
   promotion decision in the repo.
4. **It reproduces offline.** Re-running the evaluators over its captured spans
   yields byte-identical `results.jsonl` for both arms.

### The one other artifact the presentation legitimately cites, for a different claim

`docs/experiments/COMPARISON.md` (with `control-v0`, `candidate-A-prompt`,
`candidate-B-toolfix`, `candidate-AB-combined`) is the **only** place the prompt
change is measured in isolation and combined with the tool fix. Slide 11 of
`docs/PRESENTATION.md` cites it. That is correct and should stay.

**The rule: two claims, two artifacts, never mix rows between them.**

- "The loop ran end to end and produced this result" cites
  `docs/loop-runs/interview2-final/`.
- "Here is the full ablation, and here is what we recommend shipping" cites
  `docs/experiments/COMPARISON.md`.

Do not build a single table out of both. They are different runs of the same
configuration on different days, and the shipped model is not deterministic. The
visible symptom: `control-v0` scored E1 33/33 on 2026-07-19, while the loop run's
`control` scored E1 32/33 on 2026-07-21, at the same `prompt_variant v0` /
`flight_tool_fix 0`. That is run-to-run variance plus the extractor issue in
section 5, not a change in the system.

---

## 5. The E1 `+3pp` in the authoritative comparison is probably an evaluator artifact

Flagging this here rather than letting a reviewer find it.

`docs/loop-runs/interview2-final/comparison.md` reports E1 `32/33 (97%)` for
control and `33/33 (100%)` for the candidate, a `+3pp` delta. The single control
failure is:

```
user_input:   Put together a 5-day itinerary for Paris, arriving June 10, 2026.
reason:       Reply names option(s) no tool returned: Hotel Options (invention).
attribution:  model
evidence:     {"fabricated": [{"entity": "Hotel Options", "type": "hotel", "kind": "invention"}]}
```

Reading the captured reply in that row's `trace_context`, `Hotel Options` is a
**markdown section heading** (`## Hotel Options`). The two hotels listed under it,
`Hotel Lumière` and `Rive Gauche Hôtel`, were returned by the tool and were **not**
flagged. The candidate reply for the same conversation passed only because it did
not present hotels at all, so it never emitted the heading.

Consequences, stated plainly:

- The E1 `+3pp` is very likely **not** a real groundedness improvement.
- The **+89pp on E2 is unaffected** and is the real result. E2 is a different
  evaluator on a different mechanism (route direction from the tool payload).
- This is a **fourth** suspected false positive in the E1 extractor. Three were
  already found, adjudicated and fixed, and are documented in
  `docs/EVAL_ADJUDICATION.md` (cross-item price sum, price difference, diacritic
  folding). This one is **not yet adjudicated** and is not in that document.

Recommended handling in the presentation: quote E2 `11% -> 100%` as the headline,
quote E1 as "held at 100 percent on the candidate", and if E1's control number is
raised, say the control's single flag is a suspected heading-parsing false
positive under investigation. Do not claim `+3pp` on E1 as a win.

---

## 6. `docs/experiments/` (12 run directories, 3 loose files)

Status here agrees with `docs/experiments/RUN_INDEX.md` section 3, which carries
the fuller basis for each. **The one place they differ:** `RUN_INDEX.md` marks
`docs/loop-runs/interview2-final/**` as **TBD** because that run was still
executing when it was written, and it names `candidate-AB-combined` as "the
recommended candidate". Both statements were true at the time. Section 3 and
section 4 of this page supersede the TBD.

| Directory | What it is | Captured (manifest) | Status |
|---|---|---|---|
| `control-v0/` | Control arm of the July 19 four-arm experiment. `v0` / `0`, 33 turns | 2026-07-19T16:03:09Z | **AUTHORITATIVE** as the control of `COMPARISON.md` only. Not the control for the loop run |
| `candidate-A-prompt/` | Prompt change alone. `v1` / `0` | 2026-07-19T16:02:52Z | Supporting (ablation). Cite to show the prompt alone did **not** move E2 |
| `candidate-B-toolfix/` | Flight tool fix alone. `v0` / `1` | 2026-07-19T16:03:00Z | Supporting (ablation) |
| `candidate-AB-combined/` | Both changes. `v1` / `1` | 2026-07-19T16:02:56Z | **AUTHORITATIVE** as the ship recommendation in `docs/TOKEN_STRATEGY.md`. **Not** the candidate the loop run produced |
| `candidate-C-concise/` | Concision variant. `v2` / `1`, `claude-haiku-4-5` | 2026-07-19T23:08:28Z | Supporting, **not recommended for ship**. `TOKEN_STRATEGY.md` records the measured tradeoff: 28 percent fewer output tokens, but E11 tone drops 100 percent to 94 percent |
| `control-v0-cachetest/` | Prompt-cache OFF arm | 2026-07-19T22:57:17Z | **EXPLORATORY.** Named as the `PROMPT_CACHE` unset arm in `control-v0-cached/CACHE_MEASUREMENT.md` |
| `control-v0-cached/` | Prompt-cache ON arm, plus `CACHE_MEASUREMENT.md` and `selftest_cache.py` | 2026-07-19T22:59:02Z | **EXPLORATORY.** The honest finding it documents is worth citing: cache reads and cache writes were **0** in both arms, because the 1,031-token system-plus-tools prefix is below Haiku's 2,048-token minimum cacheable length. Verified independently here: summing `llm.cache_read_tokens` and `llm.cache_creation_tokens` over both `spans.jsonl` files gives 0 and 0 |
| `control-v0-cached2/` | A third replay of the control configuration | 2026-07-19T23:05:36Z | **EXPLORATORY, purpose not documented. Do not cite.** `CACHE_MEASUREMENT.md` names only two runs and this is not one of them. Its cache counters are also 0/0. No published figure depends on it |
| `model-sonnet-5/` | Model axis, shipped prompt. `claude-sonnet-5`, `v0` / `0` | 2026-07-19T23:11:59Z | Supporting (`MODEL_COMPARISON.md`). One run per cell |
| `model-sonnet-5-fixed/` | Model axis, fixed config. `v1` / `1` | 2026-07-19T23:17:52Z | Supporting |
| `model-opus-4-8/` | Model axis, shipped prompt. `claude-opus-4-8`, `v0` / `0` | 2026-07-19T23:12:46Z | Supporting |
| `model-opus-4-8-fixed/` | Model axis, fixed config. `v1` / `1` | 2026-07-19T23:18:11Z | Supporting |

### Loose files in `docs/experiments/`

| File | Status |
|---|---|
| `COMPARISON.md` | **AUTHORITATIVE** for the four-arm E1-E7 comparison. Does not include E10, which postdates it. See section 4 for the rule on mixing it with the loop run |
| `COMPARISON-evalv1.md` | **SUPERSEDED by `COMPARISON.md`. Do not cite.** Verified by reading both: they differ in **exactly one row**, E1. Under eval suite v1 the control read `31/33 (94%)` and candidates A and B read `32/33 (97%)`; under v1.2 all four read `33/33 (100%)`. `docs/EVAL_ADJUDICATION.md` documents the three false positives that caused the difference. Retained deliberately as an audit trail: it is the proof that a `+6pp` claim was withdrawn rather than shipped |
| `RUN_INDEX.md` | Companion index. Per-run manifest fields and reproducibility, not trust status. Not superseded by this page; the two are complementary |

### Superseded scoring subdirectories

`control-v0/evals-v1/`, `candidate-A-prompt/evals-v1/`,
`candidate-B-toolfix/evals-v1/` and `candidate-AB-combined/evals-v1/` hold the
eval-suite-v1 scores of the same immutable spans. **SUPERSEDED. Do not cite.**
Retained as the audit trail behind `EVAL_ADJUDICATION.md`. Each run's sibling
`evals/` directory holds the v1.2 scores.

---

## 7. `docs/evals/` (13 scoring directories)

These are **scorings of spans, not runs**. They contain no manifest, so the times
below are filesystem mtimes.

| Directory | Scored which spans | Suite | Written (mtime) | Status |
|---|---|---|---|---|
| `e10-scoring-baseline/` | `docs/baseline/2026-07-19/` | deterministic v1.2 + E10 | 2026-07-19 19:11 | **Superseded** by `docs/loop-runs/interview2-final/evals/`, which has identical pass/fail rows plus the replay payload. Still correct; just not the newest |
| `e10-scoring-control-v0/` | `docs/experiments/control-v0/` | v1.2 + E10 | 2026-07-19 19:34 | **AUTHORITATIVE** for E10 on the July 19 control. E10 is absent from `COMPARISON.md` |
| `e10-scoring-candidate-AB-combined/` | `docs/experiments/candidate-AB-combined/` | v1.2 + E10 | 2026-07-19 19:11 | **AUTHORITATIVE** for E10 on the July 19 candidate |
| `e10-scoring-candidate-C-concise/` | `docs/experiments/candidate-C-concise/` | v1.2 + E10 | 2026-07-19 19:11 | Supporting |
| `e10-scoring-model-sonnet-5/`, `-fixed/` | matching `docs/experiments/model-sonnet-5*` | v1.2 + E10 | 2026-07-19 19:14, 19:18 | Supporting (`MODEL_COMPARISON.md`) |
| `e10-scoring-model-opus-4-8/`, `-fixed/` | matching `docs/experiments/model-opus-4-8*` | v1.2 + E10 | 2026-07-19 19:14, 19:18 | Supporting (`MODEL_COMPARISON.md`) |
| `baseline-2026-07-19/` | `docs/baseline/2026-07-19/` | deterministic v1.2, no E10 | 2026-07-19 12:07 | **SUPERSEDED.** Same E1-E7 numbers as the e10 directory, without E10 |
| `baseline-2026-07-19-evalv1/` | `docs/baseline/2026-07-19/` | deterministic v1 | 2026-07-19 11:38 | **SUPERSEDED and redundant. Do not cite.** Verified: `diff` shows its `results.jsonl` is **byte-identical** to `baseline-2026-07-19/`. The v1.2 rule change did not alter a single baseline score, so the v1-versus-v1.2 distinction is meaningless on the baseline. Kept only for symmetry with the experiment `evals-v1/` directories |
| `judges-baseline-2026-07-19/` | `docs/baseline/2026-07-19/` | LLM judges: **E8 and E9 only** (predates E11) | 2026-07-19 17:23 | **MONITOR-ONLY.** E8 23/23, E9 23/23. There is **no tone score on the frozen baseline** |
| `judges-candidate-AB/` | `docs/experiments/candidate-AB-combined/` | LLM judges: E8, E9, E11 | 2026-07-19 19:20 | **MONITOR-ONLY.** E8 30/33 (91%), E9 33/33, E11 33/33 |
| `judges-candidate-C/` | `docs/experiments/candidate-C-concise/` | LLM judges: E8, E9, E11 | 2026-07-19 19:25 | **MONITOR-ONLY.** E8 30/33 (91%), E9 33/33, E11 31/33 (94%) |

**Monitor-only is not a hedge, it is the finding.** `docs/JUDGE_CALIBRATION.md`:
"All three stay monitor-only. None is fit to gate a release today." Its own
headline agreement number is reported together with the reason it is nearly
uninformative, and its Cohen's kappa of 1.000 for E9 and E11 is identified as a
degenerate value returned by construction when one label class is empty. No judge
score may be used as a release gate or presented as calibrated.

---

## 8. Quick lookup: what to cite for a given claim

| Claim | Cite |
|---|---|
| "The shipped agent recommends backwards flights" | `docs/loop-runs/interview2-final/evals/summary.md` (E2 0/6 on the baseline) and `docs/DAY1_FINDINGS.md` |
| "The loop found it, clustered it, and attributed it to the tool span" | `docs/loop-runs/interview2-final/loop_report.md` sections 2 and 3 |
| "The loop curated 8 replayable failures into the dataset" | `docs/loop-runs/interview2-final/dataset.curated.json`, `loop_report.md` section 4 |
| "The fix moved E2 from 11 percent to 100 percent, cheaper and faster" | `docs/loop-runs/interview2-final/comparison.md` |
| "Promotion is blocked pending a human" | `docs/loop-runs/interview2-final/approval.json` |
| "Here is the full ablation and the ship recommendation" | `docs/experiments/COMPARISON.md` and `docs/TOKEN_STRATEGY.md` |
| "Frontier models are worse on the shipped prompt" | `docs/MODEL_COMPARISON.md` and `docs/evals/e10-scoring-model-*` |
| "We calibrated our own evaluators and withdrew a claim" | `docs/EVAL_ADJUDICATION.md`, with `docs/experiments/COMPARISON-evalv1.md` as the before |
| "Prompt caching buys nothing at this scale, and here is why" | `docs/experiments/control-v0-cached/CACHE_MEASUREMENT.md` |
| "Monitors are specified but not deployed" | `docs/MONITORS.md` header |
| "Booking conversion" | **Nothing. It has never been measured and no transactional booking exists.** Use E1 and E5 as explicitly labelled proxies |
