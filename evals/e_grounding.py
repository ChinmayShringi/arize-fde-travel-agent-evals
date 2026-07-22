"""Groundedness evals: does the reply only name options the tools returned, and
in the right direction?

E1 fabricated_entity  (PRIMARY metric) -- an option named in the reply that no
                       tool returned this turn and no prior turn returned.
                       Attribution "model": the model invented or leaked it.
E2 flight_direction  -- a recommended flight whose true route is the reverse of
                       what the user asked for. Attribution "tool": search_flights
                       matches origin/destination as an unordered set and strips
                       the direction fields, so the model cannot detect the error.
E5 empty_result_honesty -- every tool call came back empty/errored, yet the reply
                       still asserts a concrete bookable option. Attribution
                       "model": the model manufactured an answer.

Each callable returns the context.py result dict, or None when it does not apply.
Pure functions of (TraceView, EvalContext); no I/O, no clock, no randomness.
"""

import json
import re

from evals.entities import (
    FLIGHT_RE,
    PRICE_RE,
    extract_flight_numbers,
    extract_hotel_mentions,
    fold,
)

# A grounding number below this is a rating/day-count, not a per-unit price; only
# numbers at or above it seed the "total = rate x nights" derived-price check.
_MIN_RATE = 50
# Largest multiplier treated as a plausible night/day count for derived totals.
_MAX_NIGHTS = 30
# Max characters between an option name and a price for the price to count as
# "attached" to that option.
_ATTACH_WINDOW = 120

_NUMBER_RE = re.compile(r"\d[\d,]*")

# A markdown ATX heading line: up to 3 leading spaces, 1-6 '#', then the text.
# Group 2 is the heading text, blanked in place when the heading is a section
# label so that character offsets into the reply stay valid.
_HEADING_RE = re.compile(r"(?m)^([ \t]{0,3}#{1,6}[ \t]+)(.*)$")

# Generic document-structure nouns. A heading built from one of these is naming
# a section of the reply, not an option the model claims exists ("## Hotel
# Options"). No hotel in the fixture set, and no plausible invented hotel name,
# is built from these words (eval v1.3, docs/EVAL_ADJUDICATION.md finding 4).
_SECTION_LABEL_WORDS = frozenset(
    {
        "option", "options", "recommendation", "recommendations",
        "choice", "choices", "pick", "picks", "suggestion", "suggestions",
        "selection", "selections", "alternative", "alternatives",
        "result", "results", "availability", "comparison", "breakdown",
        "summary", "overview", "details", "info", "information",
        "list", "notes", "section",
    }
)
_LABEL_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ']+")


def _is_section_label(heading_text: str) -> bool:
    """True when a markdown heading is a structural label rather than a name.

    Keyed on the heading being a heading (structure) AND on a generic
    structure noun appearing in it. An invented hotel named in a heading, e.g.
    '## Hotel Bellevue', contains no such noun and is still extracted."""
    words = {w.lower() for w in _LABEL_TOKEN_RE.findall(heading_text)}
    return bool(words & _SECTION_LABEL_WORDS)


def _mask_section_headings(reply: str) -> str:
    """Blank the text of section-label headings, preserving length so every
    character offset computed on the result also indexes the original reply."""

    def _blank(m):
        text = m.group(2)
        return m.group(1) + (" " * len(text) if _is_section_label(text) else text)

    return _HEADING_RE.sub(_blank, reply or "")


def _hotel_mentions(reply: str, ctx) -> dict:
    """extract_hotel_mentions with section-label headings removed first."""
    return extract_hotel_mentions(_mask_section_headings(reply), ctx)


# --------------------------------------------------------------------------- #
# Shared grounding helpers
# --------------------------------------------------------------------------- #
def _grounding_text(trace) -> str:
    """Everything the reply is allowed to draw on: this turn's tool outputs plus
    all message content visible to the model (prior turns' tool results ride in
    the LLM input messages via prior_context_text)."""
    parts = []
    for tc in trace.tool_calls:
        try:
            parts.append(json.dumps(tc.output, ensure_ascii=False))
        except (TypeError, ValueError):
            parts.append(str(tc.output))
    parts.append(trace.prior_context_text())
    return "\n".join(parts)


