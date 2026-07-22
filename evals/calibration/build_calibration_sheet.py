"""Build the live judge calibration sheet for the candidate-AB-combined run.

Usage:
    uv run python evals/calibration/build_calibration_sheet.py

Joins three sources and writes evals/calibration/calibration_sheet.csv:

  1. evals/calibration/blind_labels_candidate_AB.py - the independent labels,
     fixed BEFORE any judge verdict was read (see that module's docstring);
  2. docs/experiments/candidate-AB-combined/spans.jsonl - the conversations,
     read through evals/trace_model.py so the reply text is byte-identical to
     what the judge was shown;
  3. docs/evals/judges-candidate-AB/results.jsonl - the captured judge verdicts.

Nothing here calls a model. Sources 1-3 are all on disk.

Provenance rules baked into the output:
  - assistant_proposed_label holds the AI-proposed blind label.
  - human_label is PRE-POPULATED with that same value purely as a starting point
    so a reviewer only has to correct disagreements. human_reviewed is false and
    reviewer is empty on every row until a human actually flips them.
  - judge_label and agreement are DERIVED, never hand-entered. Re-running this
    script recomputes them; evals/calibration/compute_agreement.py recomputes
    agreement alone after a reviewer edits the sheet.

PII is redacted with agent.redaction.redact, the same boundary redactor the
agent uses, so the sheet cannot reintroduce PII the pipeline stripped.
"""

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "evals"))

from agent.redaction import redact  # noqa: E402
from trace_model import load_traces  # noqa: E402

from blind_labels_candidate_AB import CONTAMINATED, LABELS  # noqa: E402

SPANS = REPO / "docs/experiments/candidate-AB-combined/spans.jsonl"
JUDGE_RESULTS = REPO / "docs/evals/judges-candidate-AB/results.jsonl"
OUT = Path(__file__).resolve().parent / "calibration_sheet.csv"

SOURCE_RUN = "candidate-AB-combined"
REPLY_EXCERPT_CHARS = 400

HEADER = [
    "eval_id",
    "trace_id",
    "session_id",
    "user_input_redacted",
    "assistant_reply_excerpt",
    "assistant_proposed_label",
    "proposed_reason",
    "human_label",
    "human_reviewed",
    "reviewer",
    "review_date",
    "judge_label",
    "judge_reason",
    "agreement",
    "blind_contamination",
]

EVAL_ORDER = ["E8", "E9", "E11"]


def _excerpt(text: str, limit: int = REPLY_EXCERPT_CHARS) -> str:
    """One-line excerpt of a reply, truncated with an explicit marker so a
    reviewer always knows whether they are seeing the whole thing."""
    clean, _ = redact(text or "")
    flat = " ".join(clean.split())
    if len(flat) <= limit:
        return flat
    return flat[:limit] + f" [...truncated, {len(flat)} chars total]"


def _agreement(judge_label: str, human_label: str) -> str:
    """Derived agreement cell. 'unsure' never counts as agreement or as a
    disagreement; it is excluded from the denominator downstream."""
    if human_label == "unsure":
        return "n/a-unsure"
    return "agree" if judge_label == human_label else "disagree"


def _load_judge_verdicts(path: Path) -> dict:
    """(trace_id, eval_id) -> {'label': 'pass'|'fail', 'reason': str}."""
    verdicts = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            key = (row["trace_id"], row["eval_id"])
            verdicts[key] = {
                "label": "pass" if row["passed"] else "fail",
                "reason": row.get("reason", ""),
            }
    return verdicts


def build() -> list:
    traces = load_traces(SPANS)
    verdicts = _load_judge_verdicts(JUDGE_RESULTS)

    rows = []
    for n, trace in enumerate(traces, start=1):
        labels = LABELS.get(n)
        if labels is None:
            raise KeyError(f"no blind label recorded for trace position {n}")
        user_redacted, _ = redact(trace.user_input or "")
        for eval_id in EVAL_ORDER:
            proposed, reason = labels[eval_id]
            verdict = verdicts.get((trace.trace_id, eval_id))
            if verdict is None:
                raise KeyError(f"no judge verdict for {trace.trace_id} {eval_id}")
            rows.append(
                {
                    "eval_id": eval_id,
                    "trace_id": trace.trace_id,
                    "session_id": trace.session_id or "",
                    "user_input_redacted": " ".join(user_redacted.split()),
                    "assistant_reply_excerpt": _excerpt(trace.reply),
                    "assistant_proposed_label": proposed,
                    "proposed_reason": reason,
                    # Starting point only. human_reviewed stays false until a
                    # human actually reviews the row.
                    "human_label": proposed,
                    "human_reviewed": "false",
                    "reviewer": "",
                    "review_date": "",
                    "judge_label": verdict["label"],
                    "judge_reason": verdict["reason"],
                    "agreement": _agreement(verdict["label"], proposed),
                    "blind_contamination": CONTAMINATED.get((n, eval_id), ""),
                }
            )
    return rows


def main() -> int:
    rows = build()
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    print(f"source run: {SOURCE_RUN}")
    print(f"{len(rows)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
