import uuid
from contextlib import nullcontext

from fastapi import FastAPI
from openinference.instrumentation import using_metadata, using_session
from opentelemetry import trace as otel_trace
from pydantic import BaseModel

from agent.loop import run_agent
from agent.redaction import redact

app = FastAPI(title="Travel Agent")


def _pii_metadata(pii_types: list):
    """Propagate PII flags into the OpenInference context so the root agent span
    (created inside run_agent) carries them: run_agent merges
    get_attributes_from_context() onto that span. No-op when nothing was
    redacted. This is the mechanism that reliably tags the root span, since the
    request handler itself has no recording span."""
    if not pii_types:
        return nullcontext()
    return using_metadata({"pii.redacted": True, "pii.types": pii_types})


def _flag_pii_on_current_span(pii_types: list) -> None:
    """Best-effort: tag whatever span is currently active with the PII flags.
    Guarded so a NonRecordingSpan (the default when tracing is off, and the
    actual state inside this handler) or any tracer error never breaks the
    request. Reliable root-span tagging is handled by _pii_metadata above."""
    if not pii_types:
        return
    try:
        span = otel_trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute("pii.redacted", True)
            span.set_attribute("pii.types", pii_types)
    except Exception:
        pass


@app.on_event("shutdown")
def _flush_traces():
    # The OTLP batch processor loses its final batch if the process exits before
    # delivery (observed: last 2 baseline traces missing from AX). Flush with a
    # generous timeout on graceful shutdown; additive, no request-path change.
    from agent.tracing import setup_tracing

    provider = setup_tracing()
    if provider is not None:
        provider.force_flush(15000)


from agent.session_store import build_store

# Default (no SESSION_STORE env): in-process DictStore, semantically identical
# to the shipped module-level dict. SESSION_STORE=sqlite persists sessions.
CONVERSATIONS = build_store()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    conversation_id = req.conversation_id or str(uuid.uuid4())
    messages = CONVERSATIONS.get(conversation_id)
    # Redact AT SOURCE: only the cleaned text is ever appended, persisted, sent
    # to the model, or written to a span. The raw req.message is never stored.
    clean_message, pii_findings = redact(req.message)
    messages.append({"role": "user", "content": clean_message})
    pii_types = sorted(set(pii_findings))
    with using_session(conversation_id), _pii_metadata(pii_types):
        _flag_pii_on_current_span(pii_types)
        reply, messages = run_agent(messages)
    CONVERSATIONS.put(conversation_id, messages)
    return ChatResponse(reply=reply, conversation_id=conversation_id)
