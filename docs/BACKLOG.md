# Defect Backlog: Detected, Triaged, Deliberately Left Open

## Prioritisation principle

Thirteen code and data defects were found by reading the shipped code and by
running evals against captured spans. **Two were fixed, because eval evidence
justified them.** Ten remain open below, one has since been closed, and every one
of them is detected, attributed to an owner, and left open on purpose.

- **D-01** (system prompt) was fixed because the shipped 3-line prompt
  (`agent/prompt.py:1-7`) contradicts two stated product requirements and the
  baseline run shows the model **ignoring it**: it asked clarifying questions and
  disclosed system limitations 7+ times in 23 turns, all of which that prompt
  forbids (`docs/DAY1_FINDINGS.md:21-22,33-40`). An instruction set the model does
  not follow is not a control surface. Note the honest counterpoint: E1
  (fabricated entity) scored 23/23 pass and E5 (empty-result honesty) 1/1 pass on
  baseline, so D-01 was **not** justified by a measured hallucination rate.
- **D-02** (`search_flights` direction) was fixed because E2 scored **0/6 pass on
  the baseline run** (`docs/evals/e10-scoring-baseline/summary.md`) and every
  failure attributed to the `tool` span, not the model.

Both fixes are **implemented but env-gated and default-off**: `PROMPT_VARIANT`
selects the v1/v2 prompt (`agent/prompt.py:53-56`), `FLIGHT_TOOL_FIX=1` selects
the ordered-route flight search (`agent/tools.py:16`). Neither is the merged
default. Promotion is gated on human approval: `scripts/approval.py:27` binds the
only writable decision to `"pending_human_review"`, and `write_approval`
(`scripts/approval.py:155-163`) raises on any other value, so no loop run can
self-approve.

Fixing every bug would have produced a repo with no risk judgment in it. The
"why it was not fixed" column below is the part that matters.

## Status legend

| Status | Meaning |
|---|---|
| OPEN | Verified still present in the code on the current commit |
| ACCEPTED | Real, understood, consciously not worth fixing at this scope |
| DESCOPED | Offered to the customer and steered away from by the customer |
| CLOSED | Was on this backlog, has since shipped. Listed with evidence at the bottom |

Every OPEN row below was re-verified against the code on 2026-07-21. Verification
commands are in the "How each row was checked" section.

---

## OPEN: code and data defects

