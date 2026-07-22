"""evals/trace_model.py: the single seam between the span schema and the evals.

Every eval reads TraceView and never a raw span, so a parsing mistake here is
silently wrong scores everywhere downstream. The parsing tests below run against
the committed fixture (real spans, verbatim from docs/baseline/2026-07-19) and
against hand-built spans for the edge cases the real export does not contain.

The last section is the offline eval smoke test the fixture exists for: run the
whole deterministic suite over committed spans, with no credentials and no
network, and pin the first failing eval per trace together with its attribution.
Attribution is the load-bearing field -- it decides whether the feedback loop
proposes a tool change or a prompt change.
"""

import json

import pytest

from evals.trace_model import TraceView, _llm_input_messages, load_traces

PARIS = "I need a hotel in Paris"
MIAMI_FOLLOWUP = "Great, can you add a hotel"
CHICAGO_DENVER = "I want to fly from Chicago to Denver"
DENVER_MIAMI_EMPTY = "Are there any flights from Denver to Miami"
VISA = "Do I need a visa"


def write_spans(path, spans) -> str:
    path.write_text("\n".join(json.dumps(s) for s in spans) + "\n")
    return str(path)


def span(trace_id, span_id, parent_id, name, attributes, start="2026-07-19T10:00:00Z",
         end="2026-07-19T10:00:01Z"):
    return {
        "name": name,
        "context": {"trace_id": trace_id, "span_id": span_id},
        "parent_id": parent_id,
        "start_time": start,
        "end_time": end,
        "attributes": attributes,
        "status": {"status_code": "UNSET"},
    }


# --------------------------------------------------------------------------- #
# Parsing the real fixture
# --------------------------------------------------------------------------- #
class TestLoadRealSpans:
    def test_spans_are_grouped_one_view_per_trace(self, traces):
        assert len(traces) == 5
        assert len({t.trace_id for t in traces}) == 5

    def test_traces_are_ordered_by_root_start_time(self, traces):
        assert [t.user_input[:24] for t in traces] == [
            "I need a hotel in Paris ",
            "Great, can you add a hot",
            "I want to fly from Chica",
            "Are there any flights fr",
            "Do I need a visa to visi",
        ]

    def test_root_attributes_are_lifted_onto_the_view(self, trace_by_prefix):
        trace = trace_by_prefix(PARIS)
        assert trace.user_input.startswith("I need a hotel in Paris")
        assert trace.reply.startswith("Great! I found 2 hotels")
        assert trace.prompt_version == "v0-shipped"
        assert trace.agent_version == "baseline-0080b11"
        assert trace.iterations == 2
        assert trace.session_id

    def test_latency_is_derived_from_the_root_span_window(self, trace_by_prefix):
        trace = trace_by_prefix(PARIS)
        assert 3000 < trace.latency_ms < 4000

    def test_tool_spans_become_tool_calls_with_parsed_json(self, trace_by_prefix):
        trace = trace_by_prefix(PARIS)
        assert len(trace.tool_calls) == 1
        call = trace.tool_calls[0]
        assert call.name == "search_hotels"
        assert call.input == {
            "city": "Paris",
            "check_in": "2026-06-10",
            "check_out": "2026-06-14",
        }
        assert isinstance(call.output, list)
        assert call.result_count == 2
        assert call.result_empty is False
        assert call.error is None

    def test_an_empty_tool_result_is_marked_empty(self, trace_by_prefix):
        call = trace_by_prefix(DENVER_MIAMI_EMPTY).tool_calls[0]
        assert call.output == []
        assert call.result_count == 0
        assert call.result_empty is True

    def test_a_trace_with_no_tool_span_has_no_tool_calls(self, trace_by_prefix):
        trace = trace_by_prefix(VISA)
        assert trace.tool_calls == []
        assert len(trace.llm_calls) == 1

    def test_token_totals_sum_across_llm_calls(self, trace_by_prefix):
        trace = trace_by_prefix(PARIS)
        assert len(trace.llm_calls) == 2
        assert trace.total_prompt_tokens == sum(
            c.prompt_tokens for c in trace.llm_calls
        )
        assert trace.total_prompt_tokens > 0
        assert trace.total_completion_tokens > 0

    def test_prior_context_carries_the_previous_turns_tool_results(
        self, trace_by_prefix
    ):
        """The Miami follow-up asks only for a hotel, but the reply cites the
        $189 JetBlue fare from the previous turn. Grounding is only correct
        because that fare rides in this turn's LLM input messages."""
        trace = trace_by_prefix(MIAMI_FOLLOWUP)
        context = trace.prior_context_text()
        assert "B6 1029" in context
        assert "189" in context

    def test_single_turn_trace_has_no_prior_tool_results(self, trace_by_prefix):
        context = trace_by_prefix(VISA).prior_context_text()
        assert "search_flights" not in context
        assert "flight_number" not in context


