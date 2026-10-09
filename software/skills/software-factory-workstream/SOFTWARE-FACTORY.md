# Software factory

The software factory turns a GitHub repository's issues into verified, reviewed pull requests, the way a month-end close turns a ledger into a closed month. It follows the orchestrator design in the `orchestrator-scaffold` skill. This file is the factory's own contract: the pieces, the files that pass between them, and the policies. Nothing here names a client, a person or a machine path.

## The loop

One session of `software-factory-orchestrator` works one repository. Whatever launches it (a person, or a scheduler) runs it as three phases:

| Phase | Kind | What |
|---|---|---|
| `prepare` | code, with GitHub access | `software-factory-sync` writes a snapshot of the repo's issues, the factory's open pull requests (CI, review comments, mergeability) and default-branch CI into the Run folder, and fetches the local clone. |
| `run` | agent session, **no GitHub access** (no token, no network to GitHub) | The orchestrator: finish what is started, triage, build, verify, review, then write the ship manifest and the outbox. |
| `finish` | code, with GitHub access | `software-factory-ship` reads the manifest and the outbox: pushes verified branches, opens or updates pull requests, posts the queued comments and labels, merges what the rules allow into the integration branch, and keeps one release pull request open for a person. |

The agent session can read code, run tests and write files, but nothing it runs (including test code it wrote) can reach GitHub or the owner's token. Only the two deterministic tools do, and each does exactly its job.

Session order inside `run`:
1. **Finish what is started.** Open factory PRs with failing CI, unanswered review comments or merge conflicts go back to their builder first (the "babysit").
2. **Triage** the open issues (or the issue or topic given) under the collection policy: `build`, `ask` (unclear; a question goes on the issue), `human` (strategic, a one-way door, or outside policy), or `skip` (excluded).
3. **Build** each `build` issue in its own worktree: reproduce first, then fix.
4. **Test** each built branch independently: the tests the change needs, from the issue and the diff only.
5. **Verify** with the repo's own declared checks from the base commit, offline.
6. **Review** each verified branch independently.
7. **Record** each outcome in the ledger, and write the ship manifest and the outbox.

`software-factory-check` computes each issue's state from the ledger and the snapshot; `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_sync.py --precheck` drives a heartbeat. A weekly `software-factory-lookback` session looks for recurring problems.

## The repo's contract: `.software-factory/`

Committed in the target repository, so it travels with the code and changes by pull request.

### `.software-factory/commands.yaml`

```yaml
setup: "python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"   # optional
test: ".venv/bin/python -m pytest -q"                                  # required
lint: ".venv/bin/ruff check ."                                         # optional
typecheck: ""                                                          # optional
build: "npm run build"                                                 # optional
coverage: ".venv/bin/python -m pytest --cov=src --cov-report=json"     # optional
# A command may be a mapping: {run: "npm test", cwd: "ui/frontend"}
# A list runs in order: test: ["pytest -q", {run: "npx vitest run", cwd: ui}]
```

Read from the **base commit** (`git show <base>:.software-factory/commands.yaml`), never from the branch, so a branch cannot change the checks it is judged by. A placeholder (`true`, `echo ...`, `:`, empty) counts as no command. A repo with no `test` command cannot be built by the factory; its first factory PR is the `.software-factory/` folder itself: onboarding, below.

### `.software-factory/SOFTWARE-FACTORY-RULES.md`

The repo's policies, in prose with a few field lines tools read:

```markdown
# Factory rules

- Integration branch: development
- Default branch: main
- Auto-merge: yes            # merge a passing factory PR into the integration branch
- Release PR: yes            # keep one integration -> default PR open for a person
- Builds per week: 5
- Minimum diff coverage: 80%   # optional; needs a coverage command
- Protected paths: migrations/; infra/; .github/workflows/

## Collection policy
What the factory may take on by itself: issues with a clear expected behaviour that an agent
can reproduce and verify locally (a failing test or a recorded command), touching no
protected path. Everything else is asked or left for a person.

## Approval policy
Auto-merge into the integration branch only when CI passes, the reviewer passed, no protected
path or one-way door is touched, and the change is in a low-risk class (UI styling, a
unit-tested fix, docs, tests). Anything else waits for a person's review.

## One-way doors
Database migrations, deleting data, auth and permissions, payments, public API changes,
dependency major upgrades.
```

