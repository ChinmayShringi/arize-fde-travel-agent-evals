"""Day 0 verification: recompute every numeric claim in REPO_FINDINGS.md
from the shipped tool functions and fixtures. No API key, no model calls.

docs/ lives INSIDE the repo, so this file sits at <repo>/docs/verification/ and
resolves the repo root two levels up. Run from the repo root:
    uv run python docs/verification/recompute_fixture_tables.py
"""

import json
import sys
from pathlib import Path

# <repo>/docs/verification/this_file.py -> parents[2] is <repo>.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agent.tools import FLIGHTS, create_itinerary, get_weather, search_flights, search_hotels

lines = []


def log(s=""):
    print(s)
    lines.append(s)


def true_direction(flight_number):
    for f in FLIGHTS:
        if f["flight_number"] == flight_number:
            return f["origin"], f["destination"]
    return None, None


log("# Day 0 fixture verification (computed, not inferred)")
log()

# D-02: flight direction table
log("## D-02: search_flights direction check")
log()
log("| Requested | Returned count | Correct direction | Backwards |")
log("|---|---|---|---|")
pairs = [
    ("New York", "Miami"),
    ("San Francisco", "Tokyo"),
    ("London", "Paris"),
    ("Tokyo", "Los Angeles"),
    ("Chicago", "Denver"),
]
for origin, dest in pairs:
    results = search_flights(origin, dest, "2026-08-01")
    correct, backwards = [], []
    for r in results:
        t_o, t_d = true_direction(r["flight_number"])
        label = f"{r['airline']} {r['flight_number']}"
        if (t_o, t_d) == (origin, dest):
            correct.append(label)
        else:
            backwards.append(f"{label} ({t_o} to {t_d})")
    log(
        f"| {origin} to {dest} | {len(results)} | {', '.join(correct) or 'none'} | "
        f"{', '.join(backwards) or 'none'} |"
    )
log()

# D-07: coverage holes
log("## D-07: coverage holes reachable from shipped traffic")
log()
for city in ["Denver", "Austin", "Tokyo"]:
    r = search_hotels(city, "2026-08-07", "2026-08-09")
    log(f"- search_hotels({city!r}): {r}")
log(f"- get_weather('London'): {get_weather('London', '2026-07-21')}")
for origin, dest in [("Miami", "Tokyo"), ("Denver", "Miami")]:
    r = search_flights(origin, dest, "2026-08-14")
    log(f"- search_flights({origin!r}, {dest!r}): {r}")
log()

# D-04: check_out ignored
log("## D-04: search_hotels ignores check_out")
log()
probe = search_hotels("Paris", "2026-06-10", "2099-12-31")
log(f"- Paris check_in 2026-06-10, check_out 2099-12-31 returns {len(probe)} hotels")
log()

# D-05: itinerary off-by-one
log("## D-05: create_itinerary day count")
log()
log("| num_days requested | len(days) returned |")
log("|---|---|")
for n in [3, 5, 7]:
    it = create_itinerary("Chicago", n)
    log(f"| {n} | {len(it['days'])} |")
log()

# D-06: weather unit bug. Jitter is date-seeded (seed%5-2 on high), so the
# REPO_FINDINGS table corresponds to jitter 0. Verify formula and compression.
log("## D-06: get_weather unit bug (F treated as C)")
log()
weather_raw = json.loads((REPO / "data" / "weather.json").read_text())
date = next(
    f"2026-07-{d:02d}" for d in range(1, 32)
    if sum(ord(c) for c in f"2026-07-{d:02d}") % 5 == 2
)
log(f"Zero-jitter date used: {date}")
log()
log("| City | Fixture high_f | Returned high_f | Error |")
log("|---|---|---|---|")
for city, entry in weather_raw.items():
    out = get_weather(city, date)
    err = out["high_f"] - entry["high_f"]
    log(f"| {city} | {entry['high_f']} | {out['high_f']} | {err:+d} |")
log()

# Traffic generator counts
sys.path.insert(0, str(REPO / "scripts"))
import generate_traffic  # noqa: E402

convs = generate_traffic.CONVERSATIONS
log("## Traffic generator inventory")
log()
log(f"- Conversations: {len(convs)}")
log(f"- Messages: {sum(len(c) for c in convs)}")
log(f"- Multi-turn conversations: {sum(1 for c in convs if len(c) > 1)}")

out_path = Path(__file__).with_name("DAY0_FIXTURE_CHECKS.md")
out_path.write_text("\n".join(lines) + "\n")
print(f"\nWritten: {out_path}")
