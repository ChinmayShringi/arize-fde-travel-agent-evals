# Eval Calibration Record: v1 to v1.2

Deterministic evals need calibration exactly like judges do. First scoring of the
four experiment runs surfaced three false positives; each was adjudicated against
the actual reply, the rule was fixed, and every run was re-scored offline (no new
API spend; spans are immutable, scores are recomputable). Original v1 scores are
preserved in each run's evals-v1/ directory and docs/experiments/COMPARISON-evalv1.md.

## Findings

| # | Flag (v1) | Adjudication | Fix (v1.2) |
|---|---|---|---|
| 1 | "$725 (invention)" in the multi-turn Miami reply | JetBlue $189 + hotel total $536 = $725: legitimate cross-item sum | Derivation rule extended to sums of two grounded option prices |
| 2 | "$4 (invention)" in the Chicago-Denver reply | Fare delta $152 - $148 = $4 ("just $4 more"): legitimate arithmetic | Derivation rule extended to differences of two grounded prices |
| 3 | "Hotel Lumiere (invention)" under candidate A | The tool returned the hotel; the model restyled "Hotel" as the French "Hotel" with a circumflex, defeating accent-sensitive matching | Diacritic folding (NFKD strip) applied to both reply mentions and grounding text |

Guard on the guard: only price-like grounded numbers (>= $50) seed the derivation
and only two operands combine, keeping the false-negative surface small; a probe
value not derivable from grounded prices still flags (unit-checked).

## Effect on results

- Control E1: 31/33 (94%) v1 -> 33/33 (100%) v1.2. The shipped model does not
  fabricate on this dataset; the v1 "improvement" candidate A appeared to deliver
  on E1 was an artifact and is gone in v1.2. The honest deltas that remain:
  E2 11% -> 100% (tool fix), latency and cost improvements, E1 held at 100%.
- No other eval changed.

## Why this is presented rather than hidden

The adjudication workflow (score, inspect failures, adjudicate against raw traces,
fix the rule, re-score, keep the audit trail) is the same loop An's team would
own for judge calibration. Showing a deterministic eval going through it proves the
workflow on real data and prevents a +6pp claim that would not have survived a
panel question.
