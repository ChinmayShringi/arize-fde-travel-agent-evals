"""LLM-as-judge eval E11: tone quality.

This is the judge An asked for to automate what her team has been spot-checking
by hand ("tone and such... right now we're just spot checking... recommendation
on how we can automate that"). It scores a single assistant reply on tone.

It follows the SAME contract and the SAME judge pattern as evals/judges.py
(E8 clarification, E9 scope):

  - Verdict is a structured JSON object returned by the model.
  - The eval-level `passed` is recomputed DETERMINISTICALLY in Python from the
    judge's structured booleans, never trusted from the model's own free-form
    boolean. The judge's raw verdict (including its own `passed`) is preserved
    verbatim in evidence["judge"].
  - The judge call is temperature 0; on malformed JSON it retries with a
    corrective nudge (the nudge, not chance, is what makes a retry differ at
    temperature 0).

Model selection differs from E8/E9 on purpose. Tone is a subtler, more
qualitative judgment than the two-sided rule checks in judges.py, so E11 judges
on claude-sonnet-5 by default (a stronger judge), still overridable via the
JUDGE_MODEL env var. The model actually used is recorded in
evidence["judge_model"] so a reviewer can see which judge produced a verdict.

PROVISIONAL RUBRIC (v1) - IMPORTANT
-----------------------------------
The rubric below is PROVISIONAL. It is a first-pass, good-faith encoding of the
tone bar An described; it is NOT the customer's own published rubric. It stays
in force only until An's team supplies their authoritative rubric, at which point
the system prompt and the recompute rule should be updated to match theirs. To
keep that honest and visible downstream, every result carries
evidence["rubric_version"] == "provisional-v1-pending-customer-rubric".

Provisional-v1 dimensions (all four must hold for a PASS):
  - professional : professional and warm; not curt, rude, or dismissive; does
                   NOT shift blame onto the user or hide behind internal-system
                   excuses ("our system is down", "the backend failed").
  - concise      : no walls of text for a simple ask; length is proportional to
                   the question.
  - no_overpromising : never claims to have BOOKED, CHARGED, PAID FOR, or
                   GUARANTEED anything. The agent can only SEARCH flights and
                   hotels, look up weather, and draft itineraries; it cannot
                   transact. Claiming a completed booking or a charged card is
                   overpromising.
  - appropriate_scale : the answer matches the scale of the request. A one-line
                   question gets a compact answer; an open planning request may
                   get a longer, structured one.
"""

import os

import anthropic
from dotenv import load_dotenv

# Reuse the exact judge primitives from judges.py so E11 shares E8/E9's parsing,
# retry, coercion, and client behavior rather than re-deriving them.
from judges import (
    JudgeError,
    _as_bool,
    _extract_json,
    _get_client,
    _tools_summary,
)

load_dotenv()

# Default MUST be claude-sonnet-5 (a stronger judge for a subtler call), not the
# haiku default E8/E9 use. Still overridable via JUDGE_MODEL for cost/experiments.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-5")
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1024  # headroom: sonnet-5 runs adaptive thinking by default
JUDGE_MAX_RETRIES = 2  # up to 3 total attempts

RUBRIC_VERSION = "provisional-v1-pending-customer-rubric"


def _create_message(client, system, messages):
    """One judge API call at temperature 0. claude-sonnet-5 (and the whole
    4.6+ family) REMOVED the temperature parameter and 400s if it is sent, while
    older judges like claude-haiku-4-5 still accept it. We ask for temperature 0
    to make the judge as deterministic as the model allows, and transparently
    drop the parameter on the specific 400 that reports it is unsupported -
    sonnet-5 is already deterministic without a sampling knob, so the intent
    (a reproducible verdict) is preserved either way."""
    kwargs = dict(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        system=system,
        messages=messages,
    )
    try:
        return client.messages.create(temperature=JUDGE_TEMPERATURE, **kwargs)
    except anthropic.BadRequestError as exc:
        if "temperature" not in str(exc).lower():
            raise
        return client.messages.create(**kwargs)


def _call_tone_judge(system: str, user: str) -> dict:
    """Send one tone-judging request on JUDGE_MODEL and return the parsed verdict,
    retrying with a corrective nudge on malformed JSON. Mirrors judges._call_judge
    but binds to E11's model so the sonnet default is honored. Raises JudgeError
    if it never parses within JUDGE_MAX_RETRIES retries."""
    client = _get_client()
    messages = [{"role": "user", "content": user}]
    last_err = None
    for _ in range(JUDGE_MAX_RETRIES + 1):
        response = _create_message(client, system, messages)
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        try:
            return _extract_json(text)
        except ValueError as exc:
            last_err = exc
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
        f"tone judge returned unparsable JSON after {JUDGE_MAX_RETRIES} retries: {last_err}"
    )


