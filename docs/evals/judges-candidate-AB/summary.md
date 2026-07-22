# Eval Summary

| Eval | Name | Applicable | Pass | Fail | Pass rate |
|------|------|-----------:|-----:|-----:|----------:|
| E8 | clarification_quality | 33 | 30 | 3 | 91% |
| E9 | scope_adherence | 33 | 33 | 0 | 100% |
| E11 | tone_quality | 33 | 33 | 0 | 100% |

## Failures (3)

- **E8 clarification_quality**
  - user_input: 'Plan a 3-day trip to Chicago for me.'
  - reason: The model peppered the user with 2 separate questions.
  - attribution: model
- **E8 clarification_quality**
  - user_input: 'I need a flight from Miami to Tokyo next Friday.'
  - reason: Booking-material info was missing but the model assumed instead of asking.
  - attribution: model
- **E8 clarification_quality**
  - user_input: "What's the weather going to be in London next Tuesday?"
  - reason: Booking-material info was missing but the model assumed instead of asking.
  - attribution: model
