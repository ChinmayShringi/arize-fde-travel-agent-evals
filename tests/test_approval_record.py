"""P1-10: the promotion gate must leave a machine-readable record.

Self-contained by design: this module does its own sys.path setup and builds its
own fixtures, so it passes with or without a conftest.py. No network, no model
calls; every write lands in tmp_path.

The load-bearing claim under test is negative: the loop CANNOT approve its own
promotion. That is checked two ways, at runtime (the writer refuses any other
decision) and structurally (the module contains no literal that could be written
as an approving decision, and the decision field is bound to one constant).

Run:
    .venv/bin/python -m pytest tests/test_approval_record.py -v
"""

import ast
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT, REPO_ROOT / "evals", REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import feedback_loop  # noqa: E402

FEEDBACK_LOOP_SOURCE = REPO_ROOT / "scripts" / "feedback_loop.py"
APPROVING_DECISION = "appro" + "ved"  # built at runtime so this file is not a match


# --- fixtures ---------------------------------------------------------------


def _reporter(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    return feedback_loop.Reporter(run_dir / "loop_report.md")


def _write_results(run_dir: Path, rows: list) -> Path:
    evals_dir = run_dir / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)
    path = evals_dir / "results.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def _row(eval_id: str, passed: bool) -> dict:
    return {"eval_id": eval_id, "name": f"name_{eval_id}", "passed": passed}


def _experiment_outcome(tmp_path: Path) -> dict:
    """A control run and one candidate run with real results.jsonl files, so the
    delta in approval.json is computed from data rather than asserted."""
    exp_root = tmp_path / "experiments"
    control = exp_root / "control"
    candidate = exp_root / "candidate-A-prompt-v1"
    # E1: control 1/3, candidate 3/3 -> +66.67pp
    # E2: control 2/2, candidate 1/2 -> -50.00pp (a regression)
    _write_results(control, [_row("E1", True), _row("E1", False), _row("E1", False),
                             _row("E2", True), _row("E2", True)])
    _write_results(candidate, [_row("E1", True), _row("E1", True), _row("E1", True),
                               _row("E2", True), _row("E2", False)])
    return {
        "comparison_path": tmp_path / "comparison.md",
        "control_dir": control,
        "candidate_dirs": {"candidate-A-prompt-v1": candidate},
    }


# --- acceptance: approval.json is written, pending, unsigned ----------------


def test_gate_writes_approval_json_pending_with_null_reviewer(tmp_path):
    run_dir = tmp_path / "run-001"
    reporter = _reporter(run_dir)

    path = feedback_loop.gate(reporter, ["A"], None, run_dir)

    assert path == run_dir / "approval.json"
    record = json.loads(path.read_text())
    assert record["decision"] == "pending_human_review"
    assert record["reviewer"] is None
    assert record["decision_time"] is None


