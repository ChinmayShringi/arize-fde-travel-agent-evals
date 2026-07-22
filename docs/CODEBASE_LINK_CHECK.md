# Codebase pre-publish hygiene check

Repository: `sample-travel-agent`
Date first run: 2026-07-19
Amended: 2026-07-21 (sections 6, 7, 8 added; pre-push checklist corrected)
Amended again: 2026-07-21, second pass (this document was itself matching the secret
pattern it publishes; example key de-fanged, and every published command re-run)
Scope: engagement additions (tracing, evals, experiments, feedback loop) plus modified
upstream files. This is a real check run against the working tree; every result below is
from a command executed on the repo, not an estimate.

ASCII punctuation only. No key material is printed anywhere in this document; secret
checks report pattern hit counts and file counts only.

> **Read section 7 before trusting sections 2 and 3.** The procedure originally
> recommended for re-running the secret scan was structurally incapable of failing. The
> findings below were re-verified on 2026-07-21 with a corrected command and still hold,
> but they held by luck of scope, not by the strength of the check.

## 1. Git status summary

`git status --porcelain` at the time of the original 2026-07-19 check:

Modified (tracked), 8 files:

- `.gitignore`
- `agent/api.py`
- `agent/chat.py`
- `agent/loop.py`
- `agent/prompt.py`
- `agent/tools.py`
- `pyproject.toml`
- `uv.lock`

Untracked (new), 7 entries:

- `.github/` (contains `.github/workflows/feedback-loop.yml`)
- `agent/tracing.py`
- `evals/` (eval suite, judges, golden dataset, calibration helpers)
- `scripts/capture_baseline.py`
- `scripts/compare_experiments.py`
- `scripts/feedback_loop.py`
- `scripts/run_experiment.py`

Counts: 8 modified, 7 untracked entries. The change set is cohesive: modified files are
the agent loop plus config, and every new path is observability, evaluation, or
experiment tooling.

**These counts are a 2026-07-19 snapshot and are now superseded.** The working tree has
grown since (`docs/` moved in-repo, plus `agent/redaction.py`, `agent/session_store.py`,
and additional scripts). Deliberately no updated count is written here: the tree is
under active edit and any number committed to this page would be stale on arrival.
Re-run `git status --porcelain` yourself at commit time.

## 2. `.env` is gitignored and NOT tracked

- `git ls-files | grep -xE '\.env'` returns nothing: `.env` is not tracked.
- `git ls-files --error-unmatch .env` exits non-zero, confirming `.env` is not in the index.
- `git check-ignore -v .env` returns `.gitignore:1:.env`, confirming `.env` is ignored.
- The only env file tracked is `.env.example`, which contains empty-valued keys only.

Result: PASS. Re-verified 2026-07-21: `git check-ignore -v .env` still returns
`.gitignore:1:.env`, and `.env` is still absent from `git ls-files`.

Caveat now understood (see section 7): `.env` being ignored is exactly what made the
recommended re-scan blind. Ignored is not the same as absent, and a `git add -f` would
put it in the index while leaving it ignored.

## 3. Secret and API-key scan

Scope: all files that would enter a commit, i.e. tracked files plus untracked
non-ignored files (`git ls-files` union `git ls-files --others --exclude-standard`),
37 files total on 2026-07-19. Ignored paths (`.env`, `.venv/`, `__pycache__/`,
`traces/`) are excluded.

Patterns checked (hit counts only; no matched text is shown):

| Pattern | Description | Files matched |
|---|---|---|
| `sk-ant-[A-Za-z0-9_-]{20,}` | Anthropic API key literal | 0 |
| `AKIA[0-9A-Z]{16}` | AWS access key id | 0 |
| `ASIA[0-9A-Z]{16}` | AWS temporary access key | 0 |
| `ghp_[A-Za-z0-9]{36}` | GitHub personal access token | 0 |
| `xox[baprs]-[A-Za-z0-9-]{10,}` | Slack token | 0 |
| `BEGIN [A-Z ]*PRIVATE KEY` | PEM private key block | 0 |
| `ANTHROPIC_API_KEY[ ]*=[ ]*<value>` | Anthropic key assigned inline | 0 |
| `ARIZE_API_KEY[ ]*=[ ]*<value>` | Arize key assigned inline | 0 |
| `ARIZE_SPACE_ID[ ]*=[ ]*<value>` | Arize space id assigned inline | 0 |

