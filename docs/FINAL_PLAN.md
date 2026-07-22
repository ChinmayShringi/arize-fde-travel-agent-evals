# Engagement Record: Arize FDE Interview 2

## STATUS: THIS IS A RECORD, NOT A PLAN

**Nothing in this document is an open action item.** It was originally written on
2026-07-16 as a forward-looking plan with a Day 0 to Day 6 calendar and a blocker
list. The build finished on 2026-07-21. The document has been rewritten as a record
of what was decided, why, and what actually happened.

Two things are still genuinely unresolved, and they are isolated in the last section
("Genuinely open items") so they cannot be confused with the rest. Everything else
below is history or delivered state.

Where a number appears, it is measured and the file it came from is named. Where a
number was never measured, it says TBD and says why. Presentation date: 2026-07-22.

Prior forms of this document consolidated `BUILD_PLAN.md` and adjustments after review
of the official brief (`US_FDE_Interview_Screen.pdf`) and a four-lens adversarial audit.
Repo findings verified by computation: `docs/verification/DAY0_FIXTURE_CHECKS.md`.

---

## 1. Deliverables, and their delivered state

The brief grades three things.

| Deliverable | State | Where it lives |
|---|---|---|
| Working demo: the agent with the automated feedback loop around it | **Delivered.** Seven-stage loop, one entrypoint | `scripts/feedback_loop.py`; runs under `docs/loop-runs/` |
| Customer-facing presentation | **Delivered** | `docs/PRESENTATION.md` |
| Codebase link | **Delivered.** Committed and pushed | commit `061307e`, tag `interview2-demo-v1`, origin `github.com/ChinmayShringi/arize-fde-travel-agent-evals` (private); the Arize source repo is now the `upstream` remote. Pre-share checks in `docs/CODEBASE_LINK_CHECK.md` |

Graded core requirements and where each is evidenced:

| Requirement | State | Evidence |
|---|---|---|
| Tracing (AX or Phoenix) | Implemented | `agent/tracing.py` (arize-otel + OpenInference), spans exported to disk under `docs/baseline/` and `docs/experiments/`, and uploaded to Arize AX (`scripts/push_to_arize.py`) |
| Evaluation, justified by Interview 1 | Implemented | 11 evals, `evals/` (section 5 below) |
| Automation (repeatable process, any orchestrator) | Implemented | `scripts/feedback_loop.py`, seven stages; scheduling workflow committed at `.github/workflows/feedback-loop.yml` |
| Skills usage: which Arize/Phoenix tooling, how it helped, what we would automate further | Implemented | `docs/SKILLS_LOG.md` |

One qualification on automation, stated so no one overreads it: the GitHub Actions
workflow file is committed, but `gh run list --repo ChinmayShringi/arize-fde-travel-agent-evals`
returns **zero runs** as of 2026-07-21. The scheduler is configured; it has never
executed on GitHub. Every loop run captured in this repo was invoked locally.

Test suite: **191 tests collected** (`uv run pytest --collect-only -q`), `pytest` declared
as a dev dependency in `pyproject.toml`.

One loop run, `docs/loop-runs/interview2-final/`, was still executing when this record
was written on 2026-07-21. **TBD: fill its numbers from the final loop run.** Nothing in
this document depends on it. Two earlier loop runs are complete on disk and each carries
a `loop_report.md`, a `proposal.md`, a curated dataset copy, and its eval output:
`docs/loop-runs/llm-propose-2026-07-19/` and `docs/loop-runs/selftest-2026-07-19/`.

---

## 2. What the numbers actually say

The original plan drafted a success story with `TBD-baseline` and `TBD-result`
placeholders for groundedness, to be filled from real runs. They are filled here, and
the honest answer is not the one the plan anticipated.

**The primary groundedness metric never moved, because it was never failing.**

| Metric | Frozen baseline | control-v0 | candidate-AB-combined | Source |
|---|---|---|---|---|
| E1 `fabricated_entity` | 23/23 = **100%** | 33/33 = **100%** | 33/33 = **100%** | `docs/evals/baseline-2026-07-19/summary.md`; `docs/experiments/COMPARISON.md` |
| E2 `flight_direction` | 0/6 = **0%** | 1/9 = **11%** | 8/8 = **100%** | same |

