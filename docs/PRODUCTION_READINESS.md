# Production Readiness Plan

The demo runs locally by design: single process, `uvicorn`, JSONL on disk, the golden
dataset in the repo. That is the right shape for a one-week engagement and a live
walk-through, not a claim that the system is production-grade as shipped. This document
is the talk-through of a real rollout at millions of requests/day. Every choice below is
anchored in what was built this week: the dual-sink tracer (`agent/tracing.py`), the two
env-gated candidates (`docs/proposals/CANDIDATES.md`), the seven-stage loop
(`scripts/feedback_loop.py`), the nightly workflow (`.github/workflows/feedback-loop.yml`),
and the thresholds in `docs/MONITORS.md`. Sections 1 through 9 are the nine items on the
brief's readiness checklist (`docs/FINAL_PLAN.md:109`). Sections 10 and 11 go beyond that
checklist and cover the business-outcome join and the outcome-signal attributes, both of
which are **design specifications, not implemented code**.

Where this document and `docs/MONITORS.md` state a threshold, `MONITORS.md` is the source
of truth and this document cites it. Every measured figure below was recomputed for this
revision directly from the captured span files, and the computation is shown next to it.

## 1. Deployment architecture

Split the system into a synchronous serving path and an asynchronous eval/feedback
path, with a durable queue between them.

- **Sync serving path (latency-critical).** Load balancer -> stateless
  `POST /chat` workers (the FastAPI app in `agent/api.py`) -> Anthropic. Each turn
  emits OpenInference spans. The serving path does exactly one thing after replying:
  hand the finished spans to the queue and return. It never runs evals inline.
- **Queue (the seam).** The tracer already writes to two independent sinks
  (`agent/tracing.py`: Arize AX via the OTLP batch processor, plus a local JSONL
  file). In production the JSONL sink is replaced by an OTLP export to a collector
  that fans out to (a) AX for the hot control plane and (b) a durable queue / object
  store for the async path. The batch processor is the buffer; the serving worker is
  never blocked on eval compute.
- **Async eval/feedback path.** Consumers drain the queue and run the same seven
  stages `scripts/feedback_loop.py` runs today: COLLECT -> EVALUATE -> CLUSTER ->
  CURATE -> PROPOSE -> EXPERIMENT -> GATE. This is the nightly job in
  `feedback-loop.yml` promoted from a cron over baseline spans to a continuous
  consumer over live traces. The loop already never mutates the committed dataset
  (it curates a copy) and always ends at a human gate, so scaling it out changes
  throughput, not behavior.

### 1.1 Sampling and trigger strategy

**Status: PROPOSED.** Today the harness runs every eval over every captured trace in a
run; there is no sampler in the code. The tiering below is the production design, and the
split is not arbitrary, it falls straight out of a property of the evals themselves.

The **deterministic** evals (E1 `fabricated_entity`, E2 `flight_direction`,
E3 `tool_call_validity`, E4 `itinerary_day_count`, E5 `empty_result_honesty`, E6 `pii`,
E7 `guardrails`, E10 `conflicting_context`) decide by exact set membership against the
closed fixture set in `data/` (see the module docstring of `evals/e_conflict.py`:
"Why this is deterministic and closed-world"). They make **no model call**, so their
marginal cost per trace is CPU only and their verdicts are byte-reproducible. There is no
economic reason to sample them, so they run on everything.

The **judge** evals (E8 `clarification_quality` and E9 `scope_adherence` in
`evals/judges.py`, E11 `tone_quality` in `evals/e_tone.py`) each spend model tokens per
trace, so their cost scales linearly with traffic. They are also, per
`docs/JUDGE_CALIBRATION.md`, **monitor-only and not fit to gate a release today**. Paying
full-traffic rates for a signal that cannot gate anything is the wrong trade, so they are
sampled.