A broader sweep for `(API_KEY|SPACE_ID|TOKEN|SECRET)` followed by a non-empty inline
value across the same 37 files also matched zero files.

Result: PASS. Secret names appear in source only as `os.getenv(...)` reads and as
empty-valued keys in `.env.example`; no secret values are present in any tracked or new
file.

**Re-verified 2026-07-21 with the corrected command**, over the current in-scope set
(now larger, because `docs/` moved into the repo; 199 files at the time of this re-run,
and the tree is still under edit, so treat that figure as a timestamp, not a constant):

```
$ { git ls-files -z; git ls-files -z --others --exclude-standard; } \
    | xargs -0 command grep -lE 'sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|BEGIN [A-Z ]*PRIVATE KEY'
$ echo $?
1
```

No output, exit status 1. Zero files matched. The result stands.

**Correction, 2026-07-21 (second pass).** This re-run initially returned **one** match,
exit status 0, and the matching file was **this document**. An earlier revision of section
7 illustrated the force-add failure mode with a contiguous example key, and that example
matched the very pattern this section publishes. The scan was working correctly; the page
documenting the scan was the thing that broke it. The example literal has been de-fanged
(see the note at the end of section 7), and the exit-1 result above is from the re-run
after that change. Recorded rather than quietly corrected, because a self-matching
detector is the same class of error as the blind detector in section 7: the artifact that
certifies the check is inside the check's own scope.

One further note for accuracy: a **loose** search for `sk-ant-api` now flags two files,
`docs/REMEDIATION_PLAN.md` and this file, in both cases because the string appears in
prose as part of a written finding. Neither matches the strict 20-or-more-character
pattern, because no key material follows. Real output:

```
$ { git ls-files -z; git ls-files -z --others --exclude-standard; } \
    | xargs -0 command grep -lE 'sk-ant-api'
docs/CODEBASE_LINK_CHECK.md
docs/REMEDIATION_PLAN.md
$ echo $?
0
```

Documentation mentions, not secrets. Use the strict pattern for the gate.

## 4. `traces/` ignored

- `git check-ignore -v traces/x.jsonl` returns `.gitignore:7:traces/`.
- The local JSONL span sink defaults to `<repo>/traces/spans.jsonl`, which spans full
  conversation content, so keeping `traces/` ignored is important and confirmed.
- `.venv/` and `__pycache__/` are also confirmed ignored.

Result: PASS. Captured spans cannot be committed by accident.

## 5. Large-file check

Threshold: 256 KB. Across all 37 in-scope files on 2026-07-19, no file exceeded the
threshold.

- The largest tracked file is `uv.lock` at 233,705 bytes (about 228 KB), which is a
  normal, expected lockfile and is under the threshold.

Result: PASS as of 2026-07-19, **superseded on 2026-07-21**. Now that `docs/` is in-repo,
the captured evidence under `docs/baseline/` and `docs/experiments/` is in scope, and it
was never covered by the original check. Re-run, real output:

```
$ { git ls-files -z; git ls-files -z --others --exclude-standard; } \
    | xargs -0 ls -l | awk '$5 > 262144 {print $5, $9}'
382592 docs/baseline/2026-07-19/spans.jsonl
620136 docs/experiments/candidate-A-prompt/spans.jsonl
589198 docs/experiments/candidate-AB-combined/spans.jsonl
564444 docs/experiments/candidate-B-toolfix/spans.jsonl
627443 docs/experiments/candidate-C-concise/spans.jsonl
589144 docs/experiments/control-v0-cached/spans.jsonl
591243 docs/experiments/control-v0-cached2/spans.jsonl
569397 docs/experiments/control-v0-cachetest/spans.jsonl
570362 docs/experiments/control-v0/spans.jsonl
619520 docs/experiments/model-opus-4-8-fixed/spans.jsonl
732417 docs/experiments/model-opus-4-8/spans.jsonl
637085 docs/experiments/model-sonnet-5-fixed/spans.jsonl
768679 docs/experiments/model-sonnet-5/spans.jsonl
299646 uv.lock
```