So the correct claim is: **E1 groundedness was 100% before the fixes and 100% after.
The measured improvement is E2 flight direction, from 11% on the control to 100% on the
tool fix, a +89pp delta recorded in `docs/experiments/COMPARISON.md`.** Saying
"groundedness improved from X to Y" would be false on this traffic.

Why that is a better story rather than a weaker one: E2 is the case where the reply
looks perfectly grounded to any reply-level check, because every flight it names really
does exist in the fixtures. Only span-level attribution places the fault at the tool
rather than the model. A groundedness number alone would have shown 100% and reported
nothing wrong. This is exactly the "first mistake in the chain" argument the brief asks
for, and it is the reason the eval suite is attribution-aware.

Two caveats that must be said out loud rather than buried:

1. **The E2 comparison is not strictly paired.** Applicable counts differ across runs
   (6 baseline, 9 control-v0, 8 candidate-AB) because `e2_flight_direction` returns
   `None` when the reply names no flight numbers (`evals/e_grounding.py:207`) or when no
   `search_flights` call carries both an origin and a destination to compare against
   (`evals/e_grounding.py:219`).
   Applicability is decided per trace by what the model actually said, so the denominators
   are not the same set of turns.
2. **`candidate-B-toolfix` regressed E3.** `tool_call_validity` went 24/24 (100%) on the
   control to 22/24 (92%) on candidate B, a -8pp delta, recovering to 23/23 (100%) on
   `candidate-AB-combined`. That regression is in `docs/experiments/COMPARISON.md` and is
   not hidden. It is one of the reasons the combined candidate, not the tool fix alone,
   is the recommended configuration.

Cost, tokens, and latency, from `docs/experiments/COMPARISON.md` (33-turn runs):

| Metric | control-v0 | candidate-AB-combined |
|---|---|---|
| Median latency | 3485 ms | 2724 ms |
| Total tokens | 75,469 | 78,003 |
| Total cost | $0.1098 | $0.1052 |

Total tokens rose 3.4% while cost fell 4.2%. That is not a contradiction: output tokens
are priced 5x input on `claude-haiku-4-5` ($1.00/Mtok in, $5.00/Mtok out), so the mix
matters more than the count. Solving the two-equation system from the totals above gives
roughly 8,580 completion tokens on the control against roughly 6,800 on
`candidate-AB-combined`, which is where the saving comes from. (That split is **derived
arithmetic**, not a directly recorded figure; the recorded figures are the totals.)
**Cost, not raw token count, is the number to quote.**

Frozen baseline telemetry, recomputed from `docs/baseline/2026-07-19/spans.jsonl` for
this document: 23 turns, 78 spans, 22 sessions, 45,057 prompt + 5,598 completion =
**50,655 tokens**, **$0.073047** at haiku rates, median turn latency **2885 ms**
(min 816 ms, max 5524 ms).

---

## 3. Locked decisions and their rationale

These were locked in `CLAUDE.md` before the build and were not relitigated. They are
recorded here with the reasoning, because the reasoning is what transfers.

