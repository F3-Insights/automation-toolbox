# Orchestrator, agent, skill, tool: the design

How recurring professional work (a month-end close, a forecast, a periodic report, an audit preparation, a software factory) is built so that agents do it, people stay in control, and any session can pick up where the last one stopped. The month-end close is the worked example throughout; every name in it is generic, and nothing here is specific to a client or a machine.

Read this before building a new orchestration. Read it again before changing one.

Two orchestrations follow it in this toolbox:
- the month-end close (`month-end-orchestrator`), the worked example below;
- the software factory (`software-factory-orchestrator`), whose contract is `SOFTWARE-FACTORY.md` in the `software-factory-workstream` skill.

Where they differ is instructive. The close's system of record (the ERP) is only read, and a person posts. The factory's system of record (GitHub) is written, but only by deterministic tools that run before and after the agent session (the launcher's prepare and finish steps). The session itself has no route to it at all.

## The idea in one paragraph

The work runs like a team, not a script. A shared **engagement folder** holds the facts, the rules and the state, in plain files a person can read and edit. An **orchestrator** agent holds the goal and the definition of done, decides what to do next, dispatches **workstream** agents that own parts of the work, has every result checked by an independent **reviewer**, and records everything back in the folder. **Skills** carry the professional standard for a kind of work; **tools** do everything that must be exact. A **launcher** (a person at the command line, or a scheduler) starts the orchestrator, refreshes its data first, fences what it may touch, and keeps a record of what happened. Questions for people go through one channel to the owner's task list. Done is computed from evidence, never claimed.

## The layers

| Layer | What it is | What it owns | Month-end example |
|---|---|---|---|
| Engagement folder | Plain markdown and data files in the client's shared folder | Facts, rules, procedures, and each period's state and evidence | `Month-End/` with `MONTH-END-RULES.md`, `MONTH-END-PROCEDURES.md`, `{yyyy}/{yyyy-mm}/` |
| Orchestrator | An agent run as the main session | The goal, the plan, the dispatches, the records, the definition of done | `month-end-orchestrator` |
| Workstreams | Agents dispatched by the orchestrator | A slice of the work (accounts, checklist rows) and the judgment in it | `month-end-cash`, `month-end-ar-billing-revenue`, `month-end-accruals` |
| Reviewer | An agent, independent of the maker | Checking every result before it counts | `month-end-reviewer` |
| Keeper | An agent for housekeeping | Setting up a period, curating the folder, recording learned facts | `month-end-keeper` |
| Shared skills | Skills loaded by the agents | The method and standard for a kind of work, and the conduct every workstream shares | `orchestration-workstream`, `month-end-workstream`, `month-end-reconciliation`, `month-end-journal-entry` |
| Tools | Scripts in the owning skill's `scripts/` folder, run by path | Everything that must be exact: pulling, computing, linting, writing controlled formats, checking done | `month-end-pull`, `month-end-check`, `month-end-record`, `je-import`, `trial-balance` |
| Launcher | A scheduled task or a person's command line, kept in the owner's private settings | Launching, refreshing data first, the permission fence, the schedule, the record of Runs | a weekday `month-end` schedule |
| People channel | `comms-confirm`, relayed to the owner | Every question to a person, tracked until answered | the period's `CONFIRMATIONS.md` and the Waiting on table |

## Principles

1. **Goal over steps.** An orchestrator and a workstream are told the outcome, the standard and the definition of done, not a script. Frontier models are good at finding what is missing; let them. Precision comes from tools and the reviewer, not from longer prompts.
2. **Generic agents, specific folder.** No agent, skill or tool names a client, a person, an account number or a machine path. Everything specific lives in the engagement folder (facts, rules, procedures), the launcher (paths, permissions) or the owner's settings file. The toolbox could be published and expose nothing about the owner, the owner's family, clients or colleagues. A check that scans every file for private names, secrets and home-directory paths enforces it.
3. **Done is computed.** A tool decides from the folder and the system of record whether each test of done holds. An agent's claim of success is a claim.
4. **Evidence for everything.** Every item that counts toward done has a row in the period's evidence file: its state, the file or ledger reference that proves it, the amount it tied to, and the reviewer's verdict.
5. **People are peers.** Some work stays with people. Every agent checks "is this already done?" before acting, records the person's evidence, and moves on.
6. **Maker and checker are different agents.** The reviewer gets the work product and its sources, never the maker's reasoning, and never edits what it reviews.
7. **Authority is enforced twice.** The tool fence (what an agent can run, enforced by Claude Code and the launcher) and the rules file (what it may do, followed by the agent). Any write to a system of record goes through a deterministic tool built for exactly that write.
8. **One writer of state.** Only the orchestrator writes the period's STATUS, LOG, procedures copy and evidence file. Workstreams return; the orchestrator records. Parallel work then cannot overwrite itself.
9. **Every session can resume.** The orchestrator logs before and after each dispatch, and records each return at once. A session that dies mid-way loses at most one dispatch.
10. **Data before judgment.** The system-of-record pull is refreshed by a tool before the agent starts, not when the agent decides to. A failed refresh is reported, never hidden.
11. **One channel to people.** Questions go on the owner's task list through `comms-confirm`. No agent sends to a client, vendor or colleague directly.
12. **Learn from corrections.** When a person changes what an agent drafted, the difference is found by a tool, explained by the orchestrator, and turned into a proposed change to the folder's maps or rules, so the next period needs fewer questions.

## The engagement folder

### Root: the standing documents

| File | Holds | Who changes it |
|---|---|---|
| `<WORK>-RULES.md` | Authority by system, thresholds and tolerances, the definition of done, naming, how questions are asked | The owner only. Agents propose at the end of the period's STATUS.md. |
| `<WORK>-PROCEDURES.md` | `## Phases` (the workstreams, in order); `## Checklist` (task, workstream, owner, due, done-check, authority); the inventory the work must cover (for a close, `## Balance-sheet accounts` by workstream) | The owner; the keeper records a learned fact with its source |
| `BACKGROUND.md` | The entity, the people and their roles (`- Controller: Name <address>`), the calendar, holidays | The keeper, from answered questions |
| `SYSTEMS.md` | Systems, how data comes out, where inputs land; field lines tools read | The keeper |
| `METADATA_FIELDS.md` | Accounts, dimensions, coding rules, maps the tools read | The keeper; a workstream proposes |
| `STATUS.md` | The handoff: `Current period`, phase, open items, Waiting on summary, next action | The orchestrator |

`<WORK>` is the work's name in capitals (`MONTH-END`, `FORECAST`), so the files say what they are when someone opens the folder.

### Each period: `{yyyy}/{yyyy-mm}/`

| Path | Holds |
|---|---|
| `STATUS.md` | `## Phases` (one row per workstream: not started, in progress, waiting, done) and `## Waiting on` (`Id, Phase, Question, Asked of, How, Asked at, State, Answer, Answered at`) |
| `LOG.md` | One entry per session and dispatch, headed `## yyyy-mm-dd HH:MM by WHO`, with `- Done:`, `- Files:`, `- Decisions:`, `- Open:` |
| `<WORK>-PROCEDURES-{yyyy-mm}.md` | This period's copy of the checklist, due days as dates, with Status and Evidence columns |
| `<WORK>-EVIDENCE-{yyyy-mm}.csv` | `id,test,item,state,evidence,amount,pull_date,review,review_file,note,updated_at,by`; written only by the record tool |
| `CONFIRMATIONS.md` | Every question asked of a person, and the answer |
| work-product subfolders | For a close: `journal-entries/`, `reconciliations/`, `reporting/` (findings, review notes, package) |
| `work/source/` | The read-only pull, with `pulled.md` (date, counts, server totals, gaps, PRELIMINARY or not); superseded pulls kept under `superseded-<stamp>/` |

Nothing is ever deleted. A corrected file is a new file with ` v2`. A person's file is never edited; an agent writes its own beside it.

### Working folder and delivery folder

Where work happens and where finished work goes are often different places. The engagement folder above is the **working folder**: the agents' state, logs, pulls, drafts and review notes, usually in the owner's own storage. The client's team usually has its own shared folder, the **delivery folder**, where final work products live and the team uses them.

- Both are facts of the engagement, written in its documents, never in a skill or agent: `SYSTEMS.md` names the delivery folder and describes its layout as the team keeps it; the rules file says what agents may do there; the procedures carry a checklist row for each kind of final ("save each reviewed final reconciliation to the team folder's ...").
- Only reviewed finals go to the delivery folder, each as a new file, following the team's own layout and naming. Drafts never go there. Nothing there is replaced, edited, moved or deleted.
- The team's own workbooks (a reconciliation that rolls forward through the year) are read from the delivery folder; the agent's rolled-forward version is a new file.
- The launcher grants read and write access to both folders. A permission fence usually cannot say "create only"; the rules file does, and the reviewer checks it.

Changing where things go is a change to the engagement's documents (and, for a new path, to the launcher's permissions), never to the agents.

