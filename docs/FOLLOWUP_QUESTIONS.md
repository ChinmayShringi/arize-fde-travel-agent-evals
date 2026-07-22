# Follow-up Questions to the Customer (post Interview 1)

Protocol per playbook section 18: within 24 hours, send only consolidated, material
clarification questions. Every item carries the default we proceed with if unanswered,
so silence never stalls the build.

Panel: Nick Luzio (Director of Product), An Nguyen (PM), Lucas "Luke" Moehlenbrock (VP Eng).

Revised after a 4-lens adversarial review (hiring-panel, customer, completeness vs
playbook banks, brief auditor). Key changes from draft 1: promotion-gate language no
longer buried in a default (stated plainly instead, per the call-it-out rule); bar
anchored at 85 (Nick's floor) driving toward 90, not silently pinned at 90; ten
questions restructured to four questions plus a working-defaults list; reply-by date
added; residency clause added to the Luke question; advisory and latency/cost items
demoted out of the questions.

Status: DRAFT v2. Chinmay reviews and sends. Never sent by the assistant.

## Pre-send checklist for Chinmay

- [ ] Verify the PM's name spelling ("An" per playbook panel list vs "Anne" in session
      notes) against the calendar invite or her email address, then reconcile CLAUDE.md.
- [ ] Confirm you are comfortable disclosing the human sign-off recommendation now
      (recommended: it is the honest play and pre-plants the 22nd) rather than holding it.
- [ ] Adjust the reply-by date if you send this later than Thursday night.

---

## The email (ready to send after checklist)

Subject: Follow-ups from today's call: four questions plus my working defaults

Hi Nick, An, Luke,

Thank you all for the time today. I am building against what we agreed: the
planning-to-itinerary-to-booking workflow as the anchor, groundedness as the primary
quality bar, and incorrect tool usage as the first automation target.

Four questions, then a list of working defaults. "Defaults fine, except..." is a
complete reply. If I have not heard back by end of day Friday the 18th, I will
proceed on the defaults; most stay cheap to change later, and I will flag any that
stop being cheap.

Questions

1. Nick, golden dataset (following up from the call): even 20 to 30 examples your
   team uses for spot checks would be valuable, in any format, with or without
   expected answers. Default: I build a versioned evaluation set from representative
   traffic and merge yours whenever it arrives.

2. Nick: when you said 85 to 90 percent, did you mean that share of individual
   answers passing our checks on a fixed test set, or that share of whole
   conversations ending well in production? I will build the measurement to match.
   Default: per-answer on the versioned test set, with production monitored
   separately, using 85 (the low end of your range) as the bar and 90 as the target
   we drive toward.

3. An: does your team have any rubric, checklist, or notes from manual quality
   reviews, even informal ones? I would use them to calibrate the automated grader
   against your team's judgment and report the agreement rate. Default: I hand-label
   a calibration sample myself and show that agreement number.

4. Luke, two-part confirmation on the PII boundary: (a) may redacted conversation
   content be sent to an external model for automated quality grading, or should
   grading stay fully deterministic and in-house until we align? (b) redacted traces
   would live in Arize's US cloud; if data residency is a constraint, the same
   design runs on self-hosted Phoenix. Default: redaction at the source, the primary
   quality gate stays deterministic-only, US cloud with the self-hosted path
   documented.

Working defaults (object to any)

- Launch blockers. I am tracking four failure classes: (a) fabricated inventory,
  meaning hotels, flights, or prices that do not exist in your systems, (b)
  directionally wrong flight results, (c) out-of-scope answers such as visa or
  refund advice, (d) tone and formatting. Default: (a) and (b) block promotion,
  (c) routes to a human, (d) is tracked but not blocking. Reorder if that is wrong.
- Grounding boundary. General travel knowledge is fine for color; anything about
  hotels, flights, prices, or availability must trace to a tool result.
- Clarifying questions, per Nick's point about not producing an itinerary for a
  random date: travel dates and departure city are always-ask when missing, capped
  at one consolidated question per turn.
