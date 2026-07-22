"""E10 conflicting context: the most recent correction is the one that counts.

Luke asked for "some way to highlight the conflicting information". Within one
session, when a later user message supersedes a booking-material value, any
SUBSEQUENT tool call that still passes the old value is a conflict, attributed
to the model: the correction was in its context and it ignored it.

The slots evals/e_conflict.py actually implements are origin, place
(flight destination / hotel city / weather city / itinerary destination), and
date. There is no budget slot; see the handoff note.

Traces are built here rather than sampled because the captured baseline contains
no session where the user corrects themselves. Each one is assembled once from a
literal message list; nothing is mutated after construction.
"""

import pytest

from evals.e_conflict import e10_conflicting_context
from evals.trace_model import LlmCall, ToolCall, TraceView

FLIGHT = "search_flights"
HOTEL = "search_hotels"
WEATHER = "get_weather"


def tool_call(name: str, **params) -> ToolCall:
    return ToolCall(
        name=name,
        input=dict(params),
        output=[],
        result_count=0,
        result_empty=True,
        error=None,
    )


def session(user_messages, tool_calls, interleaved=()):
    """A TraceView for the last turn of a session.

    ``user_messages`` are the session's user utterances in order; the last is
    this turn. ``interleaved`` are extra raw message dicts (e.g. JSON tool-result
    user messages) spliced in after the first utterance, so the session
    reconstruction can be tested against realistic history.
    """
    head, *rest = user_messages
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": head},
        *interleaved,
        *({"role": "user", "content": m} for m in rest),
    ]
    return TraceView(
        trace_id="synthetic",
        session_id="session-1",
        user_input=user_messages[-1],
        reply="ok",
        tool_calls=list(tool_calls),
        llm_calls=[
            LlmCall(input_messages=messages, prompt_tokens=1, completion_tokens=1)
        ],
    )


def stale_values(result) -> list:
    return [c["stale_value"] for c in result["evidence"]["conflicts"]]


def corrections(result) -> list:
    return [
        (s["slot"], s["superseded"], s["corrected"])
        for s in result["evidence"]["supersessions"]
    ]


