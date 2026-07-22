# Run Index

One row per captured run, so every published number can be traced back to the
directory it came from and to the exact state that directory does (and does not)
pin.

**STATUS**

- This index is DESCRIPTIVE. It reports what each captured `manifest.json`
  actually contains. It changes no captured file.
- The 11-field manifest in the last section is PROPOSED, not implemented. No run
  in this repo emits it today.
- No manifest was backfilled or retro-edited. `git_dirty` and
  `evaluator_version` for the July 19 runs cannot be honestly recovered now, so
  they are reported as missing rather than reconstructed.
- **Second pass, 2026-07-21 evening.** The final loop run
  (`docs/loop-runs/interview2-final/`) finished at `2026-07-22T00:45:20Z` and its
  two experiment arms are now rows 15-16, transcribed from their manifests. Three
  claims in the first pass were corrected rather than quietly edited: the manifest
  count (15, now 16), the `dataset_path` breakdown (it is not absolute on "all 14"
  files, because the two baselines have no such key), and the status of
  `candidate-AB-combined` versus the loop's own `candidate-B-flight-tool-fix`,
  which are now disambiguated in section 3.1. Nothing under
  `docs/baseline/**` or `docs/experiments/**` was touched.

---

## How the manifests were enumerated

Run from the repo root:

```
find docs -name "manifest.json" | sort
```

Re-run on 2026-07-21 after the final loop run completed, that returns **16**
paths: 2 under `docs/baseline/`, 12 under `docs/experiments/`, and 2 under
`docs/loop-runs/interview2-final/experiments/`. Every row below was read from one
of those files.

An earlier version of this section said 15. That was correct at the time and is
now wrong for one reason, stated rather than quietly overwritten: the index was
authored while the loop run was still executing, so only the control arm's
manifest existed. The candidate arm
(`docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix/manifest.json`)
was written at `2026-07-22T00:45:19Z`, after the count was taken.

Note: the count under `docs/baseline/` and `docs/experiments/` is **14**, not 13.

---

## 1. Captured runs

Every cell is transcribed from the run's `manifest.json`. `not recorded` means
the key is absent from that file. It is never replaced with an inferred value.

`git_sha` is quoted as recorded. See section 2 for what it is and is not worth.

| # | Run directory | model | prompt_variant | flight_tool_fix | dataset_version | turn_count | wall_seconds | git_sha (as recorded) | reproducible? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `docs/baseline/2026-07-19` | `claude-haiku-4-5` | `v0-shipped` (as `prompt_version`) | not recorded | not recorded | 23 | 79.6 | `0080b11` (`git_dirty: true`) | Config replayable; code state NOT pinned |
| 2 | `docs/baseline/2026-07-19-INVALID-stale-server` | `claude-haiku-4-5` | `v0-shipped` (as `prompt_version`) | not recorded | not recorded | 0 | 87.6 | `0080b11` (`git_dirty: true`) | NO. Zero spans captured; nothing to reproduce |
| 3 | `docs/experiments/control-v0` | not recorded | `v0` | `0` | `v1-2026-07-19` | 33 | 118.1 | `0080b11` | Partial; model not recorded, code state NOT pinned |
| 4 | `docs/experiments/candidate-A-prompt` | not recorded | `v1` | `0` | `v1-2026-07-19` | 33 | 98.8 | `0080b11` | Partial; model not recorded, code state NOT pinned |
| 5 | `docs/experiments/candidate-B-toolfix` | not recorded | `v0` | `1` | `v1-2026-07-19` | 33 | 105.3 | `0080b11` | Partial; model not recorded, code state NOT pinned |
| 6 | `docs/experiments/candidate-AB-combined` | not recorded | `v1` | `1` | `v1-2026-07-19` | 33 | 100.0 | `0080b11` | Partial; model not recorded, code state NOT pinned |
| 7 | `docs/experiments/control-v0-cachetest` | `claude-haiku-4-5` | `v0` | `0` | `v1-2026-07-19` | 33 | 95.3 | `0080b11` | Config replayable; code state NOT pinned. `PROMPT_CACHE` state not recorded |
| 8 | `docs/experiments/control-v0-cached` | `claude-haiku-4-5` | `v0` | `0` | `v1-2026-07-19` | 33 | 99.4 | `0080b11` | Config replayable; code state NOT pinned. `PROMPT_CACHE` state not recorded |
| 9 | `docs/experiments/control-v0-cached2` | `claude-haiku-4-5` | `v0` | `0` | `v1-2026-07-19` | 33 | 103.9 | `0080b11` | Config replayable; code state NOT pinned. `PROMPT_CACHE` state not recorded |
| 10 | `docs/experiments/candidate-C-concise` | `claude-haiku-4-5` | `v2` | `1` | `v1-2026-07-19` | 33 | 74.3 | `0080b11` | Config replayable; code state NOT pinned |
| 11 | `docs/experiments/model-sonnet-5` | `claude-sonnet-5` | `v0` | `0` | `v1-2026-07-19` | 33 | 289.5 | `0080b11` | Config replayable; code state NOT pinned |
| 12 | `docs/experiments/model-sonnet-5-fixed` | `claude-sonnet-5` | `v1` | `1` | `v1-2026-07-19` | 33 | 172.4 | `0080b11` | Config replayable; code state NOT pinned |
| 13 | `docs/experiments/model-opus-4-8` | `claude-opus-4-8` | `v0` | `0` | `v1-2026-07-19` | 33 | 333.0 | `0080b11` | Config replayable; code state NOT pinned |
| 14 | `docs/experiments/model-opus-4-8-fixed` | `claude-opus-4-8` | `v1` | `1` | `v1-2026-07-19` | 33 | 190.2 | `0080b11` | Config replayable; code state NOT pinned |
| 15 | `docs/loop-runs/interview2-final/experiments/control` | `claude-haiku-4-5` | `v0` | `0` | `v1-2026-07-19` | 33 | 101.4 | `061307e` (no `git_dirty` in manifest; `approval.json` records `true`) | Config replayable; code state NOT pinned (tree was dirty) |
| 16 | `docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix` | `claude-haiku-4-5` | `v0` | `1` | `v1-2026-07-19` | 33 | 98.1 | `061307e` (same) | Config replayable; code state NOT pinned (tree was dirty) |