| Tier | Trigger | Which evals run | Rate |
|---|---|---|---|
| **Every interaction** | Every production trace | All 8 deterministic evals (E1-E7, E10) | 100%. Free and reproducible; no sampling justification exists. |
| **Sampled** | Random stratified draw from traffic that was not already flagged | The 3 judge evals (E8, E9, E11) | **Parameter to calibrate after initial traffic.** Set it from the observed traffic rate and the judge cost measured at that volume, not from a number picked today. Plus a forced 100% on any trace a deterministic eval already failed, since those are the traces worth a second opinion. |
| **Deployment-triggered** | A change to `PROMPT_VARIANT`, `FLIGHT_TOOL_FIX`, `PROMPT_VERSION`, `AGENT_VERSION`, or `ANTHROPIC_MODEL` (all env-gated, section 2) | Full offline suite over the golden dataset (`evals/golden_dataset.json`), control plus candidate, via `scripts/run_experiment.py` and `scripts/compare_experiments.py`; then elevated judge sampling on the canary lane | 100% of the golden dataset for the offline gate. Canary judge rate elevated above the steady-state sampled rate; **parameter to calibrate after initial traffic.** |
| **Threshold-triggered** | A `docs/MONITORS.md` monitor breaches: E1 < 100% (monitor 1, P0), E2 > 0 post-fix (monitor 2, P1), `agent.limit_breached` present (monitor 6, P1), tool-error rate > 2% (monitor 5), p95 > 10,000 ms (monitor 3), session > 15,000 tokens (monitor 4), cost/turn over the monitor 8 bands | Judges forced to 100% on the affected slice for the alert window, and the breaching traces are appended to the eval dataset by `evals/dataset.py append_failures` for replay | 100% of the affected slice while the alert is open. |
| **Scheduled** | The nightly cron in `.github/workflows/feedback-loop.yml` (`cron: "0 7 * * *"`, 07:00 UTC) | The full seven-stage loop over the previous window: COLLECT -> EVALUATE -> CLUSTER -> CURATE -> PROPOSE -> EXPERIMENT -> GATE | Deterministic evals over the whole window. The paid experiment path runs only when a key is configured, so scheduled spend is opt-in. |

Two honest notes on this table. First, every rate written as "parameter to calibrate" is
deliberately not a number: the repo has no production traffic, so any percentage here
would be invented. Second, the tiers are a specification; the only one that exists as
running code today is the scheduled tier, which is the committed nightly workflow.

## 2. Environment configuration

Everything that changes behavior is an environment variable, off by default, so a
config change is a deploy-time decision and never a code edit.

- Candidate behavior is env-gated: `PROMPT_VARIANT` (unset/`v0` = shipped,
  byte-identical; `v1` = the aligned prompt) and `FLIGHT_TOOL_FIX` (unset/`0` =
  shipped; `1` = ordered match with visible route). Verified byte-identical at
  defaults in `CANDIDATES.md` self-tests.
- Version stamping is env-driven in `agent/tracing.py`: `PROMPT_VERSION`
  (default `v0-shipped`), `AGENT_VERSION` (default `baseline-0080b11`),
  `ARIZE_PROJECT_NAME` (default `travel-agent`). Every span carries the version that
  produced it, which is what makes canary comparison and rollback auditable.
- Tracing is fully controllable by env: `TRACE_EXPORT_PATH`, `TRACING_DISABLED`, and
  the AX credentials. Config is validated at startup; a bad tracing config degrades to
  untraced rather than crashing the agent (see section 4).
- Per-environment config (dev / staging / canary / prod) is the same image with a
  different env set. No branching, no per-env code.

## 3. Secrets management

- **No secrets in code.** AX credentials (`ARIZE_SPACE_ID`, `ARIZE_API_KEY`) and
  `ANTHROPIC_API_KEY` are read from the environment only. The CI workflow sources
  `ANTHROPIC_API_KEY` from `secrets.ANTHROPIC_API_KEY` and runs the no-experiment path
  when it is absent, so the loop never hard-requires a key to be present in logs.
- **Service keys, not user keys.** Per `docs/FINAL_PLAN.md`, the ingest and experiment
  paths use service keys scoped least-privilege (export/ingest only), not a developer's
  personal user key. Rotation is scheduled; a leaked key is revoked without touching
  application code because nothing is hardcoded.
- **Secret store, not `.env` in prod.** The local `.env` pattern is a dev convenience;
  production injects secrets from a managed secret store at deploy time.

## 4. Error handling

