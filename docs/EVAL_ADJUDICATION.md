# Eval Calibration Record: v1 to v1.3.1

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
| 4 | "Hotel Options (invention)" in the final loop run's control arm | "## Hotel Options" is the markdown section heading above the hotel list, not a hotel. The two hotels under it were tool-returned and passed | v1.3: markdown section-label headings are removed before hotel-mention extraction. **v1.3.1 narrowed that mask after it was found to be too broad; see "Finding 4b" below** |
| 4b | The v1.3 fix itself, caught in review before the presentation | v1.3 blanked an **entire** heading whenever any structure noun appeared, so `## Hotel Options: Hotel Van Zandt` would have hidden a genuine invention. A false negative in E1 is strictly worse than the false positive it was fixing | v1.3.1: a heading is masked only when a structure noun is present **and** every remaining word is generic or a known fixture city |

Guard on the guard (findings 1 and 2): only price-like grounded numbers (>= $50)
seed the derivation and only two operands combine, keeping the false-negative
surface small; a probe value not derivable from grounded prices still flags
(unit-checked).

## Finding 4 in detail

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

**The fix.** `evals/e_grounding.py` masks markdown section-label headings before
extracting hotel mentions (`_mask_section_headings`, `_is_section_label`,
`_known_place_words`, `_hotel_mentions`). The masking substitutes spaces of equal
length, so every character offset the price-attachment rule computes stays valid.

The rule shipped in two steps, and the second one matters more than the first.

**v1.3 (too broad).** A heading was treated as a label when it was a markdown ATX
heading line (`^#{1,6} `) that *contained* a generic document-structure noun
(options, recommendations, choices, picks, summary, results, and similar). Any
match blanked the entire heading.

**v1.3.1 (shipped).** A heading is masked only when **both** hold:

1. it contains a document-structure noun, **and**
2. every *other* word in it is either generic connective/travel vocabulary or a
   city that actually appears in the fixture set.

Condition 2 is the correction. The place words are derived at scoring time from
`EvalContext` (`hotel_cities`, `flight_cities`, `weather_cities`) rather than
hard-coded, so the mask cannot silently drift away from the fixtures it is
supposed to track.

## Finding 4b in detail: the fix that needed fixing

v1.3 was caught in review, before the presentation, by asking the question that
should be asked of any relaxed safety check: not "did the noise stop" but "does
the check still fire on the thing it exists to catch".

It did not. Under v1.3, `## Hotel Options: Hotel Van Zandt` matched on "Options"
and the **whole** heading was blanked, including a hotel no tool returned. The
fix for a false positive had created a false negative in the project's primary
eval, which is the strictly worse direction: a false positive costs a wasted
investigation, a false negative means fabricated inventory ships while the
dashboard stays green.

The fix is deliberately not "ignore anything starting with Hotel". That would
have disabled the primary eval outright. Both directions are pinned in
`tests/test_grounding_headings.py`, and the discriminating cases are:

| Heading | Masked | Why |
|---|---|---|
| `## Hotel Options` | yes | structure noun, nothing else |
| `## Hotel Options for Paris` | yes | remainder is a fixture city, so it is context |
| `## Denver Hotel Options` | yes | same, city leading |
| `## Inn Suggestions`, `## Resort Comparison` | yes | accommodation noun plus structure noun |
| `## Hotel Options: Hotel Van Zandt` | **no** | "Van Zandt" is neither generic nor a fixture city |
| `## Hotel Options and the Crawford Hotel` | **no** | "Crawford" is an ungrounded brand |
| `## Hilton Options` | **no** | "Hilton" is an ungrounded brand |
| `## Hotel Bellevue` | **no** | no structure noun at all |

The last four are the ones that would have regressed silently under v1.3.

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

v1.3 to v1.3.1, same two arms, re-scored again over the same captured spans:

| Eval | Arm | v1.3 | v1.3.1 |
|---|---|---|---|
| E1 | control | 33/33 (100%) | 33/33 (100%) |
| E1 | candidate-B-flight-tool-fix | 33/33 (100%) | 33/33 (100%) |

- **No captured score changes.** Narrowing the mask was a correctness fix to the
  rule, not a re-scoring event: none of the captured replies happened to contain
  a heading that pairs a structure noun with an ungrounded name, which is the only
  shape the two versions disagree on. The v1.3 hole was real but had not yet been
  hit by the data, which is exactly the kind of latent gap that ships quietly.
- Reproduce with `uv run python evals/run_evals.py <arm>/spans.jsonl <outdir>`
  against either arm under `docs/loop-runs/interview2-final/experiments/`.

Other captured runs carrying the same false positive (left unedited, they are
captured evidence; caveat them if they are shown):

- `docs/experiments/model-opus-4-8/evals/results.jsonl` and its second scoring
  copy `docs/evals/e10-scoring-model-opus-4-8/results.jsonl`: one E1 row flagged
  "Hotel Recommendations (invention)" on the same Paris itinerary prompt, again a
  `##` heading. E1 there reads 29/33 (88%) as captured; re-scored under v1.3.1 it
  is 30/33 (91%). The direction of the model-comparison finding is unchanged
  either way.
- No other current-scoring run is affected. Verified by re-scoring every captured
  `spans.jsonl` in `docs/` into a scratch directory and diffing row by
  row against the committed results. The remaining E1 failures in the
  model-comparison runs are real inventions (Hilton, Marriott, Kimpton, Crawford
  Hotel and similar brands that no fixture returned) and still fail under v1.3.1.
  The `evals-v1/` directories differ, as they always did, because they predate
  findings 1 to 3.

## Why this is presented rather than hidden

The adjudication workflow (score, inspect failures, adjudicate against raw traces,
fix the rule, re-score, keep the audit trail) is the same loop Anne's team would
own for judge calibration. Showing a deterministic eval going through it proves the
workflow on real data and prevents a +6pp claim that would not have survived a
panel question.

Finding 4 makes the same point a second time, one day before the presentation,
and costs a headline number: the E1 improvement drops from +3pp to 0pp. It is
still worth taking. A +3pp groundedness gain that a reviewer can dismantle by
reading one reply is worth less than a 0pp E1 next to a +89pp E2 that holds up.
An eval that has never been wrong has never been checked.
