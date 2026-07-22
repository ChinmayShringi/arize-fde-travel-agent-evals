"""Offline orchestration tests for the improvement-loop data flow."""

from pathlib import Path

from scripts import feedback_loop


def test_main_uses_curated_dataset_for_proposal_and_experiment(monkeypatch, tmp_path):
    source_dataset = tmp_path / "golden.json"
    source_dataset.write_text("{}")
    spans_path = tmp_path / "spans.jsonl"
    spans_path.write_text("")
    run_dir = tmp_path / "run"
    curated_dataset = run_dir / "dataset.curated.json"
    calls = {}

    monkeypatch.setattr(feedback_loop, "collect", lambda reporter, path: 0)
    monkeypatch.setattr(
        feedback_loop,
        "evaluate",
        lambda reporter, path, output: output / "evals" / "results.jsonl",
    )
    monkeypatch.setattr(feedback_loop, "_load_results", lambda path: [])
    monkeypatch.setattr(feedback_loop, "cluster", lambda reporter, results: {})
    monkeypatch.setattr(
        feedback_loop,
        "curate",
        lambda reporter, results, dataset, output: curated_dataset,
    )

    def record_proposal(reporter, clusters, dataset, output):
        calls["proposal_dataset"] = dataset
        return ["B"], output / "proposal.md"

    def record_experiment(reporter, proposed, dataset, output):
        calls["experiment_dataset"] = dataset
        return None

    monkeypatch.setattr(feedback_loop, "propose", record_proposal)
    monkeypatch.setattr(feedback_loop, "experiment", record_experiment)
    monkeypatch.setattr(feedback_loop, "gate", lambda *args: Path(args[-1]) / "approval.json")

    result = feedback_loop.main(
        [
            "--spans",
            str(spans_path),
            "--dataset",
            str(source_dataset),
            "--out",
            str(run_dir),
            "--run-experiments",
        ]
    )

    assert result == 0
    assert calls == {
        "proposal_dataset": curated_dataset,
        "experiment_dataset": curated_dataset,
    }


def test_main_refuses_to_reuse_nonempty_evidence_directory(tmp_path):
    source_dataset = tmp_path / "golden.json"
    source_dataset.write_text("{}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sentinel = run_dir / "loop_report.md"
    sentinel.write_text("immutable evidence")

    result = feedback_loop.main(
        ["--dataset", str(source_dataset), "--out", str(run_dir)]
    )

    assert result == 2
    assert sentinel.read_text() == "immutable evidence"


def test_cluster_and_proposal_never_persist_raw_pii(tmp_path):
    card = "4111 1111 1111 1111"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    reporter = feedback_loop.Reporter(run_dir / "loop_report.md")
    results = [
        {
            "passed": False,
            "eval_id": "E2",
            "name": "flight_direction",
            "attribution": "tool",
            "trace_id": "t1",
            "user_input": f"Book this flight with {card}",
        }
    ]

    clusters = feedback_loop.cluster(reporter, results)
    feedback_loop.propose(
        reporter,
        clusters,
        tmp_path / "golden.json",
        run_dir,
    )

    written = (run_dir / "loop_report.md").read_text() + (run_dir / "proposal.md").read_text()
    assert card not in written
    assert "[REDACTED-CARD]" in written
