"""Replay recorded OTel spans back into Arize AX with their ORIGINAL ids, times,
names, attributes and parent-child structure.

Motivation: two baseline traces never reached AX because their final export batch
was lost at process exit, even though the spans were captured on disk in
docs/baseline/2026-07-19/spans.jsonl. This script re-emits exactly those spans so
they join the other baseline traces seamlessly (same trace/span ids -> the offline
eval push in scripts/push_to_arize.py then attaches their scores by span_id).

Usage:
    uv run python scripts/replay_spans_to_arize.py <spans.jsonl> <trace_id> [<trace_id> ...]

Trace ids may be given with or without the '0x' prefix; the JSONL stores them as
'0x'-prefixed lowercase hex.

Fidelity mechanics (verified against the installed SDK source, otel 1.44.0 /
arize 8.40.0):
  - Original ids are preserved with a custom IdGenerator whose generate_trace_id /
    generate_span_id pop from FIFO queues we prime in span-creation order. The SDK
    (opentelemetry/sdk/trace/__init__.py Tracer.start_span) calls generate_trace_id
    only for a parentless span and generate_span_id for every span, so priming the
    queues in creation order reproduces the recorded ids exactly.
  - A DEDICATED, non-global tracer provider is built via arize.otel.TracerProvider
    (the arize-aware provider that wires the GRPC exporter in __init__ and does NOT
    set itself as the global provider). This disturbs nothing else. register() was
    avoided because it does not forward an id_generator; constructing the arize
    TracerProvider directly is the cleaner supported mechanism that does.
  - Parent-child structure is rebuilt by starting each span inside the context of
    its already-created parent (trace.set_span_in_context), so the child inherits
    the recorded trace id and records the recorded parent span id. Roots are started
    with no parent context.
  - Original timing is preserved by converting the ISO start/end strings to epoch
    nanoseconds and passing them to start_span(start_time=) and span.end(end_time=).
  - All attributes are copied verbatim; recorded status code (OK/ERROR) is set
    (UNSET is the SDK default and left as-is).
"""

from __future__ import annotations

import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from opentelemetry.sdk.trace.id_generator import IdGenerator

# Repo-relative: scripts/ lives directly under the repo root, so this survives a
# fresh clone to any location.
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
PROJECT_NAME = "travel-agent"

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _norm(trace_or_span_id: str) -> str:
    """Normalize to the '0x'-prefixed lowercase form used inside the JSONL."""
    v = trace_or_span_id.strip().lower()
    return v if v.startswith("0x") else "0x" + v


def _iso_to_epoch_nanos(iso: str) -> int:
    """Convert an ISO-8601 UTC string (microsecond precision) to epoch nanos exactly."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = dt - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000


def _load_env() -> tuple[str, str]:
    from dotenv import load_dotenv

    if not ENV_PATH.exists():
        _fail(f"env file not found: {ENV_PATH}")
    load_dotenv(str(ENV_PATH))
    import os

    api_key = os.environ.get("ARIZE_API_KEY")
    space_id = os.environ.get("ARIZE_SPACE_ID")
    if not api_key:
        _fail("ARIZE_API_KEY missing from environment")
    if not space_id:
        _fail("ARIZE_SPACE_ID missing from environment")
    return api_key, space_id


def _load_spans(spans_path: Path, wanted: set[str]) -> dict[str, list[dict]]:
    """Return {trace_id(0x): [span_json, ...]} for the requested traces only."""
    by_trace: dict[str, list[dict]] = {}
    with spans_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            span = json.loads(line)
            tid = span["context"]["trace_id"].lower()
            if tid in wanted:
                by_trace.setdefault(tid, []).append(span)
    return by_trace


def _creation_order(spans: list[dict]) -> list[dict]:
    """Topologically order one trace's spans: parents strictly before children."""
    by_id = {s["context"]["span_id"]: s for s in spans}
    present = set(by_id)
    ordered: list[dict] = []
    emitted: set[str] = set()

    def visit(span: dict) -> None:
        sid = span["context"]["span_id"]
        if sid in emitted:
            return
        parent = span.get("parent_id")
        if parent in present and parent not in emitted:
            visit(by_id[parent])
        emitted.add(sid)
        ordered.append(span)

    # roots first for a stable, readable order
    for s in sorted(spans, key=lambda x: (x.get("parent_id") is not None, x["start_time"])):
        visit(s)
    return ordered


class _RecordedIdGenerator(IdGenerator):
    """IdGenerator that hands back recorded ids in the order spans are created.

    Subclasses opentelemetry.sdk.trace.id_generator.IdGenerator. generate_trace_id
    fires only for parentless spans (SDK behaviour), generate_span_id for every span,
    so both queues are primed in the exact span-creation order.
    """

    def __init__(self, trace_ids: list[int], span_ids: list[int]):
        self._trace_ids = deque(trace_ids)
        self._span_ids = deque(span_ids)

    def generate_span_id(self) -> int:
        if not self._span_ids:
            raise RuntimeError("span-id queue exhausted; creation order mismatch")
        return self._span_ids.popleft()

    def generate_trace_id(self) -> int:
        if not self._trace_ids:
            raise RuntimeError("trace-id queue exhausted; creation order mismatch")
        return self._trace_ids.popleft()

    def is_trace_id_random(self) -> bool:
        return False


