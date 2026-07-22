"""Per-eval judge/label agreement report for the live calibration sheet.

Usage:
    uv run python evals/calibration/compute_agreement.py [calibration_sheet.csv]

Why this exists alongside evals/calibration/agreement.py: that script predates
the human_reviewed / unsure columns. It picks human_label whenever any row has
one filled, which would silently present PRE-POPULATED starting-point labels as
human ground truth. This script keys the provenance banner off human_reviewed
instead, treats "unsure" as excluded rather than as a bad label, and breaks the
numbers out per eval, which is what a release-gating decision needs.

Cohen's kappa is imported from agreement.py so there is one implementation.

Definitions used throughout (stated so no one has to guess):
  - false positive : judge=pass, label=fail. The judge missed a real problem.
                     This is the dangerous direction for a release gate.
  - false negative : judge=fail, label=pass. The judge cried wolf.
  - unsure         : the labeller could not decide from the rubric. Excluded
                     from the denominator, reported separately, never silently
                     folded into agreement.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agreement import _cohen_kappa  # noqa: E402

DEFAULT_SHEET = Path(__file__).resolve().parent / "calibration_sheet.csv"


def _rows(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _report_for(rows: list, eval_id: str | None = None) -> dict:
    """Counts for one eval (or all evals when eval_id is None)."""
    subset = [r for r in rows if eval_id is None or r["eval_id"] == eval_id]
    unsure = [r for r in subset if r["human_label"].strip().lower() == "unsure"]
    scored = [r for r in subset if r not in unsure]

    agree = [r for r in scored if r["judge_label"] == r["human_label"]]
    fp = [r for r in scored if r["judge_label"] == "pass" and r["human_label"] == "fail"]
    fn = [r for r in scored if r["judge_label"] == "fail" and r["human_label"] == "pass"]

    pairs = [
        (r["judge_label"] == "pass", r["human_label"] == "pass") for r in scored
    ]
    kappa = _cohen_kappa(pairs) if pairs else None

    return {
        "eval_id": eval_id or "ALL",
        "total": len(subset),
        "unsure": len(unsure),
        "scored": len(scored),
        "agree": len(agree),
        "rate": (len(agree) / len(scored)) if scored else None,
        "false_positives": len(fp),
        "false_negatives": len(fn),
        "kappa": kappa,
        "fp_rows": fp,
        "fn_rows": fn,
        "unsure_rows": unsure,
        "label_pass": sum(1 for r in scored if r["human_label"] == "pass"),
        "label_fail": sum(1 for r in scored if r["human_label"] == "fail"),
        "judge_pass": sum(1 for r in scored if r["judge_label"] == "pass"),
        "judge_fail": sum(1 for r in scored if r["judge_label"] == "fail"),
    }


def _fmt(value, spec: str = ".3f") -> str:
    return "n/a" if value is None else format(value, spec)


def main(argv: list) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_SHEET
    rows = _rows(path)

    reviewed = [r for r in rows if r["human_reviewed"].strip().lower() == "true"]
    reviewers = sorted({r["reviewer"].strip() for r in reviewed if r["reviewer"].strip()})

    print(f"Calibration agreement report for {path}")
    if reviewed:
        print(
            f"Provenance: {len(reviewed)}/{len(rows)} rows human_reviewed=true "
            f"by {', '.join(reviewers) or '(unnamed)'}"
        )
    else:
        print(
            "Provenance: PROVISIONAL. 0 rows have human_reviewed=true, so "
            "human_label still holds the AI-proposed starting values. These "
            "numbers are agreement between two AI systems, not human ground truth."
        )
    print("=" * 72)

    for eval_id in ["E8", "E9", "E11", None]:
        rep = _report_for(rows, eval_id)
        if rep["total"] == 0:
            continue
        rate = "n/a" if rep["rate"] is None else f"{rep['rate'] * 100:.1f}%"
        print(f"\n[{rep['eval_id']}]")
        print(f"  rows                    : {rep['total']}")
        print(f"  unsure (excluded)       : {rep['unsure']}")
        print(f"  scored                  : {rep['scored']}")
        print(f"  agreements              : {rep['agree']}")
        print(f"  agreement rate          : {rep['agree']}/{rep['scored']} = {rate}")
        print(f"  judge pass/fail         : {rep['judge_pass']}/{rep['judge_fail']}")
        print(f"  label pass/fail         : {rep['label_pass']}/{rep['label_fail']}")
        print(f"  false positives (J=pass, L=fail): {rep['false_positives']}")
        print(f"  false negatives (J=fail, L=pass): {rep['false_negatives']}")
        print(f"  Cohen's kappa           : {_fmt(rep['kappa'])}")
        if rep["kappa"] is None or rep["scored"] == 0:
            pass
        elif rep["label_fail"] == 0 and rep["judge_fail"] == 0:
            print(
                "  WARNING: no fail labels on either side. A judge that always "
                "returned pass would score identically here, so this agreement "
                "rate carries no information about discrimination."
            )
        for tag, key in (("FALSE POSITIVE", "fp_rows"), ("FALSE NEGATIVE", "fn_rows")):
            for r in rep[key]:
                print(
                    f"    {tag}: {r['trace_id'][:12]} {r['user_input_redacted'][:58]!r}"
                )
        for r in rep["unsure_rows"]:
            print(
                f"    UNSURE: {r['trace_id'][:12]} judge={r['judge_label']} "
                f"{r['user_input_redacted'][:52]!r}"
            )

    contaminated = [r for r in rows if r["blind_contamination"].strip()]
    if contaminated:
        print("\n" + "=" * 72)
        print(
            f"Blind-labelling contamination: {len(contaminated)} row(s) where the "
            "labeller had already seen the judge verdict."
        )
        clean = [r for r in rows if not r["blind_contamination"].strip()]
        rep = _report_for(clean)
        rate = "n/a" if rep["rate"] is None else f"{rep['rate'] * 100:.1f}%"
        print(
            f"  Agreement on the {rep['scored']} uncontaminated scored rows: "
            f"{rep['agree']}/{rep['scored']} = {rate}"
        )
        for r in contaminated:
            print(f"  - {r['eval_id']} {r['trace_id'][:12]}: {r['blind_contamination']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
