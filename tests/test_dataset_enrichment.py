"""P1-03: appended failure cases must be replayable.

Self-contained by design: this module does its own sys.path setup and builds its
own fixtures, so it passes with or without a conftest.py. No network, no model
calls, no writes outside tmp_path (the committed golden dataset is only read).

Run:
    .venv/bin/python -m pytest tests/test_dataset_enrichment.py -v
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT, REPO_ROOT / "evals", REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from evals.dataset import (  # noqa: E402
    append_failures,
    failure_key,
    load_dataset,
)

GOLDEN = REPO_ROOT / "evals" / "golden_dataset.json"


# --- fixtures built here, not imported -------------------------------------


def _legacy_dataset() -> dict:
    """A dataset in the OLD five-key shape only. Backward compatibility is
    checked against this, not against a hand-waved assertion."""
    return {
        "version": "v1-2026-07-19",
        "conversations": [
            {
                "id": "shipped-01",
                "messages": ["Find me a flight from New York to Miami on March 12, 2026."],
                "tags": ["flight-search"],
                "eval_targets": ["E1", "E2"],
                "source": "shipped",
            },
            {
                "id": "failure-001",
                "messages": ["Book a hotel in Denver."],
                "tags": ["failure-append", "eval:E1", "reason:fabricated hotel"],
                "eval_targets": ["E1"],
                "source": "failure-append",
            },
        ],
    }


def _write_dataset(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def _grounding_case() -> dict:
    """One structured failure case as the loop now produces it."""
    return {
        "messages": [
            "I want a weekend in Denver in August 2026.",
            "Great, can you add a hotel for that weekend too?",
        ],
        "assistant_reply": "The Denver Grand Plaza is available at 189 USD a night.",
        "tool_calls": [
            {"name": "search_hotels", "input": {"city": "Denver", "check_in": "2026-08-07"}}
        ],
        "tool_outputs": [
            {
                "name": "search_hotels",
                "output": [],
                "result_count": 0,
                "result_empty": True,
                "error": None,
            }
        ],
        "failed_eval_ids": ["E1"],
        "failure_reasons": ["E1: hotel 'Denver Grand Plaza' is not in the fixture set"],
        "source_trace_id": "0xtrace-aaa",
        "source_session_id": "session-aaa",
        "pii_redacted": False,
    }


def _rows_by_source(path: Path, source: str) -> list:
    return [c for c in load_dataset(path)["conversations"] if c["source"] == source]


# --- Part A acceptance: a row round-trips with tool calls and outputs -------


def test_appended_row_round_trips_with_tool_calls_and_tool_outputs(tmp_path):
    path = _write_dataset(tmp_path, _legacy_dataset())
    version = append_failures(path, [_grounding_case()], today="2026-07-21")
    assert version == "v2-2026-07-21"

    reloaded = load_dataset(path)
    row = [c for c in reloaded["conversations"] if c["id"] == "failure-002"][0]

    # full multi-turn user history, not just the latest message
    assert row["messages"] == [
        "I want a weekend in Denver in August 2026.",
        "Great, can you add a hotel for that weekend too?",
    ]
    assert row["assistant_reply"].startswith("The Denver Grand Plaza")
    # the exact call payload, so a tool-parameter defect is reproducible
    assert row["tool_calls"] == [
        {"name": "search_hotels", "input": {"city": "Denver", "check_in": "2026-08-07"}}
    ]
    # the actual tool output the reply was built from, so groundedness is checkable
    assert row["tool_outputs"][0]["name"] == "search_hotels"
    assert row["tool_outputs"][0]["output"] == []
    assert row["tool_outputs"][0]["result_empty"] is True
    assert row["failed_eval_ids"] == ["E1"]
    assert row["failure_reasons"] == [
        "E1: hotel 'Denver Grand Plaza' is not in the fixture set"
    ]
    assert row["source_trace_id"] == "0xtrace-aaa"
    assert row["source_session_id"] == "session-aaa"
    assert row["pii_redacted"] is False
    assert row["source"] == "failure-append"


def test_expected_behavior_is_null_and_review_status_pending(tmp_path):
    """expected_behavior cannot be derived from a failed trace, so it is emitted
    as null for a human to fill. It is never auto-generated."""
    path = _write_dataset(tmp_path, _legacy_dataset())
    append_failures(path, [_grounding_case()], today="2026-07-21")
    row = [c for c in load_dataset(path)["conversations"] if c["id"] == "failure-002"][0]
    assert row["expected_behavior"] is None
    assert row["review_status"] == "pending"


# --- Part A acceptance: dedup distinguishes failures sharing an opener ------


def test_dedup_distinguishes_two_failures_sharing_opening_message(tmp_path):
    path = _write_dataset(tmp_path, _legacy_dataset())
    opener = "Plan me a trip from Denver to Miami."
    case_a = {"messages": [opener], "failed_eval_ids": ["E1"], "failure_reasons": ["fabricated"]}
    case_b = {"messages": [opener], "failed_eval_ids": ["E2"], "failure_reasons": ["backwards"]}

    append_failures(path, [case_a, case_b], today="2026-07-21")

    appended = _rows_by_source(path, "failure-append")
    # failure-001 was already present in the fixture, so 2 new rows -> 3 total
    assert len(appended) == 3
    new_rows = [r for r in appended if r["messages"] == [opener]]
    assert len(new_rows) == 2, "two different failures on one opener must not collapse"
    assert sorted(r["failed_eval_ids"][0] for r in new_rows) == ["E1", "E2"]
    assert new_rows[0]["dedup_key"] != new_rows[1]["dedup_key"]


def test_dedup_distinguishes_single_turn_from_multi_turn_same_opener(tmp_path):
    path = _write_dataset(tmp_path, _legacy_dataset())
    opener = "Plan me a trip to Tokyo."
    short = {"messages": [opener], "failed_eval_ids": ["E5"]}
    long = {"messages": [opener, "Actually make it Osaka."], "failed_eval_ids": ["E5"]}

    append_failures(path, [short, long], today="2026-07-21")

    rows = [r for r in _rows_by_source(path, "failure-append") if r["messages"][0] == opener]
    assert len(rows) == 2
    assert sorted(len(r["messages"]) for r in rows) == [1, 2]


def test_identical_failure_is_deduped_and_call_is_a_noop(tmp_path):
    path = _write_dataset(tmp_path, _legacy_dataset())
    first = append_failures(path, [_grounding_case()], today="2026-07-21")
    before = path.read_text()

    second = append_failures(path, [_grounding_case()], today="2026-07-22")

    assert second == first, "re-appending the same failure must not bump the version"
    assert path.read_text() == before, "no-op must leave the file byte-identical"


def test_dedup_key_is_stable_and_order_insensitive_on_failure_types():
    a = failure_key(["Hello there"], ["E2", "E1"])
    b = failure_key(["  hello   there "], ["E1", "E2"])
    c = failure_key(["Hello there"], ["E1"])
    assert a == b, "normalization + sorted failure types must give one stable key"
    assert a != c


# --- Part A acceptance: backward compatibility ------------------------------


def test_committed_golden_dataset_still_loads():
    data = load_dataset(GOLDEN)
    assert data["conversations"], "the committed dataset must keep loading unchanged"
    assert all("messages" in c for c in data["conversations"])


def test_legacy_and_enriched_rows_load_side_by_side(tmp_path):
    path = _write_dataset(tmp_path, _legacy_dataset())
    append_failures(path, [_grounding_case()], today="2026-07-21")
    data = load_dataset(path)
    shapes = {len(c) for c in data["conversations"]}
    assert len(shapes) > 1, "old five-key rows and new enriched rows must coexist"


def test_existing_rows_are_not_rewritten(tmp_path):
    original = _legacy_dataset()
    path = _write_dataset(tmp_path, original)
    append_failures(path, [_grounding_case()], today="2026-07-21")
    after = load_dataset(path)["conversations"]
    assert after[: len(original["conversations"])] == original["conversations"]


def test_legacy_failure_shape_is_still_accepted(tmp_path):
    """The old {"user_input", "eval_id", "reason"} contract keeps working."""
    path = _write_dataset(tmp_path, _legacy_dataset())
    append_failures(
        path,
        [{"user_input": "Weather in London?", "eval_id": "E6", "reason": "wrong unit"}],
        today="2026-07-21",
    )
    row = [c for c in load_dataset(path)["conversations"] if c["id"] == "failure-002"][0]
    assert row["messages"] == ["Weather in London?"]
    assert row["failed_eval_ids"] == ["E6"]
    assert row["failure_reasons"] == ["wrong unit"]
    assert row["tool_calls"] == []


def test_legacy_failure_row_dedups_against_its_enriched_equivalent(tmp_path):
    """A legacy failure-append row records its eval in eval_targets; the new key
    recovers that, so re-capturing the same failure stays a no-op."""
    path = _write_dataset(tmp_path, _legacy_dataset())
    version = append_failures(
        path,
        [{"user_input": "Book a hotel in Denver.", "eval_id": "E1", "reason": "fabricated"}],
        today="2026-07-21",
    )
    assert version == "v1-2026-07-19"
    assert len(_rows_by_source(path, "failure-append")) == 1


def test_bad_failure_input_fails_fast(tmp_path):
    import pytest

    path = _write_dataset(tmp_path, _legacy_dataset())
    with pytest.raises(ValueError):
        append_failures(path, [{"messages": []}], today="2026-07-21")
    with pytest.raises(TypeError):
        append_failures(path, ["not a dict"], today="2026-07-21")


# --- trace_model exposes what the enriched row needs ------------------------


def _span(trace_id, span_id, parent, attrs, name="span"):
    return {
        "name": name,
        "context": {"trace_id": trace_id, "span_id": span_id, "trace_state": "[]"},
        "kind": "SpanKind.INTERNAL",
        "parent_id": parent,
        "start_time": "2026-07-21T10:00:00.000000Z",
        "end_time": "2026-07-21T10:00:01.000000Z",
        "status": {"status_code": "OK"},
        "attributes": attrs,
        "events": [],
        "links": [],
    }


def _two_turn_spans() -> list:
    """A root span plus one LLM span whose history holds two user turns and one
    tool-result message (role 'user' with a tool_call_id), and one tool span."""
    tid = "0xabc"
    root = _span(
        tid,
        "0x01",
        None,
        {
            "openinference.span.kind": "AGENT",
            "session.id": "sess-1",
            "input.value": "Great, can you add a hotel for that weekend too?",
            "output.value": "The Denver Grand Plaza is 189 USD a night.",
            "agent.iterations": 2,
            "prompt_version": "v0",
            "agent_version": "baseline",
            "metadata": json.dumps({"pii.redacted": True, "pii.types": ["email"]}),
        },
        name="agent.run",
    )
    llm = _span(
        tid,
        "0x02",
        "0x01",
        {
            "openinference.span.kind": "LLM",
            "llm.token_count.prompt": 100,
            "llm.token_count.completion": 20,
            "llm.input_messages.0.message.role": "system",
            "llm.input_messages.0.message.content": "Help Book Travel.",
            "llm.input_messages.1.message.role": "user",
            "llm.input_messages.1.message.content": "I want a weekend in Denver in August 2026.",
            "llm.input_messages.2.message.role": "assistant",
            "llm.input_messages.2.message.content": "Here are some flights.",
            "llm.input_messages.3.message.role": "user",
            "llm.input_messages.3.message.content": '[{"airline": "Delta"}]',
            "llm.input_messages.3.message.tool_call_id": "toolu_01",
            "llm.input_messages.4.message.role": "user",
            "llm.input_messages.4.message.content": "Great, can you add a hotel for that weekend too?",
        },
        name="messages.create",
    )
    tool = _span(
        tid,
        "0x03",
        "0x01",
        {
            "openinference.span.kind": "TOOL",
            "tool.name": "search_hotels",
            "input.value": json.dumps({"city": "Denver", "check_in": "2026-08-07"}),
            "output.value": json.dumps([]),
            "tool.result_count": 0,
            "tool.result_empty": True,
        },
        name="search_hotels",
    )
    return [root, llm, tool]


def _write_spans(tmp_path: Path, spans: list) -> Path:
    path = tmp_path / "spans.jsonl"
    path.write_text("".join(json.dumps(s) + "\n" for s in spans))
    return path


def test_trace_view_exposes_full_user_history_tools_and_pii(tmp_path):
    from trace_model import load_traces

    trace = load_traces(_write_spans(tmp_path, _two_turn_spans()))[0]

    assert trace.user_messages() == [
        "I want a weekend in Denver in August 2026.",
        "Great, can you add a hotel for that weekend too?",
    ], "tool-result messages must not be mistaken for user turns"
    assert trace.tool_call_payloads() == [
        {"name": "search_hotels", "input": {"city": "Denver", "check_in": "2026-08-07"}}
    ]
    assert trace.tool_output_payloads()[0]["result_empty"] is True
    # pii flags ride in the metadata attribute written by using_metadata
    assert trace.pii_redacted is True
    assert trace.pii_types == ["email"]


def test_trace_view_pii_defaults_to_false_when_absent(tmp_path):
    from trace_model import load_traces

    spans = _two_turn_spans()
    spans[0]["attributes"].pop("metadata")
    trace = load_traces(_write_spans(tmp_path, spans))[0]
    assert trace.pii_redacted is False
    assert trace.pii_types == []


def test_run_evals_trace_context_carries_replay_payload(tmp_path):
    from run_evals import _trace_context
    from trace_model import load_traces

    trace = load_traces(_write_spans(tmp_path, _two_turn_spans()))[0]
    ctx = _trace_context(trace)

    assert len(ctx["messages"]) == 2
    assert ctx["assistant_reply"] == "The Denver Grand Plaza is 189 USD a night."
    assert ctx["tool_calls"][0]["name"] == "search_hotels"
    assert ctx["tool_outputs"][0]["output"] == []
    assert ctx["pii_redacted"] is True
    assert ctx["session_id"] == "sess-1"
    assert "expected_behavior" not in ctx, "never fabricate an expected behavior"


# --- the loop hands the structured case through -----------------------------


def _failing_result(trace_id, eval_id, reason, ctx):
    return {
        "trace_id": trace_id,
        "session_id": ctx["session_id"],
        "user_input": ctx["messages"][-1],
        "trace_context": ctx,
        "eval_id": eval_id,
        "name": f"name_{eval_id}",
        "passed": False,
        "reason": reason,
        "attribution": "model",
    }


def test_structured_cases_groups_failures_by_trace(tmp_path):
    import feedback_loop
    from run_evals import _trace_context
    from trace_model import load_traces

    trace = load_traces(_write_spans(tmp_path, _two_turn_spans()))[0]
    ctx = _trace_context(trace)
    results = [
        _failing_result("t1", "E1", "fabricated hotel", ctx),
        _failing_result("t1", "E5", "hedged answer", ctx),
        dict(_failing_result("t1", "E2", "ok", ctx), passed=True),
    ]

    cases = feedback_loop._structured_cases(results)

    assert len(cases) == 1, "one trace is one replayable case"
    case = cases[0]
    assert case["failed_eval_ids"] == ["E1", "E5"]
    assert case["failure_reasons"] == ["E1: fabricated hotel", "E5: hedged answer"]
    assert case["source_trace_id"] == "t1"
    assert case["tool_calls"][0]["name"] == "search_hotels"
    assert case["pii_redacted"] is True
    assert len(case["messages"]) == 2


def test_structured_case_appends_and_round_trips_through_the_dataset(tmp_path):
    import feedback_loop
    from run_evals import _trace_context
    from trace_model import load_traces

    trace = load_traces(_write_spans(tmp_path, _two_turn_spans()))[0]
    ctx = _trace_context(trace)
    cases = feedback_loop._structured_cases(
        [_failing_result("t1", "E1", "fabricated hotel", ctx)]
    )

    path = _write_dataset(tmp_path, _legacy_dataset())
    append_failures(path, cases, today="2026-07-21")

    row = [c for c in load_dataset(path)["conversations"] if c["id"] == "failure-002"][0]
    assert row["messages"] == ctx["messages"]
    assert row["tool_outputs"][0]["name"] == "search_hotels"
    assert row["pii_redacted"] is True
    assert row["expected_behavior"] is None


def test_results_without_trace_context_still_degrade_to_an_appendable_case():
    """Older results.jsonl rows have no trace_context; they must still curate."""
    import feedback_loop

    cases = feedback_loop._structured_cases(
        [{"trace_id": "t9", "user_input": "Flights to Austin?", "eval_id": "E1",
          "passed": False, "reason": "fabricated"}]
    )
    assert len(cases) == 1
    assert cases[0]["messages"] == ["Flights to Austin?"]
    assert cases[0]["tool_calls"] == []
