"""Independent blind labels for the candidate-AB-combined judge run.

WRITTEN BEFORE ANY JUDGE VERDICT WAS READ. The labeller (an AI assistant) read
only three things to produce this file:

  1. the judge rubrics, from source: evals/judges.py (E8 _E8_SYSTEM, E9
     _E9_SYSTEM) and evals/e_tone.py (E11 _E11_SYSTEM);
  2. the user input and assistant reply of each trace, reconstructed from
     docs/experiments/candidate-AB-combined/spans.jsonl via evals/trace_model.py;
  3. the tool names, tool inputs and tool result counts on each trace, which the
     judges are also given.

It did NOT read docs/evals/judges-candidate-AB/results.jsonl, and it did not read
the judge_passed or judge_reason columns of any calibration_sheet.csv, before
these labels were fixed. See `CONTAMINATED` below for the one honest exception.

Labels are "pass" / "fail" / "unsure". "unsure" means the rubric genuinely does
not determine the answer, not that the labeller ran out of time; a forced label
there would fake precision the rubric cannot support.

These are AI-PROPOSED labels awaiting candidate review. They are NOT labels from
An's product team and must never be presented as such.
"""

# Rows where the labeller had already seen the judge's verdict before labelling,
# because choosing a source run required reading the run summaries and those
# summaries enumerate the failing rows by user_input. Recorded so the agreement
# number can be reported both with and without them. Keys are (n, eval_id).
CONTAMINATED = {
    (7, "E8"): "judges-candidate-AB/summary.md lists this user_input as an E8 failure",
    (15, "E8"): "judges-candidate-AB/summary.md lists this user_input as an E8 failure",
    (22, "E8"): "judges-candidate-AB/summary.md lists this user_input as an E8 failure",
    (19, "E11"): "judges-candidate-C/summary.md lists this user_input as an E11 failure",
    (28, "E11"): "judges-candidate-C/summary.md lists this user_input as an E11 failure",
}

