# Monitors

## STATUS: PROPOSED CONFIGURATION. ZERO MONITORS ARE CURRENTLY LIVE.

**Nothing in this document is deployed.** As of 2026-07-21, **0 of the 8 monitors
below are configured in Arize AX.** No monitor has ever fired, no alert has ever
been routed, and no notification channel has been provisioned.

Why it is a document and not code: the project runs on the **AX free tier**, which
has no monitors-as-code path (no API, no Terraform provider, no config export for
monitors). Monitors on the free tier are created by hand in the web UI. So the
honest artifact is a **specification a human executes**, and the "Exact AX UI
steps" section at the bottom is that execution runbook.

Do not present any monitor here as observable in a demo. The correct claim is:
"here is the monitor specification, grounded in measured baseline values, ready to
be applied." Anything stronger is false.

| | |
|---|---|
| Monitors specified | 8 |
| Monitors configured in AX | **0** |
| Alert channels provisioned | **0** |
| Alerts ever fired | **0** |
| Thresholds fully grounded in a measured run | 5 (monitors 1, 2, 3, 5, 6) |
| Thresholds needing no calibration (any-occurrence rule) | 1 (monitor 7b) |
| Thresholds carrying an explicit TBD | monitor 4, monitor 7a, and monitor 8's per-session view |
| Monitors expected to fire on today's data, deliberately | 2 (monitor 2 pre-fix, monitor 5 while backlog D-07 is open) |

Three numeric claims in an earlier version of this document did not survive a
recount against the captured spans, and are corrected in place with the
computation shown: the **tool-error rate** (was "0% in both runs", is 3.85% in
control-v0 and 5.68% across all runs), the **iteration ceiling** (was 2 with a
gap of 6, is 3 with a gap of 5), and the **tokens-per-session threshold** (was
5,000, which a real captured 6,221-token baseline session already breached).

## Required-type coverage

Two sources define the required set, and they are cited separately because they
say different things. `docs/FINAL_PLAN.md:117-119` names **5** types explicitly
(groundedness rate, loop rate, p95 latency, tokens/session, tool-error rate).
`docs/REMEDIATION_PLAN.md:52` (audit item P1-09) raises that to **7** by adding
PII redaction detection rate and cost per interaction, and records that 3 of the
7 were missing here. This document previously specified 5 monitors and covered
only 4 of the 7. The three gaps are now closed.

| # | Required type | Covered by | Status |
|---|---|---|---|
| 1 | Groundedness rate | Monitor 1 | Was present |
| 2 | Loop rate / iteration limit | **Monitor 6** | **Was missing, added** |
| 3 | p95 latency | Monitor 3 | Was present |
| 4 | Tokens per session | Monitor 4 | Was present |
| 5 | Tool-error rate | Monitor 5 | Was present |
| 6 | PII redaction detection rate | **Monitor 7** | **Was missing, added** |
| 7 | Cost per interaction | **Monitor 8** | **Was missing, added** |
| -- | (project-specific addition) | Monitor 2 flight direction | Beyond the required 7 |

Monitor 2 is not one of the 7 required types. It is a project-specific monitor for
the primary defect this engagement fixed, and it is retained deliberately.

## Where the numbers come from

Thresholds are derived from real measured runs, never estimated. Two runs are
cited, and they are different populations, so they are never averaged together:

- **Baseline** (frozen, immutable): `docs/baseline/2026-07-19/spans.jsonl`,
  **23 `agent_turn` traces**, agent exactly as shipped. Eval scores in
  `docs/evals/baseline-2026-07-19/summary.md`.
- **control-v0** (experiment control): `docs/experiments/control-v0/`,
  **33 turns**, `turn_count: 33` in `manifest.json`, `git_sha 0080b11`. Scores in
  `docs/experiments/COMPARISON.md`.

