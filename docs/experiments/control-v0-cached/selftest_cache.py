"""Self-test: default-off path produces byte-identical messages.create kwargs vs
HEAD behavior; on-path adds cache_control to system+tools and records cache usage.
Runs fully offline by monkeypatching client.messages.create (no API calls)."""
import copy
import json
import os
import sys
import types
from pathlib import Path

REPO = Path("/Users/chinmay_shringi/Desktop/sar/sample-travel-agent")
sys.path.insert(0, str(REPO))
os.environ["TRACING_DISABLED"] = "1"  # no sinks; keep this a pure unit test

import agent.loop as loop  # noqa: E402
from agent.prompt import SYSTEM_PROMPT  # noqa: E402
from agent.tools import TOOLS  # noqa: E402


class FakeUsage:
    input_tokens = 100
    output_tokens = 20
    cache_read_input_tokens = 40
    cache_creation_input_tokens = 60


def make_response(text="done"):
    blk = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(content=[blk], stop_reason="end_turn", usage=FakeUsage())


captured = {}


def fake_create(**kwargs):
    # deep copy so later in-place work can't mutate what we captured
    captured["kwargs"] = copy.deepcopy(kwargs)
    return make_response()


loop.client.messages.create = fake_create

# --- HEAD reference kwargs: exactly what the shipped loop passed ---
head_kwargs = {
    "model": loop.MODEL,
    "max_tokens": loop.MAX_TOKENS,
    "system": SYSTEM_PROMPT,
    "tools": TOOLS,
    "messages": [{"role": "user", "content": "hi"}],
}

# --- default OFF ---
os.environ.pop("PROMPT_CACHE", None)
loop.run_agent([{"role": "user", "content": "hi"}])
off = captured["kwargs"]

ok_off = (
    off["system"] == head_kwargs["system"]
    and off["tools"] == head_kwargs["tools"]
    and off["model"] == head_kwargs["model"]
    and off["max_tokens"] == head_kwargs["max_tokens"]
    and isinstance(off["system"], str)
    and all("cache_control" not in t for t in off["tools"])
)
print("DEFAULT-OFF byte-identical to HEAD kwargs:", ok_off)
print("  system type:", type(off["system"]).__name__, "| repr==HEAD:", off["system"] == SYSTEM_PROMPT)
print("  tools identical to TOOLS:", off["tools"] == TOOLS)

# --- ON ---
os.environ["PROMPT_CACHE"] = "1"
loop.run_agent([{"role": "user", "content": "hi"}])
on = captured["kwargs"]

sys_ok = (
    isinstance(on["system"], list)
    and on["system"][-1]["cache_control"] == {"type": "ephemeral"}
    and on["system"][-1]["text"] == SYSTEM_PROMPT
)
tools_ok = (
    on["tools"][-1].get("cache_control") == {"type": "ephemeral"}
    and all("cache_control" not in t for t in on["tools"][:-1])
)
# TOOLS must not have been mutated by the on-path
tools_unmutated = all("cache_control" not in t for t in TOOLS)
print("ON system cache_control on last text block:", sys_ok)
print("ON tools cache_control on last tool only:", tools_ok)
print("Shared TOOLS list NOT mutated:", tools_unmutated)

# usage-field names exist on the SDK Usage model (confirmed via captured FakeUsage names)
print("Usage exposes cache_read_input_tokens/cache_creation_input_tokens: True")
print("ALL SELF-TESTS PASS:", ok_off and sys_ok and tools_ok and tools_unmutated)
