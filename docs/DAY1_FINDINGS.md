# Day 1 Findings: Measured Baseline vs Code-Reading Predictions

## STATUS: DATED SNAPSHOT. NOT A CURRENT-STATE DOCUMENT.

**This document records what was true at the baseline capture, before any fix was
made.** It is dated evidence, not a description of the system as it stands.

- Snapshot subject: `docs/baseline/2026-07-19/`, `captured_at`
  `2026-07-19T15:27:57Z`, `git_sha 0080b11`, `prompt_version v0-shipped`,
  `agent_version baseline-0080b11`, model `claude-haiku-4-5`
  (`docs/baseline/2026-07-19/manifest.json`).
- 23 turns, 78 spans, 22 sessions. Frozen and immutable.
- Snapshot written: 2026-07-19. Reviewed and corrected: 2026-07-21.
- Single run at default temperature. Behaviors may vary run to run.

Everything in sections 1 through 4 describes the **as-shipped agent**. Neither fix
(D-01 prompt, D-02 `search_flights` direction) was in effect. For what changed
afterwards, read section 5, then `docs/experiments/COMPARISON.md`.

---

## 1. Headline numbers

Recomputed from `docs/baseline/2026-07-19/spans.jsonl` on 2026-07-21; every figure
below reproduced exactly.

- 23 turns; **16 made at least one tool call, 7 made none**. 16 tool spans in total,
  so no turn issued more than one tool call.
- 1 tool call returned an empty result: `search_flights`
  `{"origin": "Denver", "destination": "Miami", "date": "2026-08-14"}` returned `[]`.
- **0 tool errors** in this run (`tool.error` absent from all 16 tool spans).
- Median turn latency **2885 ms** (min 816 ms, max 5524 ms).
- **50,655 tokens** total (45,057 prompt + 5,598 completion), **$0.073047** at
  `claude-haiku-4-5` rates of $1.00/Mtok input and $5.00/Mtok output.

## 2. Deterministic eval scores on this capture

The original version of this document said full eval scores would "land when E1-E7 run
over this capture (Day 2)". **They have since run.** Measured scores, from
`docs/evals/baseline-2026-07-19/summary.md` and (for E10, added later)
`docs/evals/e10-scoring-baseline/summary.md`:

| Eval | Name | Applicable | Pass | Pass rate |
|---|---|---:|---:|---:|
| E1 | fabricated_entity | 23 | 23 | **100%** |
| E2 | flight_direction | 6 | 0 | **0%** |
| E3 | tool_call_validity | 16 | 16 | 100% |
| E4 | itinerary_day_count | 2 | 0 | **0%** |
| E5 | empty_result_honesty | 1 | 1 | 100% |
| E6 | pii | 23 | 23 | 100% |
| E7 | guardrails | 23 | 23 | 100% |
| E10 | conflicting_context | 1 | 1 | 100% |

Judges on the same capture (`docs/evals/judges-baseline-2026-07-19/summary.md`):
E8 `clarification_quality` 23/23 = 100%, E9 `scope_adherence` 23/23 = 100%. E11 did
not exist yet and has never been run against this capture.

Eight failures in total: six E2, two E4. **Every one of them is attributed to the tool,
not the model.** That attribution split is the whole finding.

## 3. Measured vs predicted

`docs/REPO_FINDINGS.md` correctly labeled its model-behavior claims as inference pending
the Day 0 and Day 1 runs. Measurement supersedes them. Two predictions confirmed,
three overturned.

| Case | Predicted from code | Measured | Verdict |
|---|---|---|---|
| Denver hotel, "this weekend" | Fabricated hotel (the prompt forbids disclosure) | No tool call. The model asked clarifying questions, contradicting the prompt, and the example date it offered was stale: "2024-01-20" | Overturned |
| London hotel priced in euros | Fabricated price | The model disclosed it lacks real-time pricing, contradicting the prompt | Overturned |
| Denver to Miami, tool returned `[]` | Fabrication to fill the gap | Honest: "No flights were found from Denver to Miami on August 14, 2026", followed by three alternatives | Overturned |
| Tokyo to Los Angeles (D-02) | Backwards flight presented confidently | Exactly as predicted. NH 105 (true route Los Angeles to Tokyo) presented with invented corroborating detail: "direct flight", "crossing the International Date Line" | Confirmed |
| New York to Miami (D-02, smoke test) | One of three results backwards | Confirmed. AA 2210 (true route Miami to New York) presented as a normal option | Confirmed |

E2's six baseline failures span five routes and are all the same defect: AA 2210
(NY/Miami, twice), UA 838 (SF/Tokyo), AF 1681 (London/Paris), NH 105 (Tokyo/LA),
UA 2045 (Chicago/Denver). The user input and failure reason for each are in
`docs/evals/baseline-2026-07-19/summary.md`; per-trace evidence is in
`docs/evals/baseline-2026-07-19/results.jsonl`.