| Signal | Baseline (23 traces) | control-v0 (33 turns) | Source |
|---|---|---|---|
| E1 fabricated_entity | 23/23 = 100% | 33/33 = 100% | summary.md; COMPARISON.md |
| E2 flight_direction | 0/6 = 100% failure | 1/9 = 11% pass | summary.md; COMPARISON.md |
| E6 pii | 23/23 = 100% (0 detections) | 32/33 = 97% (1 card detection) | summary.md; COMPARISON.md |
| E7 guardrails | 23/23 = 100% | 33/33 = 100% | summary.md; COMPARISON.md |
| Latency | median 2885 ms, p95 4780 ms, max 5524 ms | median 3485 ms, p95 5819 ms, max 8644 ms | recomputed from spans |
| Tokens | 50,655 total; mean 2,202/turn; max 3,576/turn | 75,469 total | spans; COMPARISON.md |
| Tokens per session | 22 sessions: max **6,221**, mean **2,302.5**, median 2,523.5, min 1,099 | 31 sessions: max **6,371**, mean **2,434.5**, median 2,489 | recomputed from spans |
| Iterations | min 1, max 2, mean 1.70 | min 1, max 2, mean 1.73 | spans; E7 evidence |
| Cost per turn | not separately recorded | mean $0.003328, min $0.001447, max $0.005968, total $0.1098 | E7 evidence `cost_usd` |
| Tool errors (`tool.error`) | **0 of 16 tool calls = 0%** | **1 of 26 tool calls = 3.85%** | recomputed from spans |
| Empty results (`tool.result_empty`, not errors) | 1 (`search_flights` Denver->Miami) | 5 (2 flights, 2 hotels, 1 weather) | recomputed from spans |

p95 above is nearest-rank on the per-turn root-span durations. Both runs are small
(23 and 33 turns) and synthetic. **Every threshold here is a provisional heuristic
anchored to a small sample, not a calibrated SLO.** Re-derive all of them after the
first week of real production traffic.

Empty tool results (for example "no flights found") are honest outcomes, **not**
tool errors. The tool-error monitor keys on tool exceptions and error payloads
only. Note the two attributes are not mutually exclusive: the one control-v0 tool
error (`get_weather` for London) carries **both** `tool.result_empty = true` and
`tool.error`, because `agent/loop.py:74` sets `tool.result_empty` to
`result == [] or error is not None`. Keying on `tool.error` picks that span up
correctly; keying on `tool.result_empty` would wrongly sweep in the **4** honest
no-result calls in the same run alongside it.

### Wider population, for the three monitors whose thresholds depend on it

The baseline and control-v0 columns above are the two runs the demo narrates, but
monitors 4, 5, and 6 are thresholded against **every span file captured in this
repo**. There are 14 `spans.jsonl` files under `docs/baseline/` and
`docs/experiments/`; **13 carry spans**, and the 14th,
`docs/baseline/2026-07-19-INVALID-stale-server/spans.jsonl`, is empty (0 lines)
and contributes nothing. Recomputed across the 13:

| Signal | All captured runs | Basis |
|---|---|---|
| Tool calls | 352 | spans with `openinference.span.kind == TOOL` |
| Tool errors (`tool.error`) | **20 = 5.68%**, per-run range **0% to 8.70%** | all 20 are `get_weather`: 19 London, 1 Barcelona |
| `agent_turn` spans | **419** | -- |
| `agent.iterations` | min 1, **max 3**, mean 1.75; distribution {1: 106, 2: 311, 3: 2} | the two 3-iteration turns are in `model-sonnet-5` and `model-sonnet-5-fixed` |
| Sessions | 394 | distinct `session.id` on `agent_turn` |
| Tokens per session | **max 7,748**, mean 2,667.8, median 2,642 | `model-sonnet-5` holds the max |

## Monitor specs

Every monitor carries: metric, signal source, measured baseline, threshold,
evaluation window, alert channel, owner, and severity.

Channel names below are **proposed routing targets**. No AX notification
integration is configured, so no channel exists yet to route to.

### 1. Groundedness rate (E1) -- P0

- **Metric:** E1 `fabricated_entity` pass rate (share of replies whose named
  hotels, flights, and prices all trace to a tool result this turn or in prior
  context).
- **Signal source:** E1 eval label logged to AX as an evaluation on the root span.
  Requires the eval-logging step (see UI steps) before this monitor can be built.
- **Baseline (measured):** 23/23 = 100% (baseline); 33/33 = 100% (control-v0).
- **Threshold:** alert when pass rate < 100% over the window. Any fabricated
  inventory at all is a page.
