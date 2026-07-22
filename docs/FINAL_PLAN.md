# Final Plan: Arize FDE Interview 2 (presented Wed July 22, 2026)

Consolidates BUILD_PLAN.md plus adjustments after review of the official brief
(US_FDE_Interview_Screen.pdf), revised once more after a 4-lens adversarial audit.
Repo findings verified by computation: docs/verification/DAY0_FIXTURE_CHECKS.md.

## Deliverables (from the brief, these are graded)

1. Working demo: the agent with the automated feedback loop around it.
2. Customer-facing presentation: loop architecture (and agent improvements it drove),
   production readiness plan, mapping to Interview 1 requirements, before/after metrics.
3. Codebase link (prep task on Day 6: README run instructions, no keys or .env
   committed, visibility set, smoke-clone test).

Graded core requirements: Tracing (AX or Phoenix), Evaluation (justified by Interview 1),
Automation (repeatable process, any orchestrator), Skills Usage (which Arize/Phoenix
skills and CLI were used, how they helped, AND what we would automate further in a
real deployment; all three parts are in the brief).

## Success story (TBDs filled from real runs on Day 5, never earlier)

For a leisure traveler planning and booking a trip, the solution captures per-turn
traces with model and tool spans linked by session, detects fabricated inventory and
invalid tool calls using deterministic set-membership checks plus a human-calibrated
judge, automatically curates failures into a versioned dataset and proposes a bounded
fix, and improves groundedness from TBD-baseline to TBD-result without violating token
cost, latency, or the PII boundary. The cost/latency clause is backed by measurement:
the Day 1 baseline export includes per-run token counts and wall-clock latency, and the
Day 5 experiment table carries token-cost and latency columns alongside groundedness.

## Locked decisions (from CLAUDE.md; do not relitigate)