Rows 15 and 16 are the two arms of the final live loop run, written by
`scripts/feedback_loop.py --run-experiments`. Both were transcribed from their
`manifest.json` after the run finished; nothing here is inferred.

Three things these two rows record that rows 1-14 do not:

1. **`model` is present on both** (`claude-haiku-4-5`), closing the row 3-6 gap
   for these runs.
2. **`redact_pii` and `pii_redacted_turns` are present on both**, as `"0"` and
   `0`. Absent from all 14 earlier manifests. The `"0"` matters: it says these two
   arms ran the same unredacted-input path as every earlier experiment run, so
   they are eval-comparable to them, and it is why `pii_redacted_turns` is `0`
   rather than the count of PII-bearing turns.
3. **`dataset_path` is repo-relative** (`evals/golden_dataset.json`). See
   section 2.2 item 3.

Neither row records `git_dirty`, `span_count`, `run_id`, `evaluator_version` or
`started_at`. Field coverage against the 11-field target is **7 of 11**, the same
as rows 7-14. For the record, `spans.jsonl` line counts are 116 (control) and 114
(candidate), and `replies.jsonl` is 33 lines in both, matching `turn_count`. Those
counts were computed with `wc -l`; they are not in the manifests.

Recorded UTC capture timestamps, for ordering (`captured_at` on rows 1-2,
`timestamp` on rows 3-16):

| Run | timestamp (UTC) |
|---|---|
| `baseline/2026-07-19-INVALID-stale-server` | 2026-07-19T15:24:55Z |
| `baseline/2026-07-19` | 2026-07-19T15:27:57Z |
| `candidate-A-prompt` | 2026-07-19T16:02:52Z |
| `candidate-AB-combined` | 2026-07-19T16:02:56Z |
| `candidate-B-toolfix` | 2026-07-19T16:03:00Z |
| `control-v0` | 2026-07-19T16:03:09Z |
| `control-v0-cachetest` | 2026-07-19T22:57:17Z |
| `control-v0-cached` | 2026-07-19T22:59:02Z |
| `control-v0-cached2` | 2026-07-19T23:05:36Z |
| `candidate-C-concise` | 2026-07-19T23:08:28Z |
| `model-sonnet-5` | 2026-07-19T23:11:59Z |
| `model-opus-4-8` | 2026-07-19T23:12:46Z |
| `model-sonnet-5-fixed` | 2026-07-19T23:17:52Z |
| `model-opus-4-8-fixed` | 2026-07-19T23:18:11Z |
| `loop-runs/interview2-final/experiments/control` | 2026-07-22T00:43:40Z |
| `loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix` | 2026-07-22T00:45:19Z |

The loop run as a whole finished at `2026-07-22T00:45:20Z`, the `timestamp` in
`docs/loop-runs/interview2-final/approval.json`, one second after the candidate
arm's manifest. (`2026-07-22` UTC is the evening of `2026-07-21` local.)

---

## 2. What is not pinned, and why

### 2.1 The git_sha on every July 19 run is non-identifying. Stated plainly.

Every run in rows 1-14 records `git_sha: 0080b11`. That is a real commit, and it
is the wrong one to be reassured by:

```
$ git log --oneline -5
061307e feat: agent evaluation and automated improvement system
0080b11 Arize FDE project Init Commit

$ git ls-tree --name-only -r 0080b11 | wc -l
      16
```

Commit `0080b11` contains 16 files: the shipped agent (`agent/*.py`), the shipped
`data/*.json` fixtures, `scripts/generate_traffic.py`, `README.md`,
`pyproject.toml`, `uv.lock`, `.gitignore`, `.env.example`. It contains **no**
`evals/`, no `scripts/run_experiment.py`, no `scripts/capture_baseline.py`, no
`docs/`.

