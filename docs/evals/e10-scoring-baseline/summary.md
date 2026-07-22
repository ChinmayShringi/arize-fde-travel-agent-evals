# Eval Summary

| Eval | Name | Applicable | Pass | Fail | Pass rate |
|------|------|-----------:|-----:|-----:|----------:|
| E1 | fabricated_entity | 23 | 23 | 0 | 100% |
| E2 | flight_direction | 6 | 0 | 6 | 0% |
| E3 | tool_call_validity | 16 | 16 | 0 | 100% |
| E6 | pii | 23 | 23 | 0 | 100% |
| E7 | guardrails | 23 | 23 | 0 | 100% |
| E4 | itinerary_day_count | 2 | 0 | 2 | 0% |
| E10 | conflicting_context | 1 | 1 | 0 | 100% |
| E5 | empty_result_honesty | 1 | 1 | 0 | 100% |

## Failures (8)

- **E2 flight_direction**
  - user_input: 'Find me a flight from New York to Miami on March 12, 2026.'
  - reason: Reply recommends backwards flight(s): AA 2210 is Miami -> New York but user asked New York -> Miami.
  - attribution: tool
- **E2 flight_direction**
  - user_input: 'What flights are there from San Francisco to Tokyo on April 20, 2026?'
  - reason: Reply recommends backwards flight(s): UA 838 is Tokyo -> San Francisco but user asked San Francisco -> Tokyo.
  - attribution: tool
- **E4 itinerary_day_count**
  - user_input: 'Plan a 3-day trip to Chicago for me.'
  - reason: create_itinerary requested 3 day(s) but delivered 2.
  - attribution: tool
- **E2 flight_direction**
  - user_input: "I'm thinking about a weekend in Miami in early August. Any flights from New York on August 7, 2026?"
  - reason: Reply recommends backwards flight(s): AA 2210 is Miami -> New York but user asked New York -> Miami.
  - attribution: tool
- **E2 flight_direction**
  - user_input: 'Show me flights from London to Paris on September 3, 2026.'
  - reason: Reply recommends backwards flight(s): AF 1681 is Paris -> London but user asked London -> Paris.
  - attribution: tool
- **E2 flight_direction**
  - user_input: 'I need to get from Tokyo to Los Angeles on May 2, 2026 — what flights are there?'
  - reason: Reply recommends backwards flight(s): NH 105 is Los Angeles -> Tokyo but user asked Tokyo -> Los Angeles.
  - attribution: tool
- **E4 itinerary_day_count**
  - user_input: 'Put together a 5-day itinerary for Paris, arriving June 10, 2026.'
  - reason: create_itinerary requested 5 day(s) but delivered 4.
  - attribution: tool
- **E2 flight_direction**
  - user_input: 'I want to fly from Chicago to Denver on October 2, 2026 — what are my options?'
  - reason: Reply recommends backwards flight(s): UA 2045 is Denver -> Chicago but user asked Chicago -> Denver.
  - attribution: tool
