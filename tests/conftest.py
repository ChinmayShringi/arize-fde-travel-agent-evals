"""Shared pytest fixtures.

Everything here is offline: the only inputs are the committed span fixture
(tests/fixtures/spans.jsonl, sampled verbatim from docs/baseline/2026-07-19)
and the closed data/ fixture set. No credentials, no network, no model calls.

Environment isolation matters more than usual in this repo: agent/config.py calls
load_dotenv() at import, and several modules read behavior-changing env vars at
call time (FLIGHT_TOOL_FIX, SESSION_STORE, TOOL_MAX_RETRIES). The autouse
``clean_env`` fixture pins those to "unset" so a test never inherits a value from
the developer's shell or from .env, and a test that wants a flag sets it
explicitly with monkeypatch.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SPANS_PATH = FIXTURES_DIR / "spans.jsonl"

# pyproject sets pythonpath, but keep the suite runnable via a bare
# `python -m pytest tests/...` from anywhere in the repo.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# Env vars that change behavior of code under test. Cleared before every test.
_BEHAVIOR_ENV_VARS = (
    "FLIGHT_TOOL_FIX",
    "SESSION_STORE",
    "SESSION_DB_PATH",
    "TOOL_MAX_RETRIES",
    "TOOL_RETRY_BASE_SECONDS",
    "PROMPT_CACHE",
    # E7 telemetry ceilings (evals/e_guardrails.py) are env-overridable; a value
    # left in the shell would silently change which traces fail.
    "MAX_LATENCY_MS",
    "MAX_TOKENS_PER_TURN",
    "MAX_ITERATIONS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test from shipped-default behavior."""
    for name in _BEHAVIOR_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session")
def spans_path() -> Path:
    assert SPANS_PATH.exists(), f"missing committed fixture: {SPANS_PATH}"
    return SPANS_PATH


@pytest.fixture(scope="session")
def ctx():
    """The closed fixture world (data/*.json) the deterministic evals score against."""
    from evals.context import EvalContext

    return EvalContext.load()


@pytest.fixture(scope="session")
def traces(spans_path):
    from evals.trace_model import load_traces

    return load_traces(spans_path)


@pytest.fixture(scope="session")
def trace_by_prefix(traces):
    """Look up a fixture trace by any unique prefix of its user_input.

    Keyed on the user text rather than the trace id so a test reads as the
    scenario it is pinning.
    """

    def _lookup(prefix: str):
        matches = [t for t in traces if t.user_input.startswith(prefix)]
        assert len(matches) == 1, (
            f"expected exactly 1 fixture trace starting with {prefix!r}, "
            f"got {len(matches)}"
        )
        return matches[0]

    return _lookup
