"""Conflicting-context eval (E10): a tool call that reuses a value the user has
already superseded earlier in the same session.

Motivation (Luke): "nice to know if we have conflicting information ... some way
to highlight the conflicting information." Within one session, when a later user
message changes a booking-material value (origin, destination/city, or a date),
any SUBSEQUENT tool call that still passes the OLD value is a conflict. The model
had the correction in its context and ignored it, so attribution is "model".

Why this is deterministic and closed-world:
- Candidate cities are exactly the fixture city set
  (EvalContext.flight_cities | hotel_cities | weather_cities); a city is matched
  as a whole-word, case-insensitive occurrence. Origin is the city introduced by
  "from X"; every other named city is a "place" (destination / hotel city /
  weather city / itinerary destination). A bare new city for a slot that a prior
  turn established differently counts as a change; "instead / actually / change /
  make it" are treated as strong signals but are not required for cities.
- Dates are YYYY-MM-DD plus month-name forms ("March 15", "15 Mar 2026"). Because
  a trip carries several dates, a date change is only recognized with an explicit
  change cue (or an explicit "instead of <old date>"), so additive multi-date
  turns never false-positive.

Session reconstruction: run_evals calls every eval once per trace. The prior
turns of the session ride inside this turn's LLM input messages (the same seam
e_grounding uses via TraceView.prior_context_text). We rebuild the ordered user
messages of the session from those input messages plus this turn's user_input,
walk them to learn which values have been superseded, then check THIS trace's
tool calls against the superseded set. Single-turn traces (no prior user message)
return None. Pure function of (TraceView, EvalContext): no I/O, clock, or RNG.
"""

import re

# --------------------------------------------------------------------------- #
# Slot -> tool-parameter mapping (source of truth: agent/tools.py schemas)
# --------------------------------------------------------------------------- #
# origin: the departure city (only search_flights carries it).
# place:  the destination / stay city (flight destination, hotel city, weather
#         city, itinerary destination all name the same "where I am going").
# date:   any calendar date the trip is pinned to.
_CITY_SLOT_PARAMS = {
    "origin": {"search_flights": ("origin",)},
    "place": {
        "search_flights": ("destination",),
        "search_hotels": ("city",),
        "get_weather": ("city",),
        "create_itinerary": ("destination",),
    },
}
_DATE_PARAMS = {
    "search_flights": ("date",),
    "search_hotels": ("check_in", "check_out"),
    "get_weather": ("date",),
}

# Explicit change cues. Required for a DATE change (dates are otherwise too
# ambiguous across a multi-date trip); for cities a bare replacement also counts,
# so these only strengthen the evidence there.
_CUE_RE = re.compile(
    r"\b(instead|actually|change|make it|rather|scratch that|"
    r"reschedul\w*|move it|no wait|no,)\b",
    re.IGNORECASE,
)

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MDY_RE = re.compile(
    rf"(?i)\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\b"
)
_DMY_RE = re.compile(
    rf"(?i)\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT})\.?(?:,?\s*(\d{{4}}))?\b"
)


# --------------------------------------------------------------------------- #
# City extraction (closed world)
# --------------------------------------------------------------------------- #
def _city_tools(ctx):
    """Compiled per-call from the fixture city set: an all-cities regex, a
    from-<city> regex (origin), and a lower->canonical name map. Longest names
    first so 'New York' wins over a bare 'York' fragment."""
    cities = set(ctx.flight_cities) | set(ctx.hotel_cities) | set(ctx.weather_cities)
    canon = {c.lower(): c for c in cities}
    alt = "|".join(re.escape(c) for c in sorted(cities, key=len, reverse=True))
    all_re = re.compile(rf"(?i)\b({alt})\b")
    from_re = re.compile(rf"(?i)\bfrom\s+({alt})\b")
    return all_re, from_re, canon