The instrumentation is additive-only and fails safe: the agent behaves identically with
tracing on, off, or misconfigured (`agent/tracing.py` module docstring).

- Setup is idempotent and a failed setup is terminal with no partial global state:
  fallible local steps run before anything global is installed, and any failure prints
  an honest log line (`agent runs untraced`) and returns `None`. `get_tracer()` then
  hands back a `NoOpTracer`. Losing telemetry never takes down serving.
- Tool misses are honest outcomes, not exceptions: empty results (e.g. Denver->Miami
  returned `[]`) are distinct from tool errors, and the eval and monitor layers key on
  that distinction (`MONITORS.md` monitor 5 keys on `tool.error` only, set at
  `agent/loop.py:76`, never on the wider `tool.result_empty` at `agent/loop.py:74`).
  Measured tool-error rate: **0 of 16 tool calls in the frozen baseline**, but **1 of 26
  (3.85%) in control-v0 and 20 of 352 (5.68%) across all 13 captured runs**, all of them
  `get_weather` misses on cities absent from the fixture set (backlog D-07). "Zero tool
  errors" is true of the baseline run only and false of the corpus.
- The known handling gaps are tracked, not hidden: N-01 (tracing imports are
  unconditional; a broken install kills the agent, accepted with pinned deps) and N-02
  (`run_agent([])` raises `IndexError`, unreachable from both entrypoints) are in
  `BACKLOG.md` with production mitigations (guard imports in unmanaged envs; guard the
  empty-message path if `run_agent` ever becomes public).

## 5. Logging and tracing

- **OpenInference / OTel semconv on every span**, which is what keeps the design
  portable (see section 9). The dual-sink tracer gives a hot path (AX) and a cold path
  (durable JSONL/object store) so no trace depends on a single platform's retention.
