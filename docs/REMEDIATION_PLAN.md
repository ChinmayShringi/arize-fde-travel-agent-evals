# Remediation Plan: Interview 2 Submission (single-session, submit today)

Prepared 2026-07-21. Presentation 2026-07-22 (`docs/FINAL_PLAN.md:1`).
Supersedes the day-by-day calendar in `docs/FINAL_PLAN.md:86-94`, which assumed a week.

Source of gaps: `missing.docx` (20 items: 4 P0, 12 P1, 4 P2), each independently
verified against the real repo by 9 parallel audit agents plus an adversarial
refutation pass. Three additional items were found by the audit and are not in
the source document.

## Audit outcome

**23 items assessed. Zero came back already-done.** 21 CONFIRMED_GAP, 2 PARTIAL.
12 agents, 0 errors, 296 tool calls.

The adversarial pass corrected **three** statuses, every one upward. This matters
because an over-credited status is the dangerous direction: it means walking into
the room believing a gap is closed.

| ID | Reported | Corrected | Why the first read over-credited |
|---|---|---|---|
| P1-04 | PARTIAL | CONFIRMED | Every calibration sheet has exactly **0** filled `human_label` cells, not some |
| P2-01 | PARTIAL | CONFIRMED | `PRODUCTION_READINESS.md` contains **zero** occurrences of booking, conversion, revenue, cancellation, or handoff across all 199 lines |
| P2-03 | PARTIAL | CONFIRMED | The disclosure exists only in `FOLLOWUP_QUESTIONS.md`, whose line 17 reads "Status: DRAFT v2. Chinmay reviews and sends. **Never sent by the assistant.**" An undelivered draft is not a disclosure |

### Three gaps the source document missed

| ID | Finding | Why it matters |
|---|---|---|
| NEW-SEC-1 | `Archive.zip` is 12,392 files / 299 MB and ships `.git/`, `.venv/`, **and every internal interview-prep document**: `CLAUDE.md`, `BUILD_PLAN.md`, `REPO_FINDINGS.md`, `deep-research-report.md`, and the Interview 1 discovery playbooks | The customer would receive your private strategy notes, including the section on what to deliberately not fix |
| NEW-SEC-2 | This shell's `grep` is a **zsh function shimmed to ugrep with `--ignore-files`**, which honors `.gitignore`. The secret scan documented at `docs/CODEBASE_LINK_CHECK.md:100-102` therefore returns a **false clean** on `.env` | The verification procedure that was supposed to prove no secrets leaked is structurally incapable of finding the one secret file that exists. Demonstrated live: `grep -rl 'sk-ant-api' .` returns zero, `command grep -rlE 'sk-ant-api' .` finds it |
| NEW-SEC-3 | `origin` is `github.com/Arize-ai/sample-travel-agent`, HEAD is Nick Luzio's single init commit, and 20 paths of work are uncommitted | Deliverable 3 of 3 in the brief is "a link to your codebase". **It does not currently exist.** |

NEW-SEC-2 is worth presenting on its own merits. See "Beyond the brief" below.

## Confirmed state of the 20 documented gaps

