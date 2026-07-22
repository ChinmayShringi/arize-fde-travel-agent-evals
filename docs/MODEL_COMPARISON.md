# Model Comparison: Measured on the Golden Dataset (33 turns, same evals)

Nick's ask: "we will probably need a way to test whether changing the model will
significantly affect the agent... which model works best." Answer below, measured
with the experiment harness (--model axis), single run per cell. Every cell is a
33-turn golden-dataset run scored with the same suite (v1.2 + E10; results in
docs/evals/e10-scoring-<run>/). The Haiku-shipped cell is the control-v0 run.
Pricing per MTok: Haiku $1/$5, Sonnet 5 $3/$15, Opus 4.8 $15/$75.

## The matrix

| Model | Prompt | E1 grounded | E2 direction | E5 empty-honesty | Cost/run | Median latency |
|---|---|---|---|---|---|---|
| Haiku 4.5 | shipped | 100% | 11% | 100% | $0.110 | 3.5s |
| Sonnet 5 | shipped | **88%** | 8% | **57%** | $0.610 | 6.3s |
| Opus 4.8 | shipped | **88%** | 10% | **62%** | $2.725 | 8.5s |
| Haiku 4.5 | fixed (v1 + tool fix) | 100% | **100%** | 100% | $0.105 | 2.7s |
| Sonnet 5 | fixed | 100% | **100%** | 100% | $0.409 | 4.4s |
| Opus 4.8 | fixed | 100% | **100%** | 100% | $1.922 | 5.1s |

> Evaluator-version caveat: the E1 figures in this table were scored under evaluator
> v1.2. The `model-opus-4-8` run carries the same section-heading false positive that
> was adjudicated as finding 4 (`docs/EVAL_ADJUDICATION.md`); re-scored under v1.3.1 its
> E1 is 30/33 (91%), not 29/33 (88%). The captured artifact is left unedited as evidence.
> The direction of the finding is unchanged: frontier models on the shipped prompt still
> fabricate where Haiku does not, because they obey the prompt Haiku ignores.


E4 (itinerary off-by-one) is 0% in every cell: it is the backlogged tool bug no
candidate was authorized to fix; no model can compensate for it, which is itself
evidence for tool-level attribution. E6's constant single "failure" is the planted
card probe detecting correctly. E10 (conflicting context) passed 2/2 in every
cell (and 1/1 on the separate 23-turn immutable baseline capture).

## The headline finding

On the SHIPPED prompt, upgrading the model makes groundedness WORSE at 5-25x the
cost: Sonnet 5 and Opus 4.8 invented real-world hotels (Brown Palace, Crawford
Hotel, Kimpton Hotel Born, Hotel Van Zandt, Hotel Gracery Shinjuku) with concrete
prices after search_hotels returned empty: adjudicated against the raw replies,
these are genuine fabrications, not eval artifacts (one minor artifact noted: a
section heading "Hotel Recommendations" flagged on one Opus trace).

Mechanism: the shipped prompt orders the model to always give concrete options and
never disclose system limitations. Haiku is a weak enough instruction-follower to
ignore those orders (Day 1 finding); the frontier models OBEY them. Better
instruction-following turns a bad prompt into worse behavior. Nick's exact
nightmare scenario ("suppose the agent hallucinates a hotel that does not exist")
reproduced on demand, on the newest models, with real hotel names.

With the loop-proposed fixes applied, all three models are fully grounded, and
model choice becomes what it should be: a quality/latency/cost tradeoff. On this
workload Haiku fixed is the value pick ($0.105, 2.7s, 100 percent across E1/E2/E5);
Sonnet 5 fixed buys nothing measurable here for 3.9x the cost; if richer itinerary
prose matters (E11 tone scores can arbitrate), that is the experiment to run next.

## What this proves about the process

A bare model swap would have shipped a 12-point groundedness regression at 5.6x
cost while looking like an upgrade. The eval gate caught it in one run for under
a dollar. This is the concrete argument that (1) the eval suite must gate model
changes exactly as it gates prompt/tool changes, and (2) attribution matters:
the same E1 failures on a naive dashboard would read "the new model hallucinates";
the truth is "the new model obeys your broken prompt".

Caveats, stated plainly: single run per cell (deterministic evals; sampling
variance affects which turns call tools, so applicable-counts differ per cell);
tone/style differences between models not yet scored (E11 exists for exactly
that); Opus/Sonnet pricing taken from current published rates.
