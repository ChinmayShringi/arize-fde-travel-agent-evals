# Production Readiness Plan

The demo runs locally by design: single process, `uvicorn`, JSONL on disk, the golden
dataset in the repo. That is the right shape for a one-week engagement and a live
walk-through, not a claim that the system is production-grade as shipped. This document
is the talk-through of a real rollout at millions of requests/day. Every choice below is
anchored in what was built this week: the dual-sink tracer (`agent/tracing.py`), the two
env-gated candidates (`docs/proposals/CANDIDATES.md`), the seven-stage loop
(`scripts/feedback_loop.py`), the nightly workflow (`.github/workflows/feedback-loop.yml`),
and the thresholds in `docs/MONITORS.md`. The nine readiness items are the sections below.

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

Sampling strategy: **deterministic evals run on 100% of traffic; judge evals run on a
sample.** The primary groundedness metric is exact set membership against a closed
fixture set (E1 fabricated_entity, E2 flight_direction, E3 tool_call_validity), so it
is free, reproducible, and applied to every trace. LLM-judge evals (scope adherence,
subjective quality) are metered and cost money per call, so they run on a stratified
sample plus a forced 100% on any trace a deterministic eval already flagged.

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
  that distinction (`MONITORS.md` monitor 5 is tool exceptions / error payloads only,
  baseline 0%).
- The known handling gaps are tracked, not hidden: N-01 (tracing imports are
  unconditional; a broken install kills the agent, accepted with pinned deps) and N-02
  (`run_agent([])` raises `IndexError`, unreachable from both entrypoints) are in
  `BACKLOG.md` with production mitigations (guard imports in unmanaged envs; guard the
  empty-message path if `run_agent` ever becomes public).

## 5. Logging and tracing

- **OpenInference / OTel semconv on every span**, which is what keeps the design
  portable (see section 9). The dual-sink tracer gives a hot path (AX) and a cold path
  (durable JSONL/object store) so no trace depends on a single platform's retention.
- **Redaction at source, before export (Luke's PII boundary).** PII is redacted inside
  the app process before any span leaves it, so it never reaches the LLM provider or the
  eval system. E6 pii scored 23/23 on the baseline. In production this is a redaction
  span processor that runs before both the OTLP and archive exporters, so redaction is
  structurally upstream of every sink, not a per-sink afterthought.
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
`docs/evals/baseline-2026-07-19/summary.md`): 23 turns, 78 spans, 22 sessions,
50,655 total tokens (mean ~2,202/turn, max 3,576/turn, ~2,300/session), median latency
2.9s, p95 4.7s, max 5.5s, `~$0.073` for the run.

- Span volume per turn from the baseline: 78 spans / 23 turns = ~3.4 spans/turn. Token
  and latency budgets above set the per-turn compute envelope and feed the monitor
  thresholds (tokens/session alert at >5,000, roughly 2x baseline mean; p95 alert at
  >10s, roughly 2x observed max).
- The JSONL archive writer is append-only and owner-only; in production it is an OTLP
  export to a collector, so serving workers hold no growing on-disk state.
- Loop compute is bounded by sampling (section 1) and by the deterministic-first rule:
  the expensive judge path runs on a fraction of traffic, not all of it.

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
- Three repo-specific scaling risks from `BACKLOG.md`, each with its production
  mitigation:
  - **D-10 (unbounded loop).** `agent/loop.py` is `while True` with no iteration cap and
    no timeout. Baseline never breached (max 2 iterations, monitored by E7), so it is a
    latent blast-radius risk, not an observed one. Mitigation: hard iteration cap + wall
    clock timeout + per-turn token ceiling before production; the tokens/session monitor
    (>5,000) is the early warning.
  - **D-11 (in-process state).** `CONVERSATIONS` is a module-level dict and the Anthropic
    client is constructed at import (`agent/api.py`). With more than one worker this
    splits a session's telemetry across processes and grows unbounded. Mitigation:
    externalize conversation state (shared store keyed by `conversation_id`) so any
    worker can serve any turn and session spans stay coherent; the `using_session`
    grouping then holds across the fleet.
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
- Serving cost is bounded per turn by the D-10 caps (iteration + timeout + token
  ceiling); the baseline `~$0.073`/23-turn run and ~2,300 tokens/session give the unit
  economics to project spend, and the tokens/session monitor catches regressions early.
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
  defaults on its own. This is the deliberate, stated deviation from Nick's
  "no human gate" request in `CLAUDE.md`: automate collect -> evaluate -> cluster ->
  propose -> experiment, gate the promotion. Rollback is likewise a human decision
  informed by the monitors: a P0 fabricated-inventory alert (E1 < 100%) pages on-call;
  a P1 flight-direction regression (E2 > 0 post-fix) triages same-day
  (`MONITORS.md` severity routing).
- **Residency fallback: Phoenix self-hosted.** If a customer requires the control plane
  in their own environment, the spans are already OpenInference/OTel semconv, so only the
  control plane changes: point the same exporters at self-hosted Phoenix instead of AX.
  The agent, redaction boundary, deterministic evals, and dual-sink archive are unchanged.
  Portability was locked in `CLAUDE.md`; it is a property of the instrumentation.
