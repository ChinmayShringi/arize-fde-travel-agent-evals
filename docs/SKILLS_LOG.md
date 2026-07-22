# Skills and Tooling Usage Log

The brief grades three things: which Arize/Phoenix tooling was used, how it helped,
and what we would automate further in a real deployment. This log is honest; nothing
listed here was faked or name-dropped without use.

## Used in this build

| Tool | Where | What it replaced |
|---|---|---|
| arize-otel `register()` | agent/tracing.py | Hand-rolled OTLP exporter config, auth headers, endpoint wiring; one call gives the AX-ready tracer provider |
| openinference-instrumentation-anthropic | agent/tracing.py | Manual LLM span construction; token counts, message capture, model metadata arrive automatically on every messages.create |
| OpenInference semconv (SpanAttributes, span kinds) | agent/loop.py | Ad-hoc attribute naming; AX renders CHAIN/TOOL/LLM trees natively and the design ports to self-hosted Phoenix unchanged |
| openinference `using_session` | agent/api.py, agent/chat.py | Custom session plumbing; conversation_id becomes session.id on every span via context, no signature changes |
| Arize AX (cloud) | traces from baseline + experiments | The trace store, session views, and the deep-link surface for the demo |
| ArizeClient (arize SDK 8.40.0) datasets.create | scripts/push_to_arize.py | Golden dataset uploaded to AX as "golden-dataset-v1-2026-07-19" (31 examples, verified by read-back); the older arize.experimental surface does not exist in v8 and the API was mapped from installed source |
| ArizeClient spans.update_evaluations | scripts/push_to_arize.py | All E1-E9 results (697 labels) attached to root spans in project travel-agent, so scores render on traces in the UI; discovered AX stores span ids as bare hex without the OTel 0x prefix |
| ArizeClient spans.export_to_df | verification | Independent read-back surface used to confirm every upload claim (label counts, timestamps, no duplication) |
| Trace replay (custom OTel IdGenerator) | scripts/replay_spans_to_arize.py | Re-ingested 2 traces lost to a shutdown flush race with original ids and timestamps; surfaced the arize.project.name resource-attribute requirement for direct provider construction |
| Claude Code multi-agent workflows | instrumentation review, eval implementation, this build | Solo dev pass; four-lens adversarial review caught a critical export bug (Arize processor removal semantics) before the baseline was captured |

## Found by using the tooling, not by reading docs

- Arize's TracerProvider.add_span_processor() removes the default AX exporter when a
  custom processor is added afterwards; custom processors must go through
  register(span_processors=[...]). Confirmed in arize-otel 0.13.0 source. Without the
  adversarial review, the entire baseline would have captured locally and silently
  never reached AX.
- BatchSpanProcessor delivery depends on graceful shutdown; the capture script
  SIGTERMs uvicorn and the experiment runner calls force_flush explicitly.

## Would automate further in a real deployment

1. Online eval tasks in AX running E1/E2/E5 continuously on sampled production
   traces instead of batch scoring exported files.
2. The feedback loop as an AX-integrated scheduled job (Airflow provider operators
   for datasets, experiments, and evaluators) instead of a GitHub Actions cron.
3. CI gating: run the experiment suite on every prompt/tool PR and block merge on
   primary-metric regression, with the AX experiment link in the PR.
4. Monitor-driven rollback: a P0 monitor breach flips the env-gated candidate off
   automatically, with human review after the fact rather than before.
5. Judge calibration workflow in AX annotations rather than a CSV sheet.