| Decision | Value | Rationale |
|---|---|---|
| Platform | Arize AX Free | 25k spans/month, includes online evals; sufficient for the engagement |
| Portability | OpenInference / OTel semconv | The same design runs on self-hosted Phoenix with no re-instrumentation |
| Anchor workflow | Planning to itinerary to booking | Nick, Interview 1 |
| Primary failure mode | Groundedness (fabricated hotels, flights, prices) | Luke and Nick, Interview 1 |
| Groundedness method | Deterministic set membership, not a judge | The fixtures are a closed set, so membership is exact, free, and reproducible. A judge here would be strictly worse |
| First automation target | Incorrect tool usage (E3) | Nick: "easiest to implement the automation loop on" |
| Allowed change types | Prompt change; add a tool call; modify a tool call. Low complexity only | Nick: "not just gonna be like a 40 file PR" |
| Fixes shipped | Exactly two: prompt (D-01, `PROMPT_VARIANT=v1`) and `search_flights` direction (D-02, `FLIGHT_TOOL_FIX=1`) | Prioritization is the skill under assessment. Every other defect is detected and left in `docs/BACKLOG.md` with severity and owner |
| Promotion gate | Metric bar **and** human sign-off | Deliberate deviation from Nick; see section 8 |
| Metric bar | 85% (the low end of Nick's range) driving toward 90% | Nick set no threshold: "we don't really have a current threshold... but maybe like 85, 90% would be sufficient". 85 remains the working default because the follow-up question was never sent |
| Model | `claude-haiku-4-5` | Repo default. Never changed as an unmeasured "fix". Alternative models were measured separately, see `docs/MODEL_COMPARISON.md` |
| Orchestrator | Single Python entrypoint, cron-scheduled | The assumption recorded in the plan; it held. AX Airflow provider and CI-triggered evaluation named as scale-up paths |

---

## 4. The eval-to-fix chain, as executed

The brief's central rule is that agent changes are driven by the feedback loop, not by
a separate engineering effort. This is the chain the demo walks, and it is the chain
`scripts/feedback_loop.py` actually implements (stage 5, `propose`, maps clusters to
candidates by `(eval_id, attribution)`).

| Baseline eval failure | Cluster attribution | Proposed fix | Change type (Nick-authorized) | Outcome |
|---|---|---|---|---|
| **Not an eval failure at all.** Prompt-noncompliance, read off the baseline transcripts (see note below the table) | model | D-01 prompt fix, `PROMPT_VARIANT=v1` | Prompt change | Shipped as candidate A. No deterministic eval delta (E1 and E5 were already 100%); its value is prompt compliance and cost, see below |
| E2 flight-direction failures, attributed to the tool span and not the model | tool | D-02 `search_flights` fix, `FLIGHT_TOOL_FIX=1` | Modify a tool call | Shipped as candidate B. 11% to 100% on E2 |
| E3 tool-call validity (bad dates, unknown cities, missing params) | tool | Detection, clustering, backlog entry, proposed schema tightening | Add/modify tool schema (backlog) | Detected, not fixed. First automation target per Nick |
| E4 itinerary day count | tool | None; backlog D-05 | (out of the two-fix budget) | 0% on every run including candidates. Deliberately unfixed |

The honest note on D-01, corrected: an earlier draft of this table claimed D-01 came from
an "E1 fabricated entity + E5 empty-result honesty" cluster on empty tool results. **That
cluster never existed.** Counted directly from
`docs/evals/baseline-2026-07-19-evalv1/results.jsonl`: E1 `fabricated_entity` **23/23
pass, 0 failures**; E5 `empty_result_honesty` **1/1 pass, 0 failures**. The only baseline
failures in that file are E2 (0/6) and E4 (0/2), both tool-attributed. So the loop's
cluster stage had no model-attributed eval failure to hand D-01. D-01 is **not
eval-failure-driven**, and it should not be presented as such: it is the change the
registry *would* map a model-attributed cluster to if one appeared, and on this baseline
none did. `docs/BACKLOG.md` carries the same correction under D-01. What D-01 is actually
grounded in is the transcript finding stated next.

Candidate A also produced **no deterministic eval improvement**
(`docs/experiments/COMPARISON.md`: E1, E3, E5, E6, E7 all d+0pp; E2 unchanged at 11%),
and on its own it cost *more* ($0.1126 vs $0.1098 control). The reason it is still the
right change is in `docs/DAY1_FINDINGS.md` section 4, point 2: the shipped three-line prompt
was being **ignored** by the model, so it provided no control surface at all. D-01
replaces instructions the model refuses with instructions it follows, which is what
makes any future prompt-level tuning possible. That argument is about controllability,
not about a metric delta, and it should be presented that way.

Neither shipped fix is presented as an E3 fix. E3 is the loop's first automation target
precisely because it is cheapest to close the loop on, and its output is detection,
clustering, and a proposed bounded change that then goes through the same experiment gate.

---

## 5. Evaluation portfolio, as built

Eleven evals. Eight are deterministic and free; three are LLM judges. The original plan
listed E1 through E9; E10 and E11 were added during the build and are included here.

**Deterministic (run by `evals/run_evals.py`, no API calls):**

| ID | Name | Module | What it checks | Attribution |
|---|---|---|---|---|
| E1 | `fabricated_entity` | `evals/e_grounding.py` | PRIMARY. Every hotel, flight, and price named in the reply traces to a tool result this turn or in prior context. Exact set membership against the closed fixture set | model |
| E2 | `flight_direction` | `evals/e_grounding.py` | The reply does not recommend a flight whose true fixture route runs backwards relative to what the user asked. Applicable only when the reply names a fixture flight | **tool** |
| E3 | `tool_call_validity` | `evals/e_toolcalls.py` | Tool calls carry valid dates, known cities, and required params. First automation target | tool |
| E4 | `itinerary_day_count` | `evals/e_toolcalls.py` | `create_itinerary` delivers as many days as were requested. Catches the `range(1, num_days)` off-by-one (D-05) | tool |
| E5 | `empty_result_honesty` | `evals/e_grounding.py` | When a tool returns nothing, the reply says so rather than filling the gap | model |
| E6 | `pii` | `evals/e_guardrails.py` | Scans user input and reply for SSNs and Luhn-valid card numbers; matched values are redacted in the result row. Leakage guardrail, so attribution is n/a | n/a |
| E7 | `guardrails` | `evals/e_guardrails.py` | Telemetry thresholds: latency, total tokens, iteration count, computed `cost_usd`. Thresholds set off the measured baseline | n/a |
| **E10** | `conflicting_context` | `evals/e_conflict.py` | **Added during the build.** Within one session, when a later user message supersedes a booking-material value (origin, destination or stay city, or a date), any subsequent tool call that still passes the OLD value is a conflict. Closed-world: candidate cities are exactly the fixture city set; date changes require an explicit change cue so additive multi-date turns never false-positive. Directly answers Luke's ask: "nice to know if we have conflicting information... some way to highlight the conflicting information" | **model** (the correction was in context and was ignored) |

**LLM judges (run by `evals/run_judges.py`, `JUDGE_MODEL` defaults to `claude-sonnet-5`):**

| ID | Name | Module | What it checks |
|---|---|---|---|
| E8 | `clarification_quality` | `evals/judges.py` | Two-sided: penalizes both peppering the user with questions and assuming when booking-material information is genuinely missing |
| E9 | `scope_adherence` | `evals/judges.py` | The reply stays inside travel planning and booking, and hands off visa, refund, and policy questions rather than improvising |
| **E11** | `tone_quality` | `evals/e_tone.py` | **Added during the build.** Scores one reply on four dimensions, all of which must hold to pass: `professional`, `concise`, `no_overpromising` (never claims to have booked, charged, or guaranteed anything the agent cannot actually do), `appropriate_scale`. This is the judge An asked for, to automate what her team spot-checks by hand |

Three properties of the judges that matter for credibility:

- The eval-level `passed` is **recomputed deterministically in Python** from the judge's
  structured booleans. The model's own free-form `passed` is never trusted; it is
  preserved verbatim in `evidence["judge"]` so a reviewer can see the disagreement.
- E11's rubric is explicitly **provisional**. Every result carries
  `evidence["rubric_version"] == "provisional-v1-pending-customer-rubric"`. It is a
  good-faith first-pass encoding of An's bar, not her team's published rubric, and it is
  meant to be replaced by theirs.
- **All three judges are MONITOR-ONLY. None gates a release.** Measured agreement is
  96/96 = 100%, and `docs/JUDGE_CALIBRATION.md` explains at length why that number
  carries almost no information: 93 of 99 rows are "pass", so there is no variance to
  discriminate on, and the Cohen's kappa of 1.000 for E9 and E11 is a degenerate value
  returned by construction. The binding constraint is the absence of negative examples,
  not the judges.

The plan's privacy contingency (if Luke disallowed external judging even on redacted
content, E8 and E9 would degrade to deterministic proxies plus human annotation) was
never triggered, because the follow-up question was never sent. The judges were built
and run. The contingency stands as the fallback if he objects on the 22nd, and the
primary metric (E1 through E7 and E10) is unaffected either way.

