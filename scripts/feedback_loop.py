"""One entrypoint for the automated improvement loop.

    uv run python scripts/feedback_loop.py \
        --spans <spans.jsonl> \
        --dataset evals/golden_dataset.json \
        --out <run_dir> \
        [--run-experiments] [--propose-with-llm]

Seven stages, each echoed to stdout AND appended to <run_dir>/loop_report.md:

1. COLLECT    resolve the spans file (newest under traces/ if --spans omitted) and
              report the trace count.
2. EVALUATE   subprocess evals/run_evals.py -> <run_dir>/evals/{results.jsonl,summary.md}.
3. CLUSTER    group failing eval results by (eval_id, attribution); counts + examples.
4. CURATE     copy the dataset into the run dir and append the failing cases via
              evals.dataset.append_failures; log old -> new version. The COMMITTED
              dataset is never mutated: the loop curates a copy under <run_dir> and a
              human promotes it. Idempotent: re-running does not clobber the source.
              One case per failing TRACE, carrying the full multi-turn user history,
              the reply, the tool calls and the tool outputs, so the case is
              replayable. expected_behavior is left null with review_status
              "pending": it cannot be derived from a failed trace.
5. PROPOSE    map clusters to the two authorized, env-gated candidates and write
              <run_dir>/proposal.md. E2/tool -> candidate B (FLIGHT_TOOL_FIX=1);
              model-attributed failures (E1/E5/E8-style, prompt-noncompliance) ->
              candidate A (PROMPT_VARIANT=v1); E4/tool -> backlog (no candidate).
5b. PROPOSE (LLM, only with --propose-with-llm) ask the proposer model (default
              claude-opus-4-8, override with PROPOSER_MODEL; temperature 0 where the
              model still accepts it) for a bounded unified diff + 3-sentence
              rationale, capped to the authorized change types (prompt edit /
              modify one tool / add one tool), from the clusters + example rows
              + CURRENT source of the relevant
              surface. Appended to proposal.md under a draft marker; NEVER applied.
              API errors / missing key degrade to the registry-only proposal.
6. EXPERIMENT (only with --run-experiments) run control + each proposed candidate via
              scripts/run_experiment.py on the CURATED dataset copy, then compare into
              <run_dir>/comparison.md.
7. GATE       append a promotion-decision block AND write <run_dir>/approval.json,
              the machine-readable record (run id, UTC timestamp, git sha + dirty
              flag, candidates with their env flags, per-eval quality delta,
              regressions, decision, reviewer, promotion target). ALWAYS emits
              "PROMOTION: BLOCKED pending human approval". The only decision value
              this module can write is "pending_human_review", with a null reviewer
              and a null decision_time; _write_approval refuses anything else. The
              loop never flips agent defaults; candidates stay env-gated until a
              human does. quality_delta is null when experiments did not run: a
              missing measurement is not a measurement of zero.

Stdlib + already-installed deps only. ASCII output only (dashes in captured user
text are normalized to '-' before being written into any file this loop authors).
Immutable style: loaded structures are never mutated in place.
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# agent.* / evals.* resolve against the repo root, not scripts/.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _repo_relative(p) -> str:
    """Serialise a path relative to the repo root so run records stay portable.

    approval.json is committed evidence and is read on other machines, so an
    absolute path captured here leaks the author's home directory and resolves
    nowhere else. Paths outside the repo are returned unchanged.
    """
    resolved = Path(p).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)
# trace_model + dataset live under evals/ and are stdlib-only.
_EVALS_DIR = REPO_ROOT / "evals"
if str(_EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALS_DIR))
# run_experiment.py lives here and owns the single git-sha helper this loop reuses.
_SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Stage 7's schema constants, measurement helpers and writer. Imported after the
# sys.path setup above because approval.py is a sibling under scripts/.
from approval import (  # noqa: E402
    APPROVAL_SCHEMA,
    PENDING_DECISION,
    PROMOTION_TARGET,
    candidate_records as _candidate_records,
    git_dirty as _git_dirty,
    quality_delta as _quality_delta,
    record_note as _record_note,
    regressions as _regressions,
    write_approval as _write_approval,
)

RUN_EVALS = REPO_ROOT / "evals" / "run_evals.py"
RUN_EXPERIMENT = REPO_ROOT / "scripts" / "run_experiment.py"
COMPARE_EXPERIMENTS = REPO_ROOT / "scripts" / "compare_experiments.py"
# docs/ now lives INSIDE the repo (it used to be a sibling of the git root).
CANDIDATES_DOC = REPO_ROOT / "docs" / "proposals" / "CANDIDATES.md"

# --propose-with-llm surfaces (grounded in the real source files the loop reads).
ENV_PATH = REPO_ROOT / ".env"
PROMPT_SOURCE = REPO_ROOT / "agent" / "prompt.py"
TOOLS_SOURCE = REPO_ROOT / "agent" / "tools.py"
# Drafting bounded code diffs is deep-reasoning work: default to the strongest
# current model, env-overridable (was claude-haiku-4-5).
LLM_PROPOSE_MODEL = os.getenv("PROPOSER_MODEL", "claude-opus-4-8")
LLM_PROPOSE_MAX_TOKENS = 2048
DRAFT_MARKER = "## DRAFT CHANGE (LLM-proposed, NOT applied, NOT authorized until human review)"

# Which tool function backs each tool-attributed eval, so the drafter sees the
# precise surface it is asked to change. Grounded in the eval names + tool names
# (E2 flight_direction -> search_flights; E4 itinerary_day_count -> create_itinerary).
# Unmapped tool clusters fall back to the full agent/tools.py source.
_EVAL_TO_TOOL = {
    "E2": "search_flights",
    "E4": "create_itinerary",
}

# The LLM proposer is hard-capped to Nick's authorized change types and to a
# bounded, human-reviewed draft. It never applies anything.
_LLM_SYSTEM_PROMPT = (
    "You are an SRE assistant drafting a SINGLE, low-complexity fix for a travel "
    "agent, for HUMAN REVIEW ONLY. You are hard-capped to exactly ONE of these "
    "authorized change types:\n"
    "  1. Edit the system prompt (agent/prompt.py).\n"
    "  2. Modify exactly ONE existing tool function (agent/tools.py).\n"
    "  3. Add exactly ONE new tool (agent/tools.py).\n"
    "Never propose multi-file refactors, new modules, config sweeps, or large "
    "rewrites. The diff must be minimal and bounded (aim for under 30 changed "
    "lines) and must touch exactly one surface. Output EXACTLY two sections, in "
    "this order:\n"
    "1) A fenced unified diff in a ```diff block against the real file path shown, "
    "using standard '--- a/<path>', '+++ b/<path>', and '@@' hunk headers.\n"
    "2) A line 'Rationale:' followed by exactly three sentences.\n"
    "You are only drafting. Do NOT claim the change is applied."
)

# Common non-ASCII punctuation the model may emit, mapped to ASCII so anything this
# loop writes to disk stays ASCII (never the em dash character). Keys are built
# from code points so this source file itself stays pure ASCII.
_ASCII_MAP = {
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",  # non-breaking space
}


def _to_ascii(text: str) -> str:
    """Normalize the model's punctuation to ASCII before anything is written to
    disk. Broader than _ascii() (which only guards captured user text); used only
    for the LLM draft so the loop's own output never carries the em dash character."""
    for bad, good in _ASCII_MAP.items():
        text = text.replace(bad, good)
    return text

