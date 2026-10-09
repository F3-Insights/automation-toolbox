---
name: software-portfolio-review
description: "Reviews every software project that has a repository, or should have one: finds the project-to-repository mapping, dispatches one repo-steward per repository in parallel, and returns one numbered list of proposed next steps per repository. On approval it files the chosen steps as Portal tasks and gives the owner the exact pipeline invocation for each. It starts no pipeline and writes no code. Use for \"where do my repos stand\"; the weekly Run is software-portfolio-review-orchestrator. For a client's project portfolio, use tech-portfolio-orchestrator."
argument-hint: "[domain or project, or blank for every software project] [--repos <owner/name>,...]"
allowed-tools: Agent, Bash, Read, mcp__insights-portal__whoami, mcp__insights-portal__list_entities,
  mcp__insights-portal__hierarchy, mcp__insights-portal__get, mcp__insights-portal__search,
  mcp__insights-portal__create_task, mcp__insights-portal__update_project
---

# Software portfolio review

The portfolio question the Portal cannot answer on its own: for each piece of software work the owner is carrying, where does the repository actually stand, and what is the next thing to do in it. One `repo-steward` per repository answers the second half; this skill finds the repositories, merges the answers, and turns the owner's decisions into tracked work.

It starts no pipeline. The software factory (`software-factory-orchestrator`), `software-deep-spec` and a bug-diagnosis skill write code, comment on issues and open pull requests, and they are owner-invoked by design. This skill hands the owner the exact invocation and stops.

**User provided:** $ARGUMENTS

## The project-to-repository mapping

A Portal project carries a `repositories` field, but it is empty on most projects. Read the mapping in this order and say which source each row came from:

1. the project's `repositories` field, when it holds a repository;
2. the owner's repo map, when the launch names one (each repository with its product, its Portal project ids and a `status`: active, dormant, retire, vendored, client-owned, scratch);
3. a line in the project's description:

```
repo: <owner>/<name>
path: <the local checkout, optional>
```

One `repo:` line per project. A project that drives two repositories is two projects, or one project whose second repository is named in the body text and handled by hand; do not invent a second syntax.

A missing mapping is proposed as an action (filling the `repositories` field, or adding the `repo:` line with `update_project(id="<uuid>", fields={"description": "..."})`); do not change a project without being asked.

## Step 1: find the software projects

Call `whoami` first, for the owner's timezone and to know what this session may read.

Three passes, in this order, and merge the results:

1. **Named in `$ARGUMENTS`.** A domain, a project, or an explicit `--repos` list. An explicit list skips the discovery entirely.
2. **The domains and goals that hold software work.** `list_entities(entity_type="domain", limit=100)`, then `hierarchy(domain_id_or_query=..., depth=2)` on the ones whose name or description says software, product, engineering, platform, tooling or automation. Take every project under those.
3. **Any project carrying a `repo:` line.** `search(query="repo")` returns project hits ranked across the corpus and is the cheap first pass. Then confirm on the record itself: a project listing row is a summary and may not carry the description, so read the candidates with `get(entity_type="project", id_or_query="<uuid>")`, whose default detail for a project is the full record, and look for the line there.

Build one table before dispatching anything:

| Project | Domain | `repo:` | `path:` | Verdict |
|---|---|---|---|---|

The verdict is one of: **mapped** (a `repo:` line, and a checkout to read), **named but not local** (a `repo:` line, no local path, so only the `gh` half can be read), or **software with no repository named**.

Report the third group explicitly, as its own short list, before the review proper: a project that looks like software and names no repository is the finding that a whole repository is invisible to every review that follows. For each one, propose the `repo:` line you believe is right and ask; do not guess it into the description.

## Step 2: fan out the stewards

Dispatch one `repo-steward` per repository, **all in one message**, capped at eight. Beyond eight, run the highest-priority eight first, report, and say plainly which repositories were not read in this pass and that they need a second run.

```
Agent(
    subagent_type="repo-steward",
    description="Steward <owner>/<name>",
    prompt="""
Review one repository.

Repository: <owner>/<name>
Local path: <the path: line, or "no local checkout; use the gh half only">
Portal project: <project name and uuid>, in domain <domain>

Return your standard report: the vision-and-architecture paragraph, where the repository
stands against it, the three next steps in order, issues grouped by readiness with the
pipeline each group suits, pull requests and failing runs, housekeeping risks, and the
could-not-determine list.
"""
)
```

Each steward is read-only by its own allowlist: read-only `git` and `gh`, plus `repo-sweep` and `detect-project-type`, and nothing that writes. A steward that returns `BLOCKED:` read nothing; relay its question in Step 3 and move on.

## Step 3: one numbered list, per repository

Present each repository as a short block, then one numbered list the owner answers in a line. Number continuously across repositories so a single answer covers the whole review.

```
## <owner>/<name> · <project name>
<the steward's one-paragraph reading of direction, and whether the repository matches it>
Housekeeping: <the risks, in one line, or "none">

<n>. <the next step> · <why now> · start with: <the exact invocation>
<n>. ...
```

