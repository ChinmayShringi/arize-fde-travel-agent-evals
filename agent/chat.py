import uuid
from contextlib import nullcontext

from openinference.instrumentation import using_metadata, using_session
from opentelemetry import trace as otel_trace

from agent.loop import run_agent
from agent.redaction import redact


def _pii_metadata(pii_types: list):
    """Propagate PII flags into the OpenInference context so the root agent span
    (created inside run_agent) carries them via get_attributes_from_context().
    No-op when nothing was redacted."""
    if not pii_types:
        return nullcontext()
    return using_metadata({"pii.redacted": True, "pii.types": pii_types})


def _flag_pii_on_current_span(pii_types: list) -> None:
    """Best-effort tag of the active span; guarded so a NonRecordingSpan or any
    tracer error never breaks the turn. Reliable root-span tagging is handled by
    _pii_metadata above."""
    if not pii_types:
        return
    try:
        span = otel_trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute("pii.redacted", True)
            span.set_attribute("pii.types", pii_types)
    except Exception:
        pass


def main():
    print("Travel Agent — ask me about flights, hotels, weather, or trip plans.")
    print("Type 'quit' to exit.\n")
    session_id = str(uuid.uuid4())
    messages = []
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break
        # Redact AT SOURCE: only cleaned text is appended, sent to the model, or
        # traced. The raw user_input is never stored.
        clean_input, pii_findings = redact(user_input)
        messages.append({"role": "user", "content": clean_input})
        pii_types = sorted(set(pii_findings))
        with using_session(session_id), _pii_metadata(pii_types):
            _flag_pii_on_current_span(pii_types)
            reply, messages = run_agent(messages)
        print(f"\nagent> {reply}\n")


if __name__ == "__main__":
    main()
