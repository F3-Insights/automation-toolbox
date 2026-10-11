---
name: software-portfolio-review
description: "Reviews every software project that has a repository, or should have one: finds the project-to-repository mapping, dispatches one software-worker per repository in parallel to steward it (section Steward one repository), and returns one numbered list of proposed next steps per repository. On approval it files the chosen steps as Portal tasks and gives the owner the exact pipeline invocation for each. It starts no pipeline and writes no code. Use for \"where do my repos stand\"; the weekly Run is software-portfolio-review-orchestrator. For a client's project portfolio, use tech-portfolio-orchestrator."
argument-hint: "[domain or project, or blank for every software project] [--repos <owner/name>,...]"
allowed-tools: Agent, Bash, Read, mcp__insights-portal__whoami, mcp__insights-portal__list_entities,
  mcp__insights-portal__hierarchy, mcp__insights-portal__get, mcp__insights-portal__search,
  mcp__insights-portal__create_task, mcp__insights-portal__update_project
---

# Software portfolio review

The portfolio question the Portal cannot answer on its own: for each piece of software work the owner is carrying, where does the repository actually stand, and what is the next thing to do in it. One `software-worker` per repository, following the section Steward one repository below, answers the second half; this skill finds the repositories, merges the answers, and turns the owner's decisions into tracked work.

It starts no pipeline. The issue loop (`software-orchestrator`), `software-deep-spec` and a bug-diagnosis skill write code, comment on issues and open pull requests, and they are owner-invoked by design. This skill hands the owner the exact invocation and stops.

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

Dispatch one `software-worker` per repository, **all in one message**, capped at eight. Beyond eight, run the highest-priority eight first, report, and say plainly which repositories were not read in this pass and that they need a second run.

```
Agent(
    subagent_type="software-worker",
    description="Steward <owner>/<name>",
    prompt="""
Follow the software-portfolio-review skill, section Steward one repository.

Repository: <owner>/<name>
Local path: <the path: line, or "no local checkout; use the gh half only">
Portal project: <project name and uuid>, in domain <domain>

Return the report that section gives: the vision-and-architecture paragraph, where the repository
stands against it, the three next steps in order, issues grouped by readiness with the
pipeline each group suits, pull requests and failing runs, housekeeping risks, and the
could-not-determine list.
"""
)
```

Each steward is read-only by that section's command list: read-only `git` and `gh`, plus `software-repo-sweep` and `software-detect-project-type`, and nothing that writes. A steward that returns `BLOCKED:` read nothing; relay its question in Step 3 and move on.

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

- `claude --agent software-orchestrator` with "work the issues on OWNER/NAME: #<n>, #<n>", or that repository's scheduled issue-loop run if it has one, for the issues the steward called ready to work
- `/software-deep-spec "<the feature, in the steward's words>"` for one that needs a specification first
- `software-diagnose-bugs` for one that needs a diagnosis first
- for work that is not an issue yet, filing it as an issue with a clear expected behaviour, so the issue loop can take it up
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

Before each call, keep the Portal's write rules: propose by default and write only what the owner confirmed; call `sync_health` first and say what may be missing when sync is stale; resolve every record by UUID, never by name; strip the U+2028 line separator from any text you send.

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

`software-portfolio-review-orchestrator` runs this review weekly, unattended, on a schedule. It does Steps 1 to 3 as written, adds the inventory and issue-loop sections below, and writes the numbered list to the Run folder instead of asking. Step 4 becomes its approve pass: with the owner's answers as the launch's `answers` input, it writes the approved tasks as a change set (`RUN/changes.json`, below), and the Automation's finish step applies it with the owner's task-stack writer (`task-stack-apply`, outside this plugin). It never calls a Portal write tool. Its session is offline (no route to GitHub), so the stewards read the local clones only until portfolio-check snapshots GitHub's pull requests, issues and CI before the session.