def _slots_in_message(msg, all_re, from_re, canon):
    """Return {'origin': set, 'place': set} of canonical city names named in one
    user message. Origin = cities introduced by 'from'; place = everything else."""
    origin = {canon[m.group(1).lower()] for m in from_re.finditer(msg)}
    allc = {canon[m.group(1).lower()] for m in all_re.finditer(msg)}
    return {"origin": origin, "place": allc - origin}


# --------------------------------------------------------------------------- #
# Date extraction (closed world)
# --------------------------------------------------------------------------- #
def _extract_dates(text):
    """List of (year|None, month, day) tuples for every date in the text, in
    first-seen order. Year is None for month-name dates that omit it."""
    out = []
    for m in _ISO_DATE_RE.finditer(text):
        out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _MDY_RE.finditer(text):
        y = int(m.group(3)) if m.group(3) else None
        out.append((y, _MONTHS[m.group(1).lower()], int(m.group(2))))
    for m in _DMY_RE.finditer(text):
        y = int(m.group(3)) if m.group(3) else None
        out.append((y, _MONTHS[m.group(2).lower()], int(m.group(1))))
    # de-dup preserving order
    seen, uniq = set(), []
    for d in out:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def _date_match(a, b):
    """Same calendar day; a missing year on either side is a wildcard."""
    (ya, ma, da), (yb, mb, db) = a, b
    if (ma, da) != (mb, db):
        return False
    return ya is None or yb is None or ya == yb


def _fmt_date(d):
    y, m, day = d
    return f"{y:04d}-{m:02d}-{day:02d}" if y else f"{m:02d}-{day:02d}"


def _parse_param_date(value):
    if not isinstance(value, str):
        return None
    m = _ISO_DATE_RE.search(value)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


# --------------------------------------------------------------------------- #
# Session reconstruction from this turn's LLM input messages
# --------------------------------------------------------------------------- #
def _looks_like_user_utterance(content):
    """A genuine user turn is non-empty natural language. Tool-result user
    messages carry JSON (start with '[' or '{') and are excluded."""
    if not isinstance(content, str):
        return False
    s = content.strip()
    return bool(s) and s[0] not in "[{"


def _prior_user_messages(trace):
    """Ordered user utterances of the session before this turn, reconstructed
    from the richest LLM input-message history available on the trace."""
    best = []
    for call in trace.llm_calls:
        users = [
            m.get("content", "")
            for m in call.input_messages
            if m.get("role") == "user"
            and _looks_like_user_utterance(m.get("content", ""))
        ]
        if len(users) >= len(best):
            best = users
    current = (trace.user_input or "").strip()
    prior = [u for u in best if u.strip() != current]
    return prior


# --------------------------------------------------------------------------- #
# Supersession walk
# --------------------------------------------------------------------------- #
def _walk_city_slot(messages, slot, all_re, from_re, canon):
    """Walk the ordered messages; return (stale_values, records) for one city
    slot. A message that names a single city differing from the established value
    supersedes it; a repeated or additive same-city mention changes nothing."""
    established = None
    stale, records = {}, []
    for msg in messages:
        named = _slots_in_message(msg, all_re, from_re, canon)[slot]
        if not named:
            continue
        if established is None:
            if len(named) == 1:
                established = next(iter(named))
            continue
        differing = named - {established}
        if len(differing) == 1:
            new = next(iter(differing))
            stale[established.lower()] = established
            records.append(
                {
                    "slot": slot,
                    "superseded": established,
                    "corrected": new,
                    "message": msg,
                }
            )
            established = new
        # len(differing) > 1 is ambiguous -> conservatively ignored
    return stale, records


_INSTEAD_OF_RE = re.compile(r"(?i)\binstead of\b(.*)$")