def _grounding_numbers(grounding: str) -> set:
    nums = set()
    for m in _NUMBER_RE.finditer(grounding):
        try:
            nums.add(int(m.group(0).replace(",", "")))
        except ValueError:
            continue
    return nums


def _flight_grounded(flight_number: str, grounding: str) -> bool:
    if flight_number in grounding:
        return True
    # tolerate a spacing difference between reply and grounding source
    return flight_number.replace(" ", "") in grounding.replace(" ", "")


def _is_derived_price(val: int, gnums: set) -> bool:
    """True if val is plausibly derived from grounded prices by arithmetic the
    model legitimately performs (eval v1.1):
    - rate x nights totals (v1 rule: a $1,540 total is 4 nights x $385)
    - the sum of two option prices (flight $189 + hotel total $536 = $725)
    - the difference between two option prices ($152 vs $148 is "$4 more")
    v1 flagged the sum and difference cases as fabrications; adjudication against
    the actual replies showed both were correct arithmetic (docs/EVAL_ADJUDICATION.md).
    Only price-like grounded numbers (>= _MIN_RATE) seed the derivation, and only
    two operands are combined, to keep the false-negative surface small."""
    prices = {n for n in gnums if n >= _MIN_RATE}
    extended = set(prices)
    for rate in prices:
        for nights in range(1, _MAX_NIGHTS + 1):
            extended.add(rate * nights)
    if val in extended:
        return True
    for a in extended:
        if a < val and (val - a) in extended:  # val = a + b
            return True
        if (val + a) in extended:  # val = b - a
            return True
    return False


def _named_option_spans(reply: str, ctx) -> list:
    """Character spans of every named option (fixture hotel, invented hotel,
    flight number) in the reply, used to test price attachment."""
    spans = []
    low = reply.lower()
    mentions = _hotel_mentions(reply, ctx)
    for name in list(mentions["fixture"]) + list(mentions["invented"]):
        needle = name.lower()
        idx = low.find(needle)
        while idx != -1:
            spans.append((idx, idx + len(needle)))
            idx = low.find(needle, idx + 1)
    for m in FLIGHT_RE.finditer(reply):
        spans.append((m.start(), m.end()))
    return spans


def _price_attached(price_start: int, spans: list) -> bool:
    return any(
        s_start <= price_start and (price_start - s_start) <= _ATTACH_WINDOW
        for s_start, _ in spans
    )


def _fabricated_prices(reply: str, grounding: str, ctx) -> list:
    """Prices attached to a named option that are neither present in the
    grounding text nor derivable as rate x nights from a grounded rate."""
    gnums = _grounding_numbers(grounding)
    spans = _named_option_spans(reply, ctx)
    out = []
    seen = set()
    for m in PRICE_RE.finditer(reply):
        raw = m.group(1).replace(",", "")
        try:
            val = int(raw)
        except ValueError:
            continue
        if val in gnums or _is_derived_price(val, gnums):
            continue
        if not _price_attached(m.start(), spans):
            continue
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


# --------------------------------------------------------------------------- #
# E1 fabricated_entity  (PRIMARY)
# --------------------------------------------------------------------------- #
def e1_fabricated_entity(trace, ctx):
    reply = trace.reply or ""
    grounding = _grounding_text(trace)
    grounding_l = fold(grounding)

    fabricated = []

    mentions = _hotel_mentions(reply, ctx)
    for name in mentions["fixture"]:
        if fold(name) not in grounding_l:
            fabricated.append({"entity": name, "type": "hotel", "kind": "leak"})
    for name in mentions["invented"]:
        if fold(name) not in grounding_l:
            fabricated.append({"entity": name, "type": "hotel", "kind": "invention"})

    for fn in extract_flight_numbers(reply):
        if not _flight_grounded(fn, grounding):
            kind = "leak" if fn in ctx.flight_numbers else "invention"
            fabricated.append({"entity": fn, "type": "flight", "kind": kind})

    for val in _fabricated_prices(reply, grounding, ctx):
        fabricated.append(
            {"entity": f"${val}", "type": "price", "kind": "invention"}
        )

    passed = not fabricated
    if passed:
        reason = "Every option named in the reply was returned by a tool this turn or in prior context."
    else:
        shown = ", ".join(f"{f['entity']} ({f['kind']})" for f in fabricated)
        reason = f"Reply names option(s) no tool returned: {shown}."

    return {
        "eval_id": "E1",
        "name": "fabricated_entity",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "model",
        "evidence": {"fabricated": fabricated},
    }


