"""OpenInference/OTel tracing setup. Additive only: the agent behaves identically
with tracing on, off, or misconfigured.

Spans go to two sinks:
- Arize AX via the OTLP batch processor (when ARIZE_SPACE_ID / ARIZE_API_KEY are set)
- a local JSONL file (TRACE_EXPORT_PATH, default <repo>/traces/spans.jsonl), so every
  captured span survives independently of platform retention

The JSONL processor is passed through register(span_processors=[...]) because Arize's
TracerProvider.add_span_processor() removes the default Arize exporter when a custom
processor is added afterwards (arize-otel 0.13.0, otel.py add_span_processor override).
"""

import json
import os
from pathlib import Path

from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

PROJECT_NAME = os.getenv("ARIZE_PROJECT_NAME", "travel-agent")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v0-shipped")
AGENT_VERSION = os.getenv("AGENT_VERSION", "baseline-0080b11")

_REPO_ROOT = Path(__file__).resolve().parent.parent

# tri-state: None = not attempted, "failed" = terminal failure, provider = ready
_setup_state = None


class JsonlFileSpanExporter(SpanExporter):
    """Append each finished span as one JSON line. File is owner-only (0600):
    spans carry full conversation content."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # create with restrictive permissions before first append
        fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        os.close(fd)

    def export(self, spans) -> SpanExportResult:
        try:
            with self.path.open("a") as f:
                for span in spans:
                    f.write(json.dumps(json.loads(span.to_json())) + "\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass


def setup_tracing():
    """Idempotent; a failed setup is terminal (no retry, no partial global state
    from the pre-register steps). Returns the tracer provider or None."""
    global _setup_state
    if _setup_state is not None:
        return None if _setup_state == "failed" else _setup_state
    if os.getenv("TRACING_DISABLED", "").lower() in {"1", "true"}:
        _setup_state = "failed"
        return None

    # Fallible local steps first: nothing global is touched until they succeed.
    try:
        export_path = os.getenv(
            "TRACE_EXPORT_PATH", str(_REPO_ROOT / "traces" / "spans.jsonl")
        )
        jsonl_processor = SimpleSpanProcessor(JsonlFileSpanExporter(export_path))
        from openinference.instrumentation.anthropic import AnthropicInstrumentor

        instrumentor = AnthropicInstrumentor()
    except Exception as e:
        print(f"[tracing] setup failed before install, agent runs untraced: {e}")
        _setup_state = "failed"
        return None

    space_id = os.getenv("ARIZE_SPACE_ID", "")
    api_key = os.getenv("ARIZE_API_KEY", "")
    try:
        if space_id and api_key:
            from arize.otel import register

            provider = register(
                space_id=space_id,
                api_key=api_key,
                project_name=PROJECT_NAME,
                span_processors=[jsonl_processor],
                verbose=False,
            )
        else:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider

            provider = TracerProvider()
            provider.add_span_processor(jsonl_processor)
            trace.set_tracer_provider(provider)
    except Exception as e:
        # Nothing global was installed; the agent runs untraced.
        print(f"[tracing] exporter install failed, agent runs untraced: {e}")
        _setup_state = "failed"
        return None

    try:
        instrumentor.instrument(tracer_provider=provider)
    except Exception as e:
        # Provider and sinks are live; only auto LLM spans are missing.
        print(f"[tracing] LLM auto-instrumentation failed, continuing without LLM spans: {e}")

    _setup_state = provider
    return provider


def get_tracer():
    from opentelemetry import trace

    if _setup_state in (None, "failed"):
        return trace.NoOpTracer()
    return trace.get_tracer(PROJECT_NAME)
