# Software Development

Turns a repository's issues into verified, reviewed pull requests without ever shipping a guess, and keeps an owner's software portfolio in view. The software factory triages issues, reproduces each problem before fixing it, tests and reviews every change independently, and leaves pushing and merging to deterministic tools and people. Around it sit a release preparer, a weekly portfolio review, an issue harvest that turns what people say about the software into well-formed issues, and the owner-started methods for specs, schema documentation and doc cleanup. This department also holds the two skills every orchestrator in the toolbox uses: `orchestration-workstream` (how any worker behaves and returns) and `orchestrator-scaffold` (how to build a new orchestrator, and the template every agent file follows).

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `software-factory-orchestrator` | One factory session for one repository: finish open PRs, triage, build, test, verify, review, write what ships | commands `software-factory-*`, local clone |
| `software-factory-triager` | Classifies issues as build, ask, human or skip under the repo's policy | none |
| `software-factory-builder` | Reproduces and fixes one issue in its own worktree; answers PR failures and comments | repo's declared checks |
| `software-factory-tester` | Adds the tests a built branch needs, from the issue and diff only; drives the app for visible changes | repo's declared checks |
| `software-factory-reviewer` | Independent PASS or FAIL review of one verified head commit | none |
| `software-factory-lookback` | Weekly look for recurring bugs, fragile areas, stuck work and policy fit | command `software-factory-check` |
| `software-release-orchestrator` | Prepares a repository's next release: notes, PR body, deploy checklist, issues to close | factory ledger, local clone |
| `software-release-writer` | Drafts the release files from the merges in range | factory ledger |
| `software-release-checker` | Independent check of the release drafts against the clone and ledger | none |
| `software-portfolio-review-orchestrator` | Weekly review of every repository: inventory, one steward per repo, one numbered list of next steps | Insights Portal, repo map |
| `repo-steward` | Read-only report on one repository against its own stated direction, with three next steps | `gh`, commands `repo-sweep`, `detect-project-type` |
| `issue-harvest-orchestrator` | Turns harvested source items into decided GitHub issues and comments, each checked | Insights Portal, commands `issue-harvest-sync`, `issue-file` |
| `issue-harvest-analyst` | Decides one batch of items: new issue, comment, duplicate, not software, or a question | Insights Portal |
| `issue-harvest-checker` | Independent PASS or FAIL on each proposed issue or comment | Insights Portal |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `orchestration-workstream` | Conduct and the one json return block for any orchestrator's worker | none |
| `orchestrator-scaffold` | How to design and build an orchestrator from a spec, with the full design, a worked example, and the agent file standard with its orchestrator and sub-agent templates | command `orchestrator-scaffold` (optional) |
| `software-factory-workstream` | What factory workers add to the shared conduct; carries `SOFTWARE-FACTORY.md`, the factory contract, and `onboard.md`, which writes a repository's `.software-factory/` commands and rules as its first factory PR | command `software-factory-verify` (onboarding) |
| `software-verify` | Reproduce first, the sufficient-tests bar, the repo's own checks, evidence | none |
| `software-review` | What an independent code review checks, in order, and what fails it | none |
| `software-pr` | Branch naming, commits and a PR body a reviewer can act on | none |
| `software-security-knowledge` | OWASP patterns, Supabase, FastAPI and Express checks, severity guide (reference) | none |
| `software-release-workstream` | The release range, files, GitHub drafts and DONE checklist | none |
| `software-portfolio-review` | Map projects to repositories, fan out stewards, file approved next steps | Insights Portal |
| `issue-harvest-workstream` | The five decisions, dedupe rules and the issue standard for the harvest | Insights Portal |
| `software-deep-spec` | Owner-started ten-dimension feature spec, reviewed dimension by dimension | command `detect-project-type` |
| `software-spec-dimensions` | The ten spec dimensions and what each must say (reference) | none |
| `software-db-schema` | Owner-started read-only database introspection into `DATABASE_SCHEMA.md` with drift report | `psql`, command `detect-project-type` |
| `software-clean-docs` | Owner-started doc audit and restructure, executed only for approved groups | none |
| `software-doc-standards` | Target doc structure and quality bar for CLAUDE.md, README and docs/ (reference) | none |
| `software-diagnose-bugs` | Diagnosis loop for hard bugs and slowdowns: a tight red-capable loop first, then reproduce, hypothesise, instrument, fix with a regression test | none |
| `software-grill-with-docs` | Grills a plan against the domain glossary and ADRs, updating CONTEXT.md and docs/adr/ inline | none |
| `software-improve-architecture` | Finds deepening opportunities in a codebase and grills the chosen one into a design | none |