Platform Arize AX Free with OpenInference/OTel portability to Phoenix. Anchor workflow
planning to itinerary to booking. Primary metric groundedness, deterministic (closed
fixture set); metric bar 85 percent (the low end of Nick's stated range) with 90 as
the target, pending his answer to follow-up question 2. Two fixes only: prompt (D-01)
and search_flights direction (D-02), both presented as outputs of the loop. Promotion
requires the metric bar AND human sign-off; the sign-off is the deliberate deviation
from Nick's no-gate ask, disclosed in writing in the follow-up email and argued with
calibration data on the 22nd. Model stays claude-haiku-4-5.

## The eval-to-fix chain (must survive on stage)

The brief's central rule: agent changes are driven by the feedback loop, not a
separate engineering effort. The mechanical chain the demo shows:

| Baseline eval failure | Proposed fix | Change type (Nick-authorized) |
|---|---|---|
| E1 fabricated entity + E5 empty-result honesty failures cluster on empty tool results | D-01 prompt fix | Prompt change |
| E2 flight-direction failures attribute to the tool span, not the model | D-02 search_flights fix | Modify a tool call |
| E3 tool-call validity failures (bad dates, unknown cities, missing params) | Detection + backlog entry + proposed schema tightening; first automation target per Nick | Add/modify tool schema (backlog) |

E3 is the automation loop's first target because it is cheapest to close the loop on;
its Day 4 output is detection, clustering, and a proposed bounded change, which then
goes through the same experiment gate. Neither locked fix is presented as an E3 fix.

## Adjustments after brief review and audit

1. Skills Usage is graded three ways: docs/SKILLS_LOG.md records every Arize skill and
   CLI invocation, what it replaced manually, and a "what I would automate further in
   a real deployment" field; Day 6 distills that into one slide.
2. Orchestrator: single Python entrypoint scheduled by GitHub Actions cron (local cron
   fallback); AX Airflow provider and CI-triggered evaluation named as scale-up paths.
   ASSUMPTION by Chinmay's agent; override window closes end of Day 3 (Sun Jul 19) so
   Day 4 starts on a settled orchestrator.
3. Secrets and environment configuration in the Day 6 production section: service keys
   vs user keys, least-privilege scoping, .env handling.
4. Both fixes shown mechanically as loop outputs per the chain above.

## Evaluation portfolio

E1 fabricated entity (PRIMARY, deterministic set membership, trace level),
E2 flight direction (deterministic, attributes fault to the tool span),
E3 tool-call validity (deterministic, first automation target),
E4 itinerary day count, E5 empty-result honesty, E6 PII regex redact-at-source,
E7 telemetry guardrails (latency, tokens, cost, iterations; thresholds set off the
measured baseline), E8 clarification quality (judge, calibrated, two-sided),
E9 scope adherence (judge, calibrated).

Privacy contingency: if Luke disallows external judging even on redacted content
(follow-up question 4), E8/E9 degrade to deterministic proxies plus human annotation.
The primary metric (E1-E7) is unaffected; the promotion gate stands either way.

## Calendar

| Day | Date | Output |
|---|---|---|
| 0 | Thu Jul 16 eve / Fri am | Env ready (done), fixture verification (done), follow-up email sent by Chinmay, AX signup + retention check (needs Chinmay), smoke test (needs API key) |
| 1 | Fri Jul 17 | Instrumentation (additive only), then immutable baseline: all 22 conversations; export includes traces, per-run token counts, and wall-clock latency |
| 2 | Sat Jul 18 | Versioned golden dataset (22 queries + oversampled failures), E1-E7 implemented, baseline scored |
| 3 | Sun Jul 19 | E8/E9 judges + hand-labeled calibration + agreement number, online monitors. Designated scope-cut if slipping (customer-covered via the email's protected-tradeoff default). Orchestrator override window closes |
| 4 | Mon Jul 20 | Automation loop: collect, evaluate, cluster, append, propose bounded fix, experiment. E3 first |
| 5 | Tue Jul 21 | Experiments: baseline vs prompt fix vs tool fix, same dataset and evals. Table columns: groundedness, E-suite pass rates, token cost, latency. Fill all TBDs |
| 6 | Tue eve / Wed am | Production plan, deck, skills log slide, backlog slide (unfixed defects with severity and owner), codebase-link prep, rehearsal including the trace-replay fallback |

## Demo flow (12 beats + fallback)

Customer objective in their words; live Denver-hotel failure; trace shows empty tool
result and a confident reply; root cause is the three-line prompt; Tokyo to LA shows
the tool lying to the model (first mistake in the chain); eval suite catches both;
loop curates and proposes; experiment table; before/after; production design; backlog;
requirement-to-component map.

Fallback: hallucination beats depend on model behavior that is inference until Day 1
runs. If a live run does not reproduce in front of the panel, replay the captured
baseline trace from the disk export (hard rule 4 guarantees it exists). Rehearse the
replay path on Day 6.

## Production readiness talk-through (brief checklist, all nine items)

- Deployment architecture: sync serving separated from async eval, queue, sampling.
- Environment configuration: config via env, .env only for local dev.
- Secrets management: service keys not user keys, least privilege, rotation.
- Error handling: eval-pipeline failure behavior (retries, dead-letter, partial-run
  semantics, behavior when the grader API errors; no silently dropped evaluations).
- Logging and tracing: OpenInference spans, redaction at source, retention tiers.
- Monitoring and alerting: Day 3 online monitors (groundedness rate, loop rate, p95
  latency, tokens/session, tool-error rate) routed per the severity scheme (P0
  fabricated inventory, P1 coverage/scope, P2 telemetry).
- Resource usage: span budget tracked against the 25k/month free cap; token
  accounting per run.
- Scalability: to the brief's millions-per-day framing; sampling strategy for judges.
- Cost considerations and reliability/rollback: canary lanes by tag, rollback is the
  versioned prompt/tool config, same human gate as promotion, triggered by monitor
  breach on the primary metric. Repo-specific: D-10 unbounded loop, D-11 in-process
  state breaks multi-worker.

## Risks

| Risk | Mitigation |
|---|---|
| AX free-tier retention shorter than window | Export everything to disk at capture time (hard rule) |
| Judge calibration overruns weekend | Pre-designated cut, customer-covered by the email's protected-tradeoff default; E1-E7 carry the primary metric |
| Luke vetoes external judging on redacted content | E8/E9 degrade to deterministic proxies + human annotation; gate unaffected |
| Live demo does not reproduce a failure | Replay captured baseline trace from disk; rehearsed Day 6 |
| 25k span/month budget | ~150-200 spans per traffic run; usage tracked in resource line |
| API key/credits | Confirm Day 0; Haiku is cheap |
| Interview 1 quotes not re-verifiable (no transcript on disk) | Chinmay confirms or supplies transcript; PM name spelling checked before email send |

## Blockers needing Chinmay

1. ANTHROPIC_API_KEY (no .env, not in shell): needed for smoke test and baseline.
2. Arize AX Free signup (browser): space_id + API key + retention number.
3. Review and send the follow-up email (docs/FOLLOWUP_QUESTIONS.md), including the
   pre-send checklist (PM name spelling, gate-disclosure comfort, reply-by date).
4. Orchestrator override window closes end of Day 3 (Sun Jul 19).