def _span_kind(kind_str: str):
    from opentelemetry.trace import SpanKind

    name = kind_str.rsplit(".", 1)[-1]  # "SpanKind.INTERNAL" -> "INTERNAL"
    return getattr(SpanKind, name, SpanKind.INTERNAL)


def _set_status(span, status: dict) -> None:
    from opentelemetry.trace import Status, StatusCode

    code = (status or {}).get("status_code", "UNSET")
    if code == "OK":
        span.set_status(Status(StatusCode.OK))
    elif code == "ERROR":
        span.set_status(Status(StatusCode.ERROR, (status or {}).get("description") or ""))
    # UNSET: leave the SDK default untouched


def replay(spans_path: Path, trace_ids: list[str]) -> int:
    from opentelemetry import trace as trace_api

    wanted = {_norm(t) for t in trace_ids}
    by_trace = _load_spans(spans_path, wanted)

    missing = wanted - set(by_trace)
    if missing:
        _fail(f"trace ids not found in {spans_path}: {sorted(missing)}")

    # Deterministic order across traces: as requested on the CLI.
    ordered_traces = [t for t in (_norm(x) for x in trace_ids)]
    # de-dup while preserving order
    seen: set[str] = set()
    ordered_traces = [t for t in ordered_traces if not (t in seen or seen.add(t))]

    # Build the global creation order + prime the id queues.
    creation: list[dict] = []
    trace_id_queue: list[int] = []
    span_id_queue: list[int] = []
    for tid in ordered_traces:
        for span in _creation_order(by_trace[tid]):
            creation.append(span)
            if span.get("parent_id") in (None, "") or span["parent_id"] not in {
                s["context"]["span_id"] for s in by_trace[tid]
            }:
                # parentless within this trace -> SDK will call generate_trace_id
                trace_id_queue.append(int(span["context"]["trace_id"], 16))
            span_id_queue.append(int(span["context"]["span_id"], 16))

    gen = _RecordedIdGenerator(trace_id_queue, span_id_queue)

    api_key, space_id = _load_env()
    from arize.otel import TracerProvider
    from openinference.semconv.resource import ResourceAttributes
    from opentelemetry.sdk.resources import Resource

    # The arize TracerProvider only injects the project-name resource attribute when
    # `resource` is left unset, but binding against the base signature fills in a
    # default Resource first, so we must build and pass it ourselves (same shape
    # register() uses: {openinference.project.name: <project>}). Without it the
    # collector rejects spans ("model_id ... or arize.project.name ... is required").
    resource = Resource.create({ResourceAttributes.PROJECT_NAME: PROJECT_NAME})
    provider = TracerProvider(
        space_id=space_id,
        api_key=api_key,
        project_name=PROJECT_NAME,
        resource=resource,
        id_generator=gen,
        verbose=False,
    )
    tracer = provider.get_tracer("replay_spans_to_arize")

    created: dict[str, object] = {}  # orig span_id(0x) -> live Span
    trace_local_ids = {
        tid: {s["context"]["span_id"] for s in by_trace[tid]} for tid in ordered_traces
    }

    # Pass 1: start every span in creation order (consumes the id queues in lockstep).
    for span in creation:
        tid = span["context"]["trace_id"].lower()
        sid = span["context"]["span_id"]
        parent_id = span.get("parent_id")
        if parent_id in (None, "") or parent_id not in trace_local_ids[tid]:
            ctx = None
        else:
            ctx = trace_api.set_span_in_context(created[parent_id])

        started = tracer.start_span(
            name=span["name"],
            context=ctx,
            kind=_span_kind(span.get("kind", "SpanKind.INTERNAL")),
            attributes=span.get("attributes") or {},
            start_time=_iso_to_epoch_nanos(span["start_time"]),
        )
        _set_status(started, span.get("status") or {})
        created[sid] = started

        got_tid = f"0x{started.get_span_context().trace_id:032x}"
        got_sid = f"0x{started.get_span_context().span_id:016x}"
        if got_tid != span["context"]["trace_id"].lower() or got_sid != sid.lower():
            _fail(
                f"id mismatch on {span['name']}: "
                f"wanted trace={span['context']['trace_id']} span={sid}, "
                f"got trace={got_tid} span={got_sid}"
            )

    # Pass 2: end each span at its recorded end time (children before parents so a
    # parent never ends before its child).
    for span in reversed(creation):
        created[span["context"]["span_id"]].end(
            end_time=_iso_to_epoch_nanos(span["end_time"])
        )

    print(
        f"replay: recreated {len(creation)} spans across {len(ordered_traces)} traces "
        f"with original ids/times/attributes"
    )
    for tid in ordered_traces:
        roots = [s for s in by_trace[tid] if s.get("parent_id") in (None, "")]
        for r in roots:
            print(
                f"  trace {tid[2:]}  root '{r['name']}' span {r['context']['span_id'][2:]}"
                f"  start {r['start_time']}"
            )

    ok = provider.force_flush(timeout_millis=30000)
    provider.shutdown()
    if not ok:
        _fail("force_flush timed out; spans may not have been exported")
    print("replay: force_flush OK, spans exported to Arize AX")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _fail(
            "usage: replay_spans_to_arize.py <spans.jsonl> <trace_id> [<trace_id> ...]"
        )
    spans_path = Path(argv[0])
    if not spans_path.exists():
        _fail(f"spans file not found: {spans_path}")
    return replay(spans_path, argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
