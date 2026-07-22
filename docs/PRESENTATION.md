# Interview 2 Presentation: The System Around Your Travel Agent

Customer-facing deck, July 22, 2026. One section = one slide. Every number traces
to an artifact in this repo; bracketed pointers are the receipts, live-openable
during the demo.

## 1. What you asked for, in your/ words

- Nick: booking conversion up at least 50% over the next year (the business goal;
  groundedness is our leading proxy until production booking outcomes exist); an
  automated improvement loop; "where in the chain did it go wrong so that we can
  start from the very first mistake"; incorrect tool usage as the first automation
  target; token consumption kept on the rails.
- An: the manual spot-checking her team does today, automated.
- Luke: answers grounded in tool calls; no hallucinating around API failures; PII
  never sent to the model provider; the homegrown orchestration stays.

## 2. What we built around the agent (unchanged agent at the center)

Trace everything -> evaluate everything -> curate failures -> propose bounded fixes
-> experiment -> human-approved promotion. Local demo, production design included.
[README sections; agent diff is instrumentation-only at defaults]

## 3. Live demo beat 1: the trace

One turn, one trace: root span, model spans (tokens), tool spans (inputs, outputs,
result counts), session linkage, prompt and agent version on every span. Dual
export: Arize AX + local JSONL that survives any retention window. Every root span
carries its E1-E9 scores as eval labels, visible in the UI.
[AX project travel-agent, 23/23 baseline traces + all 4 experiment runs; docs/baseline/2026-07-19]

## 4. Live demo beat 2: the flight that does not exist

"I need to get from Tokyo to Los Angeles on May 2, 2026." The agent confidently
recommends ANA NH 105 with times, price, and a remark about crossing the date line.
There is no Tokyo to LA flight in your inventory. NH 105 flies the opposite
direction. [docs/baseline run_log; E2 evidence rows]

## 5. The first mistake in the chain is not the model

The tool span shows why: search_flights matches cities as an unordered set and
strips origin and destination from what it returns. The model was handed a
backwards flight with no way to detect it. A reply-level hallucination check calls
this grounded; span-level attribution calls it what it is: a tool defect.
[agent/tools.py:33-44 (shipped branch; lines 14-24 are the env-gated fix); E2 attribution=tool on 6 of 6 baseline failures]

## 6. Predicted vs measured: why we trace before we fix

From code reading we predicted 5 failure modes. Measurement confirmed 2 and
overturned 3: your model already refuses the prompt's worst instructions (it asked
clarifying questions and disclosed empty results despite being told not to). The
prompt's real defect: it is so misaligned the model ignores it, so it provides no
control surface. [docs/DAY1_FINDINGS.md]

## 7. The evaluation portfolio

Deterministic first (your fixtures are a closed set; groundedness is exact set
membership, free and reproducible): E1 fabricated entity, E2 flight direction,
E3 tool-call validity, E4 itinerary day count, E5 empty-result honesty, E6 PII,
E7 telemetry guardrails. Judges only where judgment is required: E8 clarification
quality (two-sided by design: you asked for questions AND complained about too
many), E9 scope adherence. Judge verdicts are recomputed deterministically from
structured facts; calibration sheet ships with an empty human-label column for
An's team. [evals/; docs/evals/baseline-2026-07-19; calibration sheet; all E1-E9
scores live on AX spans (697 labels); dataset golden-dataset-v1-2026-07-19 in AX]

## 8. Baseline scorecard (23 shipped-traffic turns, frozen)

E1 100%, E3 100%, E5 100%, E6 100%, E7 100%, E8 100%, E9 100%: and E2 0%, E4 0%.
Read together: your agent is honest on this traffic, and 100% of its flight
recommendation sets contained a wrong-direction flight while every itinerary was
short one day: all tool faults a spot check would score as fine.
[docs/evals/baseline-2026-07-19/summary.md]

## 9. The loop, mechanically

COLLECT -> EVALUATE -> CLUSTER (by eval and attribution) -> CURATE (failures append
to the versioned dataset) -> PROPOSE (bounded candidates mapped from failure
clusters) -> EXPERIMENT -> GATE. Run on the baseline it clustered 6 E2/tool and
2 E4/tool failures, appended them (v1 -> v2), proposed exactly candidate B, sent
E4 to backlog (no change type authorized), and blocked promotion pending PM
approval. Nightly via GitHub Actions; Airflow provider is the scale-up path.
[docs/loop-runs/selftest-2026-07-19/proposal.md]

