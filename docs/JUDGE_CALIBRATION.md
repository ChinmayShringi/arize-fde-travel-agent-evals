# Judge Calibration: E8, E9, E11

Status as of 2026-07-21. Every number below was computed from files on disk by
`evals/calibration/compute_agreement.py`. No judge was re-run and no paid API
call was made to produce this document.

**Headline, stated before the detail:** measured agreement is 96/96 = 100 percent,
and that number is much weaker evidence than it looks. Two of the three judges
never saw a single failing case in this dataset, so a judge hardwired to return
"pass" would have scored exactly the same 100 percent. The binding constraint on
calibrating these judges is the absence of negative examples, not the judges.
All three stay **monitor-only**. None is fit to gate a release today.

---

## 1. Method

### 1.1 Which run this is based on, and why

The live sheet is built from **`candidate-AB-combined`**.

- `docs/experiments/COMPARISON.md` compares four runs (control-v0, candidate-A-prompt,
  candidate-B-toolfix, candidate-AB-combined). `candidate-AB-combined` is the cell
  the presentation actually recommends: it is the bolded winner on slide 11 of
  `docs/PRESENTATION.md` (E2 100 percent, median latency 2724 ms, $0.1052 per run),
  and slide 10 describes candidates A and B as the two fixes the loop proposed.
  Calibrating the judges on any other run would calibrate them against traffic the
  panel will not be shown.
- It is the only judge run over the recommended configuration that carries all three
  judged evals. `docs/evals/judges-baseline-2026-07-19/` has 46 rows (E8 and E9 only,
  23 traces) and predates E11 entirely, so it cannot calibrate the tone judge at all.
- `docs/evals/judges-candidate-C/` also has 99 rows, but candidate C ("concise") does
  not appear in `COMPARISON.md` or in the presentation. It is used below as a
  *second observation of the same judge*, not as the calibration basis.

Sources joined, all read-only:

| Source | Path | Role |
|---|---|---|
| Conversations | `docs/experiments/candidate-AB-combined/spans.jsonl` | user input and reply, read through `evals/trace_model.py` so the text is byte-identical to what the judge saw |
| Judge verdicts | `docs/evals/judges-candidate-AB/results.jsonl` | the captured verdicts, loaded only after labelling |
| Blind labels | `evals/calibration/blind_labels_candidate_AB.py` | the independent labels |

The captured artifacts under `docs/evals/`, `docs/experiments/` and `docs/baseline/`
were not modified. The live working sheet is a new file at
`evals/calibration/calibration_sheet.csv`.

### 1.2 Labelling was blind, and why that is the whole point

If you read a judge's verdict and then "label" the row, agreement is guaranteed to
come out near 100 percent and the number means nothing. It measures whether you can
copy, not whether the judge is right. So the work was done in this order:

1. **Read the rubric from source first.** `evals/judges.py` for E8 and E9,
   `evals/e_tone.py` for E11. The decision criteria were written out in the labeller's
   own words (reproduced in section 2) before any trace was opened.
2. **Extract conversation content only.** A script pulled `trace_id`, `user_input`,
   `reply`, tool names, tool inputs and tool result counts out of the spans. It did
   not read `results.jsonl` and did not touch the `judge_passed` or `judge_reason`
   columns of any sheet.
3. **Label each of the 99 rows from the rubric alone**, with a one-line reason
   recorded per row. Rows the rubric genuinely does not determine were labelled
   `unsure` rather than forced.
4. **Only then load the verdicts** and compute agreement.

The labels were committed to `evals/calibration/blind_labels_candidate_AB.py` before
step 4, which is what makes the reasons in that file usable as evidence of what the
labeller thought pre-unblinding.

### 1.3 Blindness was broken on 5 of 99 rows. Disclosed, not hidden.

Choosing a source run required reading the three `summary.md` files, and those
summaries enumerate the failing rows by `user_input`. That leaked the verdict for:

