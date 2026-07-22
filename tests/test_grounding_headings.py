"""E1 regression: a markdown section heading is not an option (eval v1.3).

docs/EVAL_ADJUDICATION.md finding 4. The control arm of the final loop run was
scored E1 32/33 on a single failure whose whole evidence was:

    {"entity": "Hotel Options", "type": "hotel", "kind": "invention"}

The reply text was:

    ## Hotel Options

    1. **Hotel Lumiere** - $385/night (4.7 star rating)
    2. **Rive Gauche Hotel** - $245/night (4.0 star rating)

"Hotel Options" is the section heading. Both hotels under it were tool-returned
and passed. The Title-Case run tokenizer in evals/entities.py matched the
heading because it contains the token "hotel".

The fix is keyed on markdown structure plus generic-label wording, never on the
entity name, so the two failure directions are both pinned here:

  A. a section-label heading is not a candidate entity, and
  B. an invented hotel whose name begins with "Hotel" is still flagged, whether
     it appears in the body or as a heading itself.

Direction B is the one that matters most: a fix that dropped anything starting
with "Hotel" would silently disable the primary eval of the project.

Self-contained and offline: replies are literals, the only external input is
the closed data/ fixture set via the shared ``ctx`` fixture.
"""

import pytest

from evals.context import EvalContext
from evals.e_grounding import (
    _is_section_label,
    _mask_section_headings,
    e1_fabricated_entity,
)
from evals.trace_model import ToolCall, TraceView

# Two real Paris fixture hotels, exactly as data/hotels.json spells them.
LUMIERE = "Hotel Lumière"
RIVE_GAUCHE = "Rive Gauche Hôtel"

HOTEL_TOOL_OUTPUT = [
    {"name": LUMIERE, "city": "Paris", "price_per_night": 385, "rating": 4.7},
    {"name": RIVE_GAUCHE, "city": "Paris", "price_per_night": 245, "rating": 4.0},
]

# The shape of the adjudicated reply: heading, then the grounded options.
GROUNDED_REPLY = (
    "Here is your Paris trip.\n"
    "\n"
    "## Hotel Options\n"
    "\n"
    f"1. **{LUMIERE}** - $385/night (4.7 rating)\n"
    f"2. **{RIVE_GAUCHE}** - $245/night (4.0 rating)\n"
)

# Same reply with one option the tool never returned.
INVENTED_IN_BODY_REPLY = (
    "Here is your Paris trip.\n"
    "\n"
    "## Hotel Options\n"
    "\n"
    f"1. **{LUMIERE}** - $385/night (4.7 rating)\n"
    "2. **Hotel Bellevue** - $385/night (4.6 rating)\n"
)

# The invented hotel appears only as a heading, never in the body.
INVENTED_AS_HEADING_REPLY = (
    "Here is your Paris trip.\n"
    "\n"
    "## Hotel Bellevue\n"
    "\n"
    "A quiet spot near the river, $385/night.\n"
)


def _trace(reply: str) -> TraceView:
    """A one-turn Paris hotel trace whose tool returned both fixture hotels."""
    return TraceView(
        trace_id="0xtest",
        session_id="test-headings",
        user_input="Put together a 5-day itinerary for Paris, arriving June 10, 2026.",
        reply=reply,
        tool_calls=[
            ToolCall(
                name="search_hotels",
                input={"city": "Paris", "check_in": "2026-06-10", "check_out": "2026-06-15"},
                output=HOTEL_TOOL_OUTPUT,
                result_count=2,
                result_empty=False,
                error=None,
            )
        ],
    )


@pytest.fixture(scope="module")
def eval_ctx() -> EvalContext:
    return EvalContext.load()


# --------------------------------------------------------------------------- #
# Direction A: a section heading is not an entity
# --------------------------------------------------------------------------- #
class TestHeadingIsNotAnEntity:
    def test_section_heading_does_not_fail_e1(self, eval_ctx):
        """The adjudicated case itself: heading plus two grounded hotels passes."""
        result = e1_fabricated_entity(_trace(GROUNDED_REPLY), eval_ctx)
        assert result["passed"], result["reason"]
        assert result["evidence"]["fabricated"] == []

    @pytest.mark.parametrize(
        "heading",
        [
            "## Hotel Options",
            "## Hotel Recommendations",
            "### Hotel Choices",
            "# Hotel Picks",
            "## Hotel Options for Paris",
            "## Denver Hotel Options",
            "## Inn Suggestions",
            "## Resort Comparison",
        ],
    )
    def test_label_headings_are_masked(self, heading):
        """Every generic section label seen or plausible in the captured runs."""
        text = heading.lstrip("# ")
        assert _is_section_label(text)
        masked = _mask_section_headings(heading + "\nbody text\n")
        assert text not in masked
        assert len(masked) == len(heading + "\nbody text\n")
        assert "body text" in masked

    def test_masking_preserves_character_offsets(self):
        """Price attachment indexes the reply by character position, so the
        mask must never change the length of the text."""
        masked = _mask_section_headings(GROUNDED_REPLY)
        assert len(masked) == len(GROUNDED_REPLY)
        assert masked.index(LUMIERE) == GROUNDED_REPLY.index(LUMIERE)

    def test_prices_under_a_masked_heading_are_still_grounded(self, eval_ctx):
        """Masking the heading must not orphan the option prices beneath it and
        turn them into unattached fabrications."""
        result = e1_fabricated_entity(_trace(GROUNDED_REPLY), eval_ctx)
        assert [f for f in result["evidence"]["fabricated"] if f["type"] == "price"] == []


# --------------------------------------------------------------------------- #
# Direction B: a real invention starting with "Hotel" is still caught
# --------------------------------------------------------------------------- #
class TestInventedHotelStillFlagged:
    def test_invented_hotel_in_body_is_flagged(self, eval_ctx):
        result = e1_fabricated_entity(_trace(INVENTED_IN_BODY_REPLY), eval_ctx)
        assert not result["passed"]
        assert "Hotel Bellevue" in {
            f["entity"] for f in result["evidence"]["fabricated"]
        }
        assert result["attribution"] == "model"

    def test_invented_hotel_as_a_heading_is_flagged(self, eval_ctx):
        """The fix keys on generic-label wording, not on the '#' alone, so a
        name-shaped heading is still a candidate entity.

        The reported entity is matched by prefix, not equality: the Title-Case
        run regex in evals/entities.py separates words with ``\\s+``, so a run
        can absorb the capitalized first word of the following line
        ("Hotel Bellevue A quiet ..."). That is pre-existing behavior of the
        tokenizer, unrelated to this adjudication, and left unchanged here."""
        assert not _is_section_label("Hotel Bellevue")
        result = e1_fabricated_entity(_trace(INVENTED_AS_HEADING_REPLY), eval_ctx)
        assert not result["passed"]
        assert any(
            f["entity"].startswith("Hotel Bellevue")
            for f in result["evidence"]["fabricated"]
        ), result["reason"]

    def test_grounded_hotels_are_unaffected_by_the_mask(self, eval_ctx):
        """Both real hotels must still be recognised under a masked heading;
        a mask that swallowed the list would hide leaks as well as inventions."""
        from evals.e_grounding import _hotel_mentions

        mentions = _hotel_mentions(GROUNDED_REPLY, eval_ctx)
        assert set(mentions["fixture"]) == {LUMIERE, RIVE_GAUCHE}
        assert mentions["invented"] == []
