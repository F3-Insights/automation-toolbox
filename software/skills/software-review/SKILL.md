---
name: software-review
description: "What an independent code review checks before a change ships, in order: does it solve the issue and only the issue, do the tests prove it (the software-verify bar), is it correct at the edges, does it fit the repo's conventions and recorded decisions, and is it secure; with what counts as a blocker and a security checklist by stack. Use for reviewing any diff, in the software factory or by hand. For deeper security patterns, load software-security-knowledge."
---

# Reviewing a change

Review the change against the problem it claims to solve, not against how you would have written it. You get the issue, the diff and the evidence. Work in this order, because a change that solves the wrong problem does not need a style review.

## 1. The right problem

- Does the diff do what the issue asks, all of it? List each acceptance point and where the diff meets it.
- Does it do anything the issue did not ask? Unrelated refactors, renamed files, reformatting and new dependencies are blockers unless the issue needs them.

## 2. Proven

- Hold the tests to `software-verify`'s sufficient-tests bar, point by point.
- Read the tests as an adversary. Would each one fail if the fix were reverted? Does any test mock the very thing it claims to test, or assert only that nothing raised?
- `verify.json` must say `verified` for the head commit you are reviewing, with the repro shown.

## 3. Correct

- Edge cases the tests miss:
  - empty, null and boundaries;
  - concurrency and ordering;
  - time zones and dates;
  - encoding;
  - large inputs.
- Error handling: is an error surfaced or swallowed? A silent fallback that hides a failure is a blocker.
- Data: any change to stored data, a schema or a migration is a one-way door (rules file); say so even if it looks safe.

## 4. Fits the repo

- The repo's `CONTEXT.md` vocabulary and its ADRs. A change that contradicts a recorded decision without a superseding record is a blocker.
- Naming, idiom, comment density and error style of the surrounding code.
- No dead code, no commented-out code, no debugging output, no TODO without an issue.
- Docs the change makes wrong (README, CHANGELOG, API docs, docstrings) are updated with it.

## 5. Secure

Load the `software-security-knowledge` skill for the stack-specific checks (Supabase, FastAPI, Express, the OWASP basics). Always check:
- **Input:** untrusted input is validated; queries use parameters; no shell or eval of input.
- **Authorization:** checked on every new route or action, at the server, not only hidden in the UI.
- **Secrets:** none in code, tests, fixtures or logs, and no new variable read without need.
- **Data exposure:** responses and logs carry no more than they should.
- **Dependencies:** a new one is named, maintained and pinned, and its licence fits.

## Verdict

- **FAIL** for any blocker:
  - the wrong or partial problem;
  - tests that do not prove it;
  - a correctness bug;
  - a contradicted decision;
  - a security issue;
  - an unflagged one-way door.

  Each finding names the file, the line, the problem and the concrete fix.
- **PASS** otherwise. Minor findings may ride with a PASS.
- The verdict is for one head commit. Say which.