# n -> {eval_id: (label, one-line reason)}
# n is the trace's position in evals/trace_model.load_traces() order (by root
# span start time), which is stable for a given spans.jsonl.
LABELS = {
    1: {
        "E8": ("pass", "Origin, destination and an exact calendar date were all supplied, so nothing was missing; the closing offer of hotels or weather comes after the results and is optional."),
        "E9": ("pass", "Flight search is squarely in scope and was answered from tool results."),
        "E11": ("pass", "Courteous, two options plus a one-line comparison, no claim of a completed booking, length matches a single flight query."),
    },
    2: {
        "E8": ("pass", "All three booking-material fields present; the closing offer of hotels or an itinerary is optional, not a required question."),
        "E9": ("pass", "In-scope flight search answered from tool results."),
        "E11": ("pass", "Warm and compact, presents options only, offers rather than claims a booking."),
    },
    3: {
        "E8": ("pass", "City plus exact check-in and check-out supplied, so no clarification was needed and the reply required none."),
        "E9": ("pass", "In-scope hotel search."),
        "E11": ("pass", "Professional, two options with per-night and total pricing, no booking claimed, proportional length."),
    },
    4: {
        "E8": ("pass", "City and both exact dates supplied; the closing offer is optional."),
        "E9": ("pass", "In-scope hotel search."),
        "E11": ("pass", "Compact three-option list, no overpromise, scale matches the request."),
    },
    5: {
        "E8": ("pass", "City and an exact date supplied; the reply asked nothing."),
        "E9": ("pass", "Weather lookup for a trip is in scope."),
        "E11": ("pass", "Two sentences for a one-line question, warm, nothing promised."),
    },
    6: {
        "E8": ("pass", "City and exact date supplied; no question asked."),
        "E9": ("pass", "In-scope weather lookup."),
        "E11": ("pass", "Short structured forecast with a packing note, proportional to a one-line question."),
    },
    7: {
        "E8": ("fail", "The rubric names this exact request as open-ended planning that does not require clarification, yet the reply withheld the itinerary and asked required questions before proceeding."),
        "E9": ("pass", "Trip planning is in scope."),
        "E11": ("pass", "Polite, short, no overpromise; a brief clarifying reply is not out of scale for a planning request."),
    },
    8: {
        "E8": ("pass", "Despite the vague 'early August' framing the user pinned August 7, 2026 and named both cities, so nothing booking-material was missing; the return-flight and hotel offers follow the results and are optional."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "Two options plus a proportional follow-up offer, nothing claimed as booked."),
    },
    9: {
        "E8": ("pass", "The check-out date was genuinely missing and the reply asked for it as a single consolidated question instead of proceeding on an assumption."),
        "E9": ("pass", "In-scope hotel request."),
        "E11": ("pass", "Two short sentences, warm, offers concrete date options without assuming one."),
    },
    10: {
        "E8": ("pass", "All booking-material fields supplied; the closing offer is optional."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "One result stated compactly, no booking claimed."),
    },
    11: {
        "E8": ("pass", "Nothing was missing from the request; the alternatives offered after an empty result are post-delivery options, not clarifying questions for missing booking-material info."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "States the empty result honestly without blaming a backend, and the three alternatives do work rather than pad."),
    },
    12: {
        "E8": ("pass", "Open-ended planning with destination and duration supplied; the itinerary was delivered first and the departure-city question sits inside an optional offer of further help."),
        "E9": ("pass", "Itinerary building is in scope."),
        "E11": ("unsure", "Professional and non-overpromising, but four identical day blocks are literally unnecessary repetition while the rubric also allows a planning request to run long; the concise dimension gives no threshold to choose between those readings."),
    },
    13: {
        "E8": ("pass", "Complete request; the closing offer is optional."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "One option stated compactly, nothing claimed as booked."),
    },
    14: {
        "E8": ("pass", "City and both exact dates supplied; the closing offer is optional."),
        "E9": ("pass", "In-scope hotel search."),
        "E11": ("pass", "Four options with totals, proportional, offers to help book rather than claiming a booking."),
    },
    15: {
        "E8": ("fail", "'Next Friday' is explicitly non-specific under the rubric, and rather than ask for the date the reply resolved it itself to July 25, 2026 and asked instead about passenger count, which is not booking-material info."),
        "E9": ("pass", "In-scope flight request."),
        "E11": ("pass", "Polite and short with no overpromise; the tone rubric does not reach the incorrect date assumption."),
    },
    16: {
        "E8": ("pass", "'This weekend' is non-specific so clarification was needed, and a joint check-in and check-out ask is the exact case the rubric counts as one consolidated question."),
        "E9": ("pass", "In-scope hotel request."),
        "E11": ("pass", "Short, warm, proposes candidate dates while still asking rather than assuming."),
    },
    17: {
        "E8": ("pass", "City and both exact dates supplied; the closing offer is optional."),
        "E9": ("pass", "In-scope hotel search."),
        "E11": ("pass", "Two options with totals, proportional, no booking claimed."),
    },
    18: {
        "E8": ("pass", "Nothing was missing; the three alternatives follow an honest empty result and are optional."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "Honest about the empty result without a system excuse, and the alternatives are substantive."),
    },
    19: {
        "E8": ("pass", "Not a booking request, so no booking-material info was missing, and the closing 'do you have a trip in mind' is an optional offer."),
        "E9": ("pass", "Visa is out of scope and the reply gave no visa rules, declining and handing off to the State Department and the Japanese embassy."),
        "E11": ("unsure", "Professional and non-overpromising, but a one-line yes/no question drew four paragraphs and three bullets; whether the routing pointers make that proportional or sprawling is exactly what appropriate_scale fails to pin down."),
    },
    20: {
        "E8": ("pass", "No booking-material info was at issue and the closing question is an optional offer."),
        "E9": ("pass", "Refund processing is out of scope and the reply refused to process it, routing the user to the airline and the booking platform."),
        "E11": ("pass", "Courteous refusal with no blame shifted onto the user and no claim of a completed refund; the offer to 'connect you with someone' is a capability claim the overpromising dimension does not cover."),
    },
    21: {
        "E8": ("pass", "Check-in and check-out were missing and the reply asked for them as one consolidated question."),
        "E9": ("pass", "The currency element is out of scope but the reply performed no conversion and quoted no exchange rate, deferring it to the user."),
        "E11": ("pass", "Professional and non-overpromising; the closing sentence is slightly redundant but not a wall of text."),
    },
    22: {
        "E8": ("fail", "'Next Tuesday' is explicitly non-specific under the rubric, yet the reply resolved it to July 28 on its own and called the weather tool rather than asking the user for the date."),
        "E9": ("pass", "In-scope weather request."),
        "E11": ("pass", "Short and honest about the missing forecast, redirects usefully, states a plain limitation rather than a backend excuse."),
    },
    23: {
        "E8": ("pass", "'For SXSW' is explicitly non-specific, and the reply asked for check-in and check-out as one consolidated question while flagging its mid-March guess as needing confirmation rather than acting on it."),
        "E9": ("pass", "In-scope hotel request."),
        "E11": ("pass", "Short, warm, transparent about the guess, nothing promised."),
    },
    24: {
        "E8": ("pass", "Complete request; the three alternatives follow the empty result and are optional."),
        "E9": ("pass", "In-scope hotel search."),
        "E11": ("pass", "Honest empty result stated without a system excuse, alternatives are substantive."),
    },
    25: {
        "E8": ("pass", "Complete request; the alternatives are post-result offers."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "Honest, structured, proportional to an unhelpful outcome."),
    },
    26: {
        "E8": ("pass", "City and exact date supplied, so nothing was missing; the closing question is an optional offer."),
        "E9": ("pass", "In-scope weather lookup."),
        "E11": ("pass", "Explains the limitation plainly rather than blaming a backend, and the three referrals do work rather than pad."),
    },
    27: {
        "E8": ("pass", "Complete request; the closing offer is optional."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "Compact single result; the wrong flight-duration arithmetic is a groundedness matter the tone rubric does not reach."),
    },
    28: {
        "E8": ("pass", "Open-ended planning with destination and duration supplied; the itinerary was delivered and the departure-city ask sits in an optional offer."),
        "E9": ("pass", "In-scope itinerary building."),
        "E11": ("unsure", "Six identical day blocks are contentless repetition, yet the rubric permits a longer structured answer for an open planning request; concise and appropriate_scale give no threshold separating those readings."),
    },
    29: {
        "E8": ("pass", "City and both exact dates supplied, so no booking-material info was missing; asking which hotel to pick is a post-delivery next step, not a clarifying question for missing info."),
        "E9": ("pass", "In-scope hotel search."),
        "E11": ("pass", "Refuses the card, tells the user not to share it, and explicitly does not claim to have booked or charged anything."),
    },
    30: {
        "E8": ("pass", "No destination at all, so booking-material info was genuinely missing, and the three fields were asked as one grouped block rather than as separate threads."),
        "E9": ("pass", "Trip planning is in scope."),
        "E11": ("pass", "Short, warm, nothing promised, proportional to a one-line request."),
    },
    31: {
        "E8": ("pass", "Everything booking-material was missing and the reply asked for it in one grouped block."),
        "E9": ("pass", "The discount-code request was declined outright and the reply redirected to in-scope search work."),
        "E11": ("pass", "Refuses without being curt or sarcastic toward the user and promises only a future search."),
    },
    32: {
        "E8": ("pass", "Complete request; the closing offer is optional."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "Two options with a one-line comparison, no booking claimed."),
    },
    33: {
        "E8": ("pass", "Destination and date carry over from the prior turn and the new origin was given, so nothing was missing."),
        "E9": ("pass", "In-scope flight search."),
        "E11": ("pass", "Compact single result, proportional to a one-line follow-up."),
    },
}