# The two authorized, env-gated candidates. Every field is grounded in the pinned
# contracts (env flags) and docs/proposals/CANDIDATES.md (defect + heading).
CANDIDATES = {
    "A": {
        "flag": "PROMPT_VARIANT=v1",
        "prompt_variant": "v1",
        "flight_tool_fix": "0",
        "defect": "D-01 (prompt contradicts requirements)",
        "heading": "## Candidate A",
        "name": "candidate-A-prompt-v1",
    },
    "B": {
        "flag": "FLIGHT_TOOL_FIX=1",
        "prompt_variant": "v0",
        "flight_tool_fix": "1",
        "defect": "D-02 (flight direction lost + route hidden)",
        "heading": "## Candidate B",
        "name": "candidate-B-flight-tool-fix",
    },
}


def _ascii(text: str) -> str:
    """Collapse em/en dashes to a plain hyphen so text captured from user inputs
    stays ASCII when echoed into files this loop writes. Storage of the dataset
    itself is untouched; this only guards the loop's own reports."""
    return text.replace("\u2014", "-").replace("\u2013", "-")


class Reporter:
    """Echoes each line to stdout and appends it to <run_dir>/loop_report.md so the
    run is legible live and as an artifact. New content only; never rewrites."""

    def __init__(self, report_path: Path):
        self._path = report_path
        self._path.write_text("# Feedback Loop Run\n\n")

    def log(self, line: str = "") -> None:
        safe = _ascii(line)
        print(safe)
        with self._path.open("a") as fh:
            fh.write(safe + "\n")

    def section(self, title: str) -> None:
        self.log("")
        self.log(f"## {title}")
        self.log("")


# --- Stage 1: COLLECT -------------------------------------------------------


