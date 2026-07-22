"""Golden-dataset loader and failure-append API for the travel-agent evals.

Pinned contract (other agents build against this; do not deviate):
- load_dataset(path) -> dict
- append_failures(path, failures: list[dict]) -> str   (returns the version)

Dataset schema (evals/golden_dataset.json). Every conversation carries the five
base keys; rows appended from a failure carry additional replay keys:

    {"version": str,
     "conversations": [
        {"id": str, "messages": [str, ...], "tags": [str, ...],
         "eval_targets": [str, ...], "source": "shipped"|"synthetic"|"failure-append",

         # present only on source == "failure-append" rows (P1-03)
         "assistant_reply": str,
         "tool_calls": [{"name": str, "input": dict}, ...],
         "tool_outputs": [{"name": str, "output": obj, ...}, ...],
         "failed_eval_ids": [str, ...],
         "failure_reasons": [str, ...],
         "source_trace_id": str|null,
         "source_session_id": str|null,
         "review_status": "pending",
         "expected_behavior": null,
         "pii_redacted": bool,
         "dedup_key": "sha256:<hex>"}]}

Why the extra keys: a row holding only the latest user message cannot reproduce
most failures. Conflict evals need the earlier turns, groundedness needs the tool
outputs the reply was built from, and tool-parameter defects need the exact call
payload. All of it is measured from the trace; none of it is inferred.

expected_behavior is written as null with review_status "pending". It cannot be
derived from a failed trace: the trace records what the agent DID, never what it
should have done. Auto-filling it would be a fabricated label, so a human fills it.

append_failures rules:
- Each failure is either the legacy shape {"user_input", "eval_id", "reason"} or
  the structured shape {"messages", "failed_eval_ids", "failure_reasons", ...}.
  Legacy input is coerced to the structured shape, so old callers keep working.
- Dedup by `dedup_key`: a sha256 over the NORMALIZED full message list plus the
  sorted failure types. This replaces the old first-message-only key. Two
  different failures that share an opening message are therefore two rows, not
  one. Deliberate behavior change: a shipped conversation and a failure captured
  on that same conversation are different objects (the failure row carries the
  reply, tool calls and tool outputs), so the failure is no longer swallowed.
- If nothing novel survives dedup the call is a no-op: the file is left untouched
  and the current version is returned.
- If anything novel is appended, the version is bumped v<N>-... -> v<N+1>-<date>,
  the new conversations are appended with source "failure-append", and the file is
  rewritten. Existing rows are copied through byte-for-byte; none is rewritten.

Stdlib only. Immutable style: the loaded dict is never mutated in place; new
structures are built and written out. Deterministic given an explicit `today`.
"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

_ALLOWED_SOURCES = ("shipped", "synthetic", "failure-append")
_FAILURE_SOURCE = "failure-append"
# Written on every appended row. A human flips it; the loop never does.
_REVIEW_PENDING = "pending"

# em dash / en dash collapse to hyphen so the same query dedups regardless of
# which dash the capture used.
_DASHES = {"\u2014": "-", "\u2013": "-"}
_WS_RE = re.compile(r"\s+")
_VERSION_RE = re.compile(r"^v(\d+)(?:-.*)?$")


def _normalize(text: str) -> str:
    """Normalized form used only for dedup: lowercase, unify dashes, collapse
    whitespace, strip surrounding quotes/space. Never stored; storage keeps the
    original text verbatim."""
    if not isinstance(text, str):
        raise TypeError(f"message must be str, got {type(text).__name__}")
    t = text.strip().strip("\"'").strip()
    for bad, good in _DASHES.items():
        t = t.replace(bad, good)
    t = _WS_RE.sub(" ", t)
    return t.lower()


_LIST_FIELDS = ("tool_calls", "tool_outputs", "failed_eval_ids", "failure_reasons")


def _validate_conversation(c: dict, label: str, path: Path) -> None:
    """Validate one conversation. The five base keys are required; the P1-03
    replay keys are optional, so an old five-key row and a new enriched row both
    load. When a replay key IS present its type is checked, so a corrupt enriched
    row fails at the boundary rather than downstream."""
    msgs = c.get("messages")
    if not isinstance(msgs, list) or not msgs or not all(
        isinstance(m, str) and m.strip() for m in msgs
    ):
        raise ValueError(f"{path}: conversation {label} has empty/invalid messages")
    if c.get("source") not in _ALLOWED_SOURCES:
        raise ValueError(f"{path}: conversation {label} has invalid source")
    for field_name in _LIST_FIELDS:
        if field_name in c and not isinstance(c[field_name], list):
            raise ValueError(f"{path}: conversation {label} field '{field_name}' must be a list")
    if "review_status" in c and not isinstance(c["review_status"], str):
        raise ValueError(f"{path}: conversation {label} field 'review_status' must be a string")


def _validate(data: dict, path: Path) -> dict:
    """Fail fast on a malformed dataset; return it unchanged on success."""
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be an object")
    if not isinstance(data.get("version"), str) or not data["version"]:
        raise ValueError(f"{path}: 'version' must be a non-empty string")
    convs = data.get("conversations")
    if not isinstance(convs, list):
        raise ValueError(f"{path}: 'conversations' must be a list")
    for i, c in enumerate(convs):
        if not isinstance(c, dict):
            raise ValueError(f"{path}: conversation {i} must be an object")
        _validate_conversation(c, str(c.get("id", i)), path)
    return data


def load_dataset(path) -> dict:
    """Load and validate the golden dataset. Returns a freshly parsed dict, so
    callers can mutate the result without touching the file or shared state."""
    p = Path(path)
    data = json.loads(p.read_text())
    return _validate(data, p)


def _bump_version(current: str, today: str) -> str:
    """v<N>-<anything>  ->  v<N+1>-<today>. Falls back to v2-<today> if the
    current version does not carry a leading integer."""
    m = _VERSION_RE.match(current.strip())
    n = int(m.group(1)) + 1 if m else 2
    return f"v{n}-{today}"


def _next_failure_id(existing_ids: set) -> str:
    n = 1
    while f"failure-{n:03d}" in existing_ids:
        n += 1
    return f"failure-{n:03d}"


def failure_key(messages, failed_eval_ids) -> str:
    """Stable dedup key: sha256 over the normalized full message list plus the
    sorted failure types. Public because the loop and the tests both need to
    reason about identity without duplicating the rule.

    Full message list, not the first message: a multi-turn conflict case and a
    single-turn case that open the same way are different cases. Failure types
    included: the same conversation failing groundedness and failing tool usage
    are two distinct things to fix."""
    payload = json.dumps(
        {
            "messages": [_normalize(m) for m in messages],
            "failure_types": sorted({str(e) for e in failed_eval_ids if e}),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _existing_key(conv: dict) -> str:
    """Dedup key for a row already in the dataset, old shape or new.

    New rows carry their key. Legacy failure-append rows record the failing eval
    in eval_targets, so that is their failure type. shipped/synthetic rows are
    inputs, not failures, so their failure type set is empty and they never
    collide with a captured failure."""
    stored = conv.get("dedup_key")
    if isinstance(stored, str) and stored:
        return stored
    failed = conv.get("failed_eval_ids")
    if failed is None:
        failed = conv.get("eval_targets", []) if conv.get("source") == _FAILURE_SOURCE else []
    return failure_key(conv["messages"], failed)


def _as_str_list(value, single) -> list:
    """Coerce a list-or-single-value field to a list of non-empty strings."""
    if value is None:
        value = [single] if single else []
    elif not isinstance(value, list):
        value = [value]
    return [str(v) for v in value if v not in (None, "")]


def _coerce_case(f: dict) -> dict:
    """Normalize one failure into the structured shape. Accepts the legacy
    {"user_input", "eval_id", "reason"} and the structured
    {"messages", "failed_eval_ids", "failure_reasons", ...}. Returns a new dict;
    the caller's input is never mutated."""
    if not isinstance(f, dict):
        raise TypeError("each failure must be a dict")
    messages = f.get("messages")
    if messages is None:
        messages = _as_str_list(None, f.get("user_input"))
    if not isinstance(messages, list) or not messages or not all(
        isinstance(m, str) and m.strip() for m in messages
    ):
        raise ValueError("failure needs a non-empty 'messages' list (or a 'user_input' string)")
    return {
        "messages": [*messages],
        "failed_eval_ids": sorted(set(_as_str_list(f.get("failed_eval_ids"), f.get("eval_id")))),
        "failure_reasons": _as_str_list(f.get("failure_reasons"), f.get("reason")),
        "assistant_reply": f.get("assistant_reply") or "",
        "tool_calls": list(f.get("tool_calls") or []),
        "tool_outputs": list(f.get("tool_outputs") or []),
        "source_trace_id": f.get("source_trace_id") or f.get("trace_id"),
        "source_session_id": f.get("source_session_id") or f.get("session_id"),
        "pii_redacted": bool(f.get("pii_redacted", False)),
    }


