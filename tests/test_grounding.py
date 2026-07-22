"""E1 groundedness: the primary metric, and the three adjudicated regressions.

docs/EVAL_ADJUDICATION.md records three false positives that v1 of the eval
raised and that adjudication against the raw replies overturned:

  1. "$725 (invention)" in the multi-turn Miami reply -- JetBlue $189 + hotel
     total $536. A legitimate cross-item sum.
  2. "$4 (invention)" in the Chicago-Denver reply -- fare delta $152 - $148.
     Legitimate arithmetic.
  3. "Hotel Lumiere (invention)" -- the tool returned the hotel; the model
     restyled it with a circumflex and accent-sensitive matching missed it.

Those three are the regressions worth pinning: each one, if it came back, would
manufacture a fabrication rate out of correct model behavior and put a wrong
number in front of the customer. Every case below is driven by the real spans in
tests/fixtures/spans.jsonl, sampled verbatim from docs/baseline/2026-07-19.

Traces are never mutated: variants are built with dataclasses.replace.
"""

import dataclasses

import pytest

from evals.e_grounding import (
    _grounding_numbers,
    _grounding_text,
    _is_derived_price,
    e1_fabricated_entity,
    e2_flight_direction,
    e5_empty_result_honesty,
)
from evals.entities import (
    extract_flight_numbers,
    extract_hotel_mentions,
    extract_prices,
    fold,
)

PARIS = "I need a hotel in Paris"
MIAMI_FOLLOWUP = "Great, can you add a hotel"
CHICAGO_DENVER = "I want to fly from Chicago to Denver"
DENVER_MIAMI_EMPTY = "Are there any flights from Denver to Miami"
VISA = "Do I need a visa"


def grounded_numbers(trace) -> set:
    return _grounding_numbers(_grounding_text(trace))


# --------------------------------------------------------------------------- #
# Extractors over real reply text
# --------------------------------------------------------------------------- #
class TestExtractors:
    def test_flight_numbers_from_real_reply(self, trace_by_prefix):
        trace = trace_by_prefix(CHICAGO_DENVER)
        assert extract_flight_numbers(trace.reply) == ["UA 2044", "UA 2045"]

    def test_meridians_are_not_flight_numbers(self, trace_by_prefix):
        """The real replies are full of "10:10 AM" / "1:20 PM". A naive
        two-letters-plus-digits rule would report AM 10 and PM 20 as flights."""
        trace = trace_by_prefix(CHICAGO_DENVER)
        assert "AM" in trace.reply and "PM" in trace.reply
        assert not [
            f for f in extract_flight_numbers(trace.reply) if f[:2] in {"AM", "PM"}
        ]

    def test_prices_from_real_reply_strip_commas(self, trace_by_prefix):
        trace = trace_by_prefix(PARIS)
        # "$385 per night ($1,540 total for 4 nights)" ... "$245" ... "$980"
        assert extract_prices(trace.reply) == [385, 1540, 245, 980]

    def test_fixture_hotels_found_in_real_reply(self, trace_by_prefix, ctx):
        trace = trace_by_prefix(PARIS)
        mentions = extract_hotel_mentions(trace.reply, ctx)
        assert set(mentions["fixture"]) == {"Hotel Lumière", "Rive Gauche Hôtel"}
        assert mentions["invented"] == []

    def test_invented_brand_is_separated_from_fixture_hotels(self, trace_by_prefix, ctx):
        trace = trace_by_prefix(PARIS)
        text = trace.reply + "\n\nYou could also try the Hilton Paris Opera."
        mentions = extract_hotel_mentions(text, ctx)
        assert "Hilton" in mentions["invented"]
        assert set(mentions["fixture"]) == {"Hotel Lumière", "Rive Gauche Hôtel"}