# --------------------------------------------------------------------------- #
# Applicability
# --------------------------------------------------------------------------- #
class TestApplicability:
    def test_a_single_turn_session_cannot_have_a_conflict(self):
        trace = session(
            ["Book a flight from Chicago to Denver on 2026-10-02."],
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
        )
        assert e10_conflicting_context(trace, None) is None

    def test_a_multi_turn_session_with_no_correction_passes(self, ctx):
        trace = session(
            [
                "Book a flight from Chicago to Denver on 2026-10-02.",
                "Great, can you add a hotel in Denver too?",
            ],
            [tool_call(HOTEL, city="Denver", check_in="2026-10-02",
                       check_out="2026-10-05")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert result["passed"]
        assert corrections(result) == []


# --------------------------------------------------------------------------- #
# Origin
# --------------------------------------------------------------------------- #
class TestOrigin:
    MESSAGES = [
        "Find me a flight from Chicago to Denver on 2026-10-02.",
        "Actually, I'm flying from New York instead.",
    ]

    def test_reusing_the_superseded_origin_fails_and_blames_the_model(self, ctx):
        trace = session(
            self.MESSAGES,
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert not result["passed"]
        assert result["attribution"] == "model"
        assert stale_values(result) == ["Chicago"]
        assert corrections(result) == [("origin", "Chicago", "New York")]

    def test_the_conflict_quotes_the_message_that_corrected_it(self, ctx):
        trace = session(
            self.MESSAGES,
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
        )
        conflict = e10_conflicting_context(trace, ctx)["evidence"]["conflicts"][0]
        assert conflict["quoting_message"] == self.MESSAGES[1]

    def test_using_the_corrected_origin_passes(self, ctx):
        trace = session(
            self.MESSAGES,
            [tool_call(FLIGHT, origin="New York", destination="Denver",
                       date="2026-10-02")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert result["passed"]
        assert corrections(result) == [("origin", "Chicago", "New York")]

    def test_destination_is_not_confused_with_origin(self, ctx):
        """"from X" makes X the origin; every other city named is a place. The
        destination is unchanged here, so nothing is superseded."""
        trace = session(
            [
                "Find me a flight from Chicago to Denver on 2026-10-02.",
                "Actually, I'm flying from New York instead.",
            ],
            [tool_call(FLIGHT, origin="New York", destination="Denver",
                       date="2026-10-02")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert [c[0] for c in corrections(result)] == ["origin"]


# --------------------------------------------------------------------------- #
# Most recent correction wins
# --------------------------------------------------------------------------- #
class TestMostRecentCorrectionWins:
    MESSAGES = [
        "Find me a flight from Chicago to Denver on 2026-10-02.",
        "Actually, I'm flying from New York instead.",
        "No wait, from Miami instead.",
    ]

    def _run(self, ctx, origin):
        trace = session(
            self.MESSAGES,
            [tool_call(FLIGHT, origin=origin, destination="Denver",
                       date="2026-10-02")],
        )
        return e10_conflicting_context(trace, ctx)

    def test_both_corrections_are_recorded_in_order(self, ctx):
        assert corrections(self._run(ctx, "Miami")) == [
            ("origin", "Chicago", "New York"),
            ("origin", "New York", "Miami"),
        ]

    def test_only_the_latest_value_passes(self, ctx):
        assert self._run(ctx, "Miami")["passed"]

    @pytest.mark.parametrize("origin", ["Chicago", "New York"])
    def test_every_earlier_value_is_stale_including_the_intermediate_one(
        self, ctx, origin
    ):
        """The intermediate value is the interesting case: "New York" was correct
        for one turn, and a rule that only remembered the original request would
        wave it through."""
        result = self._run(ctx, origin)
        assert not result["passed"]
        assert stale_values(result) == [origin]


# --------------------------------------------------------------------------- #
# Place (destination / hotel city / weather city)
# --------------------------------------------------------------------------- #
class TestPlace:
    MESSAGES = [
        "I need a hotel in Paris from 2026-06-10 to 2026-06-14.",
        "Actually, change it to London.",
    ]

    def test_reusing_the_superseded_city_fails(self, ctx):
        trace = session(
            self.MESSAGES,
            [tool_call(HOTEL, city="Paris", check_in="2026-06-10",
                       check_out="2026-06-14")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert not result["passed"]
        assert stale_values(result) == ["Paris"]
        assert corrections(result) == [("place", "Paris", "London")]

    def test_the_place_slot_spans_every_tool_that_names_a_destination(self, ctx):
        """A stale city is a conflict wherever it lands: hotel city, weather
        city, flight destination, itinerary destination."""
        trace = session(
            self.MESSAGES,
            [
                tool_call(HOTEL, city="Paris", check_in="2026-06-10",
                          check_out="2026-06-14"),
                tool_call(WEATHER, city="Paris", date="2026-06-10"),
            ],
        )
        conflicts = e10_conflicting_context(trace, ctx)["evidence"]["conflicts"]
        assert [(c["tool"], c["param"]) for c in conflicts] == [
            (HOTEL, "city"),
            (WEATHER, "city"),
        ]

    def test_using_the_corrected_city_passes(self, ctx):
        trace = session(
            self.MESSAGES,
            [tool_call(HOTEL, city="London", check_in="2026-06-10",
                       check_out="2026-06-14")],
        )
        assert e10_conflicting_context(trace, ctx)["passed"]


# --------------------------------------------------------------------------- #
# Date
# --------------------------------------------------------------------------- #
class TestDate:
    def test_a_cued_change_to_the_only_established_date_is_caught(self, ctx):
        trace = session(
            [
                "Book a flight from Chicago to Denver on 2026-10-02.",
                "Actually, change it to 2026-10-05.",
            ],
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert not result["passed"]
        assert stale_values(result) == ["2026-10-02"]
        assert corrections(result) == [("date", "2026-10-02", "2026-10-05")]

    def test_month_name_dates_are_understood(self, ctx):
        trace = session(
            [
                "Book a flight from Chicago to Denver on October 2, 2026.",
                "Actually, make it October 5, 2026.",
            ],
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
        )
        assert not e10_conflicting_context(trace, ctx)["passed"]

    def test_using_the_corrected_date_passes(self, ctx):
        trace = session(
            [
                "Book a flight from Chicago to Denver on 2026-10-02.",
                "Actually, change it to 2026-10-05.",
            ],
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-05")],
        )
        assert e10_conflicting_context(trace, ctx)["passed"]

    def test_instead_of_names_the_old_date_explicitly(self, ctx):
        """With two dates on the table, the "instead of <old date>" form is what
        disambiguates which one was replaced."""
        trace = session(
            [
                "I need a hotel in Paris from 2026-06-10 to 2026-06-14.",
                "Make the check-in 2026-06-12 instead of 2026-06-10.",
            ],
            [tool_call(HOTEL, city="Paris", check_in="2026-06-10",
                       check_out="2026-06-14")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert not result["passed"]
        assert [c["param"] for c in result["evidence"]["conflicts"]] == ["check_in"]

    def test_an_additional_date_without_a_cue_is_not_a_correction(self, ctx):
        """A trip carries several dates. Treating every new date as a
        replacement would flag ordinary multi-date planning."""
        trace = session(
            [
                "Book a flight from Chicago to Denver on 2026-10-02.",
                "Also, what is the weather on 2026-10-05?",
            ],
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert result["passed"]
        assert corrections(result) == []

    def test_known_gap_a_cue_alone_misses_when_two_dates_are_established(self, ctx):
        """PINNED LIMITATION, not a contract. evals/e_conflict.py only accepts a
        bare cue when exactly one date is established, so a cued check-in change
        on a hotel stay (two dates) is a false negative. Recorded as a handoff
        note rather than fixed here: E10 is not in the two authorized changes,
        and loosening it risks false positives on additive multi-date turns."""
        trace = session(
            [
                "I need a hotel in Paris from 2026-06-10 to 2026-06-14.",
                "Actually, change the check-in to 2026-06-12.",
            ],
            [tool_call(HOTEL, city="Paris", check_in="2026-06-10",
                       check_out="2026-06-14")],
        )
        result = e10_conflicting_context(trace, ctx)
        assert result["passed"]
        assert corrections(result) == []


# --------------------------------------------------------------------------- #
# Session reconstruction
# --------------------------------------------------------------------------- #
class TestSessionReconstruction:
    def test_json_tool_result_messages_are_not_treated_as_user_turns(self, ctx):
        """Tool results are appended with role "user". If they counted as
        utterances, a city inside a tool payload could fabricate a correction."""
        trace = session(
            [
                "Book a flight from Chicago to Denver on 2026-10-02.",
                "Actually, from New York instead.",
            ],
            [tool_call(FLIGHT, origin="Chicago", destination="Denver",
                       date="2026-10-02")],
            interleaved=[
                {
                    "role": "user",
                    "content": '[{"flight_number": "UA 2044", "origin": "Miami"}]',
                }
            ],
        )
        result = e10_conflicting_context(trace, ctx)
        assert result["evidence"]["session_turns"] == 2
        assert corrections(result) == [("origin", "Chicago", "New York")]

    def test_the_real_multi_turn_baseline_trace_has_no_conflict(
        self, trace_by_prefix, ctx
    ):
        """End-to-end on real spans: the Miami follow-up is a genuine two-turn
        session and the model carried the context forward correctly."""
        trace = trace_by_prefix("Great, can you add a hotel")
        result = e10_conflicting_context(trace, ctx)
        assert result is not None
        assert result["passed"], result["reason"]