def _walk_dates(messages):
    """Walk the ordered messages; return (stale_dates, records). A date change is
    only recognized with an explicit cue (or 'instead of <old date>') so additive
    multi-date turns do not false-positive."""
    established, stale, records = [], [], []
    for msg in messages:
        dates = _extract_dates(msg)
        if not dates:
            continue
        cue = _CUE_RE.search(msg)
        io = _INSTEAD_OF_RE.search(msg)
        old = None
        if io:
            tail = _extract_dates(io.group(1))
            if tail:
                old = tail[0]
        if old is None and cue and len(established) == 1:
            old = established[0]
        if old is not None:
            new = [d for d in dates if not _date_match(d, old)]
            if new:
                stale.append(old)
                records.append(
                    {
                        "slot": "date",
                        "superseded": _fmt_date(old),
                        "corrected": _fmt_date(new[0]),
                        "message": msg,
                    }
                )
                established = [d for d in established if not _date_match(d, old)]
        for d in dates:
            if not any(_date_match(d, e) for e in established):
                established.append(d)
    return stale, records


# --------------------------------------------------------------------------- #
# Conflict detection against this trace's tool calls
# --------------------------------------------------------------------------- #
def _city_conflicts(trace, slot, stale, canon):
    conflicts = []
    for tc in trace.tool_calls:
        params = tc.input if isinstance(tc.input, dict) else {}
        for pname in _CITY_SLOT_PARAMS[slot].get(tc.name, ()):
            val = params.get(pname)
            if isinstance(val, str) and val.lower() in stale:
                conflicts.append(
                    {
                        "slot": slot,
                        "tool": tc.name,
                        "param": pname,
                        "stale_value": val,
                        "superseded": stale[val.lower()],
                    }
                )
    return conflicts


def _date_conflicts(trace, stale_dates):
    conflicts = []
    for tc in trace.tool_calls:
        params = tc.input if isinstance(tc.input, dict) else {}
        for pname in _DATE_PARAMS.get(tc.name, ()):
            pd = _parse_param_date(params.get(pname))
            if pd and any(_date_match(pd, s) for s in stale_dates):
                conflicts.append(
                    {
                        "slot": "date",
                        "tool": tc.name,
                        "param": pname,
                        "stale_value": params.get(pname),
                        "superseded": _fmt_date(
                            next(s for s in stale_dates if _date_match(pd, s))
                        ),
                    }
                )
    return conflicts


def e10_conflicting_context(trace, ctx):
    """Session-level: fail the trace whose tool call reuses a value the user
    superseded earlier in the session. Applies only to multi-turn sessions;
    single-turn traces (no prior user message) return None."""
    messages = _prior_user_messages(trace)
    if not messages:
        return None  # turn 1 / single-turn: nothing could be superseded yet
    messages = messages + [(trace.user_input or "").strip()]

    all_re, from_re, canon = _city_tools(ctx)

    stale_by_slot, records = {}, []
    for slot in ("origin", "place"):
        stale, recs = _walk_city_slot(messages, slot, all_re, from_re, canon)
        stale_by_slot[slot] = stale
        records.extend(recs)
    stale_dates, date_recs = _walk_dates(messages)
    records.extend(date_recs)

    conflicts = []
    for slot in ("origin", "place"):
        conflicts.extend(_city_conflicts(trace, slot, stale_by_slot[slot], canon))
    conflicts.extend(_date_conflicts(trace, stale_dates))

    # Attach the quoting user message to each conflict from its supersession.
    quote_by_slot_value = {
        (r["slot"], str(r["superseded"]).lower()): r["message"] for r in records
    }
    for c in conflicts:
        key = (c["slot"], str(c["superseded"]).lower())
        c["quoting_message"] = quote_by_slot_value.get(key)

    passed = not conflicts
    if passed:
        if records:
            reason = (
                f"{len(records)} value(s) were superseded this session and every "
                "subsequent tool call used the corrected value."
            )
        else:
            reason = "No booking-material value was superseded earlier in this session."
    else:
        shown = "; ".join(
            f"{c['tool']}.{c['param']} still uses '{c['stale_value']}' "
            f"(superseded by the user)"
            for c in conflicts
        )
        reason = f"Tool call reuses conflicting/superseded value(s): {shown}."

    return {
        "eval_id": "E10",
        "name": "conflicting_context",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "model",
        "evidence": {
            "conflicts": conflicts,
            "supersessions": records,
            "session_turns": len(messages),
        },
    }


EVALS = [e10_conflicting_context]
