"""Approval record for the promotion gate (stage 7 of scripts/feedback_loop.py).

Extracted from feedback_loop.py to keep that module under the house file-size
limit. Behavior is unchanged: this module owns the approval schema constants, the
measurement helpers that turn experiment directories into a per-eval quality
delta, and the writer.

The load-bearing guarantee lives in `write_approval`: the ONLY decision value it
will persist is PENDING_DECISION, with a null reviewer and a null decision_time.
It raises ValueError on anything else, so no caller (and no future edit to the
loop) can quietly self-approve a promotion. A human records a real decision by
editing the written file; nothing in the loop can do it.

Note that `_build_approval_record` deliberately stays in feedback_loop.py: the
"decision" key must be bound there to the PENDING_DECISION name, and that binding
is asserted structurally (by AST) in tests/test_approval_record.py.

Stdlib only. Immutable style: nothing loaded here is mutated in place.
"""

import json
import subprocess
from pathlib import Path

APPROVAL_SCHEMA = "approval/v1"
APPROVAL_FILENAME = "approval.json"
PENDING_DECISION = "pending_human_review"
PROMOTION_TARGET = "agent production defaults (PROMPT_VARIANT / FLIGHT_TOOL_FIX)"


def git_dirty(repo_root: Path):
    """True when the working tree has uncommitted changes, None when git could
    not answer. Recorded because the sha alone is not identifying: a run against
    a dirty tree is not reproducible from the sha."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except Exception:  # noqa: BLE001 - absence of git is data, not a crash
        return None
    if out.returncode != 0:
        return None
    return bool(out.stdout.strip())


def _pass_rates(run_dir: Path) -> dict | None:
    """eval_id -> {passed, applicable, pass_rate} for one experiment dir, or None
    when that run produced no results. Reuses compare_experiments' aggregation so
    approval.json and comparison.md cannot disagree."""
    from compare_experiments import _eval_stats, _resolve_results

    results_path = _resolve_results(Path(run_dir))
    if results_path is None:
        return None
    stats = _eval_stats(results_path)
    return {
        eid: {
            "passed": slot["passed"],
            "applicable": slot["applicable"],
            "pass_rate": (slot["passed"] / slot["applicable"] * 100) if slot["applicable"] else None,
        }
        for eid, slot in stats.items()
    }


def _delta_pp(control_rate, candidate_rate):
    if control_rate is None or candidate_rate is None:
        return None
    return round(candidate_rate - control_rate, 2)


def quality_delta(outcome: dict | None) -> dict | None:
    """Per-candidate, per-eval pass-rate delta against the control.

    Returns None when no experiment ran. A missing measurement is recorded as
    null, never as zero: zero would assert that quality did not move, which was
    not measured."""
    if not outcome or not outcome.get("control_dir"):
        return None
    control = _pass_rates(outcome["control_dir"])
    if control is None:
        return None
    delta: dict = {}
    for name, cand_dir in (outcome.get("candidate_dirs") or {}).items():
        rates = _pass_rates(cand_dir)
        if rates is None:
            delta[name] = None
            continue
        delta[name] = {
            eid: {
                "control_pass_rate": control.get(eid, {}).get("pass_rate"),
                "candidate_pass_rate": slot["pass_rate"],
                "delta_pp": _delta_pp(control.get(eid, {}).get("pass_rate"), slot["pass_rate"]),
                "control_applicable": control.get(eid, {}).get("applicable"),
                "candidate_applicable": slot["applicable"],
            }
            for eid, slot in sorted(rates.items())
        }
    return delta or None


def regressions(delta: dict | None) -> list:
    """Every eval whose pass rate went DOWN versus the control. Empty list when
    nothing regressed; still empty (not null) when nothing was measured, with the
    null quality_delta carrying the 'not measured' meaning."""
    out: list = []
    for name, per_eval in (delta or {}).items():
        for eid, cell in (per_eval or {}).items():
            if cell.get("delta_pp") is not None and cell["delta_pp"] < 0:
                out.append({
                    "candidate": name,
                    "eval_id": eid,
                    "delta_pp": cell["delta_pp"],
                    "control_pass_rate": cell["control_pass_rate"],
                    "candidate_pass_rate": cell["candidate_pass_rate"],
                })
    return out


def candidate_records(proposed: list, candidates: dict) -> list:
    """The proposed candidates with the exact env flags that enable them.
    `candidates` is the caller's candidate registry (letter -> spec)."""
    records = []
    for letter in proposed:
        c = candidates.get(letter)
        if c is None:
            continue
        records.append({
            "id": letter,
            "name": c["name"],
            "defect": c["defect"],
            "enable_flag": c["flag"],
            "env_flags": {
                "PROMPT_VARIANT": c["prompt_variant"],
                "FLIGHT_TOOL_FIX": c["flight_tool_fix"],
            },
        })
    return records


def record_note() -> str:
    """The provenance note embedded in every record, naming the writer and the
    single decision value it is capable of producing."""
    return (
        "Written by scripts/feedback_loop.py. The loop can only write "
        f"decision '{PENDING_DECISION}' with a null reviewer. A human records "
        "the real decision by editing this file; promotion is not automated."
    )


def write_approval(run_dir: Path, record: dict) -> Path:
    """Write approval.json. Refuses any record whose decision is not the pending
    value, so no future edit to the loop can quietly self-approve a promotion."""
    if record.get("decision") != PENDING_DECISION:
        raise ValueError(
            f"feedback_loop may only write decision '{PENDING_DECISION}'; "
            f"refusing to write {record.get('decision')!r}"
        )
    if record.get("reviewer") is not None or record.get("decision_time") is not None:
        raise ValueError("feedback_loop may not write a reviewer or a decision_time")
    path = run_dir / APPROVAL_FILENAME
    path.write_text(json.dumps(record, indent=2, ensure_ascii=True) + "\n")
    return path
