# Eval Calibration Record: v1 to v1.3

Deterministic evals need calibration exactly like judges do. First scoring of the
four experiment runs surfaced three false positives; a fourth was found later,
while preparing the final deck, in the final loop run. Each was adjudicated
against the actual reply, the rule was fixed, and every affected run was
re-scored offline (no new API spend; spans are immutable, scores are
recomputable). Original v1 scores are preserved in each run's evals-v1/ directory
and docs/experiments/COMPARISON-evalv1.md; the superseded v1.2 scores of the
final loop run are preserved in its evals-v1.2/ directories.

## Findings

| # | Flag | Adjudication | Fix |
|---|---|---|---|
| 1 | "$725 (invention)" in the multi-turn Miami reply | JetBlue $189 + hotel total $536 = $725: legitimate cross-item sum | v1.2: derivation rule extended to sums of two grounded option prices |
| 2 | "$4 (invention)" in the Chicago-Denver reply | Fare delta $152 - $148 = $4 ("just $4 more"): legitimate arithmetic | v1.2: derivation rule extended to differences of two grounded prices |
| 3 | "Hotel Lumiere (invention)" under candidate A | The tool returned the hotel; the model restyled "Hotel" as the French "Hotel" with a circumflex, defeating accent-sensitive matching | v1.2: diacritic folding (NFKD strip) applied to both reply mentions and grounding text |
| 4 | "Hotel Options (invention)" in the final loop run's control arm | "## Hotel Options" is the markdown section heading above the hotel list, not a hotel. The two hotels under it were tool-returned and passed | v1.3: markdown section-label headings are removed before hotel-mention extraction |

Guard on the guard (findings 1 and 2): only price-like grounded numbers (>= $50)
seed the derivation and only two operands combine, keeping the false-negative
surface small; a probe value not derivable from grounded prices still flags
(unit-checked).

## Finding 4 in detail (v1.3)

Found on the day before the presentation, while checking every number that was
going into the deck.

**What was flagged.** One E1 failure in
`docs/loop-runs/interview2-final/experiments/control/evals/results.jsonl`, on
`"Put together a 5-day itinerary for Paris, arriving June 10, 2026."`

```
reason:   Reply names option(s) no tool returned: Hotel Options (invention).
evidence: {"fabricated": [{"entity": "Hotel Options", "type": "hotel", "kind": "invention"}]}
```

**Why it was wrong.** The reply contained:

```
## Hotel Options

1. **Hotel Lumiere** - $385/night (4.7 rating)
2. **Rive Gauche Hotel** - $245/night (4.0 rating)
```

Both hotels were returned by `search_hotels` and were correctly scored as
grounded. The Title-Case run tokenizer in `evals/entities.py` also matched the
heading itself, because "Hotel Options" contains the hotel keyword "hotel". Same
class as findings 1 to 3: the reply was correct and the rule was not.

**The fix.** `evals/e_grounding.py` now masks markdown section-label headings
before extracting hotel mentions (`_mask_section_headings`, `_is_section_label`,
`_hotel_mentions`). A heading is treated as a label only when it is both:

1. a markdown ATX heading line (`^#{1,6} `), and
2. built from a generic document-structure noun (options, recommendations,
   choices, picks, summary, results, and similar).

The masking substitutes spaces of equal length, so every character offset the
price-attachment rule computes stays valid.

The fix is deliberately not "ignore anything starting with Hotel". That would
have disabled the primary eval of the project. Both directions are pinned in
`tests/test_grounding_headings.py`:

- `## Hotel Options` is not a candidate entity, and the grounded hotels and
  prices beneath it are still recognised.
- An invented `Hotel Bellevue` that no tool returned is still flagged, in the
  body **and** as a heading of its own, because "Bellevue" is not a
  structure noun. Keying on structure alone would have missed that one.

## Effect on results

v1 to v1.2, four-experiment comparison:

- Control E1: 31/33 (94%) v1 -> 33/33 (100%) v1.2. The shipped model does not
  fabricate on this dataset; the v1 "improvement" candidate A appeared to deliver
  on E1 was an artifact and is gone in v1.2. The honest deltas that remain:
  E2 11% -> 100% (tool fix), latency and cost improvements, E1 held at 100%.
- No other eval changed.

v1.2 to v1.3, final loop run (`docs/loop-runs/interview2-final/`), re-scored over
the already-captured spans of both arms:

| Eval | Arm | v1.2 | v1.3 |
|---|---|---|---|
| E1 | control | 32/33 (97%) | 33/33 (100%) |
| E1 | candidate-B-flight-tool-fix | 33/33 (100%) | 33/33 (100%) |

- **The E1 delta is 0pp, not +3pp.** The +3pp in the first cut of
  `comparison.md` was the artifact: the control was wrongly marked as
  fabricating, and the candidate passed the same case only because that reply
  happened not to list hotels at all. Presenting it as a groundedness gain would
  have been an overclaim.
- Exactly one result row changed across both arms (control trace
  `0x26b355e36ad8f43a2146f8027ed3f612`, E1, fail -> pass). Every other eval, both
  arms, is byte-identical to v1.2; the superseded scores are kept in each arm's
  `evals-v1.2/`.
- The claim that survives is E2 flight_direction: control 1/9 (11%) ->
  candidate 8/8 (100%), a +89pp delta from the tool fix, unaffected by this
  adjudication.

Other captured runs carrying the same false positive (left unedited, they are
captured evidence; caveat them if they are shown):

- `docs/experiments/model-opus-4-8/evals/results.jsonl` and its second scoring
  copy `docs/evals/e10-scoring-model-opus-4-8/results.jsonl`: one E1 row flagged
  "Hotel Recommendations (invention)" on the same Paris itinerary prompt, again a
  `##` heading. E1 there reads 29/33 (88%) as captured; re-scored under v1.3 it
  is 30/33 (91%).
- No other current-scoring run is affected. Verified by re-scoring every captured
  `spans.jsonl` in `docs/` under v1.3 into a scratch directory and diffing row by
  row against the committed results. The remaining E1 failures in the
  model-comparison runs are real inventions (Hilton, Marriott, Kimpton, Crawford
  Hotel and similar brands that no fixture returned) and still fail under v1.3.
  The `evals-v1/` directories differ, as they always did, because they predate
  findings 1 to 3.

## Why this is presented rather than hidden

The adjudication workflow (score, inspect failures, adjudicate against raw traces,
fix the rule, re-score, keep the audit trail) is the same loop An's team would
own for judge calibration. Showing a deterministic eval going through it proves the
workflow on real data and prevents a +6pp claim that would not have survived a
panel question.

Finding 4 makes the same point a second time, one day before the presentation,
and costs a headline number: the E1 improvement drops from +3pp to 0pp. It is
still worth taking. A +3pp groundedness gain that a reviewer can dismantle by
reading one reply is worth less than a 0pp E1 next to a +89pp E2 that holds up.
An eval that has never been wrong has never been checked.