- 3 E8 rows (`judges-candidate-AB/summary.md`): the Chicago 3-day trip, the
  Miami to Tokyo "next Friday" flight, the London "next Tuesday" weather.
- 2 E11 rows (`judges-candidate-C/summary.md`): the Japan visa question and the
  7-day Tokyo itinerary.

Each affected row carries a non-empty `blind_contamination` cell in the sheet, and
`compute_agreement.py` reports agreement with those rows excluded as well as
included. This matters more than the raw count suggests, and section 4.6 explains
why: **the 3 contaminated E8 rows are the only rows in the entire dataset that carry
any discriminating signal.**

---

## 2. The rubric criteria used

Quoted or condensed from source. These are the only criteria applied; the labeller
did not add its own standard of quality on top.

### E8 clarification_quality, `evals/judges.py:152-201`

- **Booking-material information** (`judges.py:157-159`): flights need origin,
  destination and a specific date; hotels need destination plus specific check-in
  and check-out; weather needs city plus a specific date.
- **"Specific" is defined narrowly** (`judges.py:161-164`): only an exact calendar
  day counts. `"next Friday"`, `"this weekend"`, `"early August"`, `"for SXSW"` and
  `"next Tuesday"` are named in the rubric as NOT specific.
- **Open-ended planning is exempt** (`judges.py:165-166`): "Open-ended planning like
  'plan a 3-day trip to Chicago' does NOT strictly need clarification".
- **One consolidated question is the ideal** (`judges.py:169-173`): count independent
  question threads; a grouped ask for related missing fields counts as one. Asking
  check-in and check-out together is explicitly ONE question, not two.
- **Required question versus optional offer** (`judges.py:175-184`): only questions
  the user must answer for the assistant to proceed count. An offer of further help
  made after the requested output was already delivered does not. If the reply
  assumes or fabricates a missing value instead of asking, `asked` is false.
- **Verdict** (`judges.py:196-200`, recomputed in Python at `judges.py:226-228`):
  fail if clarification was needed but the model assumed instead of asking; fail if
  it asked more than one consolidated question; fail if it asked when nothing was
  missing.

### E9 scope_adherence, `evals/judges.py:264-291`

- **In scope**: searching flights and hotels, weather for a trip, building itineraries.
  **Out of scope** (`judges.py:267-270`): visa and immigration rules, refunds and past
  bookings, currency conversion, tax and legal advice.
- **Declining or handing off is correct behavior** (`judges.py:272-275`). Offering an
  in-scope alternative counts as a fine hand-off.
- **Verdict** (`judges.py:288-290`, recomputed at `judges.py:313`): fail *only* if the
  request was out of scope AND the reply answered it substantively. Everything else
  passes.

### E11 tone_quality, `evals/e_tone.py:135-174` (rubric version `provisional-v1-pending-customer-rubric`, `e_tone.py:74`)

All four dimensions must hold (recomputed at `e_tone.py:199`):

1. **professional** (`e_tone.py:144-148`): warm and courteous; not curt, rude,
   dismissive or sarcastic; no blame shifted onto the user; no internal-system
   excuses. A plainly stated limitation is fine.
2. **concise** (`e_tone.py:150-152`): no wall of text for a simple ask; length
   proportional to the request.
3. **no_overpromising** (`e_tone.py:154-158`): never claims to have BOOKED, RESERVED,
   PAID FOR, CHARGED, CONFIRMED or GUARANTEED anything.
4. **appropriate_scale** (`e_tone.py:160-163`): a one-line question gets a compact
   answer; an open planning request may get a longer structured one.

The rubric is explicitly provisional and is not Anne's team's own rubric
(`e_tone.py:25-32`). That caveat is inherited by every number in this document.

---

## 3. Agreement, measured

Verbatim output of `uv run python evals/calibration/compute_agreement.py`:

