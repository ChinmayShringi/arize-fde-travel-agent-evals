"""Read exported spans (JSONL, OpenInference attributes) into per-trace views.

This is the single seam between the span schema and the evals: every eval reads
TraceView, never raw spans. Works on any spans.jsonl produced by agent.tracing,
independent of Arize AX.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolCall:
    name: str
    input: dict
    output: object  # list or dict, parsed from JSON
    result_count: int | None
    result_empty: bool
    error: str | None


@dataclass
class LlmCall:
    # [{"role": ..., "content": ..., "tool_call_id": ...}] flattened from attributes.
    # tool_call_id is present only on tool-result messages (Anthropic sends those
    # with role "user"), so it is how a real user turn is told from a tool result.
    input_messages: list
    prompt_tokens: int
    completion_tokens: int


@dataclass
class TraceView:
    trace_id: str
    session_id: str | None
    user_input: str
    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    llm_calls: list[LlmCall] = field(default_factory=list)
    iterations: int | None = None
    prompt_version: str | None = None
    agent_version: str | None = None
    latency_ms: float | None = None
    root_status: str | None = None
    # Set by agent/chat.py and agent/api.py when redact() found PII in the turn.
    # False means "no redaction flag on this trace", which is also what an export
    # from a code path that never redacts looks like.
    pii_redacted: bool = False
    pii_types: list = field(default_factory=list)

    def user_messages(self) -> list:
        """The multi-turn user history the model saw this turn, oldest first.

        Needed to replay a failure: a conflict or follow-up defect is invisible
        without the earlier turns. Tool results arrive as role "user" messages
        carrying a tool_call_id, so those are excluded. The LLM span with the
        most input messages holds the longest history in the trace."""
        if not self.llm_calls:
            return [self.user_input] if self.user_input else []
        richest = max(self.llm_calls, key=lambda c: len(c.input_messages))
        msgs = [
            m.get("content", "")
            for m in richest.input_messages
            if m.get("role") == "user" and not m.get("tool_call_id")
        ]
        msgs = [m for m in msgs if isinstance(m, str) and m.strip()]
        return msgs or ([self.user_input] if self.user_input else [])

    def tool_call_payloads(self) -> list:
        """[{"name", "input"}] for every tool call, in call order."""
        return [{"name": c.name, "input": c.input} for c in self.tool_calls]

    def tool_output_payloads(self) -> list:
        """[{"name", "output", ...}] for every tool call, in call order. Aligned
        index-for-index with tool_call_payloads()."""
        return [
            {
                "name": c.name,
                "output": c.output,
                "result_count": c.result_count,
                "result_empty": c.result_empty,
                "error": c.error,
            }
            for c in self.tool_calls
        ]

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.llm_calls)

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.llm_calls)

    def prior_context_text(self) -> str:
        """All message content visible to the model this turn, including prior
        turns' tool results (they ride in the LLM spans' input messages). Used
        by groundedness checks so a reply restating an earlier turn's tool
        result is not flagged as fabricated."""
        parts = []
        for call in self.llm_calls:
            for msg in call.input_messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    parts.append(content)
        return "\n".join(parts)


def _parse_ts(ts: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _llm_input_messages(attrs: dict) -> list:
    """Reconstruct llm.input_messages.{i}.message.* flattened attributes."""
    msgs = {}
    prefix = "llm.input_messages."
    for key, value in attrs.items():
        if not key.startswith(prefix):
            continue
        rest = key[len(prefix):]
        idx_str, _, tail = rest.partition(".")
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        slot = msgs.setdefault(idx, {})
        if tail == "message.role":
            slot["role"] = value
        elif tail == "message.content":
            slot["content"] = value
        elif tail == "message.tool_call_id":
            slot["tool_call_id"] = value
        elif tail.startswith("message.contents."):
            # block-structured content: collect text blocks in order
            slot.setdefault("blocks", []).append((tail, value))
    out = []
    for idx in sorted(msgs):
        m = msgs[idx]
        if "content" not in m and "blocks" in m:
            texts = [v for k, v in sorted(m["blocks"]) if k.endswith("text")]
            m["content"] = "\n".join(str(t) for t in texts)
        m.pop("blocks", None)
        out.append(m)
    return out


def _read_pii(attrs: dict) -> tuple:
    """Read the PII flags off a root span. The agent sets them two ways and both
    are honored here:
      - directly on the active span as "pii.redacted" / "pii.types"
        (agent/chat.py _flag_pii_on_current_span, agent/api.py)
      - via openinference using_metadata, which serializes the dict into the
        "metadata" span attribute as a JSON string
    Absent flags mean "not redacted"; this never guesses PII from the text.
    Returns (redacted: bool, types: list)."""
    redacted = bool(attrs.get("pii.redacted", False))
    types = attrs.get("pii.types") or []
    meta = attrs.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = None
    if isinstance(meta, dict):
        redacted = redacted or bool(meta.get("pii.redacted", False))
        if not types:
            types = meta.get("pii.types") or []
    if isinstance(types, str):
        types = [types]
    return redacted, list(types)


def load_traces(spans_path: str | Path) -> list[TraceView]:
    spans = [json.loads(line) for line in Path(spans_path).open()]
    by_trace: dict[str, list[dict]] = {}
    for s in spans:
        by_trace.setdefault(s["context"]["trace_id"], []).append(s)

    traces = []
    for trace_id, group in by_trace.items():
        root = next((s for s in group if s["parent_id"] is None), None)
        if root is None:
            continue  # incomplete export; skip but do not crash
        a = root["attributes"]
        pii_redacted, pii_types = _read_pii(a)
        view = TraceView(
            trace_id=trace_id,
            session_id=a.get("session.id"),
            user_input=a.get("input.value", ""),
            reply=a.get("output.value", ""),
            iterations=a.get("agent.iterations"),
            prompt_version=a.get("prompt_version"),
            agent_version=a.get("agent_version"),
            latency_ms=(
                (_parse_ts(root["end_time"]) - _parse_ts(root["start_time"])) * 1000
                if root.get("end_time") and root.get("start_time")
                else None
            ),
            root_status=(root.get("status") or {}).get("status_code"),
            pii_redacted=pii_redacted,
            pii_types=pii_types,
        )
        for s in sorted(group, key=lambda s: s["start_time"]):
            sa = s["attributes"]
            kind = sa.get("openinference.span.kind")
            if kind == "TOOL":
                try:
                    output = json.loads(sa.get("output.value", "null"))
                except json.JSONDecodeError:
                    output = sa.get("output.value")
                try:
                    tool_input = json.loads(sa.get("input.value", "{}"))
                except json.JSONDecodeError:
                    tool_input = {}
                view.tool_calls.append(
                    ToolCall(
                        name=sa.get("tool.name", s["name"]),
                        input=tool_input,
                        output=output,
                        result_count=sa.get("tool.result_count"),
                        result_empty=bool(sa.get("tool.result_empty")),
                        error=sa.get("tool.error"),
                    )
                )
            elif kind == "LLM":
                view.llm_calls.append(
                    LlmCall(
                        input_messages=_llm_input_messages(sa),
                        prompt_tokens=int(sa.get("llm.token_count.prompt", 0)),
                        completion_tokens=int(sa.get("llm.token_count.completion", 0)),
                    )
                )
        traces.append(view)

    # stable order: by root start time
    def root_start(v: TraceView) -> str:
        for s in spans:
            if s["context"]["trace_id"] == v.trace_id and s["parent_id"] is None:
                return s["start_time"]
        return ""

    traces.sort(key=root_start)
    return traces
