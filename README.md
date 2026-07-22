# AI Travel Agent

A simple AI travel agent built on the Anthropic API. It helps users plan trips: searching flights and hotels, checking the weather, and assembling day-by-day itineraries. All travel data comes from local JSON fixtures in `data/`; there are no external API calls beyond the LLM.

It exposes two interfaces:

- an interactive **CLI chat** (`python -m agent.chat`)
- a **FastAPI endpoint** (`POST /chat`) with in-memory multi-turn conversations

## How it works

The agent is a standard Anthropic tool-calling loop, written plainly with no frameworks:

```
agent/
├── config.py   # env vars (model, data dir)
├── prompt.py   # system prompt
├── tools.py    # tool schemas + implementations backed by data/*.json
├── loop.py     # the tool-calling loop
├── chat.py     # CLI entrypoint
└── api.py      # FastAPI app
data/
├── flights.json
├── hotels.json
└── weather.json
scripts/
└── generate_traffic.py   # sends ~20 sample queries to the API
```

The model can call four tools:

| Tool | What it does |
|---|---|
| `search_flights(origin, destination, date)` | Look up flights between two cities |
| `search_hotels(city, check_in, check_out)` | Look up hotels for a stay |
| `get_weather(city, date)` | Get a forecast for a city |
| `create_itinerary(destination, num_days, notes?)` | Assemble a day-by-day trip plan |

## Setup

Requires Python 3.11+ and an Anthropic API key.

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Then configure your key:

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

Environment variables:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | none | Anthropic API key |
| `ANTHROPIC_MODEL` | no | `claude-haiku-4-5` | Model used by the agent |
| `MAX_AGENT_ITERATIONS` | no | `8` | Maximum model calls in one user turn before the loop stops (`agent/config.py`) |
| `AGENT_DEADLINE_SECONDS` | no | `60` | Wall-clock budget for one user turn, in seconds (`agent/config.py`) |

`MAX_AGENT_ITERATIONS` and `AGENT_DEADLINE_SECONDS` bound the tool-calling loop in
`agent/loop.py`, which is otherwise a `while True`. Both are checked immediately before
each model call, so a request already in flight is never cut off mid-call. When either
limit is reached the turn stops and the agent returns this fixed reply verbatim:

> I could not complete the itinerary reliably within the allowed number of steps. Please
> revise the request or try again.

The fallback deliberately contains no itinerary content. A truncated run has no verified
tool inventory behind it, so emitting flights, hotels, or prices at that point would mean
fabricating them; the agent returns the honest failure instead. The breach is also recorded
on the `agent_turn` span (`agent.limit_breached` set to `max_iterations` or `deadline`, span
status `ERROR`) so it is visible in traces rather than silent.

The defaults sit above measured traffic rather than being guessed. Across the 419
`agent_turn` spans in the captured runs under `docs/`, the highest observed iteration count
is 3 (limit 8) and the longest observed turn is 31.5 seconds (limit 60), so neither control
fires on any run captured so far.

## Usage

### CLI chat

```bash
uv run python -m agent.chat
```

```
you> Find me a flight from New York to Miami on March 12, 2026.
agent> I found a few options for you! ...
```

Type `quit` (or Ctrl-D) to exit. Conversation history is kept for the session.

### API

Start the server:

```bash
uv run uvicorn agent.api:app
```

Send a message:

```bash
curl -s localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "I need a hotel in Paris from June 10 to June 14, 2026."}'
```

```json
{"reply": "Here are some hotels in Paris for those dates! ...", "conversation_id": "1f0e..."}
```

To continue a conversation, pass the returned `conversation_id` back:

```bash
curl -s localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Which one is cheapest?", "conversation_id": "1f0e..."}'
```

Conversations are held in memory and reset when the server restarts. `GET /health` returns `{"status": "ok"}`.

### Traffic generator

With the API server running, send ~20 varied sample queries (including one multi-turn conversation):

```bash
uv run python scripts/generate_traffic.py
```

Point it at a different host with an argument or env var:

```bash
uv run python scripts/generate_traffic.py http://localhost:9000
# or
TRAVEL_AGENT_URL=http://localhost:9000 uv run python scripts/generate_traffic.py
```

## Notes

- Flight, hotel, and weather data are static fixtures: edit the files in `data/` to change what the agent can find.
- There is no database, auth, or persistence; this is intentionally a minimal service.

---

# Observability, evaluation, and experiment tooling (engagement additions)