---

## 6. Monitoring: specified, not deployed

An earlier version of this document named five online monitor types in a single line and
described them as a Day 3 output. That is superseded. **`docs/MONITORS.md` is the
authority**, and it specifies **eight monitors, of which zero are configured in Arize AX.**

No monitor exists. No alert channel is provisioned. No alert has ever fired.

| # | Monitor | Severity | Threshold grounding |
|---|---|---|---|
| 1 | Groundedness rate (E1) | P0 | Measured |
| 2 | Flight-direction failure rate (E2) | P1 | Measured; expected-red and muted until the fix ships |
| 3 | p95 latency | P2 | Measured |
| 4 | Tokens per session | P2 | Measured, with an explicit TBD to recalibrate against real session lengths |
| 5 | Tool-error rate | P2 | Measured; expected-red and muted until backlog D-07 closes |
| 6 | Iteration-limit / deadline breach rate | P1 | Measured |
| 7a / 7b | PII redaction drift / confirmed leak | P1 / P0 | 7a is TBD pending production traffic; 7b needs no calibration (any occurrence) |
| 8 | Cost per interaction | P2 | Measured per turn; per-session view is TBD |

Why it is a document and not code: the project runs on the AX free tier, which has no
monitors-as-code path. Monitors are created by hand in the web UI, so the honest artifact
is a specification a human executes, and `docs/MONITORS.md` carries that runbook.

