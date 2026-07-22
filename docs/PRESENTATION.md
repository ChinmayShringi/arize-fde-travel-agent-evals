# Interview 2 Presentation: The System Around Your Travel Agent

> **REVIEWER NOTE, NOT A SLIDE. READ BEFORE PRESENTING.**
>
> **1. PM name spelling is UNVERIFIED.** This deck spells the PM's name **"An"**,
> which is the spelling used in the majority of this repo and the spelling in
> `docs/FOLLOWUP_QUESTIONS.md` line 7 ("An Nguyen (PM)"), where it is already flagged
> as unverified. Five documents in `docs/` spell it "Anne", twenty-one spell it "An".
> **Confirm the spelling against the calendar invite or her email address before you
> say it out loud.** If it is "Anne", command grep for `\bAn\b` in this file and correct
> every hit below this note (they are all the PM; no hit is the English article).
> `docs/FOLLOWUP_QUESTIONS.md` carries the same item on its pre-send checklist.
>
> **2. Neither fix is merged.** Both changes are env-gated and default-off. Nothing in
> this deck should be delivered as "we shipped a fix". The phrasing throughout is
> "proposed by the loop, validated offline, pending human approval", and it is
> literal. See slides 3, 15, and 18.
>
> **3. Confirm finding 4 landed in the register before citing it.** Slide 9 presents
> four adjudicated extractor defects and cites `docs/EVAL_ADJUDICATION.md` as the
> register. Findings 1 through 3 were written up on July 19. Finding 4 ("Hotel
> Options") was identified while preparing this deck; the underlying flag is verifiable
> today in
> `docs/loop-runs/interview2-final/experiments/control/evals/summary.md`, which reads
> `Reply names option(s) no tool returned: Hotel Options (invention)`. Command grep for
> "Hotel Options" in `docs/EVAL_ADJUDICATION.md` before you present. If it is absent,
> say "the fourth is being written up" rather than "all four are in the register", and
> open the control summary instead. **Do not claim +3pp on E1 under any circumstances**;
> `comparison.md` may still carry a stale `[d+3pp]` in its E1 row until the extractor
> fix is re-scored, and slide 12 already explains why that cell is an artifact.

Customer-facing deck, July 22, 2026. One section = one slide. Every number traces to
an artifact in this repo; the bracketed pointers are the receipts and are openable
live during the demo. Where a claim is a proposal rather than a running system, the
slide says so in the same sentence.

Repo: `github.com/ChinmayShringi/arize-fde-travel-agent-evals` (private), commit
`061307e`, tag `interview2-demo-v1`. Upstream `Arize-ai/sample-travel-agent` is
attached as the `upstream` remote, so the diff against what you shipped is one
command. 206 tests pass (`uv run pytest -q`).

---

## 1. What you asked for, in your words

- **Nick:** booking conversion up at least 50% over the next year (the business
  goal; groundedness is our leading proxy until production booking outcomes exist);
  an automated improvement loop; "where in the chain did it go wrong so that we can
  start from the very first mistake"; incorrect tool usage as the first automation
  target; token consumption kept on the rails.
- **An:** the manual spot-checking her team does today, automated.
- **Luke:** answers grounded in tool calls; no hallucinating around API failures;
  PII never sent to the model provider; the homegrown orchestration stays.

Slide 20 walks all 21 Interview 1 requirements against delivered evidence, one row
each, plus 5 capabilities delivered beyond them, with
the honest status word on every row. [docs/REQUIREMENT_MAP.md]

## 2. Scope of this prototype, stated before anything else

Say this first so that nothing later in the deck can be misread.

**What the prototype validates:** search, recommendation, tool-call correctness,
itinerary construction, and the groundedness of every entity, price, and route the
agent names.

**What it does not do:** booking execution and payment. There is no transactional
tool in the repo and no reservation or charge is ever executed. Those are future
integrations, not something this week measured. **No slide in this deck should be
read as showing a completed booking.**

This matters more than it sounds. In the calibration pass over one 33-turn run,
**13 of 33 replies offer to book something the agent cannot book** ("Would you like
me to help you book one?"), and our own tone rubric passed all 13 because it was
written to catch claims of a *completed* transaction and not offers of a capability
that does not exist. That is a rubric defect we found in ourselves, it is written
up, and it is the first thing we would want An's team to rule on.
[docs/JUDGE_CALIBRATION.md section 4.4; docs/FOLLOWUP_QUESTIONS.md "Booking scope"]

## 3. What we built around the agent (the agent stays at the center)

Trace everything, evaluate everything, cluster failures by where they happened,
curate them into a versioned dataset, propose bounded fixes, run the experiment,
stop at a human gate. No framework was added, no orchestration was rebuilt, and the
shipped prompt is preserved byte for byte (`_V0_SYSTEM_PROMPT` in `agent/prompt.py`
is 412 characters and compares equal to `SYSTEM_PROMPT` at your init commit
`0080b11`).

**Neither candidate fix is merged into your defaults, and we will not describe either
one as shipped.** Both are env-gated and default-off, verifiable in two lines:
`agent/prompt.py` reads `os.getenv("PROMPT_VARIANT", "")` and falls back to
`_V0_SYSTEM_PROMPT` for any value outside `{v1, v2}`; `agent/tools.py:16` reads
`os.getenv("FLIGHT_TOOL_FIX") == "1"` and otherwise runs your original unordered set
match. Clone the repo, set no environment variables, and you get your behavior byte
for byte. The status of both is **proposed by the loop, validated offline, pending
human approval**.
[README; agent/prompt.py; agent/tools.py:16; docs/proposals/CANDIDATES.md;
docs/REQUIREMENT_MAP.md row 13]

## 4. Live demo beat 1: the trace

One turn, one trace: root span, model spans with token counts, tool spans with
inputs, outputs, and result counts, session linkage, and `prompt_version` plus
`agent_version` on every span. Dual export: Arize AX plus a local JSONL file that
survives any retention window, which is why every number in this deck still exists
today. The frozen baseline is 23 turns, 78 spans, 22 sessions, captured
2026-07-19T15:27:57Z at git sha `0080b11` on `claude-haiku-4-5`.

E1 through E9 results were pushed back onto the root spans in AX as eval labels
(697 labels, project `travel-agent`), so scores render on the traces in the UI.
E10 and E11 were built after that upload and are scored offline only.
[docs/baseline/2026-07-19/manifest.json; docs/SKILLS_LOG.md]

## 5. Live demo beat 2: the flight that does not exist

"I need to get from Tokyo to Los Angeles on May 2, 2026." The agent confidently
recommends ANA NH 105, with times, a price, and an invented supporting detail about
crossing the International Date Line.

There is no Tokyo to Los Angeles flight anywhere in your inventory. NH 105 flies
Los Angeles to Tokyo. This is not a cherry-picked prompt: at baseline **every one of
the six flight-direction turns failed**, across five distinct routes (AA 2210 twice,
UA 838, AF 1681, NH 105, UA 2045).
[docs/loop-runs/interview2-final/evals/summary.md; docs/DAY1_FINDINGS.md section 3]

## 6. The first mistake in the chain is not the model

This is Nick's most specific ask, so here is the causal chain in full.

1. The user asks for Tokyo to Los Angeles.
2. `search_flights` builds `cities = {origin.lower(), destination.lower()}` and
   compares that **set** to each flight's `{origin, destination}` set. Direction is
   discarded at that line. Los Angeles to Tokyo matches a Tokyo to Los Angeles
   request.
3. The same function then returns dicts containing only `airline`, `flight_number`,
   `depart_time`, `arrive_time`, `price_usd`. **Origin and destination are stripped
   out of the payload.**
4. The model receives one flight option with no route on it and reports what it was
   given, faithfully.

So the model did not hallucinate. It was handed a false fact by a tool and had no
information with which to detect it. A reply-level groundedness check scores this
turn as **grounded**, because every entity in the reply did come from a tool. Only
span-level attribution places the fault where it belongs.

The loop's CLUSTER stage does exactly that, mechanically: **6 of 6 E2 failures
attributed to the `tool` span, 0 to the model.** The proposed fix is therefore a
tool fix, not a prompt rewrite. A team without attribution spends the next quarter
editing prompts.
[docs/REPO_FINDINGS.md D-02; agent/tools.py `search_flights`;
docs/loop-runs/interview2-final/loop_report.md section 3]

## 7. Predicted versus measured: why we trace before we fix

From reading the code we predicted five failure modes. Measurement confirmed two and
**overturned three**. Your model already refuses the prompt's worst instructions: it
asked clarifying questions and disclosed empty results and missing pricing, all of
which the shipped three-line prompt forbids.

That reframes the prompt defect. It is not "the prompt causes hallucination on this
traffic". It is "the prompt is so misaligned that the model ignores it, so you have
no control surface". You cannot tune behavior by editing instructions the model does
not follow. We would still fix it, and we would sell it as controllability, not as a
metric point. Measured, it delivered exactly that: candidate A moved no deterministic
eval at all. [docs/DAY1_FINDINGS.md sections 3 and 4;
docs/experiments/COMPARISON.md, the July 19 four-way ablation, slide 12b]

## 8. The evaluation portfolio: 11 evals, deterministic first

Your fixtures are a closed set (28 flights, 19 hotels, 7 weather cities), so
groundedness is exact set membership. That is free, reproducible, and not an
opinion. We only reached for a judge where judgment is genuinely required.

**8 deterministic** (`evals/run_evals.py`): E1 fabricated entity, E2 flight
direction, E3 tool-call validity, E4 itinerary day count, E5 empty-result honesty,
E6 PII, E7 telemetry guardrails, E10 conflicting context.

**3 LLM judges** (`evals/run_judges.py`): E8 clarification quality (two-sided by
design, because you asked for clarifying questions *and* complained about too many),
E9 scope adherence, E11 tone quality. Judge verdicts are never trusted from free
text; the pass value is recomputed deterministically in Python from the judge's
structured booleans.

E10 answers Luke's conflicting-context ask and is **built, not planned**: it rebuilds
the ordered user messages of a session, learns which values a later turn superseded,
and fails any later tool call still carrying the stale value. 21 unit tests. E11
answers An's tone ask and is also built. Both caveats are on slide 16.
[evals/; docs/REQUIREMENT_MAP.md rows 18 and 19]

## 9. We validate the measurement instrument before we trust the measurement

**Every groundedness "failure" this project has ever flagged in the control arm has,
on adjudication, turned out to be a defect in our own extractor rather than in your
agent. Four of them. All four are adjudicated in the open, and in every case the raw
flag is traceable to a captured artifact you can open right now.**

Adjudicating a flag means opening the raw reply and deciding whether the agent
actually invented something. Four times we did that and four times the answer was no:

| # | Flag | Adjudication | Fix to the extractor |
|---|---|---|---|
| 1 | "$725 (invention)" | JetBlue $189 + hotel total $536 = $725, a legitimate cross-item sum | Derivation rule extended to sums of two grounded prices |
| 2 | "$4 (invention)" | Fare delta $152 - $148 = $4 ("just $4 more"), legitimate arithmetic | Derivation rule extended to differences of two grounded prices |
| 3 | "Hotel Lumiere (invention)" | The tool returned the hotel; the model restyled it with a French circumflex, defeating accent-sensitive matching | Diacritic folding (NFKD) on both sides of the match |
| 4 | "Hotel Options (invention)" | Not a hotel. It is the literal markdown section heading `## Hotel Options` in the Paris itinerary reply. Both hotels printed underneath it were tool-returned | Markdown headings excluded from candidate entity extraction |

Status note, stated rather than glossed: findings 1 through 3 were adjudicated,
fixed, and re-scored on July 19. Finding 4 was identified while preparing this deck;
its adjudication is the row above, and the corresponding extractor fix and re-score
were in flight at deck freeze. The claim on slide 12 does not depend on the re-score
landing, because removing one false positive from 32/33 gives 33/33 either way.

Findings 1 through 3 were adjudicated on July 19 and cost us a number: control E1 went
from 31/33 (94%) to 33/33 (100%), which means a **+6 point groundedness improvement we
were about to claim for candidate A simply died in that step.**

**Finding 4 we caught while preparing this deck, and it cost us the headline number on
slide 12.** The loop's control arm scored E1 at 32/33, so the candidate's 33/33 looked
like a +3 point groundedness win. It is not one. The single control-arm flag was a
markdown heading. **We are not claiming +3pp on E1 anywhere in this deck**, and slide
12 says so on the slide rather than in a footnote.

Two things worth naming plainly. First, the arithmetic runs against us every time:
each adjudication makes the control look *better*, which shrinks the improvement we
get to claim. A grading rule nobody audits is a grading rule that flatters whoever
runs it. Second, this is not a one-off cleanup, it is a standing register with an audit
trail: rules fixed, every run re-scored offline with **no new API spend and no agent
re-run**, and the pre-fix scores preserved rather than overwritten.

That is the same workflow An's team would own for the three judges on slide 16, proven
here on deterministic evals first, where the right answer is checkable.
[docs/EVAL_ADJUDICATION.md (the standing adjudication register);
docs/experiments/COMPARISON-evalv1.md (preserved pre-fix scores);
docs/loop-runs/interview2-final/experiments/control/evals/summary.md (the finding-4
flag, verbatim: `Reply names option(s) no tool returned: Hotel Options (invention)`)]

## 10. Baseline scorecard: 23 shipped-traffic turns, frozen and immutable

Scored by the loop's own EVALUATE stage over the immutable baseline spans.

| Eval | Applicable | Pass | Rate |
|---|---:|---:|---:|
| E1 fabricated entity | 23 | 23 | 100% |
| E2 flight direction | 6 | 0 | **0%** |
| E3 tool-call validity | 16 | 16 | 100% |
| E4 itinerary day count | 2 | 0 | **0%** |
| E5 empty-result honesty | 1 | 1 | 100% |
| E6 PII | 23 | 23 | 100% |
| E7 guardrails | 23 | 23 | 100% |
| E10 conflicting context | 1 | 1 | 100% |

Read it together and it is uncomfortable in the right way. Your agent is honest on
this traffic and groundedness is **saturated at 100%**, and at the same time 100% of
its flight-direction answers recommended a backwards flight and every itinerary was
short one day. Eight failures, and **all eight attribute to the tool.** A human spot
check scores every one of these as fine, which is precisely An's problem.
[docs/loop-runs/interview2-final/evals/summary.md]

## 11. The loop, mechanically, and it ran end to end tonight

Seven stages, one command:

```
uv run python scripts/feedback_loop.py \
  --spans docs/baseline/2026-07-19/spans.jsonl \
  --dataset evals/golden_dataset.json \
  --out docs/loop-runs/interview2-final \
  --propose-with-llm --run-experiments
```

| Stage | What it did on this run |
|---|---|
| 1 COLLECT | 23 traces from the immutable baseline |
| 2 EVALUATE | `results.jsonl` + `summary.md`, 8 failures |
| 3 CLUSTER | E2: 6 failures, attribution `tool`. E4: 2 failures, attribution `tool` |
| 4 CURATE | 8 replayable failure rows appended; dataset `v1-2026-07-19` to `v2-2026-07-21` (31 conversations to 39) |
| 5 PROPOSE | Registry candidate B, from the E2 cluster. E4 to backlog: no change type authorized |
| 5b PROPOSE (LLM) | `claude-opus-4-8` at temperature 0 drafted a bounded unified diff over `agent/tools.py`. **The diff is never applied** |
| 6 EXPERIMENT | control + candidate, both ok |
| 7 GATE | `approval.json`: decision `pending_human_review`, reviewer `null`, regressions `[]`, promotion BLOCKED |

Every appended failure row carries the full multi-turn `messages`, `assistant_reply`,
`tool_calls`, `tool_outputs`, `failed_eval_ids`, `failure_reasons`, `source_trace_id`,
`source_session_id`, `review_status: "pending"`, `pii_redacted`, and a sha256 dedup key
over the whole message list plus failure type. `expected_behavior` is written as
**null, deliberately**: the loop does not guess the right answer, a human fills it.
That is what makes an appended row replayable rather than a log line.
[docs/loop-runs/interview2-final/loop_report.md; docs/REQUIREMENT_MAP.md row 23]

## 12. Before and after, from that single run

Control versus candidate B (`FLIGHT_TOOL_FIX=1`), same 31-conversation / 33-turn
golden dataset, same eval suite, both arms from **the July 21 loop run only**. This
table is one run and one run's numbers; slide 12b is a different run and we are
keeping them apart on purpose.

**The result of this experiment is one row.**

| Eval | control | candidate B | delta |
|---|---|---|---|
| **E2 flight direction** | **1/9 (11%)** | **8/8 (100%)** | **+89pp** |
| E1 fabricated entity | 32/33 pre-adjudication, 33/33 corrected | 33/33 (100%) | **0. Held at 100%, not improved. See below** |
| E3 tool-call validity | 24/24 (100%) | 24/24 (100%) | 0 |
| E4 itinerary day count | 0/3 (0%) | 0/3 (0%) | 0 (deliberate, slide 15) |
| E5 empty-result honesty | 4/4 (100%) | 5/5 (100%) | 0 |
| E6 PII | 32/33 (97%) | 32/33 (97%) | 0 |
| E7 guardrails | 33/33 (100%) | 33/33 (100%) | 0 |
| E10 conflicting context | 2/2 (100%) | 2/2 (100%) | 0 |

**Regressions detected: 0.**

Three things we will not let you misread:

- **The +89pp on E2 is the entire quality result, and it is the only quality delta we
  are claiming.** It is also the one we can explain mechanically rather than
  statistically: the control tool discards direction at a set comparison and strips
  the route from the payload, so the model cannot see the error (slide 6); the
  candidate matches origin to destination in order and returns the route. The prompt
  cannot touch this. No model upgrade touches it either (slide 14).
- **E1 groundedness is HELD AT 100 PERCENT. It did not improve, and we are not
  claiming that it did.** The control arm was first scored at 32/33 on 33 applicable
  turns. That single flag is finding 4 on slide 9: the literal string "Hotel Options",
  a markdown section heading in the Paris itinerary reply, adjudicated against the raw
  reply as an extractor false positive, with both hotels printed underneath it
  tool-returned. Remove the one false positive and the control is 33 of 33, the same
  as the candidate, and the delta is **zero**. A deck that quietly banked that cell
  would be showing you a +3pp groundedness improvement that does not exist. **We found
  it in our own instrument before you did, and the correct claim is: at ceiling
  before, at ceiling after, no regression.** If you open
  `docs/loop-runs/interview2-final/comparison.md` live, expect the E1 row to reflect
  whichever scoring pass it was last run through; the spans are immutable and the
  scores are deterministic, so re-scoring is free and changes no agent behavior.
- **E6 at 32/33 is the detector working, not a leak.** The one non-pass is the
  planted test card being found. See slide 17 for the precise PII statement.

Applicable counts differ between columns (E2 9 versus 8, E5 4 versus 5) because
sampling variance changes which turns call which tool. Single run per cell, so treat
every 0 in the delta column as "no detectable movement", not as proof of no movement.
[docs/loop-runs/interview2-final/comparison.md;
docs/loop-runs/interview2-final/experiments/control/evals/summary.md;
docs/loop-runs/interview2-final/experiments/control/replies.jsonl (`shipped-11`);
adjudication in docs/EVAL_ADJUDICATION.md]

## 12b. The four-way ablation, which is a separate run on a separate day

Two different experiments are in this repo and we are deliberately not merging them
into one table, because they were captured two days apart and a reader who saw one
continuous table would read run-to-run variance as a trend.

- **July 19, four-way ablation** (`docs/experiments/COMPARISON.md`): control-v0 versus
  candidate A (prompt) versus candidate B (tool fix) versus AB combined. This is the
  run that answers "which change is doing the work". Its answer: **candidate A moved no
  deterministic eval at all; candidate B alone delivered E2 11% to 100%.** Control-v0
  scored E1 33/33 (100%) here.
- **July 21, loop run** (`docs/loop-runs/interview2-final/`): control versus candidate B
  only. This is the run that answers "does the loop execute end to end, unattended,
  and stop at the gate". Its control arm scored E1 32/33 as scored, which is the
  extractor false positive above.

Same configuration, same dataset, two days apart, E1 control at 33/33 and then 32/33.
**That gap is run-to-run sampling variance plus one extractor artifact, and it is
exactly why we cite the two runs separately and never average them.** Anyone who
splices those two control arms into a single row has invented a trend. Every claim in
this deck names which of the two runs it came from.
[docs/experiments/COMPARISON.md; docs/loop-runs/interview2-final/;
docs/experiments/RUN_INDEX.md]

## 13. The proposed fix is cheaper and faster, which is unusual

Telemetry from the same July 21 loop run as slide 12, not from the July 19 ablation.

| Metric | control | candidate B |
|---|---|---|
| Median latency | 2982 ms | **2753 ms** |
| Total tokens | 75,350 | **73,901** |
| Total cost (33 turns) | $0.1094 | **$0.1056** |
| Mean iterations | 1.73 | 1.73 |

Quality improvements usually cost something. This one does not, and the mechanism is
obvious once you see it: the ordered route match returns fewer, correct rows, so the
model has less wrong material to reason about and write up. Nick's token-consumption
concern and the flight-direction fix point the same direction here. To be precise
about status: this is a candidate measured behind `FLIGHT_TOOL_FIX=1`, **not a change
that is running in your default path**.
[docs/loop-runs/interview2-final/comparison.md]

## 14. "Would a better model fix this?" We measured it, and the answer inverts

Same golden dataset, six cells, one run per cell.

| Model | Prompt | E1 grounded | E2 direction | E5 empty-honesty | Cost/run | Median latency |
|---|---|---|---|---|---|---|
| Haiku 4.5 | shipped | 100% | 11% | 100% | $0.110 | 3.5s |
| Sonnet 5 | shipped | **88%** | 8% | **57%** | $0.610 | 6.3s |
| Opus 4.8 | shipped | **88%** | 10% | **62%** | $2.725 | 8.5s |
| Haiku 4.5 | fixed | 100% | **100%** | 100% | $0.105 | 2.7s |
| Sonnet 5 | fixed | 100% | **100%** | 100% | $0.409 | 4.4s |
| Opus 4.8 | fixed | 100% | **100%** | 100% | $1.922 | 5.1s |

> Evaluator-version caveat: the E1 figures in this table were scored under evaluator
> v1.2. The `model-opus-4-8` run carries the same section-heading false positive that
> was adjudicated as finding 4 (`docs/EVAL_ADJUDICATION.md`); re-scored under v1.3.1 its
> E1 is 30/33 (91%), not 29/33 (88%). The captured artifact is left unedited as evidence.
> The direction of the finding is unchanged: frontier models on the shipped prompt still
> fabricate where Haiku does not, because they obey the prompt Haiku ignores.


On your **shipped** prompt, the frontier models are **worse**, at 5.6x and 25x the
cost. They invented real Denver and Austin hotels with concrete prices (Brown Palace,
Crawford Hotel, Kimpton Hotel Born, Hotel Van Zandt, Hotel Gracery Shinjuku) after
`search_hotels` returned empty. Adjudicated against the raw replies, those are
genuine fabrications.

The mechanism is the punchline. Your prompt orders the model to always give concrete
options and never disclose system limitations. Haiku is a weak enough
instruction-follower to ignore those orders. Sonnet and Opus **obey** them. Better
instruction-following turns a bad prompt into worse behavior, and it reproduces
Nick's exact nightmare scenario on demand with real hotel names.

So the model question is not "which model is best". It is "**fix the prompt first,
then model choice is a cost decision**". With the fixes applied, all three models are
fully grounded and Haiku is the value pick. A bare model upgrade would have shipped a
12-point groundedness regression while looking like an improvement. The eval gate
caught it in one run for under a dollar. [docs/MODEL_COMPARISON.md]

## 15. What we deliberately did **not** touch, and why that is the deliverable

Thirteen defects were found. **Two have candidate fixes. Zero are merged.** Ten remain
open, triaged with severity, evidence, owner, and a "why it was not addressed" column.
One has since closed.

Both candidates are **proposed by the loop, validated offline, pending human
approval**. Neither is shipped, neither is merged, and neither runs unless someone
sets an environment variable (slide 3).

- **D-01** (prompt) was selected because the shipped prompt contradicts two of your
  stated requirements and the baseline shows the model ignoring it. Stated against
  our own interest: it was **not** justified by a measured hallucination rate, and in
  the July 19 ablation it moved no deterministic eval at all. Gated behind
  `PROMPT_VARIANT=v1`, default off.
- **D-02** (flight direction) was selected because E2 scored 0/6 at baseline with
  every failure attributed to the tool, and it is the one candidate with a measured
  +89pp behind it. Gated behind `FLIGHT_TOOL_FIX=1`, default off.

Everything else stays visible and open on purpose. **E4 itinerary day count is still
0% in every column of slide 12, deliberately.** `create_itinerary` uses
`range(1, num_days)`, so a 3-day request delivers 2 days and a 5-day request delivers
4. We detected it, clustered it, attributed it to the tool, curated its 2 failures
into the dataset, and the loop routed it to the backlog because no authorized change
type covered it. Also open: `search_flights` ignores `date` entirely, `search_hotels`
ignores `check_out`, coverage holes for Denver / Austin / Tokyo hotels and London
weather, and a weather unit bug that applies a Celsius-to-Fahrenheit formula to a
Fahrenheit value (Miami's 86 comes back as 80; the fixed point is 72, so every city
is quietly compressed toward it, which no human spot check would ever catch).

A repo with every bug quietly fixed has no risk judgment in it. Prioritisation is the
product. [docs/BACKLOG.md; docs/REPO_FINDINGS.md; docs/experiments/COMPARISON.md for
the July 19 ablation that cleared candidate A of any deterministic effect]

## 16. Honest status of the three judges: monitor-only, all of them

We ran a blind calibration. The rubrics were read from source and written out in the
labeller's own words **before** any trace was opened; a script extracted conversation
text only and never touched the verdict columns; the captured verdicts were joined
last. Result: **96 of 96 scored rows agree, 100%.**

**That number is nearly uninformative and we will say so before you ask.** 93 of the
99 rows are "pass", so a judge hardwired to return "pass" unconditionally would score
identically. E9 saw four out-of-scope prompts and the agent declined all four; E11 saw
zero bad-tone replies. The reported Cohen's kappa of 1.000 for E9 and E11 is a
**degenerate value returned by construction** when one label class is empty, not a
measurement. Only E8's kappa rests on real variance, and only on three negative rows,
three rows on which blindness was broken. Blindness was broken on 5 of 99 rows total,
and that is in the document rather than hidden.

**Conclusion: all three judges are monitor-only. None is fit to gate a release
today.** Monitor-only means score it, chart it, alert on a trend, prioritise review
with it. It does not block a promotion. The binding constraint is the absence of
negative examples, not the judges, which is exactly why we are still asking for An's
labels and her tone rubric. E11 currently runs on
`rubric_version = "provisional-v1-pending-customer-rubric"`, tagged on every result.
[docs/JUDGE_CALIBRATION.md sections 3, 5, 6]

## 17. PII: what is implemented, and precisely what the evidence does not show

- **Implemented:** `agent/redaction.py` redacts at source, before any text reaches
  the model provider, and it is called on both serving entry points
  (`agent/api.py:82` for HTTP `/chat`, `agent/chat.py:52` for the CLI). 26 unit tests.
- **Detected:** E6 is a Luhn-checked detector in the eval suite. It finds the planted
  test card in every experiment run, which is why E6 reads 32/33.
- **Not demonstrated:** `pii.redacted` has **never appeared in a captured span**, in
  zero of 13 captured runs. The reason is mundane and we would rather state it than
  let you discover it: `scripts/run_experiment.py` calls `run_agent()` in-process and
  bypasses both serving handlers, so the redactor is not in that path. Separately,
  `pii.redacted` is carried inside the OpenInference `metadata` attribute, not as a
  top-level span attribute, so a monitor filtering on a bare `pii.redacted` attribute
  would never fire.

The control is real and unit-verifiable. The captured evidence proves the detector,
not the redactor. Closing that gap is a harness change, not a design change.
Whether redacted content may go to an external judge at all is an open question for
Luke, along with whether residency binds us to self-hosted Phoenix.
[docs/PII_BOUNDARY.md; docs/REQUIREMENT_MAP.md row 12]

## 18. The human gate, and why we are deviating from what Nick asked for

Nick asked for failures to auto-append to the eval dataset with no human gate. We
built the auto-append (slide 11). **We are recommending against automating the last
step, promotion to production, and we want that on the record as a recommendation,
not a misunderstanding.**

The reason is narrow and specific: an automated promotion gate has to rest on a
metric, and the judged metrics are not calibrated (slide 16). Gating on an
uncalibrated judge is worse than no gate, because it launders the defect. The
deterministic evals are trustworthy; the judged ones are not yet.

So we made the gate a **structural property of the code, not a policy in a document**:

- `scripts/approval.py` binds `PENDING_DECISION = "pending_human_review"` and
  `write_approval` **raises `ValueError` on any other decision value**, always with a
  null reviewer and a null decision time.
- There is no code path by which a loop run can self-approve. A human records a real
  decision by editing the written file.
- `tests/test_approval_record.py` asserts this **by AST**, checking that the
  `decision` key is bound to the `PENDING_DECISION` name rather than to a string
  literal, so the guarantee cannot be edited away without a test failing. 14 tests.
- The record also captures `git_dirty` next to the commit sha, because a run against
  a dirty tree is not reproducible from the sha alone. Tonight's run: `061307e`,
  `git_dirty: true`.

Tonight's gate output, verbatim: decision `pending_human_review`, reviewer `null`,
regressions `[]`, **PROMOTION: BLOCKED pending human approval.** The proposal that
takes E2 from 11% to 100% with zero regressions is sitting there unpromoted, because
the loop is incapable of promoting it. That is the demo.

Say the status plainly, because it is the point of the whole gate: **the best result
in this deck is not shipped and not merged.** It is proposed by the loop, validated
offline against the versioned dataset, and waiting on a human. `approval.json` cannot
record any other state, and the two env flags are still off by default. The candidate
gets promoted when one of you decides it should be, not when a script decides.

We would revisit this the moment the judges clear the bar on slide 16.
[docs/loop-runs/interview2-final/approval.json; scripts/approval.py;
docs/REQUIREMENT_MAP.md row 24]

## 19. Your "85 to 90 percent", made precise (a proposal, not a running rule)

Proposed promotion criteria, and we want you to edit these today:

- Groundedness E1 at or above an **85% floor** on the versioned golden dataset, 90%
  target. 85 is Nick's floor, not a number we invented.
- **Zero fabricated-inventory regressions**, as a hard blocker rather than a
  percentage.
- Telemetry non-regression on latency, tokens, and cost.
- All of the above are **necessary, not sufficient**. Promotion additionally requires
  PM sign-off, per slide 18.

Two honest notes. First, this numeric gate is a **written proposal only**; it is not
enforced anywhere in code and it is not in `docs/MONITORS.md`. Second, one question
is genuinely still open and it changes the number: is 85 to 90 percent measured
**per answer or per conversation**? A five-turn planning session that is 90% correct
per answer can still be 100% wrong per conversation.

Related: the follow-up email in `docs/FOLLOWUP_QUESTIONS.md` that puts the human-gate
recommendation and the booking-scope note in writing is **draft status and has not
been sent**. So today's session is the first time you are hearing both, which is why
they are slides 2 and 18 rather than a footnote.
[docs/FOLLOWUP_QUESTIONS.md; docs/REQUIREMENT_MAP.md row 4]

## 20. Does this satisfy what you asked for in Interview 1?

Twenty-one Interview 1 requirements, one row each, plus 5 delivered beyond them,
with a status word we do not soften:
`IMPLEMENTED` means code exists and a captured artifact scores it;
`IMPLEMENTED (not fired)` means the code exists and is unit-tested but no captured
run exercises it; `PROPOSED` means a specification with no running system behind it;
`GAP` means nothing is built.

One clarification before you read the column, because it is the easiest row in this
deck to misread: **`IMPLEMENTED` describes the evaluation and loop system we built
around your agent. It never means your agent's production behavior has been
changed.** The two agent-side candidates remain env-gated, default-off, and pending
human approval (slides 3, 15, 18).

Headlines from that table:

| Requirement | Status |
|---|---|
| Nick: "where in the chain did it go wrong" | IMPLEMENTED (attribution on every eval result) |
| Nick: "hallucinates a hotel that does not exist" | IMPLEMENTED (E1 + E5 + 9 synthetic probes) |
| Nick: incorrect tool usage as first automation target | IMPLEMENTED (E3 caught a real date-format slip at 22/24 in an earlier B run) |
| Nick: failures auto-append to the dataset | IMPLEMENTED (replayable schema, 18 tests) |
| Nick: automated improvement loop end to end | IMPLEMENTED (7 stages, nightly cron) |
| Nick: "85, 90% would be sufficient" | **PROPOSED** numeric gate; human half IMPLEMENTED in code |
| Nick: token consumption on the rails | E7 IMPLEMENTED; monitors **PROPOSED** |
| Nick: "plug and play" for future agents | IMPLEMENTED (evals read OpenInference spans, not the agent) |
| Nick: no human gate wanted | **Deliberate deviation**, slide 18 |
| An: automate the manual spot-check | IMPLEMENTED (8 deterministic + 3 judges + calibration workflow) |
| An: automate tone review | IMPLEMENTED, **monitor-only**, provisional rubric |
| Luke: grounded in the tool calls | IMPLEMENTED (exact set membership, after 4 adjudicated grader fixes, slide 9) |
| Luke: no hallucinating around API failures | IMPLEMENTED (E5) |
| Luke: conflicting/outdated session context | **IMPLEMENTED** (E10, 21 tests), not a backlog item |
| Luke: block PII from the provider | Redactor IMPLEMENTED; **firing NOT DEMONSTRATED**, slide 17 |
| Luke: do not rebuild the agent | IMPLEMENTED (zero frameworks, shipped prompt byte-identical) |
| Nick: booking conversion +50% | Proxies IMPLEMENTED; **conversion NOT MEASURABLE offline** |

That last row is the one to dwell on. **Booking conversion has never been measured
here and cannot be, because no transactional booking exists.** Groundedness and
empty-result honesty are our leading proxies. The join key from trace to booking
outcome is a design specification in the production plan, to be instrumented at
rollout. [docs/REQUIREMENT_MAP.md]

## 21. Production readiness at millions of requests a day

Nine sections against the brief's checklist, all anchored in what was built this week
rather than in generic advice.

- **Architecture:** sync serving split from async eval, with a durable queue at the
  seam. The tracer already writes two independent sinks, so the seam exists today.
- **Evaluation split:** deterministic evals on 100% of traffic (they are free),
  judges on a sample (they are not).
- **Redaction at source**, before the provider call, per slide 17.
- **Rollback:** every change is env-gated and versioned, so rollback is a flag flip
  and not a deploy.
- **Canary lanes** keyed on the `prompt_version` / `agent_version` span attributes
  that every span already carries.
- **Repo-specific risks named rather than hidden:** in-process conversation state
  breaks multi-worker; there is no auth or rate limit on `POST /chat` (explicitly out
  of scope per Luke).
- **One of those risks is already closed.** The unbounded `while True` agent loop now
  enforces `MAX_AGENT_ITERATIONS` (default 8) and `AGENT_DEADLINE_SECONDS`
  (default 60), sets `agent.limit_breached` on the root span, marks span status
  ERROR, and returns a fixed fallback sentence that admits the turn did not complete
  and **fabricates no itinerary content**. 6 tests.
- **Portability:** Phoenix self-hosted is the data-residency fallback and runs on the
  same OpenInference spans with no eval rewrite.

**Monitors: 8 specified, 0 configured in Arize AX, 0 alert channels provisioned, 0
alerts ever fired.** We are not going to demo a monitor. The AX free tier has no
monitors-as-code path, so the honest artifact is a specification a human executes,
and the runbook of exact UI steps is in the document. 5 of the 8 thresholds are
grounded in measured values from a real run; the rest carry an explicit TBD.
[docs/PRODUCTION_READINESS.md; docs/MONITORS.md]

## 22. Skills and tooling usage: what we used, how it helped, what we would automate

**What we used.** `arize-otel register()` for the AX-ready tracer provider;
`openinference-instrumentation-anthropic` for automatic LLM spans with token counts;
OpenInference semantic conventions and span kinds so AX renders CHAIN / TOOL / LLM
trees natively and the same design ports to self-hosted Phoenix unchanged;
`using_session` so `conversation_id` becomes `session.id` with no signature changes;
`ArizeClient.datasets.create` to upload the golden dataset (31 examples, verified by
read-back); `ArizeClient.spans.update_evaluations` to attach 697 eval labels to root
spans so scores render on traces; `ArizeClient.spans.export_to_df` as an independent
read-back surface to verify every upload claim.

**How it helped, including the parts we only learned by using it.**
`TracerProvider.add_span_processor()` **removes** the default AX exporter when a
custom processor is added afterwards; custom processors must go through
`register(span_processors=[...])`. Confirmed in `arize-otel` 0.13.0 source. Without
catching that, the entire baseline would have written to local disk and silently
never reached AX. We also found that AX stores span ids as bare hex without the OTel
`0x` prefix, and that BatchSpanProcessor delivery depends on graceful shutdown, which
is why the capture script SIGTERMs uvicorn and the experiment runner calls
`force_flush` explicitly. Two traces lost to a shutdown flush race were re-ingested
with their original ids and timestamps using a custom OTel `IdGenerator`.

**What we would automate further in a real deployment.**

1. Online eval tasks in AX running E1 / E2 / E5 continuously on sampled production
   traces, instead of batch-scoring exported files.
2. The feedback loop as an AX-integrated scheduled job using the Airflow provider
   operators for datasets, experiments, and evaluators, instead of a GitHub Actions
   cron.
3. CI gating: run the experiment suite on every prompt or tool PR and block merge on
   primary-metric regression, with the AX experiment link posted into the PR.
4. Monitor-driven rollback: a P0 breach flips the env-gated candidate off
   automatically, with human review after the fact rather than before. Note this is
   the one place we would accept automation without a human in front of it, because
   the automated action is a **revert to your current shipped behavior**, which is
   the safe direction.
5. Judge calibration as AX annotations rather than a CSV sheet, so An's team labels
   in the same UI where they read the trace.

[docs/SKILLS_LOG.md]

## 23. What we would do next, in order

1. **Merge your golden dataset** when it arrives. Ours is versioned and merge-ready;
   the question has been open since Interview 1.
2. **A real calibration round with An's team.** At least 50 domain-owner labels per
   judge and at least 10 labelled failures, because until a judge is shown failures
   it can be caught on, agreement measures nothing. This is the single item blocking
   any judge from gating a release.
3. **Get An's tone rubric** and replace the provisional E11 rubric, then repeat the
   calibration.
4. **Answer the per-answer versus per-conversation question** so slide 19 becomes an
   enforceable rule instead of a proposal.
5. **Close the PII evidence gap** by routing the experiment harness through the
   redacting path and promoting `pii.redacted` to a top-level span attribute so a
   monitor can filter on it.
6. **Apply the 8 monitor specs in the AX UI** and provision the alert channel.
7. **Work the backlog by severity**, starting with the ignored `date` on
   `search_flights`, which makes every flight answer ungrounded on date, always.
8. **Instrument the trace-to-booking join key** at rollout, which is the only way the
   +50% conversion goal ever becomes measurable rather than proxied.

[docs/BACKLOG.md; docs/REQUIREMENT_MAP.md section 3; docs/JUDGE_CALIBRATION.md 5.1]
