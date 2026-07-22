"""agent/tools.py: the tool layer, including the bugs that are deliberately
still shipped.

Two kinds of test live here and they must not be confused:

  * CONTRACT tests -- behavior the system is supposed to have.
  * PINNED-BUG tests -- behavior that is wrong, is known to be wrong, is recorded
    in docs/REPO_FINDINGS.md, and is intentionally left unfixed so the baseline
    stays the baseline. These assert the WRONG value on purpose. Each one says so
    in its docstring. If one of them starts failing, someone fixed a bug without
    re-capturing the baseline, and the before/after story stops being valid.

search_flights is the one bug with an authorized fix, gated behind
FLIGHT_TOOL_FIX=1. Both sides of that gate are asserted explicitly: buggy when
the flag is off (the shipped default), correct when it is on.

No test here reaches the network or the model. agent.tools reads JSON from data/.
"""

import pytest

from agent.tools import (
    TOOL_FUNCTIONS,
    create_itinerary,
    execute_tool,
    get_weather,
    search_flights,
    search_hotels,
)

# data/flights.json: UA 2044 is Chicago -> Denver, UA 2045 is Denver -> Chicago.
CHI_TO_DEN = "UA 2044"
DEN_TO_CHI = "UA 2045"


def numbers(rows) -> list:
    return [r["flight_number"] for r in rows]


# --------------------------------------------------------------------------- #
# search_flights: the shipped bug, and the gated fix
# --------------------------------------------------------------------------- #
class TestSearchFlightsShippedDefault:
    """FLIGHT_TOOL_FIX unset. This is what the baseline ran."""

    def test_direction_is_ignored_both_ways_return_the_same_rows(self):
        """PINNED BUG (D-02): origin/destination are compared as an unordered
        set, so a Chicago -> Denver search and a Denver -> Chicago search return
        an identical list containing both directions."""
        forward = search_flights("Chicago", "Denver", "2026-10-02")
        backward = search_flights("Denver", "Chicago", "2026-10-02")
        assert numbers(forward) == [CHI_TO_DEN, DEN_TO_CHI]
        assert forward == backward

    def test_route_fields_are_stripped_from_the_payload(self):
        """PINNED BUG (D-02): because origin/destination never reach the model,
        it cannot detect that one of the rows runs the wrong way. This is why
        E2's attribution is "tool" and not "model"."""
        rows = search_flights("Chicago", "Denver", "2026-10-02")
        assert rows
        for row in rows:
            assert "origin" not in row
            assert "destination" not in row

    def test_matching_is_case_insensitive(self):
        assert search_flights("chicago", "DENVER", "2026-10-02") == search_flights(
            "Chicago", "Denver", "2026-10-02"
        )


class TestSearchFlightsWithFix:
    """FLIGHT_TOOL_FIX=1. Candidate B, the authorized change."""

    @pytest.fixture(autouse=True)
    def enable_fix(self, monkeypatch):
        monkeypatch.setenv("FLIGHT_TOOL_FIX", "1")

    def test_only_the_requested_direction_is_returned(self):
        assert numbers(search_flights("Chicago", "Denver", "2026-10-02")) == [CHI_TO_DEN]
        assert numbers(search_flights("Denver", "Chicago", "2026-10-02")) == [DEN_TO_CHI]

    def test_route_fields_are_exposed_so_the_model_can_verify(self):
        rows = search_flights("Chicago", "Denver", "2026-10-02")
        assert rows[0]["origin"] == "Chicago"
        assert rows[0]["destination"] == "Denver"

    def test_matching_is_case_insensitive(self):
        assert numbers(search_flights("chicago", "DENVER", "2026-10-02")) == [CHI_TO_DEN]

    def test_the_fix_is_opt_in_only(self, monkeypatch):
        """Anything other than exactly "1" leaves the shipped behavior alone, so
        the default stays byte-identical to what the baseline measured."""
        for value in ("0", "", "true", "yes"):
            monkeypatch.setenv("FLIGHT_TOOL_FIX", value)
            assert numbers(search_flights("Chicago", "Denver", "2026-10-02")) == [
                CHI_TO_DEN,
                DEN_TO_CHI,
            ]


class TestEmptyResultsAreHonest:
    """A search with no inventory returns an empty list. It never substitutes a
    near miss, and it never errors. E5 depends on this."""

    @pytest.mark.parametrize("fix", ["off", "on"])
    def test_no_flights_on_an_unserved_route(self, monkeypatch, fix):
        if fix == "on":
            monkeypatch.setenv("FLIGHT_TOOL_FIX", "1")
        assert search_flights("Denver", "Miami", "2026-08-14") == []

    def test_no_hotels_in_an_uncovered_city(self):
        assert search_hotels("Denver", "2026-08-07", "2026-08-09") == []

    def test_unknown_city_flights_return_empty_not_an_error(self):
        assert search_flights("Atlantis", "Narnia", "2026-01-01") == []