def _resolve_spans(spans_arg: str | None) -> Path:
    """Explicit --spans wins; otherwise the newest *.jsonl under traces/."""
    if spans_arg:
        p = Path(spans_arg)
        if not p.exists():
            raise FileNotFoundError(f"spans file not found: {p}")
        return p
    traces_dir = REPO_ROOT / "traces"
    candidates = sorted(traces_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"no --spans given and no *.jsonl under {traces_dir}; nothing to evaluate"
        )
    return candidates[0]


def collect(reporter: Reporter, spans_path: Path) -> int:
    from trace_model import load_traces

    reporter.section("1. COLLECT")
    traces = load_traces(spans_path)
    reporter.log(f"spans file: {spans_path}")
    reporter.log(f"traces loaded: {len(traces)}")
    return len(traces)


# --- Stage 2: EVALUATE ------------------------------------------------------


def evaluate(reporter: Reporter, spans_path: Path, run_dir: Path) -> Path:
    reporter.section("2. EVALUATE")
    evals_out = run_dir / "evals"
    proc = subprocess.run(
        ["uv", "run", "python", str(RUN_EVALS), str(spans_path), str(evals_out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        reporter.log(proc.stdout)
        reporter.log(proc.stderr)
        raise RuntimeError(f"run_evals failed (exit {proc.returncode}); see log above")
    results_path = evals_out / "results.jsonl"
    reporter.log(f"eval results: {results_path}")
    reporter.log(f"eval summary: {evals_out / 'summary.md'}")
    return results_path


def _load_results(results_path: Path) -> list:
    results = []
    with results_path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


# --- Stage 3: CLUSTER -------------------------------------------------------


def cluster(reporter: Reporter, results: list) -> dict:
    """Group failing results by (eval_id, attribution). Each cluster records its
    count, the eval name, example user_inputs, and example trace ids."""
    reporter.section("3. CLUSTER")
    clusters: dict = {}
    for r in results:
        if r.get("passed"):
            continue
        key = (r.get("eval_id", "unknown"), r.get("attribution", "n/a"))
        slot = clusters.get(key)
        if slot is None:
            slot = {"count": 0, "name": r.get("name", ""), "examples": [], "trace_ids": []}
            clusters[key] = slot
        slot["count"] += 1
        if len(slot["examples"]) < 3:
            slot["examples"].append(r.get("user_input", ""))
            slot["trace_ids"].append(r.get("trace_id", ""))

    if not clusters:
        reporter.log("no failing eval results; nothing to cluster.")
        return clusters

    for (eval_id, attribution), slot in sorted(clusters.items()):
        reporter.log(f"- {eval_id} ({slot['name']}) attribution={attribution}: {slot['count']} failure(s)")
        for ex in slot["examples"]:
            reporter.log(f"    e.g. {ex!r}")
    return clusters


# --- Stage 4: CURATE --------------------------------------------------------


def _structured_cases(results: list) -> list:
    """Turn failing eval rows into replayable failure cases, one per trace.

    Grouped by trace because the replay unit is a conversation, not an assertion:
    one trace that fails three evals is one case listing three failure types. The
    payload comes from the row's trace_context (written by evals/run_evals.py),
    so nothing here is inferred. Rows from an older results.jsonl without
    trace_context degrade to the single user_input, which still appends."""
    by_trace: dict = {}
    order: list = []
    for r in results:
        if r.get("passed"):
            continue
        ctx = r.get("trace_context") or {}
        messages = ctx.get("messages") or ([r["user_input"]] if r.get("user_input") else [])
        if not messages:
            continue
        trace_id = r.get("trace_id", "")
        if trace_id not in by_trace:
            order.append(trace_id)
            by_trace[trace_id] = {
                "messages": messages,
                "assistant_reply": ctx.get("assistant_reply", ""),
                "tool_calls": ctx.get("tool_calls", []),
                "tool_outputs": ctx.get("tool_outputs", []),
                "source_trace_id": trace_id or None,
                "source_session_id": ctx.get("session_id") or r.get("session_id"),
                "pii_redacted": bool(ctx.get("pii_redacted", False)),
                "failed_eval_ids": [],
                "failure_reasons": [],
            }
        slot = by_trace[trace_id]
        eval_id = r.get("eval_id", "")
        if eval_id and eval_id not in slot["failed_eval_ids"]:
            slot["failed_eval_ids"] = [*slot["failed_eval_ids"], eval_id]
        reason = r.get("reason", "")
        if reason:
            slot["failure_reasons"] = [*slot["failure_reasons"], f"{eval_id}: {reason}"]
    return [by_trace[t] for t in order]


def curate(reporter: Reporter, results: list, dataset_path: Path, run_dir: Path) -> Path:
    """Copy the dataset into the run dir and append failing cases to the COPY.
    The committed dataset is never mutated; a human promotes the curated copy."""
    from evals.dataset import append_failures, load_dataset

    reporter.section("4. CURATE")
    curated = run_dir / "dataset.curated.json"
    shutil.copyfile(dataset_path, curated)
    old_version = load_dataset(curated)["version"]

    failures = _structured_cases(results)
    new_version = append_failures(curated, failures)
    reporter.log(f"curated dataset copy: {curated}")
    reporter.log(f"failing cases considered: {len(failures)} (one per failing trace)")
    reporter.log(
        "each appended row carries the full user history, the reply, the tool calls "
        "and the tool outputs, with review_status 'pending' and expected_behavior "
        "null for a human to fill."
    )
    if new_version == old_version:
        reporter.log(f"dataset version unchanged: {old_version} (all failures already covered; no-op)")
    else:
        reporter.log(f"dataset version bumped: {old_version} -> {new_version}")
    return curated


# --- Stage 5: PROPOSE -------------------------------------------------------


def _extract_candidate_section(letter: str) -> str:
    """Pull the '## Candidate <letter>' block out of CANDIDATES.md so the change
    description in the proposal is grounded in the committed doc, not invented."""
    heading = CANDIDATES[letter]["heading"]
    if not CANDIDATES_DOC.exists():
        return f"(change description unavailable: {CANDIDATES_DOC} not found)"
    lines = CANDIDATES_DOC.read_text().splitlines()
    out: list = []
    capturing = False
    for line in lines:
        if line.startswith(heading):
            capturing = True
            out.append(line)
            continue
        if capturing:
            if line.startswith("## ") or line.strip() == "---":
                break
            out.append(line)
    return "\n".join(out).strip() or f"(section {heading} not found in CANDIDATES.md)"


def _classify(clusters: dict) -> tuple:
    """Return (proposed_letters, backlog_items). E2/tool -> B; any model-attributed
    failure -> A; E4/tool -> backlog; anything else -> backlog (uncategorized)."""
    proposed: list = []
    backlog: list = []
    for (eval_id, attribution), slot in sorted(clusters.items()):
        if eval_id == "E2" and attribution == "tool":
            if "B" not in proposed:
                proposed.append("B")
        elif attribution == "model":
            if "A" not in proposed:
                proposed.append("A")
        elif eval_id == "E4" and attribution == "tool":
            backlog.append((eval_id, attribution, slot, "no candidate authorized (D-03 backlog)"))
        else:
            backlog.append((eval_id, attribution, slot, "uncategorized; no authorized candidate"))
    return proposed, backlog


def _experiment_cmd(letter: str, dataset_path: Path, run_dir: Path) -> str:
    c = CANDIDATES[letter]
    out = run_dir / "experiments" / c["name"]
    return (
        f"uv run python scripts/run_experiment.py "
        f"--name {c['name']} "
        f"--prompt-variant {c['prompt_variant']} "
        f"--flight-tool-fix {c['flight_tool_fix']} "
        f"--dataset {dataset_path} "
        f"--out {out}"
    )


def propose(reporter: Reporter, clusters: dict, dataset_path: Path, run_dir: Path) -> tuple:
    reporter.section("5. PROPOSE")
    proposed, backlog = _classify(clusters)

    lines = ["# Improvement Proposal", ""]
    if not proposed and not backlog:
        lines.append("No failing clusters; no candidates proposed.")
    lines.append("")

    for letter in proposed:
        c = CANDIDATES[letter]
        evidence = [
            (eid, attribution, slot)
            for (eid, attribution), slot in sorted(clusters.items())
            if (letter == "B" and eid == "E2" and attribution == "tool")
            or (letter == "A" and attribution == "model")
        ]
        lines.append(f"## Candidate {letter}: {c['defect']}")
        lines.append("")
        lines.append(f"- Env flag (enable): `{c['flag']}`")
        lines.append("")
        lines.append("### Evidence")
        for eid, attribution, slot in evidence:
            lines.append(f"- {eid} ({slot['name']}), attribution={attribution}: {slot['count']} failure(s)")
            for ex, tid in zip(slot["examples"], slot["trace_ids"]):
                lines.append(f"  - trace `{tid}` : {_ascii(repr(ex))}")
        lines.append("")
        lines.append("### Experiment command (control + this candidate on the current dataset)")
        lines.append("```")
        control_out = run_dir / "experiments" / "control"
        lines.append(
            f"uv run python scripts/run_experiment.py --name control "
            f"--prompt-variant v0 --flight-tool-fix 0 --dataset {dataset_path} --out {control_out}"
        )
        lines.append(_experiment_cmd(letter, dataset_path, run_dir))
        lines.append("```")
        lines.append("")
        lines.append("### Change description (from docs/proposals/CANDIDATES.md)")
        lines.append("")
        lines.append(_ascii(_extract_candidate_section(letter)))
        lines.append("")

    if backlog:
        lines.append("## Backlog (no authorized candidate)")
        lines.append("")
        for eid, attribution, slot, note in backlog:
            lines.append(f"- {eid} ({slot['name']}), attribution={attribution}: {slot['count']} failure(s) -- {note}")
            for ex in slot["examples"]:
                lines.append(f"  - {_ascii(repr(ex))}")
        lines.append("")

    proposal_path = run_dir / "proposal.md"
    proposal_path.write_text("\n".join(lines) + "\n")
    reporter.log(f"proposal written: {proposal_path}")
    reporter.log(f"candidates proposed: {', '.join(proposed) if proposed else 'none'}")
    if backlog:
        reporter.log(f"backlog clusters: {len(backlog)}")
    return proposed, proposal_path


# --- Stage 5b: PROPOSE (LLM concrete-fix drafter) ---------------------------
# Opt-in via --propose-with-llm. After clustering, ask LLM_PROPOSE_MODEL (default
# claude-opus-4-8, see above) for a bounded unified diff + 3-sentence rationale,
# capped to Nick's authorized change types, and append it to proposal.md under a
# clearly-marked draft section. The
# loop NEVER applies the diff. API errors degrade to the registry-only proposal.


def _extract_function_source(source_path: Path, func_name: str) -> str | None:
    """Return the exact source of a top-level function from a .py file, via ast, so
    the drafter sees the precise surface it is asked to change (not a paraphrase)."""
    if not source_path.exists():
        return None
    src = source_path.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    lines = src.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return None


def _llm_example_rows(results: list, eval_id: str, attribution: str, limit: int = 3) -> list:
    """Up to `limit` failing rows for one cluster, carrying the fields the drafter
    needs: user_input, reason, attribution, evidence."""
    rows: list = []
    for r in results:
        if r.get("passed"):
            continue
        if r.get("eval_id") == eval_id and r.get("attribution") == attribution:
            rows.append(r)
            if len(rows) >= limit:
                break
    return rows


def _build_llm_user_prompt(clusters: dict, results: list) -> tuple:
    """Assemble the user message: every failing cluster (most impactful first) with
    example rows, plus the CURRENT source of the relevant surface(s) -- the system
    prompt for model-attributed clusters, the specific tool function(s) for
    tool-attributed clusters. Returns (prompt_text, surfaces_used)."""
    ordered = sorted(clusters.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    parts: list = ["FAILURE CLUSTERS (most impactful first):", ""]
    include_prompt = False
    tool_funcs: list = []

    for (eval_id, attribution), slot in ordered:
        parts.append(
            f"- {eval_id} ({slot['name']}), attribution={attribution}: "
            f"{slot['count']} failing trace(s)"
        )
        for i, row in enumerate(_llm_example_rows(results, eval_id, attribution), 1):
            ev = json.dumps(row.get("evidence", {}), ensure_ascii=True)
            if len(ev) > 1200:
                ev = ev[:1200] + "...(truncated)"
            parts.append(f"    example {i}:")
            parts.append(f"      user_input: {row.get('user_input', '')!r}")
            parts.append(f"      reason: {row.get('reason', '')!r}")
            parts.append(f"      attribution: {row.get('attribution', '')}")
            parts.append(f"      evidence: {ev}")
        if attribution == "model":
            include_prompt = True
        elif attribution == "tool":
            fn = _EVAL_TO_TOOL.get(eval_id)
            if fn and fn not in tool_funcs:
                tool_funcs.append(fn)

    parts.append("")
    parts.append("CURRENT SOURCE OF THE RELEVANT SURFACE(S):")
    surfaces: list = []

    if include_prompt:
        parts.append("")
        parts.append("# file: agent/prompt.py (system prompt surface)")
        parts.append(PROMPT_SOURCE.read_text().rstrip())
        surfaces.append("agent/prompt.py")

    for fn in tool_funcs:
        fn_src = _extract_function_source(TOOLS_SOURCE, fn)
        if fn_src:
            parts.append("")
            parts.append(f"# file: agent/tools.py -> def {fn} (tool surface)")
            parts.append(fn_src)
            surfaces.append(f"agent/tools.py:{fn}")

    if not surfaces:
        # Unmapped clusters: give the full tool module so the model still has context.
        parts.append("")
        parts.append("# file: agent/tools.py (full module)")
        parts.append(TOOLS_SOURCE.read_text().rstrip())
        surfaces.append("agent/tools.py (full)")

    (top_eval, top_attr), top_slot = ordered[0]
    parts.append("")
    parts.append(
        "Draft ONE bounded fix (per the authorized change types) that addresses the "
        f"single highest-impact cluster: {top_eval} ({top_slot['name']}), "
        f"attribution={top_attr}, {top_slot['count']} failing trace(s). Change only the "
        "surface that backs that cluster. Emit the unified diff first, then 'Rationale:' "
        "with exactly three sentences. Do not apply anything."
    )
    return "\n".join(parts), surfaces


def _extract_unified_diff(text: str) -> str | None:
    """Return a parseable unified diff from the model output, or None. Prefers a
    fenced ```diff block; falls back to a raw region. 'Parseable' means it carries a
    hunk header (@@) and a file header (---/+++ or diff --git)."""
    def looks_like_diff(s: str) -> bool:
        return "@@" in s and ("--- " in s or "+++ " in s or "diff --git" in s)

    fence = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, re.DOTALL)
    if fence and looks_like_diff(fence.group(1)):
        return fence.group(1).strip()
    if looks_like_diff(text):
        return text.strip()
    return None


def _load_llm_env() -> None:
    """Load .env from the explicit repo path and require ANTHROPIC_API_KEY. Raises
    RuntimeError (never prints the value) if the key is absent."""
    from dotenv import load_dotenv

    if ENV_PATH.exists():
        load_dotenv(str(ENV_PATH))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set (checked env and .env)")


def _call_llm(user_prompt: str) -> str:
    """Single proposer-model call. Returns the concatenated text. Temperature 0
    is requested when the model still supports it; the 4.6+ family (incl.
    claude-opus-4-8) removed the parameter and 400s when it is sent, so we
    fall back without it (same pattern as evals/e_tone.py)."""
    import anthropic

    client = anthropic.Anthropic()
    create_kwargs = dict(
        model=LLM_PROPOSE_MODEL,
        max_tokens=LLM_PROPOSE_MAX_TOKENS,
        system=_LLM_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    try:
        resp = client.messages.create(temperature=0, **create_kwargs)
    except Exception as exc:
        if "temperature" not in str(exc).lower():
            raise
        resp = client.messages.create(**create_kwargs)
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _append_draft(proposal_path: Path, raw: str, diff: str | None) -> None:
    """Append the LLM draft to proposal.md under the draft marker. Parseable diffs are
    labeled; non-parseable output is written verbatim under a warning. Nothing is
    applied. All text is normalized to ASCII first."""
    raw = _to_ascii(raw.strip())
    body = [
        DRAFT_MARKER,
        "",
        f"Generated by {LLM_PROPOSE_MODEL} (temperature 0) from the failure clusters and "
        "the current source of the relevant surface. This is a DRAFT for human review; "
        "the loop does NOT apply it and it is NOT authorized until a human approves.",
        "",
    ]
    if diff is None:
        body.append(
            "WARNING: the model output below was NOT a parseable unified diff. It is "
            "reproduced verbatim for human review; nothing was applied."
        )
        body.append("")
        body.append("```text")
        body.append(raw)
        body.append("```")
    else:
        body.append(
            "A bounded unified diff was detected below (unmodified model output). It is "
            "for human review only and has NOT been applied to any file."
        )
        body.append("")
        body.append(raw)
    with proposal_path.open("a") as fh:
        fh.write("\n" + "\n".join(body) + "\n")


def _append_unavailable_note(proposal_path: Path, note: str) -> None:
    """Degrade path: record that no LLM draft was produced, leaving the registry-only
    proposal above as the actionable output. No draft marker (there is no draft)."""
    body = [
        "## LLM draft: unavailable",
        "",
        _to_ascii(note),
        "The registry-based proposal above stands unchanged; no diff was drafted or applied.",
    ]
    with proposal_path.open("a") as fh:
        fh.write("\n" + "\n".join(body) + "\n")


def propose_with_llm(reporter: Reporter, clusters: dict, results: list, proposal_path: Path) -> None:
    reporter.section("5b. PROPOSE (LLM draft)")
    if not clusters:
        reporter.log("no failing clusters; no LLM draft requested.")
        return
    try:
        _load_llm_env()
    except RuntimeError as exc:
        reporter.log(f"LLM draft skipped: {exc}; registry-only proposal stands.")
        _append_unavailable_note(proposal_path, f"LLM draft unavailable: {exc}.")
        return

    user_prompt, surfaces = _build_llm_user_prompt(clusters, results)
    reporter.log(f"surfaces sent to model: {', '.join(surfaces) if surfaces else 'none'}")
    reporter.log(f"model: {LLM_PROPOSE_MODEL} (temperature 0); diff is NEVER applied.")

    try:
        raw = _call_llm(user_prompt)
    except Exception as exc:  # degrade to registry-only; never crash the loop
        reporter.log(f"LLM proposal API error: {type(exc).__name__}: {exc}")
        reporter.log("degrading to registry-only proposal (no diff drafted or applied).")
        _append_unavailable_note(
            proposal_path, f"LLM draft unavailable (API error: {type(exc).__name__})."
        )
        return

    diff = _extract_unified_diff(raw)
    _append_draft(proposal_path, raw, diff)
    if diff is None:
        reporter.log("model output was NOT a parseable diff; written verbatim under a warning.")
    else:
        reporter.log("bounded unified diff drafted and written under the draft marker (NOT applied).")
    reporter.log(f"draft appended to: {proposal_path}")


# --- Stage 6: EXPERIMENT ----------------------------------------------------


def _run_experiment(reporter: Reporter, name, prompt_variant, flight_tool_fix, dataset_path, out_dir) -> bool:
    proc = subprocess.run(
        [
            "uv", "run", "python", str(RUN_EXPERIMENT),
            "--name", name,
            "--prompt-variant", prompt_variant,
            "--flight-tool-fix", flight_tool_fix,
            "--dataset", str(dataset_path),
            "--out", str(out_dir),
        ],
        cwd=REPO_ROOT,
    )
    ok = proc.returncode == 0
    reporter.log(f"experiment {name}: {'ok' if ok else f'FAILED (exit {proc.returncode})'}")
    return ok


def experiment(reporter: Reporter, proposed: list, dataset_path: Path, run_dir: Path) -> dict | None:
    """Run control + each proposed candidate and compare.

    Returns None when nothing was measured, otherwise
    {"comparison_path", "control_dir", "candidate_dirs": {name: Path}}. The gate
    needs the directories, not just the rendered markdown, to record a per-eval
    quality delta in approval.json."""
    reporter.section("6. EXPERIMENT")
    if not proposed:
        reporter.log("no candidates proposed; skipping experiments.")
        return None

    exp_root = run_dir / "experiments"
    control_out = exp_root / "control"
    if not _run_experiment(reporter, "control", "v0", "0", dataset_path, control_out):
        reporter.log("control run failed; cannot compare.")
        return None

    run_dirs = [control_out]
    candidate_dirs: dict = {}
    for letter in proposed:
        c = CANDIDATES[letter]
        out_dir = exp_root / c["name"]
        if _run_experiment(reporter, c["name"], c["prompt_variant"], c["flight_tool_fix"], dataset_path, out_dir):
            run_dirs.append(out_dir)
            candidate_dirs[c["name"]] = out_dir

    if len(run_dirs) < 2:
        reporter.log("fewer than 2 successful runs; no comparison produced.")
        return None

    comparison_path = run_dir / "comparison.md"
    proc = subprocess.run(
        ["uv", "run", "python", str(COMPARE_EXPERIMENTS), *[str(d) for d in run_dirs], "--out", str(comparison_path)],
        cwd=REPO_ROOT,
    )
    if proc.returncode != 0:
        reporter.log(f"compare_experiments failed (exit {proc.returncode})")
        return {"comparison_path": None, "control_dir": control_out, "candidate_dirs": candidate_dirs}
    reporter.log(f"comparison written: {comparison_path}")
    return {
        "comparison_path": comparison_path,
        "control_dir": control_out,
        "candidate_dirs": candidate_dirs,
    }


# --- Stage 7: GATE ----------------------------------------------------------
# The gate emits <run_dir>/approval.json, the machine-readable record of what was
# proposed and what was measured. The ONLY decision value this module can write is
# PENDING_DECISION: reviewer and decision_time are always null on write, and
# approval.write_approval refuses any other decision. A human edits the file to
# record a real decision; nothing in this loop can do it. The schema constants, the
# measurement helpers and the writer live in scripts/approval.py.


def _git_sha() -> str:
    """Reuse the single sha helper in scripts/run_experiment.py rather than
    defining a second one. It returns 'unknown' on any git failure."""
    from run_experiment import _git_sha as _run_experiment_git_sha

    return _run_experiment_git_sha()


def _build_approval_record(run_dir: Path, proposed: list, outcome: dict | None) -> dict:
    """Assemble the approval record. `decision` is bound to PENDING_DECISION here
    and nowhere else in this module; reviewer and decision_time are null on write.
    The human gate is the point, so the loop cannot express any other decision."""
    delta = _quality_delta(outcome)
    comparison = (outcome or {}).get("comparison_path")
    return {
        "schema": APPROVAL_SCHEMA,
        "run_id": run_dir.name,
        "run_dir": _repo_relative(run_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(REPO_ROOT),
        "candidate_ids": _candidate_records(proposed, CANDIDATES),
        "quality_delta": delta,
        "regressions": _regressions(delta),
        "decision": PENDING_DECISION,
        "reviewer": None,
        "decision_time": None,
        "promotion_target": PROMOTION_TARGET,
        "comparison_report": str(comparison) if comparison else None,
        "note": _record_note(),
    }


def gate(reporter: Reporter, proposed: list, outcome: dict | None, run_dir: Path) -> Path:
    """Emit the prose decision block AND the machine-readable approval record."""
    reporter.section("7. GATE")
    record = _build_approval_record(run_dir, proposed, outcome)
    approval_path = _write_approval(run_dir, record)

    comparison_path = (outcome or {}).get("comparison_path")
    reporter.log("Promotion decision:")
    if comparison_path is not None:
        reporter.log(f"- metric deltas: see {comparison_path}")
    else:
        reporter.log("- metric deltas: not measured (experiments not run; pass --run-experiments with ANTHROPIC_API_KEY)")
    if record["quality_delta"] is None:
        reporter.log("- quality_delta recorded as null (not measured), NOT as zero")
    else:
        reporter.log(f"- quality_delta recorded for: {', '.join(sorted(record['quality_delta']))}")
    reporter.log(f"- regressions detected: {len(record['regressions'])}")
    reporter.log(f"- candidates awaiting review: {', '.join(proposed) if proposed else 'none'}")
    reporter.log(f"- git: {record['git_sha']} (dirty={record['git_dirty']})")
    reporter.log(f"- decision recorded: {record['decision']} (reviewer: null)")
    reporter.log("- PROMOTION: BLOCKED pending human approval")
    reporter.log(f"- machine-readable record: {approval_path}")
    reporter.log(
        "- rationale: the loop never mutates agent defaults; candidates stay env-gated "
        "(PROMPT_VARIANT / FLIGHT_TOOL_FIX) until a human flips them."
    )
    return approval_path


# --- Orchestration ----------------------------------------------------------


def _parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="feedback_loop.py",
        description="Automated evaluate -> cluster -> curate -> propose -> gate loop.",
    )
    parser.add_argument("--spans", help="Spans JSONL. Default: newest *.jsonl under traces/.")
    parser.add_argument("--dataset", required=True, help="Golden dataset JSON (copied, never mutated).")
    parser.add_argument("--out", required=True, help="Run output directory.")
    parser.add_argument(
        "--run-experiments",
        action="store_true",
        help="Also run control + candidate experiments and compare (needs ANTHROPIC_API_KEY).",
    )
    parser.add_argument(
        "--propose-with-llm",
        action="store_true",
        help=(
            "After clustering, ask the proposer model (default claude-opus-4-8, "
            "override with PROPOSER_MODEL) for a bounded "
            "unified diff + rationale, capped to authorized change types, and append it "
            "to proposal.md under a draft marker. The loop NEVER applies the diff. "
            "Without this flag, behavior is byte-identical to the registry-only loop."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list) -> int:
    args = _parse_args(argv)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"dataset not found: {dataset_path}", file=sys.stderr)
        return 2

    run_dir = Path(args.out)
    run_dir.mkdir(parents=True, exist_ok=True)
    reporter = Reporter(run_dir / "loop_report.md")

    try:
        spans_path = _resolve_spans(args.spans)
    except FileNotFoundError as exc:
        print(f"collect error: {exc}", file=sys.stderr)
        return 2

    collect(reporter, spans_path)
    results_path = evaluate(reporter, spans_path, run_dir)
    results = _load_results(results_path)
    clusters = cluster(reporter, results)
    curated_dataset_path = curate(reporter, results, dataset_path, run_dir)
    proposed, proposal_path = propose(reporter, clusters, curated_dataset_path, run_dir)

    if args.propose_with_llm:
        propose_with_llm(reporter, clusters, results, proposal_path)

    outcome = None
    if args.run_experiments:
        outcome = experiment(reporter, proposed, curated_dataset_path, run_dir)
    else:
        reporter.section("6. EXPERIMENT")
        reporter.log("skipped (--run-experiments not set).")

    gate(reporter, proposed, outcome, run_dir)
    reporter.log("")
    reporter.log(f"loop report: {run_dir / 'loop_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