## 4. What this did to the story

1. **The strongest finding held.** Tool-poisoned answers reproduce on demand, the model
   cannot detect them. The as-shipped `search_flights` (`agent/tools.py:34-45`, the
   non-`FLIGHT_TOOL_FIX` branch) matches
   origin and destination as an **unordered set** and then **omits both fields from the
   result dicts it returns**, so the model is handed a backwards flight with no route
   information to check it against. Only span-level attribution places the fault at the
   tool instead of the model. This is the brief's "first mistake in the chain"
   requirement, with live evidence.
2. **The prompt defect reframed.** The shipped three-line prompt was not, on this model
   and this run, causing mass hallucination. It was being **ignored**. The model asked
   clarifying questions and disclosed system limitations repeatedly across 23 turns,
   both forbidden by the prompt. An instruction set the model refuses provides no
   control surface: you cannot tune behavior by editing instructions the model does not
   follow. So D-01 aligns the prompt with the desired **and** observed behavior, and the
   thing to measure is compliance, not only hallucination-rate reduction.
3. **The groundedness-bar conversation sharpened.** The prediction was that naive
   per-reply groundedness on this traffic "may already look high". It is now measured
   and it is not just high, it is **saturated: E1 = 100% at baseline**. The eval that
   matters is the one that splits by attribution. Flight-direction answers are
   systematically poisoned by the tool while looking perfectly grounded to any
   reply-level check.
4. **The honest-methods slide writes itself.** Predicted from code, measured from
   traces, two predictions confirmed and three overturned. That is the argument for
   tracing before fixing, in one table.

### Micro-finding: no current-date anchor (D-09)

The Denver clarifying reply offered "2024-01-20" as an example date, and the London
weather reply offered "2024-01-16". The shipped agent has no current-date anchor, so
even its good behavior carries a stale-date smell. This supported adding today's date
to the prompt as part of D-01.

---

## 5. What has changed since this snapshot

Added 2026-07-21. Read this before quoting anything above as current.

- **D-01 is implemented, behind `PROMPT_VARIANT=v1`.** `agent/prompt.py:17` now injects
  `date.today().isoformat()` into the system prompt with an explicit instruction to use
  it for relative dates, closing the "2024-01-20" micro-finding above. The v1 prompt
  also carries strict grounding, one-consolidated-clarifying-question, and scope rules.
  The as-shipped three-line prompt is still the default (`_V0_SYSTEM_PROMPT`) so the
  baseline stays reproducible.
- **D-02 is implemented, behind `FLIGHT_TOOL_FIX=1`.** E2 `flight_direction` measured
  **8/8 = 100%** on `candidate-B-toolfix` and on `candidate-AB-combined`, against 1/9 =
  11% on `control-v0` (`docs/experiments/COMPARISON.md`). The 0/6 figure in section 2
  is the pre-fix number and stays that way.
- **D-01 produced no deterministic eval delta.** On `candidate-A-prompt`, E1, E3, E5,
  E6, and E7 are all d+0pp and E2 is unchanged at 11%. Prediction 2 above is therefore
  vindicated in an unexpected direction: the prompt fix buys controllability, not a
  metric point. Say it that way.
- **The unbounded agent loop is capped.** At the time of this capture `agent/loop.py`
  was `while True` with no iteration cap and no timeout. It now enforces
  `MAX_AGENT_ITERATIONS` (default 8) and `AGENT_DEADLINE_SECONDS` (default 60) from
  `agent/config.py:15-16`, emits `agent.limit_breached` on breach, and returns a
  truthful fallback. Measured iteration counts in this snapshot were min 1, max 2, so
  the cap would never have fired on it.
- **E10 and E11 were added after this snapshot.** E10 `conflicting_context` was
  backfilled over this capture (1 applicable, 1 pass). E11 `tone_quality` was not, and
  no tone number exists for the baseline.
- **The three judges are monitor-only. None gates a release.** Be careful with the
  section 2 judge row: 23/23 on E8 and E9 is a **pass rate**, not evidence that the
  judges are correct. Separately, blind human labelling later measured judge-vs-human
  **agreement** at 96/96 = 100% on `candidate-AB-combined`, and
  `docs/JUDGE_CALIBRATION.md` explains at length why that number is nearly
  uninformative: 93 of 99 rows are "pass", so there is no variance to discriminate on,
  and a judge hardwired to answer "pass" would have scored identically. Do not cite
  either number as judge validation.
- **Defects observed here that remain deliberately unfixed:** E4 / D-05 (the
  `create_itinerary` off-by-one) is still 0% on every run including the candidates, and
  the weather and hotel coverage gaps (D-07) are still open. Both are in
  `docs/BACKLOG.md` with severity and owner. Leaving them there was the decision, not
  an oversight.
