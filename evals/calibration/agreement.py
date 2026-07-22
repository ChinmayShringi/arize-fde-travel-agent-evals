"""Judge/human agreement report for a filled calibration_sheet.csv.

Usage:
    uv run python evals/calibration/agreement.py <calibration_sheet.csv>

Reads a calibration sheet (as written by evals/run_judges.py, with a label
column filled in) and prints:
  - the overall agreement rate,
  - Cohen's kappa (chance-corrected agreement), and
  - every disagreement row.

Label column selection (honesty-preserving): the sheet's ground-truth column is
`human_label`. If no row has a human_label but rows have `assistant_proposed_label`
filled, this script falls back to that column and clearly marks the whole report
PROVISIONAL - the numbers are then agreement against an assistant's own proposals,
not human ground truth. Rows whose chosen label is empty are skipped (unlabeled).

Labels are compared as booleans: "pass"/"true"/"yes"/"1" -> pass, and
"fail"/"false"/"no"/"0" -> fail (case-insensitive). judge_passed is read the same
way. A row with an unrecognizable label is reported and skipped.
"""

import csv
import sys
from pathlib import Path

_TRUE = {"pass", "true", "yes", "1", "y", "t", "passed"}
_FALSE = {"fail", "false", "no", "0", "n", "f", "failed"}


def _parse_label(raw: str):
    """Return True/False for a pass/fail-ish token, or None if blank/unknown."""
    if raw is None:
        return None
    token = raw.strip().lower()
    if token == "":
        return None
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    return "UNKNOWN"


def _pick_label_column(rows: list) -> tuple[str, bool]:
    """Choose the label column. Prefer human_label; fall back to
    assistant_proposed_label (provisional). Returns (column_name, provisional)."""
    has_human = any((r.get("human_label") or "").strip() for r in rows)
    if has_human:
        return "human_label", False
    has_proposed = any((r.get("assistant_proposed_label") or "").strip() for r in rows)
    if has_proposed:
        return "assistant_proposed_label", True
    return "human_label", False  # nothing filled; report will show 0 labeled


def _cohen_kappa(pairs: list) -> float | None:
    """Cohen's kappa over (judge_bool, human_bool) pairs. None if undefined
    (no rows, or agreement/chance degenerate)."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for j, h in pairs if j == h) / n
    # Marginal probabilities for the "pass" class and "fail" class.
    pj = sum(1 for j, _ in pairs if j) / n
    ph = sum(1 for _, h in pairs if h) / n
    pe = pj * ph + (1 - pj) * (1 - ph)
    if pe == 1.0:
        # Perfect chance agreement (one class only on a side): kappa undefined;
        # report 1.0 when observed agreement is also perfect, else 0.0.
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def main(argv: list) -> int:
    if len(argv) != 2:
        print(
            "usage: uv run python evals/calibration/agreement.py <calibration_sheet.csv>",
            file=sys.stderr,
        )
        return 2

    path = Path(argv[1])
    try:
        with path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as exc:
        print(f"io error: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    label_col, provisional = _pick_label_column(rows)

    pairs = []
    disagreements = []
    skipped_unknown = []
    for r in rows:
        judge = _parse_label(r.get("judge_passed"))
        human = _parse_label(r.get(label_col))
        if human is None:
            continue  # unlabeled row
        if human == "UNKNOWN" or judge == "UNKNOWN":
            skipped_unknown.append(r)
            continue
        pairs.append((judge, human))
        if judge != human:
            disagreements.append((r, judge, human))

    banner = "PROVISIONAL (assistant_proposed_label)" if provisional else "human_label"
    print(f"Agreement report for {path}")
    print(f"Label column: {label_col}  [{banner}]")
    print("-" * 60)

    n = len(pairs)
    if n == 0:
        print("No labeled rows to compare (fill in a label column first).")
        if skipped_unknown:
            print(f"Skipped {len(skipped_unknown)} row(s) with unrecognizable labels.")
        return 0

    agree = sum(1 for j, h in pairs if j == h)
    rate = agree / n
    kappa = _cohen_kappa(pairs)
    kappa_str = "n/a" if kappa is None else f"{kappa:.3f}"

    print(f"Labeled rows compared : {n}")
    print(f"Agreements            : {agree}")
    print(f"Agreement rate        : {rate * 100:.1f}%")
    print(f"Cohen's kappa         : {kappa_str}")
    if skipped_unknown:
        print(f"Skipped (bad label)   : {len(skipped_unknown)}")
    print("-" * 60)

    if not disagreements:
        print("Disagreements: none.")
    else:
        print(f"Disagreements ({len(disagreements)}):")
        for r, judge, human in disagreements:
            j = "pass" if judge else "fail"
            h = "pass" if human else "fail"
            print(
                f"  - {r.get('eval_id', '?')} {r.get('trace_id', '?')[:12]} "
                f"judge={j} label={h} | {(r.get('user_input') or '')[:60]!r}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
