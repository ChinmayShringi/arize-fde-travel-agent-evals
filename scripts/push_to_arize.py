"""Push the golden dataset and every offline eval score into Arize AX.

Two subcommands:

    push-dataset   golden_dataset.json  ->  AX dataset "golden-dataset-v1-2026-07-19"
    push-evals     five scored runs     ->  eval labels/scores/explanations on the
                                            ROOT span of each trace in project "travel-agent"

Usage:
    uv run python scripts/push_to_arize.py push-dataset
    uv run python scripts/push_to_arize.py push-evals
    uv run python scripts/push_to_arize.py push-evals --run baseline control-v0

Discovery notes (arize 8.40.0, verified against installed source + a live export):
  - Dataset upload:  ArizeClient().datasets.create(name=, space=, examples=[dict, ...])
                     idempotency read-back via .datasets.list(name=, space=)
  - Span eval upload: ArizeClient().spans.update_evaluations(space_id=, project_name=,
                     dataframe=<df with 'context.span_id' + 'eval.<NAME>.{label,score,explanation}'>)
  - Arize stores span_id / trace_id as bare hex WITHOUT the OTel '0x' prefix, so we strip it.
  - The root span of every trace is the single parent-less 'agent_turn' (CHAIN) span.
  - An eval column set that is entirely null for a span is valid (means "no eval"), so a
    wide one-row-per-span frame with NaNs where an eval does not apply is accepted.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Repo-relative: scripts/ lives directly under the repo root, and docs/ is inside
# the repo, so every path below survives a fresh clone to any location.
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

DATASET_NAME = "golden-dataset-v1-2026-07-19"
GOLDEN_PATH = REPO_ROOT / "evals" / "golden_dataset.json"

PROJECT_NAME = "travel-agent"
EXPLANATION_MAX_CHARS = 1000

# Each run: display name -> (spans.jsonl, results.jsonl).
RUNS: dict[str, tuple[Path, Path]] = {
    "baseline": (
        REPO_ROOT / "docs/baseline/2026-07-19/spans.jsonl",
        REPO_ROOT / "docs/evals/baseline-2026-07-19/results.jsonl",
    ),
    "control-v0": (
        REPO_ROOT / "docs/experiments/control-v0/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-control-v0/results.jsonl",
    ),
    "candidate-A-prompt": (
        REPO_ROOT / "docs/experiments/candidate-A-prompt/spans.jsonl",
        REPO_ROOT / "docs/experiments/candidate-A-prompt/evals/results.jsonl",
    ),
    "candidate-B-toolfix": (
        REPO_ROOT / "docs/experiments/candidate-B-toolfix/spans.jsonl",
        REPO_ROOT / "docs/experiments/candidate-B-toolfix/evals/results.jsonl",
    ),
    "candidate-AB-combined": (
        REPO_ROOT / "docs/experiments/candidate-AB-combined/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-candidate-AB-combined/results.jsonl",
    ),
    "candidate-C-concise": (
        REPO_ROOT / "docs/experiments/candidate-C-concise/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-candidate-C-concise/results.jsonl",
    ),
    "model-sonnet-5": (
        REPO_ROOT / "docs/experiments/model-sonnet-5/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-model-sonnet-5/results.jsonl",
    ),
    "model-opus-4-8": (
        REPO_ROOT / "docs/experiments/model-opus-4-8/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-model-opus-4-8/results.jsonl",
    ),
    "model-sonnet-5-fixed": (
        REPO_ROOT / "docs/experiments/model-sonnet-5-fixed/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-model-sonnet-5-fixed/results.jsonl",
    ),
    "model-opus-4-8-fixed": (
        REPO_ROOT / "docs/experiments/model-opus-4-8-fixed/spans.jsonl",
        REPO_ROOT / "docs/evals/e10-scoring-model-opus-4-8-fixed/results.jsonl",
    ),
    "control-v0-cachetest": (
        REPO_ROOT / "docs/experiments/control-v0-cachetest/spans.jsonl",
        REPO_ROOT / "docs/experiments/control-v0-cachetest/evals/results.jsonl",
    ),
    "control-v0-cached2": (
        REPO_ROOT / "docs/experiments/control-v0-cached2/spans.jsonl",
        REPO_ROOT / "docs/experiments/control-v0-cached2/evals/results.jsonl",
    ),
}

# LLM-as-judge scores (E8/E9) for the baseline run live only in this calibration sheet.
# eval_id -> human-readable eval name; matches evals/run_judges.py ("E8 clarification, E9 scope").
JUDGE_CSV = REPO_ROOT / "evals" / "calibration" / "baseline_provisional.csv"
JUDGE_NAMES = {"E8": "clarification", "E9": "scope"}


def _fail(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _load_env() -> tuple[str, str]:
    """Load .env with an explicit path and return (api_key, space_id)."""
    from dotenv import load_dotenv

    if not ENV_PATH.exists():
        _fail(f"env file not found: {ENV_PATH}")
    load_dotenv(str(ENV_PATH))
    api_key = os.environ.get("ARIZE_API_KEY")
    space_id = os.environ.get("ARIZE_SPACE_ID")
    if not api_key:
        _fail("ARIZE_API_KEY missing from environment")
    if not space_id:
        _fail("ARIZE_SPACE_ID missing from environment")
    return api_key, space_id


def _client(api_key: str):
    from arize.client import ArizeClient

    return ArizeClient(api_key=api_key)


def _strip0x(value: str) -> str:
    return value[2:] if value.startswith("0x") else value


def _truncate(text: str) -> str:
    text = text or ""
    if len(text) <= EXPLANATION_MAX_CHARS:
        return text
    return text[: EXPLANATION_MAX_CHARS - 3] + "..."


# --------------------------------------------------------------------------- #
# push-dataset
# --------------------------------------------------------------------------- #
def _build_dataset_rows() -> list[dict]:
    """Flatten each conversation to one row (lists are JSON-encoded)."""
    data = json.loads(GOLDEN_PATH.read_text())
    rows: list[dict] = []
    for conv in data["conversations"]:
        messages = conv.get("messages") or [""]
        rows.append(
            {
                # 'id' is a reserved/system field on create, so the golden id is
                # carried as 'conversation_id'.
                "conversation_id": conv["id"],
                "input": messages[0],
                "tags": json.dumps(conv.get("tags", [])),
                "eval_targets": json.dumps(conv.get("eval_targets", [])),
                "source": conv.get("source", ""),
                "dataset_version": data.get("version", ""),
            }
        )
    return rows


def cmd_push_dataset(client, space_id: str) -> int:
    rows = _build_dataset_rows()
    print(f"push-dataset: {len(rows)} rows flattened from {GOLDEN_PATH}")

    existing = client.datasets.list(name=DATASET_NAME, space=space_id)
    match = next(
        (d for d in existing.datasets if d.name == DATASET_NAME), None
    )
    if match is not None:
        print(
            f"push-dataset: dataset already exists, skipping create (idempotent)\n"
            f"  name={match.name}\n  id={match.id}"
        )
        return 0

    created = client.datasets.create(
        name=DATASET_NAME, space=space_id, examples=rows
    )
    print(
        f"push-dataset: created dataset\n  name={created.name}\n  id={created.id}\n"
        f"  examples={len(rows)}"
    )
    return 0


# --------------------------------------------------------------------------- #
# push-evals
# --------------------------------------------------------------------------- #
def _root_span_map(spans_path: Path) -> dict[str, str]:
    """trace_id(no 0x) -> root span_id(no 0x); root == parent-less span."""
    mapping: dict[str, str] = {}
    with spans_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            span = json.loads(line)
            if span.get("parent_id") in (None, ""):
                ctx = span["context"]
                mapping[_strip0x(ctx["trace_id"])] = _strip0x(ctx["span_id"])
    return mapping


def _eval_records_for_run(run_name: str) -> list[dict]:
    """Return normalized eval records: {trace_id(no0x), eval_name, label, score, explanation}."""
    _, results_path = RUNS[run_name]
    records: list[dict] = []
    with results_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            passed = bool(row["passed"])
            records.append(
                {
                    "trace_id": _strip0x(row["trace_id"]),
                    "eval_name": f"{row['eval_id']} {row['name']}",
                    "label": "pass" if passed else "fail",
                    "score": 1.0 if passed else 0.0,
                    "explanation": _truncate(row.get("reason", "")),
                }
            )
    if run_name == "baseline":
        records.extend(_baseline_judge_records())
    return records


def _baseline_judge_records() -> list[dict]:
    """E8/E9 LLM-as-judge scores for baseline, read from the calibration CSV."""
    if not JUDGE_CSV.exists():
        print(f"  WARN: judge CSV not found, skipping E8/E9: {JUDGE_CSV}")
        return []
    records: list[dict] = []
    with JUDGE_CSV.open(newline="") as fh:
        for row in csv.DictReader(fh):
            eval_id = row["eval_id"]
            name = JUDGE_NAMES.get(eval_id)
            if name is None:
                continue
            passed = row["judge_passed"].strip().lower() == "pass"
            records.append(
                {
                    "trace_id": _strip0x(row["trace_id"]),
                    "eval_name": f"{eval_id} {name}",
                    "label": "pass" if passed else "fail",
                    "score": 1.0 if passed else 0.0,
                    "explanation": _truncate(row.get("judge_reason", "")),
                }
            )
    return records


def _build_evals_frame(run_name: str):
    """Build a wide one-row-per-root-span eval frame plus a reject report."""
    import pandas as pd

    spans_path, _ = RUNS[run_name]
    roots = _root_span_map(spans_path)
    records = _eval_records_for_run(run_name)

    span_rows: dict[str, dict] = {}
    logged = 0
    rejects: list[str] = []
    for rec in records:
        span_id = roots.get(rec["trace_id"])
        if span_id is None:
            rejects.append(
                f"{rec['eval_name']} trace={rec['trace_id']} (no root span in spans.jsonl)"
            )
            continue
        row = span_rows.setdefault(span_id, {"context.span_id": span_id})
        base = f"eval.{rec['eval_name']}"
        row[f"{base}.label"] = rec["label"]
        row[f"{base}.score"] = rec["score"]
        row[f"{base}.explanation"] = rec["explanation"]
        logged += 1

    frame = pd.DataFrame(list(span_rows.values()))
    return frame, logged, len(span_rows), rejects


def _summarize_response(resp: dict) -> str:
    updated = resp.get("spans_updated", resp.get("records_updated"))
    processed = resp.get("spans_processed")
    errors = resp.get("errors") or []
    return f"spans_updated={updated} spans_processed={processed} errors={len(errors)}"


def cmd_push_evals(client, space_id: str, run_names: list[str]) -> int:
    import pandas as pd  # noqa: F401 (ensures dependency present early)

    hard_failure = False
    print(f"push-evals: project={PROJECT_NAME} runs={run_names}")
    for run_name in run_names:
        frame, logged, n_spans, rejects = _build_evals_frame(run_name)
        eval_cols = [c for c in frame.columns if c != "context.span_id"]
        n_eval_names = len({c.rsplit(".", 1)[0] for c in eval_cols})
        print(
            f"\n[{run_name}] {logged} eval results across {n_spans} root spans, "
            f"{n_eval_names} distinct eval names"
        )
        if frame.empty:
            print(f"[{run_name}] nothing to log")
            continue
        try:
            resp = client.spans.update_evaluations(
                space_id=space_id,
                project_name=PROJECT_NAME,
                dataframe=frame,
            )
            print(f"[{run_name}] logged OK: {_summarize_response(resp)}")
        except Exception as exc:  # noqa: BLE001
            hard_failure = True
            print(f"[{run_name}] FAILED: {type(exc).__name__}: {exc}")
        if rejects:
            print(f"[{run_name}] {len(rejects)} rejected (no matching root span):")
            for r in rejects:
                print(f"    - {r}")

    return 1 if hard_failure else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("push-dataset", help="upload golden dataset to Arize AX")
    evals = sub.add_parser("push-evals", help="log eval scores onto root spans")
    evals.add_argument(
        "--run",
        nargs="+",
        choices=list(RUNS.keys()),
        default=list(RUNS.keys()),
        help="subset of runs to push (default: all five)",
    )
    args = parser.parse_args(argv)

    api_key, space_id = _load_env()
    client = _client(api_key)

    if args.command == "push-dataset":
        return cmd_push_dataset(client, space_id)
    if args.command == "push-evals":
        return cmd_push_evals(client, space_id, args.run)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
