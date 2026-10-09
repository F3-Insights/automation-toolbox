---
name: software-verify
description: "The standard for proving a code change works: reproduce the problem before fixing it, hold the tests to a sufficient-tests bar (each acceptance point, edge cases, error paths, a regression test, the full suite, the running app for visible changes), run the repo's own declared checks, and keep the evidence. Use when building or testing a change, by hand or in the software factory, or for \"is this actually fixed\". For reviewing someone else's diff, use software-review."
---

# Verifying a change

A change is verified when the evidence says so, not when the code looks right. The evidence is a reproduction that failed before and passes after, tests that would catch the problem coming back, the repo's own checks passing, and, for anything a person sees, the thing itself working.

## 1. Reproduce first

Before any fix, show the problem:
- **a failing test** in the repo's framework that encodes the expected behaviour, or
- **a recorded command** whose output shows the problem (a CLI call, an HTTP request, a script), when a test cannot express it yet.

Run it on the unchanged code and keep the output. If it does not fail, you have not found the problem: look further, ask, or stop. A bug that resists reproduction gets a feedback loop first: build a fast, deterministic pass/fail command that drives the real code path and goes red on this exact symptom (a test at some seam, a scripted HTTP call, a CLI run against a fixture, a headless browser script, a replayed captured request), then come back here. Never write the fix first and the test after; a test written after the fix tends to test the fix, not the problem.

A feature has no bug to reproduce: its repro is the acceptance test that fails because the feature is missing.

## 2. Sufficient tests

A change is sufficiently tested when:
1. **Each acceptance point** of the issue has a test that would fail without the change.
2. **Edge cases** around what changed are covered: empty and missing input, boundaries (zero, one, many, the limit), wrong types or formats, and the year, month or timezone boundary for anything with dates.
3. **Error paths** the change touches are tested, not only the happy path: what the user sees when it goes wrong.
4. **A regression test** names the issue (in its name or a one-line comment) so that it stays when someone tidies the suite.
5. **The full suite** the repo declares passes, not only the new tests. A failure that already failed on the base is named as pre-existing, not fixed in passing and not hidden.
6. **Visible changes are looked at:**
   - a UI change is checked in a browser at the size it ships at, with a before and an after screenshot;
   - an API or CLI change is called for real and the response kept.
7. **Coverage**, when the repo's rules set `- Minimum diff coverage: N%` and declare a `coverage` command: the lines the change added or altered are covered at least that much.

Tests are not sufficient when they:
- assert only that no exception was raised;
- mock the thing being fixed;
- were changed to match new wrong behaviour;
- are skipped or marked expected-to-fail.

## 3. The repo's own checks

Run what the repo declares, in its order:
- in the software factory, `.software-factory/commands.yaml` (setup, lint, typecheck, test, build, coverage);
- otherwise its documented check command (`CONTRIBUTING`, `CLAUDE.md`, the CI workflow).

In the software factory, `software-factory-verify` runs them from the base commit in a clean, offline environment and writes `verify.json`; its verdict is the one that counts. Your own run is for finding problems early.

## 4. Evidence

Keep, in the evidence folder you are given:
- the repro command and its output before and after;
- the test command and its summary;
- the screenshots or API responses.

The pull request body cites them (`software-pr`).