Owner-private policy (whose issues are the owner's to decide, people to ask) stays in the owner's own settings, never in the repo.

## Onboarding: issue 0

Onboarding is the factory's issue 0: the change that writes a repo's `.software-factory/` (`onboard.md` in the `software-factory-workstream` skill). It is needed when the integration branch has no `.software-factory/commands.yaml` with a real `test` command, and then it is the only work of the session. Its branch is exactly `software-factory/onboard`, its worktree `.../issue-0/`, and its ledger rows are issue `0`; output names it `onboarding`, never `#0`.

```
python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_worktree.py OWNER/NAME --issue 0 --format json
python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_record.py OWNER/NAME --issue 0 --state building --branch software-factory/onboard --title Onboarding --by software-factory-orchestrator
python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_verify.py <worktree> --base <base_sha> --commands-from head --out RUN/evidence/issue-0/verify.json
```

`--commands-from head` exists for this branch only: the base has no commands yet, so verify reads the commands file and the rules from the branch's HEAD, records `commands_from` as `<file>@<head_sha>` and says so in `notes`. On any other branch it is refused. The manifest entry has `"issue": 0`, `"branch": "software-factory/onboard"`, `verify_file` `evidence/issue-0/verify.json` and a `title` of its own. `software-factory-ship` opens its PR with that title, adds no `Refs #0` and comments on no issue, and never merges it: a person merges a repo's first rules, whatever its risk. The outbox cannot comment on or label issue 0.

## Branches, worktrees, names

- Factory branches: `software-factory/issue-<n>-<slug>` (slug: lowercase, `[a-z0-9-]`, at most 40 characters). One per issue. `software-factory/onboard` is issue 0, onboarding.
- Worktrees: `<repos_dir>/.software-factory-worktrees/<owner>__<repo>/issue-<n>/`, where `<repos_dir>` is `$SOFTWARE_FACTORY_REPOS_DIR`, else the `repos_dir` setting under `[software-factory-workstream]` (the folder holding the local clones), made by `software-factory-worktree` from the local clone's `origin/<integration branch>`.
- Never push or merge to the default branch or any protected name (`main`, `master`, `prod`, `production`, `release`, `live`). Merges go only into the integration branch.

## Files that pass between the phases

All in the Run folder (`RUN`), except the ledger and the worktrees.

### Written by `software-factory-sync` (prepare)

`RUN/sync/`:
- `repo.json`: `{owner, name, default_branch, integration_branch, has_integration_branch, local_clone, fetched_at, head_sha_integration, factory_dir_present, rules_present, rules, protected_paths, notes, commands_file, test_command, needs_onboarding, owner_login, filter}` (`rules` is the rules file's field lines, keys lowercased; `commands_file` the commands file on the integration branch or null; `test_command` whether it declares a real test command, null without a clone; `needs_onboarding` true when it does not).
- `issues.json`: a JSON list of the open issues, each `{number, title, body, labels, author, assignees, created_at, updated_at, comments: [{author, body, created_at}], excluded}`, where `excluded` is the owner policy's reason or null. Filtered by issue numbers or `--topic` when given.
- `prs.json`: a JSON list of the open pull requests whose head is a factory branch, each `{number, url, title, head, base, issue, head_sha, state, is_draft, mergeable ("mergeable"|"conflicting"|"unknown"), merge_state, ci ("success"|"failure"|"pending"|"none"), failing_checks: [{name, conclusion, url, log_tail}], review_state (GitHub's review decision, e.g. "APPROVED", or null), unanswered_comments: [{kind, author, body, created_at, path?, url?}] (people's comments after the last factory comment), last_factory_comment_at, labels, author}`.
- `ci.json`: the default and integration branches' latest CI runs and failures.
- `SYNC.md`: the human summary, and the first line `SYNCED: <n> issues, <m> factory PRs, CI <state>` (or `STALE: <reason>` when GitHub could not be read; then nothing else is written and the session works from nothing new). `SYNC.md` is written last, so a folder without it is an incomplete snapshot; `software-factory-check` refuses one.

A comment the factory posts starts `From the software factory:` and carries the line `<!-- software-factory -->`. That marker, never the wording, is how sync and check tell the factory's comments from people's.

### Written by the session (run)

`RUN/ship/manifest.json`:

```json
{"repo": "owner/name",
 "branches": [
   {"issue": 42, "branch": "software-factory/issue-42-fix-date-parse", "worktree": "<path>",
    "head_sha": "<sha>", "base": "development",
    "title": "Fix date parsing for ISO week dates", "body_file": "ship/pr-42.md",
    "verify_file": "evidence/issue-42/verify.json", "review_file": "evidence/issue-42/review.json",
    "risk": "low|normal|one-way-door", "action": "open|update",
    "changes": "on update: what the new commits do (optional)"}
 ]}
```

`base` is the integration branch's name from `repo.json`. `worktree` is absolute; the other paths are relative to `RUN`.

`RUN/ship/outbox.json`: queued GitHub writes that are not branches:

```json
{"comments": [{"issue": 51, "body": "...", "kind": "question|status|answer"}],
 "labels":   [{"issue": 51, "add": ["software-factory:needs-info"], "remove": []}]}
```

`RUN/evidence/issue-<n>/`: `verify.json` (from `software-factory-verify`), `review.json` (the reviewer's json block as returned: `software-factory-ship` reads its `review` and `head_sha`), screenshots, logs.

### `software-factory-verify` output (`verify.json`)

```json
{"worktree": "...", "base": "development", "base_sha": "...", "head_sha": "...",
 "commands_from": ".software-factory/commands.yaml@<base_sha>",
 "steps": [{"name": "setup|lint|typecheck|test|build|coverage", "run": "...", "cwd": ".", "exit": 0,
            "seconds": 12.3, "log": "evidence/issue-42/test.log", "summary": "212 passed"}],
 "repro": {"command": "pytest tests/test_dates.py::test_iso_week", "base_exit": 1, "head_exit": 0},
 "diff_coverage": {"percent": 85.7, "covered": 12, "total": 14, "minimum": 80.0,
                   "files": [{"path": "src/dates.py", "covered": 12, "total": 14, "percent": 85.7,
                              "uncovered": [88, 91]}],
                   "report": "coverage.json", "format": "coverage.py"},
 "verdict": "verified|failed|no-tests|repro-not-shown",
 "notes": ["..."],
 "offline": true}
```

`commands_from` is `<file>@<base_sha>`, or `<file>@<head_sha>` for onboarding with `--commands-from head`; `software-factory-ship` refuses a head-sourced one on any other branch.

`verified` needs every declared step to exit 0, the worktree clean when the checks start, the diff coverage at or above the rules' minimum when one is set, and, when a repro is given, the repro to fail on the base and pass on the head.

Diff coverage is the covered share of the lines the branch added or changed (`git diff -U0
<base_sha>...HEAD`) among the lines the coverage report knows. The `coverage` command must
write `coverage.json` (coverage.py's `coverage json`), `coverage/lcov.info` or `lcov.info` (lcov), or `coverage/coverage-final.json` (istanbul), in its folder or the worktree root; istanbul's `coverage-summary.json` has no line data and does not count. The minimum is read from the base commit's rules, like the commands. With a minimum set, no usable report is a `failed`; with none, `diff_coverage` is only reported (and absent when there is no coverage command).

### The ledger

`<state_dir>/<owner>__<name>/SOFTWARE-FACTORY-LEDGER.csv`, where `state_dir` is `$SOFTWARE_FACTORY_STATE_DIR` or `~/.local/state/software-factory`. One row per issue attempt, appended or updated by `software-factory-record` only:

`id,issue,attempt,state,branch,pr,head_sha,verify,review,risk,note,updated_at,by`

state: `triaged-build`, `triaged-ask`, `triaged-human`, `skipped`, `building`, `verified`, `failed`, `reviewed`, `pr-open`, `merged`, `released`, `reopened`, `abandoned`. `id` is `<issue>:<attempt>`; issue `0` is onboarding. Nothing is deleted.

## The tools (commands)

| Command | Phase | Does |
|---|---|---|
| `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_sync.py OWNER/NAME [N ...] --out RUN/sync [--issue N ...] [--topic TEXT] [--owner LOGIN]`, or `... --precheck` in place of `--out` | prepare, heartbeat | The snapshot above, and `git fetch` of the local clone. Issue numbers may follow OWNER/NAME as arguments (as a scheduler expands a list) or come as `--issue`. `--precheck` prints `WORK: ...` or `NOTHING: ...` (open eligible issues not in the ledger, factory PRs needing attention, mergeable PRs to merge, or onboarding needed: no commands file with a test command on the integration branch and no `software-factory/onboard` PR open), fetches nothing and writes nothing. |
| `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_worktree.py OWNER/NAME --issue N --slug S [--base B] [--format text\|json]` | run | Creates or reuses the issue's worktree and branch from the local clone, offline. Prints the path, or with json `{path, branch, base, base_sha, created\|reused}`. `--issue 0` is onboarding: branch `software-factory/onboard`, no `--slug`. |
| `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_verify.py WORKTREE --base REF [--repro CMD] [--out FILE] [--steps LIST] [--timeout-s S] [--commands-from base\|head]` | run | Runs the base commit's `.software-factory/commands.yaml` (the head's, with `--commands-from head`, on the onboarding branch only) in the worktree, offline (no GitHub token, no SSH agent), the repro on base and head, and the diff coverage against the base's rules. Writes `verify.json`. |
| `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_record.py OWNER/NAME --issue N --state S [--attempt K \| --new-attempt] [--branch B] [--pr P] [--head-sha H] [--verify V] [--review R] [--risk X] [--note T] [--title T] --by WHO` | run | Upserts one ledger row (issue 0 is onboarding; default: the issue's latest attempt; `--new-attempt` for a re-build). `--verify` takes a verdict (`verified`, `failed`, `no-tests`, `repro-not-shown`) and `--review` `PASS` or `FAIL`, not file paths. A new head SHA without a new review clears the review. `--title` keeps the title beside the ledger for the repeat check. |
| `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_check.py OWNER/NAME [--sync RUN/sync] [--format text\|json] [--stale-hours 24]` | run, heartbeat | Each issue's state from the ledger and the snapshot, the counts, stalled work (a branch verified but never shipped, a PR open with failing CI or unanswered comments past the stale hours, a PR approved and green but not merged, a build that died, a question unanswered for 3 days), reopened issues, and repeat offenders (several attempts; titles like a recent merge, heuristic). Issue 0 is shown as `onboarding`. |
| `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_ship.py OWNER/NAME --run RUN [--dry-run] [--owner LOGIN] [--format text\|json]` | finish | Applies the manifest and the outbox, under the guards. |

### `software-factory-ship`'s guards

For each manifest branch, refuse unless:
- the branch name matches the factory pattern for its issue (`software-factory/onboard` for issue 0) and the base is the integration branch, never a protected name or the default branch;
- the worktree's HEAD equals `head_sha`;
- `verify.json` says `verified` for that `head_sha`, its base SHA is an ancestor of the pushed branch, and its `commands_from` is at the base SHA (or, on the onboarding branch only, at `head_sha`);
- `review.json` says `PASS` for that `head_sha`;
- the diff touches no protected path, unless `risk` is `one-way-door` (then the PR opens but is never auto-merged).

Push with `git push origin <branch>` (no force, except `--force-with-lease` on the factory's own branch when updating), then `gh pr create` or update, with the body file, the `software-factory:pr-open` label, and a comment on the issue linking the PR. Then, for every open factory PR (not only this run's): merge into the integration branch (squash) when the rules say `Auto-merge: yes`, CI is `success`, the review passed, the PR is mergeable, it is not a one-way door or the onboarding PR, and every review comment has a factory answer. Keep or open one release PR (integration -> default branch) when `Release PR: yes`; a person merges it. Post the outbox. Record each result in the ledger (a refusal as a note on the issue's row; every note one run writes for an issue is kept, joined with `; `). A refusal is reported, never forced. `--dry-run` prints what it would do and writes nothing.

## The agents

| Agent | Model | Role |
|---|---|---|
| `software-factory-orchestrator` | opus | The main session for one repo: the loop above. The only writer of the ledger, the manifest and the outbox. |
| `software-factory-triager` | sonnet | Classifies issues under the collection policy (`build`, `ask`, `human`, `skip`) with a reason and, for `ask`, the question. |
| `software-factory-builder` | opus | One issue in one worktree: reproduce, fix, write the PR body. Also answers a PR's CI failures and review comments (babysit mode). |
| `software-factory-tester` | opus | Independent tests for one built branch from the issue and the diff only: acceptance points, edge cases, error paths, a regression test, the running app for visible changes. |
| `software-factory-reviewer` | opus; fable for one-way doors and large diffs | Independent review of one verified branch: correctness against the issue, tests that prove it, code quality, security. PASS or FAIL with fixes. Never edits. |
| `software-factory-lookback` | fable | Weekly: reopened issues, repeated reports, fixes that did not hold; proposes whole-system fixes as issues for a person. |

## The skills

- `orchestration-workstream`: the conduct every workstream of any orchestrator follows and the shared return block; loaded first.
- `software-factory-workstream`: what the factory adds to it (always offline, the repo's way, reproduce first, the agent file's return shape) and this contract.
- `software-verify`: the reproduce-first standard and the sufficient-tests bar (a failing test or recorded command before any fix; each acceptance point, edge cases and error paths tested; the full declared checks after; screenshots for UI; diff coverage when the rules set one).
- `software-review`: what a reviewer checks, including the security pass.
- `software-pr`: branch naming and the pull request body (summary, the issue, the evidence, the risk, how to verify by hand).
- `software-factory-workstream`'s `onboard.md`: write a repo's `.software-factory/` (detect the stack, propose commands, draft the rules) as the repo's first factory pull request.

## Authority

- Agents never hold GitHub credentials and never push, merge, comment or label; `software-factory-ship` does, under its guards.
- Nothing is ever pushed or merged to the default branch. A person merges the release PR.
- A question on an issue the owner did not file or own goes to the owner instead (the outbox marks it `kind: question` and `software-factory-ship` posts only questions on issues the owner policy allows; the rest come back in the session's `for_owner`).
- A comment the factory posts says it is from the factory.
