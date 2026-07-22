# Repo Findings — Arize-ai/sample-travel-agent

Method: full read of all 9 source files (~300 lines) plus fixture computation against the tool functions.
**Nothing here is from a live agent run.** Predicted model behavior is inference from the prompt plus
tool contracts. Day 0 converts inference into measurement.

## The headline: the system prompt contradicts the customer

`agent/prompt.py` in full:

```
Help Book Travel.

Guidelines:
- Always give the user concrete options and recommendations. Users hate vague non-answers, answer what they ask for.
- Don't bombard the user with clarifying questions — make reasonable assumptions and get them an answer quickly.
- Never mention internal systems, data sources, or technical issues to the user. never refer users to other websites or tell them to search elsewhere.
```

Against Interview 1:

| Prompt line | Customer said | Conflict |
|---|---|---|
| "Don't bombard the user with clarifying questions" | Nick: *"we do want the agent to ask clarifying questions if there isn't enough information... we don't want to just produce an itinerary for some random date"* | Direct contradiction |
| "Never mention internal systems, data sources, or technical issues" + "Always give the user concrete options" | Luke: *"if the API fails, it's not just going to go ahead and do a web search or just mix something up and hallucinate"* | Direct contradiction |

Tools return `[]` or `{"error": ...}` on a miss. The prompt forbids reporting that. The only remaining
exit is fabrication.

Nick's named failure was: *"suppose the agent hallucinates a hotel that does not exist."*
`scripts/generate_traffic.py` ships **"Can you get me a hotel in Denver for this weekend?"**
There is no Denver in `hotels.json`. The gun and the trigger were both shipped.

## Defect inventory

| ID | Defect | Location | Evidence | Severity | Fix in demo? |
|---|---|---|---|---|---|
| D-01 | Prompt forbids reporting empty results and forbids clarifying questions | `agent/prompt.py` | Text above vs. transcript | **Critical** | **Yes — prompt fix** |
| D-02 | `search_flights` matches origin/destination as an unordered set; strips `origin`/`destination` from payload | `agent/tools.py:13-25` | Table below | **Critical** | **Yes — tool fix** |
| D-03 | `search_flights` accepts `date` and never uses it; `flights.json` has no date field at all | `agent/tools.py:13`, `data/flights.json` | Every flight answer is ungrounded on date, always | High | No — backlog |
| D-04 | `search_hotels` ignores `check_out` | `agent/tools.py:28-38` | Stay can extend past `available_to` and pass | High | No — backlog |
| D-05 | `create_itinerary` uses `range(1, num_days)`; echoes `num_days` back correctly | `agent/tools.py:57` | 3→2 days, 5→4 days, 7→6 days | Medium | No — backlog |
| D-06 | `get_weather` applies C→F formula to a value already in F | `agent/tools.py:49-50` | Table below | Low | No — backlog |
| D-07 | Coverage holes reachable from shipped traffic | `data/*.json` | Table below | High | No — D-01 mitigates |
| D-08 | Two shipped queries have no tool at all (Japan visa, refund) | `scripts/generate_traffic.py:18-19` | Prompt says answer anyway → hallucinated immigration advice | **Critical** | No — D-01 mitigates |
| D-09 | Three shipped queries use relative dates; no current date anywhere in the prompt | `generate_traffic.py`, `prompt.py` | "next Friday", "this weekend", "next Tuesday" | Medium | No — backlog |
| D-10 | `while True` with no iteration cap, no timeout | `agent/loop.py:19` | Unbounded token spend — Nick's stated cost concern | Medium | No — production plan |
| D-11 | Module-level `CONVERSATIONS` dict and `anthropic.Anthropic()` at import | `agent/api.py:10`, `loop.py:8` | Breaks multi-worker; unbounded growth | Medium | No — production plan |
| D-12 | No auth, no rate limit on `POST /chat` | `agent/api.py` | Out of scope per Luke | Low | No — explicitly out of scope |

## D-02 evidence: the tool lies to the model

`cities = {origin.lower(), destination.lower()}` compared by set equality, so direction is discarded.
The returned dict contains only `airline, flight_number, depart_time, arrive_time, price_usd`.
**The model cannot detect the error.** Computed against `data/flights.json`:

| Requested | Returned | Correct | Backwards |
|---|---|---|---|
| New York → Miami | 3 | `DL 883`, `B6 1029` | `AA 2210` (Miami→NY) |
| San Francisco → Tokyo | 3 | `UA 837`, `NH 7` | `UA 838` (Tokyo→SF) |
| London → Paris | 2 | `BA 306` | `AF 1681` (Paris→London) |
| **Tokyo → Los Angeles** | **1** | **none** | **`NH 105` (LA→Tokyo)** |
| Chicago → Denver | 2 | `UA 2044` | `UA 2045` (Denver→Chicago) |

Tokyo → Los Angeles is the demo case. There is no Tokyo→LA flight in the data. The tool returns exactly
one option, it is backwards, and the agent will present it confidently.

**Why this matters more than any other finding:** Nick asked *"where in the chain did it go wrong so that
we can start from the very first mistake."* Here the first mistake is the **tool**, not the model. A naive
groundedness eval scores this as a model hallucination and sends the team to rewrite prompts forever.
Correct instrumentation attributes it to the tool span. That distinction is the FDE value proposition.

## D-07 evidence: coverage holes

| Tool | Missing, reachable from shipped traffic | Result |
|---|---|---|
| `search_hotels` | Denver, Austin, Tokyo | `[]` |
| `get_weather` | London | `{"error": "No weather data available for London"}` |
| `search_flights` | Miami→Tokyo, Denver→Miami | `[]` |

Each lands in a prompt that forbids saying so.

## D-06 evidence: unit bug compresses toward 72°F

`round((high_f) * 5 / 9 + 32)` — the fixed point of that map is 72, so error scales with distance from it.

| City | Fixture `high_f` | Returned | Error |
|---|---|---|---|
| Miami | 86 | 80 | -6 |
| Los Angeles | 78 | 75 | -3 |
| San Francisco | 64 | 68 | +4 |
| Chicago | 62 | 66 | +4 |
| Paris | 63 | 67 | +4 |
| New York | 68 | 70 | +2 |
| Tokyo | 72 | 72 | 0 |

Plausible-looking output, which is what makes it a good deterministic-eval case and a bad
human-spot-check case. Anne's team spot-checks today. They would never catch this. That is the argument
for automation, stated in her own problem.

## Fixture inventory

- **Flights:** 28 records. Cities: New York, Los Angeles, San Francisco, Chicago, Miami, Tokyo, London, Paris, Denver. No date field.
- **Hotels:** 19 records across Chicago, London, Miami, New York, Paris, San Francisco. Fields include `available_from`/`available_to` (ISO strings, compared lexicographically).
- **Weather:** 7 cities. No London.
- **Traffic generator:** 22 conversations, 23 messages, one multi-turn.

Closed set ⇒ groundedness is exact set membership. No judge required for the primary metric.