```
Calibration agreement report for evals/calibration/calibration_sheet.csv
Provenance: PROVISIONAL. 0 rows have human_reviewed=true, so human_label still
holds the AI-proposed starting values. These numbers are agreement between two
AI systems, not human ground truth.
========================================================================

[E8]
  rows                    : 33
  unsure (excluded)       : 0
  scored                  : 33
  agreements              : 33
  agreement rate          : 33/33 = 100.0%
  judge pass/fail         : 30/3
  label pass/fail         : 30/3
  false positives (J=pass, L=fail): 0
  false negatives (J=fail, L=pass): 0
  Cohen's kappa           : 1.000

[E9]
  rows                    : 33
  unsure (excluded)       : 0
  scored                  : 33
  agreements              : 33
  agreement rate          : 33/33 = 100.0%
  judge pass/fail         : 33/0
  label pass/fail         : 33/0
  false positives (J=pass, L=fail): 0
  false negatives (J=fail, L=pass): 0
  Cohen's kappa           : 1.000
  WARNING: no fail labels on either side. A judge that always returned pass would
  score identically here, so this agreement rate carries no information about
  discrimination.

[E11]
  rows                    : 33
  unsure (excluded)       : 3
  scored                  : 30
  agreements              : 30
  agreement rate          : 30/30 = 100.0%
  judge pass/fail         : 30/0
  label pass/fail         : 30/0
  false positives (J=pass, L=fail): 0
  false negatives (J=fail, L=pass): 0
  Cohen's kappa           : 1.000
  WARNING: no fail labels on either side. A judge that always returned pass would
  score identically here, so this agreement rate carries no information about
  discrimination.
    UNSURE: 0x43da445195 judge=pass 'Put together a 5-day itinerary for Paris, arriving J'
    UNSURE: 0x5300981bef judge=pass 'Do I need a visa to visit Japan as a US citizen?'
    UNSURE: 0xc3ba2ba2d2 judge=pass 'Put together a 7-day itinerary for Tokyo, arriving J'

[ALL]
  rows                    : 99
  unsure (excluded)       : 3
  scored                  : 96
  agreements              : 96
  agreement rate          : 96/96 = 100.0%
  judge pass/fail         : 93/3
  label pass/fail         : 93/3
  false positives (J=pass, L=fail): 0
  false negatives (J=fail, L=pass): 0
  Cohen's kappa           : 1.000

========================================================================
Blind-labelling contamination: 5 row(s) where the labeller had already seen the
judge verdict.
  Agreement on the 93 uncontaminated scored rows: 93/93 = 100.0%
```

### 3.1 Summary table

| Eval | Rows | Unsure | Scored | Agree | Rate | False pos | False neg | Judge pass/fail | Label pass/fail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E8 clarification_quality | 33 | 0 | 33 | 33 | 100.0% | 0 | 0 | 30/3 | 30/3 |
| E9 scope_adherence | 33 | 0 | 33 | 33 | 100.0% | 0 | 0 | 33/0 | 33/0 |
| E11 tone_quality | 33 | 3 | 30 | 30 | 100.0% | 0 | 0 | 30/0 | 30/0 |
| **All** | **99** | **3** | **96** | **96** | **100.0%** | **0** | **0** | **93/3** | **93/3** |

Definitions: a **false positive** is judge=pass with label=fail, meaning the judge
missed a real problem (the dangerous direction for a gate). A **false negative** is
judge=fail with label=pass, the judge crying wolf. **Unsure** rows are excluded from
the denominator and never folded into agreement.

### 3.2 Read the kappa carefully; two of the three are not real

Cohen's kappa is chance-corrected agreement. For E9 and E11 the reported 1.000 is
**not a measured value**. Both sides produced a single class (all pass), so expected
chance agreement `pe` is exactly 1.0, and `_cohen_kappa` (`evals/calibration/agreement.py:68-71`)
returns 1.0 from its degenerate branch by construction:

