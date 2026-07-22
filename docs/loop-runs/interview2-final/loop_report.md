# Feedback Loop Run


## 1. COLLECT

spans file: docs/baseline/2026-07-19/spans.jsonl
traces loaded: 23

## 2. EVALUATE

eval results: docs/loop-runs/interview2-final/evals/results.jsonl
eval summary: docs/loop-runs/interview2-final/evals/summary.md

## 3. CLUSTER

- E2 (flight_direction) attribution=tool: 6 failure(s)
    e.g. 'Find me a flight from New York to Miami on March 12, 2026.'
    e.g. 'What flights are there from San Francisco to Tokyo on April 20, 2026?'
    e.g. "I'm thinking about a weekend in Miami in early August. Any flights from New York on August 7, 2026?"
- E4 (itinerary_day_count) attribution=tool: 2 failure(s)
    e.g. 'Plan a 3-day trip to Chicago for me.'
    e.g. 'Put together a 5-day itinerary for Paris, arriving June 10, 2026.'

## 4. CURATE

curated dataset copy: docs/loop-runs/interview2-final/dataset.curated.json
failing cases considered: 8 (one per failing trace)
each appended row carries the full user history, the reply, the tool calls and the tool outputs, with review_status 'pending' and expected_behavior null for a human to fill.
dataset version bumped: v1-2026-07-19 -> v2-2026-07-21

## 5. PROPOSE

proposal written: docs/loop-runs/interview2-final/proposal.md
candidates proposed: B
backlog clusters: 1

## 5b. PROPOSE (LLM draft)

surfaces sent to model: agent/tools.py:search_flights, agent/tools.py:create_itinerary
model: claude-opus-4-8 (temperature 0); diff is NEVER applied.
bounded unified diff drafted and written under the draft marker (NOT applied).
draft appended to: docs/loop-runs/interview2-final/proposal.md

## 6. EXPERIMENT

experiment control: ok
experiment candidate-B-flight-tool-fix: ok
comparison written: docs/loop-runs/interview2-final/comparison.md

## 7. GATE

Promotion decision:
- metric deltas: see docs/loop-runs/interview2-final/comparison.md
- quality_delta recorded for: candidate-B-flight-tool-fix
- regressions detected: 0
- candidates awaiting review: B
- git: 061307e (dirty=True)
- decision recorded: pending_human_review (reviewer: null)
- PROMOTION: BLOCKED pending human approval
- machine-readable record: docs/loop-runs/interview2-final/approval.json
- rationale: the loop never mutates agent defaults; candidates stay env-gated (PROMPT_VARIANT / FLIGHT_TOOL_FIX) until a human flips them.

loop report: docs/loop-runs/interview2-final/loop_report.md