So at capture time the entire engagement - the eval suite that produced the
scores, the runner that produced the spans, the prompt variants under test - was
uncommitted working-tree state. `0080b11` identifies the untouched upstream code,
not the code that actually ran. **No run captured before commit `061307e` can be
tied to a verified code state.** That is a limitation of the evidence, and it is
disclosed here rather than papered over.

The two baseline manifests at least say so out loud: they carry
`"git_dirty": true`. The twelve experiment manifests do not record `git_dirty` at
all, so they do not even flag the problem. That asymmetry is why section 5 exists.

**Rows 15-16 improve on this, but do not close it.** They are the first captured
runs to record `061307e`, the commit that actually contains the engagement code
(`evals/`, `scripts/run_experiment.py`, `docs/`). So unlike rows 1-14, their sha
points at code that plausibly ran. It is still not a pin, for one honest reason:
the working tree was dirty at capture. `docs/loop-runs/interview2-final/approval.json`
records `"git_dirty": true`, and `scripts/feedback_loop.py` printed
`git: 061307e (dirty=True)` in the GATE section of `loop_report.md`. The
experiment manifest schema has no `git_dirty` field, so **the manifests alone do
not disclose this; only the approval record does.** Field 3 of section 5 is
therefore still the highest-priority schema fix.

### 2.2 Fields missing from every run

| Target field | Recorded by baseline manifests | Recorded by experiment manifests |
|---|---|---|
| `run_id` | no | no (`name` is a human label, not a unique id) |
| `git_commit` | yes, as `git_sha` (short) | yes, as `git_sha` (short) |
| `git_dirty` | yes (`true` on both) | **no** |
| `model` | yes | yes on 8 of 12; **absent on 4** (rows 3-6) |
| `prompt_version` | yes | yes, as `prompt_variant` |
| `agent_version` | yes | yes, as `name` (the runner exports it as `AGENT_VERSION`) |
| `dataset_version` | **no** (baselines replay `scripts/generate_traffic.py`, not the golden dataset) | yes (`v1-2026-07-19`) |
| `evaluator_version` | **no** | **no** |
| `flight_tool_fix` | **no** (shipped tools implied, not asserted) | yes |
| `started_at` | **no** | **no** |
| `finished_at` | approximately, as `captured_at` | approximately, as `timestamp` |

The table above describes rows 1-14. **Rows 15-16, written by the current
`_write_manifest`, differ in three ways:** `model` is present, `redact_pii` and
`pii_redacted_turns` are present (both absent from every earlier manifest), and
`dataset_path` is repo-relative. Everything the table marks missing for the
experiment column is still missing on them: no `run_id`, no `git_dirty`, no
`evaluator_version`, no `started_at`, no `span_count`.

Field coverage against the 11-field target: **6 of 11** for both baselines and
for the four experiment runs missing `model` (rows 3-6); **7 of 11** for the
remaining eight experiment runs and for rows 15-16.

Three consequences worth naming:

1. **`evaluator_version` does not exist anywhere in the codebase.**
   `command grep -rn "evaluator_version\|SUITE_VERSION\|eval_version\|EVAL_VERSION" evals/ scripts/ agent/ tests/`
   returns nothing (exit 1). The eval suite has been through at least two
   revisions (v1 to v1.2, documented in `docs/EVAL_ADJUDICATION.md`, plus the
   later addition of E10), and **no captured artifact records which revision
   scored it**. Suite revision is inferred from directory naming
   (`evals-v1/`, `e10-scoring-*`), not from recorded metadata.
2. **`started_at` is not recorded.** `timestamp` is written after the replay
   finishes (`_write_manifest` is called after `_replay` returns in
   `scripts/run_experiment.py`), so it is a finish time. A start time can only be
   approximated as `timestamp - wall_seconds`.
3. **`dataset_path` split into two shapes, and the split is now visible in the
   captured evidence.** Corrected: an earlier version of this item said the
   absolute path appears "on all 14 captured manifests". It does not. The two
   baseline manifests have **no `dataset_path` key at all** (they replay
   `scripts/generate_traffic.py`, not a dataset file). The true breakdown, read
   from every file:

   | Manifests | `dataset_path` |
   |---|---|
   | 2 baselines (rows 1-2) | absent |
   | 12 historical experiments (rows 3-14) | absolute: `/Users/chinmay_shringi/Desktop/sar/sample-travel-agent/evals/golden_dataset.json` |
   | 2 final-loop-run arms (rows 15-16) | repo-relative: `evals/golden_dataset.json` |

   The absolute form does not resolve on any other machine, which is the reason
   for the change: `scripts/run_experiment.py` applies a `repo_relative()` helper
   to `dataset_path` in `_write_manifest`, and rows 15-16 are the first captures
   written after that helper landed. Note the count: it is **12** historical
   manifests carrying the absolute path, not 13 and not 14, because the two
   baselines omit the key entirely. All 14 are **left exactly as captured** rather
   than backfilled, per the STATUS block at the top of this file. So a reader comparing
   two manifests will see two different path conventions; that is a real schema
   change with a date on it, not an inconsistency to be tidied away.

### 2.3 What IS fully reproducible today: the scores

The generation half of every published number is not reproducible (section 2.1).
The **scoring** half is, exactly, at zero API cost, because `spans.jsonl` is
immutable captured evidence and the eval suite is deterministic.