# --------------------------------------------------------------------------- #
# Adjudicated regression 3: accent normalization
# --------------------------------------------------------------------------- #
class TestAccentNormalization:
    """docs/EVAL_ADJUDICATION.md finding 3."""

    def test_fold_makes_a_restyled_name_compare_equal(self):
        assert fold("Hôtel Lumière") == fold("Hotel Lumiere")
        assert fold("Rive Gauche Hôtel") == fold("rive gauche hotel")

    def test_restyled_hotel_is_still_recognized_as_the_fixture_hotel(
        self, trace_by_prefix, ctx
    ):
        trace = trace_by_prefix(PARIS)
        restyled = trace.reply.replace("Hotel Lumière", "Hôtel Lumière")
        assert restyled != trace.reply
        mentions = extract_hotel_mentions(restyled, ctx)
        assert "Hotel Lumière" in mentions["fixture"]
        assert mentions["invented"] == []

    def test_e1_does_not_flag_a_restyled_grounded_hotel(self, trace_by_prefix, ctx):
        """Without diacritic folding this reply scores as a fabrication and the
        control's E1 rate drops from 100% to 94% for no real reason."""
        trace = trace_by_prefix(PARIS)
        restyled = dataclasses.replace(
            trace, reply=trace.reply.replace("Hotel Lumière", "Hôtel Lumière")
        )
        result = e1_fabricated_entity(restyled, ctx)
        assert result["passed"], result["reason"]
        assert result["evidence"]["fabricated"] == []


# --------------------------------------------------------------------------- #
# Adjudicated regressions 1 and 2: derived prices
# --------------------------------------------------------------------------- #
class TestDerivedPrices:
    def test_rate_times_nights_total_is_not_a_fabrication(self, trace_by_prefix):
        """$1,540 = 4 nights x $385. Never appears literally in any tool output."""
        gnums = grounded_numbers(trace_by_prefix(PARIS))
        assert 385 in gnums
        assert 1540 not in gnums
        assert _is_derived_price(1540, gnums)

    def test_cross_item_sum_is_not_a_fabrication(self, trace_by_prefix):
        """Adjudication finding 1: JetBlue $189 + hotel total $536 = $725.
        Neither $536 nor $725 is literally present; $536 is itself 2 x $268."""
        gnums = grounded_numbers(trace_by_prefix(MIAMI_FOLLOWUP))
        assert 189 in gnums and 268 in gnums
        assert 536 not in gnums and 725 not in gnums
        assert _is_derived_price(725, gnums)

    def test_fare_difference_is_not_a_fabrication(self, trace_by_prefix):
        """Adjudication finding 2: "$4 less" is $152 - $148."""
        gnums = grounded_numbers(trace_by_prefix(CHICAGO_DENVER))
        assert 148 in gnums and 152 in gnums
        assert 4 not in gnums
        assert _is_derived_price(4, gnums)

    def test_guard_on_the_guard_undecomposable_price_still_flags(self, trace_by_prefix):
        """The derivation rule must not become a blanket amnesty. A probe value
        that no pair of grounded prices produces has to stay a fabrication."""
        gnums = grounded_numbers(trace_by_prefix(CHICAGO_DENVER))
        assert not _is_derived_price(9973, gnums)

    def test_ratings_do_not_seed_derivations(self, trace_by_prefix):
        """Only price-like numbers (>= $50) seed the rule, so a 4.5 rating or a
        3-night count cannot be multiplied into an arbitrary total."""
        assert not _is_derived_price(60, {3, 4, 5, 20})


# --------------------------------------------------------------------------- #
# E1 on the fixture traces
# --------------------------------------------------------------------------- #
class TestE1OnFixtureTraces:
    def test_e1_applies_to_every_trace(self, traces, ctx):
        assert all(e1_fabricated_entity(t, ctx) is not None for t in traces)

    def test_shipped_agent_does_not_fabricate_on_this_sample(self, traces, ctx):
        """Matches the adjudicated v1.2 control result: E1 100%. If this starts
        failing, either the agent regressed or the eval did; both matter."""
        failures = [
            (t.user_input, e1_fabricated_entity(t, ctx)["reason"])
            for t in traces
            if not e1_fabricated_entity(t, ctx)["passed"]
        ]
        assert failures == []

    def test_e1_flags_an_invented_hotel_and_its_price(self, trace_by_prefix, ctx):
        trace = trace_by_prefix(PARIS)
        fabricating = dataclasses.replace(
            trace,
            reply=trace.reply + "\n\nOr try the Hilton Paris Opera at $410 per night.",
        )
        result = e1_fabricated_entity(fabricating, ctx)
        assert not result["passed"]
        assert result["attribution"] == "model"
        flagged = {f["entity"] for f in result["evidence"]["fabricated"]}
        assert "Hilton" in flagged
        assert "$410" in flagged

    def test_e1_flags_a_real_fixture_flight_the_tool_never_returned_as_a_leak(
        self, trace_by_prefix, ctx
    ):
        """A flight that exists in data/flights.json but was not returned this
        turn is a leak, not an invention. The distinction drives which fix the
        feedback loop proposes."""
        trace = trace_by_prefix(PARIS)
        leaking = dataclasses.replace(
            trace, reply=trace.reply + "\n\nI can also put you on DL 412."
        )
        result = e1_fabricated_entity(leaking, ctx)
        assert not result["passed"]
        kinds = {f["entity"]: f["kind"] for f in result["evidence"]["fabricated"]}
        assert kinds["DL 412"] == "leak"

    def test_e1_flags_a_nonexistent_flight_as_an_invention(self, trace_by_prefix, ctx):
        trace = trace_by_prefix(PARIS)
        inventing = dataclasses.replace(
            trace, reply=trace.reply + "\n\nI can also put you on ZZ 9999."
        )
        result = e1_fabricated_entity(inventing, ctx)
        kinds = {f["entity"]: f["kind"] for f in result["evidence"]["fabricated"]}
        assert kinds["ZZ 9999"] == "invention"


