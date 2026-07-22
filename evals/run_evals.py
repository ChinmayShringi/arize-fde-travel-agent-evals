"""CLI runner for the deterministic eval suite.

Usage:
    uv run python evals/run_evals.py <spans.jsonl> <output_dir>

Loads traces via load_traces and the fixture context via EvalContext.load(),
runs every eval from e_grounding, e_toolcalls, and e_guardrails on every trace,
and writes results.jsonl plus a summary.md to <output_dir>. The summary table is
also printed to stdout.

Each results.jsonl row carries a "trace_context" block (full multi-turn user
history, assistant reply, tool calls and tool outputs, PII flag) so a failing row
is enough on its own to build a replayable dataset case. The block is additive:
every key that existed before is still present and unchanged.

Eval failures are data, not runner errors: the process exits 0 whenever it ran to
completion. It exits 2 only on an IO or import failure (a broken/missing eval
module, or an unreadable spans file), and names the module or path that failed so
the fault is not swallowed silently.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Sibling modules (trace_model, context, e_*) resolve because the script's own
# directory is on sys.path when run as `python evals/run_evals.py`.
from context import EvalContext
from agent.redaction import redact
from trace_model import load_traces

# Eval modules are imported inside main() so a broken module is reported by name.
_EVAL_MODULES = ("e_grounding", "e_toolcalls", "e_guardrails", "e_conflict")


def _redact_value(value):
    """Recursively redact JSON-like output before it reaches an eval artifact."""
    if isinstance(value, str):
        clean, findings = redact(value)
        return clean, findings
    if isinstance(value, list):
        cleaned = [_redact_value(item) for item in value]
        return [item for item, _ in cleaned], [kind for _, kinds in cleaned for kind in kinds]
    if isinstance(value, dict):
        cleaned = {key: _redact_value(item) for key, item in value.items()}
        return (
            {key: item for key, (item, _) in cleaned.items()},
            [kind for _, kinds in cleaned.values() for kind in kinds],
        )
    return value, []


def _sanitize_result(result: dict) -> dict:
    """Return an artifact-safe result without mutating the evaluator output."""
    safe, findings = _redact_value(result)
    if not findings:
        return safe
    trace_context = safe.get("trace_context")
    if not isinstance(trace_context, dict):
        return safe
    pii_types = list(dict.fromkeys([*trace_context.get("pii_types", []), *findings]))
    return {
        **safe,
        "trace_context": {
            **trace_context,
            "pii_redacted": True,
            "pii_types": pii_types,
        },
    }


def _load_evals() -> list:
    """Import each eval module and collect its EVALS list, preserving order.
    Raises ImportError naming the offending module on any failure."""
    import importlib

    evals = []
    for name in _EVAL_MODULES:
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - re-raised with module name
            raise ImportError(f"eval module '{name}' failed to import: {exc}") from exc
        module_evals = getattr(module, "EVALS", None)
        if module_evals is None:
            raise ImportError(f"eval module '{name}' defines no EVALS list")
        evals.extend(module_evals)
    return evals


def _trace_context(trace) -> dict:
    """The replay payload for one trace, carried on every result row so a failing
    row can be turned into a replayable dataset case without re-reading spans.

    Only measured fields go in here. There is no "expected_behavior": it cannot
    be derived from a failed trace, and inventing one would be fabricated data."""
    return {
        "messages": trace.user_messages(),
        "assistant_reply": trace.reply,
        "session_id": trace.session_id,
        "prompt_version": trace.prompt_version,
        "agent_version": trace.agent_version,
        "pii_redacted": trace.pii_redacted,
        "pii_types": trace.pii_types,
        "tool_calls": trace.tool_call_payloads(),
        "tool_outputs": trace.tool_output_payloads(),
    }


def _run_all(traces, ctx, evals) -> list:
    """Run every eval on every trace; collect non-None results with trace context.
    An eval raising on one trace is recorded as an error result rather than
    aborting the run (failures, including crashes, are data)."""
    results = []
    for trace in traces:
        # Built once per trace, not once per eval: the payload is identical for
        # every eval on the same trace and can be large (full tool outputs).
        context = _trace_context(trace)
        for fn in evals:
            try:
                result = fn(trace, ctx)
            except Exception as exc:  # noqa: BLE001 - surfaced as a failed result
                result = {
                    "eval_id": getattr(fn, "__name__", "unknown"),
                    "name": getattr(fn, "__name__", "unknown"),
                    "passed": False,
                    "reason": f"eval raised: {exc}",
                    "attribution": "n/a",
                    "evidence": {"error": str(exc)},
                }
            if result is None:
                continue
            enriched = {
                "trace_id": trace.trace_id,
                "session_id": trace.session_id,
                "user_input": trace.user_input,
                "trace_context": context,
                **result,
            }
            results.append(_sanitize_result(enriched))
    return results


def _write_results(results: list, out_dir: Path) -> None:
    with (out_dir / "results.jsonl").open("w") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=True) + "\n")


def _summarize(results: list) -> list:
    """Aggregate per eval_id in first-seen order: applicable / pass / fail."""
    order = []
    stats = {}
    for r in results:
        eid = r.get("eval_id", "unknown")
        if eid not in stats:
            order.append(eid)
            stats[eid] = {"name": r.get("name", ""), "applicable": 0, "passed": 0, "failed": 0}
        stats[eid]["applicable"] += 1
        if r.get("passed"):
            stats[eid]["passed"] += 1
        else:
            stats[eid]["failed"] += 1
    return [{"eval_id": eid, **stats[eid]} for eid in order]


def _render_summary_md(summary: list, results: list) -> str:
    lines = ["# Eval Summary", ""]
    lines.append("| Eval | Name | Applicable | Pass | Fail | Pass rate |")
    lines.append("|------|------|-----------:|-----:|-----:|----------:|")
    for row in summary:
        appl = row["applicable"]
        rate = f"{(row['passed'] / appl * 100):.0f}%" if appl else "n/a"
        lines.append(
            f"| {row['eval_id']} | {row['name']} | {appl} | "
            f"{row['passed']} | {row['failed']} | {rate} |"
        )

    failures = [r for r in results if not r.get("passed")]
    lines.append("")
    lines.append(f"## Failures ({len(failures)})")
    lines.append("")
    if not failures:
        lines.append("None.")
    else:
        for r in failures:
            lines.append(f"- **{r.get('eval_id')} {r.get('name')}**")
            lines.append(f"  - user_input: {r.get('user_input', '')!r}")
            lines.append(f"  - reason: {r.get('reason', '')}")
            lines.append(f"  - attribution: {r.get('attribution', '')}")
    lines.append("")
    return "\n".join(lines)


def _render_summary_table(summary: list) -> str:
    header = f"{'Eval':<6} {'Name':<22} {'Appl':>5} {'Pass':>5} {'Fail':>5} {'Rate':>6}"
    lines = [header, "-" * len(header)]
    for row in summary:
        appl = row["applicable"]
        rate = f"{(row['passed'] / appl * 100):.0f}%" if appl else "n/a"
        lines.append(
            f"{row['eval_id']:<6} {row['name']:<22} {appl:>5} "
            f"{row['passed']:>5} {row['failed']:>5} {rate:>6}"
        )
    return "\n".join(lines)


def main(argv: list) -> int:
    if len(argv) != 3:
        print(
            "usage: uv run python evals/run_evals.py <spans.jsonl> <output_dir>",
            file=sys.stderr,
        )
        return 2

    spans_path = Path(argv[1])
    out_dir = Path(argv[2])

    try:
        evals = _load_evals()
    except ImportError as exc:
        print(f"import error: {exc}", file=sys.stderr)
        return 2

    try:
        traces = load_traces(spans_path)
        ctx = EvalContext.load()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"io error: failed to load traces/context: {exc}", file=sys.stderr)
        return 2

    results = _run_all(traces, ctx, evals)
    summary = _summarize(results)

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_results(results, out_dir)
        (out_dir / "summary.md").write_text(_render_summary_md(summary, results))
    except OSError as exc:
        print(f"io error: failed to write output: {exc}", file=sys.stderr)
        return 2

    print(_render_summary_table(summary))
    print(f"\n{len(traces)} trace(s), {len(results)} result(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