# --------------------------------------------------------------------------- #
# Other shipped bugs: pinned, not fixed
# --------------------------------------------------------------------------- #
class TestPinnedShippedBugs:
    def test_search_flights_ignores_the_date(self):
        """PINNED BUG: `date` is accepted and never used, so an impossible date
        still returns a full result set. The model has no way to know."""
        assert search_flights("Chicago", "Denver", "not-a-date") == search_flights(
            "Chicago", "Denver", "2026-10-02"
        )

    def test_search_hotels_ignores_check_out(self):
        """PINNED BUG: only check_in is range-checked. Le Marais Boutique is
        available_to 2026-04-05 yet is returned for a 2026-04-07 check-out."""
        rows = search_hotels("Paris", "2026-04-03", "2026-04-07")
        assert "Le Marais Boutique" in [r["name"] for r in rows]

    def test_create_itinerary_is_off_by_one(self):
        """PINNED BUG: range(1, num_days) drops the last day, so a 3-day trip
        comes back with 2 days."""
        result = create_itinerary("Chicago", 3)
        assert result["num_days"] == 3
        assert [d["day"] for d in result["days"]] == [1, 2]

    def test_get_weather_applies_a_celsius_conversion_to_fahrenheit(self):
        """PINNED BUG: data/weather.json stores Miami at high_f 86, already
        Fahrenheit, but get_weather runs it through `v * 5 / 9 + 32` anyway. The
        reported high lands in the 70s-80s and looks plausible, which is exactly
        why it survived. Asserting the raw fixture is untouched would be the
        contract; this asserts the wrong value that the baseline actually
        produced."""
        reported = get_weather("Miami", "2026-07-15")
        assert reported["high_f"] == 80  # not 86, and not 84-88
        assert reported["low_f"] == 73  # not 74

    def test_get_weather_is_deterministic_for_a_given_date(self):
        assert get_weather("Miami", "2026-07-15") == get_weather("Miami", "2026-07-15")


# --------------------------------------------------------------------------- #
# execute_tool: error handling
# --------------------------------------------------------------------------- #
class TestExecuteToolErrorHandling:
    def test_unknown_tool_name_returns_an_error_dict_not_a_raise(self):
        result = execute_tool("no_such_tool", {})
        assert isinstance(result, dict)
        assert "no_such_tool" in result["error"]

    def test_missing_arguments_return_an_error_dict(self):
        result = execute_tool("search_flights", {"origin": "Chicago"})
        assert "missing" in result["error"]
        assert "destination" in result["error"]

    def test_tool_level_error_is_passed_through(self):
        result = execute_tool("get_weather", {"city": "Atlantis", "date": "2026-07-15"})
        assert result == {"error": "No weather data available for Atlantis"}

    def test_an_arbitrary_exception_is_captured_as_an_error_string(self, monkeypatch):
        def boom(**_kwargs):
            raise ValueError("upstream schema changed")

        monkeypatch.setitem(TOOL_FUNCTIONS, "search_hotels", boom)
        result = execute_tool("search_hotels", {"city": "Paris"})
        assert result == {"error": "upstream schema changed"}

    def test_a_transient_error_is_retried_then_reported(self, monkeypatch):
        """Transient network-shaped failures retry up to TOOL_MAX_RETRIES and
        then return an error dict, so a flaky tool degrades instead of killing
        the turn."""
        calls = []

        def flaky(**_kwargs):
            calls.append(1)
            raise ConnectionError("connection reset")

        monkeypatch.setitem(TOOL_FUNCTIONS, "search_hotels", flaky)
        monkeypatch.setenv("TOOL_MAX_RETRIES", "3")
        monkeypatch.setenv("TOOL_RETRY_BASE_SECONDS", "0")

        result = execute_tool("search_hotels", {"city": "Paris"})
        assert len(calls) == 3
        assert "temporarily unavailable after 3 attempts" in result["error"]

    def test_a_transient_error_that_clears_returns_the_real_result(self, monkeypatch):
        calls = []

        def flaky(**kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise TimeoutError("read timed out")
            return search_hotels(**kwargs)

        monkeypatch.setitem(TOOL_FUNCTIONS, "search_hotels", flaky)
        monkeypatch.setenv("TOOL_MAX_RETRIES", "3")
        monkeypatch.setenv("TOOL_RETRY_BASE_SECONDS", "0")

        result = execute_tool(
            "search_hotels",
            {"city": "Paris", "check_in": "2026-06-10", "check_out": "2026-06-14"},
        )
        assert len(calls) == 2
        assert [r["name"] for r in result] == ["Hotel Lumière", "Rive Gauche Hôtel"]