def test_approval_record_carries_every_required_field(tmp_path):
    run_dir = tmp_path / "run-002"
    feedback_loop.gate(_reporter(run_dir), ["A", "B"], None, run_dir)
    record = json.loads((run_dir / "approval.json").read_text())

    for key in (
        "run_id", "timestamp", "git_sha", "git_dirty", "candidate_ids",
        "quality_delta", "regressions", "decision", "reviewer",
        "decision_time", "promotion_target",
    ):
        assert key in record, f"approval.json is missing {key}"

    assert record["run_id"] == "run-002"
    assert record["promotion_target"]
    # UTC ISO 8601, parseable rather than merely a string
    parsed = datetime.fromisoformat(record["timestamp"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_candidate_ids_record_the_env_flags_that_enable_them(tmp_path):
    run_dir = tmp_path / "run-003"
    feedback_loop.gate(_reporter(run_dir), ["A", "B"], None, run_dir)
    record = json.loads((run_dir / "approval.json").read_text())

    by_id = {c["id"]: c for c in record["candidate_ids"]}
    assert by_id["A"]["env_flags"] == {"PROMPT_VARIANT": "v1", "FLIGHT_TOOL_FIX": "0"}
    assert by_id["B"]["env_flags"] == {"PROMPT_VARIANT": "v0", "FLIGHT_TOOL_FIX": "1"}
    assert by_id["A"]["enable_flag"] == "PROMPT_VARIANT=v1"


def test_git_sha_and_dirty_flag_are_both_recorded(tmp_path):
    run_dir = tmp_path / "run-004"
    feedback_loop.gate(_reporter(run_dir), [], None, run_dir)
    record = json.loads((run_dir / "approval.json").read_text())

    assert isinstance(record["git_sha"], str) and record["git_sha"]
    # the audit found git_sha alone is not identifying, so dirty must be recorded
    assert record["git_dirty"] in (True, False, None)


def test_git_sha_helper_is_reused_from_run_experiment():
    """One sha helper, not two. feedback_loop delegates to run_experiment's."""
    import run_experiment

    assert feedback_loop._git_sha() == run_experiment._git_sha()
    source = FEEDBACK_LOOP_SOURCE.read_text()
    assert "from run_experiment import _git_sha" in source
    assert "rev-parse" not in source, "the sha must not be re-implemented here"


# --- acceptance: a missing measurement is not a measurement of zero ---------


def test_quality_delta_is_null_when_experiments_did_not_run(tmp_path):
    run_dir = tmp_path / "run-005"
    feedback_loop.gate(_reporter(run_dir), ["A"], None, run_dir)
    record = json.loads((run_dir / "approval.json").read_text())

    assert record["quality_delta"] is None, "unmeasured must be null, never 0"
    assert record["regressions"] == []
    assert record["comparison_report"] is None


def test_quality_delta_and_regressions_are_computed_from_results(tmp_path):
    run_dir = tmp_path / "run-006"
    outcome = _experiment_outcome(run_dir)
    feedback_loop.gate(_reporter(run_dir), ["A"], outcome, run_dir)
    record = json.loads((run_dir / "approval.json").read_text())

    delta = record["quality_delta"]["candidate-A-prompt-v1"]
    assert delta["E1"]["delta_pp"] == pytest.approx(66.67, abs=0.01)
    assert delta["E1"]["control_applicable"] == 3
    assert delta["E2"]["delta_pp"] == pytest.approx(-50.0, abs=0.01)

    assert len(record["regressions"]) == 1
    regression = record["regressions"][0]
    assert regression["eval_id"] == "E2"
    assert regression["candidate"] == "candidate-A-prompt-v1"
    assert regression["delta_pp"] < 0


def test_quality_delta_is_null_when_the_control_produced_no_results(tmp_path):
    run_dir = tmp_path / "run-007"
    outcome = {
        "comparison_path": None,
        "control_dir": run_dir / "experiments" / "control",
        "candidate_dirs": {},
    }
    feedback_loop.gate(_reporter(run_dir), ["A"], outcome, run_dir)
    record = json.loads((run_dir / "approval.json").read_text())
    assert record["quality_delta"] is None


# --- acceptance: the loop cannot approve itself -----------------------------


def test_writer_refuses_any_decision_other_than_pending(tmp_path):
    run_dir = tmp_path / "run-008"
    run_dir.mkdir()
    record = feedback_loop._build_approval_record(run_dir, ["A"], None)
    tampered = {**record, "decision": APPROVING_DECISION}

    with pytest.raises(ValueError):
        feedback_loop._write_approval(run_dir, tampered)
    assert not (run_dir / "approval.json").exists()


def test_writer_refuses_a_record_that_names_a_reviewer(tmp_path):
    run_dir = tmp_path / "run-009"
    run_dir.mkdir()
    record = feedback_loop._build_approval_record(run_dir, ["A"], None)

    with pytest.raises(ValueError):
        feedback_loop._write_approval(run_dir, {**record, "reviewer": "PM"})
    with pytest.raises(ValueError):
        feedback_loop._write_approval(
            run_dir, {**record, "decision_time": "2026-07-21T00:00:00+00:00"}
        )
    assert not (run_dir / "approval.json").exists()


def test_builder_always_produces_the_pending_decision(tmp_path):
    """Whatever the inputs, the built record is unsigned and pending."""
    run_dir = tmp_path / "run-010"
    run_dir.mkdir()
    for proposed, outcome in (([], None), (["A"], None), (["A", "B"], _experiment_outcome(run_dir))):
        record = feedback_loop._build_approval_record(run_dir, proposed, outcome)
        assert record["decision"] == feedback_loop.PENDING_DECISION
        assert record["reviewer"] is None
        assert record["decision_time"] is None


def test_module_contains_no_approving_decision_literal():
    """Structural proof: no string constant anywhere in feedback_loop.py equals
    the approving decision, so no code path can write one."""
    tree = ast.parse(FEEDBACK_LOOP_SOURCE.read_text())
    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.strip().lower() == APPROVING_DECISION
    ]
    assert offenders == []


def test_decision_field_is_bound_to_the_single_pending_constant():
    """Structural proof: _build_approval_record binds "decision" to the
    PENDING_DECISION name, not to a literal that a later edit could flip."""
    tree = ast.parse(FEEDBACK_LOOP_SOURCE.read_text())
    builder = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_build_approval_record"
    )
    bindings = [
        value
        for node in ast.walk(builder)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "decision"
    ]
    assert len(bindings) == 1
    assert isinstance(bindings[0], ast.Name)
    assert bindings[0].id == "PENDING_DECISION"
    assert feedback_loop.PENDING_DECISION == "pending_human_review"


def test_loop_report_states_the_promotion_is_blocked(tmp_path):
    run_dir = tmp_path / "run-011"
    feedback_loop.gate(_reporter(run_dir), ["A"], None, run_dir)
    report = (run_dir / "loop_report.md").read_text()
    assert "PROMOTION: BLOCKED pending human approval" in report
    assert "approval.json" in report
    assert "—" not in report, "no em dash may reach disk"
