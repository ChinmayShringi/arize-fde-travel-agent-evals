"""Runtime termination controls on the agent tool-calling loop (P1-05).

Self-contained on purpose: no conftest.py, no fixtures from elsewhere, and no
network. The Anthropic client is replaced with a fake that always answers
stop_reason "tool_use", which is exactly the shape that looped forever before
the caps existed.

Run with:  pytest tests/test_loop_limits.py
Or bare:   python tests/test_loop_limits.py
"""

import contextlib
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Must be set before importing agent.loop: it builds a tracer and an
# anthropic.Anthropic() at import time. No real key is ever used because the
# client object is replaced below, but the constructor needs one to exist.
os.environ["TRACING_DISABLED"] = "1"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

from agent import loop as agent_loop  # noqa: E402


class MiniMonkeyPatch:
    """Stand-in for pytest's monkeypatch fixture so this file also runs under a
    bare interpreter: the project venv does not currently ship pytest."""

    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value):
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self):
        for target, name, original in reversed(self._undo):
            setattr(target, name, original)
        self._undo = []


class FakeBlock:
    """Minimal stand-in for an anthropic content block."""

    def __init__(self, type_, **kwargs):
        self.type = type_
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeUsage:
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class FakeResponse:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = FakeUsage()


class FakeMessages:
    """Counts calls and replays a fixed script of responses."""

    def __init__(self, response_factory):
        self._response_factory = response_factory
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        return self._response_factory(self.call_count)


class FakeClient:
    def __init__(self, response_factory):
        self.messages = FakeMessages(response_factory)


class FakeSpan:
    def __init__(self):
        self.attributes = {}
        self.status = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_attributes(self, mapping):
        self.attributes.update(mapping)

    def set_status(self, status):
        self.status = status


class FakeTracer:
    """Records every span so the test can assert on breach telemetry."""

    def __init__(self):
        self.spans = []

    @contextlib.contextmanager
    def start_as_current_span(self, name):
        span = FakeSpan()
        span.name = name
        self.spans.append(span)
        yield span

    def root_span(self):
        return next(s for s in self.spans if s.name == "agent_turn")


class FakeClock:
    """Monotonic clock that jumps forward a fixed amount on every read."""

    def __init__(self, step_seconds):
        self.step_seconds = step_seconds
        self.now = 0.0

    def monotonic(self):
        value = self.now
        self.now += self.step_seconds
        return value


def _tool_use_response(_call_number):
    """A response that always asks for another tool call: unbounded without a cap."""
    return FakeResponse(
        content=[
            FakeBlock(
                "tool_use",
                id="toolu_fake",
                name="search_flights",
                input={"origin": "NYC", "destination": "London", "date": "2026-08-01"},
            )
        ],
        stop_reason="tool_use",
    )


def _install(monkeypatch, tracer, response_factory):
    client = FakeClient(response_factory)
    monkeypatch.setattr(agent_loop, "client", client)
    monkeypatch.setattr(agent_loop, "tracer", tracer)
    return client


def test_iteration_cap_fires_and_returns_truthful_fallback(monkeypatch):
    tracer = FakeTracer()
    client = _install(monkeypatch, tracer, _tool_use_response)
    monkeypatch.setattr(agent_loop, "MAX_AGENT_ITERATIONS", 3)

    reply, messages = agent_loop.run_agent([{"role": "user", "content": "plan a trip"}])

    assert reply == agent_loop.LIMIT_FALLBACK_REPLY
    assert client.messages.call_count == 3
    root = tracer.root_span()
    assert root.attributes["agent.limit_breached"] == "max_iterations"
    assert root.attributes["agent.iterations"] == 3
    assert root.status is not None
    assert messages[-1] == {"role": "assistant", "content": reply}


def test_default_iteration_cap_terminates_at_eight(monkeypatch):
    tracer = FakeTracer()
    client = _install(monkeypatch, tracer, _tool_use_response)

    reply, _ = agent_loop.run_agent([{"role": "user", "content": "plan a trip"}])

    assert reply == agent_loop.LIMIT_FALLBACK_REPLY
    assert client.messages.call_count == agent_loop.MAX_AGENT_ITERATIONS == 8


def test_fallback_invents_no_itinerary_content(monkeypatch):
    tracer = FakeTracer()
    _install(monkeypatch, tracer, _tool_use_response)
    monkeypatch.setattr(agent_loop, "MAX_AGENT_ITERATIONS", 2)

    reply, _ = agent_loop.run_agent([{"role": "user", "content": "plan a trip"}])

    lowered = reply.lower()
    for fabricated in ("hotel", "flight", "$", "day 1", "airline", "check-in"):
        assert fabricated not in lowered


def test_deadline_fires_before_the_iteration_cap(monkeypatch):
    tracer = FakeTracer()
    client = _install(monkeypatch, tracer, _tool_use_response)
    # 25s per clock read against a 60s budget: reads at 0s and 25s pass, 50s passes,
    # 75s breaches. The iteration cap of 8 is never reached.
    monkeypatch.setattr(agent_loop, "time", FakeClock(step_seconds=25.0))
    monkeypatch.setattr(agent_loop, "AGENT_DEADLINE_SECONDS", 60.0)

    reply, _ = agent_loop.run_agent([{"role": "user", "content": "plan a trip"}])

    assert reply == agent_loop.LIMIT_FALLBACK_REPLY
    assert client.messages.call_count < 8
    assert tracer.root_span().attributes["agent.limit_breached"] == "deadline"


def test_normal_conversation_is_unchanged(monkeypatch):
    """One tool call then a text answer: well inside both limits, so the reply is
    the model's own text and no breach attribute is recorded."""
    tracer = FakeTracer()

    def script(call_number):
        if call_number == 1:
            return _tool_use_response(call_number)
        return FakeResponse(
            content=[FakeBlock("text", text="Here is your itinerary.")],
            stop_reason="end_turn",
        )

    client = _install(monkeypatch, tracer, script)

    reply, messages = agent_loop.run_agent([{"role": "user", "content": "plan a trip"}])

    assert reply == "Here is your itinerary."
    assert client.messages.call_count == 2
    root = tracer.root_span()
    assert "agent.limit_breached" not in root.attributes
    assert root.attributes["agent.iterations"] == 2
    assert root.status is None


def test_measured_traffic_fits_inside_the_defaults():
    """Guards the default choice: the caps must stay above what real runs did.
    Max observed agent_turn iterations in docs/baseline and docs/experiments is 3."""
    assert agent_loop.MAX_AGENT_ITERATIONS >= 8
    assert agent_loop.AGENT_DEADLINE_SECONDS >= 60


def _run_without_pytest() -> int:
    """Minimal runner for `python tests/test_loop_limits.py`."""
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    failures = 0
    for name, test in tests:
        patch = MiniMonkeyPatch()
        try:
            if test.__code__.co_argcount:
                test(patch)
            else:
                test()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc!r}")
        finally:
            patch.undo()
    print(f"\n{len(tests) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        import pytest
    except ImportError:
        sys.exit(_run_without_pytest())
    sys.exit(pytest.main([__file__, "-v"]))
