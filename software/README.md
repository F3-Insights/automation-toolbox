# Software Development

Turns a repository's issues into verified pull requests, and keeps an owner's software portfolio in view. The software factory is the issue loop: `software-orchestrator` works one repository from its GitHub issues, triaging, planning, building and fixing through one worker at a time, with GitHub holding the state, and merges verified agent work into the integration branch only; promotion to production stays with people. Around it sit a release preparer, a weekly portfolio review, an issue harvest that turns what people say about the software into well-formed issues, and the owner-started methods for specs, schema documentation and doc cleanup. This department also holds the two skills every orchestrator in the toolbox uses: `orchestration-workstream` (how any worker behaves and returns) and `orchestrator-scaffold` (how to build a new orchestrator, and the template every agent file follows).

## Bringing up the issue loop

The issue loop (`software-orchestrator` and its workers) is the toolbox's software factory. It replaced an earlier offline factory, retired on 2026-10-11 and kept in git history. It is brought up in three steps. Each step starts only when the one before it works, because the corrections found in an earlier step are the only instructions worth adding.

1. **You are the orchestrator.** In an ordinary Claude Code session in the repository's clone, ask for one job at a time (the prompts below) and watch. Write down only what it gets wrong; those corrections go into the worker prompts. No Sentinel, no orchestrator.
2. **The orchestrator chooses, interactively.** When triage, plan and build each work by hand, run `software-orchestrator` in an interactive session and watch what it picks and delegates. The new question is only whether it chooses well.
3. **Sentinel runs it unattended.** Only once watching is boring. This is when the sealed-session plumbing (tool allowlists, no loaded skills, sub-agent wiring) is worth fixing.

Principles behind it:

- Prove the job by hand before automating it; automate what you find yourself repeating.
- Prompts state goals and principles, not procedures. Add a rule only for a mistake the agent actually made.
- Rules live once, in the design rules (`F3-AGENT`, `F3-BRANCH`, `F3-DOC`); prompts point at them.
- Configuration (schedules, tools, caps) lives in the runner, not in the prompts.

A candidate to bring in later: the retired factory's script-run verification (the repo's declared checks run from the base commit in a clean worktree, and a repro that fails before the fix and passes after it). Its script is in git history.

### Step 1 prompts

Run in Claude Code from the repository's clone. Replace the issue numbers.

**Triage**
> Read this repo's own docs (agent file, README, vision, handoff) and the F3-AGENT rules in the design rules. Then triage issues #16 to #20: for each, decide whether it is ready to build, needs a plan first, needs a question answered, or is blocked; set a type and status label; and leave one short comment saying what it needs next. Create any missing labels.

**Plan**
> Read this repo's docs and the F3-AGENT rules. Write the plan for issue #N as docs/plans/N-slug.md, one page of decisions and risks (goal, approach, decisions, out of scope, verification, size) on branch issue/N-slug, open it as a draft PR labeled ai-agent, and comment on the issue. Then stop for my review.

**Build**
> Read this repo's docs and the F3-AGENT rules. Build issue #N (following docs/plans/N-slug.md if it exists): a failing test first for a bug, the repo's own checks before you finish, and the PR into the integration branch labeled ai-agent, saying how it was verified. Do not merge.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `software-orchestrator` | **Draft.** The software factory. Works one repository from its GitHub issues: one worker at a time, status on the issues, merges into the integration branch only | `gh`, local clone, the design rules (`F3-AGENT`, `F3-BRANCH`) |
| `issue-triager` | Draft. Decides what one issue needs next: ready, plan, a question, or blocked | `gh` |
| `issue-planner` | Draft. Writes `docs/plans/N-slug.md` as a draft PR for the owner to review | `gh`, local clone |
| `issue-builder` | Draft. Builds one ready issue, verifies it and opens the PR | `gh`, repo's checks |
| `pr-fixer` | Draft. Gets one PR back to green: failing checks and review comments | `gh`, repo's checks |
| `pr-reviewer` | Draft. Independent review of a risky PR, PASS or FAIL | `gh` |
| `software-release-orchestrator` | Prepares a repository's next release: notes, PR body, deploy checklist, issues to close | local clone |
| `software-release-writer` | Drafts the release files from the merges in range | local clone |
| `software-release-checker` | Independent check of the release drafts against the clone | none |
| `software-portfolio-review-orchestrator` | Weekly review of every repository: inventory, one steward per repo, one numbered list of next steps | Insights Portal, repo map |
| `repo-steward` | Read-only report on one repository against its own stated direction, with three next steps | `gh`, commands `repo-sweep`, `detect-project-type` |
| `issue-harvest-orchestrator` | Turns harvested source items into decided GitHub issues and comments, each checked | Insights Portal, commands `issue-harvest-sync`, `issue-file` |
| `issue-harvest-analyst` | Decides one batch of items: new issue, comment, duplicate, not software, or a question | Insights Portal |
| `issue-harvest-checker` | Independent PASS or FAIL on each proposed issue or comment | Insights Portal |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `software-issue-loop` | Draft. The issue loop's shared facts and `repo_status.py`, the one-page snapshot the lead reads | `gh` |
| `orchestration-workstream` | Conduct and the one json return block for any orchestrator's worker | none |
| `orchestrator-scaffold` | How to design and build an orchestrator from a spec, with the full design, a worked example, and the agent file standard with its orchestrator and sub-agent templates | command `orchestrator-scaffold` (optional) |
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

**`software-issue-loop`**
- `repo_status.py`: one repository's open issues and pull requests on one page, grouped by status label.

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

- **Issue loop**: `gh`, signed in, and a local clone of the repository; the brief names where the design rules are. It reads no settings file.
- **Issue harvest**: `repos_file` under `[issue-harvest-workstream]` (the repo map) is required; `state`, `horizon_days`, `closed_days`, `public_denylist_files`, `private_terms` and the `sources` sub-tables are optional. It reads the Portal through `portal_mcp_config`, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- **Portfolio review**: `repos_root` under `[software-portfolio-review]`, or a folder argument to `repo_sweep.py`.
- **Scaffold lint**: `F3I_TOOLBOX_DENYLIST` (files of private names, `:`-separated).
- Python 3.11 or later, with `pyyaml`, declared in each script's `# /// script` block.