| ID | Status | Remaining work | Min | Risk |
|---|---|---|---|---|
| P0-01 | CONFIRMED | Rotate 3 live credentials; `.env` is byte-identical inside `Archive.zip`. Never committed to git, so no history scrub | 30 | high |
| P0-02 | CONFIRMED | `docs/` is a sibling of the git root, not inside it. CI references `docs/baseline/.../spans.jsonl` which does not survive a clone | 40 | blocker |
| P0-03 | CONFIRMED | See NEW-SEC-3. Zero commits of your own work | 35 | blocker |
| P0-04 | CONFIRMED | Exactly 2 source lines hard-code `/Users/chinmay_shringi/Desktop/sar`, plus 30 occurrences in 17 generated artifacts | 20 | high |
| P1-01 | CONFIRMED | **This is a RUN, not a BUILD.** All 7 stages already exist in one entrypoint (`feedback_loop.py:755-793`); they have simply never been executed together | 30 | high |
| P1-02 | CONFIRMED | CI passes `--run-experiments` but never `--propose-with-llm` | 15 | medium |
| P1-03 | CONFIRMED | Appended rows carry 5 keys only (`dataset.py:138-144`). ~80% of the target schema is already reachable from `TraceView`; this is plumbing | 75 | medium |
| P1-04 | CONFIRMED (corrected) | 0 of 99 human labels filled across every sheet | 75 | medium |
| P1-05 | CONFIRMED | `agent/loop.py:81` is `while True`, no cap, no deadline, no `except` | 20 | medium |
| P1-06 | CONFIRMED | Zero test files. pytest is not a dependency anywhere | 75 | high |
| P1-07 | CONFIRMED | Worse than claimed: **the workflow cannot run at all**, because the files it needs are uncommitted | 45 | medium |
| P1-08 | CONFIRMED | 11 doc-vs-code contradictions, 3 claimed plus 8 more found | 95 | blocker |
| P1-09 | CONFIRMED | 5 monitor specs, none labeled proposed vs deployed, 3 of 7 required types missing | 30 | high |
| P1-10 | CONFIRMED | `gate()` emits prose only; approver is a hardcoded string | 40 | high |
| P1-11 | CONFIRMED | Archive ships a live credential | 50 | blocker |
| P1-12 | PARTIAL | Manifests record 6 of 11 fields; `git_sha` is non-identifying on all 13 runs | 60 | high |
| P2-01 | CONFIRMED (corrected) | Zero occurrences of booking/conversion/revenue in `PRODUCTION_READINESS.md` | 40 | medium |
| P2-02 | CONFIRMED | None of the 6 attributes exist. `tracing.py` sets no span attributes | 30 | medium |
| P2-03 | CONFIRMED (corrected) | The disclosure exists **only in an email draft marked "Never sent"** | 15 | high |
| P2-04 | PARTIAL | Sampling half exists at `PRODUCTION_READINESS.md:35-40`; trigger tiers do not | 30 | low |

Serial total is 900 minutes. Parallelized, the critical path is about 5 hours.

## Task graph

Nodes on the critical path are marked `*`. Everything else runs concurrently.

```
YOU (start now, runs alongside everything)
  U1  Rotate Anthropic + Arize keys ............ P0-01
  U2  Decide: git link only, or zip too? ....... NEW-SEC-1

WAVE 1  (no dependencies, all parallel)
* A1  Move docs/ into repo, fix all paths ...... P0-02      40m
  A2  Fix the broken secret-scan procedure ..... NEW-SEC-2  10m
  A3  Iteration cap + graceful fallback ........ P1-05      20m
  A4  Label monitors proposed, add 3 types ..... P1-09      30m
  A5  Enrich appended failure records .......... P1-03      75m
  A6  Emit approval.json from gate() ........... P1-10      40m
  A7  Test suite + pytest dependency ........... P1-06      75m

WAVE 2  (after A1)
* B1  Strip absolute paths ..................... P0-04      20m
  B2  Manifest fields + RUN_INDEX.md ........... P1-12      60m

WAVE 3  (after code settles: A3, A5, A6, B1)
* C1  Personal repo, commit, repoint origin .... P0-03 + NEW-SEC-3  35m
  C2  CI quality gates before the loop ......... P1-07      45m
  C3  Add --propose-with-llm to CI ............. P1-02      15m

WAVE 4  (after C1, so the manifest binds a clean sha)
* D1  THE unified end-to-end loop run .......... P1-01      30m
      One command. Produces the single artifact the panel asked for.

WAVE 5  (after D1 yields real numbers)
* E1  Reconcile 11 doc contradictions .......... P1-08      95m
  E2  Human calibration labels + agreement ..... P1-04      75m
  E3  Booking-conversion join design ........... P2-01      40m
  E4  Satisfaction/completion attributes ....... P2-02      30m
  E5  Booking-scope disclosure into the deck ... P2-03      15m
  E6  Sampling and trigger tiers ............... P2-04      30m

WAVE 6  (final)
* F1  Prune artifacts, EVIDENCE_INDEX, reviewer page .. P1-11  50m
  F2  Rebuild or delete Archive.zip ............ NEW-SEC-1  15m
* F3  Corrected secret scan, tag, push ......... gate       15m
* F4  Rehearse the demo and the fallback ....... gate       30m
```

Critical path: A1 → B1 → C1 → D1 → E1 → F1 → F3 → F4, about 5 hours.

## Ordering constraints that are easy to get wrong

1. **A1 before everything that writes an artifact.** Moving `docs/` after new
   evidence is generated means fixing paths twice.
