# Token and Cost Strategy: Measured, Not Assumed

Every number below is from a real run in docs/experiments/ or the sourced research
brief (wave-1 research agent, web sources cited in its report). Pricing basis:
claude-haiku-4-5 at $1/MTok input, $5/MTok output; an output token costs 5x an
input token.

## Where the money goes on this agent

Golden-dataset run (33 turns, ~56 model calls): ~67-79k input tokens, ~5-8.5k
output tokens. Input is ~60-65 percent of run cost; output the rest. Two levers,
one per side.

## Lever 1: output concision (works now, at any scale)

The measured chain, same dataset, same evals:

| run | output tokens | median latency | notes |
|---|---|---|---|
| control (shipped prompt) | 8,496-8,587 | ~2.9-3.5s | across the two control runs |
| A+B (v1 prompt + tool fix) | 6,807 | 2724 ms | -21 percent output vs control |
| C (v2-concise + tool fix) | 4,905 | 2200 ms | -28 percent vs A+B, -42 percent vs control |

v2-concise adds explicit output-style rules (lead with the answer, no filler, max
3 options, one warm sentence). Inspired by the "caveman" skill's finding that
agent verbosity is mostly filler; adapted for a customer-facing surface instead
of caveman-speak, and gated on the E11 tone judge so brevity never buys a tone
regression silently. MEASURED TRADEOFF: A+B holds E11 tone at 100 percent
(33/33); v2-concise scores 94 percent (31/33, two flags) for its extra -28
percent output tokens. Recommendation: ship v1 (A+B) as primary; v2 is the
quantified concision option for Anne's team to accept or decline against her
rubric. Cost effect at demo scale is small (-1.6 percent: the longer
v2 prompt adds input) but latency -19 percent is a real UX win, and at production
volume output tokens are the 5x-priced class.

## Lever 2: prompt caching (the production lever; measured honestly at zero here)

Implemented env-gated (PROMPT_CACHE=1) with the correct breakpoint (top-level
cache_control covering message history; verified against anthropic SDK 0.116.0).
Measured twice on the golden dataset: ZERO cache reads and writes both times.
Root cause, definitively: our conversations are short (roughly 56 calls averaging
about 1,200 tokens of context each) and never cross Haiku's minimum cacheable
prefix. There is nothing big enough to cache at demo scale.

When it pays: production sessions with long planning conversations. Research math
at a 60-70k-token steady-state context: cache reads bill at 0.1x, writes at
1.25x, netting 70-85 percent input savings, which is most of the bill at that
scale. The implementation ships ready; the flag flips when session lengths justify
it. Monitor usage.cache_read_input_tokens to catch silent invalidation.

## Levers evaluated and rejected (sourced in the research brief)

- LLMLingua-family prompt compression: research-grade; needs its own local model,
  savings do not transfer to hosted APIs, and compressing tool schemas risks
  dropping load-bearing tokens. Skip.
- Server-side context editing/compaction betas: not documented for Haiku; DIY
  tool-result compaction (replacing consumed JSON with a summary) is the
  production-plan path, batched so it does not thrash the cache.

## Model choice is a cost lever with a trap (measured)

Same shipped prompt, same dataset: claude-sonnet-5 costs 3.7x and claude-opus-4-8
8.3x per run vs Haiku, with 2-3x the latency, and BOTH fabricate real-sounding
hotels with prices on empty tool results (E1 88 percent, E5 57-62 percent vs
Haiku's 100 percent): stronger instruction-following obeys the shipped prompt's
gag rules that Haiku ignores. Model upgrades without the eval gate are a
groundedness regression at 3.7x to 8.3x the price. The fixed-prompt model runs quantify
how much of that the prompt fix recovers (docs/experiments/model-*-fixed).

## Bottom line for Nick

Track first (E7 does), then optimize: concision now (output side, free win,
tone-gated), caching at production session lengths (input side, the big lever),
model choice only through the experiment harness, never as a bare swap.
