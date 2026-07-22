"""CLI runner for the LLM-as-judge evals (E8 clarification, E9 scope).

Usage:
    uv run python evals/run_judges.py <spans.jsonl> <output_dir>

Runs every judge in judges.EVALS over every trace and writes, into <output_dir>:
  - results.jsonl        same row shape as run_evals.py (trace context + result)
  - summary.md           same table + failures layout as run_evals.py
  - calibration_sheet.csv one row per judged trace for human review

The summary table is also printed to stdout. Like run_evals.py, judge failures
are data: the process exits 0 whenever it ran to completion, and 2 only on an IO
or import failure (unreadable spans, a broken judges module, or an unwritable
output dir). A judge raising on one trace is recorded as a failed result rather
than aborting the whole run.

calibration_sheet.csv columns (order fixed; the first seven are the required
schema, the last is an honesty-preserving extra):
  trace_id, user_input, eval_id, judge_passed, judge_reason,
  human_label (EMPTY), notes (EMPTY), assistant_proposed_label (EMPTY)
The human_label column is always written EMPTY. assistant_proposed_label is a
clearly named, also-empty column that a reviewer (human or assistant) may fill
to compute a provisional agreement rate with evals/calibration/agreement.py.
"""

import csv
import json
import sys
from pathlib import Path

# Sibling modules resolve because evals/ is on sys.path under `python evals/...`.
from trace_model import load_traces
from context import EvalContext
from run_evals import (
    _render_summary_md,
    _render_summary_table,
    _summarize,
    _write_results,
)

CALIBRATION_HEADER = [
    "trace_id",
    "user_input",
    "eval_id",
    "judge_passed",
    "judge_reason",
    "human_label",
    "notes",
    "assistant_proposed_label",
]


def _load_judges() -> list:
    """Import the judge EVALS lists (judges: E8/E9; e_tone: E11) in order,
    raising ImportError naming the offending module on failure."""
    import importlib

    evals = []
    for name in ("judges", "e_tone"):
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - re-raised with module name
            raise ImportError(f"judge module '{name}' failed to import: {exc}") from exc
        module_evals = getattr(module, "EVALS", None)
        if module_evals is None:
            raise ImportError(f"judge module '{name}' defines no EVALS list")
        evals.extend(module_evals)
    return evals


def _run_all(traces, ctx, evals) -> list:
    """Run every judge on every trace; a judge raising is recorded as a failed
    result (attribution n/a: a judging-infra failure is not a model fault)."""
    results = []
    for trace in traces:
        for fn in evals:
            try:
                result = fn(trace, ctx)
            except Exception as exc:  # noqa: BLE001 - surfaced as a failed result
                result = {
                    "eval_id": getattr(fn, "__name__", "unknown"),
                    "name": getattr(fn, "__name__", "unknown"),
                    "passed": False,
                    "reason": f"judge raised: {exc}",
                    "attribution": "n/a",
                    "evidence": {"error": str(exc)},
                }
            if result is None:
                continue
            results.append(
                {
                    "trace_id": trace.trace_id,
                    "user_input": trace.user_input,
                    **result,
                }
            )
    return results


def _write_calibration_sheet(results: list, out_dir: Path) -> None:
    """One row per judged trace; human_label / notes / assistant_proposed_label
    are written EMPTY for a reviewer to fill later."""
    with (out_dir / "calibration_sheet.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CALIBRATION_HEADER)
        for r in results:
            writer.writerow(
                [
                    r.get("trace_id", ""),
                    (r.get("user_input", "") or "")[:100],
                    r.get("eval_id", ""),
                    "pass" if r.get("passed") else "fail",
                    r.get("reason", ""),
                    "",  # human_label - stays EMPTY by contract
                    "",  # notes - EMPTY
                    "",  # assistant_proposed_label - EMPTY
                ]
            )


def main(argv: list) -> int:
    if len(argv) != 3:
        print(
            "usage: uv run python evals/run_judges.py <spans.jsonl> <output_dir>",
            file=sys.stderr,
        )
        return 2

    spans_path = Path(argv[1])
    out_dir = Path(argv[2])

    try:
        evals = _load_judges()
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
        _write_calibration_sheet(results, out_dir)
    except OSError as exc:
        print(f"io error: failed to write output: {exc}", file=sys.stderr)
        return 2

    print(_render_summary_table(summary))
    print(f"\n{len(traces)} trace(s), {len(results)} result(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
