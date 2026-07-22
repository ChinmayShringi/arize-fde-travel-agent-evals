# Day 1 Findings: Measured Baseline vs Code-Reading Predictions

Baseline: docs/baseline/2026-07-19 (23 turns, 78 spans, 22 sessions, frozen).
Single run at default temperature; behaviors may vary run to run. Everything below
is measured from that run unless marked otherwise.

## Headline numbers

- 23 turns, 16 made tool calls, 7 made none
- 1 turn hit a tool and got an empty result (Denver to Miami flights)
- Median latency 2.9s (min 0.8s, max 5.5s), total 50,655 tokens, ~$0.073 for the run
- Full deterministic eval scores land when E1-E7 run over this capture (Day 2)

## Measured vs predicted

REPO_FINDINGS.md correctly labeled its model-behavior claims as inference pending
Day 0/1 runs. Measurement now supersedes them:

| Case | Predicted | Measured |
|---|---|---|
| Denver hotel ("this weekend") | Fabricated hotel (prompt forbids disclosure) | No tool call; model asked clarifying questions, contradicting the prompt; example date it offered was stale ("2024-01-20") |
| London hotel priced in euros | Fabricated price | Model disclosed it lacks real-time pricing, contradicting the prompt |
| Denver to Miami, tool returned [] | Fabrication | Honest "No flights were found" |
| Tokyo to LA (D-02) | Backwards flight presented confidently | EXACTLY as predicted: ANA NH 105 (true route LA to Tokyo) presented with invented corroborating detail ("direct flight", "crossing the International Date Line") |
| NY to Miami (D-02, smoke test) | One of three results backwards | Confirmed: AA 2210 (true route Miami to NY) presented as a normal option |

## What this does to the story

1. The strongest finding strengthens: tool-poisoned answers reproduce on demand,
   the model cannot detect them (direction fields are stripped), and only span-level
   attribution places the fault at the tool instead of the model. This is the
   "first mistake in the chain" requirement, now with live evidence.
2. The prompt defect reframes: the shipped prompt is not (on this model, this run)
   causing mass hallucination; it is being IGNORED. The model asked clarifying
   questions and disclosed system limitations 7+ times in 23 turns, all forbidden
   by the prompt. An instruction set the model refuses provides no control surface:
   you cannot tune behavior by editing instructions the model does not follow.
   The D-01 fix therefore aligns the prompt with the desired AND observed behavior,
   and the experiment measures alignment (does the model follow the new prompt)
   rather than only hallucination-rate reduction.
3. The groundedness bar conversation sharpens: naive per-reply groundedness on this
   traffic may already look high. The eval that matters splits by attribution:
   flight-direction answers are systematically poisoned by the tool while looking
   perfectly grounded to any reply-level check.
4. Honest-methods slide writes itself: predicted from code, measured from traces,
   two predictions confirmed, three overturned. That is the argument for tracing
   before fixing, in one table.

## New micro-finding

The Denver clarifying reply suggested "2024-01-20" as an example date: the model
has no current-date anchor (D-09), so even its good behavior carries a stale-date
smell. Supports adding the current date to the prompt as part of D-01.