def _build_row(cid: str, case: dict, key: str) -> dict:
    """Build the appended conversation row. The five base keys keep their old
    meaning so every existing consumer (run_experiment replay, push_to_arize)
    still works; the replay keys are additive."""
    tags = [_FAILURE_SOURCE, *[f"eval:{e}" for e in case["failed_eval_ids"]]]
    return {
        "id": cid,
        "messages": case["messages"],
        "tags": tags,
        "eval_targets": case["failed_eval_ids"],
        "source": _FAILURE_SOURCE,
        "assistant_reply": case["assistant_reply"],
        "tool_calls": case["tool_calls"],
        "tool_outputs": case["tool_outputs"],
        "failed_eval_ids": case["failed_eval_ids"],
        "failure_reasons": case["failure_reasons"],
        "source_trace_id": case["source_trace_id"],
        "source_session_id": case["source_session_id"],
        "review_status": _REVIEW_PENDING,
        # Never auto-generated: a failed trace shows what happened, not what
        # should have. A human fills this in during review.
        "expected_behavior": None,
        "pii_redacted": case["pii_redacted"],
        "dedup_key": key,
    }


def append_failures(path, failures, today: str = None) -> str:
    """Append novel failures to the dataset and return the resulting version.

    `failures` accepts both the legacy {"user_input", "eval_id", "reason"} shape
    and the structured shape (see the module docstring). Duplicates, by the
    dedup_key over the full message list plus the failure types, are dropped.
    No-op when nothing is novel. `today` defaults to the current date and exists
    for deterministic tests.
    """
    p = Path(path)
    data = load_dataset(p)
    today = today or date.today().isoformat()

    existing_convs = data["conversations"]
    seen = {_existing_key(c) for c in existing_convs}
    existing_ids = {c["id"] for c in existing_convs}

    new_convs = []
    for f in failures:
        case = _coerce_case(f)
        key = failure_key(case["messages"], case["failed_eval_ids"])
        if key in seen:
            continue  # dedup: this exact failure is already represented
        seen.add(key)
        cid = _next_failure_id(existing_ids)
        existing_ids.add(cid)
        new_convs.append(_build_row(cid, case, key))

    if not new_convs:
        return data["version"]  # no-op: nothing novel, leave file untouched

    new_version = _bump_version(data["version"], today)
    # Immutable build: new dict, new list; the loaded structures are not mutated.
    new_data = {
        **data,
        "version": new_version,
        "conversations": [*existing_convs, *new_convs],
    }
    p.write_text(json.dumps(new_data, indent=2, ensure_ascii=True) + "\n")
    return new_version