```
E9 / E11:  pj = ph = 1.0  ->  pe = 1.0*1.0 + 0.0*0.0 = 1.0  ->  degenerate, returns 1.0
```

Only E8's kappa is arithmetic on real variance, and even it rests on 3 negatives:

```
E8:  po = 33/33 = 1.0
     pj = ph = 30/33 = 0.9091
     pe = (0.9091 * 0.9091) + (0.0909 * 0.0909) = 0.8347
     kappa = (1.0 - 0.8347) / (1.0 - 0.8347) = 1.000
```

### 3.3 The unsure rate, and what it is telling you

3 of 99 rows (3.0 percent), all E11, all on the same two dimensions:

| Row | Input | Why unsure |
|---|---|---|
| `0x43da445195` | 5-day Paris itinerary | Four identical day blocks are literally "unnecessary repetition" (fails `concise`), yet the rubric also permits a planning request to run long (passes `concise`). No threshold separates the readings. |
| `0x5300981bef` | Japan visa question | A one-line yes/no question drew four paragraphs and three bullets. Whether the referral pointers make that proportional or "sprawling" is undecidable from `appropriate_scale` as written. |
| `0xc3ba2ba2d2` | 7-day Tokyo itinerary | Same as the Paris row, with six identical day blocks. |

E8 and E9 produced zero unsure rows. Their rubrics are operational: they name the
exact strings that count as vague dates, and they enumerate the out-of-scope topics.
E11's `concise` and `appropriate_scale` name no threshold at all, and that is where
every unsure landed. Section 4.1 shows this was not a labeller quirk.

---

## 4. Disagreement classes

There are **zero judge-versus-label disagreements** to group. That is itself the
finding, and reporting "no disagreement classes" would be the useless answer. So this
section reports the three things that actually carry signal: where the judge is
demonstrably unstable against itself, where its reasoning diverged from the
labeller's even though the verdict matched, and where the rubric lets real defects
through.

### 4.1 D1. `appropriate_scale` is unstable and has no threshold (E11, highest severity)

`candidate-AB` and `candidate-C` were judged by the **same model**, `claude-sonnet-5`
(confirmed from `evidence.judge_model` on all 33 E11 rows of each run). Across the 99
comparable rows there are exactly **2 verdict flips**, and both are E11:

| Input | AB | C | Dimension that moved |
|---|---|---|---|
| "Do I need a visa to visit Japan as a US citizen?" | pass | fail | `appropriate_scale` only |
| "Put together a 7-day itinerary for Tokyo, arriving June 1, 2026." | pass | fail | `appropriate_scale` only |

In both flips `professional`, `concise` and `no_overpromising` held on both sides.
The only moving part was `appropriate_scale`.

**These are two of the three rows the labeller had independently marked `unsure`,
for exactly the reason that the scale criterion states no threshold.** The blind
label predicted the instability before the verdicts were loaded. When a human
labeller cannot decide a dimension from the rubric, the judge cannot either, and it
resolves the coin flip differently on different inputs.

Consequence: any release gate that depends on E11 would flip on reply-length noise.
This is the single strongest argument for keeping E11 monitor-only.

### 4.2 D2. E8 is structurally blind on multi-turn follow-ups

E8 is handed only the current turn's user input, the reply, and the tool names
(`judges.py:209-214`). It never sees prior turns. On a follow-up whose missing-info
state is only determinable from earlier context, the judge has no choice but to infer
that state from the reply it is supposed to be grading, which is circular.

There is exactly one such row in the dataset, and it is the **only** E8 row of 33
whose `needed_clarification` flips between the two variants:

```
'Great, can you add a hotel for that weekend too?'
  candidate-AB : needed_clarification=True   question_count=1
  candidate-C  : needed_clarification=False  question_count=0
```

The labeller had prior context available (the preceding turn booked an August 7 flight)
and labelled `needed=true` on the ground that the check-out date was genuinely missing.
The judge reached the same verdict on AB but the opposite underlying fact on C. The
verdict survived by luck: under E9-style recomputation a wrong `needed` still lands on
pass when `question_count` moves with it.

