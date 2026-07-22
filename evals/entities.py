"""Deterministic entity extraction from agent reply text.

These extractors are the shared vocabulary the grounding evals use to decide
whether a named option in a reply was actually returned by a tool. Everything
here is pure string work: same input, same output, no data-file access except
the closed fixture set passed in via EvalContext.

Public surface:
    extract_flight_numbers(text) -> list[str]   normalized "DL 883" forms
    extract_prices(text)         -> list[int]   dollar amounts, commas stripped
    extract_hotel_mentions(text, ctx) -> dict   {"fixture": [...], "invented": [...]}

The compiled regexes (FLIGHT_RE, PRICE_RE) are exposed for the grounding module,
which needs match positions (attachment of a price to a named option).
"""

import re

# Airline-code + number: two capital letters (DL, AA, NH) or a capital letter
# followed by a digit (B6). Fixture flight numbers are exactly these two shapes.
# An optional single space separates code and number ("NH105" and "NH 105" both
# normalize to "NH 105"). AM/PM are excluded so time meridians never match.
FLIGHT_RE = re.compile(r"\b([A-Z]{2}|[A-Z]\d)\s?(\d{1,4})\b")

# Dollar amount: "$189", "$1,540", "$ 1042". Captures the digit run; commas are
# stripped by the caller. A currency word after the number is not required.
PRICE_RE = re.compile(r"\$\s?(\d[\d,]*)")

# Two-letter tokens that are English/prose, not airline codes.
_FLIGHT_STOPWORDS = frozenset({"AM", "PM"})

# Words that mark a phrase as a hotel name. Matched as whole tokens inside a
# Title-Case run (see _RUN_RE). Kept exactly as the task specifies.
_HOTEL_KEYWORDS = frozenset(
    {"hotel", "hôtel", "inn", "suites", "resort", "lodge", "grand", "plaza"}
)

# Brand names that never appear in the fixture set; any occurrence is an
# invented hotel. Matched as case-insensitive substrings of the whole reply so
# multi-word and punctuated brands ("Four Seasons", "St. Regis") are caught
# without depending on the Title-Case run tokenizer.
_BRAND_NAMES = (
    "Hilton",
    "Marriott",
    "Hyatt",
    "Sheraton",
    "Ritz-Carlton",
    "Ritz Carlton",
    "Four Seasons",
    "Holiday Inn",
    "Radisson",
    "Westin",
    "Fairmont",
    "InterContinental",
    "Best Western",
    "Wyndham",
    "Novotel",
    "Ibis",
    "Kimpton",
    "Waldorf",
    "St. Regis",
    "Mandarin Oriental",
    "Peninsula Hotel",
    "Shangri-La",
    "DoubleTree",
    "Hampton Inn",
    "Courtyard by Marriott",
    "Comfort Inn",
    "Days Inn",
    "Motel 6",
)

# A Title-Case run: a capitalized (optionally accented) word, then any number of
# following capitalized words or lowercase connective words. Accented letters are
# admitted so "Hotel Lumiere", "Rive Gauche Hotel" survive as single runs. The
# connector set is deliberately narrow (hotel-name particles only, no "and"/"on"/
# "at") so a run never chains across a clause boundary and swallows a sentence.
_WORD = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'&-]*"
_CONNECT = r"(?:of|the|de|du|des|la|le|by|&)"
_RUN_RE = re.compile(rf"{_WORD}(?:\s+(?:{_CONNECT}|{_WORD}))*")

# Leading words that begin a recommendation sentence but are never part of a
# hotel name; trimmed from the front of a matched run so the reported entity is
# the name itself, not "Try The Grand ...". Trailing connectors are trimmed too.
_LEADING_TRIM = frozenset(
    {"try", "visit", "stay", "book", "explore", "take", "consider", "check",
     "recommend", "suggest", "the", "a", "an", "at", "in", "on", "and", "or"}
)
_TRAILING_TRIM = frozenset({"of", "the", "de", "du", "des", "la", "le", "by", "&"})


def _trim_run(run: str) -> str:
    tokens = run.split()
    while tokens and tokens[0].lower() in _LEADING_TRIM:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in _TRAILING_TRIM:
        tokens.pop()
    return " ".join(tokens)


def extract_flight_numbers(text: str) -> list[str]:
    """Return normalized flight numbers ("DL 883") in first-seen order.

    Both "NH 105" and "NH105" normalize to "NH 105" to match the fixture
    format. AM/PM are never treated as airline codes.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in FLIGHT_RE.finditer(text or ""):
        code, num = m.group(1), m.group(2)
        if code in _FLIGHT_STOPWORDS:
            continue
        norm = f"{code} {num}"
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def extract_prices(text: str) -> list[int]:
    """Return dollar amounts as ints, in first-seen order (commas stripped)."""
    out: list[int] = []
    seen: set[int] = set()
    for m in PRICE_RE.finditer(text or ""):
        raw = m.group(1).replace(",", "")
        try:
            val = int(raw)
        except ValueError:
            continue
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _fixture_related(run_lower: str, fixture_names_lower: frozenset) -> bool:
    """True if a Title-Case run is a fixture hotel name, or a substring of one,
    or contains one. Such runs are handled by the fixture tier and must not be
    reported as invented."""
    for name in fixture_names_lower:
        if run_lower == name or run_lower in name or name in run_lower:
            return True
    return False


def fold(s: str) -> str:
    """Accent-insensitive, case-insensitive comparison form (eval v1.2): the
    model may restyle 'Hotel Lumiere' as 'Hôtel Lumière'; both must compare
    equal or a grounded mention gets misclassified as an invention
    (docs/EVAL_ADJUDICATION.md, finding 2)."""
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def extract_hotel_mentions(text: str, ctx) -> dict:
    """Two-tier hotel detection against the closed fixture set.

    Returns {"fixture": [...], "invented": [...]}:
      - "fixture": fixture hotel names that appear verbatim in the reply.
      - "invented": Title-Case phrases containing a hotel keyword, or brand
        names, that are NOT any fixture hotel.
    Whether a mention is grounded (returned by a tool this turn) is decided by
    the grounding eval, not here.
    """
    text = text or ""
    low = fold(text)
    fixture_names_lower = frozenset(fold(n) for n in ctx.hotel_names)

    fixture = [name for name in ctx.hotel_names if fold(name) in low]

    invented: list[str] = []
    seen: set[str] = set()

    # Brand substrings first: strongest signal, punctuation-tolerant.
    for brand in _BRAND_NAMES:
        if fold(brand) in low and fold(brand) not in fixture_names_lower:
            key = fold(brand)
            if key not in seen:
                seen.add(key)
                invented.append(brand)

    # Keyword-anchored Title-Case runs.
    for m in _RUN_RE.finditer(text):
        run = _trim_run(m.group(0).strip())
        if not run:
            continue
        run_lower = fold(run)
        tokens = frozenset(run_lower.replace("-", " ").split())
        if not (tokens & _HOTEL_KEYWORDS):
            continue
        if _fixture_related(run_lower, fixture_names_lower):
            continue
        if run_lower in seen:
            continue
        seen.add(run_lower)
        invented.append(run)

    return {"fixture": fixture, "invented": invented}