# --------------------------------------------------------------------------- #
# E11: tone quality (provisional rubric v1)
# --------------------------------------------------------------------------- #

_E11_SYSTEM = """\
You judge the TONE of a single reply from a travel-booking assistant. The
assistant can ONLY search flights, search hotels, look up weather, and draft
itineraries. It CANNOT book, pay for, charge a card, confirm, or guarantee
anything - it has no transactional tools.

Judge the reply against four dimensions. This rubric is PROVISIONAL (a first
pass), so apply it literally and do not invent extra criteria.

1. professional: The reply is professional and warm - courteous, helpful, and
   respectful. It is NOT curt, rude, dismissive, or sarcastic. It does NOT shift
   blame onto the user, and it does NOT hide behind internal-system excuses
   (e.g. "our system is down", "the backend failed", "that's a known bug"). A
   plain, honest limitation stated politely is fine and stays professional.

2. concise: The reply is not a wall of text for a simple ask. Length should be
   proportional to the request. Padding a one-line question with long preambles
   or unnecessary repetition is NOT concise.

3. no_overpromising: The reply never claims to have BOOKED, RESERVED, PAID FOR,
   CHARGED, CONFIRMED, or GUARANTEED anything. Presenting search results, prices,
   options, or a draft itinerary is fine. Saying "I've booked it" or "I charged
   your card" or "your reservation is confirmed" is overpromising and FAILS this
   dimension, because the assistant cannot actually do those things.

4. appropriate_scale: The answer matches the scale of the request. A one-line
   question should get a compact answer; an open-ended planning request may get
   a longer, structured answer. A tiny question answered with a sprawling reply,
   or a big planning request answered with a single terse line, fails this.

Return ONLY a JSON object with these keys:
{
  "professional": bool,       // dimension 1 holds
  "concise": bool,            // dimension 2 holds
  "no_overpromising": bool,   // dimension 3 holds
  "appropriate_scale": bool,  // dimension 4 holds
  "passed": bool,             // true only if ALL FOUR above are true
  "reason": "one sentence"
}
"""


def e11_tone_quality(trace, ctx):
    """Judge the tone of the reply on the provisional v1 rubric. Passes only when
    all four dimensions (professional, concise, no_overpromising, appropriate_scale)
    hold. `passed` is recomputed in Python from the judge's four structured
    booleans; the judge's raw verdict is kept in evidence["judge"], and the model
    actually used in evidence["judge_model"]."""
    tools_called, tool_names = _tools_summary(trace)
    user = (
        f"USER INPUT:\n{trace.user_input}\n\n"
        f"ASSISTANT REPLY:\n{trace.reply}\n\n"
        f"TOOLS CALLED THIS TURN: {tool_names if tool_names else 'none'}\n\n"
        "Judge the tone and return the JSON object."
    )
    verdict = _call_tone_judge(_E11_SYSTEM, user)

    professional = _as_bool(verdict.get("professional"))
    concise = _as_bool(verdict.get("concise"))
    no_overpromising = _as_bool(verdict.get("no_overpromising"))
    appropriate_scale = _as_bool(verdict.get("appropriate_scale"))

    # Deterministic recomputation: PASS only when all four dimensions hold. The
    # judge's own free-form `passed` is ignored here (kept in evidence["judge"]).
    passed = professional and concise and no_overpromising and appropriate_scale

    if passed:
        reason = "Tone is professional and warm, concise, does not overpromise, and matches the request scale."
    else:
        failed = [
            label
            for label, ok in (
                ("not professional/warm", professional),
                ("not concise", concise),
                ("overpromising", no_overpromising),
                ("wrong scale", appropriate_scale),
            )
            if not ok
        ]
        reason = "Tone failed on: " + ", ".join(failed) + "."

    return {
        "eval_id": "E11",
        "name": "tone_quality",
        "passed": passed,
        "reason": reason,
        "attribution": "n/a" if passed else "model",
        "evidence": {
            "tools_called": tools_called,
            "tool_names": tool_names,
            "professional": professional,
            "concise": concise,
            "no_overpromising": no_overpromising,
            "appropriate_scale": appropriate_scale,
            "rubric_version": RUBRIC_VERSION,
            "judge_model": JUDGE_MODEL,
            "judge": verdict,
        },
    }


EVALS = [e11_tone_quality]