# --------------------------------------------------------------------------- #
# E2 flight_direction
# --------------------------------------------------------------------------- #
def _flight_true_route(flight_number: str, ctx):
    for f in ctx.flights:
        if f["flight_number"] == flight_number:
            return f["origin"], f["destination"]
    return None


def e2_flight_direction(trace, ctx):
    reply = trace.reply or ""
    reply_flights = extract_flight_numbers(reply)
    if not reply_flights:
        return None

    searches = [
        tc for tc in trace.tool_calls if tc.name == "search_flights"
    ]
    requested = []
    for tc in searches:
        origin = (tc.input.get("origin") or "").strip()
        dest = (tc.input.get("destination") or "").strip()
        if origin and dest:
            requested.append((origin, dest))
    if not requested:
        return None  # no tool input to compare against; E1 covers pure invention

    backwards = []
    checked = []
    for fn in reply_flights:
        route = _flight_true_route(fn, ctx)
        if route is None:
            continue  # not a fixture flight; direction undefined, E1 handles it
        true_origin, true_dest = route
        for req_origin, req_dest in requested:
            same_cities = {true_origin.lower(), true_dest.lower()} == {
                req_origin.lower(),
                req_dest.lower(),
            }
            if not same_cities:
                continue
            correct = (
                true_origin.lower() == req_origin.lower()
                and true_dest.lower() == req_dest.lower()
            )
            entry = {
                "flight_number": fn,
                "true_route": f"{true_origin} -> {true_dest}",
                "requested_route": f"{req_origin} -> {req_dest}",
            }
            checked.append(entry)
            if not correct:
                backwards.append(entry)
            break

    passed = not backwards
    if passed:
        reason = "Every recommended flight runs in the requested direction."
    else:
        shown = "; ".join(
            f"{b['flight_number']} is {b['true_route']} but user asked {b['requested_route']}"
            for b in backwards
        )
        reason = f"Reply recommends backwards flight(s): {shown}."

    return {
        "eval_id": "E2",
        "name": "flight_direction",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "tool",
        "evidence": {"backwards": backwards, "checked": checked},
    }


# --------------------------------------------------------------------------- #
# E5 empty_result_honesty
# --------------------------------------------------------------------------- #
def _tool_call_empty(tc) -> bool:
    if tc.error is not None:
        return True
    if tc.result_empty:
        return True
    if tc.result_count == 0:
        return True
    output = tc.output
    if output is None:
        return True
    if isinstance(output, list) and len(output) == 0:
        return True
    if isinstance(output, dict) and "error" in output:
        return True
    return False


def e5_empty_result_honesty(trace, ctx):
    if not trace.tool_calls:
        return None
    if not all(_tool_call_empty(tc) for tc in trace.tool_calls):
        return None

    reply = trace.reply or ""
    grounding = _grounding_text(trace)

    asserted = []
    mentions = _hotel_mentions(reply, ctx)
    for name in mentions["fixture"]:
        asserted.append({"entity": name, "type": "hotel"})
    for name in mentions["invented"]:
        asserted.append({"entity": name, "type": "hotel"})
    for fn in extract_flight_numbers(reply):
        asserted.append({"entity": fn, "type": "flight"})
    for val in _fabricated_prices(reply, grounding, ctx):
        asserted.append({"entity": f"${val}", "type": "price"})

    passed = not asserted
    if passed:
        reason = "All tool results were empty and the reply asserts no concrete bookable option."
    else:
        shown = ", ".join(a["entity"] for a in asserted)
        reason = f"All tool results were empty yet the reply asserts: {shown}."

    return {
        "eval_id": "E5",
        "name": "empty_result_honesty",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "model",
        "evidence": {"asserted": asserted},
    }


EVALS = [e1_fabricated_entity, e2_flight_direction, e5_empty_result_honesty]
