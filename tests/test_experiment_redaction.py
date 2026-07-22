"""The experiment harness must enforce the same source PII boundary as serving."""

from scripts import run_experiment


def _required_args():
    return [
        "--name",
        "test-run",
        "--prompt-variant",
        "v0",
        "--flight-tool-fix",
        "0",
        "--dataset",
        "evals/golden_dataset.json",
        "--out",
        "tmp/test-run",
    ]


def test_experiment_redacts_pii_by_default(monkeypatch):
    monkeypatch.delenv("EXPERIMENT_REDACT_PII", raising=False)

    args = run_experiment._parse_args(_required_args())

    assert args.redact_pii == "1"


def test_legacy_verbatim_replay_requires_explicit_opt_out(monkeypatch):
    monkeypatch.delenv("EXPERIMENT_REDACT_PII", raising=False)

    args = run_experiment._parse_args([*_required_args(), "--redact-pii", "0"])

    assert args.redact_pii == "0"