Everything below was added on top of the upstream sample agent to make it observable,
measurable, and improvable. It is all additive: with every new env var left unset the
agent behaves byte-identically to the shipped version. All commands are verified to run
as written.

## 0. Repository layout

Every path in this README, in `scripts/`, and in the CI workflow is repo-relative and is
resolved from the repository root at runtime, so the checkout can live at any absolute path
without edits. Run all commands from the repository root.

What the commands do require is that the engagement additions are actually present in the
checkout. `docs/`, `evals/`, `.github/`, and all of `scripts/` except the upstream
`generate_traffic.py`, plus three `agent/` modules, were added during this engagement and
are not part of the upstream sample. Check any checkout with:

```bash
git ls-files docs evals scripts .github | wc -l
```

If that prints `1`, only the upstream `scripts/generate_traffic.py` is tracked: the
engagement additions have not been committed yet, and a clone of the remote will not contain
them, so work from the working copy rather than a fresh clone. Once they are committed the
count is far higher and a fresh clone is self-sufficient.

```
agent/      the shipped agent, plus additive tracing / redaction / session modules
data/       static JSON fixtures (flights, hotels, weather)
evals/      the E1-E9 eval suite, the golden dataset, and judge calibration
scripts/    baseline capture, experiment runner, comparison, feedback loop, Arize push
docs/       all engagement output and captured evidence (in-repo, see below)
traces/     local span sink (gitignored)
```

Captured evidence lives under `docs/` and is treated as immutable once written:

```
docs/baseline/       the Day 0 baseline capture (spans, manifest, logs)
docs/evals/          eval results scored against each run
docs/experiments/    per-variant experiment runs (spans, replies, manifest, evals)
docs/loop-runs/      recorded feedback-loop runs
docs/proposals/      the authorized candidate-change registry
docs/verification/   fixture re-derivation checks
```

## 1. Observability (tracing)

`agent/tracing.py` sets up OpenInference / OpenTelemetry tracing around the Anthropic
tool-calling loop. Setup is idempotent and fail-open: if any tracing dependency or
exporter fails to initialize, the agent logs a line and continues untraced. It never
changes agent behavior.

Spans are written to two sinks at once (dual-sink export):

- **Arize AX** via the OTLP batch processor, but only when both `ARIZE_SPACE_ID` and
  `ARIZE_API_KEY` are set. When they are unset, tracing falls back to a plain local
  `TracerProvider` and no data leaves the machine.
- **A local JSONL file**, one span per line, so every captured span survives
  independently of any platform retention window. The file is created owner-only (0600)
  because spans carry full conversation content.

Tracing environment variables:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ARIZE_SPACE_ID` | no | unset | Arize AX space id; the Arize sink turns on only when this and the API key are both present |
| `ARIZE_API_KEY` | no | unset | Arize AX API key; pairs with the space id to enable the OTLP export |
| `TRACE_EXPORT_PATH` | no | `<repo>/traces/spans.jsonl` | Path for the local JSONL span sink |
| `TRACING_DISABLED` | no | unset | Set to `1` or `true` to skip tracing setup entirely |

The `traces/` directory is gitignored, so captured spans are never committed by accident.

## 2. Evaluation

Two CLIs score a captured `spans.jsonl` file. Both take the same positional arguments
(`<spans.jsonl> <output_dir>`), exit `0` whenever they run to completion (a failing eval
is data, not a runner error), and exit `2` only on an IO or import failure.

Deterministic suite (no API key, no model calls):

```bash
uv run python evals/run_evals.py <spans.jsonl> <output_dir>
```

Writes `results.jsonl` and `summary.md` into `<output_dir>` and prints the summary table.

LLM-as-judge suite (needs `ANTHROPIC_API_KEY`; uses `claude-haiku-4-5` at temperature 0):

```bash
uv run python evals/run_judges.py <spans.jsonl> <output_dir>
```

Writes `results.jsonl`, `summary.md`, and a `calibration_sheet.csv` (one row per judged
trace, with the `human_label` column intentionally left EMPTY for human review).

### The E1-E9 portfolio

| Eval | Name | What it checks |
|---|---|---|
| E1 | `fabricated_entity` | PRIMARY metric: flags any option named in the reply that no tool returned this turn or any prior turn (model invented or leaked it). |
| E2 | `flight_direction` | Flags a recommended flight whose true route is the reverse of what the user asked for; attributed to the tool, which matches origin/destination as an unordered set. |
| E3 | `tool_call_validity` | Validates the input the model built for every tool call against each tool's required params and strict `YYYY-MM-DD` date format. |
| E4 | `itinerary_day_count` | Checks that `create_itinerary` delivered the number of days the user requested. |
| E5 | `empty_result_honesty` | Flags a reply that asserts a concrete bookable option when every tool call this turn came back empty or errored. |
| E6 | `pii` | Scans user input and reply for SSNs and Luhn-valid payment-card numbers. |
| E7 | `guardrails` | Reports per-turn telemetry (latency, tokens, iterations, computed cost) and fails when any metric exceeds its configured ceiling. |
| E8 | `clarification_quality` | LLM-as-judge: did the agent ask for clarification when the request was underspecified? Judge verdict is recomputed deterministically in Python. |
| E9 | `scope_adherence` | LLM-as-judge: did the agent stay within travel-planning scope? Same deterministic re-scoring of the judge verdict. |

E1 through E7 run under `run_evals.py`; E8 and E9 (the judges) run under `run_judges.py`.

## 3. Experiments

Two CLIs run and compare A/B experiments over the golden dataset.

Run one experiment (replay the dataset through the agent under a fixed variant, export
spans and replies plus a manifest, then score with the deterministic suite):

```bash
uv run python scripts/run_experiment.py \
  --name <label> \
  --prompt-variant v0 \
  --flight-tool-fix 0 \
  --dataset evals/golden_dataset.json \
  --out <out_dir> \
  [--model <model-id>]