This identifies inconsistent "clarification needed" reasoning between candidates and
localises it to 1 of 33 rows.

**Fix, before E8 is trusted on conversational traffic:** pass prior-turn context into
the E8 prompt. The dataset here is 33 turns across 31 conversations, of which only 2
conversations are multi-turn, so it under-samples the failure mode by construction.
Real traffic will not.

### 4.3 D3. The `question_count` counting rule diverges on heterogeneous grouped asks

One row where the verdict agreed but the reasoning did not:

```
'Plan a 3-day trip to Chicago for me.'
  judge    : needed=False  asked=True  question_count=2  -> FAIL
  labeller : needed=False  asked=True  question_count=1  -> FAIL
```

The reply asked for departure city and travel dates as two numbered items inside one
block. The rubric's counting rule (`judges.py:171-173`) says to treat "a single grouped
ask for related missing fields as one", and its worked example pairs two dates. It does
not say whether a city and a date are "related". The labeller read one grouped ask; the
judge read two threads.

It is verdict-neutral here only because `needed=False` already forces a fail. It would
**not** be neutral on a row where clarification was genuinely needed: there the judge's
count of 2 would fail a reply the labeller would pass, as a "peppering" false alarm.
This is a latent false-negative source that this dataset happens not to trigger.

### 4.4 D4. `no_overpromising` is scoped too narrowly to catch the overpromise that actually occurs

The dimension only catches claims of a *completed* transaction (`e_tone.py:156-160`).
It says nothing about *offering* a capability the agent does not have. In this run:

- **13 of 33 replies** offer to book, in phrasings such as "Would you like to book one
  of these flights?" and "would you like me to help you book one?". The agent has no
  transactional tool and cannot honor any of them.
- One reply (the refund request) says "Let me connect you with someone who can assist
  with that." There is no handoff mechanism.

Both the judge and the labeller passed all of these, correctly, because the rubric as
written does not cover them. That is a rubric defect, not a judge defect. Anne's team
would very plausibly score a promise to book as a tone failure, and that is precisely
the kind of divergence a real calibration round with them should surface.

### 4.5 D5. E9 and E11 have no negative examples at all

E9 saw 4 out-of-scope prompts (visa, refund, currency, discount code) and the agent
declined all 4 correctly. E11 saw no reply that overpromised a completed booking, was
rude, or shifted blame. Zero fails on either side, for both evals.

A judge that ignored its input and returned `pass` unconditionally would score 33/33
on E9 and 30/30 on E11 against these labels. **The 100 percent agreement on these two
evals is not evidence that they work.** It is evidence that the dataset never asked
them a hard question.

### 4.6 D6. The only discriminating E8 rows are the contaminated ones

E8 is the one eval with label variance: 3 fails out of 33. Those 3 rows are the Chicago
planning row, the "next Friday" flight and the "next Tuesday" weather, and they are
exactly the 3 rows whose verdicts leaked via the run summary (section 1.3). On the
30 uncontaminated E8 rows both sides pass everything, which carries no information.

So the honest reading of E8's 33/33 is: **30 rows of no signal, plus 3 rows where the
labeller had seen the answer.** The labeller's recorded reasons are rubric-derived and
would have produced the same three fails independently, but that cannot be proven from
this run. E8 needs a fresh, uncontaminated labelling pass before its agreement number
is worth anything.

### 4.7 On the prior audit's "Sonnet flags 3/33 where Haiku passed all"

This was investigated and **the comparison does not hold up.** The two judges were
never shown the same text.

`docs/evals/judges-baseline-2026-07-19/` was produced by `claude-haiku-4-5`
(`judges.py:36-38`) over `docs/baseline/2026-07-19/spans.jsonl`, which is the
**shipped-prompt agent**. `judges-candidate-AB` was produced by `claude-sonnet-5` over
the **fixed-prompt agent**. Checking every user input the two runs share:

```
user_inputs in BOTH baseline (haiku-judged) and candidate-AB (sonnet-judged): 20
  of those, byte-identical replies: 0
```

Zero. There is no head-to-head row anywhere in the captured evidence. And on the three
rows in question the agent behaved differently, which fully accounts for the verdict
change without implicating the judge model:

| Input | Baseline reply (haiku judged: pass) | Candidate-AB reply (sonnet judged: fail) |
|---|---|---|
| Miami to Tokyo "next Friday" | Asked for the exact date in YYYY-MM-DD | Resolved it itself to July 25, 2026 and asked about passenger count instead |
| London "next Tuesday" | Asked for the exact date in YYYY-MM-DD | Resolved it itself to July 28 and called the weather tool |
| Chicago 3-day trip | Delivered the itinerary, then asked | Withheld the itinerary and asked first |

Both judges were right about the reply in front of them. The agent regressed on
relative-date handling between the two configurations; the judge did not get stricter.
Two of those self-resolved dates are also simply wrong: July 25, 2026 is a Saturday,
not a Friday, and the reply to the Denver "this weekend" row calls July 26 a Saturday
and July 27 a Sunday when they are a Sunday and a Monday.

There is no same-dataset control judge run. That is the actual gap: **build a
same-dataset, same-replies, two-model judge run before making any claim about judge
model choice.** It costs one extra judge pass over spans already on disk.

---

## 5. Recommendation per eval

| Eval | Recommendation | Why |
|---|---|---|
| **E8** clarification_quality | **Monitor-only** | Best of the three. Structured reasoning is sound and it caught a real agent regression. But its only discriminating rows are verdict-contaminated (D6), it is blind on multi-turn follow-ups (D2), and its counting rule is under-specified (D3). |
| **E9** scope_adherence | **Monitor-only** | Zero negative examples (D5). Nothing has been measured about its ability to detect an out-of-scope answer, because it was never shown one. |
| **E11** tone_quality | **Monitor-only**, and the weakest of the three | Zero negatives (D5), a demonstrably unstable dimension (D1), a rubric that misses the overpromise actually present in 13 of 33 replies (D4), and the rubric is self-declared provisional and is not the customer's. |

Monitor-only means: score it, chart it, alert on a trend, use it to prioritise review.
It does not block a promotion.

### 5.1 What would promote an eval to release-gating

All five, per eval:

1. **Domain-owner labels.** At least 50 rows labelled by Anne's product team, not by the
   candidate and not by an AI. These are the people whose spot-checking the judge is
   replacing; their standard is the target.
2. **Negative examples in the set.** At least 10 rows that a domain owner labels fail.
   Until a judge is shown failures it can be caught on, agreement measures nothing.
   For E9 this means deliberately seeding replies that answer visa and currency
   questions substantively; for E11, replies that claim completed bookings.
3. **Cohen's kappa at or above 0.75 on a non-degenerate distribution**, with the class
   balance reported alongside so a degenerate 1.000 can never be mistaken for a real one.
4. **Zero false positives on the severity class being gated.** A judge that passes a
   reply the domain owner fails is worse than no gate, because it launders the defect.
   False negatives are tolerable at a published rate.
5. **At least two independent labellers on an overlapping subset**, so an inter-rater
   reliability figure exists. Without it there is no way to tell a judge that is wrong
   from a rubric that is ambiguous, which is exactly the confusion D1 sits in.

E11 additionally must not be gated on the provisional rubric under any circumstances.
It needs Anne's team's own rubric first, at which point `_E11_SYSTEM` and the
`RUBRIC_VERSION` constant both change and this whole exercise is repeated.

### 5.2 Cheapest next actions, in order

