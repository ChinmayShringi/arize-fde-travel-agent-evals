# Day 0 fixture verification (computed, not inferred)

## D-02: search_flights direction check

| Requested | Returned count | Correct direction | Backwards |
|---|---|---|---|
| New York to Miami | 3 | Delta DL 883, JetBlue B6 1029 | American AA 2210 (Miami to New York) |
| San Francisco to Tokyo | 3 | United UA 837, ANA NH 7 | United UA 838 (Tokyo to San Francisco) |
| London to Paris | 2 | British Airways BA 306 | Air France AF 1681 (Paris to London) |
| Tokyo to Los Angeles | 1 | none | ANA NH 105 (Los Angeles to Tokyo) |
| Chicago to Denver | 2 | United UA 2044 | United UA 2045 (Denver to Chicago) |

## D-07: coverage holes reachable from shipped traffic

- search_hotels('Denver'): []
- search_hotels('Austin'): []
- search_hotels('Tokyo'): []
- get_weather('London'): {'error': 'No weather data available for London'}
- search_flights('Miami', 'Tokyo'): []
- search_flights('Denver', 'Miami'): []

## D-04: search_hotels ignores check_out

- Paris check_in 2026-06-10, check_out 2099-12-31 returns 2 hotels

## D-05: create_itinerary day count

| num_days requested | len(days) returned |
|---|---|
| 3 | 2 |
| 5 | 4 |
| 7 | 6 |

## D-06: get_weather unit bug (F treated as C)

Zero-jitter date used: 2026-07-01

| City | Fixture high_f | Returned high_f | Error |
|---|---|---|---|
| New York | 68 | 70 | +2 |
| Los Angeles | 78 | 75 | -3 |
| San Francisco | 64 | 68 | +4 |
| Chicago | 62 | 66 | +4 |
| Miami | 86 | 80 | -6 |
| Paris | 63 | 67 | +4 |
| Tokyo | 72 | 72 | +0 |

## Traffic generator inventory

- Conversations: 22
- Messages: 23
- Multi-turn conversations: 1
