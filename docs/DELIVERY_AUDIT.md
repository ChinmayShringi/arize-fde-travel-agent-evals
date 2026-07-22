# Delivery Audit

Audited on 2026-07-21 against the source code, captured artifacts, public GitHub
repository, supplied Interview 1 transcript, and executable test suite.

## Verdict

The project is a strong interview prototype and is ready to present as an evaluation
system. It is not ready for autonomous production promotion, and the deck does not claim
that it is.

The strongest story is trace-level attribution. A Tokyo to Los Angeles request reached a
flight tool that matched routes as an unordered set and removed direction from its output.
The reply-level symptom looked like a model failure, but the first incorrect step was the
tool. Candidate B fixes only that tool path.

## Verified delivery state

| Item | Status | Evidence |
|---|---|---|
| Public codebase | Complete | <https://github.com/ChinmayShringi/arize-fde-travel-agent-evals> |
| Customer presentation | Complete | `docs/Interview_2_Customer_Presentation.pptx` |
| Automated feedback loop | Implemented and executed | `scripts/feedback_loop.py`; `docs/loop-runs/interview2-final/` |
| Test suite | Passing | 214 tests, plus slide overflow validation |
| CI | Passing | GitHub Actions on the reviewed branch |
| Promotion gate | Intentionally pending | `approval.json` permits only `pending_human_review` |

## Measured result

The historical paired experiment recorded:

- E2 flight direction: 1/9 control to 8/8 candidate, an increase of 88.89 percentage points.
- E1 groundedness: 33/33 in both arms after correcting the heading extractor, a 0 point delta.
- E4 itinerary day count: 0/3 in both arms, a known defect deliberately left in backlog.
- No regressions in measured rate-based evaluations.
- Median latency: 2982 ms to 2753 ms.
- Estimated run cost: $0.1094 to $0.1056.
- Tokens: 75,350 to 73,901.

Counts accompany percentages because E2 applicability differs between arms.

## Audit corrections

1. The feedback loop curated eight replayable failures but passed the original dataset to
   proposal and experiment. `scripts/feedback_loop.py` now threads the curated dataset path
   through both stages. `tests/test_feedback_loop_orchestration.py` prevents recurrence.
2. Experiment replay defaulted to unredacted input. It now redacts at source by default,
   while an explicit legacy opt-out remains for reproduction. `tests/test_experiment_redaction.py`
   covers the boundary.
3. The apparent 97% to 100% groundedness improvement was a grader artifact. The extractor
   interpreted the markdown heading `Hotel Options` as an invented hotel. The evaluator was
   corrected, re-scored, and pinned with positive and negative tests.
4. Several documents overstated Nick's request as autonomous production promotion. The
   transcript requests automatic failure appending to the evaluation dataset. It does not
   grant authority to promote code to production. Dataset automation and production
   authority are now described separately.
5. The Product Manager's name is Anne. This is verified by her introduction in the supplied
   transcript. The customer deck uses role labels to avoid unnecessary dependence on names.
6. Stale claims about repository privacy, test counts, deleted audit documents, the
   experiment redaction default, and historical reproduction commands were corrected in
   reviewer-facing documents.
7. Invalid `EXPERIMENT_REDACT_PII` values now stop execution instead of silently disabling
   redaction.
8. The loop refuses to reuse a non-empty output directory, preserving captured evidence as
   immutable by default.
9. Historical unredacted failures are recursively redacted before curation or an optional
   proposal-model call. Legacy results without trace IDs receive stable per-conversation keys
   instead of being merged into one case.
10. CI now scopes the Anthropic key only to paid execution steps and pins third-party actions
    to immutable commit SHAs.
11. GitHub secret scanning, push protection, and Dependabot security updates are enabled on
    the public repository.

## What exceeds the interview minimum

- OpenInference and OpenTelemetry conventions make the instrumentation portable between
  Arize AX and Phoenix self-hosted.
- Deterministic evaluators are used before model judges when fixtures define the full truth set.
- Every result carries attribution to user input, tool behavior, model behavior, or evaluator.
- Baseline, spans, scores, explanations, manifests, and approval records are exported to disk.
- Experiments are versioned by prompt and agent configuration and compared against a control.
- The loop is bounded by iteration and wall-clock limits and returns a non-fabricating fallback.
- Failure cases are quarantined as replayable records rather than silently merged into production truth.
- Production promotion and rollback remain human-owned until judge calibration has useful variance.
- The production plan connects trace versions to booking outcomes through canary analysis before
  anyone claims impact on the 50% conversion objective.

## Remaining human actions

1. Review `evals/calibration/calibration_sheet.csv`. All 99 labels are AI-proposed and
   `human_reviewed=false`; all three judges therefore remain monitor-only.
2. Run a fresh clean paired experiment on the curated dataset with the corrected redaction
   default before describing the loop as fully closed on its own generated failures.
3. Decide whether to delete and rotate credentials associated with
   `/Users/chinmay_shringi/Desktop/sar/Archive.UNSAFE-CONTAINS-LIVE-KEY-DO-NOT-SEND.zip`.
   It is outside the public repository. It should never be shared.
4. Confirm the proposed numeric release threshold with the customer. The 85 to 90 percent
   range came from discovery, but the exact gate semantics were not specified.
5. Treat broad PII blocking as an open production requirement. The current deterministic
   redactor covers formatted US SSNs and Luhn-valid cards, not every identifier category.
6. Keep the demo API private. Authentication, conversation ownership, request-size limits,
   and per-caller rate limiting are required before internet exposure.

## Presentation guidance

Lead with the E2 result and its trace-level explanation. State E1 as 100% in both arms.
Do not describe the judges as calibrated release gates, do not claim booking conversion was
measured, and do not describe the historical loop run as having tested its curated dataset.