Fourteen files now exceed the 256 KB threshold, where the 2026-07-19 run found zero.
Assessment, and it is a deliberate accept rather than a failure:

- The thirteen `spans.jsonl` files are the **captured evidence** the whole engagement
  rests on. They are text JSONL, they diff, and hard rule 4 of the project constitution
  requires them to survive independently of the platform's 7-day retention. Committing
  them is the point. Largest is 768,679 bytes (about 750 KB); total is well inside what
  git handles comfortably and nowhere near needing LFS.
- `uv.lock` has grown from 233,705 to 299,646 bytes and now crosses the threshold. It is
  a normal lockfile and the growth tracks dependency additions made during the
  engagement. Accept.

Result: PASS with the threshold consciously waived for evidence files and the lockfile.
No unexpected binary blob, no build artifact, and no `.venv` content is in scope.

## 6. `docs/` now lives inside the repository

Structural change, 2026-07-21. Previously `docs/` was a **sibling** of the git root
(`.../sar/docs`, next to `.../sar/sample-travel-agent`). It has been moved to
`<repo root>/docs`, i.e. `sample-travel-agent/docs`.

What this changes for this document:

- `docs/` is **not** ignored: `git check-ignore -v docs` exits non-zero. It is
  untracked-but-eligible, so it enters the commit scope and enters the secret-scan
  scope. Both were re-run above with `docs/` included.
- Paths of the form `../docs/...` or the absolute `/Users/chinmay_shringi/Desktop/sar/docs/...`
  are obsolete. Everything now resolves as `<repo root>/docs/...`, and repo-relative
  paths such as `docs/baseline/2026-07-19/spans.jsonl` are valid from the repo root.
- The checklist command in step 5 below (`evals/run_evals.py docs/baseline/...`) now
  actually resolves after a fresh `git clone`. Before the move it could not, because the
  referenced file was outside the repository and therefore not part of the deliverable.
  This was the substance of finding P0-02.
- The in-scope file count and the large-file check (section 5) both grew as a result and
  are the two sections most affected.

No statement elsewhere in this document assumes `docs/` sits outside the repo; sections
1, 3, and 5 have been annotated where their counts predate the move.

## 7. Discovered defect: the recommended secret re-scan reported a false clean

This is a defect **in this project's own verification procedure**, not in the code under
review. It is recorded here because a check that cannot fail is worse than no check: it
manufactures confidence.

**What the procedure claimed.** The pre-push checklist (previously step 2) said to
"re-run the secret scan over the files you are about to commit (section 3 patterns);
expect zero hits." The natural reading, and the natural command, is a recursive `grep`
from the project root.

**Why it was structurally blind.** In this shell environment, `grep` is not
`/usr/bin/grep`. It is a **zsh function** that execs `ugrep` with `--ignore-files`, which
makes the search honor `.gitignore`. Line 1 of `.gitignore` is `.env`. Therefore any
recursive `grep` from the project root **cannot see `.env`**, which is precisely the file
that holds live credentials. The check reported clean unconditionally: it would have
printed the same result with or without a secret on disk.

**How it was caught.** By diffing the shimmed `grep` against `command grep` on the same
pattern over the same tree. Real output, section-3 Anthropic pattern, re-run from the
repository root on 2026-07-21 after the de-fang described at the end of this section:

```
$ grep -rlE 'sk-ant-[A-Za-z0-9_-]{20,}' .
$ echo $?
1

$ command grep -rlE 'sk-ant-[A-Za-z0-9_-]{20,}' .
./.env
$ echo $?
0
```