```

`--name`, `--prompt-variant`, `--flight-tool-fix`, `--dataset`, and `--out` are all required.
`--model` is optional: it sets `ANTHROPIC_MODEL` before any `agent.*` import, so a run can
test a different model without touching config. Omit it and the agent default
(`claude-haiku-4-5` unless `ANTHROPIC_MODEL` is already set) is used, leaving behavior
unchanged.

Compare two or more run directories (the first is the control; others are reported as
deltas against it):

```bash
uv run python scripts/compare_experiments.py <dir1> <dir2> [<dir3> ...] [--out report.md]
```

Candidate fixes are gated by two environment variables, both defaulting to the shipped
behavior. The experiment runner sets them from its flags before importing any `agent.*`
module (agent modules read these at import time):

| Env var | Flag | Shipped value | Candidates |
|---|---|---|---|
| `PROMPT_VARIANT` | `--prompt-variant` | `v0` | `v1`, `v2` (candidate prompts) |
| `FLIGHT_TOOL_FIX` | `--flight-tool-fix` | `0` | `1` (direction-corrected `search_flights`) |

`--prompt-variant` accepts three values (`PROMPT_VARIANTS` in `scripts/run_experiment.py`),
each selecting a system prompt built in `agent/prompt.py`:

| Value | System prompt |
|---|---|
| `v0` | The shipped 3-line prompt, unchanged. Any value other than `v1` or `v2` also falls back to this. |
| `v1` | Candidate A (D-01): adds today's date for anchoring relative dates, a strict grounding rule (every hotel, flight, price, and availability claim must come from a tool result this conversation), an instruction to say so plainly on an empty or failed search, one consolidated clarifying question when booking-material info is missing, and a travel-only scope rule that hands visa, refund, and policy questions to a human. |
| `v2` | Candidate C (v2-concise): the full `v1` text plus an output-style section (lead with the answer, no preamble or closing filler, short one-line bullets, at most 3 options, at most one warm sentence). Aimed at cutting output tokens without losing tone. |

With `--prompt-variant v0 --flight-tool-fix 0` and no `--model`, the agent behaves
identically to the shipped version, so a control run reproduces baseline behavior exactly.

## 4. Feedback loop

`scripts/feedback_loop.py` is one entrypoint that chains the evaluate-to-propose pipeline.
Each stage is echoed to stdout and appended to `<run_dir>/loop_report.md`:

1. **COLLECT** resolve the spans file (newest under `traces/` if `--spans` is omitted) and report the trace count.
2. **EVALUATE** run `evals/run_evals.py` into `<run_dir>/evals/`.
3. **CLUSTER** group failing results by `(eval_id, attribution)` with counts and examples.
4. **CURATE** copy the dataset into the run dir and append failing cases; the committed dataset is never mutated.
5. **PROPOSE** map clusters to the two authorized env-gated candidates and write `proposal.md`.
6. **EXPERIMENT** (only with `--run-experiments`) run control plus each candidate and compare.
7. **GATE** append a promotion decision; it always emits "PROMOTION: BLOCKED pending human approval". The loop never flips agent defaults.

Default run (no API key, no model calls):

```bash
uv run python scripts/feedback_loop.py \
  --spans <spans.jsonl> \
  --dataset evals/golden_dataset.json \
  --out <run_dir>