Used by name from other departments: `task-stack-workstream`, `task-stack-apply`, `portal-write-safety` and `comms-confirm` (productivity). For bug diagnosis, use `software-diagnose-bugs`.

`software-diagnose-bugs`, `software-grill-with-docs` and `software-improve-architecture`, and parts of `software-deep-spec`, are adapted from mattpocock/skills under the MIT License; see [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed. The three `.sh` scripts run with `bash` the same way.

**`software-factory-workstream`**
- `software_factory_sync.py`: takes the snapshot of one repository before a session, or prechecks it.
- `software_factory_worktree.py`: creates or reuses one issue's worktree and branch from the local clone, offline.
- `software_factory_verify.py`: runs the base commit's declared checks in a worktree, offline, and writes `verify.json`.
- `software_factory_record.py`: upserts one row of the repository's factory ledger.
- `software_factory_check.py`: where each issue of a repository stands in the factory.
- `software_factory_ship.py`: applies a session's manifest and outbox to GitHub, under the guards.

**`issue-harvest-workstream`**
- `issue_harvest_sync.py`: gathers a Run's source items and each repository's issues before the session, read only.
- `issue_file.py`: files the Run's decided issues and comments on GitHub, the one writer, after the session.
- `issue_harvest_record.py`: records each queued item's outcome in the harvest ledger.
- `issue_harvest_check.py`: whether the harvest is done, from its ledger, the Portal and GitHub.

**`software-portfolio-review`**
- `repo_sweep.py`: the health of every git repository under a folder, in one table.
- `detect_project_type.sh`: describes one project (language, framework, test command) as one JSON object.

**`orchestrator-scaffold`**
- `orchestrator_scaffold.py`: generates a new orchestrator's files from a spec, and lints an existing one.

**`software-deep-spec`**
- `find-spec-dir.sh`: finds or creates the spec folder and prints the new spec's file name.

**`software-db-schema`**
- `detect-db-type.sh`: detects the database type and connection method from a project's files.

`task_stack_apply.py` (portfolio approve pass) lives in `task-stack-workstream` (productivity). Planned but not yet built: `release-snapshot`, `release-ship`, `release-check`, `portfolio-check`.

### Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Factory**: `repos_dir` under `[software-factory-workstream]` (or `SOFTWARE_FACTORY_REPOS_DIR`), the folder of local clones, is required. The ledger lives under `SOFTWARE_FACTORY_STATE_DIR`, else `<state_dir>/software-factory`, else `~/.local/state/software-factory`. `gh` with its own login does the GitHub reads and the ship step; `GH` names another program.
- **Issue harvest**: `repos_file` under `[issue-harvest-workstream]` (the repo map) is required; `state`, `horizon_days`, `closed_days`, `public_denylist_files`, `private_terms` and the `sources` sub-tables are optional. It reads the Portal through `portal_mcp_config`, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- **Portfolio review**: `repos_root` under `[software-portfolio-review]`, or a folder argument to `repo_sweep.py`.
- **Scaffold lint**: `F3I_TOOLBOX_DENYLIST` (files of private names, `:`-separated).
- Python 3.11 or later, with `pyyaml`, declared in each script's `# /// script` block.
