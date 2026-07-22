# Candidate Fixes

Two low-complexity, env-gated candidate fixes. Each targets exactly one defect from
`REPO_FINDINGS.md` and is off by default. With both env vars unset/default, the agent
behaves byte-identically to the shipped code (verified; see Self-tests below).

Files touched: `agent/prompt.py`, `agent/tools.py`. No other files change.

| Candidate | Defect | Env flag (enable) | Default (shipped) |
|---|---|---|---|
| A | D-01 (prompt contradicts requirements) | `PROMPT_VARIANT=v1` | `PROMPT_VARIANT` unset or `v0` |
| B | D-02 (flight direction lost + route hidden) | `FLIGHT_TOOL_FIX=1` | `FLIGHT_TOOL_FIX` unset or `0` |

---

## Candidate A: system prompt rewrite (`PROMPT_VARIANT=v1`, fixes D-01)

### What it changes

`agent/prompt.py` now selects the system prompt at import time:

- `PROMPT_VARIANT` unset or `v0` -> `SYSTEM_PROMPT` is the shipped 3-line prompt,
  byte-for-byte (the `_V0_SYSTEM_PROMPT` constant is the unmodified original text).
- `PROMPT_VARIANT=v1` -> `SYSTEM_PROMPT` is a rewritten prompt built by
  `_build_v1_system_prompt()`.

The v1 prompt (kept tight, 11 lines) replaces the three shipped guidelines with rules
that align to the customer requirements AND the model's measured Day 1 behavior:

- Grounding: every hotel/flight/price/availability claim must come from tool results
  returned in this conversation; never invent options, prices, routes, or details.
- Empty/error handling: if a search returns nothing or an error, say so plainly and
  offer alternatives (different dates, nearby cities); do not fabricate to fill the gap.
- Clarifying questions: when booking-material info is missing (travel dates, departure
  city), ask ONE consolidated clarifying question; once there is enough to act, act
  (do not pepper the user with questions).
- Current date: `date.today()` is computed inside the v1 branch only and embedded as
  `YYYY-MM-DD`, so relative dates ("this weekend", "next Friday") can be anchored.
- Scope: travel planning and booking only; for visa/refund/policy questions,
  acknowledge and hand off to a human, do not improvise.

`date.today()` is evaluated only when `PROMPT_VARIANT=v1`, so the default path stays
free of any date dependency and remains byte-identical to HEAD.

### Eval evidence that motivated it

- `REPO_FINDINGS.md` D-01: the shipped prompt directly contradicts two stated
  requirements. Nick asked the agent to ask clarifying questions when information is
  missing; the prompt says "Don't bombard the user with clarifying questions." Luke
  required that on an API failure the agent not "mix something up and hallucinate";
  the prompt says "Never mention internal systems, data sources, or technical issues"
  and "Always give the user concrete options," which leaves fabrication as the only
  exit on an empty/error result.
- `docs/DAY1_FINDINGS.md`: the measured baseline shows the model is *ignoring* the
  shipped prompt (it asked clarifying questions and disclosed system limitations 7+
  times in 23 turns, all forbidden by the prompt). An instruction set the model
  refuses to follow is not a control surface. v1 aligns the prompt with the desired
  and observed behavior so the behavior becomes tunable.
- Day 1 micro-finding: the Denver clarifying reply offered a stale example date
  ("2024-01-20"), evidence of no current-date anchor (D-09). v1 embeds today's date.

### How to enable

```
PROMPT_VARIANT=v1
```

---

## Candidate B: `search_flights` direction fix (`FLIGHT_TOOL_FIX=1`, fixes D-02)

### What it changes

`agent/tools.py` `search_flights` now branches on `FLIGHT_TOOL_FIX`:

- unset or `0` -> shipped behavior: unordered set match on
  `{origin, destination}`, and the returned dicts strip `origin`/`destination`.
  Byte-identical to HEAD.
- `1` -> ordered match: `f["origin"].lower() == origin.lower()` AND
  `f["destination"].lower() == destination.lower()`, and each returned flight dict
  includes `"origin"` and `"destination"` so the model can see the route.

Only `search_flights` is modified. `date` remains unused (D-03 stays in the backlog);
this candidate fixes direction and route visibility only, deliberately staying
low-complexity per the locked constraint.

### Eval evidence that motivated it

- `REPO_FINDINGS.md` D-02 and `DAY0_FIXTURE_CHECKS.md`: the unordered set match
  returns backwards flights and the payload strips the route, so the model cannot
  detect the error. The demo case Tokyo -> Los Angeles returns exactly one option,
  `ANA NH 105`, whose true route is Los Angeles -> Tokyo.
- `docs/DAY1_FINDINGS.md`: this reproduced live at baseline. The model presented
  `ANA NH 105` for Tokyo -> LA with invented corroborating detail ("direct flight",
  "crossing the International Date Line"), and presented `AA 2210` (true route
  Miami -> New York) as a normal New York -> Miami option. This is the E2 pathway
  that scores 0% at baseline: every flight-direction answer is systematically
  poisoned by the tool while looking perfectly grounded to any reply-level check.
- With the fix, Tokyo -> Los Angeles correctly returns `[]` (no such route exists),
  and New York -> Miami returns only the two true forward flights, `DL 883` and
  `B6 1029`, each carrying visible `origin`/`destination` fields.

### How to enable

```
FLIGHT_TOOL_FIX=1
```

Both flags can be combined by the experiment runner (`--prompt-variant v1
--flight-tool-fix 1`) to measure the candidates together or in isolation.

---

## Self-tests (run 2026-07-19, all passing)

1. `recompute_fixture_tables.py` under default env regenerates
   `DAY0_FIXTURE_CHECKS.md` identically (diff empty).
2. Under default env, `agent.prompt.SYSTEM_PROMPT` equals `HEAD:agent/prompt.py`'s
   `SYSTEM_PROMPT` byte-for-byte (both length 412).
3. With `FLIGHT_TOOL_FIX=1`: Tokyo -> Los Angeles returns `[]`; New York -> Miami
   returns only `DL 883` and `B6 1029`, each with `origin`/`destination` present.
   With the flag unset, New York -> Miami still returns 3 (including backwards
   `AA 2210`) with no route fields, matching HEAD across five city pairs.
4. With `PROMPT_VARIANT=v1`: `SYSTEM_PROMPT` contains today's date (`2026-07-19`)
   and the grounding, empty/error, single-clarifying-question, and scope/handoff
   rules.