- **Evaluation window:** rolling 1 hour, minimum 20 evaluated traces before the
  monitor is allowed to fire (below that the rate is too noisy to act on).
- **Alert channel:** paging channel (on-call).
- **Owner:** Luke, VP Engineering. Groundedness is his stated requirement.
- **Severity:** P0. This is the "never hallucinate a booking" invariant.

### 2. Flight-direction failure rate (E2) -- P1

- **Metric:** E2 `flight_direction` failure rate (replies recommending a backwards
  flight relative to the user's requested origin and destination).
- **Signal source:** E2 eval label logged to AX as an evaluation on the root span.
- **Baseline (measured):** 100% failure pre-fix (0/6 baseline, 1/9 control-v0);
  100% pass post-fix (8/8 on candidate-B-toolfix and candidate-AB-combined,
  d+89pp, per COMPARISON.md).
- **Threshold:** before the fix ships, this monitor is **expected-red and stays
  muted with a note**. Once `FLIGHT_TOOL_FIX=1` is in production, alert when
  failure rate > 0 (any regression back to backwards flights).
- **Evaluation window:** rolling 1 day, minimum 10 evaluated flight-search traces.
- **Alert channel:** eng channel.
- **Owner:** Luke, VP Engineering.
- **Severity:** P1. Wrong-direction flights reach the user looking fully grounded.

### 3. p95 latency -- P2

- **Metric:** p95 of per-turn end-to-end latency (`agent_turn` root span duration).
- **Signal source:** span duration. AX ingests this already; no extra logging.
- **Baseline (measured):** p95 4780 ms / max 5524 ms (baseline);
  p95 5819 ms / max 8644 ms (control-v0).
- **Threshold:** alert when p95 > 10000 ms over the window. That is about 1.7x the
  higher of the two measured p95 values and above both measured maxima, so it
  catches regressions without firing on a normal tail.
- **Evaluation window:** rolling 1 hour, minimum 20 traces.
- **Alert channel:** eng channel.
- **Owner:** Luke, VP Engineering.
- **Severity:** P2.

### 4. Tokens per session -- P2

- **Metric:** total LLM tokens (prompt + completion) summed per session.
- **Signal source:** token-count span attributes, grouped by session id.
- **Baseline (measured, grouped by `session.id`, not by turn):**
  - baseline run, 22 sessions over 23 turns: **max 6,221**, mean **2,302.5**,
    median 2,523.5, min 1,099.
  - control-v0, 31 sessions over 33 turns: **max 6,371**, mean **2,434.5**,
    median 2,489.
  - across all 13 captured runs, 394 sessions: **max 7,748**, mean **2,667.8**.
  - for contrast, the busiest single *turn* is 3,576 (baseline) and 7,748
    (`model-sonnet-5`). The per-turn figure is the one previously quoted here and
    it is **not** the right basis for a per-session threshold.
- **Threshold:** alert when a session exceeds **15,000 tokens**. Arithmetic, so it
  is auditable: 15,000 / 7,748 = **1.94x** the largest session ever captured, and
  15,000 / 6,221 = 2.41x the largest baseline session.
  - **The previous 5,000 threshold was wrong and is corrected here.** A real
    captured baseline session (`9de7fde2-49f5-4df6-91d0-d40ad004dbcd`, 2 turns,
    **6,221 tokens**) already exceeds 5,000, so the monitor would have fired on
    the frozen baseline itself. That is a bad threshold, not a finding.
  - **Stated caveat, because it matters more than the number:** no captured
    session runs longer than **2 turns** (session-length distribution is 21
    single-turn plus 1 two-turn in baseline; 29 plus 2 in each experiment run).
    Token use per session grows roughly linearly with turns because the whole
    conversation is resent each turn, so a genuine 6-turn production session
    will plausibly clear 15,000 on its own. **This threshold is a placeholder
    against regressions in the synthetic population, not a production SLO.
    TBD - recalibrate against the real session-length distribution after the
    first week of production traffic**, and prefer tokens-per-turn-within-session
    over a flat session ceiling once that distribution is known.
- **Evaluation window:** per session, evaluated on session close; rolling 1 day for
  the alert-rate view.
- **Alert channel:** eng channel.
- **Owner:** Nick, Director of Product. Token consumption is his stated concern
  ("not going off the rails with our token consumption").
- **Severity:** P2 (cost and context-bloat early warning).

### 5. Tool-error rate -- P2

- **Metric:** share of tool calls that raise or return an error payload. **Empty
  results are excluded**; they are honest outcomes.
- **Signal source:** `tool.error` span attribute (`agent/loop.py:76`), which is
  set only when the tool returned an error. `tool.result_empty`
  (`agent/loop.py:74`) is a *different* attribute with a wider condition
  (`result == [] or error is not None`), so it is true on every error span **and**
  on honest no-result spans. This monitor must key on `tool.error` only.
- **Baseline (measured, recounted from spans):**
  - baseline run: **0 of 16 tool calls = 0%**.
  - control-v0: **1 of 26 tool calls = 3.85%**. The error is
    `get_weather` -> `"No weather data available for London"`, span status ERROR.
  - all 13 captured runs: **20 of 352 tool calls = 5.68%**, per-run range
    **0% to 8.70%**. All 20 are `get_weather` (19 London, 1 Barcelona).
  - **The earlier claim of "0% in both runs" was false** and is corrected here.
- **Threshold:** alert when error rate > 2% over the window. Baseline run is 0%;
  the small band absorbs one-off transient failures before paging.
- **This monitor is expected-red on the current fixture set, and that is
  deliberate.** 3.85% (control-v0) and 5.68% (all runs) both breach the 2% band.
  Two ways to resolve that, and the choice is stated rather than made quietly:
  - *Raise the threshold above 8.70%.* **Rejected.** The London errors are not
    transient infrastructure noise; they are a real data-coverage defect,
    backlog item **`docs/BACKLOG.md` D-07** (`data/weather.json` holds exactly
    **7** cities: Chicago, Los Angeles, Miami, New York, Paris, San Francisco,
    Tokyo. Neither London nor Barcelona is among them. See also
    `docs/REPO_FINDINGS.md:78` and `:105`). Setting the band above the defect
    rate would make the monitor green
    while the defect is live, which is precisely the failure this monitor exists
    to prevent.
  - *Keep 2% and declare the monitor expected-red until D-07 closes.* **Chosen.**
    Create it **muted with a note** referencing D-07, exactly as monitor 2 is
    muted pre-fix, and unmute once the fixture gap is closed or the agent is
    changed to state coverage limits explicitly. Muted-with-a-reason is honest;
    a threshold tuned around a known defect is not.
  - Consequence to say out loud in the demo: on today's fixtures this monitor
    would fire, and the thing it would be pointing at is D-07, not a regression.
- **Evaluation window:** rolling 1 hour, minimum 50 tool calls.
- **Alert channel:** eng channel.
- **Owner:** Luke, VP Engineering.
- **Severity:** P2.

### 6. Iteration-limit / deadline breach rate -- P1

Closes required type 2 (loop rate). This is the monitor that would have caught the
unbounded `while True` loop.

- **Metric:** share of turns whose root span carries the `agent.limit_breached`
  attribute, broken out by its value (`max_iterations` or `deadline`).
- **Signal source:** **`agent.limit_breached`** span attribute, set on the
  `agent_turn` root span at `agent/loop.py:155`. Values come from
  `_limit_breached()` at `agent/loop.py:29-36`: `"max_iterations"` when
  `iterations >= MAX_AGENT_ITERATIONS`, `"deadline"` when the wall-clock deadline
  passes. **The attribute is set only on a breach**, so its absence means the turn
  completed normally, and the monitor keys on presence, not on a boolean value.
  Companion attribute `agent.iterations` (`agent/loop.py:163`) carries the count on
  every turn and is the right thing to chart alongside the rate.
- **Caps being enforced (from `agent/config.py:15-16`):**
  `MAX_AGENT_ITERATIONS = 8` (env `MAX_AGENT_ITERATIONS`),
  `AGENT_DEADLINE_SECONDS = 60` (env `AGENT_DEADLINE_SECONDS`).
  The comment at `agent/config.py:11-14` states the same measured basis
  (419 captured `agent_turn` spans, maximum observed iteration count 3), and an
  independent recount for this document reproduced both figures exactly.
- **Baseline (measured, with a caveat):** in the two narrated runs, iterations were
  min 1, max 2 (mean 1.70 baseline, 1.73 control-v0). But the threshold must be
  set against **every** captured turn, not those two runs, so it was recounted
  across all 13 span files: **419 `agent_turn` spans, min 1, max 3, mean 1.75**,
  distribution {1 iteration: 106, 2: 311, 3: 2}. The two 3-iteration turns are in
  `docs/experiments/model-sonnet-5/spans.jsonl` and
  `docs/experiments/model-sonnet-5-fixed/spans.jsonl`.
  - So the observed ceiling is **3**, against a cap of 8: a gap of **5**
    iterations. **An earlier version of this document claimed a ceiling of 2 and
    a gap of 6; both were wrong** and are corrected here.
  - Caveat, stated plainly: the cap and the `agent.limit_breached` attribute did
    not exist when those runs were captured, so "zero breaches" is **recomputed
    from `agent.iterations`**, not an observation of the attribute itself. The
    attribute has zero production observations to date.
- **Threshold:** alert when breach rate > 0 over the window. Justified by the
  measured gap: the observed maximum is 3 against a cap of 8 (8 / 3 = **2.67x**),
  so any breach is at minimum a 2.7x deviation from the busiest turn ever
  recorded, and a 4x deviation from the 99.5% of turns (417 of 419) that finish
  in 1 or 2 iterations. Either way it is worth a human look.
- **Evaluation window:** rolling 1 hour, minimum 20 traces.
- **Alert channel:** eng channel.
- **Owner:** Luke, VP Engineering.
- **Severity:** P1. A breach means the user got a degraded fallback reply and no
  itinerary, and it is the leading indicator of a runaway-cost loop.

### 7. PII redaction detection rate -- P1 (P0 on a confirmed leak)

Closes required type 6. Two distinct conditions share one metric, so they are
specified as 7a and 7b and must be created as two monitors in the UI.

- **Metric:** share of turns whose root span carries `pii.redacted = true`, and the
  breakdown of `pii.types`.
- **Signal source, and the shape matters.** The redaction flag is emitted on **two
  different paths**, and a monitor that keys on the wrong one will silently read
  zero:
  1. `span.set_attribute("pii.redacted", True)` at `agent/api.py:36` and
     `agent/chat.py:29`. This tags whichever span is **current** at that moment,
     which is not guaranteed to be the root. `agent/api.py:30` says so in its own
     docstring: "Reliable root-span tagging is handled by `_pii_metadata` above."
  2. `using_metadata({"pii.redacted": True, "pii.types": [...]})` at
     `agent/api.py:23` and `agent/chat.py:17`. This is the reliable root-level
     path, but OpenInference serialises it into a **single `metadata` span
     attribute holding a JSON string**, not into a top-level `pii.redacted` field.
  Therefore an AX monitor must key on the **`metadata` attribute contents** (or a
  platform-derived field extracted from it), not on a bare top-level
  `pii.redacted`. See `docs/PII_BOUNDARY.md` section 2.
- **Baseline: TBD - calibrate after first production traffic.** Stated honestly:
  **these attributes appear in zero captured spans.** The experiment harness calls
  `run_agent` directly (`scripts/run_experiment.py:187`), bypassing `api.py` and
  `chat.py`, so no captured run exercised the redaction entry point. The only
  measured PII figures come from the **eval layer**, which scans text
  independently: E6 detected **0 of 23** turns (baseline) and **1 of 33** turns
  (control-v0, one Luhn-valid card, values redacted in the result row). A 1/33
  synthetic rate is not a usable production prior.

**7a. Redaction-rate drift -- P1**

- **Threshold:** **TBD - calibrate after first production traffic.** Establish the
  observed `pii.redacted = true` rate over the first full week, then alert on a
  material deviation in either direction. A sharp *drop* is as suspicious as a
  spike, because it can mean the redactor stopped matching.
- **Evaluation window:** rolling 1 day, minimum 200 turns.
- **Alert channel:** eng channel.
- **Owner:** Luke, VP Engineering.
- **Severity:** P1.

**7b. Redaction bypass (confirmed leak) -- P0**

- **Threshold:** alert on **any single occurrence**, over any window, of raw PII
  reaching a stored span, a model request, or an eval record. Concretely: E6 fails
  on a turn that went through the redaction path, or a span body matches an SSN or
  Luhn-valid card pattern.
- **Evaluation window:** rolling 5 minutes, no minimum volume. One event fires it.
- **Alert channel:** paging channel, plus the security contact.
- **Owner:** Luke, VP Engineering.
- **Severity:** P0. This is a direct breach of Luke's stated requirement that PII
  never reach the LLM provider.

### 8. Cost per interaction -- P2

Closes required type 7. Monitor 4 tracks tokens; this tracks money, and the two
diverge the moment the model or the input/output mix changes.

- **Metric:** USD cost per turn, and the rolling mean of it. Computed from
  prompt/completion token counts times the model rate.
- **Signal source:** token-count span attributes plus the model id. The same
  computation the eval layer already does; per-turn values are recorded as
  `cost_usd` in E7 evidence rows.
- **Baseline (measured, control-v0, 33 turns, `claude-haiku-4-5` at $1.00/Mtok
  input and $5.00/Mtok output):**
  - mean **$0.003328** per turn
  - min **$0.001447**, max **$0.005968** per turn
  - total **$0.109817** for the 33-turn run, which is the **$0.1098** in the
    `Total cost (USD)` row of COMPARISON.md
  - cross-check on the unrounded total: 0.109817 / 33 = 0.0033278, which rounds
    to the $0.003328 mean above.
  - cross-check against raw span token counts: control-v0 spans sum to **66,882**
    prompt and **8,587** completion tokens, and
    66,882 / 1e6 x $1.00 + 8,587 / 1e6 x $5.00 = **$0.109817**, reproducing the
    total exactly. The rate constants live in `evals/e_guardrails.py:140-155`.
- **Threshold (provisional, arithmetic shown so it is auditable):**
  - rolling mean cost/turn > **$0.0067** (2 x $0.003328 = $0.006656, rounded up
    to $0.0067), or
  - any single turn > **$0.0120** (2 x $0.005968 = $0.011936, rounded up to
    $0.0120).
  Both are heuristics anchored to a 33-turn synthetic run, in the same style as
  monitors 3 and 4. **Re-derive after the first week of production traffic.**
  Cost per *session* is deliberately not thresholded yet: no measured run has a
  representative multi-turn session length. **TBD - calibrate after first
  production traffic.**
- **Evaluation window:** rolling 1 day for the mean; per-turn for the single-turn
  ceiling.
- **Alert channel:** eng channel.
- **Owner:** Nick, Director of Product. He owns the business outcome and the
  spend.
- **Severity:** P2. Escalate to P1 if a cost breach coincides with a monitor 6
  breach, since that combination is the signature of a runaway loop.

## Severity routing

Routing is **proposed**. No channel or paging integration is configured.

| Severity | Trigger | Route |
|---|---|---|
| P0 | Fabricated inventory (monitor 1, E1 < 100%); confirmed PII leak (monitor 7b) | Page on-call immediately; open incident. |
| P1 | Coverage and scope (monitor 2 E2 > 0 post-fix); iteration/deadline breach (monitor 6); redaction-rate drift (monitor 7a) | Notify eng channel; triage same day. |
| P2 | Telemetry and cost (monitors 3, 4, 5, 8: latency, tokens, tool errors, cost) | Notify eng channel; review next business day. |

## Owner summary

| Owner | Role | Monitors |
|---|---|---|
| Luke | VP Engineering | 1, 2, 3, 5, 6, 7a, 7b |
| Nick | Director of Product | 4, 8 |
| Anne | Product Manager | Reviews the P1 and P2 digest weekly; no monitor pages her directly. |

Ownership is assignment of the **triage duty**, not of the AX account. All eight
monitors still need one human to sit down in the AX UI and create them.

## Exact AX UI steps

Prerequisite for eval-based monitors (1, 2, and the E6 half of 7): the E1, E2, and
E6 labels must be logged to AX as **evaluations on each trace** (log `eval_id` and
the `passed` flag as an evaluation or annotation on the root span) before the
monitor can select them. Telemetry monitors (3, 4, 5, 6, 7 attribute half, 8) read
span attributes AX already ingests, so they need no extra logging, **except**
monitors 6 and 7, whose attributes (`agent.limit_breached`, `pii.redacted`) exist
in code but have **not yet appeared in any exported span**. Confirm they are
arriving in AX before creating those two monitors, or they will sit permanently at
zero and read as green when they are actually blind.

Steps to create each monitor:

1. Sign in to AX and open the travel-agent project (the model or project the spans
   are exported to).
2. Open the Monitors tab, then click New Monitor.
3. Choose the monitor type:
   - Monitors 1, 2: Performance (or Custom Metric) over the logged evaluation.
     Select the eval by name (E1 `fabricated_entity` / E2 `flight_direction`) and
     use its pass/fail as the metric.
   - Monitor 3: Performance monitor on latency; pick the p95 aggregation.
   - Monitor 4: Data Quality (or Custom Metric) on the total token-count
     attribute, summed per session.
   - Monitor 5: Data Quality monitor on the `tool.error` attribute; metric =
     error rate. Do **not** point it at `tool.result_empty` (the London weather
     span carries both, and four honest no-result calls carry only the latter).
     Create it **muted**, with a note referencing backlog D-07, because at the
     measured 3.85% to 5.68% it breaches its own 2% band on today's fixtures.
   - Monitor 6: Data Quality (or Custom Metric) on `agent.limit_breached`; metric
     = share of traces where the attribute is present. Group by its value so
     `max_iterations` and `deadline` are separable.
   - Monitor 7a: Data Quality on the **`metadata`** attribute contents, not on a
     bare top-level `pii.redacted` (see the signal-source note above: the reliable
     root-level flag is serialised inside `metadata` as a JSON string). Metric =
     share of root spans whose metadata reports `pii.redacted` true. Leave the
     threshold unset until calibrated, and label the monitor "uncalibrated".
     Before creating it, confirm in the AX UI that the field is actually arriving,
     because it has never appeared in a captured span.
   - Monitor 7b: Custom Metric alerting on any occurrence; pair it with the E6
     eval and a raw-pattern check over span bodies.
   - Monitor 8: Custom Metric on computed cost per turn; configure both the
     rolling-mean and the single-turn ceiling.
4. Set the evaluation window and the minimum-volume floor from the spec above.
   Without the volume floor, a rolling window with 2 traces in it will produce
   false pages.
5. Set the threshold from the spec above (for example, monitor 1: alert when pass
   rate is below 100%; monitor 3: alert when p95 is above 10000 ms; monitor 4:
   alert when a session exceeds 15000 tokens). For monitors 7a and 8's session
   view, leave the threshold unset and revisit after calibration rather than
   entering a placeholder number.
6. Set the notification channel by severity: P0 to the paging channel, P1 and P2
   to the eng channel. Channels are configured once under Settings > Integrations,
   and **none exist yet**, so this step includes creating them.
7. Name the monitor to match this document (for example
   "E1 groundedness < 100% (P0)") and Save.

Repeat steps 2 through 7 for each of the eight monitors. All configuration lives in
the AX UI on the free tier; there is no code artifact to commit for the monitors
themselves, which is exactly why this document has to carry the specification.

## What to say about this, and what not to say

- Accurate: "Eight monitors are specified, five with thresholds fully grounded in
  measured runs, ready to apply in the AX UI."
- Accurate: "Three thresholds are deliberately left uncalibrated rather than filled
  with a plausible-looking number."
- Accurate: "Two of the eight are expected to fire on today's data on purpose:
  monitor 2 until the flight fix ships, monitor 5 until backlog D-07 closes the
  weather-fixture gap. Both are created muted with the reason recorded."
- **Not accurate:** "The tool-error rate is zero." It is 3.85% in control-v0 and
  5.68% across all 352 captured tool calls.
- **Not accurate:** "We have monitoring in place." "The groundedness monitor would
  catch that." "Here is the alert firing." None of that is true today.