The accurate sentence to say on stage is: "Eight monitors are specified, five with
thresholds fully grounded in measured runs, ready to apply in the AX UI." The sentences
that would be **false** are "we have monitoring in place", "the groundedness monitor would
catch that", and "here is the alert firing".

Note for anyone maintaining cross-references: `docs/MONITORS.md` cites this file by line
number (`docs/FINAL_PLAN.md:117-119`) for the five-type list. Those line numbers refer to
the pre-rewrite version of this document. The list they point at is the one in the table
above.

---

## 7. Production readiness

Full treatment is in `docs/PRODUCTION_READINESS.md`. This is the checklist coverage,
recorded so the mapping to the brief's nine items is auditable.

- **Deployment architecture:** sync serving separated from async eval, queue, sampling.
- **Environment configuration:** config via env vars; `.env` for local development only.
- **Secrets management:** service keys not user keys, least privilege, rotation.
- **Error handling:** eval-pipeline failure behavior, retries, dead-letter, partial-run
  semantics, defined behavior when the grader API errors. No silently dropped evaluations.
- **Logging and tracing:** OpenInference spans, redaction at source (`agent/redaction.py`,
  `docs/PII_BOUNDARY.md`), retention tiers.
- **Monitoring and alerting:** the eight monitors of section 6, routed by severity
  (P0 fabricated inventory and confirmed PII leak; P1 coverage, scope, loop breach,
  redaction drift; P2 telemetry and cost). Proposed routing; no channel exists yet.
- **Resource usage:** span budget tracked against the 25k/month free cap; per-run token
  and cost accounting recorded in E7 evidence.
- **Scalability:** to the brief's millions-per-day framing; sampling strategy for judges.
- **Cost, reliability, rollback:** canary lanes by tag; rollback is the versioned prompt
  and tool config; same human gate as promotion; triggered by monitor breach on the
  primary metric.

Two repo-specific readiness items that were in the plan as future work have since changed
state, and the change is material:

- **D-10, unbounded agent loop.** The shipped `agent/loop.py` was `while True` with no
  iteration cap and no timeout. It now enforces `MAX_AGENT_ITERATIONS` (default 8) and
  `AGENT_DEADLINE_SECONDS` (default 60) from `agent/config.py:15-16`, emits an
  `agent.limit_breached` span attribute on breach (`agent/loop.py:155`), sets span status
  ERROR, and returns a truthful fallback that never fabricates itinerary content.
  Monitor 6 keys on that attribute.