## Building the pieces

Build from the bottom up: tools first, then the shared skills, then the workstreams, then the orchestrator, then the launcher. Each layer is useful and testable without the ones above it.

A build is not done while the private-name check fails. Fix the file, not the check's allowlist: a client or person becomes a role or the made-up Acme Components, a folder or address becomes an input or an owner setting, and genuinely private material moves out of the toolbox with a pointer left behind.

### Tools

A tool is a command for anything that must be exact or repeatable: reading a system, computing a number, checking a file, writing a controlled format, deciding done.

- Tests use a made-up company (Acme Components). A command is a script in the `scripts/` folder of the skill that owns it, and every caller, a scheduler included, runs it by path (`python3 ~/.claude/skills/<skill>/scripts/<command>.py`); a step naming a path that does not exist fails as "not found".
- `--help` documents it; `--format json` for agents, text for people.
- Exit codes: 0 when it ran (whatever it found), 1 when a check it exists to make fails, 2 for a bad argument. A tool a scheduler runs exits 0 on a soft problem and says so on its first line (`FRESH: ...` / `STALE: ...`, `WORK: ...` / `NOTHING: ...`).
- Reads its settings from the engagement folder (`SYSTEMS.md` field lines, `METADATA_FIELDS.md` tables), never from its own code.
- Read-only toward systems of record by default. A tool that writes to one does exactly one kind of write, in the safest state the system offers (a draft), and is the only way agents make that write. Credentials are found the tool's documented way and never printed.
- Never overwrites: refuses, or keeps the old file beside the new.