- Promotion process. Passing the quality bar is necessary, and I will also recommend
  a brief human sign-off before any production change until the automated grader is
  proven against your team's labels. This is a deliberate refinement of the fully
  automatic flow we discussed; I will bring the reasoning and the data on the 22nd.
- Booking scope. The agent exercises the full planning-to-booking flow, but no real
  reservation or charge is executed in this phase.
- Latency and cost. No budgets were set today; I will measure p95 latency and
  per-conversation cost from the baseline and propose budgets with the results.
- If I hit a time tradeoff during the build week, I protect the complete loop on the
  anchor workflow with the deterministic groundedness checks; the judge-based
  clarification-quality and scope-adherence evals are the first cut, and would still
  be presented as designs.
- For the 22nd, I plan to demonstrate the loop live on the anchor workflow: a trace,
  an evaluation catching a failure, the failure curated into the dataset, a proposed
  fix, and a before/after experiment, with scale-out shown architecturally. Tell me
  if the bar is different.

I am capturing the baseline now and will bring before/after numbers on the 22nd.

Best,
Sariya

---

## Assumption register (internal; presented as assumptions on the 22nd)

Items marked [email] are now surfaced in the email's defaults list; the rest stay
internal until the presentation.

| # | Item | Stated assumption |
|---|---|---|
| 1 | Production volume | Design production plan for the brief's millions-per-day framing |
| 2 | Promotion approver [email] | PM team signs off; presented as recommendation with calibration data |
| 3 | Alert routing and severity | Slack channel + weekly review; P0 fabricated inventory, P1 coverage/scope, P2 telemetry |
| 4 | Dataset/rubric ownership after handoff | An's team owns labels and rubric; engineering owns evaluator code (playbook D08) |
| 5 | Data residency / retention [email] | AX cloud US; verify free-tier retention at signup; export all artifacts to disk regardless |
| 6 | Loop trigger and orchestrator | Scheduled run (GitHub Actions cron, local fallback) this phase; CI-triggered evaluation and the AX Airflow provider named as scale-up paths |
| 7 | Business-outcome baseline | No conversion number exists; groundedness reported as the leading proxy; no conversion figure will be claimed (hard rule: never fabricate a number) |
| 8 | Idempotency | Advisory phase implies none required; if booking execution enters scope, idempotency keys go in the production plan |
| 9 | Constraint tolerances | Budget and dates treated as hard constraints, other preferences soft; zero tolerance on inventory facts |
| 10 | Rollback | Same human gate as promotion (PM signs off), triggered by a monitor breach on the primary metric; the artifact rolled back is the versioned prompt/tool config |
| 11 | Advisory scope [email] | Repo has no booking/payment path (verified in agent/tools.py); full flow exercised, no real side effects |
| 12 | Latency/cost budgets [email] | Measured from baseline (tokens, wall-clock); budgets proposed with results; E7 thresholds set off baseline |
| 13 | Interview 2 acceptance bar [email] | Live loop run on anchor workflow; scale-out architectural |

## Tier 4: recruiter/coordinator, not the customer

- Interview 2 logistics only: duration, attendee list, whether they want the codebase
  link in advance. (What must run live belongs to the customer panel and is now an
  email default, not a recruiter question.)

## Why four questions and not ten

Questions 1 and 3 are dataset provenance: their labels beat our synthetics, and only
they can supply them. Question 2 is the one number the whole gate design hangs on,
rewritten in plain language because it is also the question most likely to be skimmed.
Question 4 is the one answer with architectural blast radius (judge policy and
residency). Everything else either had a default that executes identically with or
without an answer (latency/cost), was answered by the repo itself (booking capability),
or re-asked something Nick already said in the call (clarifying questions), so those
became confirmable defaults instead of questions. The defaults list also gives the
customer written cover for the two things the playbook says must never be hidden
tradeoffs: the protected-requirement choice under time pressure and the human sign-off
recommendation.
