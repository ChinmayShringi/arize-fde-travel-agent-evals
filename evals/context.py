"""Shared context and result contract for all deterministic evals.

Contract every eval module follows:
- module exposes EVALS: list[callable]
- each callable: (trace: TraceView, ctx: EvalContext) -> dict | None
- return None when the eval does not apply to this trace (e.g. E4 on a trace
  with no create_itinerary call). Otherwise return:
  {
    "eval_id": "E1",
    "name": "fabricated_entity",
    "passed": bool,
    "reason": str,                      # one sentence, human-readable
    "attribution": "tool" | "model" | "n/a",   # where the fault originates
    "evidence": dict,                   # eval-specific supporting data
  }
"""

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class EvalContext:
    hotels: tuple          # full fixture records
    flights: tuple
    weather_cities: tuple  # city names with weather data
    hotel_names: frozenset
    hotel_cities: frozenset
    flight_numbers: frozenset
    airlines: frozenset
    flight_cities: frozenset

    @classmethod
    def load(cls) -> "EvalContext":
        hotels = json.loads((DATA_DIR / "hotels.json").read_text())
        flights = json.loads((DATA_DIR / "flights.json").read_text())
        weather = json.loads((DATA_DIR / "weather.json").read_text())
        return cls(
            hotels=tuple(hotels),
            flights=tuple(flights),
            weather_cities=tuple(weather.keys()),
            hotel_names=frozenset(h["name"] for h in hotels),
            hotel_cities=frozenset(h["city"] for h in hotels),
            flight_numbers=frozenset(f["flight_number"] for f in flights),
            airlines=frozenset(f["airline"] for f in flights),
            flight_cities=frozenset(
                c for f in flights for c in (f["origin"], f["destination"])
            ),
        )