Exit 1 with no output is "clean". Exit 0 naming `./.env` is the truth. Same pattern, same
directory, opposite verdicts. The shim is confirmed by `type grep`, which reports
`grep is a shell function`; the function body execs the `claude` binary under `ARGV0=ugrep`
with `-G --ignore-files --hidden -I --exclude-dir=.git` (plus the other VCS directories)
prepended to the caller's arguments, so `--ignore-files` is applied whether or not the
caller asked for it.

**The failure mode this would have missed in production.** A `git add -f .env` puts the
file in the index while it remains gitignored, so it commits and the shimmed scan still
says clean. Reproduced in a throwaway repository:

```
$ mkdir /tmp/scanproof && cd /tmp/scanproof
$ git init -q .
$ printf '.env\n' > .gitignore
$ KEY="sk-ant-""api03-EXAMPLENOTAREALKEY000000000"
$ printf 'ANTHROPIC_API_KEY=%s\n' "$KEY" > .env
$ git add .gitignore && git add -f .env && git commit -qm x

$ grep -rlE 'sk-ant-[A-Za-z0-9_-]{20,}' .
$ echo $?
1                                    <-- committed secret, still reports clean

$ git ls-files -z | xargs -0 command grep -nE 'sk-ant-[A-Za-z0-9_-]{20,}' \
    | command cut -d: -f1,2
.env:1                               <-- caught, with file and line

$ git ls-files -z | xargs -0 command grep -qE 'sk-ant-[A-Za-z0-9_-]{20,}'
$ echo $?
0
```

Re-run in full on 2026-07-21; the output above is what that run printed. The throwaway
repository was deleted afterwards.

**Why the example key is written as `"sk-ant-""api03-..."` and why `cut` is in the
pipeline. Do not "clean this up".** This document publishes the pattern
`sk-ant-[A-Za-z0-9_-]{20,}` and is itself inside the scan scope, so any contiguous
example key written on this page becomes a hit against the repo's own secret scan. The
adjacent-string-concatenation form is a single shell token that expands to the intended
value at runtime, so the demonstration still runs exactly as printed, while the page text
never contains a contiguous match. `command cut -d: -f1,2` keeps `grep -n`'s file and line
number and drops the matched text, for the same reason. The separate `grep -q` line is
there because the exit status of a pipeline is the exit status of its last stage, so `cut`
would otherwise mask the result being demonstrated. A future editor who replaces this with
a realistic-looking literal will make the section 3 scan report a false positive on this
file and will make the pre-push checklist fail for everyone who follows it.

**Scope of the impact.** The original section 3 result was *correct*, because section 3
scoped itself explicitly with `git ls-files` union `git ls-files --others
--exclude-standard` rather than a bare recursive grep. The defect was in the
**instruction given to the reader for re-running it**, which dropped that scoping. So no
wrong conclusion was published; the risk was that the next person to follow the checklist
would get a guaranteed pass.

**The fix.** The checklist now specifies the index-driven form
(`git ls-files -z | xargs -0 command grep -nE ...`) with `command` written explicitly, and
says why, so that a future reader does not "simplify" it back to `grep -r` and silently
restore the blind spot. `git ls-files` is the right scope precisely because it lists the
index, which means a force-added file appears there even though it is gitignored.

**Generalization worth carrying forward.** Any verification step whose passing output is
indistinguishable from its blind output is not a verification step. When a check has
never once failed, deliberately break it and confirm it fails.

## 8. Archive hygiene: a ZIP containing a live key was quarantined

The deliverable for this engagement is a **git link**, not an archive. That distinction
turned out to matter.

**What was found.** A ZIP at `<parent of repo>/Archive.zip`, about 90 MB, 12,392 entries,
containing:

- `sample-travel-agent/.env` (253 bytes) with **live credentials**, byte-identical to the
  working `.env`. The `.gitignore` protection is a git mechanism; a filesystem ZIP walks
  straight past it.