# --------------------------------------------------------------------------- #
# Edge cases the real export does not contain
# --------------------------------------------------------------------------- #
class TestLoadEdgeCases:
    def test_a_group_with_no_root_span_is_skipped_not_crashed(self, tmp_path):
        """Truncated exports happen. Dropping the incomplete trace is the
        documented behavior; raising would lose the whole run's scores."""
        spans = [
            span("0xaaa", "0x1", None, "agent_turn",
                 {"openinference.span.kind": "CHAIN", "input.value": "hi",
                  "output.value": "hello"}),
            # orphan: parent_id set, but the parent span is not in the export
            span("0xbbb", "0x2", "0x999", "search_flights",
                 {"openinference.span.kind": "TOOL", "tool.name": "search_flights",
                  "input.value": "{}", "output.value": "[]"}),
        ]
        traces = load_traces(write_spans(tmp_path / "s.jsonl", spans))
        assert [t.trace_id for t in traces] == ["0xaaa"]

    def test_malformed_tool_json_falls_back_to_the_raw_string(self, tmp_path):
        spans = [
            span("0xaaa", "0x1", None, "agent_turn",
                 {"openinference.span.kind": "CHAIN", "input.value": "hi",
                  "output.value": "hello"}),
            span("0xaaa", "0x2", "0x1", "search_flights",
                 {"openinference.span.kind": "TOOL", "tool.name": "search_flights",
                  "input.value": "not json", "output.value": "not json either"}),
        ]
        call = load_traces(write_spans(tmp_path / "s.jsonl", spans))[0].tool_calls[0]
        assert call.input == {}
        assert call.output == "not json either"

    def test_tool_error_attribute_is_surfaced(self, tmp_path):
        spans = [
            span("0xaaa", "0x1", None, "agent_turn",
                 {"openinference.span.kind": "CHAIN", "input.value": "hi",
                  "output.value": "hello"}),
            span("0xaaa", "0x2", "0x1", "get_weather",
                 {"openinference.span.kind": "TOOL", "tool.name": "get_weather",
                  "input.value": "{}", "output.value": '{"error": "boom"}',
                  "tool.error": "boom", "tool.result_empty": True}),
        ]
        call = load_traces(write_spans(tmp_path / "s.jsonl", spans))[0].tool_calls[0]
        assert call.error == "boom"
        assert call.result_empty is True

    def test_tool_calls_are_ordered_by_span_start_time(self, tmp_path):
        base = {"openinference.span.kind": "TOOL", "input.value": "{}",
                "output.value": "[]"}
        spans = [
            span("0xaaa", "0x1", None, "agent_turn",
                 {"openinference.span.kind": "CHAIN", "input.value": "hi",
                  "output.value": "hello"},
                 start="2026-07-19T10:00:00Z"),
            span("0xaaa", "0x3", "0x1", "second", {**base, "tool.name": "second"},
                 start="2026-07-19T10:00:02Z"),
            span("0xaaa", "0x2", "0x1", "first", {**base, "tool.name": "first"},
                 start="2026-07-19T10:00:01Z"),
        ]
        trace = load_traces(write_spans(tmp_path / "s.jsonl", spans))[0]
        assert [c.name for c in trace.tool_calls] == ["first", "second"]

    def test_missing_root_output_yields_an_empty_reply_not_none(self, tmp_path):
        spans = [span("0xaaa", "0x1", None, "agent_turn",
                      {"openinference.span.kind": "CHAIN", "input.value": "hi"})]
        assert load_traces(write_spans(tmp_path / "s.jsonl", spans))[0].reply == ""


