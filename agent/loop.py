import json
import os
import time

import anthropic
from openinference.instrumentation import get_attributes_from_context
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry.trace import Status, StatusCode

from agent.config import AGENT_DEADLINE_SECONDS, MAX_AGENT_ITERATIONS, MAX_TOKENS, MODEL
from agent.prompt import SYSTEM_PROMPT
from agent.tools import TOOLS, execute_tool
from agent.tracing import AGENT_VERSION, PROMPT_VERSION, get_tracer, setup_tracing

setup_tracing()
client = anthropic.Anthropic()
tracer = get_tracer()


# Returned verbatim when a termination control fires. It must never contain
# itinerary content: a truncated run has no verified inventory behind it, and
# groundedness is the primary metric for this system.
LIMIT_FALLBACK_REPLY = (
    "I could not complete the itinerary reliably within the allowed number of "
    "steps. Please revise the request or try again."
)


def _limit_breached(iterations: int, deadline: float) -> str | None:
    """Name of the termination control that has fired, or None to keep going.
    Checked before each model call, so a turn already in flight is never cut off
    mid-request."""
    if iterations >= MAX_AGENT_ITERATIONS:
        return "max_iterations"
    if time.monotonic() >= deadline:
        return "deadline"
    return None


def _prompt_cache_on() -> bool:
    """Env gate. Default off: when unset/0 the messages.create call shape is
    byte-identical to the shipped agent (plain string system, bare TOOLS list)."""
    return os.getenv("PROMPT_CACHE") == "1"


def _cacheable_system(prompt: str) -> list:
    """System prompt as a single cacheable text block (cache_control on the last
    block marks the whole prefix cacheable, per anthropic SDK 0.116.0 TextBlockParam)."""
    return [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]


def _cacheable_tools(tools: list) -> list:
    """New tools list with cache_control on the final tool (ToolParam.cache_control,
    SDK 0.116.0). Marks the whole tools array as a cacheable prefix. Never mutates
    the shared TOOLS list."""
    return [*tools[:-1], {**tools[-1], "cache_control": {"type": "ephemeral"}}]


def _execute_tool_traced(name: str, tool_input: dict):
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(
            SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value
        )
        span.set_attribute(SpanAttributes.TOOL_NAME, name)
        span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(tool_input))
        span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
        span.set_attributes(dict(get_attributes_from_context()))
        result = execute_tool(name, tool_input)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, json.dumps(result))
        span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
        error = result.get("error") if isinstance(result, dict) else None
        if isinstance(result, list):
            span.set_attribute("tool.result_count", len(result))
        span.set_attribute("tool.result_empty", result == [] or error is not None)
        if error is not None:
            span.set_attribute("tool.error", error)
            span.set_status(Status(StatusCode.ERROR, error))
        return result


def run_agent(messages: list) -> tuple[str, list]:
    """Run one user turn through the tool-calling loop.

    `messages` must end with the latest user message. Returns the assistant's
    reply text and the updated message history.
    """
    with tracer.start_as_current_span("agent_turn") as root:
        root.set_attribute(
            SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value
        )
        root.set_attribute(SpanAttributes.INPUT_VALUE, str(messages[-1]["content"]))
        root.set_attribute("prompt_version", PROMPT_VERSION)
        root.set_attribute("agent_version", AGENT_VERSION)
        root.set_attributes(dict(get_attributes_from_context()))
        iterations = 0
        cache_on = _prompt_cache_on()
        system = _cacheable_system(SYSTEM_PROMPT) if cache_on else SYSTEM_PROMPT
        tools = _cacheable_tools(TOOLS) if cache_on else TOOLS
        cache_read_tokens = 0
        cache_creation_tokens = 0
        deadline = time.monotonic() + AGENT_DEADLINE_SECONDS
        breach = None
        try:
            while True:
                breach = _limit_breached(iterations, deadline)
                if breach is not None:
                    break
                create_kwargs = dict(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    tools=tools,
                    messages=messages,
                )
                if cache_on:
                    # Top-level cache_control auto-marks the LAST cacheable block,
                    # so the cacheable prefix includes the whole message history.
                    # Marking only system+tools (1,031 tok) is below Haiku's
                    # minimum cacheable length and silently never caches: see
                    # docs/experiments/control-v0-cached/CACHE_MEASUREMENT.md.
                    create_kwargs["cache_control"] = {"type": "ephemeral"}
                response = client.messages.create(**create_kwargs)
                iterations += 1
                if cache_on:
                    usage = response.usage
                    cache_read_tokens += usage.cache_read_input_tokens or 0
                    cache_creation_tokens += usage.cache_creation_input_tokens or 0
                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = _execute_tool_traced(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )
                messages.append({"role": "user", "content": tool_results})

            if breach is None:
                reply = "".join(
                    block.text for block in response.content if block.type == "text"
                )
            else:
                detail = (
                    f"agent stopped by {breach} control after {iterations} "
                    f"iterations; no itinerary was produced"
                )
                root.set_attribute("agent.limit_breached", breach)
                root.set_status(Status(StatusCode.ERROR, detail))
                reply = LIMIT_FALLBACK_REPLY
                # Close the history with the fallback so the stored conversation
                # ends on an assistant turn, exactly as the normal path does.
                messages = [*messages, {"role": "assistant", "content": reply}]
            root.set_attribute(SpanAttributes.OUTPUT_VALUE, reply)
        finally:
            root.set_attribute("agent.iterations", iterations)
            if cache_on:
                # Additive, cache-only: summed across every turn in this agent run.
                root.set_attribute("llm.cache_read_tokens", cache_read_tokens)
                root.set_attribute("llm.cache_creation_tokens", cache_creation_tokens)
    return reply, messages