- **Redaction at source, before export (partial implementation of Luke's boundary).**
  Formatted US SSNs and Luhn-valid cards are redacted inside the app process before model
  execution, tracing, experiment replay, or new eval artifacts. E6 scored 23/23 on the
  baseline. Names, email, phone, addresses, passports, non-US identifiers, and obfuscated
  values remain an explicit production gap; see `docs/PII_BOUNDARY.md`.
- **Retention tiers.** Hot: recent traces in AX for monitors, dashboards, and eval
  labels. Cold: the append-only JSONL archive (owner-only `0600`, since spans carry full
  conversation content) promoted to object storage with lifecycle rules. This is exactly
  the dual-sink already shipped; production only swaps the local file for durable
  storage.
- **Versioned and session-scoped.** `PROMPT_VERSION` / `AGENT_VERSION` on every span,
  and `using_session(conversation_id)` groups turns into sessions for per-session
  metrics like tokens.

## 6. Resource usage

Measured from the frozen baseline (`docs/DAY1_FINDINGS.md`,
`docs/evals/baseline-2026-07-19/summary.md`, recomputed for this revision from
`docs/baseline/2026-07-19/spans.jsonl`): 23 turns, 78 spans, 22 sessions,
50,655 total tokens, median latency 2.9s, p95 4.7s, max 5.5s, `~$0.073` for the run.

Tokens, split by the two groupings, because conflating them is what produced a wrong
threshold in an earlier draft:

| Grouping | Baseline (23 turns / 22 sessions) | All 13 captured span files (419 turns / 394 sessions) |
|---|---|---|
| Per **turn** | mean 2,202.4, max 3,576 | mean 2,508.6, max 7,748 |
| Per **session** (`session.id`) | mean 2,302.5, median 2,523.5, max **6,221**, min 1,099 | mean 2,667.8, median 2,642, max **7,748** |

- Span volume per turn from the baseline: 78 spans / 23 turns = ~3.4 spans/turn. Token
  and latency budgets above set the per-turn compute envelope and feed the monitor
  thresholds: **tokens/session alerts at >15,000** (`MONITORS.md` monitor 4), and p95
  alerts at >10s (monitor 3, about 2x the observed max).
  - The tokens/session figure is 15,000, **not the 5,000 an earlier draft of this
    document carried**. 5,000 was derived from the per-*turn* mean and is invalid as a
    per-*session* ceiling: a real captured baseline session
    (`9de7fde2-49f5-4df6-91d0-d40ad004dbcd`, 2 turns, **6,221 tokens**) already exceeds
    it, so the monitor would have fired on the frozen baseline itself. 15,000 is
    15,000 / 7,748 = **1.94x** the largest session ever captured and
    15,000 / 6,221 = **2.41x** the largest baseline session.
  - Carry the caveat with the number: no captured session runs longer than **2 turns**
    (baseline session-length distribution is 21 single-turn plus 1 two-turn). Because the
    whole conversation is resent each turn, a genuine multi-turn production session will
    plausibly clear 15,000 on its own. **TBD - recalibrate against the real
    session-length distribution after the first week of production traffic.**
- The JSONL archive writer is append-only and owner-only; in production it is an OTLP
  export to a collector, so serving workers hold no growing on-disk state.
- Loop compute is bounded by the proposed sampling tiers (section 1.1) and by the
  deterministic-first rule: the expensive judge path runs on a fraction of traffic, not
  all of it. Note the tiers are a design; no sampler exists in the code today.

## 7. Scalability

Scale math kept honest from the measured baseline (~3.4 spans/turn):

- At 1,000,000 requests/day, one span per request already implies ~1e6 spans/day; at the
  baseline ~3.4 spans/turn it is closer to ~3.4e6 spans/day. AX Free is 25,000 spans/mo
  (locked in `CLAUDE.md`). Production span volume exceeds the free tier by three-plus
  orders of magnitude in a single day. That gap is *why* the architecture is what it is:
  100% deterministic eval on cheap self-computed labels, judge evals on a sample, and
  head-based trace sampling into the hot platform while the cold archive keeps the full
  record. You do not send millions/day of full-fidelity judged traces to a hosted
  control plane; you send a representative sample plus all flagged traces.
- Three repo-specific scaling risks from `BACKLOG.md`. The unbounded-loop half of D-10 is
  **bounded in code as of today**; its token-ceiling half is not, and the other two risks
  remain open. Each is stated below with what landed and what is still open:
  - **D-10 (unbounded loop) - IMPLEMENTED, with one part still outstanding.**
    - *Landed.* `agent/loop.py` is no longer an unbounded `while True`. It enforces a
      hard iteration cap and a wall-clock deadline: `MAX_AGENT_ITERATIONS = 8` and
      `AGENT_DEADLINE_SECONDS = 60` (`agent/config.py:15-16`, both env-overridable),
      checked by `_limit_breached()` (`agent/loop.py:29-37`) **before each model call**,
      so a request already in flight is never cut off mid-call. On a breach the run sets
      the `agent.limit_breached` span attribute (`agent/loop.py:155`), sets span status
      ERROR (`agent/loop.py:156`), and returns `LIMIT_FALLBACK_REPLY`
      (`agent/loop.py:23-26`), which deliberately contains **no itinerary content**: a
      truncated run has no verified inventory behind it, and groundedness is the primary
      metric. `agent.iterations` (`agent/loop.py:163`) is set on every turn, breach or
      not.
    - *Basis for the cap, recomputed for this revision.* Across all 13 captured span
      files, 419 `agent_turn` spans: iterations min 1, **max 3**, mean 1.75, distribution
      {1: 106, 2: 311, 3: 2}. The cap of 8 is 2.67x the busiest turn ever recorded. Within
      the **frozen baseline run alone**, the maximum is 2 (mean 1.70, 23 turns), which is
      the figure earlier drafts quoted; it is correct for the baseline and **wrong as a
      ceiling for the captured population**. `MONITORS.md` monitor 6 uses the 419-span
      figure, and so does `agent/config.py:11-14`.
    - *Still outstanding, and it is a real gap.* There is **no cumulative per-turn or
      per-session token ceiling.** `MAX_TOKENS = 4096` (`agent/config.py:9`) caps a single
      model response, not the sum across iterations. So the iteration cap bounds the
      number of calls and the deadline bounds wall clock, but nothing bounds tokens
      directly. Until that lands, the tokens/session monitor (>15,000, `MONITORS.md`
      monitor 4) is the detective control, not a preventive one.
    - *Also outstanding: the control has never been observed firing.* `agent.limit_breached`
      did not exist when the 419 spans were captured, so "zero breaches" is **recomputed
      from `agent.iterations`**, not an observation of the attribute. Confirm the attribute
      is arriving in AX before trusting monitor 6, or it will read green while blind.
  - **D-11 (in-process state) - PARTIALLY ADDRESSED, still open for multi-worker.**
    Session state is now behind a two-method `get`/`put` interface
    (`agent/session_store.py`), and `agent/api.py:58` builds it via `build_store()`.
    `SESSION_STORE=sqlite` persists conversations across restarts. **The default is still
    an in-process `DictStore`**, and the Anthropic client is still constructed at import
    (`agent/loop.py:16`). SQLite gives durability on one box; it does not give a shared
    session across workers. Mitigation unchanged: point the same interface at a real
    shared database keyed by `conversation_id`, so any worker can serve any turn and the
    `using_session` grouping (`agent/api.py:85`) stays coherent across the fleet.
  - **D-12 (no auth / rate limit).** `POST /chat` is unauthenticated with no rate limit,
    and the security review confirmed the amplification: unauthenticated input drives
    **unbounded durable trace writes**, and an attacker-chosen `conversation_id` lands
    directly on spans. Mitigation: auth + per-caller rate limit + size caps on `message`
    and `conversation_id`, so the durable write path cannot be driven by anonymous
    traffic.

## 8. Cost considerations

- The free-tier ceiling (25k spans/mo) versus millions/day (section 7) is the primary
  cost forcing-function. It is what makes sampling non-optional rather than a nicety.
- Deterministic evals are free and reproducible (exact set membership on a closed
  fixture set), so the highest-value signal (E1 groundedness, E2 flight-direction)
  costs nothing per trace. Only judge evals spend model tokens, and they run on a
  sample.
- Serving cost is bounded per turn by the two D-10 caps that landed (iteration cap 8 and
  60s deadline, `agent/config.py:15-16`). The **token ceiling is not implemented**, so
  cost is bounded indirectly by call count, not directly by tokens. The baseline
  `~$0.073`/23-turn run and the measured mean of 2,302.5 tokens/session give the unit
  economics to project spend; monitors 4 (tokens/session > 15,000) and 8 (cost per turn,
  mean > $0.0067 or any single turn > $0.0120, from the 33-turn control-v0 run) are the
  regression detectors. Both monitors are **specified, not configured**
  (`MONITORS.md` status block: 0 of 8 live).
- The nightly loop runs the no-experiment path with no model calls by default
  (`feedback-loop.yml`); the paid experiment path runs only when a key is configured, so
  improvement compute is opt-in, not always-on.

## 9. Reliability and rollback strategy

- **Rollback is a flag flip plus a versioned config, not a redeploy.** Because both
  fixes are env-gated (`PROMPT_VARIANT`, `FLIGHT_TOOL_FIX`) and default to
  byte-identical shipped behavior, reverting a bad change is setting the flag back to
  its default. The versioned prompt/tool config is what the flag selects, and every span
  is stamped with `PROMPT_VERSION` / `AGENT_VERSION`, so before/after is auditable in the
  trace record.
- **Canary lanes by tag.** Route a slice of traffic to the candidate version, compare
  against the control on the same evals (the loop already runs control + each candidate
  and compares; `scripts/run_experiment.py` / `compare_experiments.py`). Version tags on
  spans keep the two lanes separable in the monitors.
- **Human gate on promotion AND rollback.** The loop always emits
  `PROMOTION: BLOCKED pending human approval` (stage 7 GATE) and never flips agent
  defaults on its own. The transcript asks to automate failure curation, but does not
  authorize autonomous production promotion: automate collect -> evaluate -> cluster ->
  propose -> experiment, gate the promotion. `scripts/approval.py` holds the approval
  logic and the gate stage always writes `approval.json` with decision
  `pending_human_review` and reviewer `null` (`scripts/approval.py:26-27`;
  `write_approval` at `scripts/approval.py:154` raises on any other decision and at
  `:162-163` refuses to write a reviewer or a decision_time at all). There is deliberately
  no code path by which the loop can self-approve. Rollback is likewise a human decision informed by the
  monitors. In the **specified** routing (`MONITORS.md` severity routing, which is
  proposed, with 0 of 8 monitors configured and 0 alerts ever fired): a P0
  fabricated-inventory alert (E1 < 100%) pages on-call; a P1 flight-direction regression
  (E2 > 0 post-fix) triages same-day.
- **Residency fallback: Phoenix self-hosted.** If a customer requires the control plane
  in their own environment, the spans are already OpenInference/OTel semconv, so only the
  control plane changes: point the same exporters at self-hosted Phoenix instead of AX.
  The agent, redaction boundary, deterministic evals, and dual-sink archive are unchanged.
  Portability was locked in `CLAUDE.md`; it is a property of the instrumentation.

## 10. Connecting evaluations to the business outcome (booking conversion)

### STATUS: DESIGN ONLY. NOTHING IN THIS SECTION IS IMPLEMENTED.

Say this first, in the room, before the design: **this prototype has no transactional
booking path, and booking conversion has not been measured.** There is no checkout, no
payment, no reservation write, and no revenue event anywhere in the repo. `search_flights`,
`search_hotels`, `get_weather`, and `create_itinerary` (`agent/tools.py`) are all read-only
lookups: `agent/tools.py:7-12` loads `flights.json`, `hotels.json`, and `weather.json` from
`data/` at import and every tool reads from those dicts. Nothing writes. The v1 candidate
prompt calls the agent a "travel planning and booking assistant"
(`agent/prompt.py:17`, built only when `PROMPT_VARIANT=v1`) and the shipped v0 prompt opens
with "Help Book Travel." (`agent/prompt.py:1`), but no tool books anything under either.

Therefore **every number this engagement produced is a leading indicator, not an outcome
measure.** E1 groundedness, E2 flight direction, latency, and cost are quality signals that
we have reason to believe move conversion; none of them *is* conversion. The correct claim
is "the flight-direction candidate measured 8/8 on E2, d+89pp against control"
(`docs/experiments/COMPARISON.md`), with the further qualifier that the fix is env-gated
behind `FLIGHT_TOOL_FIX=1` and is not on by default. The incorrect claim, which must not
be made in the room or in the deck, is "conversion improved." No conversion figure exists
to improve, because no booking event has ever been emitted.

Nick's stated business goal is increasing booking conversion. What follows is the join that
would let this eval system answer that question, once a real booking service exists.

### 10.1 The join key already exists in the traces

The foreign key is the conversation/session id, and it is already stamped on every span:

- `agent/api.py:78` mints or accepts it: `conversation_id = req.conversation_id or str(uuid.uuid4())`.
- `agent/api.py:85` binds it to the trace context: `with using_session(conversation_id), _pii_metadata(pii_types):`.
  OpenInference's `using_session` writes it as the **`session.id`** span attribute, which is
  visible on the captured spans (for example
  `session.id = "96b55aa9-2ff7-49c6-ac51-47dc6dfefb4c"` on the first span of
  `docs/baseline/2026-07-19/spans.jsonl`).
- `agent/api.py:89` returns it to the caller in `ChatResponse`, so the client already holds
  the key and can attach it to downstream events without any new plumbing in the agent.
- The CLI entrypoint does the same thing with a locally generated id
  (`agent/chat.py:38` and `agent/chat.py:55`).

That is the whole mechanism. `session.id` on the agent side joins to `session_id` on the
booking side. No new identifier needs to be invented, and nothing in the serving path
changes.

### 10.2 Events the booking service must emit

These are the events the **product** emits, not the agent. Each carries `session_id`
(the same value as the span `session.id`) plus a timestamp.

| Event | Payload | Meaning |
|---|---|---|
| `booking_started` | `session_id`, `booking_type` (flight / hotel / package) | User entered checkout after an agent conversation. Denominator half of conversion. |
| `booking_completed` | `session_id`, `booking_id`, `booking_type` | Reservation confirmed. Numerator of conversion. |
| `booking_value` | `session_id`, `booking_id`, `amount`, `currency` | Revenue attached to a completed booking. Lets quality be weighed by value, not just count. |
| `cancellation` | `session_id`, `booking_id`, `reason_code`, `hours_since_booking` | The counter-metric. A conversion win that raises cancellations is not a win, and a fabricated hotel is exactly the defect that would show up here. |
| `human_handoff_requested` | `session_id`, `handoff_reason` | User escalated to a human. A cost signal and a quality signal at once. Note the trigger exists only in the **v1 candidate** prompt (`agent/prompt.py:27`, gated on `PROMPT_VARIANT=v1`), which instructs handoff on visa, refund, and policy questions. The shipped v0 prompt (`agent/prompt.py:1-7`) has no scope or handoff rule at all, which is itself part of the headline finding. Nothing emits this event under either prompt. |

Conversion rate is then `count(booking_completed) / count(sessions)` over a window, with
`booking_started` giving the intermediate funnel step, and cancellation rate computed over
completed bookings on the same key.

### 10.3 Segmenting conversion by the versions we already stamp

This is the reason the join is worth building: it turns the eval loop into an
outcome-attributable experiment rather than a quality-only one. Every `agent_turn` root span
already carries the three dimensions needed to segment:

- `prompt_version` (`agent/loop.py:92`, from `PROMPT_VERSION`, default `v0-shipped`).
- `agent_version` (`agent/loop.py:93`, from `AGENT_VERSION`, default `baseline-0080b11`).
- Model id, from `ANTHROPIC_MODEL` (`agent/config.py:8`, default `claude-haiku-4-5`) and
  recorded on the LLM spans.

Join booking events to sessions on `session.id`, roll each session up to the
`(prompt_version, agent_version, model)` triple its spans carry, and conversion becomes a
per-variant metric on exactly the same axis the canary lanes and the experiment harness
already use (section 9). The candidate comparison in `COMPARISON.md` today reports E1/E2
pass rates per variant; with this join it reports conversion, revenue per session, and
cancellation rate per variant alongside them. That is the point at which "the loop improved
quality" becomes "the loop improved the business outcome", and not before.

Two properties to preserve when this is built:

- **Sessions with no booking event are not missing data.** They are the zero class. A
  left join from sessions to bookings, never an inner join, or conversion silently becomes
  100%.
- **The redaction boundary applies to booking events too.** `booking_id` and `amount` are
  fine; traveller names, payment details, and contact information are not, and must not
  ride into the eval store on these events. See section 5 and `docs/PII_BOUNDARY.md`.

### 10.4 Ownership

| Responsibility | Owner | Why |
|---|---|---|
| Emit the five events from the booking service | Luke, VP Engineering | He owns the repo and the serving path; the events originate in product code, not in the agent. |
| Define the event schema and the conversion definition | Nick, Director of Product | He owns the business outcome and therefore owns what counts as a conversion. |
| Own the join and the per-variant dashboard | Nick (metric), Luke (pipeline) | The join is a data-pipeline artifact; the metric definition it computes is a product decision. |
| Review the quality-to-conversion correlation weekly | Anne, Product Manager | Her team does the spot-checking today; this is the automated version of that review. |

None of these owners has been asked to do this yet. This section is a proposal to take to
them, not a record of an agreement.

## 11. User satisfaction and task-completion signals

### STATUS: DESIGN ONLY. NONE OF THESE ATTRIBUTES EXIST TODAY.

To be precise about what the code sets now: `agent/tracing.py` sets **no span attributes at
all**. It is setup only, and it exports three module constants (`PROJECT_NAME`,
`PROMPT_VERSION`, `AGENT_VERSION`, `agent/tracing.py:20-22`) plus a JSONL exporter and the
`setup_tracing()` / `get_tracer()` pair. The attributes that actually land on spans are set
in `agent/loop.py` (`prompt_version`, `agent_version`, `agent.iterations`,
`agent.limit_breached`, `tool.result_count`, `tool.result_empty`, `tool.error`, plus the
OpenInference input/output/span-kind fields), and in `agent/api.py` / `agent/chat.py`
(`session.id` via `using_session`, and the PII flags via `using_metadata`).

Not one of the outcome-signal attributes below is among them. They require **real product
events from a real product**, which this prototype does not have.

| Attribute | Source of truth | Status today |
|---|---|---|
| `user.feedback_score` | Explicit user rating in the product UI (thumbs or 1-5), posted with the `conversation_id` returned by `agent/api.py:89` | **Not implemented.** No UI, no rating widget, no endpoint. Zero occurrences across `agent/`, `evals/`, `scripts/`, and `tests/`. |
| `user.feedback_text_redacted` | Free-text comment from the same widget, passed through `agent/redaction.py redact()` before it is ever stored or exported | **Not implemented.** The redactor exists and works (it strips SSNs and Luhn-valid card numbers, `agent/redaction.py:50-74`), but nothing calls it on feedback text because there is no feedback text. |
| `task.completed` | Product-side determination that the user got what they came for. Definition must be explicit: for this agent, the honest proxy is a completed booking, not "the agent replied" | **Not implemented.** Note the trap: the agent returning a fluent reply is *not* task completion, and treating it as such is how a groundedness failure gets scored as a success. |
| `booking.started` | `booking_started` event from the booking service (section 10.2), joined on `session.id` | **Not implemented.** No transactional booking path exists. |
| `booking.completed` | `booking_completed` event, joined on `session.id` | **Not implemented.** Same reason. This is the attribute conversion is computed from, and its absence is why no conversion number appears anywhere in this repo. |
| `conversation.abandoned` | Derived, not emitted: session with no terminal event and no further turn after an inactivity window. Requires a session-close signal the product does not currently produce | **Not implemented.** Also not currently derivable: 21 of 22 baseline sessions are a single turn, and the harness drives them synthetically, so "abandoned" has no meaning in the captured data. |
| `human_handoff.requested` | `human_handoff_requested` event, or a deterministic detector over the reply text keyed to the handoff rule in the v1 candidate prompt (`agent/prompt.py:27`) | **Not implemented** as a span attribute. Closest existing thing is the E9 `scope_adherence` judge (`evals/judges.py:324-325`), which is **monitor-only** per `docs/JUDGE_CALIBRATION.md` and is an eval label, not a product event. |
| `user_correction_count` | Count per session of user turns that supersede an earlier booking-material value | **Not implemented** as an attribute, but partially computable today. E10 `conflicting_context` (`evals/e_conflict.py`) already reconstructs the ordered user turns of a session and detects superseded origin / destination / date values deterministically. That detector is the natural source for this attribute; it just has never been written back onto a span. |

### 11.1 How these attach to the same trace, without hoarding PII

All eight attach on the **same `session.id` join described in section 10.1**, and none of
them requires the agent to store anything new about the user:

- **Post-hoc annotation, not inline capture.** Feedback and booking events arrive after the
  turn's span has closed. They are attached as evaluations/annotations on the root span in
  AX (the same mechanism the E1/E2/E6 labels use, per the "Exact AX UI steps" section of
  `MONITORS.md`), keyed by `session.id`. The serving path stays untouched, which is the
  same discipline as section 1: the sync path never does eval work.
- **Redact before the boundary, not after.** `user.feedback_text_redacted` is named for
  what it is: only the redacted form exists. The raw string is redacted in the app process
  by `redact()` and the original is never written, exactly as `agent/api.py:80-83` already
  does for the inbound user message ("Redact AT SOURCE: only the cleaned text is ever
  appended, persisted, sent to the model, or written to a span. The raw `req.message` is
  never stored."). In production this is additionally enforced by a redaction span
  processor upstream of every exporter (section 5).
- **Store the signal, not the person.** Every attribute above is either a scalar
  (`user.feedback_score`, `user_correction_count`), a boolean (`task.completed`,
  `booking.started`, `booking.completed`, `conversation.abandoned`,
  `human_handoff.requested`), or already-redacted text. **No name, email, phone number,
  payment detail, or loyalty identifier is needed to compute any metric in section 10.**
  `session.id` is an opaque UUID minted per conversation (`agent/api.py:78`); it is a join
  key, not an identity, and it deliberately carries no user identifier. That is what lets
  the eval system answer business questions without becoming a second copy of the customer
  database, which is precisely Luke's stated boundary.
- **Retention follows the trace, not the booking.** These annotations live on the hot
  trace record and expire with it (section 5). The durable record of a booking belongs in
  the booking system, not in the eval archive.