Verified, not asserted. Re-running the current suite over three captured span
files reproduced the captured summaries byte-for-byte:

```
uv run python evals/run_evals.py docs/experiments/control-v0/spans.jsonl          <tmp>
  -> summary.md identical to docs/evals/e10-scoring-control-v0/summary.md
uv run python evals/run_evals.py docs/experiments/candidate-AB-combined/spans.jsonl <tmp>
  -> summary.md identical to docs/evals/e10-scoring-candidate-AB-combined/summary.md
uv run python evals/run_evals.py docs/baseline/2026-07-19/spans.jsonl             <tmp>
  -> summary.md identical to docs/evals/e10-scoring-baseline/summary.md
```

(`diff` reported no differences in all three cases. No API calls: `run_evals.py`
reads spans and `data/*.json` fixtures only.)

So the honest statement to a reviewer is: *the eval scores in the deck are exactly
recomputable from files in this repo; the traces those scores were computed over
cannot be regenerated against a verified code state, because the code was
uncommitted when they were captured.*

---

## 3. Status: authoritative, superseded, exploratory, invalid

### 3.1 The two runs the deck should cite

| Role | Run | Authoritative scoring |
|---|---|---|
| **Baseline (Day 0, shipped agent)** | `docs/baseline/2026-07-19` | `docs/evals/e10-scoring-baseline/` |
| **Candidate (the proposed fix)** | `docs/experiments/candidate-AB-combined` | `docs/evals/e10-scoring-candidate-AB-combined/` |

The before/after **A/B comparison** has a third required member, because the
baseline and the candidate are not the same workload:

| Role | Run | Authoritative scoring |
|---|---|---|
| **Control arm of the experiment** | `docs/experiments/control-v0` | `docs/evals/e10-scoring-control-v0/` |

Why three and not two. `docs/baseline/2026-07-19` is the immutable Day 0 capture:
the shipped agent driven through `scripts/generate_traffic.py` over HTTP, 23 turns,
78 spans. `docs/experiments/control-v0` is the control arm of the experiment: the
same shipped configuration (`prompt_variant v0`, `flight_tool_fix 0`) replayed
in-process over the 33-turn golden dataset. Deltas must be quoted
candidate-AB-combined **versus control-v0** (same dataset, same harness). The
baseline is the untouched-system evidence, not the arithmetic control. Quoting a
delta of candidate-AB against the 23-turn baseline would be comparing two
different workloads.

#### The two "candidates" are different things. Do not conflate them.

There are now two candidate arms in this repo whose names both start with
"candidate", they were produced by different processes, and only one of them is
the ship recommendation. Naming them side by side because a reviewer will
otherwise assume the loop produced the thing we recommend shipping:

| | `candidate-AB-combined` | `candidate-B-flight-tool-fix` |
|---|---|---|
| Directory | `docs/experiments/candidate-AB-combined` | `docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix` |
| Produced by | A hand-designed 4-arm experiment run on 2026-07-19 | The automated loop, `scripts/feedback_loop.py --run-experiments`, on 2026-07-21 |
| Change | Prompt `v1` **and** flight tool fix (`PROMPT_VARIANT=v1`, `FLIGHT_TOOL_FIX=1`) | Flight tool fix **only** (`PROMPT_VARIANT=v0`, `FLIGHT_TOOL_FIX=1`) |
| Its control | `docs/experiments/control-v0` | `docs/loop-runs/interview2-final/experiments/control` |
| Role | **The ship recommendation.** Still the arm `docs/TOKEN_STRATEGY.md` recommends promoting | **The loop's output.** Evidence that the automation works end to end, chosen by the clustering stage, not by us |

Why both exist, read from the code rather than guessed. `_classify()` in
`scripts/feedback_loop.py` (line 409 at time of writing) maps clusters to
candidates by rule:
`E2 + tool -> B`, **any `attribution == "model"` cluster `-> A`**, `E4 + tool ->
backlog`, everything else `-> backlog`. The CLUSTER stage on the frozen baseline
found exactly two clusters, and `loop_report.md` section 3 records both as
`attribution=tool`: E2 with 6 failures and E4 with 2. **No model-attributed
cluster existed, so the rule never fired for A.** The loop proposed B alone and
filed E4 under "Backlog (no authorized candidate)". That is the rule behaving
correctly on the evidence it had, not the loop judging A to be a worse change. So:

- **The loop is authoritative for "does the automation work".** One command, all
  seven stages, a real candidate, a real A/B, a real gate record.
- **`candidate-AB-combined` remains authoritative for "what should we ship".** It
  is a superset of B, and it is the arm with the token and quality tradeoff
  measured in `docs/TOKEN_STRATEGY.md` and `docs/experiments/COMPARISON.md`.
- **Their numbers are not interchangeable.** Each candidate must be quoted against
  its own control. `candidate-B-flight-tool-fix` versus `control-v0` would be a
  cross-run comparison and is not supported by anything in this repo.

### 3.2 Full status table