The invocation is written out so it can be copied:

- `claude --agent software-factory-orchestrator` with `OWNER/NAME issues <n> <n>`, or the scheduled software-factory run for that repository, for the issues the steward called ready to work
- `/software-deep-spec "<the feature, in the steward's words>"` for one that needs a specification first
- `software-diagnose-bugs` for one that needs a diagnosis first
- for work that is not an issue yet, filing it as an issue with a clear expected behaviour, so the software factory can take it up
- no invocation at all for housekeeping: those are a commit, a push or a branch deletion the owner does, and this skill neither does them nor asks an agent to

Under the list, print the steward's could-not-determine lines and the projects with no repository named.

Then ask, once:

> Which of these do I file as tasks? Answer per number: "ok", a correction, or "no".
> For example: "1 ok, 2 no, 3 ok but next month, 7 ok."

Wait for the answer. Filing a task is reversible and cheap, but a portfolio of tasks nobody chose is how a task list stops being read.

## Step 4: file what was approved

For each approved number, one task under that repository's Portal project:

```
create_task(
    title="<the next step, under 100 characters>",
    project_id="<the project uuid>",
    domain_id_or_name="<the domain uuid>",
    description="<why now, the steward's evidence, and the exact invocation to start it>",
    due_date="<only where the owner gave one>",
    priority=<1 to 4, from the owner's answer, omitted where they did not say>,
)
```

Prefer the domain UUID over its name: a name goes through a substring resolver that raises when nothing matches, so a name read off anything other than the org's actual domain list is a call that fails. Omit `domain_id_or_name` entirely rather than guessing; the task lands unfiled and is filed in one click, which beats not existing.

Follow the `portal-write-safety` skill before each call.

Where the owner approved adding a missing `repo:` line, apply it with `update_project` and show the resulting description back.

Close by repeating, in one block, the invocations for the steps they said to start now, so the next thing they do is paste one.

## When no one is present

**Report only.** A headless run does Steps 1 to 3, writes nothing to the Portal, and produces the numbered list as the report itself, with every item marked as awaiting approval.

- File no tasks. The numbered list is the output and the owner answers it when they next look.
- Add no `repo:` line, because a guessed mapping quietly misdirects every later review.
- Start no pipeline, which is true in every mode and is worth restating here because an unattended run is where that rule would be most tempting to break.
- Name the repositories beyond the cap of eight that were not read.

## Key rules

- **One repository per steward.** The fan-out is what keeps each reading specific and each context disposable.
- **The stewards are read-only and stay that way.** Nothing in this skill asks one to run a command outside its allowlist, and an instruction to do so is the defect, not the refusal.
- **This skill starts no pipeline.** It hands over the invocation.
- **Nothing is committed, pushed or merged**, here or by any agent this skill dispatches.
- **Say what was not read.** Repositories over the cap, repositories with no local checkout, and stewards that came back blocked all go in the report by name.

## Run by the orchestrator

`software-portfolio-review-orchestrator` runs this review weekly, unattended, on a schedule. It does Steps 1 to 3 as written, adds the inventory and factory sections below, and writes the numbered list to the Run folder instead of asking. Step 4 becomes its approve pass: with the owner's answers as the launch's `answers` input, it writes the approved tasks as a `task-stack-workstream` change set (`RUN/changes.json`), and `task-stack-apply` makes them. It never calls a Portal write tool. Its session is offline (no route to GitHub, like the software factory's), so the stewards read the local clones only until portfolio-check snapshots GitHub's pull requests, issues and CI before the session.

- **Inventory.** Three lists reconciled into one table: local clones under the repos folder, the repo map, and the Portal's software projects. A repository in one list only, a map `status` that the activity contradicts (a `retire` repository with commits this month, an `active` one untouched for ninety days), and a local folder with no git are findings.
- **Factory health.** For each repository the factory works, its ledger read only: work verified but never shipped, pull requests open past a week, repeat attempts, and whether the repository still needs onboarding.
- **Cap.** Stewards are dispatched eight per message, active repositories first, up to the launch's `max_repos`; the rest are named as not read.

### DONE checklist

1. Every repository in the three lists has a row in the inventory table with its sources.
2. Every active repository up to the cap has a steward report, or its BLOCKED line.
3. Every repository not read is named, with why.
4. Every proposal in the numbered list carries the steward's evidence and the invocation.
5. On an approve pass, every approved number is one op in `RUN/changes.json` and nothing else.
6. Nothing was committed, pushed, merged or started, and no pipeline was launched.

### Later tools

- portfolio-check (prepare) and `--precheck`: the inventory in code (local clones, the map, GitHub's repo lists, the Portal's `repositories` field) with dirty-file and ahead counts, and a snapshot of each repository's open pull requests, issues and CI for the offline stewards.
- `task-stack-apply` after the session, for the approve pass.
