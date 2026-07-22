"""agent/redaction.py: PII is removed at the process boundary.

Luke's requirement is that PII never reaches the LLM provider and never reaches
the eval system. agent.redaction.redact() is the single choke point: agent/chat.py
and agent/api.py call it before the text is appended to the message history, sent
to the model, or written to a span.

The tests that matter here are the negative ones. A blanket "13-19 digits ->
redact" regex would pass every positive case while destroying itinerary numbers,
confirmation codes, and prices. Every positive case below is therefore paired
with a Luhn-INVALID number of the same shape that must survive untouched.
"""

import pytest

from agent.redaction import _CARD_TOKEN, _SSN_TOKEN, redact

# Publicly documented test card numbers. None is a real account.
VISA_16 = "4111111111111111"          # Luhn valid
VISA_13 = "4222222222222"             # Luhn valid, shortest accepted length
MASTERCARD_16 = "5555555555554444"    # Luhn valid
AMEX_15 = "378282246310005"           # Luhn valid

# Same shape, Luhn INVALID. These prove the check is a checksum, not a digit run.
VISA_16_BAD_CHECKSUM = "4111111111111112"
SEQUENTIAL_16 = "1234567890123456"

SSN = "123-45-6789"


class TestSsn:
    def test_ssn_is_redacted(self):
        clean, findings = redact(f"My SSN is {SSN}, can you help?")
        assert SSN not in clean
        assert clean == f"My SSN is {_SSN_TOKEN}, can you help?"
        assert findings == ["ssn"]

    def test_nine_digit_run_without_grouping_is_not_an_ssn(self):
        text = "Confirmation 123456789 please"
        clean, findings = redact(text)
        assert clean == text
        assert findings == []

    def test_ssn_embedded_in_a_longer_digit_run_is_not_matched(self):
        text = "ref 5123-45-67890"
        clean, findings = redact(text)
        assert clean == text
        assert findings == []


class TestCardLuhn:
    @pytest.mark.parametrize("number", [VISA_16, VISA_13, MASTERCARD_16, AMEX_15])
    def test_luhn_valid_card_is_redacted(self, number):
        clean, findings = redact(f"charge it to {number} today")
        assert number not in clean
        assert clean == f"charge it to {_CARD_TOKEN} today"
        assert findings == ["card"]

    @pytest.mark.parametrize(
        "number", [VISA_16_BAD_CHECKSUM, SEQUENTIAL_16]
    )
    def test_luhn_invalid_number_is_left_alone(self, number):
        """The load-bearing negative case: same length, same shape, fails Luhn,
        so it is a booking reference and not a card. It must survive verbatim."""
        text = f"my booking reference is {number}, look it up"
        clean, findings = redact(text)
        assert clean == text
        assert findings == []

    @pytest.mark.parametrize("sep", [" ", "-"])
    def test_separated_card_is_redacted(self, sep):
        spaced = sep.join([VISA_16[i:i + 4] for i in range(0, 16, 4)])
        clean, findings = redact(f"card: {spaced}")
        assert clean == f"card: {_CARD_TOKEN}"
        assert findings == ["card"]

    @pytest.mark.parametrize("sep", [" ", "-"])
    def test_separated_luhn_invalid_number_is_left_alone(self, sep):
        spaced = sep.join(
            [VISA_16_BAD_CHECKSUM[i:i + 4] for i in range(0, 16, 4)]
        )
        text = f"card: {spaced}"
        clean, findings = redact(text)
        assert clean == text
        assert findings == []

    def test_twelve_digit_run_is_below_the_card_length_floor(self):
        text = "order 411111111111 shipped"
        clean, findings = redact(text)
        assert clean == text
        assert findings == []


class TestRealAgentTraffic:
    """Text the shipped agent actually produces must pass through untouched, or
    redaction becomes a groundedness bug of its own."""

    @pytest.mark.parametrize(
        "text",
        [
            "Find me a flight from New York to Miami on March 12, 2026.",
            "**Delta DL 883** - $214, departs 9:40 AM, arrives 12:55 PM",
            "Hotel Lumiere: $385 per night ($1,540 total for 4 nights)",
            "search_hotels(city='Miami', check_in='2026-08-07', check_out='2026-08-09')",
        ],
    )
    def test_no_false_positive_on_agent_text(self, text):
        clean, findings = redact(text)
        assert clean == text
        assert findings == []


class TestContract:
    def test_clean_text_is_returned_as_the_same_object(self):
        """Byte-identical pass-through: no PII means no rebuild, so the redaction
        step cannot perturb a trace that had nothing to redact."""
        text = "Plan a 3-day trip to Chicago for me."
        clean, findings = redact(text)
        assert clean is text
        assert findings == []

    def test_findings_follow_order_of_appearance(self):
        clean, findings = redact(f"card {VISA_16} then ssn {SSN}")
        assert findings == ["card", "ssn"]
        assert clean == f"card {_CARD_TOKEN} then ssn {_SSN_TOKEN}"

        clean, findings = redact(f"ssn {SSN} then card {VISA_16}")
        assert findings == ["ssn", "card"]
        assert clean == f"ssn {_SSN_TOKEN} then card {_CARD_TOKEN}"

    def test_multiple_cards_all_redacted(self):
        clean, findings = redact(f"{VISA_16} and {MASTERCARD_16}")
        assert findings == ["card", "card"]
        assert VISA_16 not in clean and MASTERCARD_16 not in clean

    @pytest.mark.parametrize("value", ["", None, 12345, ["a"]])
    def test_non_text_input_passes_through(self, value):
        clean, findings = redact(value)
        assert clean is value or clean == value
        assert findings == []


def test_boundary_and_e6_detector_share_one_pattern_source():
    """agent/redaction.py claims it imports the canonical patterns from
    evals/e_guardrails.py so the boundary and the after-the-fact E6 detector can
    never drift. Pin that: identity, not equality."""
    import agent.redaction as boundary
    import evals.e_guardrails as detector

    assert boundary._SSN_RE is detector._SSN_RE
    assert boundary._CARD_RE is detector._CARD_RE
    assert boundary._luhn_ok is detector._luhn_ok