- `sample-travel-agent/.git/` (full history and object store)
- `sample-travel-agent/.venv/` (the reason for most of the 12,392 entries)
- Internal preparation material not intended for the customer: `BUILD_PLAN.md`,
  `CLAUDE.md`, `Arize_AI_FDE_Interview_1_Master_Discovery_Playbook.pdf`,
  `Arize_FDAIE_Interview_1_Discovery_Playbook.docx`, `US_FDE_Interview_Screen.pdf`.

**Action taken.** The file has been quarantined by renaming it in place to:

```
Archive.UNSAFE-CONTAINS-LIVE-KEY-DO-NOT-SEND.zip
```

The name is deliberately unmissable so it cannot be attached by muscle memory. It sits in
the repo's parent directory and is therefore outside the git deliverable entirely.

**Exposure assessment.** The ZIP was **never sent**. The keys were exposed **locally
only**: on-disk, on one machine, never transmitted, never committed to git history (`.env`
has never been tracked; see section 2). Accordingly, key rotation is a **deferred hygiene
item, not an incident.** Rotate at the next convenient point and note it as good practice
rather than as breach response. Do not describe this as a security incident, because it
was not one, and overstating it is as inaccurate as understating it.

**Standing rule.** Ship the git link. If an archive is ever genuinely required, build it
from `git archive HEAD`, which exports the tracked tree only and therefore cannot include
`.env`, `.git/`, or `.venv/` by construction. Never build a deliverable with a recursive
filesystem zip of a working directory.

## Recommended pre-push checklist for the candidate

Run these yourself before pushing. This document did not run `git add`, `git commit`, or
`git push`.

**Write `command grep`, not `grep`, in every step below.** In this environment `grep` is
a shell function that execs `ugrep --ignore-files`, so it honors `.gitignore` and will
silently skip `.env` and anything else ignored. `command` bypasses the function and runs
the real `/usr/bin/grep`. Removing the word `command` re-introduces the false clean
documented in section 7. This is the single most important line in this checklist.

Every step below was executed from the repository root on 2026-07-21 and the output shown
is what it actually printed on that run. Exit statuses are stated explicitly, because for
three of these steps a bare "no output" is the pass condition and you cannot tell a pass
from a crash without the status.

1. Re-confirm `.env` is not staged:

   ```
   $ git status --porcelain | command grep -E '(^| )\.env$'
   $ echo $?
   1
   ```

   No output, exit 1. That is the pass. (This one reads a pipe rather than the file tree,
   so the shim would not actually have broken it, but keep `command` for consistency: a
   checklist where the rule holds everywhere is a checklist people follow.)

2. Re-run the secret scan over exactly the files that will enter the commit:

   ```
   $ { git ls-files -z; git ls-files -z --others --exclude-standard; } \
       | xargs -0 command grep -nE \
         'sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|BEGIN [A-Z ]*PRIVATE KEY'
   $ echo $?
   1
   ```

   No output, exit 1. That is the pass, and it is the observed result as of 2026-07-21.
   Why this exact form: `git ls-files` enumerates the **index**, so a gitignored file that
   was force-added with `git add -f` still appears and still gets scanned. A recursive
   `grep -r` from the project root would not scan it, and would report clean whether or not
   a secret was committed.

   If this step ever prints `docs/CODEBASE_LINK_CHECK.md`, you have not found a secret. You
   have found that someone rewrote the example key in section 7 into a contiguous literal.
   That exact false positive occurred on 2026-07-21 and is recorded in section 3.

3. Prove the check can still fail, once, before you trust it:

   ```
   $ command grep -rlE 'sk-ant-[A-Za-z0-9_-]{20,}' .
   ./.env
   $ echo $?
   0
   ```

   `./.env` and exit 0 is the expected result on this machine, and is what the 2026-07-21
   run printed. If it prints nothing, either the key has been rotated out of `.env` or you
   have re-introduced the shim, and you must find out which before proceeding. Note that
   this step is expected to name exactly one file: `./.env`. If it names a second file
   under `docs/`, see step 2.