**The check tool.** Every orchestration has one, named `<domain>-check`:

```
<domain>-check SCOPE [--format text|json] [--precheck]
```

- `SCOPE` is what the check is about: the engagement folder (`python3 ~/.claude/skills/month-end-workstream/scripts/month_end_check.py FOLDER`), a repository (`python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_check.py OWNER/NAME`), or whatever the domain's unit of work is. Further options narrow it (`--period`, `--sync`).
- Without `--precheck` it reports each test of done: text for a person, `--format json` for the orchestrator.
- With `--precheck` its first line is `WORK: <reason>` or `NOTHING: <reason>`, for a scheduler's heartbeat; detail lines may follow, indented.
- Exit 0 whenever it ran, whatever it found; 2 on a bad argument or a missing scope.

**The evidence ledger.** Every record tool writes its domain's evidence file through the ledger helper in its own skill's `scripts/_common.py`. There is no shared library: a skill that needs the ledger carries a short copy of it (ADR 0002), and a fix to one copy is made to the others on purpose. The ledger is a CSV with declared columns and an id column, and it guarantees:
- upsert by id, where fields not given keep their recorded value, and no row is ever deleted;
- an atomic write that keeps every other row byte for byte, CRLF and byte-order mark included;
- validation hooks: the allowed states, optionally per kind of item, and a callable for the domain's own rules;
- a review that never outlives the work it passed: a change to a work field (state, evidence, amount, head SHA) without a new review clears the review fields.

The record tool keeps the domain parts: its columns, its id (`<test>:<item>`, `<issue>:<attempt>`), its CLI and its warnings.

### Skills

A skill is the method and standard for a kind of work: what good looks like, the checks a professional makes, the files it produces and how they are named. It is shared by every agent that does that kind of work.