class TestLlmInputMessageReconstruction:
    def test_flattened_role_and_content_are_rebuilt_in_index_order(self):
        attrs = {
            "llm.input_messages.1.message.role": "user",
            "llm.input_messages.1.message.content": "second",
            "llm.input_messages.0.message.role": "system",
            "llm.input_messages.0.message.content": "first",
        }
        assert _llm_input_messages(attrs) == [
            {"role": "system", "content": "first"},
            {"role": "user", "content": "second"},
        ]

    def test_block_structured_content_is_joined_into_one_string(self):
        attrs = {
            "llm.input_messages.0.message.role": "assistant",
            "llm.input_messages.0.message.contents.0.message_content.text": "alpha",
            "llm.input_messages.0.message.contents.1.message_content.text": "beta",
        }
        rebuilt = _llm_input_messages(attrs)
        assert rebuilt == [{"role": "assistant", "content": "alpha\nbeta"}]

    def test_non_message_attributes_are_ignored(self):
        attrs = {
            "llm.token_count.prompt": 10,
            "llm.input_messages.notanindex.message.role": "user",
            "llm.input_messages.0.message.role": "user",
            "llm.input_messages.0.message.content": "hi",
        }
        assert _llm_input_messages(attrs) == [{"role": "user", "content": "hi"}]

    def test_no_llm_attributes_yields_no_messages(self):
        assert _llm_input_messages({"openinference.span.kind": "TOOL"}) == []


class TestTraceViewDefaults:
    def test_a_bare_view_has_empty_collections_and_zero_totals(self):
        view = TraceView(trace_id="t", session_id=None, user_input="", reply="")
        assert view.tool_calls == []
        assert view.llm_calls == []
        assert view.total_prompt_tokens == 0
        assert view.total_completion_tokens == 0
        assert view.prior_context_text() == ""

    def test_views_do_not_share_mutable_defaults(self):
        a = TraceView(trace_id="a", session_id=None, user_input="", reply="")
        b = TraceView(trace_id="b", session_id=None, user_input="", reply="")
        assert a.tool_calls is not b.tool_calls


# --------------------------------------------------------------------------- #
# Offline eval smoke test: first failure per trace, and its attribution
# --------------------------------------------------------------------------- #
def all_evals() -> list:
    import evals.e_conflict as e_conflict
    import evals.e_grounding as e_grounding
    import evals.e_guardrails as e_guardrails
    import evals.e_toolcalls as e_toolcalls

    # Same module order as _EVAL_MODULES in evals/run_evals.py, so "first
    # failure" means the same thing here as it does in a real scoring run.
    return [
        *e_grounding.EVALS,
        *e_toolcalls.EVALS,
        *e_guardrails.EVALS,
        *e_conflict.EVALS,
    ]


def first_failure(trace, ctx):
    """The first eval that fails on this trace, in suite order, or None."""
    for fn in all_evals():
        result = fn(trace, ctx)
        if result is not None and not result["passed"]:
            return result
    return None


class TestOfflineEvalSmoke:
    def test_the_whole_suite_runs_on_committed_spans_without_credentials(
        self, traces, ctx
    ):
        """No ANTHROPIC_API_KEY, no network, no Arize. Every eval either returns
        the result contract or None."""
        seen = 0
        for trace in traces:
            for fn in all_evals():
                result = fn(trace, ctx)
                if result is None:
                    continue
                seen += 1
                assert set(result) >= {
                    "eval_id", "name", "passed", "reason", "attribution", "evidence"
                }
                assert isinstance(result["passed"], bool)
                assert result["attribution"] in {"tool", "model", "n/a"}
        assert seen > 0

    def test_the_only_failure_in_the_fixture_is_the_backwards_flight(
        self, traces, ctx
    ):
        failures = {
            t.user_input[:24]: first_failure(t, ctx)
            for t in traces
            if first_failure(t, ctx) is not None
        }
        assert list(failures) == ["I want to fly from Chica"]

    def test_first_failure_is_attributed_to_the_tool_not_the_model(
        self, trace_by_prefix, ctx
    ):
        """This is the attribution that drives the whole fix decision. The reply
        looks like a hallucinated flight, but search_flights handed the model a
        backwards row with the route fields stripped, so the fault is the tool's
        and the authorized fix is a tool change (D-02), not a prompt change."""
        result = first_failure(trace_by_prefix(CHICAGO_DENVER), ctx)
        assert result["eval_id"] == "E2"
        assert result["attribution"] == "tool"

    def test_a_passing_result_never_localizes_blame(self, traces, ctx):
        for trace in traces:
            for fn in all_evals():
                result = fn(trace, ctx)
                if result is not None and result["passed"]:
                    assert result["attribution"] == "n/a"

    @pytest.mark.parametrize(
        "prefix", [PARIS, MIAMI_FOLLOWUP, DENVER_MIAMI_EMPTY, VISA]
    )
    def test_no_other_fixture_trace_fails_any_eval(self, trace_by_prefix, ctx, prefix):
        assert first_failure(trace_by_prefix(prefix), ctx) is None