## 10. The two bounded fixes the loop proposed

Candidate A (prompt): grounding rules, honest empty-result handling, one
consolidated clarifying question, current date, scope hand-offs. Candidate B
(tool): ordered route match, direction fields restored. Both env-gated; defaults
are byte-identical to shipped behavior; rollback is a flag flip.
[docs/proposals/CANDIDATES.md]

## 11. Before and after (golden dataset, 31 conversations, same evals)

| | control | A (prompt) | B (tool) | A+B |
|---|---|---|---|---|
| E1 groundedness | 100% | 100% | 100% | 100% |
| E2 flight direction | 11% | 11% | **100%** | **100%** |
| Median latency | 3485 ms | 2992 ms | 2741 ms | **2724 ms** |
| Cost per full run | $0.1098 | $0.1126 | $0.1071 | **$0.1052** |

The +89pp on E2 is the tool fix; the prompt alone cannot touch it because the
model never sees the direction. E4 stays 0% by design: detected, backlogged, not
authorized. One E3 dip (92%) in the B run was a date-format slip the suite caught:
run-to-run variance, clean in A+B. [docs/experiments/COMPARISON.md]

## 11b. "Which model works best": your question, measured

Same golden dataset, six cells: Haiku 4.5 / Sonnet 5 / Opus 4.8, each on the
shipped prompt and on the fixed config. On the SHIPPED prompt the frontier models
get WORSE: they invented real Denver and Austin hotels with prices after the tool
returned empty (E1 88 percent, empty-result honesty 57-62 percent, at 5.6x and
25x Haiku's cost). Mechanism: they OBEY the shipped prompt's "always concrete,
never disclose" rules that Haiku ignores; better instruction-following turns a
bad prompt into worse behavior. With the loop's two fixes applied, all three
models score 100 percent on E1/E2/E5, and model choice becomes a legitimate
cost/latency tradeoff (Haiku fixed: $0.105 and 2.7s; Sonnet fixed: 3.9x the cost
for nothing measurable here). A bare model upgrade would have shipped your
nightmare scenario looking like an improvement; the eval gate caught it for under
a dollar. [docs/MODEL_COMPARISON.md; docs/experiments/model-*]

## 12. We also calibrated the evals themselves

First scoring flagged three fabrications; adjudication against raw replies showed
all three were eval artifacts (a price sum, a fare delta, a French accent). Rules
fixed, everything re-scored offline, v1 scores kept as the audit trail. Same
workflow An's team owns for judges. A +6pp groundedness claim died in this step;
that is the point. [docs/EVAL_ADJUDICATION.md]

## 13. Your 85 to 90 percent, made precise

Proposed gate: groundedness (E1) at or above 85% floor on the versioned golden
dataset (90% target), zero fabricated-inventory regressions, plus telemetry
non-regression: as a necessary condition. Promotion additionally requires PM
sign-off until the judges are calibrated against your team's labels: a deliberate
refinement of the fully automatic flow, and the email put it in writing before
today. [docs/FOLLOWUP_QUESTIONS.md; docs/MONITORS.md]

## 14. Production: the same system at millions of requests a day

Sync serving split from async eval, queue between; deterministic evals on 100%,
judges sampled; redaction at source (PII never leaves your process); service keys;
canary lanes by version tag; rollback = flag flip + versioned config; monitors
routed P0/P1/P2. Repo-specifics named: unbounded agent loop, in-process state,
missing auth: with mitigations. Phoenix self-hosted is the residency fallback on
the same OpenInference spans. [docs/PRODUCTION_READINESS.md; docs/MONITORS.md]

## 15. What we deliberately did not fix, and what is next

Backlog with severity, detection, and owner: itinerary off-by-one, ignored dates,
ignored checkout, coverage holes, weather unit bug, and more. Next: your golden
dataset merged when it arrives, judge calibration on An's labels, a tone judge on
her rubric, conflicting-context detection (Luke's ask, seeded by the multi-turn
case), tool retry/backoff, online evals in AX, CI gating on the experiment suite.
[docs/BACKLOG.md; docs/SKILLS_LOG.md]