- **Inventory.** Three lists reconciled into one table: local clones under the repos folder, the repo map, and the Portal's software projects. A repository in one list only, a map `status` that the activity contradicts (a `retire` repository with commits this month, an `active` one untouched for ninety days), and a local folder with no git are findings.
- **Issue-loop health.** For each repository the issue loop works, from the local clone: `issue/N-slug` branches not yet merged into the integration branch and how old they are, and an integration branch far ahead of the default branch with no release in sight. The rest of the loop's state is on GitHub (status labels and `ai-agent` pull requests) and waits for portfolio-check's snapshot.
- **Cap.** Stewards are dispatched eight per message, active repositories first, up to the launch's `max_repos`; the rest are named as not read.

### The orchestrator's steps

1. Run `whoami`. Read the repo map. On an approve pass: read the last Run's `review.md`, write `RUN/changes.json` with one `create` op per approved number, and go to step 6.
2. Build the inventory (Step 1 plus the inventory above): local clones by `Glob`, the map, the Portal's software projects. Write `RUN/inventory.md`.
3. Dispatch one `software-worker` per active repository, eight per message, up to `max_repos`, each told to follow the section Steward one repository, with its path, `owner/name` and Portal project, and the line "offline: no gh; read the local clone only, and list GitHub's half under Could not determine". Save each report to `RUN/stewards/<name>.md`.
4. For the repositories reviewed, list with `git -C` the `issue/N-slug` branches not merged into the integration branch and their age; note stalled work.
5. Write `RUN/review.md`: per repository the steward's reading and housekeeping line, then the numbered list across all of them with the exact invocations; then the repositories not read and the inventory findings.
6. Walk the DONE checklist into `RUN/done.md`, each line with its evidence.

### The change set

The approve pass writes `RUN/changes.json` in the task-stack change-set shape, using only `create` ops:

```json
{"tool": "task-stack-changes", "version": 1, "orchestrator": "software-portfolio-review-orchestrator",
 "dry_run": false,
 "ops": [
  {"id": "n1", "op": "create", "title": "Fix the failing nightly build", "project": "<project id>",
   "due_date": "2030-03-10", "evidence": "RUN/stewards/<name>.md", "reason": "Approved as item 3 of the review"}],
 "questions": [], "notes": []}
```

- `dry_run` is the session's own mode, always a boolean; a dry run's change set is never applied for real.
- Op `id`s are unique in the set; `reason` is one line a person reads on the task.
- A `create` needs a verb-first title under 100 characters, a project (or `domain` for its catch-all project), and no open task in that project that is already it. The description carries why now, the steward's evidence and the exact invocation; `due_date` and `priority` only where the owner gave them.

### DONE checklist

1. Every repository in the three lists has a row in the inventory table with its sources.
2. Every active repository up to the cap has a steward report, or its BLOCKED line.
3. Every repository not read is named, with why.
4. Every proposal in the numbered list carries the steward's evidence and the invocation.
5. On an approve pass, every approved number is one op in `RUN/changes.json` and nothing else.
6. Nothing was committed, pushed, merged or started, and no pipeline was launched.

### Later tools

- portfolio-check (prepare) and `--precheck`: the inventory in code (local clones, the map, GitHub's repo lists, the Portal's `repositories` field) with dirty-file and ahead counts, and a snapshot of each repository's open pull requests, issues and CI for the offline stewards.
- The finish step's `task-stack-apply` (kept with the owner's task-stack tools, outside this plugin) for the approve pass.

## Steward one repository

For a `software-worker` given one repository: read it and report where it stands against its own stated direction. One repository per worker, because other workers are reading other repositories at the same time. You change nothing, you start nothing, you report.

### The command rule, which is hard

Bash is for read-only inspection of this repository only. The commands you may run are these and nothing else: `git status`, `git log`, `git branch`, `git worktree list`, `git diff --stat`, `git remote -v`, `gh issue list`, `gh issue view`, `gh pr list`, `gh pr view`, `gh run list`, `gh workflow list`, `gh repo view`, `software-repo-sweep`, `software-detect-project-type` and `ls`.

