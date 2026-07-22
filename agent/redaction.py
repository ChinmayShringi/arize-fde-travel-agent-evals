"""Redaction at source: strip SSNs and Luhn-valid payment card numbers from user
text BEFORE it reaches the Anthropic API, the trace store, or the eval system.

This closes Luke's requirement (PII must never reach the LLM provider and must
stay out of the eval system) at the boundary, upstream of E6's detect-after-the-
fact scan in evals/e_guardrails.py.

Pattern source of truth: evals/e_guardrails.py (_SSN_RE, _CARD_RE, _luhn_ok).
They are imported directly so the boundary redaction and the E6 detector can
never drift. The import has no side effects (that module only defines regexes
and pure functions at import time). If the eval package is not importable at
runtime (e.g. a serving-only deploy that ships without evals/), an identical
mirror is used; the comment on the mirror names e_guardrails.py as canonical.

Deterministic, stdlib only, always-on. A no-op byte-identical pass-through when
the text contains no PII.
"""

import re

try:
    # Canonical patterns live in evals/e_guardrails.py; importing keeps the
    # boundary redaction and the E6 detector provably in lock-step.
    from evals.e_guardrails import _CARD_RE, _SSN_RE, _luhn_ok
except Exception:  # pragma: no cover - serving-only deploys without evals/
    # Mirror of evals/e_guardrails.py (SOURCE OF TRUTH). Keep byte-identical.
    # SSN: three-two-four grouping, not embedded in a longer digit run.
    _SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
    # Payment-card candidate: 13-19 digits, optional single space/hyphen
    # separators, not embedded in a longer digit run. Luhn filters false hits.
    _CARD_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")

    def _luhn_ok(digits: str) -> bool:
        """Standard Luhn checksum over a string of digits."""
        total = 0
        for i, ch in enumerate(reversed(digits)):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0


_SSN_TOKEN = "[REDACTED-SSN]"
_CARD_TOKEN = "[REDACTED-CARD]"


def redact(text):
    """Replace SSNs and Luhn-valid payment card numbers in ``text``.

    Returns ``(clean_text, findings)``. ``findings`` is a list of type strings
    ("ssn" / "card") in order of appearance; empty when nothing was redacted.

    When there is no PII the ORIGINAL object is returned unchanged (byte-identical
    pass-through) and ``findings`` is ``[]``. The original raw text is never
    retained by this function.
    """
    if not isinstance(text, str) or not text:
        return text, []

    # Collect all match spans first, then rebuild once. Card matches are kept
    # only when Luhn-valid, mirroring E6 exactly. SSN (9 digits) and card
    # (13-19 digits) candidates cannot overlap, but overlap-skipping is applied
    # defensively so a rebuilt string is always well-formed.
    spans = []  # (start, end, kind, token)
    for m in _SSN_RE.finditer(text):
        spans.append((m.start(), m.end(), "ssn", _SSN_TOKEN))
    for m in _CARD_RE.finditer(text):
        raw = m.group()
        digits = re.sub(r"[ -]", "", raw)
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            spans.append((m.start(), m.end(), "card", _CARD_TOKEN))

    if not spans:
        return text, []

    spans.sort(key=lambda s: s[0])
    out = []
    findings = []
    last = 0
    for start, end, kind, token in spans:
        if start < last:
            continue  # overlapping match already covered; skip
        out.append(text[last:start])
        out.append(token)
        findings.append(kind)
        last = end
    out.append(text[last:])
    return "".join(out), findings