| ID | Defect | Severity | Evidence it is real | Owner | Why it was NOT fixed |
|---|---|---|---|---|---|
| D-03 | `search_flights` accepts `date` and never reads it; `data/flights.json` has no date field at all | High | `agent/tools.py:15` takes `date`; the parameter appears in neither the fixed branch (`:16-33`) nor the shipped branch (`:34-45`). Flight records carry only `airline, arrive_time, depart_time, destination, flight_number, origin, price_usd` | Eng + Product | Not a code patch. There is no schedule data to filter on, so fixing it means a data-model decision (add per-date schedules, or declare the tool date-agnostic and make the agent say so). That decision belongs to Product, and the demo authorised two bounded changes only |
| D-04 | `search_hotels` ignores `check_out`; availability is bounded on `check_in` only | High | `agent/tools.py:48-59`. Line 58 tests `h["available_from"] <= check_in <= h["available_to"]`; `check_out` is never referenced. Covered by `tests/test_tools.py:129 test_search_hotels_ignores_check_out` | Eng | The fix is the same shape as D-02 (an ordered-range check), but no eval in the current suite detects it, so shipping it would have been an unmeasured change. Fixing without an eval is exactly the habit this system exists to replace. Add the eval first, then the fix |
| D-05 | `create_itinerary` off by one: a 3-day trip returns 2 days | High | `agent/tools.py:80` is `for day in range(1, int(num_days))`. E4 scored **2 applicable, 0 pass, 2 fail (0%)** on baseline (`docs/evals/baseline-2026-07-19-evalv1/summary.md:10`). Covered by `tests/test_tools.py:135` | Eng | One-line fix, and it is genuinely queued for next sprint. Held out of the demo because the change budget was two, and the two spent were the ones with the larger measured blast radius (E2 at 0/6 across all traffic, versus E4 at 2 applicable traces) |
| D-06 | `get_weather` applies the Celsius-to-Fahrenheit formula to values already in Fahrenheit | Low | `agent/tools.py:73-74` returns `round(high * 5 / 9 + 32)` where `high` derives from `entry["high_f"]` (`:67`). Covered by `tests/test_tools.py:142 test_get_weather_applies_a_celsius_conversion_to_fahrenheit` | Eng | Low severity because the output stays plausible: no user and no human spot-check catches a 20-degree-off forecast that still reads like weather. That is exactly the argument for a fixture-truth eval rather than a quiet patch, so the deliberate choice is to leave the bug in place until an eval exists that would have caught it. Fixing it silently would remove the demonstration |
| D-07 | Fixture coverage holes: no hotels in Denver, Austin, Tokyo or Los Angeles; no weather for London or Denver; no flights Miami to Tokyo or Denver to Miami | High | Computed from `data/*.json`: hotel cities are Chicago, London, Miami, New York, Paris, San Francisco; weather cities are Chicago, Los Angeles, Miami, New York, Paris, San Francisco, Tokyo; the 22 flight routes do not include Miami-Tokyo or Denver-Miami. All of these are reachable from the shipped traffic generator (`scripts/generate_traffic.py:36,39,41,46`) | Product | This is an inventory decision, not a bug. Two legitimate answers exist (expand inventory, or make the agent state its coverage limits explicitly) and they have different product implications. Referenced by ID from `docs/MONITORS.md:233,241,439,480`: monitor 5 is specified muted-and-expected-red while D-07 is open, so this ID must not be renumbered |
| D-08 | No tool for visa, refund or policy questions | Medium | `agent/tools.py:97-149` defines exactly four tools: `search_flights`, `search_hotels`, `get_weather`, `create_itinerary`. Surfaced by the E9 scope-adherence judge | Product | The baseline model already declines or hands off rather than improvising, so the observed behaviour is acceptable today (E9: 23/23 pass on baseline, `docs/evals/judges-baseline-2026-07-19/summary.md`). Building a routing path is net-new product surface, not a defect fix |
| D-09 | Relative dates are unanchored: the model has no current-date reference | Medium | The shipped prompt (`agent/prompt.py:1-7`) contains no date. DAY1 observed the model offering a stale 2024 example date (`docs/DAY1_FINDINGS.md:52-53`) | Eng | Partially mitigated, not closed. The v1 prompt candidate injects today's date (`agent/prompt.py:16-17`), but that candidate is env-gated and unmerged, and a prompt line does not normalise "next Friday" into an ISO date at the tool boundary. The real fix is date normalisation in the tool layer, which is a larger change than the authorised budget |
| D-11 | Anthropic client and session store are both constructed at import time | Medium | `agent/loop.py:16` constructs `anthropic.Anthropic()` at module import. `agent/api.py:58` builds the session store at module import | Eng | Partially mitigated by `agent/session_store.py` (see T-04 below), which moves session state behind a `get`/`put` interface and adds a SQLite backend. What remains open is the import-time client construction and the fact that the default `DictStore` still keeps sessions per process, so multi-worker deployment splits a session's telemetry. Deliberately deferred: Luke steered away from hardening ("we're not super interested in hardening today"), and this is documented in `docs/PRODUCTION_READINESS.md:147` rather than fixed |
| D-12 | `POST /chat` has no auth, no rate limit and no size caps | Low (per Luke: out of scope) | `agent/api.py:76-89`. The handler accepts an unauthenticated `message` and a caller-chosen `conversation_id`, both of which drive durable trace writes and land on spans | Eng | Explicitly out of scope for this engagement. Carried into the production plan (`docs/PRODUCTION_READINESS.md:153`) rather than fixed, because adding auth to a demo endpoint would change nothing measurable about agent quality, which is what the panel asked to see |
| D-13 | Concurrent turns on one `conversation_id` are last-write-wins | Medium | `agent/api.py:79-88` does read (`.get`) then append then `run_agent` then write (`.put`) with no lock and no transaction. `chat` is a sync `def`, so FastAPI runs it in a threadpool and two requests for the same conversation can interleave. Neither backend guards it: `DictStore.put` (`agent/session_store.py:48-49`) is a bare assignment and `SqliteStore.put` (`:69-76`) is an unconditional upsert with no compare-and-swap | Eng | Newly identified, not yet observed in traffic: every captured run is single-threaded synthetic traffic, so there is no measurement behind it. Fixing it means per-conversation locking or optimistic concurrency, which is production hardening (same bucket as D-11 and D-12) and would be an unmeasured change today |

## OPEN: measurement and eval-coverage gaps

These are gaps in the evaluation system itself. They are listed separately
because their owner and their fix shape are different: they are addressed by
collecting data, not by patching the agent.

