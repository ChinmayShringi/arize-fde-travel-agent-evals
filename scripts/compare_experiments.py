"""Compare two or more experiment runs side by side.

    uv run python scripts/compare_experiments.py <dir1> <dir2> [<dir3> ...] [--out <file.md>]

The FIRST directory is the control; every other variant is reported as a delta
against it. For each run directory the tool reads:
    <dir>/evals/results.jsonl   (falls back to <dir>/results.jsonl)  -> eval pass rates
    <dir>/manifest.json         (optional)                          -> variant label
    <dir>/spans.jsonl           (optional)                          -> telemetry

It renders a markdown report to stdout and, with --out, to a file:
  - one row per eval (E1..E7): applicable count and pass-rate per variant, with
    the pass-rate delta versus the control
  - a telemetry block: median latency, total tokens, total cost, mean iterations

Telemetry needs spans; a directory without spans.jsonl (e.g. a raw baseline
evals dir) simply shows n/a for those cells, and the eval rows still render.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# trace_model lives in evals/ and is self-contained (stdlib only).
_EVALS_DIR = REPO_ROOT / "evals"
if str(_EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALS_DIR))

# Model is locked to claude-haiku-4-5 (see the project constitution). Pricing is
# USD per million tokens; used only to turn measured token counts into a cost.
PRICE_PER_MTOK = {"input": 1.00, "output": 5.00}

# Canonical eval ordering for the table; any eval id not listed is appended.
EVAL_ORDER = ("E1", "E2", "E3", "E4", "E5", "E6", "E7")


def _resolve_results(run_dir: Path) -> Path | None:
    for candidate in (run_dir / "evals" / "results.jsonl", run_dir / "results.jsonl"):
        if candidate.exists():
            return candidate
    return None


def _resolve_spans(run_dir: Path) -> Path | None:
    for candidate in (run_dir / "spans.jsonl", run_dir / "evals" / "spans.jsonl"):
        if candidate.exists():
            return candidate
    return None


def _load_manifest(run_dir: Path) -> dict:
    path = run_dir / "manifest.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _label(run_dir: Path, manifest: dict) -> str:
    return manifest.get("name") or run_dir.name


def _eval_stats(results_path: Path) -> dict:
    """Aggregate per eval_id: applicable count, passed count, name."""
    stats: dict = {}
    with results_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            eid = r.get("eval_id", "unknown")
            slot = stats.setdefault(eid, {"name": r.get("name", ""), "applicable": 0, "passed": 0})
            slot["applicable"] += 1
            if r.get("passed"):
                slot["passed"] += 1
    return stats


def _telemetry(spans_path: Path | None) -> dict | None:
    if spans_path is None:
        return None
    from trace_model import load_traces  # imported here so a missing evals dir is not fatal at import

    traces = load_traces(spans_path)
    if not traces:
        return {"traces": 0, "median_latency_ms": None, "total_tokens": 0, "cost_usd": 0.0, "mean_iterations": None}

    latencies = [t.latency_ms for t in traces if t.latency_ms is not None]
    prompt_tokens = sum(t.total_prompt_tokens for t in traces)
    completion_tokens = sum(t.total_completion_tokens for t in traces)
    iterations = [t.iterations for t in traces if t.iterations is not None]
    cost = (
        prompt_tokens / 1_000_000 * PRICE_PER_MTOK["input"]
        + completion_tokens / 1_000_000 * PRICE_PER_MTOK["output"]
    )
    return {
        "traces": len(traces),
        "median_latency_ms": statistics.median(latencies) if latencies else None,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": cost,
        "mean_iterations": statistics.mean(iterations) if iterations else None,
    }


def _pass_rate(slot: dict) -> float | None:
    appl = slot["applicable"]
    return (slot["passed"] / appl * 100) if appl else None


def _fmt_rate(rate: float | None) -> str:
    return f"{rate:.0f}%" if rate is not None else "n/a"


def _load_runs(dirs: list) -> list:
    runs = []
    for d in dirs:
        run_dir = Path(d)
        results_path = _resolve_results(run_dir)
        if results_path is None:
            print(f"error: no results.jsonl under {run_dir} (looked in evals/ and dir root)", file=sys.stderr)
            raise SystemExit(2)
        manifest = _load_manifest(run_dir)
        runs.append(
            {
                "dir": run_dir,
                "label": _label(run_dir, manifest),
                "manifest": manifest,
                "stats": _eval_stats(results_path),
                "telemetry": _telemetry(_resolve_spans(run_dir)),
            }
        )
    return runs


def _render(runs: list) -> str:
    control = runs[0]
    labels = [r["label"] for r in runs]
    lines = ["# Experiment Comparison", ""]
    lines.append(f"Control (baseline for deltas): **{control['label']}**")
    lines.append("")

    # Ordered union of eval ids across every run.
    seen = []
    for eid in EVAL_ORDER:
        if any(eid in r["stats"] for r in runs):
            seen.append(eid)
    for r in runs:
        for eid in r["stats"]:
            if eid not in seen:
                seen.append(eid)

    lines.append("## Evals")
    lines.append("")
    header = ["Eval", "Name"] + labels
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for eid in seen:
        name = next((r["stats"][eid]["name"] for r in runs if eid in r["stats"]), "")
        control_slot = control["stats"].get(eid)
        control_rate = _pass_rate(control_slot) if control_slot else None
        row = [eid, name or ""]
        for i, r in enumerate(runs):
            slot = r["stats"].get(eid)
            if slot is None:
                row.append("-")
                continue
            rate = _pass_rate(slot)
            cell = f"{slot['passed']}/{slot['applicable']} ({_fmt_rate(rate)})"
            if i > 0 and rate is not None and control_rate is not None:
                cell += f" [d{rate - control_rate:+.0f}pp]"
            row.append(cell)
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("## Telemetry")
    lines.append("")
    thead = ["Metric"] + labels
    lines.append("| " + " | ".join(thead) + " |")
    lines.append("|" + "|".join(["---"] * len(thead)) + "|")

    def tel_row(metric: str, fmt) -> str:
        cells = [metric]
        for r in runs:
            tel = r["telemetry"]
            cells.append(fmt(tel) if tel is not None else "n/a")
        return "| " + " | ".join(cells) + " |"

    lines.append(
        tel_row(
            "Median latency (ms)",
            lambda t: f"{t['median_latency_ms']:.0f}" if t.get("median_latency_ms") is not None else "n/a",
        )
    )
    lines.append(tel_row("Total tokens", lambda t: f"{t['total_tokens']:,}"))
    lines.append(tel_row("Total cost (USD)", lambda t: f"${t['cost_usd']:.4f}"))
    lines.append(
        tel_row(
            "Mean iterations",
            lambda t: f"{t['mean_iterations']:.2f}" if t.get("mean_iterations") is not None else "n/a",
        )
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="compare_experiments.py",
        description="Compare 2+ experiment run directories (first dir is the control).",
    )
    parser.add_argument("dirs", nargs="+", help="Experiment out dirs; the first is the control.")
    parser.add_argument("--out", help="Also write the markdown report to this file.")
    args = parser.parse_args(argv)

    if len(args.dirs) < 2:
        print("error: need at least 2 experiment directories to compare", file=sys.stderr)
        return 2

    runs = _load_runs(args.dirs)
    report = _render(runs)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
