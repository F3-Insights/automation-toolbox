# Onboarding a repository (issue 0)

Part of the `software-factory-workstream` skill: read when the factory onboards a repository.

The factory cannot build in a repo until the repo says how to check itself. This skill writes that, on the onboarding branch the orchestrator made (issue 0: branch `software-factory/onboard`, from `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_worktree.py OWNER/NAME --issue 0`), as the repo's first factory pull request. A person reviews and merges it; the factory never does, and nothing is assumed.

## 1. Find the commands

Read, in this order, until the commands are clear:
- the CI workflows (`.github/workflows/*.yml`);
- `CONTRIBUTING`, `CLAUDE.md`, `AGENTS.md` and the README's development section;
- the package files (`pyproject.toml`, `package.json` scripts, `Makefile`, `justfile`, `Cargo.toml`, `go.mod`).

Prefer what CI runs.

## 2. Make them work offline, from a clean worktree

Run each command in the worktree, the way the factory will: no GitHub token, a fresh clone.
- **setup** must create everything the other commands need from nothing: a virtual environment (never install into the system Python; `pip` refuses with "externally-managed-environment"), `npm ci`, build steps.
- **test** must run the real suite. If the suite needs a service (a database, a browser), say so in the rules and use the repo's own test configuration for it. If part of the suite cannot run offline, leave it out of `test` and name it in the rules.
- **lint**, **typecheck**, **build** and **coverage** only when the repo already has them. Add nothing new to the repo's toolchain here.
- **coverage** must leave a report with line data where `software-factory-verify` reads it: `coverage.json` (coverage.py, `coverage json` or `--cov-report=json`), `coverage/lcov.info`, or `coverage/coverage-final.json` (istanbul's `json` reporter), in the command's folder.

A command that does not pass on the integration branch as it stands is a finding for the owner, not something to fix in passing: record it in the rules' "Known failures" and leave it out until it is fixed.

## 3. Write the folder

`.software-factory/commands.yaml`, in the shape `SOFTWARE-FACTORY.md` (in this skill's folder) gives: strings, `{run, cwd}`, or lists.

`.software-factory/SOFTWARE-FACTORY-RULES.md`:
- the field lines:
  - `- Integration branch:` (`development` if it exists, else ask);
  - `- Default branch:`;
  - `- Auto-merge: yes`;
  - `- Release PR: yes`;
  - `- Builds per week: 5`;
  - `- Protected paths:` (migrations, infrastructure, CI workflows, anything holding secrets);
  - `- Minimum diff coverage:` (only if a coverage command exists);
- then the collection policy, the approval policy and the one-way doors, starting from the defaults in `SOFTWARE-FACTORY.md` and adjusted to what this repo is (a public library has a public API; an app with payments has a payment path);
- and "Known failures", if any.

## 4. Prove it

Commit both files, then run `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_verify.py <worktree> --base <base_sha> --commands-from head`, where `base_sha` is the integration branch's commit the worktree started from. `--commands-from head` reads the commands and the rules from the branch's own commit, because the base has none yet; it works only on `software-factory/onboard`. It must say `verified`, with `commands_from` naming the head commit. The orchestrator runs the same command itself before review. Write the PR body (`software-pr`): what each command does, what was left out and why, and the policies chosen.