1. Have Chinmay review the 99 rows in `evals/calibration/calibration_sheet.csv`, flipping
   `human_reviewed` to `true` and correcting `human_label` where it disagrees. Rerun
   `compute_agreement.py`. This upgrades the labels from AI-proposed to candidate-reviewed,
   which is still not domain-owner-reviewed, but it is a real second opinion.
2. Re-label the 3 contaminated E8 rows from scratch, by someone who has not read the
   summaries, to recover E8's only informative rows (D6).
3. Add negative examples to the golden dataset for E9 and E11 (D5). This is the single
   highest-value change and needs no new labels to justify.
4. Pass prior-turn context into the E8 judge prompt (D2).
5. Run both judge models over one identical spans file to get the head-to-head that
   does not currently exist (section 4.7).

---

## 6. Provenance and limitations

### 6.1 Who labelled what

- **Labeller:** an AI assistant (Claude), working blind to the verdicts per section 1.2,
  from the rubrics in `evals/judges.py` and `evals/e_tone.py`.
- **Reviewer:** nobody yet. `human_reviewed` is `false` and `reviewer` is empty on all
  99 rows. `human_label` is **pre-populated with the AI-proposed label as a starting
  point only**, so a reviewer edits disagreements rather than typing 99 cells. Until
  `human_reviewed` flips, `human_label` is not a human label.
- **These are not Anne's team's labels.** They are not customer ground truth and must
  never be presented as such, in the deck or anywhere else. The intended path is
  candidate review first, then a real labelling round with Anne's team.
- **Judge:** `claude-sonnet-5` for all three evals in this run, confirmed from
  `evidence.judge_model` for E11 and from the `JUDGE_MODEL` default at `judges.py:39`
  for E8 and E9. Note that E8 and E9 do **not** record the judge model in their
  evidence; that provenance had to be inferred from the default and the run timestamp,
  which is a gap worth closing in `judges.py`.

### 6.2 Limitations, stated plainly

1. **Single labeller, so there is no inter-rater reliability figure at all.** Nothing
   here separates "the judge is right" from "the labeller and the judge share the same
   blind spot". Both read the same rubric; correlated error is the expected failure mode.
2. **Sample size 33 turns (99 rows), from one run of one agent configuration.** Those
   33 turns span 31 conversations and only 2 of them are multi-turn, which under-samples
   the multi-turn case that produced D2.
3. **Severe class imbalance.** 93 of 96 scored rows are pass on both sides. E9 and E11
   have no negatives whatsoever, which makes their agreement rates uninformative (D5).
4. **5 of 99 rows were labelled after the verdict was already known** (section 1.3), and
   3 of those are the only E8 rows with any discriminating power (D6).
5. **AI-proposed labels are not domain expertise.** The labeller applied the written
   rubric faithfully; it does not know what Anne's team would actually accept from a
   customer-facing reply. D4 is a concrete example of the gap: 13 replies offer to book
   something the agent cannot book, and the rubric as written passes all of them.
6. **E11's rubric is provisional and self-declared as such** (`e_tone.py:25-32`). Every
   E11 number inherits that caveat.
7. **No judge was re-run for this document.** All verdicts are the captured 2026-07-19
   artifacts. Judge behavior may drift with model updates; the model identity is
   recorded so a future re-run is comparable.

### 6.3 Reproducing this

```
uv run python evals/calibration/build_calibration_sheet.py   # rebuild the sheet
uv run python evals/calibration/compute_agreement.py         # recompute agreement
```

Both are deterministic, read-only with respect to `docs/`, and make no API calls.
`build_calibration_sheet.py` redacts user input with `agent.redaction.redact`, the same
boundary redactor the agent uses, so the sheet cannot reintroduce PII the pipeline
stripped. One row in this dataset carries a payment card number and appears in the sheet
as `[REDACTED-CARD]`.

The `assistant_reply_excerpt` column is verbatim agent output, copied mechanically and
normalised only for whitespace and length. Its punctuation is the agent's, not this
document's, and it is deliberately left unedited so a reviewer is reading exactly what
the judge was shown.
