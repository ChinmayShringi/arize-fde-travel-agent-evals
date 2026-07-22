# Defect Backlog: Detected, Deliberately Not Fixed in the Demo

Two fixes ship as loop outputs (D-01 prompt, D-02 flight direction; see
docs/proposals/CANDIDATES.md). Everything else is detected, attributed, and owned.
Prioritization is the point: a repo with every bug quietly fixed has no story and
no risk judgment.

| ID | Defect | Severity | Detected by | Attribution | Owner | Recommendation |
|---|---|---|---|---|---|---|
| D-05 | create_itinerary off-by-one (range(1, num_days)) | High | E4: 0% pass on baseline (2/2 failed) | Tool | Eng | One-line fix; next sprint. Not in demo scope: only two bounded changes were authorized |
| D-03 | search_flights accepts date but ignores it; no date field in data | High | Not directly evaluable (every flight answer is date-ungrounded) | Tool/data | Eng + Product | Requires a data-model decision (add schedules), not a code patch |
| D-04 | search_hotels ignores check_out | High | Detectable via availability cross-check; not in E1-E7 v1 | Tool | Eng | Add ordered-range check alongside the D-02 pattern |
| D-07 | Coverage holes (hotels: Denver/Austin/Tokyo; weather: London; flights: Miami-Tokyo, Denver-Miami) | High | E5 + coverage_gap notes in E3 evidence | Data | Product | Decide: expand inventory or make the agent state coverage limits explicitly |
| D-06 | get_weather applies C-to-F conversion to Fahrenheit values | Low | Not in E1-E7 v1; deterministic check possible against fixtures | Tool | Eng | Plausible-looking output is exactly what human spot-checks miss; add a fixture-truth eval when weather matters |
| D-08 | No tool for visa/refund questions | Medium | E9 judge (scope adherence) | Product gap | Product | Baseline model already declines/hands off; codify with v1 prompt scope rule + routing |
| D-09 | Relative dates unanchored ("next Friday") | Medium | E3 fails relative dates when passed to tools; DAY1: model offered stale 2024 example date | Model+prompt | Eng | v1 prompt adds current date; full fix needs date normalization at the tool boundary |
| D-10 | while True agent loop, no iteration cap or timeout | Medium | E7 iteration count monitors it; no breach on baseline (max 2) | Code | Eng | Cap iterations + timeout before production; cost blast radius |
| D-11 | Module-level CONVERSATIONS dict + client at import | Medium | Breaks multi-worker session telemetry (splits sessions across processes) | Code | Eng | Externalize conversation state before scaling past one worker |
| D-12 | No auth or rate limit on POST /chat | Low (per Luke: out of scope) | Security review: unauthenticated input drives unbounded durable trace writes; attacker-chosen conversation_id lands on spans | Code | Eng | In production plan: auth, rate limit, size caps on message and conversation_id |
| N-01 | Tracing packages are unconditional imports; broken install kills the agent | Accepted risk | Instrumentation review (confirmed) | Code | Eng | Acceptable with pinned deps; guard imports if the env is not managed |
| N-02 | run_agent([]) raises IndexError instead of API BadRequestError | Accepted risk | Instrumentation review (confirmed; unreachable from both entrypoints) | Code | Eng | Guard only if run_agent becomes a public API |
| T-01 | Conflicting/outdated session context not detected (Luke: "nice to know if we have conflicting information... highlight that") | Medium | No eval covers it yet; the multi-turn "make it from Chicago instead" golden case is the seed scenario | Model/session | Eng + Product | Session-level conflict eval: flag when the agent uses a date/destination the user has since changed |
| T-02 | Tone/style not evaluated (An: her team spot-checks "tone and such", wants it automated) | Medium | E8/E9 cover behavior, not tone | Model | An's team + Eng | Tone judge calibrated on An's labels; needs her rubric (follow-up email Q3) |
| T-03 | No retry/backoff on tool calls (Luke described exponential-backoff retries as the intended production behavior; repo has none) | Medium | Code reading; tool errors currently surface as {"error": ...} in one shot | Code | Eng | Retry policy with backoff + eventual honest failure, per Luke's description |
| T-04 | Session state database: offered and explicitly descoped | Descoped | Sariya asked "would you be okay if I add a database?"; panel said yes, but Luke then steered: "we're not super interested in hardening today... focus is how do we ensure the product is working from an evaluation standpoint" | Scope decision | Eng | Revisit at production rollout (covered in PRODUCTION_READINESS.md, D-11) |

Fixed during this engagement (outside the two demo candidates, all
instrumentation-layer, none touch agent behavior): traces/ gitignored, trace files
0600, export path repo-anchored, atomic tracing setup with honest failure logging,
dual-sink processor wiring (the Arize add_span_processor removal semantics), baseline
capture hardened (port preflight, fail-loud validity gates).
