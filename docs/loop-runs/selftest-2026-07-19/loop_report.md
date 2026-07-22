# Feedback Loop Run


## 1. COLLECT

spans file: /Users/chinmay_shringi/Desktop/sar/docs/baseline/2026-07-19/spans.jsonl
traces loaded: 23

## 2. EVALUATE

eval results: /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/evals/results.jsonl
eval summary: /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/evals/summary.md

## 3. CLUSTER

- E2 (flight_direction) attribution=tool: 6 failure(s)
    e.g. 'Find me a flight from New York to Miami on March 12, 2026.'
    e.g. 'What flights are there from San Francisco to Tokyo on April 20, 2026?'
    e.g. "I'm thinking about a weekend in Miami in early August. Any flights from New York on August 7, 2026?"
- E4 (itinerary_day_count) attribution=tool: 2 failure(s)
    e.g. 'Plan a 3-day trip to Chicago for me.'
    e.g. 'Put together a 5-day itinerary for Paris, arriving June 10, 2026.'

## 4. CURATE

curated dataset copy: /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/dataset.curated.json
failing cases considered: 8
dataset version bumped: v1-2026-07-19 -> v2-2026-07-19

## 5. PROPOSE

proposal written: /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/proposal.md
candidates proposed: B
backlog clusters: 1

## 6. EXPERIMENT

skipped (--run-experiments not set).

## 7. GATE

Promotion decision:
- metric deltas: not measured (experiments not run; pass --run-experiments with ANTHROPIC_API_KEY)
- candidates awaiting review: B
- PROMOTION: BLOCKED pending human approval
- approver: PM
- rationale: the loop never mutates agent defaults; candidates stay env-gated (PROMPT_VARIANT / FLIGHT_TOOL_FIX) until a human flips them.

loop report: /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/loop_report.md