- `<department>/skills/<name>/SKILL.md` with frontmatter `name`, `description` (what it does and when to use it, in words a router can match), `argument-hint`, `allowed-tools`.
- Goal-led prose for judgment work: the standard, then the work, then the file. Use a tagged `## Steps` contract (`N. [script|judgment|hand-off|ask] text`, branch lines `→ condition: destination`) only for a fixed procedure with real branches.
- An `## Inputs` section when a person or a scheduler launches it directly: a launch form can be built from it.
- No client facts. A skill names the folder sections it reads; the folder holds the values.
- A companion `rules.md` for a contract too long for SKILL.md (formats, outcome tables). Scripts in `scripts/`, standard library, called by full path.
- `orchestration-workstream` is a special shared skill: the conduct every workstream of any orchestrator follows and the one json return block. A domain extends it with a thin skill of its own that holds only what is specific to the domain: `month-end-workstream` (the evidence item tests and states), `software-factory-workstream` (always offline, and the factory's contract in `SOFTWARE-FACTORY.md` beside it). A new workstream loads both, the shared one first, rather than restating either.

### Agents

An agent is a role: who does the work, with which tools and model, toward which outcome. `<department>/agents/<name>.md` with frontmatter `name` (equal to the file name), `description` (at most 700 characters: what it does, when to call it, when not and which sibling to use instead, the one briefing rule), `model`, `color`, `skills`, and `tools` (pinned for every sub-agent).

Every agent file follows the standard in `agent-standard.md` beside this file and starts from one of its templates (`templates/orchestrator.md`, `templates/sub-agent.md`): an opening sentence saying what the agent owns, then Goal, Inputs, Context, Approach, Boundaries, Done when and Output, in that order. Make a piece an agent only when it needs its own context window, parallel runs, a different model, independence or different tool access; otherwise it is a skill.

**Orchestrator** (one per kind of work; the main session; `claude --agent <name>`):
- Its Approach is the five stages: A. Gather (the standing documents, the period's state, the check's output, the pull already refreshed by the launcher), B. Plan & clarify (the unblocked work, and every question in one batch), C. Build (dispatch with a log line before, recording each return at once), D. Test & review (an independent reviewer; a FAIL returns to B with its findings, at most two rounds), E. Deliver (STATUS, root STATUS, LOG, the check's result; nothing sent or posted without a person). Each stage says its Goal, Who and "Move on when".
- Its `## Team` gives each sub-agent's objective, inputs, boundaries, output and when it is dispatched. Its Done when points at the check tool; its Boundaries carry the authority pointer to the rules file.
- The only writer of state. Records each workstream's return block field by field: items to the evidence file, rows to the procedures copy, questions through `comms-confirm`, proposals to the keeper, findings to the findings file.
- Dispatched as a sub-agent it cannot dispatch, so it is always the main session.

The sub-agents below follow the sub-agent template: their Approach is the principles and judgment calls for their slice, never a step script; a fixed procedure goes in a skill they load.

**Workstream** (one per area of the work):
- Owns rows and accounts from the procedures. Says what good looks like in its area and which shared skills it uses. Loads `orchestration-workstream` first, then its domain's extension, for conduct and the return block.
- Cannot dispatch sub-agents, so everything it needs is a skill or a tool it runs itself.
- Its `tools` list only the commands its work needs.

**Reviewer**: maker-checker. Gets files and sources only. Writes one review note and returns PASS or FAIL per item with fixes, plus a close-level verdict when asked for the sign-off. Runs on the everyday model per item and on the strongest model for the sign-off.

**Keeper**: sets up a period (folders, the procedures copy with dates, STATUS, LOG, the findings file, carry-forward), curates (links, stale questions, long logs), and records a learned fact in the right standing document with its source. Rules changes are proposals.

Writing agents that run headless under a guarded scheduler:
- A skill may not be loaded as a tool there: say "read its `SKILL.md` if it is not loaded".
- One command per call, no pipes, redirects, `&&` or variables: a command guard refuses them.
- Call a skill's script by its full path; a rule on a bare interpreter (`Bash(python3:*)`) is too broad for a guarded session, so grant the exact script.
- Avoid the phrase "follow the <name> skill" in an orchestrator that follows no single skill: a launcher may read it as the skill the agent follows.

### The launcher

The launcher is how the owner starts, schedules and watches the work. It lives in the owner's private settings because it names the client's folder and the machine's paths. Whatever runs it, it holds:

- the agent: the orchestrator;
- the folders it may read (the engagement folder) and fixed inputs such as the folder path;
- the permission fence: Write and Edit on the client folder, and each skill script by its exact command;
- prepare: the deterministic commands that run before the agent (the pull refresh); their first line reaches the agent;
- finish: the deterministic commands that run after a session that ended done (the software factory's ship step). They never run after a stopped or failed session, and a command that writes to a system is skipped on a dry run;
- the launch form (period, instructions, dry run);
- the schedule and the precheck for a heartbeat. The precheck is the check tool's `--precheck`, so a scheduled Run starts only when something changed. It ships disabled until one live period has run;
- a turn and time budget, and the list of worker agents whose commands the session must allow.

Give the orchestrator a dry run (read everything, report the plan, write nothing) and use it to prove a new launcher before its first live Run.

## Authority

- The ladder for every checklist row: **verify** (check and report), **draft** (prepare a file for a person), **execute** (do it in the system). Agents verify and draft; people execute, until the rules say otherwise for a specific system and action.
- The rules file states, per system, what agents may and may not do. It is the owner's.
- To widen authority (for example, drafting journal entries in the ERP), in this order:
  1. build the deterministic tool that does exactly that write, in the safest state, with a least-privilege credential;
  2. prove it in a sandbox;
  3. add it to the agents' tool lists;
  4. change the rules file.

  Never widen by giving an agent a general command.

## Models

- **Opus** for the orchestrator, the workstreams and the per-item review: the everyday work.
- **The strongest available model** for the hardest reasoning: a close-level sign-off, a difficult investigation, a judgment that is close. The orchestrator can raise a single dispatch to it.
- **Sonnet** for bulk reading and data processing, and for housekeeping (the keeper).
- Report which model ran each piece.

## Done, evidence and learning

- The definition of done lives in the rules file. For a close it is four tests:
  1. entries booked and confirmed posted, with backup;
  2. every balance-sheet account reconciled, final and tied;
  3. significant flux explained in the findings;
  4. every question answered or its effect stated.
- `<work>-check` computes it from the evidence file, the folder and the pull. The orchestrator reports the check's result; the close-level sign-off reviews it.
- The check also compares every draft with what was posted. "Posted but different" means a person changed the draft: the orchestrator finds why and proposes the lesson.

## Questions to people

- One question per item, asked only after the folder, the prior periods and the system cannot answer it, through `comms-confirm` (relayed to the owner, who passes it on or answers it).
- Each becomes a Waiting on row and a task on the owner's list, due by the end of the next full business day, with a weekday-morning reminder.
- The session does not wait. It records the question and moves on to other work; the next session starts from the answer.
- A stop that waits for the owner is only for a decision that blocks every remaining task and that only the owner can make.

## Naming

- Agents and skills: `<work>-<role>` (`month-end-cash`, `month-end-reviewer`); a skill useful beyond one kind of work drops the prefix (`erp-ledger-pull`).
- Folder files: `<WORK>-RULES.md`, `<WORK>-PROCEDURES.md`, `<WORK>-PROCEDURES-{yyyy-mm}.md`, `<WORK>-FINDINGS-{yyyy-mm}.md`, `<WORK>-EVIDENCE-{yyyy-mm}.csv`.
- Work products: say what they are and the period (`{account} {name} recon {yyyy-mm}.xlsx`), drafts end `DRAFT`.

## Building a new one: the checklist

1. Write the rules and procedures with the owner: authority, thresholds, the definition of done, the checklist with owners and due days, and the inventory the work must cover.
2. List the workstreams from the procedures (group the rows; give every inventory item a workstream or a person).
3. Find what exists: the department READMEs for agents, skills and commands. Improve before building.
4. Build the tools the definition of done needs: the pull, the check (`<domain>-check`, with `--precheck`), the record tool (on the skill's own copy of the ledger helper), and the controlled writers.
5. Write the shared skills for each kind of work product, and, if the kind of work is new, a thin domain extension of `orchestration-workstream`.
6. Write the spec, then the files. Put the orchestrator in a spec (the worked example is `references/example-spec.yaml` in the `orchestrator-scaffold` skill), generate or write the skeleton from it, then write the workstreams, the reviewer and the keeper, then the orchestrator, goal-first, each keeping its template's sections.
7. Set up the engagement folder and one period with the keeper.
8. Set up the launcher, lint the orchestrator (descriptions, the "follow the skill" phrase, interpreter rules, private names and home paths, missing skills and commands), then prove it with a dry run.
9. Run the private-name check with the rest of the tests; the build is not done while it fails.
10. Run one live period with the owner watching. Then retire whatever it replaces.
11. Then turn on the heartbeat.

## What not to do

- **Bookkeeping ceremony in every skill.** Opening and closing scripts in every step list make each skill a ceremony. One writer of state, and simple tools for it.
- **Prose returns.** The orchestrator has to interpret them. Return a json block.
- **Letting the agent decide whether to refresh data.** Refresh in code before it starts.
- **Hard-coded paths or names in a skill.** They break on the next machine and leak private facts. Inputs and the folder hold them.
- **`Bash(python3:*)` in a headless agent.** Grant the exact script.
- **A sub-agent that dispatches.** It cannot. Methods it needs are skills and tools.
- **Two systems for the same work.** Retire the old one once the new one has run a period.
- **Trusting a rebuilt number without comparing it.** Prove a tool that replaces a number by reproducing the last good result on real data before it runs unattended, and have it report the size of any change it makes.
- **Silent platform breakage.** A platform update can stop every Run until a person notices. Have the launcher verify a new version itself and tell the owner once.