| Run / artifact | Status | Basis |
|---|---|---|
| `docs/baseline/2026-07-19` | **AUTHORITATIVE** (Day 0 baseline) | Only baseline with spans (78 spans, 23 turns). Files are chmod `r--` / `r--------`, i.e. deliberately frozen |
| `docs/baseline/2026-07-19-INVALID-stale-server` | **INVALID.** Do not cite | `spans.jsonl` is 0 bytes, `span_count: 0`, `turn_count: 0`. `WHY_INVALID.txt`: "Captured against a stale pre-fix server on port 8000; spans empty. Not a baseline." `server_log.txt` confirms `[Errno 48] address already in use`. Retained as an audit trail of a caught bad capture |
| `docs/experiments/control-v0` | **AUTHORITATIVE** (experiment control arm) | The named control in `docs/experiments/COMPARISON.md` |
| `docs/experiments/candidate-AB-combined` | **AUTHORITATIVE** (the **ship recommendation**) | Prompt v1 + flight tool fix. The arm `docs/TOKEN_STRATEGY.md` recommends shipping as primary. **Not** the candidate the loop produced; see the disambiguation table in section 3.1 |
| `docs/experiments/candidate-A-prompt` | Supporting (ablation) | Isolates the prompt change. Cite only to show the tool fix, not the prompt, moved E2 |
| `docs/experiments/candidate-B-toolfix` | Supporting (ablation) | Isolates the tool fix |
| `docs/experiments/candidate-C-concise` | Supporting (optional variant, NOT recommended for ship) | v2-concise. `docs/TOKEN_STRATEGY.md` records the measured tradeoff and recommends v1 as primary, offering v2 as a quantified option |
| `docs/experiments/control-v0-cachetest` | **EXPLORATORY** (prompt-cache OFF arm) | Named in `docs/experiments/control-v0-cached/CACHE_MEASUREMENT.md` as the `PROMPT_CACHE` unset arm |
| `docs/experiments/control-v0-cached` | **EXPLORATORY** (prompt-cache ON arm) | Named in `CACHE_MEASUREMENT.md` as the `PROMPT_CACHE=1` arm |
| `docs/experiments/control-v0-cached2` | **EXPLORATORY, purpose not documented** | A third replay of the control configuration. `CACHE_MEASUREMENT.md` names only two runs and this is not one of them. `command grep -rln "cached2" docs/` finds it in prose only in `docs/PII_BOUNDARY.md`, and there only inside a per-file span inventory, never as the source of a published figure. Do not cite it; nothing depends on it |
| `docs/experiments/model-sonnet-5`, `-fixed`, `model-opus-4-8`, `-fixed` | Supporting (model-axis matrix) | The four non-Haiku cells of `docs/MODEL_COMPARISON.md`. Single run per cell, as that document already states |
| `docs/loop-runs/interview2-final/experiments/control` | **AUTHORITATIVE** (control arm of the loop run) | Written by the loop itself. `prompt_variant v0`, `flight_tool_fix 0`, 33 turns, 101.4 s |
| `docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix` | **AUTHORITATIVE** (the candidate the **loop** produced) | `prompt_variant v0`, `flight_tool_fix 1`, 33 turns, 98.1 s. Quote it only against the control directly above it. It is **not** the ship recommendation; that is `candidate-AB-combined` |
| `docs/loop-runs/interview2-final/` (`loop_report.md`, `comparison.md`, `proposal.md`, `approval.json`, `dataset.curated.json`, `evals/`) | **AUTHORITATIVE** for the end-to-end automation claim | One command, 7 stages, finished `2026-07-22T00:45:20Z`. Headline from `comparison.md`: E2 `flight_direction` **1/9 = 11% to 8/8 = 100%**, 0 regressions, `decision: pending_human_review`. **E1 reads 32/33 to 33/33 in that file; do not quote the +3pp.** The single control-arm E1 flag is the markdown heading `## Hotel Options`, a confirmed extractor false positive under adjudication. E1 is held at 100% |

**Important on the `PROMPT_CACHE` axis:** none of rows 7-9 record whether
`PROMPT_CACHE` was set. The manifest schema has no field for it. The distinction
between the cache-on and cache-off arms exists only in the prose of
`CACHE_MEASUREMENT.md` and in the directory names. This is exactly the class of
un-pinned axis the forward-looking manifest is meant to close.

### 3.3 Superseded scoring artifacts (retained deliberately, do not cite)

These are re-scorings of immutable spans, not separate runs. They have no
manifests.