Point every `git` call at the repository with `git -C <path>`. Flags that only narrow or format the read are fine (a revision range, a date limit, `--json`, `-n`, `--format`, a path filter); a flag that names a ref to move to or a file to write never is. Never run push, commit, checkout, switch, reset, revert, clean, merge, rebase, stash, tag, fetch or pull; no `gh` command that creates or edits anything (issues, pull requests, workflow runs, releases, settings); no file written, nothing installed, not the repository's tests or build, and no command whose effect you would have to guess at. If the work needs a forbidden command, say so in the report and stop there. `software-repo-sweep` reports the health of every git repository under a folder and never fetches; `software-detect-project-type` prints one JSON object (language, framework, package manager, test runner, start and test commands) and writes nothing.

When the brief says offline, run no `gh` at all: read the local clone and list GitHub's half under Could not determine. Where `gh` is not signed in or the repository has no GitHub remote, say so once and carry on with the local half.

### What you read, in order

1. **The repository's own account of itself.** Whichever of these exist, at the root and one level down (find them with `Glob`): `README` in any extension, `CONTEXT.md`, `STATUS.md`, `DESIGN.md`, `CLAUDE.md`, and every file under `docs/adr/`, newest first (a decision stays in force until a later one supersedes it by number). Write one paragraph stating the vision and the architecture in the repository's own vocabulary: what it is for, who uses it, the shape it is built in, and the decisions that constrain what may change. A repository with none of these files gets a paragraph saying so, which is itself the most important finding.
2. **The working tree.** `git -C <path>` `status --porcelain`, `log --oneline -15`, `branch -vv`, `worktree list`, `remote -v`, `diff --stat`. Report uncommitted and untracked files, commits ahead of the upstream, whether there is an upstream at all, branches with no commit in sixty days, and worktrees on disk.
3. **Open issues, by readiness.** `gh issue list --limit 100 --json number,title,labels,updatedAt,comments`, and `gh issue view <n>` on the ones that matter. Put each open issue in exactly one group: **Ready to work** (problem, expected behaviour and acceptance stated, no open question); **Needs a specification first**; **Needs a diagnosis first** (broken or slow, no reproduction or cause); **Needs a decision from the owner** (say the question); **Stale** (no movement in ninety days, nothing depends on it).
4. **Pull requests and runs.** `gh pr list --limit 50` and `gh run list --limit 20`: open pull requests with their age and blocker, failing or repeatedly failing runs. A failing run on the default branch outranks almost everything else.

### What you return

```
## <repository name>

### Where it stands against its stated direction
<the paragraph, then two or three sentences on whether the current state matches it and where it has drifted>

### The three next steps, in order
1. <the step> · <why it is first> · <the skill or command that does it>
2. ...
3. ...

### Issues by readiness
| # | Title | Readiness | Note |

Ready to work: hand these to the issue loop (`software-orchestrator`): #<n>, #<n>
Need a specification first, via `software-deep-spec`: #<n>
Need a diagnosis first, via `software-diagnose-bugs`: #<n>
Need a decision from the owner: #<n>, and the question is <the question>

### Pull requests and runs
<open PRs with age and blocker; failing runs with the workflow and the branch>

### Housekeeping risks
<uncommitted work, unpushed commits, no remote, stale branches, abandoned worktrees, each with what is at risk>

### Could not determine
<what a reader will expect you to have answered and you could not, and why>
```

Exactly three next steps; ordering them is the judgment you are there for, so if the third is weak, say the repository has two. Quote the repository's vocabulary, not your own. Say when documentation is absent or stale (a `STATUS.md` six months older than the last commit is a finding). You never start a pipeline: you name which issue suits which one. If the brief names two repositories, report the first and say the second needs its own worker. You cannot ask a question: return `BLOCKED:` followed by the question and stop.
