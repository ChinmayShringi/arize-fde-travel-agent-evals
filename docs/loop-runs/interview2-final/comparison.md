# Experiment Comparison

Control (baseline for deltas): **control**

## Evals

| Eval | Name | control | candidate-B-flight-tool-fix |
|---|---|---|---|
| E1 | fabricated_entity | 33/33 (100%) | 33/33 (100%) [d+0pp] |
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


> E1 note: re-scored under evaluator v1.3. The control arm's single flag was the
> markdown heading "## Hotel Options", adjudicated as extractor false positive 4 in
> docs/EVAL_ADJUDICATION.md. Superseded v1.2 scores are preserved in each arm's
> evals-v1.2/. E1 holds at 100 percent on both arms; the real result is E2 +89pp.
