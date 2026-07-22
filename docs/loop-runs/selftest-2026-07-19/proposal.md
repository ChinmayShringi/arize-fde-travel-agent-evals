# Improvement Proposal


## Candidate B: D-02 (flight direction lost + route hidden)

- Env flag (enable): `FLIGHT_TOOL_FIX=1`

### Evidence
- E2 (flight_direction), attribution=tool: 6 failure(s)
  - trace `0x18b1b686361b7e265e231e37dbdf6254` : 'Find me a flight from New York to Miami on March 12, 2026.'
  - trace `0x63b5bc221e858fff5899a9df6169d1f9` : 'What flights are there from San Francisco to Tokyo on April 20, 2026?'
  - trace `0xf312f76aef5e761811c400846065aaca` : "I'm thinking about a weekend in Miami in early August. Any flights from New York on August 7, 2026?"

### Experiment command (control + this candidate on the current dataset)
```
uv run python scripts/run_experiment.py --name control --prompt-variant v0 --flight-tool-fix 0 --dataset /private/tmp/claude-501/-Users-chinmay-shringi-Desktop-sar/a0cc4b1e-e102-4cd2-9e8a-aa55811d61f9/scratchpad/dataset_prefailure.json --out /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/experiments/control
uv run python scripts/run_experiment.py --name candidate-B-flight-tool-fix --prompt-variant v0 --flight-tool-fix 1 --dataset /private/tmp/claude-501/-Users-chinmay-shringi-Desktop-sar/a0cc4b1e-e102-4cd2-9e8a-aa55811d61f9/scratchpad/dataset_prefailure.json --out /Users/chinmay_shringi/Desktop/sar/docs/loop-runs/selftest-2026-07-19/experiments/candidate-B-flight-tool-fix
```

### Change description (from docs/proposals/CANDIDATES.md)

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

## Backlog (no authorized candidate)

- E4 (itinerary_day_count), attribution=tool: 2 failure(s) -- no candidate authorized (D-03 backlog)
  - 'Plan a 3-day trip to Chicago for me.'
  - 'Put together a 5-day itinerary for Paris, arriving June 10, 2026.'