| ID | Gap | Severity | Evidence it is real | Owner | Why it was NOT fixed |
|---|---|---|---|---|---|
| M-01 | E10 (conflicting context) has near-zero applicability on current traffic | Medium | Counted from `docs/evals/e10-scoring-*/results.jsonl`: E10 is applicable to **1 trace on baseline and 2 traces on each of the 7 experiment runs**, against 23+ traces per run. All applicable rows pass, so E10 has never produced a failure | Eng + Product | The eval is correct; the traffic is the problem. Raising applicability means writing more multi-turn correction scenarios into the golden dataset, which is data work rather than a code fix, and inventing scenarios purely to make an eval fire would be gaming our own metric. Flagged so nobody reads "E10 100% pass" as a strong signal |
| M-02 | E10 misses a bare date change when more than one date is already established | Medium | `evals/e_conflict.py:233` gates the bare-cue path on `len(established) == 1`. Executed check: `["Fly out March 12, 2026 and come back March 20, 2026.", "Actually make it March 14, 2026."]` yields 0 supersession records, while the same correction with only one prior date yields 1, and adding an explicit "instead of March 12, 2026" recovers it | Eng | Conservative by design, and the design is defensible: with two live dates and a bare "make it the 14th", the referent is genuinely ambiguous, and a wrong guess produces a false-positive conflict flag on a correct trace. False positives are more expensive than misses for a monitor-only eval. Resolving it properly needs slot-aware date roles (outbound vs return), which is a rewrite of `_walk_dates`, not a patch |
| M-03 | The E11 tone judge has no baseline measurement, so there is no before/after tone number | Medium | Counted from `docs/evals/judges-*/results.jsonl`: `judges-baseline-2026-07-19` contains **46 rows, E8 and E9 only, zero E11 rows**. E11 exists only on `judges-candidate-AB` (33 rows) and `judges-candidate-C` (33 rows) | Eng | E11 was written after the baseline judge run, and the baseline artifacts are immutable captured evidence. Backfilling would mean re-running judges over baseline spans, which costs paid API calls that were not budgeted before the demo. Consequence stated plainly: no tone improvement can be claimed, only a tone level on the candidate runs |
| M-04 | Judge calibration has almost no discriminating power: two of three judges saw zero failing cases | Medium | Counted from `docs/evals/judges-candidate-AB/results.jsonl`: E9 is 33 pass / 0 fail and E11 is 33 pass / 0 fail; only E8 produced failures (30 pass / 3 fail). `docs/JUDGE_CALIBRATION.md` states the same in its headline and concludes all three judges are monitor-only | Eng + An's team | The binding constraint is the absence of negative examples, not the judges. Manufacturing failing traffic to calibrate against would calibrate the judge on traffic the product does not produce. The correct fix is An's team supplying labelled real failures, which is a customer dependency (An's tone rubric is follow-up question Q3). Until then the honest position is monitor-only, and it is stated as such rather than papered over |
| M-05 | Zero monitors are configured in Arize AX | High (operational) | `docs/MONITORS.md:3-7,21-24`: 8 monitors specified, **0 configured, 0 alert channels provisioned, 0 alerts ever fired** | Eng | Not a fix that can be committed. The project runs on the AX free tier, which has no monitors-as-code path (no API, no Terraform provider, no config export), so monitors are created by hand in the web UI. The honest artifact is a specification plus a UI runbook, and it is labelled PROPOSED everywhere it appears |

## ACCEPTED risks

| ID | Item | Evidence | Why accepted |
|---|---|---|---|
| N-01 | Tracing packages are unconditional imports; a broken install kills the agent | `agent/loop.py:6-8` imports `openinference.instrumentation`, `openinference.semconv.trace` and `opentelemetry.trace` at module scope with no guard | Acceptable with pinned dependencies in a managed environment (`uv.lock` is committed). Guarding the imports would add a degraded-observability mode that hides a real deployment error. Guard only if the runtime environment stops being managed |
| N-02 | `run_agent([])` raises `IndexError` rather than a clean API error | `agent/loop.py:91` reads `messages[-1]["content"]` with no length check | Unreachable from both entrypoints: `agent/api.py:83` and `agent/chat.py:53` both append the user message before calling. Guarding a private function against a call that cannot happen is defensive code for an impossible condition. Guard only if `run_agent` becomes a public API |

## DESCOPED by the customer

| ID | Item | What happened | Status |
|---|---|---|---|
| T-04 | Session state database | Sariya asked "would you be okay if I add a database?" and the panel said yes, but Luke then steered away: "we're not super interested in hardening today... focus is how do we ensure the product is working from an evaluation standpoint" | **Partially shipped anyway, opt-in and default-off.** `agent/session_store.py:52-76` implements a SQLite backend selected only by `SESSION_STORE=sqlite` (`:79-83`); the default remains the in-process `DictStore`, semantically identical to the shipped module-level dict. Durability and single-host cross-process sharing are covered. The concurrency race (D-13) and cross-host sharing (D-11) are not |

---

## CLOSED since the previous revision of this file

These were listed as open. They have shipped. Kept here so the change is
auditable rather than silently deleted.

| Old ID | Was listed as | Now | Evidence |
|---|---|---|---|
| D-10 | "`while True` agent loop, no iteration cap or timeout" | **FIXED** | `agent/config.py:15-16` defines `MAX_AGENT_ITERATIONS` (default 8) and `AGENT_DEADLINE_SECONDS` (default 60). `agent/loop.py:29-37` checks both before each model call; `:101-106` arms the deadline; `:146-160` sets `agent.limit_breached`, sets span status ERROR, and returns `LIMIT_FALLBACK_REPLY` (`:23-26`), which deliberately contains no itinerary content so a truncated run cannot fabricate. Per the rationale comment at `agent/config.py:11-14`, the defaults are set above measured traffic (max observed 3 iterations and 31.5s across 419 captured `agent_turn` spans); that count is quoted from the comment, not recomputed here. 6 tests in `tests/test_loop_limits.py` pass |
| T-01 | "Conflicting/outdated session context not detected; no eval covers it yet" | **IMPLEMENTED as E10** | `evals/e_conflict.py` (14,454 bytes) emits `"eval_id": "E10"` at `:347`. It has run on baseline plus 7 experiment configurations (`docs/evals/e10-scoring-*/`). Residual limitations are now tracked as M-01 (low applicability) and M-02 (multi-date bare cue), not as "no eval exists" |
| T-02 | "Tone/style not evaluated; E8/E9 cover behavior, not tone" | **IMPLEMENTED as E11** | `evals/e_tone.py` emits `"eval_id": "E11"` at `:217`, judges on `claude-sonnet-5` by default, and recomputes `passed` deterministically in Python from the judge's structured booleans rather than trusting the model's own boolean. 33 E11 rows exist on each of `judges-candidate-AB` and `judges-candidate-C`. Residual limitations are now M-03 (no baseline run) and M-04 (no negative examples), plus the rubric being explicitly `provisional-v1-pending-customer-rubric` until An's team supplies theirs |
| T-03 | "No retry/backoff on tool calls; repo has none" | **IMPLEMENTED** | `agent/tools.py:165-180` retries on `_TRANSIENT_ERRORS` (`ConnectionError`, `TimeoutError`, `OSError`, `:162`) up to `TOOL_MAX_RETRIES` (default 3) with exponential backoff `TOOL_RETRY_BASE_SECONDS * 2**(attempt-1)` (default 0.1s), then returns an honest `{"error": "temporarily unavailable after N attempts: ..."}`. Non-transient exceptions still fail fast in one shot. **Caveat stated in the code comment at `:159-161`:** the shipped local JSON tools never raise those exception types, so the retry path is unexercised by real traffic and is covered only by injected-fault tests (`tests/test_tools.py:183,201`, 2 passing) |

## How each row was checked

Re-run these to reproduce the two reclassifications:

```
# T-03: retry/backoff exists in agent/tools.py
command grep -n "max_retries\|backoff_base\|_TRANSIENT_ERRORS\|time.sleep\|TOOL_MAX_RETRIES" agent/tools.py

# D-10: iteration cap and deadline exist in agent/config.py + agent/loop.py
command grep -n "MAX_AGENT_ITERATIONS\|AGENT_DEADLINE_SECONDS\|agent.limit_breached" agent/config.py agent/loop.py

# Both, under test
.venv/bin/python -m pytest tests/test_loop_limits.py tests/test_tools.py -q -k "transient or cap or deadline or fallback"

# M-02: the multi-date bare-cue limitation
PYTHONPATH=evals .venv/bin/python -c "
from e_conflict import _walk_dates
print(_walk_dates(['Fly me out on March 12, 2026.', 'Actually make it March 14, 2026.']))
print(_walk_dates(['Fly out March 12, 2026 and come back March 20, 2026.', 'Actually make it March 14, 2026.']))
"

# M-01 / M-03 / M-04: eval row counts, read-only over captured evidence
.venv/bin/python -c "
import json, glob
from collections import Counter
for p in sorted(glob.glob('docs/evals/*/results.jsonl')):
    c = Counter((json.loads(l).get('eval_id'), json.loads(l).get('passed')) for l in open(p))
    print(p, sorted(c.items(), key=str))
"
```

## Fixed earlier in this engagement (instrumentation layer only)

None of these touch agent behaviour, so none of them can move an eval score:
`traces/` gitignored, trace files written 0600, export path repo-anchored, atomic
tracing setup with honest failure logging, dual-sink processor wiring (working
around the Arize `add_span_processor` removal semantics), and baseline capture
hardened with a port preflight and fail-loud validity gates.