- **D-11, in-process session state.** `agent/session_store.py` now exists, and
  `DictStore.get` no longer returns an internal list by reference, so both backends have
  identical semantics. The multi-worker externalization is still open work, and remains
  in `docs/BACKLOG.md`.

---

## 8. The deviation from the customer, stated deliberately

Nick asked for failures to auto-append to the eval dataset with no human gate.

**What was automated:** collect, evaluate, cluster, curate, propose, experiment. All six
run end to end with no human in the path.

**What was gated:** promotion to production. Stage 7 (`gate`) also runs automatically,
but the only decision it is capable of writing is a pending one.
`scripts/feedback_loop.py` stage 7 always
writes `approval.json` with `decision: "pending_human_review"` and `reviewer: null`.
`scripts/approval.py` enforces this: it raises if the loop attempts to write a reviewer
or a decision time (`scripts/approval.py:162-163`). **There is deliberately no code path
by which the loop can self-approve.**

This is a recommendation, not a misunderstanding of the ask, and it must be presented as
one. The argument is the calibration data in `docs/JUDGE_CALIBRATION.md`: the judges have
seen essentially no failing examples, so their apparent 100% agreement is uninformative.
Gating on an uncalibrated judge would be worse than not gating. The gate is meant to lift
once the judges have negative examples to calibrate against.

The loop also never mutates the committed dataset. It curates a copy under the run
directory and a human promotes it. Appended failure cases are fully replayable: full
multi-turn messages, assistant reply, tool calls, tool outputs, failed eval ids, failure
reasons, source trace and session ids, review status, and the PII-redaction flag.
Deduplication hashes the full message list plus failure type.

---

## 9. Risks, and how each was actually handled

| Risk | Mitigation as planned | What happened |
|---|---|---|
| AX free-tier retention shorter than the demo window | Export everything to disk at capture time | Held. Every trace, score, and explanation is on disk under `docs/baseline/`, `docs/experiments/`, `docs/evals/`. The demo does not depend on AX being up |
| Judge calibration overruns the weekend | Pre-designated scope cut; E1 through E7 carry the primary metric | Not needed as a cut, but the outcome was worse than a cut in one sense and better in another: the judges were built and run, and calibration then showed they cannot gate. Recorded honestly in `docs/JUDGE_CALIBRATION.md` |
| Luke vetoes external judging on redacted content | E8/E9 degrade to deterministic proxies plus human annotation | Never triggered; the follow-up was not sent. Contingency stands |
| Live demo does not reproduce a failure | Replay the captured baseline trace from disk | Capability exists (`scripts/replay_spans_to_arize.py`, plus the disk exports). Rehearsal is the presenter's task |
| 25k span/month budget | Track usage in the resource line | Never came close. 14 span files captured, 13 non-empty, **1,505 spans in total** (78 for the 23-turn baseline; 112 to 144 per 33-turn experiment run). Counted with `wc -l` over every `spans.jsonl` under `docs/baseline/` and `docs/experiments/` |
| API key and credits | Confirm early; haiku is cheap | Resolved. The full baseline run cost $0.073 |
| Interview 1 quotes not re-verifiable (no transcript on disk) | Chinmay confirms or supplies the transcript; check the PM's name spelling before sending anything | **Still open.** See section 11 |

One risk that was not on the original list and should have been: **the primary metric
being already green at baseline.** E1 was 100% before any fix. A plan that had promised a
groundedness improvement number would have had nothing to show. What saved it was
building attribution-aware evals rather than a single reply-level groundedness score.
That is the transferable lesson.

---

## 10. How the week was sequenced (history, not a schedule)

Preserved because the sequencing is itself part of the method: baseline before any edit,
evals before any fix, experiments before any promotion. **None of these dates is
upcoming.** All are in the past.

The Day 0 through Day 6 labels below are the **original plan's intended sequencing**,
kept because the order is the point. Two dates are verifiable from artifacts rather than
from the plan, and only those two are asserted as fact:

- The surviving baseline was captured **2026-07-19T15:27:57Z**
  (`docs/baseline/2026-07-19/manifest.json`), at `git_sha 0080b11`, 23 turns, 78 spans,
  22 sessions. An invalidated capture is retained beside it at
  `docs/baseline/2026-07-19-INVALID-stale-server/` and holds 0 spans.
- The repo was committed and tagged as `061307e` / `interview2-demo-v1`.

Everything else in the table is the plan's sequencing, not a timestamped claim.

| Day | Intended date | Output |
|---|---|---|
| 0 | Thu Jul 16 evening / Fri morning | Environment ready; fixture verification (`docs/verification/DAY0_FIXTURE_CHECKS.md`); AX signup; smoke test |
| 1 | Fri Jul 17 | Instrumentation, additive only, then the immutable baseline capture. Findings in `docs/DAY1_FINDINGS.md` |
| 2 | Sat Jul 18 | Versioned golden dataset; E1 through E7 implemented; baseline scored |
| 3 | Sun Jul 19 | E8 and E9 judges plus hand-labeled calibration; monitor specification. Baseline artifacts frozen under `docs/baseline/2026-07-19/` |
| 4 | Mon Jul 20 | Automation loop: collect, evaluate, cluster, curate, propose, experiment, gate |
| 5 | Tue Jul 21 | Experiments: control-v0 vs candidate A vs candidate B vs candidate AB, same dataset and evals (`docs/experiments/COMPARISON.md`). E10 and E11 added. Blind judge calibration. Monitor numbers recomputed and corrected. Loop hardening (iteration cap, deadline, replayable failure cases, `approval.json`). Test suite. Repo committed and tagged |
| 6 | Tue evening / Wed morning | Production plan, deck, skills log, backlog, codebase-link prep, rehearsal |

The one structural note worth carrying forward: **hard rule 1 was to capture the baseline
before touching anything.** That rule is why the E1-was-already-100% finding is credible
rather than an excuse. The baseline is frozen, immutable, and predates every fix.

---

## 11. Genuinely open items

Everything above is closed. These are not.

1. **The follow-up email to the customer has not been sent.** `docs/FOLLOWUP_QUESTIONS.md`
   is at **DRAFT v2** and is explicitly marked "Chinmay reviews and sends. Never sent by
   the assistant." Its pre-send checklist is also unticked. Three consequences follow and
   they should be acknowledged on stage rather than papered over:
   - The metric bar is the working default of **85%**, not a customer-confirmed number.
   - The PM's name is unreconciled: "An" in the playbook panel list, "Anne" in the session
     notes and in `CLAUDE.md`. Verify against the calendar invite before addressing her.
   - The human-approval gate has not been disclosed to Nick in writing in advance. It will
     be argued live on the 22nd instead, which is a harder position than pre-planting it.
2. **Interview 1 quotes are not independently re-verifiable.** No transcript is on disk.
   Every quote attributed to Nick, An, or Luke in this repo traces to session notes, not to
   a recording. If a panelist disputes a quote, concede the sourcing immediately.

Items that were on the old blocker list and are now **resolved**, recorded so nobody
re-opens them: `ANTHROPIC_API_KEY` (resolved; the baseline and every experiment run
were captured with real API calls), Arize AX signup (resolved; datasets and 697 eval
labels were uploaded and read back, per `docs/SKILLS_LOG.md`), and the orchestrator choice
(the override window closed on Jul 19 with the single-Python-entrypoint decision standing).

---

## Appendix: demo flow

Twelve beats, plus a fallback. Recorded here as the plan of record for the walkthrough;
the authoritative deck is `docs/PRESENTATION.md`.

Customer objective in their words; live Denver-hotel behavior; the trace showing an empty
tool result and the reply that follows; root cause in the three-line prompt; Tokyo to LA
showing the tool lying to the model, which is the first mistake in the chain; the eval
suite catching both; the loop curating and proposing; the experiment table; before and
after; production design; backlog; requirement-to-component map.

Fallback: if a live run does not reproduce a failure in front of the panel, replay the
captured baseline trace from the disk export. Hard rule 4 guarantees the export exists.
