# Interview 2 Talk Track

Companion notes for `docs/Interview_2_Customer_Presentation.pptx`.

The Product Manager's name is Anne, verified from her introduction in the supplied
transcript. The slides use role labels. Do not claim that booking conversion was measured,
that the judges are release-ready, or that the historical loop experimented on its curated
dataset.

## Slide 1: A safer improvement loop

The center of the work is the system around the agent. I will show how we find the first
incorrect step, prove a bounded repair, and keep production authority explicit.

## Slide 2: What you asked for

Nick owns the conversion goal, Anne wants scalable quality review, and Luke needs grounded
answers without replacing the homegrown orchestration. Planning to itinerary to booking is
the anchor workflow. This prototype has no booking or payment tool, so groundedness and tool
correctness are leading indicators, not proof of conversion lift.

## Slide 3: The first failure

Use the Tokyo to Los Angeles trace. The flight tool treated direction as an unordered set
and removed route fields from its output. The model received a backwards result and could
not reliably verify it. The earliest wrong step was the tool, not the final reply.

## Slide 4: Evaluation portfolio

When fixtures define the complete inventory, exact set membership is stronger than an LLM
opinion. Deterministic checks cover groundedness, direction, tool arguments, itinerary days,
conflict handling, and telemetry. Clarification, scope, and tone judges remain monitor-only
until Anne's team supplies labels with meaningful negative examples.

## Slide 5: Improvement loop

The loop collects, evaluates, clusters, curates, proposes, experiments, and gates in one
bounded command. The first six stages can run without a person. The final artifact is always
`pending_human_review`; the loop cannot approve itself.

## Slide 6: Measured result

Lead with E2: 1 of 9 applicable control replies had the correct direction, compared with 8
of 8 for Candidate B, an increase of 88.89 percentage points. State the counts because
applicability differs between arms. E1 is 33 of 33 in both arms. E4 is 0 of 3 in both arms
and remains deliberately unfixed. Median latency, estimated cost, and tokens also moved in
the favorable direction, but this was a small offline experiment.

## Slide 7: Bounded change

Candidate B changes one tool path. It matches origin and destination in order and preserves
those fields for model verification. It remains behind `FLIGHT_TOOL_FIX` and was compared
against an unchanged control arm. The model was not changed as an unmeasured fix.

## Slide 8: Evidence integrity

The first scoring pass appeared to improve groundedness from 97 to 100 percent. That was
false. The extractor treated the markdown heading `Hotel Options` as an invented hotel.
After correction and re-scoring, E1 is 100 percent in both arms. This is worth emphasizing:
evaluation code needs adjudication and regression tests too.

## Slide 9: Honest limits

The captured run measured the original 33-turn dataset with experiment redaction off. The
audit found that the newly curated dataset was not passed into the experiment. Current code
now passes that curated copy and defaults experiment replay to redaction on, with fail-closed
configuration and recursive redaction before curation or proposal. Those corrections have
tests but have not yet been measured in a fresh paid run.

## Slide 10: Beyond the interview

The production pattern separates serving, telemetry, evaluation, triage, replay, and release
authority. OpenInference and OpenTelemetry keep it portable across Arize AX and Phoenix.
Artifacts are exported to disk for retention safety. Real conversion claims require joining
trace and version IDs to booking outcomes during a canary.

State two open security requirements clearly. The deterministic redactor currently covers
formatted US SSNs and Luhn-valid cards, not every PII category. The demo API also requires
authentication, conversation ownership, request limits, and rate limiting before public
internet exposure.

## Slide 11: Release gate

Promotion requires evidence integrity, hard safety invariants, no material regression,
targeted capability improvement, operational budgets, and eventually business outcomes.
Human approval records the named owner and timestamp. The current output is correctly
`pending_human_review` because the judges are not calibrated to gate a release.

## Slide 12: Close

The reusable product is the loop: find the first mistake, prove a repair, then roll it out
with control. The measured headline is flight direction from 1 of 9 to 8 of 8 with no
rate-based regressions. Invite questions and open the public repository or captured trace.

## Demo links

- Public repository: <https://github.com/ChinmayShringi/arize-fde-travel-agent-evals>
- Audit: `docs/DELIVERY_AUDIT.md`
- Historical loop report: `docs/loop-runs/interview2-final/loop_report.md`
- Comparison: `docs/loop-runs/interview2-final/comparison.md`
- Approval: `docs/loop-runs/interview2-final/approval.json`