```

Add `--run-experiments` (needs `ANTHROPIC_API_KEY`) to also run stage 6.

### Scheduled run (GitHub Actions cron)

`.github/workflows/feedback-loop.yml` runs the loop nightly at `07:00 UTC`
(`cron: "0 7 * * *"`) and on manual `workflow_dispatch`. It runs the no-experiments loop
by default, and runs the experiment stage only when the `ANTHROPIC_API_KEY` secret is
configured. Loop outputs are uploaded as a `feedback-loop-run` artifact.

## 5. Baseline capture

`scripts/capture_baseline.py` records an immutable baseline: it boots the API on a
dedicated port (8317) with tracing on, replays the shipped traffic generator, exports
every span to disk, validates that the captured root-span count matches the messages
sent, and writes a `manifest.json` (git sha, dirty flag, model, span and turn counts).

```bash
uv run python scripts/capture_baseline.py <output_dir>
```

The output directory must not already contain a capture; baselines are never overwritten.

### Pushing artifacts to Arize AX

Upload the golden dataset and attach all eval scores to the traced spans in the
AX project (idempotent; requires ARIZE_SPACE_ID and ARIZE_API_KEY in .env):

    uv run python scripts/push_to_arize.py push-dataset
    uv run python scripts/push_to_arize.py push-evals

Re-ingest specific traces from a local spans.jsonl with their original ids and
timestamps (recovery for batches lost at process exit):

    uv run python scripts/replay_spans_to_arize.py <spans.jsonl> <trace_id> [...]

## 6. Remaining environment variables

Every other variable read by `agent/` or `scripts/`. All are optional and all default to the
shipped behavior, so an empty `.env` beyond `ANTHROPIC_API_KEY` runs the agent as shipped.
`.env.example` lists each of them commented out.

| Variable | Default | Read by | Purpose |
|---|---|---|---|
| `PROMPT_VARIANT` | unset (`v0` prompt) | `agent/prompt.py` | Selects the system prompt; see section 3. Read at import time. |
| `FLIGHT_TOOL_FIX` | unset (shipped tool) | `agent/tools.py` | `1` enables the direction-corrected `search_flights`; see section 3. |
| `PROMPT_CACHE` | unset (off) | `agent/loop.py` | `1` adds Anthropic prompt caching to the `messages.create` call. Left unset, the call shape is byte-identical to the shipped agent. |
| `TOOL_MAX_RETRIES` | `3` | `agent/tools.py` | Attempts per tool call before returning an error result. Only transient `ConnectionError` / `TimeoutError` / `OSError` are retried; the local JSON tools never raise these. |
| `TOOL_RETRY_BASE_SECONDS` | `0.1` | `agent/tools.py` | Base delay for the retry backoff, in seconds. |
| `SESSION_STORE` | unset (in-memory) | `agent/session_store.py` | Set to `sqlite` to persist API conversations across restarts instead of holding them in a process dict. |
| `SESSION_DB_PATH` | `<repo>/sessions.db` | `agent/session_store.py` | SQLite file path, used only when `SESSION_STORE=sqlite`. |
| `ARIZE_PROJECT_NAME` | `travel-agent` | `agent/tracing.py` | AX project spans are written to; also the OTel tracer name. |
| `PROMPT_VERSION` | `v0-shipped` | `agent/tracing.py`, `scripts/capture_baseline.py` | Value of the `prompt_version` span attribute and the baseline manifest field. `scripts/run_experiment.py` sets it to the run's prompt variant. |
| `AGENT_VERSION` | `baseline-0080b11` | `agent/tracing.py`, `scripts/capture_baseline.py` | Value of the `agent_version` span attribute and the baseline manifest field. `scripts/run_experiment.py` sets it to `--name`. |
| `PROPOSER_MODEL` | `claude-opus-4-8` | `scripts/feedback_loop.py` | Model used to draft candidate changes, and only when the loop is run with `--propose-with-llm`. |
| `TRAVEL_AGENT_URL` | `http://localhost:8000` | `scripts/generate_traffic.py` | Target API for the traffic generator; a positional argument overrides it. |

`TRACE_EXPORT_PATH`, `TRACING_DISABLED`, `ARIZE_SPACE_ID`, and `ARIZE_API_KEY` are documented
in section 1.
