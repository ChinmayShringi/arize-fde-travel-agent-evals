# Experiment Comparison

Control (baseline for deltas): **control-v0**

## Evals

| Eval | Name | control-v0 | candidate-A-prompt | candidate-B-toolfix | candidate-AB-combined |
|---|---|---|---|---|---|
| E1 | fabricated_entity | 31/33 (94%) | 32/33 (97%) [d+3pp] | 32/33 (97%) [d+3pp] | 33/33 (100%) [d+6pp] |
| E2 | flight_direction | 1/9 (11%) | 1/9 (11%) [d+0pp] | 8/8 (100%) [d+89pp] | 8/8 (100%) [d+89pp] |
| E3 | tool_call_validity | 24/24 (100%) | 25/25 (100%) [d+0pp] | 22/24 (92%) [d-8pp] | 23/23 (100%) [d+0pp] |
| E4 | itinerary_day_count | 0/3 (0%) | 0/2 (0%) [d+0pp] | 0/3 (0%) [d+0pp] | 0/2 (0%) [d+0pp] |
| E5 | empty_result_honesty | 4/4 (100%) | 6/6 (100%) [d+0pp] | 5/5 (100%) [d+0pp] | 6/6 (100%) [d+0pp] |
| E6 | pii | 32/33 (97%) | 32/33 (97%) [d+0pp] | 32/33 (97%) [d+0pp] | 32/33 (97%) [d+0pp] |
| E7 | guardrails | 33/33 (100%) | 33/33 (100%) [d+0pp] | 33/33 (100%) [d+0pp] | 33/33 (100%) [d+0pp] |

## Telemetry

| Metric | control-v0 | candidate-A-prompt | candidate-B-toolfix | candidate-AB-combined |
|---|---|---|---|---|
| Median latency (ms) | 3485 | 2992 | 2741 | 2724 |
| Total tokens | 75,469 | 82,301 | 74,422 | 78,003 |
| Total cost (USD) | $0.1098 | $0.1126 | $0.1071 | $0.1052 |
| Mean iterations | 1.73 | 1.76 | 1.73 | 1.70 |