| Artifact | Status | Basis |
|---|---|---|
| `docs/experiments/COMPARISON-evalv1.md` | **SUPERSEDED** by `docs/experiments/COMPARISON.md` | Eval suite v1 scores. `docs/EVAL_ADJUDICATION.md` documents three adjudicated false positives fixed in v1.2, and states the v1 scores are preserved on purpose as an audit trail |
| `docs/experiments/{control-v0,candidate-A-prompt,candidate-B-toolfix,candidate-AB-combined}/evals-v1/` | **SUPERSEDED**, retained as audit trail | Same reason. Diffing `evals-v1/summary.md` against `evals/summary.md` shows the change is confined to E1: control 31/33 to 33/33, candidate-A 32/33 to 33/33, candidate-B 32/33 to 33/33. `candidate-AB-combined` is byte-identical in both (it scored E1 33/33 under v1 too) |
| `docs/evals/baseline-2026-07-19-evalv1/` | **SUPERSEDED and redundant** | `diff` shows `results.jsonl` and `summary.md` are byte-identical to `docs/evals/baseline-2026-07-19/`. The v1.2 rule change did not alter a single baseline score. Both are in turn superseded by `docs/evals/e10-scoring-baseline/` |
| `docs/evals/baseline-2026-07-19/` | Superseded by `docs/evals/e10-scoring-baseline/` | Same E1-E7 numbers; the e10 dir adds E10 (`conflicting_context`, 1/1) |
| `docs/experiments/COMPARISON.md` | **AUTHORITATIVE** for the 4-arm E1-E7 comparison | Scores match each run's `evals/summary.md`. Does not include E10; for E10 use the `e10-scoring-*` dirs |

### 3.4 Scoring artifact to source run, complete mapping

Every `docs/evals/` directory, and the run whose `spans.jsonl` it scored. Mapping
is by directory name and corroborated by applicable-counts (23-turn baseline vs
33-turn golden dataset), and for three of them by the byte-identical re-score in
section 2.3.

| Scoring artifact | Source run spans | Suite | Status |
|---|---|---|---|
| `docs/evals/e10-scoring-baseline/` | `docs/baseline/2026-07-19/` | deterministic, v1.2 + E10 | **AUTHORITATIVE** for the baseline |
| `docs/evals/e10-scoring-control-v0/` | `docs/experiments/control-v0/` | deterministic, v1.2 + E10 | **AUTHORITATIVE** for the control |
| `docs/evals/e10-scoring-candidate-AB-combined/` | `docs/experiments/candidate-AB-combined/` | deterministic, v1.2 + E10 | **AUTHORITATIVE** for the candidate |
| `docs/evals/e10-scoring-candidate-C-concise/` | `docs/experiments/candidate-C-concise/` | deterministic, v1.2 + E10 | Supporting |
| `docs/evals/e10-scoring-model-sonnet-5{,-fixed}/` | matching `docs/experiments/model-sonnet-5{,-fixed}/` | deterministic, v1.2 + E10 | Supporting (`MODEL_COMPARISON.md`) |
| `docs/evals/e10-scoring-model-opus-4-8{,-fixed}/` | matching `docs/experiments/model-opus-4-8{,-fixed}/` | deterministic, v1.2 + E10 | Supporting (`MODEL_COMPARISON.md`) |
| `docs/evals/baseline-2026-07-19/` | `docs/baseline/2026-07-19/` | deterministic, v1.2, no E10 | Superseded |
| `docs/evals/baseline-2026-07-19-evalv1/` | `docs/baseline/2026-07-19/` | deterministic, v1 | Superseded and byte-identical to the above |
| `docs/evals/judges-baseline-2026-07-19/` | `docs/baseline/2026-07-19/` | LLM judges: E8, E9 | MONITOR-ONLY per `docs/JUDGE_CALIBRATION.md`. Not release-gating |
| `docs/evals/judges-candidate-AB/` | `docs/experiments/candidate-AB-combined/` | LLM judges: E8, E9, E11 | MONITOR-ONLY per `docs/JUDGE_CALIBRATION.md` |
| `docs/evals/judges-candidate-C/` | `docs/experiments/candidate-C-concise/` | LLM judges: E8, E9, E11 | MONITOR-ONLY per `docs/JUDGE_CALIBRATION.md` |
| `docs/loop-runs/interview2-final/evals/` | `docs/baseline/2026-07-19/spans.jsonl` | deterministic, current suite | The loop's own EVALUATE stage, re-scoring the frozen baseline. This is what CLUSTER and CURATE consumed |
| `docs/loop-runs/interview2-final/experiments/control/evals/` | that arm's `spans.jsonl` | deterministic, current suite | **AUTHORITATIVE** for the loop run's control |
| `docs/loop-runs/interview2-final/experiments/candidate-B-flight-tool-fix/evals/` | that arm's `spans.jsonl` | deterministic, current suite | **AUTHORITATIVE** for the loop run's candidate |

The three loop-run scoring artifacts live **inside** the run directory rather than
under `docs/evals/`, because the loop writes them itself. They have no
`e10-scoring-*` twin and need none: they were scored by the current suite at run
time, which is why E10 appears in them inline.

Each run directory also holds its own `evals/` subdirectory, written by the
runner at capture time. For the four July 19 morning runs those were scored under
suite v1.2 without E10; `candidate-C-concise`, `control-v0-cached2` and the four
model-axis runs carry E10 inline because they were captured after E10 landed.
When a run has both an inline `evals/` and an `e10-scoring-*` dir, **cite the
`e10-scoring-*` dir**: it is the newest suite and it covers every run uniformly.

### 3.5 One traceability gap this index resolves

`docs/TOKEN_STRATEGY.md` cites "8,496-8,587" output tokens "across the two
control runs" without naming which two of the four control-configuration runs.
Summing `llm.token_count.completion` over `messages.create` spans in each
captured `spans.jsonl` resolves it:

| Run | LLM calls | input tokens | output tokens |
|---|---|---|---|
| `control-v0` | 57 | 66,882 | **8,587** |
| `control-v0-cachetest` | 57 | 66,648 | **8,496** |
| `control-v0-cached` | 57 | 66,834 | 8,656 |
| `control-v0-cached2` | 57 | 66,693 | 8,412 |

So the quoted range is `control-v0-cachetest` (low) and `control-v0` (high). The
two figures in `CACHE_MEASUREMENT.md` (66,648 / 8,496 off, 66,834 / 8,656 on) are
`control-v0-cachetest` and `control-v0-cached`, matching that document's own
labelling. Counts computed from the immutable `spans.jsonl` files; no API calls.

---

## 4. Reproducing a run

All commands run from the repo root
(`/Users/chinmay_shringi/Desktop/sar/sample-travel-agent`).

**Both runners refuse to overwrite an existing capture** (`run_experiment.py`
aborts if `<out>/spans.jsonl` exists; `capture_baseline.py` aborts likewise).
Reproductions must therefore write to a NEW directory. That is intentional: it
makes captured evidence immutable in practice, not just by convention.

### 4.1 Re-score captured spans (no API calls, no cost, exactly reproducible)

This is the only step that is fully reproducible today, and it is verified in
section 2.3.

```
uv run python evals/run_evals.py docs/experiments/control-v0/spans.jsonl           docs/evals/<new-dir>
uv run python evals/run_evals.py docs/experiments/candidate-AB-combined/spans.jsonl docs/evals/<new-dir>
uv run python evals/run_evals.py docs/baseline/2026-07-19/spans.jsonl               docs/evals/<new-dir>
```

### 4.2 Regenerate the baseline capture (PAID: makes live API calls)

```
uv run python scripts/capture_baseline.py docs/baseline/<new-dir>
```

Boots `agent.api:app` on port 8317 (chosen to avoid colliding with a dev server
on 8000, which is what invalidated row 2), replays
`scripts/generate_traffic.py`, and aborts with `CAPTURE INVALID` if zero spans
were exported or if the root-span count does not match the messages sent.

### 4.3 Regenerate the control arm (PAID)

```
uv run python scripts/run_experiment.py \
    --name control-v0 \
    --prompt-variant v0 \
    --flight-tool-fix 0 \
    --dataset evals/golden_dataset.json \
    --out docs/experiments/<new-dir>
```

### 4.4 Regenerate the candidate arm (PAID)

```
uv run python scripts/run_experiment.py \
    --name candidate-AB-combined \
    --prompt-variant v1 \
    --flight-tool-fix 1 \
    --dataset evals/golden_dataset.json \
    --out docs/experiments/<new-dir>
```

`run_experiment.py` runs `evals/run_evals.py` automatically at the end and writes
the scores to `<out>/evals/`.

**Caveat on `--model`, stated rather than assumed.** Neither captured command
passed `--model`: rows 3-6 record no model at all. `agent/config.py:8` reads
`MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")`, and the runner only
sets `ANTHROPIC_MODEL` when `--model` is given, so an unset environment would
have resolved to `claude-haiku-4-5`. That is an inference from code, not a
recorded fact, and it cannot be checked because the manifest is silent and the
capture-time environment is gone. **Any reproduction should pass `--model`
explicitly** so the new run does not inherit the same ambiguity:

```
    --model claude-haiku-4-5
```

### 4.5 Re-run the LLM judges (PAID)

```
uv run python evals/run_judges.py docs/experiments/candidate-AB-combined/spans.jsonl docs/evals/<new-dir>
```

Judge outputs are NOT deterministic and will not reproduce byte-for-byte. All
three judges are MONITOR-ONLY per `docs/JUDGE_CALIBRATION.md`.

### 4.6 Re-run the whole loop, all 7 stages (PAID)

This is the single command behind `docs/loop-runs/interview2-final/`. Both flags
are required to reach stage 6: without `--run-experiments` the loop prints
"skipped (--run-experiments not set)" and never captures rows 15-16.

```
uv run python scripts/feedback_loop.py \
    --spans docs/baseline/2026-07-19/spans.jsonl \
    --dataset evals/golden_dataset.json \
    --out docs/loop-runs/<new-dir> \
    --run-experiments \
    --propose-with-llm
```

It writes its own `experiments/control` and `experiments/<candidate>` directories
underneath `--out`, each with the same `manifest.json` / `spans.jsonl` /
`replies.jsonl` / `evals/` shape as a hand-run experiment. `--out` must be a new
directory, for the same immutability reason as section 4.

`--propose-with-llm` drafts a bounded unified diff and appends it to
`proposal.md` under a draft marker. **The loop never applies it.** Stages 1
through 5 are free; stages 5b and 6 make paid calls.

---

## 5. PROPOSED: the 11-field manifest for future runs

**Not implemented.** No run in this repo emits this schema. It is the target for
the next run captured, so that a future reader can do what section 2.1 shows
cannot be done for the July 19 runs: tie a published number to a verified code
state.