4. Re-run the large-file check:

   ```
   $ { git ls-files -z; git ls-files -z --others --exclude-standard; } \
       | xargs -0 ls -l | awk '$5 > 262144 {print $5, $9}'
   382592 docs/baseline/2026-07-19/spans.jsonl
   620136 docs/experiments/candidate-A-prompt/spans.jsonl
   589198 docs/experiments/candidate-AB-combined/spans.jsonl
   564444 docs/experiments/candidate-B-toolfix/spans.jsonl
   627443 docs/experiments/candidate-C-concise/spans.jsonl
   589144 docs/experiments/control-v0-cached/spans.jsonl
   591243 docs/experiments/control-v0-cached2/spans.jsonl
   569397 docs/experiments/control-v0-cachetest/spans.jsonl
   570362 docs/experiments/control-v0/spans.jsonl
   619520 docs/experiments/model-opus-4-8-fixed/spans.jsonl
   732417 docs/experiments/model-opus-4-8/spans.jsonl
   637085 docs/experiments/model-sonnet-5-fixed/spans.jsonl
   768679 docs/experiments/model-sonnet-5/spans.jsonl
   299646 uv.lock
   ```

   Exit 0. These are the fourteen known entries listed in section 5 (thirteen
   `spans.jsonl` evidence files plus `uv.lock`), all consciously accepted, and the sizes
   above are byte-identical to the section 5 capture. Investigate anything else,
   particularly anything binary or under `.venv/`.

5. Sanity-run the offline eval CLI to confirm the suite still loads, from the repo root:

   ```
   $ uv run python evals/run_evals.py docs/baseline/2026-07-19/spans.jsonl /tmp/evalcheck
   Eval   Name                    Appl  Pass  Fail   Rate
   ------------------------------------------------------
   E1     fabricated_entity         23    23     0   100%
   E2     flight_direction           6     0     6     0%
   E3     tool_call_validity        16    16     0   100%
   E6     pii                       23    23     0   100%
   E7     guardrails                23    23     0   100%
   E4     itinerary_day_count        2     0     2     0%
   E10    conflicting_context        1     1     0   100%
   E5     empty_result_honesty       1     1     0   100%

   23 trace(s), 95 result(s) -> /tmp/evalcheck
   $ echo $?
   0
   ```

   Exit 0. This runs against the **baseline** spans, so the two 0% rows are the expected
   as-shipped failures, not a regression introduced by this check:

   - E2 `flight_direction` 0/6 matches the baseline figure already recorded in
     `docs/MONITORS.md` ("0/6 = 100% failure").
   - E4 `itinerary_day_count` 0/2 is the off-by-one at `agent/tools.py:80`,
     `for day in range(1, int(num_days))`, which is a known detected-but-unfixed item.

   The table lists E1 through E7 plus E10; the row order is emission order, not numeric
   order. This step makes no network calls, so it is safe to run offline and costs nothing.
   The repo-relative path only works because `docs/` now lives inside the repository; see
   section 6.

6. Confirm no archive is being attached. The deliverable is the git link. If an archive
   is unavoidable, build it with `git archive HEAD`, never with a recursive filesystem
   zip. See section 8.

7. Review the diff of the modified upstream files so the observability changes stay
   additive and default-off.

8. Stage the observability, eval, experiment, and documentation additions together as one
   logical change. Suggested commit message:

   ```
   feat: add tracing, eval suite, experiments, and nightly feedback loop

   - agent/tracing.py: dual-sink OTel export (Arize AX + local JSONL),
     fail-open and default-off; agent behavior unchanged when env is unset
   - agent/redaction.py: PII redaction at the serving entry point
   - evals/: deterministic E1-E7 suite + E8/E9 LLM judges, golden dataset,
     run_evals / run_judges CLIs
   - scripts/: run_experiment, compare_experiments, capture_baseline,
     feedback_loop (env-gated candidates PROMPT_VARIANT / FLIGHT_TOOL_FIX)
   - docs/: findings, baseline and experiment evidence, monitor specification
   - .github/workflows/feedback-loop.yml: nightly loop, experiments gated
     on the ANTHROPIC_API_KEY secret
   ```

9. Push with upstream tracking if this is a new branch: `git push -u origin <branch>`.
