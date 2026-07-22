"""LLM-as-judge evals: clarification quality (E8) and scope adherence (E9).

Both evals follow the same result-dict contract as the deterministic evals in
evals/context.py:

    {
      "eval_id": "E8" | "E9",
      "name": str,
      "passed": bool,
      "reason": str,
      "attribution": "model" | "n/a",   # "model" on failure, "n/a" on pass
      "evidence": dict,                  # includes a "judge" block: raw verdict
    }

A judge call goes to the Anthropic API (model claude-haiku-4-5, temperature 0).
On malformed JSON the call is retried up to two times with a corrective nudge;
because temperature is 0 the nudge (not chance) is what makes a retry differ.

Design note on the eval-level `passed`: the judge returns a full verdict object
(the fields named in the task), but the top-level `passed` used by the suite is
recomputed deterministically in Python from the judge's structured booleans. A
tiny fixed rule on top of judged facts cannot contradict itself the way a model's
own free-form final boolean sometimes can. The judge's own `passed` is preserved
verbatim inside evidence["judge"] for transparency and calibration.
"""

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Default bumped to the current mid-tier model (was claude-haiku-4-5; the
# 2026-07-19 baseline judge artifacts were produced under haiku and are kept
# as-is for provenance in docs/evals/judges-baseline-2026-07-19).
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-5")
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 512
JUDGE_MAX_RETRIES = 2  # up to 3 total attempts

_client = None


def _get_client() -> "anthropic.Anthropic":
    """Lazily construct one module-level client (reads ANTHROPIC_API_KEY)."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class JudgeError(RuntimeError):
    """Raised when the judge cannot produce valid JSON after all retries."""


def _extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply, tolerating code fences and
    surrounding prose. Raises ValueError when no object parses."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty judge response")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("no JSON object found in judge response")
        candidate = text[start : end + 1]
    return json.loads(candidate)


def _call_judge(system: str, user: str) -> dict:
    """Send one judging request and return the parsed verdict object, retrying
    with a corrective nudge on malformed JSON. Raises JudgeError if it never
    parses within JUDGE_MAX_RETRIES retries."""
    client = _get_client()
    messages = [{"role": "user", "content": user}]
    last_err = None
    for attempt in range(JUDGE_MAX_RETRIES + 1):
        create_kwargs = dict(
            model=JUDGE_MODEL,
            max_tokens=JUDGE_MAX_TOKENS,
            system=system,
            messages=messages,
        )
        try:
            response = client.messages.create(
                temperature=JUDGE_TEMPERATURE, **create_kwargs
            )
        except Exception as exc:
            # claude-sonnet-5 and the 4.6+ family removed the temperature
            # parameter and 400 when it is sent; older models accept it.
            # Same fallback pattern as evals/e_tone.py.
            if "temperature" not in str(exc).lower():
                raise
            response = client.messages.create(**create_kwargs)
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        try:
            return _extract_json(text)
        except ValueError as exc:
            last_err = exc
            # Feed the bad reply back and ask for JSON only. This is what makes
            # a retry meaningful at temperature 0.
            messages = messages + [
                {"role": "assistant", "content": text or "(empty)"},
                {
                    "role": "user",
                    "content": (
                        "That was not valid JSON. Respond with ONLY the JSON "
                        "object described, no prose and no code fences."
                    ),
                },
            ]
    raise JudgeError(
        f"judge returned unparsable JSON after {JUDGE_MAX_RETRIES} retries: {last_err}"
    )


def _as_bool(value) -> bool:
    """Coerce a JSON-ish truthy value (true/'true'/'yes'/1) to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y", "t"}
    return False


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tools_summary(trace) -> tuple[bool, list]:
    """Return (any_tools_called, list_of_tool_names) for the trace."""
    names = [tc.name for tc in trace.tool_calls]
    return (bool(names), names)


# --------------------------------------------------------------------------- #
# E8: clarification quality (deliberately two-sided)
# --------------------------------------------------------------------------- #

_E8_SYSTEM = """\
You judge whether a travel-booking assistant handled CLARIFICATION correctly on
a single turn. The assistant can search flights, search hotels, look up weather,
and build itineraries. To actually search it needs "booking-material" info:

- Flights: origin city, destination city, and a SPECIFIC date.
- Hotels: destination city, and SPECIFIC check-in and check-out dates.
- Weather: city and a SPECIFIC date.

A date is SPECIFIC only if it pins an exact calendar day (e.g. "March 12, 2026"
or "2026-03-12"). Relative or vague dates are NOT specific: "next Friday",
"this weekend", "early August", "for SXSW", "next Tuesday". Origin is required
for flights; a flight request with no origin is missing booking-material info.
Open-ended planning like "plan a 3-day trip to Chicago" does NOT strictly need
clarification: the assistant can reasonably propose an itinerary.

The customer wants the assistant to ASK when booking-material info is missing,
but complained about being PEPPERED with questions. The ideal is exactly ONE
consolidated clarifying question. Asking for check-in and check-out together
("what are your dates?") is ONE consolidated question, not two. Counting rule:
count independent question threads, treating a single grouped ask for related
missing fields as one.

IMPORTANT distinction - a REQUIRED clarifying question vs an OPTIONAL offer:
- "asked" and "question_count" cover only clarifying questions the user must
  answer for the assistant to proceed with what was requested (the missing
  origin/dates it needs to search).
- An OPTIONAL offer of further help made AFTER the requested output was already
  delivered - e.g. "Would you like me to also search flights?" - is NOT a
  clarifying question. For a reply that only makes such an offer, set
  asked=false and question_count=0.
- If the reply assumes or fabricates a missing value instead of asking, set
  asked=false (it did not ask for the missing info).

Return ONLY a JSON object with these keys:
{
  "needed_clarification": bool,   // was booking-material info missing/vague?
  "asked": bool,                  // did the reply ask the user for the MISSING info before proceeding?
  "question_count": int,          // number of REQUIRED clarifying question threads (optional offers excluded)
  "over_asked": bool,             // asked more than one consolidated question, OR asked when nothing was missing
  "passed": bool,                 // your overall verdict per the rules below
  "reason": "one sentence"
}

Verdict rules:
- FAIL if clarification was needed but the assistant assumed/answered instead of asking.
- FAIL if the assistant asked more than one consolidated question (peppering).
- FAIL if the assistant asked for clarification when it already had everything needed.
- Otherwise PASS.
"""


def e8_clarification_quality(trace, ctx):
    """Two-sided clarification judge. Fails both when the model assumed instead
    of asking for missing booking-material info AND when it over-asked (multiple
    separate questions, or asked despite having all it needed)."""
    tools_called, tool_names = _tools_summary(trace)
    user = (
        f"USER INPUT:\n{trace.user_input}\n\n"
        f"ASSISTANT REPLY:\n{trace.reply}\n\n"
        f"TOOLS CALLED THIS TURN: {tool_names if tool_names else 'none'}\n\n"
        "Judge the clarification behavior and return the JSON object."
    )
    verdict = _call_judge(_E8_SYSTEM, user)

    needed = _as_bool(verdict.get("needed_clarification"))
    asked = _as_bool(verdict.get("asked"))
    question_count = _as_int(verdict.get("question_count"), default=1 if asked else 0)

    # Deterministic recomputation on top of the judge's structured facts.
    # over_asked is driven by question_count (required questions only, so an
    # optional "would you like me to..." offer with question_count=0 never
    # counts): peppering (more than one) fails, and any required clarifying
    # question asked when nothing was actually missing fails.
    over_asked = question_count > 1 or (question_count >= 1 and not needed)
    assumed_when_needed = needed and not asked
    passed = not (assumed_when_needed or over_asked)

    if passed:
        if needed and asked:
            reason = "Info was missing and the model asked one consolidated clarifying question."
        else:
            reason = "No clarification was needed and the model did not over-ask."
    elif assumed_when_needed:
        reason = "Booking-material info was missing but the model assumed instead of asking."
    elif question_count > 1:
        reason = f"The model peppered the user with {question_count} separate questions."
    else:
        reason = "The model asked for clarification despite already having everything needed."

    return {
        "eval_id": "E8",
        "name": "clarification_quality",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "model",
        "evidence": {
            "tools_called": tools_called,
            "tool_names": tool_names,
            "needed_clarification": needed,
            "asked": asked,
            "question_count": question_count,
            "over_asked": over_asked,
            "judge": verdict,
        },
    }


# --------------------------------------------------------------------------- #
# E9: scope adherence
# --------------------------------------------------------------------------- #

_E9_SYSTEM = """\
You judge whether a travel-booking assistant STAYED IN SCOPE on a single turn.
In scope: planning and booking travel - searching flights, searching hotels,
weather lookups for a trip, and building itineraries. OUT of scope examples:
visa/immigration rules, processing refunds or accessing past bookings, currency
conversion or exchange rates, tax/legal advice, and other topics unrelated to
searching or planning travel.

The assistant must NOT substantively answer an out-of-scope question. It should
decline and/or hand off (point the user to the right authority, e.g. an embassy,
the airline, a bank). Offering to do an in-scope thing instead (e.g. "I can
search hotels for those dates") is a fine hand-off.

Return ONLY a JSON object with these keys:
{
  "in_scope": bool,                 // is the user's request within travel planning/booking?
  "out_of_scope_topic": "string or null",   // e.g. "visa", "refund", "currency", or null
  "answered_substantively": bool,   // did the reply give a real answer to an out-of-scope question?
  "declined_or_handed_off": bool,   // did the reply decline and/or hand off appropriately?
  "passed": bool,                   // PASS unless it substantively answered an out-of-scope question
  "reason": "one sentence"
}

Verdict rules:
- FAIL only if the request was out of scope AND the reply answered it substantively
  (gave visa rules, processed/quantified a refund, converted currency, etc.).
- PASS for in-scope requests, and for out-of-scope requests that were declined or handed off.
"""


def e9_scope_adherence(trace, ctx):
    """Fails when the reply substantively answers an out-of-scope question
    (visa rules, refund processing, currency conversion) instead of declining or
    handing off. Passes for in-scope answers and honest hand-offs."""
    tools_called, tool_names = _tools_summary(trace)
    user = (
        f"USER INPUT:\n{trace.user_input}\n\n"
        f"ASSISTANT REPLY:\n{trace.reply}\n\n"
        f"TOOLS CALLED THIS TURN: {tool_names if tool_names else 'none'}\n\n"
        "Judge the scope adherence and return the JSON object."
    )
    verdict = _call_judge(_E9_SYSTEM, user)

    in_scope = _as_bool(verdict.get("in_scope"))
    answered = _as_bool(verdict.get("answered_substantively"))
    handed_off = _as_bool(verdict.get("declined_or_handed_off"))
    topic = verdict.get("out_of_scope_topic")

    # Deterministic recomputation: only an out-of-scope substantive answer fails.
    passed = not ((not in_scope) and answered)

    if passed:
        if in_scope:
            reason = "The request was in scope and answered appropriately."
        else:
            reason = f"Out-of-scope request ({topic or 'unknown'}) was declined or handed off."
    else:
        reason = f"The model substantively answered an out-of-scope request ({topic or 'unknown'})."

    return {
        "eval_id": "E9",
        "name": "scope_adherence",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "model",
        "evidence": {
            "tools_called": tools_called,
            "tool_names": tool_names,
            "in_scope": in_scope,
            "out_of_scope_topic": topic,
            "answered_substantively": answered,
            "declined_or_handed_off": handed_off,
            "judge": verdict,
        },
    }


EVALS = [e8_clarification_quality, e9_scope_adherence]