2. **C1 before D1.** The whole point of P1-12 is that every result binds to a
   clean commit. Running the loop first produces another manifest with a dirty
   or non-identifying sha.
3. **D1 before E1.** The doc reconciliation must cite numbers from the final
   run, not the superseded ones. Writing docs first guarantees rework.
4. **A2 before F3.** The final secret scan must use `command grep`, or it will
   report clean regardless of what is actually in the tree.
5. **Do not retro-edit the 13 existing manifests.** `git_dirty` and
   `evaluator_version` for those runs cannot be honestly recovered now.
   Post-hoc rewriting is exactly the fabrication `CLAUDE.md` forbids. Write a
   forward-looking `RUN_INDEX.md` instead and mark the old runs as they are.
6. **The baseline at `docs/baseline/2026-07-19` stays immutable.** Moving the
   directory preserves bytes; editing its contents does not. Move, never edit.

## Beyond the brief

Gap-closing gets to parity. These five make the submission memorable, and every
one is already true in the repo, so none of it is new work beyond framing.

1. **First-failure attribution as a named artifact.** Nick's single most specific
   ask was "where in the chain did it go wrong." Eval results already carry an
   `attribution` field. Having D1's report emit an explicit causal chain per
   failed trace (user turn, first bad span, downstream symptom, attributed
   component) converts an implementation detail into the thing he asked for.

2. **The frontier-model inversion.** Sonnet 5 and Opus 4.8 fabricate *more* than
   Haiku on the shipped prompt (E1 88%, E5 57-62%) because they **obey** the bad
   three-line prompt that Haiku ignores. Under the fixes, all models reach 100%.
   This reframes "should we upgrade the model?" into "fix the prompt first, then
   model choice is purely a cost decision." Counterintuitive, measured, and it
   answers Nick's model-comparison question with a better question.

3. **Evaluating your own evaluators.** `docs/EVAL_ADJUDICATION.md` records three
   adjudicated false positives in your own graders. Almost nobody validates their
   measurement instrument. Show it.

4. **Deliberate non-fixing.** Four of six known defects are left unfixed with
   severity and owner. The skill on display is prioritization, not bug count.

5. **NEW-SEC-2 as a live trust demonstration.** "My secret scan reported clean.
   It was lying, because the shell aliased `grep` to a gitignore-aware tool, so
   the scan structurally could not see `.env`. I found it by diffing against
   `command grep`." For a Forward Deployed role this says more about how you
   verify than any passing test does.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Key rotation blocks the D1 run (new key not yet in `.env`) | Medium | Do U1 first; D1 is the only step that needs live credentials |
| D1 surfaces a regression late in the day | Medium | Run D1 against the existing baseline spans, which are known-good; candidate deltas are already measured in `COMPARISON.md` as a fallback |
| Doc reconciliation (E1, 95m) overruns | High | It is the longest non-parallel task. Split the 11 contradictions across parallel agents by file |
| Moving `docs/` breaks a path nobody grepped for | Medium | After A1, run the full loop once locally before C1 commits |
| Rotating the Arize key orphans the 12 runs already pushed to AX | Low | Rotation changes ingest credentials, not stored data. Verify by SDK read-back after rotation |

## Open questions for you

1. **Has `Archive.zip` been sent to anyone?** If yes, the three keys are already
   compromised and rotation is mandatory rather than precautionary. Either way
   the remediation is identical, so this does not block starting.
2. **Delivery channel: git link only, or link plus zip?** The brief asks for a
   link. If a zip is not required, deleting `Archive.zip` closes NEW-SEC-1
   outright instead of rebuilding it.
3. **P1-04 human labels.** Labeling 99 rows yourself is honest only if the sheet
   records that the labeler was the candidate, not Anne's team. Confirm you want
   that, versus presenting the judges as monitor-only and uncalibrated.

## Definition of done

Security: keys rotated; archive resolved; **secret scan re-run with `command grep`** and clean.
Repository: personal origin; clean tree; docs inside the repo; no absolute paths; tagged.
Loop: one run directory containing all 7 stages, first-failure attribution, and a machine-readable `approval.json` that no automation can write.
Quality: pytest suite green; CI gates ordered before the loop; iteration cap proven by a test.
Docs: zero contradictions; implemented and proposed clearly separated; monitors labeled proposed.
Evidence: every number in the deck traceable to one manifest bound to the tagged commit.