| # | Field | Type | Source | Why it is required |
|---|---|---|---|---|
| 1 | `run_id` | string, unique | uuid4, or `<name>-<utc-timestamp>` | `name` is reused across reruns (four runs share the `control-v0` configuration). A unique id makes a row in a deck point at exactly one directory |
| 2 | `git_commit` | string, **full 40-char sha** | `git rev-parse HEAD` | The short sha is ambiguous over a long enough history. Store the full one |
| 3 | `git_dirty` | boolean | `bool(git status --porcelain)` | Without it, field 2 is unfalsifiable. This is the single field whose absence caused the section 2.1 problem. The baselines record it; the experiment runner does not |
| 4 | `model` | string | `agent.config.MODEL` after import | Absent on 4 of 14 captured runs. Always record the resolved value, never the flag |
| 5 | `prompt_version` | string | `args.prompt_variant` | Already recorded as `prompt_variant`; rename or duplicate under the canonical key |
| 6 | `agent_version` | string | `args.name` | Already recorded as `name`; same treatment. It is already exported as `AGENT_VERSION` and lands on every span |
| 7 | `dataset_version` | string | `dataset["version"]` | Already recorded on experiment runs. **Missing on both baselines**, which use `scripts/generate_traffic.py`; `capture_baseline.py` should record a traffic-generator version |
| 8 | `evaluator_version` | string | new constant in `evals/`, bumped on any rule change | **Does not exist anywhere today.** The suite has already changed twice (v1 to v1.2, then E10) and no artifact records which revision scored it. This is the highest-value field to add |
| 9 | `flight_tool_fix` | string `"0"`/`"1"` | `args.flight_tool_fix` | Already recorded on experiment runs; absent on baselines. Any future behavioral env gate (`PROMPT_CACHE`, `redact_pii`) belongs in the same block, for the reason in section 3.2 |
| 10 | `started_at` | ISO-8601 UTC | captured before `_replay` | Not recorded today. `timestamp` is a finish time; a start time is currently only approximable as `timestamp - wall_seconds` |
| 11 | `finished_at` | ISO-8601 UTC | captured after `_replay` | Rename of the existing `timestamp`, made explicit |

Keep the fields already present and useful: `dataset_path` (repo-relative),
`turn_count`, `wall_seconds`, `redact_pii`, `pii_redacted_turns`, and
`span_count` (which only `capture_baseline.py` records today, and which is a
cheap integrity check the experiment runner should also emit).

### Handoff notes (files this index does not own)

1. **`scripts/run_experiment.py`, function `_write_manifest`** (line 216 at time
   of writing; the file is being edited concurrently, so locate it by name). It
   currently builds a 12-key dict: `name`, `prompt_variant`, `flight_tool_fix`,
   `model`, `redact_pii`, `pii_redacted_turns`, `dataset_version`,
   `dataset_path`, `git_sha`, `timestamp`, `turn_count`, `wall_seconds`. This is
   the one function that must change to emit the 11 fields above. It needs a
   `_git_dirty()` helper next to the existing `_git_sha()` (line 133), and
   `_git_sha()` should drop `--short`. `started_at` must be captured in `main()`
   before `_replay` is called and threaded through, because `_write_manifest`
   currently only sees `wall_seconds`.
   **Do not edit this file while a loop run is executing against it.**
2. **`scripts/capture_baseline.py`**, manifest block at line 95. It already
   records `git_dirty` and `span_count` (which the experiment runner does not)
   but omits `dataset_version`, `flight_tool_fix`, `run_id`, `evaluator_version`
   and `started_at`. The two manifest schemas should converge on one shape.
3. **`evals/`** has no version constant of any kind. Field 8 requires introducing
   one and threading it into `run_evals.py` output.
4. `docs/TOKEN_STRATEGY.md` cites "the two control runs" without naming them.
   Section 3.5 resolves which two; the owner of that file may want to name them
   inline.
5. **`scripts/feedback_loop.py`, function `_classify()`, defect-ID mislabel.**
   (Line 422 at time of writing; the file is being edited concurrently, so locate
   it by the string, not the number.) The E4 backlog branch writes the reason string
   `"no candidate authorized (D-03 backlog)"`. Per `docs/REPO_FINDINGS.md`, E4
   `itinerary_day_count` is **D-05** (`create_itinerary` uses `range(1, num_days)`,
   line 42); **D-03** is the unrelated "`search_flights` accepts `date` and never
   uses it" (line 40). The string is wrong in the code and therefore wrong in the
   captured `docs/loop-runs/interview2-final/proposal.md` line 66. The captured
   artifact stays as captured; the **code** should be corrected before it is
   demoed, because a reviewer who opens `REPO_FINDINGS.md` will catch it. This
   index does not own either file.
6. **Rows 15-16 are the first manifests to carry `redact_pii` and
   `pii_redacted_turns`.** Both read `"0"` and `0`, meaning redaction was off, so
   `docs/PII_BOUNDARY.md`'s "`pii.redacted` has never appeared in a captured span"
   still holds, now across 16 runs rather than 14. The owner of that file may want
   to update its count.