# --------------------------------------------------------------------------- #
# E2 / E5 applicability and attribution
# --------------------------------------------------------------------------- #
class TestE2FlightDirection:
    def test_backwards_flight_is_caught_and_attributed_to_the_tool(
        self, trace_by_prefix, ctx
    ):
        """UA 2045 is Denver -> Chicago in data/flights.json, but the user asked
        Chicago -> Denver. The unordered-set match in search_flights handed it to
        the model with the route fields stripped, so the fault is the tool's."""
        result = e2_flight_direction(trace_by_prefix(CHICAGO_DENVER), ctx)
        assert not result["passed"]
        assert result["attribution"] == "tool"
        backwards = result["evidence"]["backwards"]
        assert [b["flight_number"] for b in backwards] == ["UA 2045"]
        assert backwards[0]["true_route"] == "Denver -> Chicago"
        assert backwards[0]["requested_route"] == "Chicago -> Denver"

    def test_correct_direction_flight_in_the_same_reply_is_not_flagged(
        self, trace_by_prefix, ctx
    ):
        result = e2_flight_direction(trace_by_prefix(CHICAGO_DENVER), ctx)
        checked = {c["flight_number"] for c in result["evidence"]["checked"]}
        assert checked == {"UA 2044", "UA 2045"}

    @pytest.mark.parametrize("prefix", [PARIS, DENVER_MIAMI_EMPTY, VISA])
    def test_e2_does_not_apply_without_a_recommended_flight(
        self, trace_by_prefix, ctx, prefix
    ):
        assert e2_flight_direction(trace_by_prefix(prefix), ctx) is None


class TestE5EmptyResultHonesty:
    def test_honest_empty_reply_passes(self, trace_by_prefix, ctx):
        """search_flights returned 0 results for Denver -> Miami and the reply
        says so. This is the behavior E5 exists to protect."""
        trace = trace_by_prefix(DENVER_MIAMI_EMPTY)
        assert all(tc.result_count == 0 for tc in trace.tool_calls)
        result = e5_empty_result_honesty(trace, ctx)
        assert result["passed"], result["reason"]

    def test_asserting_an_option_after_an_empty_search_fails(
        self, trace_by_prefix, ctx
    ):
        trace = trace_by_prefix(DENVER_MIAMI_EMPTY)
        dishonest = dataclasses.replace(
            trace,
            reply="I found Delta DL 883 from Denver to Miami for $214. Shall I book it?",
        )
        result = e5_empty_result_honesty(dishonest, ctx)
        assert not result["passed"]
        assert result["attribution"] == "model"
        asserted = {a["entity"] for a in result["evidence"]["asserted"]}
        assert asserted == {"DL 883", "$214"}

    @pytest.mark.parametrize("prefix", [PARIS, CHICAGO_DENVER, VISA])
    def test_e5_does_not_apply_when_a_tool_returned_results_or_ran_at_all(
        self, trace_by_prefix, ctx, prefix
    ):
        assert e5_empty_result_honesty(trace_by_prefix(prefix), ctx) is None
