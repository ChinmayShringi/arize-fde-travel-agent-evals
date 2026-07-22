"""Tool-call evals: input validity (E3) and itinerary day count (E4).

E3 validates the INPUT the model constructed for every tool call in a trace.
E4 checks that create_itinerary delivered the number of days requested.

Both read only the TraceView; E3 pulls the tool schema (required params) from
agent.tools.TOOLS as the source of truth. Deterministic: no LLM, no clock, no
randomness. Each eval returns the result-dict contract from evals/context.py,
or None when it does not apply to the trace.
"""

import re
from datetime import datetime

from agent.tools import TOOLS

# Params whose value must be a calendar date in strict YYYY-MM-DD form. Named
# consistently across tools (search_flights.date, search_hotels.check_in/out,
# get_weather.date), so detection is by param name, not tool name.
DATE_PARAMS = ("date", "check_in", "check_out")

# City-bearing params per tool, checked against the closed fixture coverage set.
# A city outside coverage is a DATA gap (D-07), not a model error, so it is only
# noted in evidence, never a failure.
_COVERAGE_PARAMS = {
    "search_flights": ("origin", "destination"),
    "search_hotels": ("city",),
    "get_weather": ("city",),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Required-param lists straight from the tool schema (source of truth).
_REQUIRED = {
    t["name"]: tuple(t.get("input_schema", {}).get("required", [])) for t in TOOLS
}


def _parses_as_iso_date(value) -> bool:
    """True only for a strict, zero-padded YYYY-MM-DD string naming a real date.
    Relative/free-text dates ("next Friday", "this weekend") fail here: the agent
    has no current-date anchor to resolve them (REPO_FINDINGS D-09)."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _is_positive_int(value) -> bool:
    """num_days must be a positive integer. bool is rejected (it subclasses int);
    an all-digit string is accepted since JSON encoding may deliver it as text."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.isdigit() and int(value) > 0
    return False


def _coverage_set(ctx, tool_name: str, param: str) -> frozenset:
    if tool_name == "get_weather":
        return frozenset(c.lower() for c in ctx.weather_cities)
    if tool_name == "search_hotels":
        return frozenset(c.lower() for c in ctx.hotel_cities)
    if tool_name == "search_flights":
        return frozenset(c.lower() for c in ctx.flight_cities)
    return frozenset()


def e3_tool_call_validity(trace, ctx):
    """Every tool-call input must be well-formed: date params parse as strict
    YYYY-MM-DD, required params present, num_days a positive int, check_out after
    check_in. Fault is the MODEL (it formed the call). One result per trace."""
    if not trace.tool_calls:
        return None

    violations = []
    coverage_gaps = []

    for call in trace.tool_calls:
        name = call.name
        params = call.input if isinstance(call.input, dict) else {}

        # (b) required params present per schema
        for req in _REQUIRED.get(name, ()):
            if req not in params or params[req] is None:
                violations.append(
                    {"tool": name, "param": req, "issue": "missing_required"}
                )

        # (a) date-bearing params parse as YYYY-MM-DD
        for dparam in DATE_PARAMS:
            if dparam in params and params[dparam] is not None:
                if not _parses_as_iso_date(params[dparam]):
                    violations.append(
                        {
                            "tool": name,
                            "param": dparam,
                            "issue": "not_iso_date",
                            "value": params[dparam],
                        }
                    )

        # (c) num_days is a positive integer
        if "num_days" in params and not _is_positive_int(params["num_days"]):
            violations.append(
                {
                    "tool": name,
                    "param": "num_days",
                    "issue": "not_positive_int",
                    "value": params["num_days"],
                }
            )

        # (d) check_out strictly after check_in when both parse
        ci, co = params.get("check_in"), params.get("check_out")
        if _parses_as_iso_date(ci) and _parses_as_iso_date(co) and not (co > ci):
            violations.append(
                {
                    "tool": name,
                    "param": "check_out",
                    "issue": "check_out_not_after_check_in",
                    "value": {"check_in": ci, "check_out": co},
                }
            )

        # coverage note (NOT a failure): city outside the closed fixture set
        for cparam in _COVERAGE_PARAMS.get(name, ()):
            city = params.get(cparam)
            if isinstance(city, str) and city:
                if city.lower() not in _coverage_set(ctx, name, cparam):
                    coverage_gaps.append(
                        {"tool": name, "param": cparam, "city": city}
                    )

    passed = not violations
    if passed:
        reason = f"All {len(trace.tool_calls)} tool call input(s) are well-formed."
    else:
        parts = [f"{v['tool']}.{v['param']} ({v['issue']})" for v in violations]
        reason = f"{len(violations)} invalid tool call input(s): " + "; ".join(parts)

    return {
        "eval_id": "E3",
        "name": "tool_call_validity",
        "passed": passed,
        "reason": reason,
        "attribution": "model" if not passed else "n/a",
        "evidence": {
            "calls_checked": len(trace.tool_calls),
            "violations": violations,
            "coverage_gaps": coverage_gaps,
        },
    }


def e4_itinerary_day_count(trace, ctx):
    """create_itinerary must deliver len(days) == requested num_days. The D-05
    off-by-one (tools.py range(1, num_days)) delivers one day short. Fault is the
    TOOL. Applies only when create_itinerary was called."""
    calls = [c for c in trace.tool_calls if c.name == "create_itinerary"]
    if not calls:
        return None

    mismatches = []
    checked = []
    for call in calls:
        params = call.input if isinstance(call.input, dict) else {}
        output = call.output if isinstance(call.output, dict) else {}

        requested = params.get("num_days")
        if requested is None:
            requested = output.get("num_days")
        try:
            requested = int(requested)
        except (TypeError, ValueError):
            requested = None

        days = output.get("days")
        delivered = len(days) if isinstance(days, list) else None

        record = {"requested": requested, "delivered": delivered}
        checked.append(record)
        if requested is None or delivered is None or delivered != requested:
            mismatches.append(record)

    passed = not mismatches
    if passed:
        reason = (
            f"create_itinerary delivered the requested day count "
            f"({checked[0]['requested']} day(s))."
        )
    else:
        m = mismatches[0]
        reason = (
            f"create_itinerary requested {m['requested']} day(s) but delivered "
            f"{m['delivered']}."
        )

    return {
        "eval_id": "E4",
        "name": "itinerary_day_count",
        "passed": passed,
        "reason": reason,
        "attribution": "tool" if not passed else "n/a",
        "evidence": {"itineraries": checked, "mismatches": mismatches},
    }


EVALS = [e3_tool_call_validity, e4_itinerary_day_count]
