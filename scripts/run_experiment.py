"""Run one experiment: replay a golden dataset through the agent under a fixed
prompt/tool variant, export spans + replies + a manifest, then score with the
deterministic eval suite.

Pinned CLI (do not deviate; other agents build against this):

    uv run python scripts/run_experiment.py \
        --name <label> \
        --prompt-variant v0|v1 \
        --flight-tool-fix 0|1 \
        --dataset <path> \
        --out <dir> \
        [--model <model-id>] [--redact-pii 0|1]

Outputs written under <dir>:
    spans.jsonl        every OTel span exported during the replay
    replies.jsonl      one line per turn (conversation id, turn index, user, reply)
    manifest.json      run metadata (name, variant, git sha, timestamps, counts)
    evals/summary.md   eval summary table (produced by evals/run_evals.py)
    evals/results.jsonl per-eval results

Candidate fixes are gated by two env vars that this runner sets BEFORE importing
any agent.* module (agent modules read env at import time):
    PROMPT_VARIANT   "v0" (default, shipped) | "v1"
    FLIGHT_TOOL_FIX  "0"  (default, shipped) | "1"
With both at their defaults the agent behaves byte-identically to today.

PII redaction on the replay path (--redact-pii / EXPERIMENT_REDACT_PII, DEFAULT 1):
    1 (default) the replay applies agent/redaction.py redact() and the OpenInference
      pii metadata context first, matching the serving path in agent/api.py and
      agent/chat.py.
    0 is an explicit legacy opt-out for reproducing already-captured runs that
      fed dataset text to run_agent verbatim. The golden dataset contains a
      Luhn-valid card in synth-06, so this mode crosses the stated PII boundary
      and must never be used for new evidence or production-like experiments.

The default is fail-safe even though it changes the model input for the planted
PII probe and makes new runs incomparable to historical unredacted captures. See
docs/PII_BOUNDARY.md.

The runner refuses to overwrite an out dir that already holds a spans.jsonl.
A per-turn API error is recorded as data ({"error": ...}) and the replay
continues; a failed turn is a data point, not a runner crash.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# agent.* and evals.* imports resolve against the repo root, not scripts/.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def repo_relative(p) -> str:
    """Serialise a path relative to the repo root so manifests stay portable.

    Manifests are committed evidence and are read on other machines and in CI,
    so an absolute path baked in at capture time leaks the author's home
    directory and does not resolve anywhere else. Paths outside the repo are
    returned unchanged, since there is no meaningful relative form for them.
    """
    resolved = Path(p).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)

PROMPT_VARIANTS = ("v0", "v1", "v2")
FLIGHT_TOOL_FIXES = ("0", "1")
REDACT_PII_CHOICES = ("0", "1")


def _parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_experiment.py",
        description="Replay a golden dataset through the agent and score it.",
    )
    parser.add_argument("--name", required=True, help="Experiment label (AGENT_VERSION).")
    parser.add_argument(
        "--prompt-variant",
        required=True,
        choices=PROMPT_VARIANTS,
        help="v0 = shipped prompt (default behavior), v1 = candidate prompt.",
    )
    parser.add_argument(
        "--flight-tool-fix",
        required=True,
        choices=FLIGHT_TOOL_FIXES,
        help="0 = shipped search_flights, 1 = direction-corrected search_flights.",
    )
    parser.add_argument("--dataset", required=True, help="Path to the golden dataset JSON.")
    parser.add_argument("--out", required=True, help="Output directory for this run.")
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Anthropic model id to test (sets ANTHROPIC_MODEL before agent import). "
            "Omit to use the agent default; default behavior is unchanged when omitted."
        ),
    )
    parser.add_argument(
        "--redact-pii",
        choices=REDACT_PII_CHOICES,
        default=os.environ.get("EXPERIMENT_REDACT_PII", "1"),
        help=(
            "1 = apply the serving-path PII redaction before each turn. "
            "1 is the safe default. 0 is an explicit legacy opt-out for reproducing "
            "historical unredacted captures and must not be used for new evidence; "
            "see docs/PII_BOUNDARY.md."
        ),
    )
    return parser.parse_args(argv)


def _load_dataset(path: str) -> dict:
    """Reuse evals.dataset.load_dataset when present; fall back to a plain JSON
    read (the schema is pinned, so json.load yields the same dict)."""
    try:
        from evals.dataset import load_dataset  # type: ignore
    except Exception:
        with open(path) as fh:
            return json.load(fh)
    return load_dataset(path)


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _redact_turn(user_message: str, redact_pii: bool) -> tuple:
    """Return (text_to_send, pii_types) for one turn.

    With redact_pii False this is an identity pass-through, so a default run
    feeds run_agent exactly the bytes every captured run fed it. With it True the
    single redaction implementation in agent/redaction.py is applied, the same
    call the serving path makes."""
    if not redact_pii:
        return user_message, []
    from agent.redaction import redact

    clean, findings = redact(user_message)
    return clean, sorted(set(findings))


def _replay(dataset: dict, name: str, spans_path: Path, redact_pii: bool = True):
    """Replay every conversation in-process. Returns (replies, turn_count, redacted_turns).

    Env must already be set: this function imports agent.loop, so setup_tracing()
    runs (reading TRACE_EXPORT_PATH) and prompt/tool variants are locked in."""
    # Imported here, after env is set, so tracing + variants pick up the run config.
    from openinference.instrumentation import using_session

    # _pii_metadata is the SAME helper the CLI serving path uses. Imported rather
    # than reimplemented so the experiment path cannot drift from serving; it is
    # a no-op nullcontext when nothing was redacted.
    from agent.chat import _pii_metadata
    from agent.loop import run_agent

    replies = []
    turn_count = 0
    redacted_turns = 0
    for conv in dataset.get("conversations", []):
        conv_id = conv["id"]
        messages: list = []
        # Group every turn of this conversation under one session so sessions
        # partition cleanly per variant in Arize.
        with using_session(f"{conv_id}-{name}"):
            for turn_index, user_message in enumerate(conv.get("messages", [])):
                turn_count += 1
                # Redact BEFORE append, exactly as agent/api.py and agent/chat.py
                # do, so the raw text is never appended, sent, traced, or written
                # to replies.jsonl.
                sent_text, pii_types = _redact_turn(user_message, redact_pii)
                if pii_types:
                    redacted_turns += 1
                messages = [*messages, {"role": "user", "content": sent_text}]
                record = {
                    "conversation_id": conv_id,
                    "turn": turn_index,
                    "user": sent_text,
                }
                if pii_types:
                    record["pii_types"] = pii_types
                try:
                    with _pii_metadata(pii_types):
                        reply, messages = run_agent(messages)
                    record["reply"] = reply
                except Exception as exc:  # noqa: BLE001 - a failed turn is data
                    record["error"] = f"{type(exc).__name__}: {exc}"
                replies.append(record)
    return replies, turn_count, redacted_turns


def _write_replies(replies: list, out: Path) -> None:
    with (out / "replies.jsonl").open("w") as fh:
        for r in replies:
            fh.write(json.dumps(r, ensure_ascii=True) + "\n")


def _write_manifest(
    out: Path,
    args: argparse.Namespace,
    dataset: dict,
    turn_count: int,
    wall_seconds: float,
    model: str,
    redacted_turns: int = 0,
) -> dict:
    manifest = {
        "name": args.name,
        "prompt_variant": args.prompt_variant,
        "flight_tool_fix": args.flight_tool_fix,
        "model": model,
        # Historical captures used "0". New runs default to "1" so experiments
        # enforce the same source boundary as serving.
        "redact_pii": getattr(args, "redact_pii", "1"),
        "pii_redacted_turns": redacted_turns,
        "dataset_version": dataset.get("version", "unknown"),
        "dataset_path": repo_relative(args.dataset),
        "git_sha": _git_sha(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "turn_count": turn_count,
        "wall_seconds": round(wall_seconds, 1),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _run_evals(spans_path: Path, out: Path) -> int:
    """Invoke evals/run_evals.py as a subprocess so a broken eval module fails
    this run by name rather than corrupting the runner process."""
    evals_out = out / "evals"
    proc = subprocess.run(
        ["uv", "run", "python", "evals/run_evals.py", str(spans_path), str(evals_out)],
        cwd=REPO_ROOT,
    )
    return proc.returncode


def main(argv: list) -> int:
    args = _parse_args(argv)

    out = Path(args.out)
    spans_path = out / "spans.jsonl"
    if spans_path.exists():
        print(f"refusing to overwrite existing run in {out} (spans.jsonl present)", file=sys.stderr)
        return 2

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"dataset not found: {dataset_path}", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    dataset = _load_dataset(str(dataset_path))

    # Lock the run config into the environment BEFORE importing any agent.* module.
    # agent.tracing reads PROMPT_VERSION / AGENT_VERSION / TRACE_EXPORT_PATH at import;
    # agent.prompt / agent.tools read PROMPT_VARIANT / FLIGHT_TOOL_FIX at import.
    os.environ["PROMPT_VARIANT"] = args.prompt_variant
    os.environ["FLIGHT_TOOL_FIX"] = args.flight_tool_fix
    os.environ["PROMPT_VERSION"] = args.prompt_variant
    os.environ["AGENT_VERSION"] = args.name
    os.environ["TRACE_EXPORT_PATH"] = str(spans_path)
    # agent.config reads ANTHROPIC_MODEL at import; only override it when the flag
    # is given so the default path stays byte-identical to today's behavior.
    if args.model is not None:
        os.environ["ANTHROPIC_MODEL"] = args.model

    started = time.time()
    replies, turn_count, redacted_turns = _replay(
        dataset, args.name, spans_path, redact_pii=(args.redact_pii == "1")
    )
    wall_seconds = time.time() - started

    # Flush the OTLP batch processor so Arize receives the tail spans. The local
    # JSONL file already holds every span via the SimpleSpanProcessor.
    import agent.tracing as tracing

    provider = tracing.setup_tracing()
    if provider is not None:
        try:
            provider.force_flush()
        except Exception as exc:  # noqa: BLE001 - flush is best effort
            print(f"[run_experiment] force_flush failed: {exc}", file=sys.stderr)

    # Read the model the agent actually resolved at import (agent.config reads
    # ANTHROPIC_MODEL once, so this reflects --model when given and the agent
    # default otherwise). Single source of truth for the manifest.
    from agent.config import MODEL as effective_model

    _write_replies(replies, out)
    manifest = _write_manifest(
        out, args, dataset, turn_count, wall_seconds, effective_model, redacted_turns
    )
    print(json.dumps(manifest, indent=2))

    if not spans_path.exists():
        print("WARNING: no spans.jsonl was written; tracing may be disabled", file=sys.stderr)

    rc = _run_evals(spans_path, out)
    if rc != 0:
        print(f"run_evals exited {rc}; see output above", file=sys.stderr)
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
