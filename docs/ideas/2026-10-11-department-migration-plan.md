# Plan: migrating every department to the software pattern

- **Written:** 2026-10-11, after the software department became the first plugin and passed a
  dry run on a real repository.
- **Status:** a plan. D1 to D5 were decided on 2026-10-11 (section 3); nothing has been built yet.
- **How it was made:** a script inventoried the toolbox (190 agents, 152 skills, 70
  Automations, 67 overlays). Five agents then read every agent and skill file of three or
  four departments each and designed them to one template (Part 2). The parts that cut
  across departments (Part 1) and the claims they rest on were checked against the code.

Part 1 is the plan. Part 2 is the per-department design, one section per department.

---

# Part 1: the plan

## 1. Where this ends

Every department becomes what `software/` is today:

- **One standalone plugin per department.** `<dept>/.claude-plugin/plugin.json`, its own
  `agents/`, `skills/` and `bin/`. No dependency on another plugin.
- **One short main agent per job** (a job is what one Automation runs). It is named for what
  it does and drops "-orchestrator". About 40 lines: goal, inputs, done, never, `skills:`
  and `tools:`.
- **One `<dept>-reviewer` and, where needed, one `<dept>-worker`.** They replace the
  specialists. A specialist's know-how becomes a `##` section of the job's skill, run in one
  of three ways:
  - by the main agent itself;
  - by the worker, only for parallel or isolated slices;
  - as a reviewer checklist, only where independence matters.
- **A `## Steps` section in each job's skill,** so Sentinel's "How it works" draws it.
- **Scripts become named commands in `bin/`.** Tool rules read `Bash(name:*)`.
- **Shared skills are copied into each department that uses them,** from one source, by a
  build step, with a check that keeps the copies identical (your decision 5).
- **Nothing from the toolbox loads in an everyday Claude Code session.** `~/.claude/skills`
  is unlinked, and you switch a department on where you want it.

### The numbers, converting each job one-for-one

| | Today | After the 1:1 conversion |
|---|---|---|
| Agents | 190 | about 99: 64 main agents, 17 reviewers, 15 workers, plus software's 6 (counted in) |
| Agents with an `-orchestrator` name | 67 | 0 |
| Specialist agents | 123 | 0; each becomes a skill section or a checklist |
| Plugins | 1 (software) | 17 (obsidian holds skills only) |
| Skills per plugin | n/a | 3 to about 34. The total rises because of copies; what matters is one plugin's listing |
| Toolbox skills loaded in an everyday session | 154 | 0 |

"Main agents" here means one per job. The later merges the department designs propose
(Part 2, "Merge candidates") would take the count down by perhaps 15 more. Those are separate
decisions, made after the conversion has run for a while, never during it.

## 2. What the inventory found that shapes the plan

These are facts about today's code, checked by hand. Each one becomes work in section 4.

1. **Scripts call other skills by their `~/.claude/skills` path.** 26 scripts in 12 places
   do. Examples:
   - `board-package-workstream/_common.py` runs accounting's `month_end_check.py`.
   - `delivery_apply.py` and the goal alignment run productivity's `task_stack_apply.py`.
   - `firm_billing_deliver.py` and `client_update_deliver.py` run productivity's
     `email_deliver.py`.
   - `accruals.py` finds `je_import.py`.

   All of these break the day `~/.claude/skills` is unlinked.
2. **The Automations' `sentinel.yaml` files hold 66 script paths** (`{skills_dir}/<skill>/scripts/x.py`).
   29 are `comms-confirm`'s and 8 are `task-stack-workstream`'s. `{skills_dir}` resolves to
   `~/.claude/skills` today.
3. **Sentinel's prepare, precheck and finish commands run outside the Claude session.** A
   plugin's `bin/` is on PATH only inside a session. The sidecars therefore cannot call
   named commands yet.
4. **Agent names are written into scripts and records:**
   - `CHECKED_CANCELS = ("task-reconcile-orchestrator",)` in `task_stack_apply.py`;
   - `ORCHESTRATOR` constants in the calendar steward and weekly review;
   - `agent_slug` lookups in relationship tending;
   - the `"orchestrator"` field in every change set;
   - `LOG.md` headings in your own folders.

   Renaming an agent without an alias period breaks these quietly.
5. **Settings tables are keyed by skill name** (`[task-stack-workstream]`,
   `[meeting-scheduled-worker]`, `[daily-plan-method]`, ...). Renaming a skill breaks your
   settings. So skills keep their names; only agents are renamed.
6. **Sentinel tells a main agent by its name.** The pattern is `-orchestrator$` or
   `chief-of-staff`. Today it affects only the agent page's Run once form and part of the
   Fleet. Once nothing is called "-orchestrator", it should decide from what the agent does.
7. **Sentinel draws one `## Steps` per skill.** Two jobs that share one skill
   (`bd-workstream`, `marketing-content-workstream`, `project-engagement-workstream`,
   `discovery-workstream`) each need a thin job skill of their own to hold their Steps.
8. **Several skills marked as having Steps use `### Step N:` headings,** not the
   `N. [kind]` format Sentinel draws: `accomplishment-*-method`, `decision-case-mining`,
   `playbook-distilling`, `recording-harvest`. They need converting.
9. **A worker's model is fixed per agent definition.** Sentinel passes the worker's model
   from its file. Dispatching one worker at haiku for research and at opus for drafting
   relies on Claude Code's per-call `model` override. That is unverified under Sentinel's
   `--agents`.
10. **Main agents dispatch other departments' agents in only a few real places:**
    - project-health dispatches three productivity agents;
    - sales dispatches five;
    - learning dispatches two;
    - chief-of-staff dispatches many.

    Every other "X dispatches Y" across departments is a hand-off line in a return block, or
    a "Not for" pointer. The shared reviewers are the exception: `numbers-reviewer`,
    `fact-check`, `executive-red-team` and `completeness-audit` serve 3 to 9 departments
    each.
11. **The toolbox's own audit enforces the old pattern.** It finds agents by
    `-orchestrator`, lints them against ADR 0003 (`## Team`, stages A to E) and expects
    script paths. Left alone, it reports every converted department as broken.

## 3. Decisions for you, with my recommendation

**Decided by the owner on 2026-10-11:** D1 to D5, each as recommended below:
- D1: shared sources in `shared/skills/`, which is not a plugin, with copies made by a build step.
- D2: a copied skill's commands keep one unprefixed name in every copy.
- D3: copy whole skills, after splitting the big shared ones into small pieces.
- D4: the four shared reviewers become checklist skills.
- D5: every reviewer is read-only, and the main agent writes the review file.

D6 to D13 are still open.

These are listed in the order they block work. The first five block everything; the rest
block only their department.

| # | Decision | My recommendation | Why |
|---|---|---|---|
| D1 | **Where a shared skill's single source lives** | A `shared/skills/` folder at the toolbox root, which is not a plugin, with `shared/manifest.yaml` saying which department gets which copy | A neutral home: marketing doesn't carry four unslop sub-skills it never uses, and productivity doesn't own 10 skills other departments need. An edit always goes to one obvious place, and the identity check knows where the source is. |
| D2 | **What a copied skill's commands are called** | One name with no department prefix (`task-stack-apply`, `comms-confirm-ask`, `report-tieout`), the same in every copy. A department's own scripts keep the prefix. | The skill's text stays identical in every copy, so the identity check is a plain file comparison. Scripts that call a sibling keep working. Two plugins on one PATH run identical code, so whichever comes first doesn't matter. The alternative (`accounting-task-stack-apply`, `finance-task-stack-apply`, ...) makes each copy differ and needs a substitution step. |
| D3 | **Copy whole skills, or pick files** | Whole skills, kept small. Split the big shared ones into small shareable pieces first: `calendar-time` out of `calendar-steward-method`, `html-deck-kit` out of `writing-seminar-builder`, `portal-research` from the three researcher agents, and `engagement-context` out of `client-update-workstream`. | One rule ("a copy is identical to its source") is easy to check. Picking files makes every copy a special case. |
| D4 | **The four shared reviewers** | They become checklist skills in `shared/`: `review-numbers`, `review-facts`, `review-red-team` and `review-completeness`, plus `evidence-check` from compliance. Each department's reviewer is briefed with the ones it needs. The job's own check section may set the return shape (process flow's claim ledger and the client update's verdict JSON must not change). | It keeps your decision 2 (a reviewer per department) without four separate reviewer agents. |
| D5 | **Whether a reviewer may write a file** | No. The reviewer returns its note, and the main agent writes the file that `month-end-record --review-file` and `firm-billing-record --review-file` expect. | Keeps every reviewer read-only, as `software-reviewer` is. One fewer kind of reviewer to reason about. |
| D6 | **Productivity: one plugin or several** | One plugin. | Its 13 jobs share the task-stack change set and rules file, the waiting-on tracker, the draft check and the email drafter. Splitting it four ways would copy those into 3 or 4 plugins and add 4 reviewers. If the trial shows its listing (about 34 skills) is too heavy, split into "people" and "work". |
| D7 | **What chief-of-staff becomes** | Option A in its section: a router that reads each department's catalogue and **launches Automations through Sentinel**. It never dispatches another department's agent. Its doers become small Automations. | One plugin per session makes cross-department dispatch impossible anyway. Most of its routing table already says "hand it over". The cost is that a cycle's receipt reports launches, not results (a one-cycle lag). |
| D8 | **Hand-offs between jobs** | Always a `for_owner` item ("launch X for engagement Y, with these inputs"), a filed task, or a file another job reads. Never a dispatch. Process engineering → sales and software go through a shared `automation-backlog-format` skill and a Portal note the issue collector already reads. | It is what the agents' return blocks say today, made explicit. You stay the gate between jobs. |
| D9 | **Shorter plugin names** | `recurring-summaries` → `daily`; `process-engineering` → `process`. Keep the rest. | Command names become usable (`daily-plan-pull`, not `recurring-summaries-daily-plan-pull`). The folder name is the plugin name. |
| D10 | **Skills that move between departments** | Confirm this list (each has one real user elsewhere): `month-end-results-report` → accounting; `project-engagement-baseline` → process; `start-session` → daily; `quick-capture` → productivity; `project-status-update` → projects; `task-stack-produce` → chief-of-staff; `content-scout-workstream` → marketing; `project-landscape` → strategy; `pressure-test-method` → toolbox-maintenance. | Each moves to the department that runs it. |
| D11 | **Main agents' shell** | No bare `Bash` on any main agent. Only named commands, plus `git`/`gh` patterns where the job needs them. Add the "no merge into the default branch" guard to Sentinel's Bash guard before the software developer runs in full mode. | The dry run showed bare Bash lets the agent do anything not on the deny list. |
| D12 | **Model tiers** | Each section says the tier its slice needs, and the dispatch passes it. If the per-call override doesn't hold under Sentinel (fact 9), a department gets a second worker, `<dept>-drafter`, on opus. | Otherwise the haiku researchers and sonnet trackers silently become opus. |
| D13 | **Department-specific questions** | In each section of Part 2, under "Risks and open questions". | These can wait for their wave. |

## 4. The foundation work (wave 0), before the second department

Each item says where it lives and what it unblocks.

### In Sentinel

1. **Plugin commands on PATH for code phases.** Prepare, precheck, finish, check and Monitor
   commands get every installed department plugin's `bin/` on PATH (read from the
   Libraries). The sidecars can then say `daily-plan-pull` instead of a path, and a finish
   step that needs another department's command (the client update's email delivery) still
   works. The session itself stays one plugin. Tests: a code phase finds a plugin command;
   doctor's "command missing" check already accepts plugin commands.
2. **`{skills_dir}` independent of `~/.claude/skills`.** Point it at the toolbox's merged
   folder (`~/.local/share/f3i-toolbox/skills`) until every sidecar uses commands. Doctor
   lists sidecars that still use a `{skills_dir}` path, so the count reaches zero visibly.
3. **Main agent by what it does, not its name.** A main agent is one an Automation names, or
   one whose tools include `Agent`. Rename the UI's "orchestrator" to "main agent" (badge,
   filter, Run once text). Give the Fleet a "plugin" tag per department, so converted
   departments are visible.
4. **A probe of two Claude Code behaviours** (one session each, as for the plugin probe):
   - does a dispatch's `model` override apply to a worker defined through `--agents`?
   - does a worker's `skills:` preload from the department plugin when the agent is
     dispatched by the plugin-qualified name?

   The answers settle D12.
5. **The merge guard.** A Bash-guard rule that refuses `gh pr merge` when the PR's base is
   the default branch, or a `software-pr-merge` command that checks the base first. Needed
   before the software developer's full mode, and reused by the release prep.
6. **Housekeeping:**
   - 25 Automations ask for an owner field under an old personal name, which Sentinel
     doesn't read. Change them to `for_owner:`.
   - Give the weekly review's two `fleet` sources distinct names.
   - Sentinel's `watch.py` mentions the chief of staff's `fleet-launch`; update it with the
     rename.

### In the toolbox

7. **The copy build.** `shared/skills/`, `shared/manifest.yaml` and
   `scripts/build_shared.py`:
   - each copy carries a "generated, do not edit" marker;
   - `build_bins.py` gives a copied skill's scripts its own unprefixed names (D2);
   - `toolbox_check.py` fails when a copy differs from its source or a manifest entry has no
     copy.

   First sources to move in:
   - `orchestration-workstream`, `task-stack-workstream` (with the new "Check task-stack ops"
     section), `comms-confirm` (with `notify_owner.py`), `office-files`, `comms-draft-check`
     (with show and deliver);
   - the unslop family and `brand-guide`;
   - the four `review-*` checklists and `evidence-check`;
   - `report-tieout`, `erp-ledger-pull`, `transcript-tools`, `waiting-on-tracker-method`,
     `email-drafter-method`, `meeting-analyst-method`, `portal-write-safety` and
     `portal-note-types`.
8. **Fix the 26 hard-coded paths.** A script finds a sibling script relative to its own file,
   or calls the unprefixed command. Every script's tests must still pass.
9. **Name aliases for the renames:**
   - `CHECKED_CANCELS` and the `ORCHESTRATOR` constants accept the old and new agent names;
   - change sets accept either in `"orchestrator"`;
   - relationship tending reads both slugs.

   Remove the old names a month after the last department converts.
10. **Templates.** From software's six agents: a main-agent template, a `<dept>-reviewer`
    template and a `<dept>-worker` template, plus a checklist (section 5) as
    `docs/converting-a-department.md`.
11. **The audit learns the new pattern.** `toolbox_audit_scan.py`, the `orchestrator-scaffold`
    standard and `toolbox-audit-workstream`'s "agent file standard" are updated to check the
    new pattern:
    - a plugin manifest;
    - main agents of about 40 lines with Goal, Inputs, Done, Never, `skills:` and `tools:`;
    - a reviewer and a worker;
    - `## Steps` in each job skill;
    - `bin/` matching the scripts;
    - copies identical to their sources;
    - no `skills:` or `Agent(...)` naming another department.

    `skill_inventory.py` reads plugin `skills/` folders. Done early, the audit polices the
    migration instead of flagging it.
12. **A catalogue per plugin** (`scripts/build_catalogue.py`): its main agents with job,
    inputs and Automation name, its skills you start yourself, and its commands. Checked
    like `bin/`. Needed only by chief-of-staff (wave 6), so it can wait until then.

**Wave 0 is done when** software has been re-checked against the new audit, the copy build
passes its check, every sidecar's script paths still run (through `{skills_dir}` or
commands), and the probe has answered D12.

## 5. Converting one department: the checklist

This is how software was done, made general. One department per branch in the toolbox, a
second branch in Sentinel only if it needs an engine change. Each step names its check.

1. **Read before cutting.**
   - Read the department's section in Part 2 and settle its open questions with the owner.
   - Note each Automation's sidecar: agent, prepare, precheck, finish, rules and inputs.
   - Note the baseline from the trace: the last Runs' tokens, turns and time.
2. **The plugin skeleton.** Write `.claude-plugin/plugin.json`, then add the department to
   `shared/manifest.yaml` for the copies it needs and run the copy build. Check:
   `toolbox_check.py`.
3. **Commands.** Run `build_bins.py <dept>`, then rewrite every `python3 <path>` in the
   department's skills and agents to the command. Check: `build_bins.py --check`, and the
   department's script tests.
4. **Skills.** Give each job skill its sections (each specialist's brief and return shape),
   its checklist sections and a `## Steps` list. Make thin job skills where two jobs shared
   one. Check: Sentinel's Steps parser reports no problems (as for the software skills).
5. **Agents.** Write one main agent per job from the template, then the reviewer and worker
   (only if a job needs parallel or isolated slices). Delete the specialists and the old
   main agents in the same commit; other departments' references to them follow in that
   commit. Check: the toolbox check, and that nothing in the repo names a deleted agent.
6. **Sentinel config on this machine** (`~/.sentinel`, backed up first):
   - the overlays become the new names, with `subagents:` set to worker and reviewer and
     tools set to named commands;
   - each Automation's `agent:`, script paths → commands, and folder name follow;
   - change the old owner field to `for_owner` where it is still there.

   Check: `sentinel agents`, each Automation's preview shows no missing items, and How it
   works draws.
7. **Dry run each job** from the UI, launched by you. Read its trace for:
   - tool calls refused or failing;
   - whether the reviewer and worker were dispatched as the Steps say;
   - whether the check script passed;
   - tokens, turns and time against the baseline.
8. **Live run each job** once, on a real but low-stakes input. The old agents are already
   gone (step 5); if a live run fails, fix forward or revert the branch.
9. **Write it down.** Update the department's README, the getting-started guide, the memory
   note of what was renamed, and Sentinel's docs if an engine change was needed. Merge and
   push both repositories.

A department is done when every job has passed a dry run and a live run and the audit
reports it clean.

## 6. The order

Each wave starts after the one before is done. Within a wave, the departments are
independent and can go in any order, or in parallel on separate branches.

| Wave | Departments | Why here |
|---|---|---|
| 0 | Foundations (section 4) | Everything depends on the copy build, the commands on PATH and the probe. |
| 1 | **daily** (recurring-summaries), **decision-playbooks** | The daily plan is the architecture review's trial 1: twice a weekday, with a pull, a publish and a check script, so feedback is fast. Its Steps are already drafted (Part 2). Decision playbooks is small and first proves "reviewer with a copied checklist". |
| 2 | **marketing**, **personal**, **compliance**, **learning**, **obsidian** | Small, few or no scripts, mostly the main-agent-plus-reviewer shape. Marketing settles the unslop copies; compliance makes `evidence-check`; learning splits out `html-deck-kit`. |
| 3 | **accounting**, **finance**, **reporting** | The money departments, coupled by the month-end results move, `erp-ledger-pull` and the board package's close gate. Accounting first, starting with firm billing (the review's trial 2: monthly, money, a computed check). Then finance. Reporting last, after the results report has moved and the close gate is a file contract. |
| 4 | **productivity** | The largest (13 jobs, 54 scripts). Its shared skills have already moved to `shared/` in wave 0, so it no longer blocks anyone and can go once the pattern has been proven on money and on many small departments. Task jobs first, time study last. |
| 5 | **projects**, **process**, **sales**, **strategy**, **toolbox-maintenance** | The departments with hand-offs: projects ↔ reporting's collector, process → sales and software, sales' research sections, strategy's `goal-audit` copy into projects. Toolbox-maintenance's audit was already updated in wave 0; this converts its two jobs. |
| 6 | **chief-of-staff** | It needs every other department's catalogue and Automations (D7). |
| 7 | **Cleanup** | See below. |

**Wave 7, cleanup:**
- unlink `~/.claude/skills`, and set up a local plugin marketplace so you can switch a
  department on per project or for your user;
- retire `setup/link.py`'s global linking, and make the npm installer copy `bin/`;
- remove the name aliases;
- clean up gaf-canon, and move the other PC onto this layout;
- fix any of the 25 old owner fields that remain;
- run the separate evaluation of Sentinel's own weight.

## 7. Effort

Roughly, in working sessions of the kind today's software conversion took. A day of
focused work is two or three.

| Work | Sessions |
|---|---|
| Wave 0: Sentinel (items 1–6) | 2 |
| Wave 0: toolbox (items 7–11) | 3 |
| Wave 1: daily (M), decision-playbooks (S) | 1.5 |
| Wave 2: marketing (S), personal (S–M), compliance (M), learning (M), obsidian (S) | 3.5 |
| Wave 3: accounting (L), finance (M), reporting (L) | 5 |
| Wave 4: productivity (L, the largest) | 3 |
| Wave 5: projects (M–L), process (M), sales (M–L), strategy (S–M), toolbox-maintenance (M) | 5 |
| Wave 6: chief-of-staff (L) | 2 |
| Wave 7: cleanup | 1 |
| **Total** | **about 26 sessions** |

The dry and live runs add elapsed time: a monthly job's live run waits for its month.
Nothing forces a wave to wait on a monthly job, though; a department is done in code when
its dry runs pass, and its live runs follow as their dates come.

## 8. How we will know it worked

Per Automation, before and after, from Sentinel's trace (which already records these per
model call):
- startup context: cache-write tokens at the first turn;
- total tokens, turns and wall time;
- the check script's verdict;
- reviewer FAIL rounds;
- corrections.

Per department:
- agents and skills before and after;
- the plugin's skill listing size;
- the number of files a single rule change touches.

Across the toolbox:
- everyday sessions load no toolbox skills (one `claude` session started anywhere lists none);
- the audit reports the new pattern clean.

The software dry run gives the first data point: 26 turns, about 11,000 output tokens, 2
minutes, $0.88 API-equivalent, in intake mode on four issues.

## 9. Risks across the migration

1. **Independence lost by accident.** Folding a specialist into the main agent is right for
   doing work and wrong for checking it. The template keeps every check with the reviewer,
   briefed from the sources and never the maker's reasoning. Watch the first runs of each
   department for a main agent checking its own work.
2. **Copies drifting, or an edit landing in a copy.** The identity check catches it at
   commit. Chief-of-staff's improver and the toolbox audit's fixer must map a skill to its
   source in `shared/` (both flagged in Part 2).
3. **Portal writes from more places.** `task_stack_apply.py` runs in eight departments'
   finish steps. They are identical copies under one command name (D2), so one bug is one
   bug, but it is everywhere at once. Its tests run once, against the source.
4. **Least privilege loosens a little.** A worker's tools are the union of its slices', wider
   than any one specialist had. Name each worker's commands, never bare Bash, and keep
   Portal write tools off workers that don't draft.
5. **Interactive skills that name agents** (`comms-inbox-replies`, `comms-follow-ups`,
   `crm-data-review`, `work-survey`) must be rewritten to brief the worker with a section.
   Otherwise they fail the first time you use them by hand.
6. **Your own folders name old agents** (`LOG.md` headings, rules files, `BILLING-RULES.md`).
   Nothing found so far parses them, but check per department in step 1 of section 5.
7. **Per-client Automations multiply the sidecar edits** (client delivery, client update,
   month-end, product costing, tech portfolio, board package). Script the sidecar rewrite
   per department rather than editing by hand.
8. **A long migration leaves two patterns side by side for weeks.** That is fine, because
   each department is standalone. The audit (wave 0, item 11) must accept both until the
   last wave.

---

# Part 2: the departments

Each section below was written by an agent that read the department's files. They follow
one template: today, plugin, main agents, specialists, reviewer and worker, skills,
cross-department dependencies, Automations, merge candidates, risks, effort and order. Where
a section disagrees with Part 1 (on copied command names, where shared sources live, or
whether the reviewer may write), Part 1's recommendation stands until you decide.

They are not edited beyond removing their opening notes. Names of clients are left out; per-client
Automations are called that.

---

I read every agent and skill file in the five departments, the software worked example, sections 5 and "The owner's decisions" of the architecture review, and the parts of Sentinel that matter here: `engine/model_claude_code.py` `department_plugin`, `engine/automations.py` `ORCHESTRATOR`, and `sentinel launch` in `engine/cli.py`. I edited nothing.

**Points that affect all five departments (each also comes up in the sections below):**
- **Copying must be built first.** Recurring-summaries, strategy, decision-playbooks and toolbox-maintenance all need `orchestration-workstream` (software) and `task-stack-workstream` (productivity). The build-copy step and its identity check (decision 1) have to exist before any of them converts. `task_stack_apply.py` runs in four departments' finish steps, and goal-alignment's scripts call it by path.
- **Command names for copied scripts.** I recommend that a copied skill's scripts keep one name without a department prefix (`task-stack-apply`, `task-stack-check`). The copies are checked identical, so whichever plugin's `bin/` comes first on PATH runs the same code. The department prefix is then reserved for a department's own scripts. This needs the owner's decision.
- **Sentinel finds main agents by name.** Its main-agent test is the pattern `(-orchestrator|^chief-of-staff)$` (`engine/automations.py`, used by `is_orchestrator` and `worker_of`). Every main agent renamed without "-orchestrator" stops counting as one. Sentinel needs another test, for example "the agent an Automation names" or a frontmatter key.
- **One plugin per session.** Sentinel gives a working session exactly one department plugin (`department_plugin`). Anything that needs several plugins in one session is a Sentinel change.
- **Steps headings need rewriting.** Several skills the data marks as having Steps (`accomplishment-*-method`, `decision-case-mining`, `playbook-distilling`, `recording-harvest`) use `### Step N:` headings, not the `N. [tag]` format Sentinel draws. They still need rewriting.

---

### recurring-summaries

**Today:** 11 agents (2 main), 4 skills, 8 scripts (plus 2 `_common.py` modules). The owner's own daily rhythm. Each weekday morning the daily plan picks the top three, fits them to free time and names conflicts and missing meeting prep. Each evening it closes the day on evidence, re-dates what moved, writes the done list and names tomorrow's three. Each night the sweep handles each unswept date: it files the day's email as tasks and notes, completes tasks the sent mail finished, names five relationships to tend, preps the next day's external meetings and writes a Daily Note. Both jobs read the Portal and leave their writes in the Run folder for a finish script.

**Plugin:** `recurring-summaries`, one plugin. Both jobs are the owner's own day, read the same Portal entities and share the state folder. Open question: the name makes very long commands (`recurring-summaries-daily-plan-pull`). Renaming the plugin `daily` would give `daily-planner`, `daily-sweep`, `daily-reviewer`, `daily-worker`, `daily-plan-pull`, `daily-sweep-apply`. The tables below use the current name.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| `daily-plan-orchestrator` | `recurring-summaries-daily-planner` | In the morning it picks the top three and fits them to the calendar; in the evening it closes each item on evidence and names tomorrow's three. | **worker**: one per active domain packet for the done-list candidates, in parallel on a cheap model. **reviewer**: each medium-confidence `complete` op, for independence. | `daily-plan` |
| `nightly-sweep-orchestrator` | `recurring-summaries-nightly-sweep` | For each unswept date (oldest first, at most 3) it files the email, closes finished tasks, names relationships, preps meetings and writes the Daily Note, with each plan dry-run checked. | **worker**: phases 1 to 4, to keep each phase's reading (a day of mail, every open task) out of the main context. **reviewer**: none; `sweep-apply --dry-run` is the independent check, in code. | `nightly-sweep-skill` |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `daily-plan-planner` | 29 | section "Morning: picking three" plus "Morning: fitting the day" of `daily-plan-method`, run by main | These sections already exist; the agent added only its brief. Matches the trial plan: no dispatch in the morning. |
| `daily-plan-closer` | 29 | section "Evening: closing the day" of `daily-plan-method`, run by main | Holds the `extra.ops` shape. |
| `accomplishment-gatherer` | 110 | section "Gather one domain" of `daily-plan-method` (from `accomplishment-gatherer-method`), by worker with `model: haiku` | Keep the issue harvest's rule: with one or two packets, main gathers itself. |
| `accomplishment-synthesizer` | 91 | section "Done today" of `daily-plan-method` (from `accomplishment-synthesizer-method`), run by main | The cap of ten and the grouping by domain move into the section. |
| `task-reconcile-checker` (productivity) | n/a | reviewer checklist "Check an op", copied in with `task-stack-workstream` | Write that checklist once, as a section of `task-stack-workstream` in productivity, so every copy carries it. |
| `nightly-sweep-email-processor` | 19 | section "Phase 1: Process the email" of `nightly-sweep-workstream` (from `briefs/email-processing.md`), by worker | Needs `maxTurns` of about 100 on the worker. |
| `nightly-sweep-task-reconciler` | 19 | section "Phase 2: Reconcile tasks" (from `briefs/task-reconciliation.md`), by worker | |
| `nightly-sweep-relationship-scout` | 19 | section "Phase 3: Relationship health" (from `briefs/relationship-health.md`), by worker | Small enough for main; worker keeps it 1:1. |
| `nightly-sweep-calendar-preparer` | 19 | section "Phase 4: Prep the next day's meetings" (from `briefs/calendar-prep.md`), by worker | Needs the Portal `meeting_prep` tool. |
| `nightly-sweep-note-writer` | 19 | section "Phase 5: Write the Daily Note" (from `briefs/daily-note.md`), run by main | Main already holds the phase returns it saved. If a three-date catch-up floods the context in the trial, move it back to the worker. |

**Reviewer:** `recurring-summaries-reviewer` (opus, read-only Portal tools including `email_bodies`, no Write). It checks one medium-confidence task op from the sources alone: did this evidence do what the task says, for the right party, after the task was created? It is briefed with the section "Check an op" from the copied `task-stack-workstream`. No shared reviewer checklist (numbers, fact-check, red team, completeness) is needed.

**Worker:** `recurring-summaries-worker` (default opus, `maxTurns` about 100). Tools: Read, Grep, Skill, and the Portal reads `whoami`, `get`, `search`, `list_entities`, `email_bodies`, `meeting_prep`, `priority_review`. No Write: every slice returns its block. It is used for the sweep phases 1 to 4 and for "Gather one domain" on haiku through the Agent tool's `model` override. Confirm Sentinel's `subagent_definition` passes that override.

**Skills**

| skill | change | add `## Steps`? | scripts → commands |
|---|---|---|---|
| `daily-plan-method` | keep; merge in both accomplishment skills as sections, plus "Check the plan" (the orchestrator's acceptance test) | **yes** (draft below) | `daily_plan_pull.py` → `recurring-summaries-daily-plan-pull`; `daily_plan_publish.py` → `recurring-summaries-daily-plan-publish`; `daily_plan_check.py` → `recurring-summaries-daily-plan-check` |
| `accomplishment-gatherer-method` | merge into `daily-plan-method` ("Gather one domain"); retire | n/a | none |
| `accomplishment-synthesizer-method` | merge into `daily-plan-method` ("Done today"); retire | n/a | none |
| `nightly-sweep-workstream` | keep; fold `briefs/*.md` into `## Phase 1` to `## Phase 5` sections; keep `rules.md` beside it; turn "The session, step by step" into `## Steps` | **yes** (draft below) | `sweep_dates.py` → `recurring-summaries-sweep-dates`; `sweep_emails.py` → `-sweep-emails`; `sweep_tasks.py` → `-sweep-tasks`; `sweep_apply.py` → `-sweep-apply`; `sweep_note_publish.py` → `-sweep-note-publish` |
| copied in: `orchestration-workstream`, `task-stack-workstream` | copies (source in software and productivity) | no | `task-stack-apply`, `task-stack-check` (unprefixed, see the opening points) |

**Draft `## Steps` for `daily-plan-method`** (for `recurring-summaries-daily-planner`):

```
1. [judgment] Orient. `whoami`; read TASK-STACK-RULES.md and DAILY-PLAN.md (they override this skill), then RUN/pull.json: the pass, the date, free minutes, conflicts, external meetings without prep, candidate count.
   → the prepare line says STALE, or pull.json is missing: step 2
   → pass morning: step 3
   → pass evening: step 7
2. [judgment] Read the Portal yourself for what the pull lacks (`list_entities`, `priority_review`, today's calendar) and note the gap for the report.
   → pass morning: step 3
   → pass evening: step 7
3. [judgment] Pick three, by section Morning: picking three: score each candidate on goal leverage, time decay and top of mind, apply the five overrides, and add at most five "also today" items.
4. [judgment] Fit the day, by section Morning: fitting the day: a free slot or focus block for each top item, every conflict with a fix, every `needs_prep` meeting with a prep line, at most three focus-block proposals.
5. [judgment] Check the plan, by section Check the plan: every ref is in the pull or reads back, every slot lies in a free slot, every conflict and every `needs_prep` meeting appears, at most three proposals.
   → a gap: step 3 (max 1)
   → clean: step 6
6. [judgment] Write RUN/plan.json (the morning shape, `"tool": "daily-plan"`, `pass`, `dry_run`) and RUN/changes.json (a `task-stack-changes` set with no ops).
   → step 12
7. [judgment] Close each planned item, by section Evening: closing the day: done, moved, carried or dropped, on evidence, each with its op. A `null` `morning_plan` means you account for the day's top work instead.
8. [judgment] Capture the day's commitments: search the open tasks first, then a `create` op for each promise or assigned action with no task.
9. [hand-off: recurring-summaries-worker] Gather the done-list candidates: one worker per active packet in the pull's `packets` (at most six), told to follow section Gather one domain, with `model: haiku`. With one or two packets, gather them yourself by the same section. Save each return to RUN/returns/.
   → no packets: step 10
10. [judgment] Done today, by section Done today: pool the candidates, pick at most ten, group by domain, write the one-line header.
11. [hand-off: recurring-summaries-reviewer] Check each `complete` op of medium confidence, told to follow the copied task-stack-workstream's section Check an op, with the op only, never your reasoning. A FAIL drops the op and the item becomes carried.
   → no medium op: step 12
12. [script] Write RUN/plan.json and RUN/changes.json for the pass (evening: the close with `close.done`, at most 20 ops, each op id on its item), then run `recurring-summaries-daily-plan-check DATE --pass P --run RUN --offline`.
   → a failed test: step 5 if morning, step 7 if evening (max 1)
   → passes: step 13
13. [judgment] Report: the top three or the close in a few lines, conflicts and prep, the calendar proposals and questions as one numbered list, and what could not be read. Never claim the note was written or a task moved.
   → reported: done
```

Steps 6 and 12 overlap on purpose: step 6 is the morning write, step 12 the evening write plus the in-session check. `--offline` exists today. Whether it tolerates the missing `apply.json` in the evening still needs checking.

**Draft `## Steps` for `nightly-sweep-workstream`** (for `recurring-summaries-nightly-sweep`, converted from "The session, step by step"):

```
1. [judgment] Orient. `whoami`; read this skill, rules.md, the owner's NIGHTLY-SWEEP-RULES.md and RUN/dates.json.
   → no dates.json or unreadable: step 11 (stopped, with the reason)
   → status nothing: step 11
   → refused IN_PROGRESS: step 11 (stopped, the refusal's reason; never "nothing to sweep")
   → ok: step 2
2. [judgment] Take the next date in dates.json this Run has not handled; keep its outcome.
   → none left: step 11
   → a date: step 3
3. [hand-off: recurring-summaries-worker] Phase 1, section Phase 1: Process the email, with the date, its weekday, `email_window` and the paths of RUN/D/emails.json, rules.md and the owner's rules file. Save its block as RUN/D/phase1.json.
   → emails.json missing, unreadable or no inbound rows: step 5 (record why)
4. [script] `recurring-summaries-sweep-apply --dry-run RUN/D/phase1.json --date D`.
   → would_apply or nothing: step 5
   → refused INVALID_PLAN: step 3 (max 1), with the refusal verbatim
   → BLOCKED, WRONG_DATE, WRONG_PHASE, a second refusal, or could not run: step 5 (record it)
5. [hand-off: recurring-summaries-worker] Phase 2, section Phase 2: Reconcile tasks, with the date, the window and the paths of emails.json, tasks.json and rules.md, saying which is missing. Save as RUN/D/phase2.json.
6. [script] `recurring-summaries-sweep-apply --dry-run RUN/D/phase2.json --date D`.
   → would_apply or nothing: step 7
   → refused INVALID_PLAN: step 5 (max 1)
   → otherwise: step 7 (record it)
7. [hand-off: recurring-summaries-worker] Phase 3, section Phase 3: Relationship health, with the date, `vip_stale_days` and rules.md. Save as RUN/D/phase3.json. It proposes no writes.
   → `relationship_check` false: step 8
8. [hand-off: recurring-summaries-worker] Phase 4, section Phase 4: Prep the next day's meetings, with the date, `next_day`, `calendar_window` and rules.md. Save as RUN/D/phase4.json.
   → `calendar_prep` false: step 10
9. [script] `recurring-summaries-sweep-apply --dry-run RUN/D/phase4.json --date D`.
   → would_apply or nothing: step 10
   → refused INVALID_PLAN: step 8 (max 1)
   → otherwise: step 10 (record it)
10. [judgment] Phase 5, section Phase 5: Write the Daily Note: from the phase files and the dry-run check files (counts from the checks, never the proposals), with every missing or failed phase named. Write RUN/D/daily-note.md and RUN/D/phase5.json.
   → step 2
11. [judgment] Report: RUN/report.md (per date each phase's status, check results, note or none, the for_owner lines; then waiting, beyond lookback, given up), then the finishing block.
   → reported: done
```

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `orchestration-workstream` (software) | in | copy in |
| `task-stack-workstream` with `task_stack_apply.py` and `task_stack_check.py` (productivity) | in (in-session shape; finish step) | copy in, with its scripts and the new "Check an op" section |
| `task-reconcile-checker` agent (productivity) | in (dispatch) | becomes `recurring-summaries-reviewer` with "Check an op" |
| calendar steward reads `<state_dir>/daily-plan/<date>/morning.json` (productivity) | out (a file contract) | keep; write the contract in both skills. It is a file, not a dispatch. |
| `start-session` (chief-of-staff) reads the plan note and runs `daily_plan_pull.py` | out | move `start-session` into this plugin (it is the plan's interactive front) |
| `weekly-review-orchestrator`, `calendar-steward-method` (productivity) name the daily plan in "Not for" lines | out (text only) | rename the mentions; no code dependency |
| sweep phases overlap `task-reconcile-`, `task-capture-`, `crm-relationship-tending-` and `meeting-prep-orchestrator` (productivity) | none (stated overlaps) | keep the "Where it meets other pieces" section; phase 4 shares the prep note title with meeting-prep by contract |

**Automations to update**
- `daily-plan`:
  - Agent: `daily-plan-orchestrator` → `recurring-summaries-daily-planner`, with `--plugin-dir <toolbox>/recurring-summaries`.
  - Prepare: `daily_plan_pull.py` → `recurring-summaries-daily-plan-pull`.
  - Finish: `daily_plan_publish.py` → `recurring-summaries-daily-plan-publish`; `task_stack_apply.py` → `task-stack-apply`; `daily_plan_check.py` → `recurring-summaries-daily-plan-check`.
  - Precheck, if any: `daily_plan_check.py --precheck` → the same command.
  - Overlay `subagents:`: the planner, closer, gatherer, synthesizer and `task-reconcile-checker` → `recurring-summaries-worker`, `recurring-summaries-reviewer`.
  - Tools: add `Skill` and `Bash(recurring-summaries-daily-plan-check:*)`.
- `nightly-sweep-skill`:
  - Agent → `recurring-summaries-nightly-sweep`.
  - Prepare: `sweep_dates.py`, `sweep_emails.py`, `sweep_tasks.py` → their commands.
  - Finish: `sweep_apply.py --run`, `sweep_note_publish.py --run` → their commands.
  - The in-session rule `Bash(python3 …/sweep_apply.py --dry-run:*)` → `Bash(recurring-summaries-sweep-apply --dry-run:*)`.
  - `Agent(five phase workers)` → `Agent(recurring-summaries-worker)`.
  - The "-skill" suffix suggests it was made with `sentinel automation new --skill`. If its `SKILL.md` names the skill's path or the orchestrator, rewrite that too.

**Merge candidates for later**
- **calendar-steward (productivity) into the daily planner.** The architecture review proposes it. They share the focus-block proposal shape and the state folder. Risk: it crosses a department line, the 14-day horizon and the twice-daily cadence differ, and it makes the planner bigger.
- **Sweep phase 4 and meeting-prep-orchestrator.** Same ranking, same cap, same note title. Risk: also cross-department, and meeting-prep adds an independent check the sweep does not have.
- **Running the sweep's phases 1 to 4 in parallel.** They read different inputs. This is a speed-up, not a merge. Risk: the step order and the dry-run sequence change.

**Risks and open questions**
1. The daily planner is the architecture review's trial 1 ("no dispatch"). Keeping the gatherer as a worker adds dispatch to the evening pass. The trial could drop step 9 and have main gather from the packets itself. Measure tokens both ways.
2. The haiku model override for "Gather one domain" through a single worker definition depends on Sentinel's `--agents` object honouring the `model` given at dispatch.
3. Whether `daily-plan-check --offline` passes in the evening before `apply.json` exists. If not, step 12 needs a `--pre-apply` mode.
4. Command length and the plugin rename (`daily`).
5. `[nightly-sweep-workstream]` and `[daily-plan-method]` settings keep their table names. Renaming the skills would break the owner's settings, so the skill names should stay.

**Effort:** M. It depends on: the copy mechanism existing (this is the first non-software department to need it), two orchestrators of 70 and 117 lines turned into Steps, folding 5 briefs and 2 skills into sections, 8 commands, two Automations, and the tests for sweep and daily-plan scripts that call paths.

**Order:**
1. Copy step for `orchestration-workstream` and `task-stack-workstream`, including the "Check an op" section.
2. Plugin manifest, bin wrappers, reviewer and worker.
3. Daily planner, then a dry run and a live run, then retire its 5 agents and 2 skills.
4. Nightly sweep likewise.
5. Move `start-session` in.

---

### chief-of-staff

**Today:** 8 agents (2 main: the interactive `chief-of-staff` and `chief-of-staff-cycle-orchestrator`), 6 skills, 12 scripts (plus 2 `_common.py`).
- **The front door:** the owner starts `chief-of-staff` by hand. It holds a 40-row routing table to skills and agents in productivity, projects, reporting, process-engineering, strategy, software and toolbox-maintenance, dispatches them and checks what comes back.
- **The cycle:** an unattended run reads the owner's private documents, the orchestrator fleet and the task stack. It picks priorities, launches at most two registered orchestrators through the fleet scripts, runs at most two doers, proposes or commits one improvement on a branch, and files a verified receipt note and decision tasks.
- **Daily tools:** `start-session`, `quick-capture`, `project-status-update`, and a one-off `work-survey`.

**What chief-of-staff becomes.** Today it routes across departments, and with one plugin per session that cannot work. Read correctly, though, most of the cross-department routing was never real dispatch:
- **Recurring jobs were already handed over.** The routing table says "never dispatch it as a sub-agent; hand it over" for month-end, process-flow, the software developer, the time study, the weekly reporter and the fleet. A sub-agent cannot dispatch, so a main agent can never run as one.
- **The real cross-plugin dependencies are narrower:**
  - (a) about 20 interactive skills and single agents it calls in the same session (`comms-*`, `meeting-*`, `person-researcher`, `numbers-reviewer`, `fact-check`, `pre-mortem`, ...);
  - (b) the cycle's doers, which run productivity's `meeting-prep` and `task-stack-produce` skills and the `person-researcher` and `domain-researcher` agents;
  - (c) scripts called by path: `fleet_*`, `task_stack_check.py`, `notify_owner.py` (comms-reply-to-email), `outbound_check.py`, `daily_plan_pull.py`.

Options:

| option | how | good | costs |
|---|---|---|---|
| **A. Router over a catalogue; launches, never dispatches** (recommended) | Each plugin carries a generated `catalogue.json` (built beside `build_bins.py`): its main agents, each one's job, `## Inputs` and Automation name, its owner-started skills with descriptions, its commands. `chief-of-staff` reads every catalogue plus Sentinel's own lists (`sentinel automation list`, `sentinel runs --live --format json`). It launches recurring jobs with `sentinel launch <automation>`. For an interactive skill it answers with the exact start line (`claude --plugin-dir <toolbox>/<dept> --agent <dept>-<agent>`, or "Run once" in the Sentinel UI) instead of running it. The cycle becomes decide, launch, receipt: every doer becomes a launch of an Automation, as the doer registry's `[retired]` table already does for two doers. | Keeps decision 1 intact. Sentinel already enforces what `fleet_launch.py` enforces for an agent's launch (only an Automation in `automations_dir`, the daily cap, no `--mode live`, no `--force-new`), so the fleet scripts shrink to thin wrappers. The context stays small. Each launched job runs with its own plugin, reviewer and check. | The interactive "do it here" convenience is lost for skills like `comms-reply-to-email`: the owner switches sessions. Doer results reach the receipt one cycle later, not in the same cycle. Some doers need small Automations to exist first (meeting-prep for one focus, person brief, domain brief, produce-work). The fleet registry's per-entry authority and param patterns must move into the Automation folders or stay as a chief-of-staff file. |
| B. Load several plugins | The interactive session is started with several `--plugin-dir` flags (an alias), so all skills are in reach. | The routing table keeps working for skills and single agents. | Brings back the large skill listing the slimming removed. Copied shared skills appear once per plugin. Sentinel gives one plugin per session (`department_plugin`), so the cycle cannot use this without an engine change. Main agents still cannot be dispatched as sub-agents, so jobs still need launching. |
| C. Retire the interactive front door | The Sentinel UI (Automations, Run once, the agents page) is the front door; only the cycle stays. | The simplest. | Loses the conversational "which thing do I need" router and the "check the result against the source" habit. |

Recommendation: A for both the cycle and the interactive agent. Offer B only as the owner's own shell alias for hand sessions, never in Sentinel.

**Plugin:** `chief-of-staff`, one plugin. The daily tools leave (see Skills). I did not split it: the cycle and the router share the catalogue reading and the launch path.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| `chief-of-staff-cycle-orchestrator` | `chief-of-staff-cycle` | One unattended cycle: read the owner's documents and the fleet, decide priorities, launch at most two Automations, file one verified receipt and the decision tasks. | **worker**: only for the produce-work doer while it stays in-cycle (no Portal tools, isolated private packet). **reviewer**: none; `decide_check`, `publish` and `verify` are the independent checks, in code. | `chief-of-staff-skill` (and the Monitor that runs `cos_watch.py`) |
| `chief-of-staff` (interactive, 95 lines) | `chief-of-staff` (keep; Sentinel's pattern names it) | The owner's front door: finds the job or skill for a request in the catalogues, launches Automations through Sentinel or gives the start line, and checks results against their sources. | **worker**: research slices (`person-researcher`- and `domain-researcher`-type reads) as sections. **reviewer**: a deliverable the owner asks to have checked. | none (hand-started) |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `chief-of-staff-decider` | 11 (brief 164) | section "Decide the cycle" of `chief-of-staff-cycle` (from `briefs/decider.md`), run by main | The decision is the main agent's own job; `decide_check` stays the gate. |
| `chief-of-staff-receipt-writer` | 9 (brief 110) | section "Write the receipt" (from `briefs/receipt-writer.md`), run by main | `publish` and `verify` are the independent check. |
| `chief-of-staff-improver` | 9 (brief 21) | section "One improvement" (from `briefs/improver.md`), run by main | See risk 3: the target must be a source skill, never a copy. |
| `chief-of-staff-producer` | 10 (brief 9) | section "Produce one draft" by `chief-of-staff-worker`, or retired once produce-work is an Automation | Uses `task-stack-produce` (productivity): copy that skill in, or launch it. |
| `chief-of-staff-readonly-doer` | 9 | retire; each registry doer with route `skill` becomes an Automation launch | Its value was running other departments' skills, which a launch does with the right plugin. |
| `chief-of-staff-meeting-prep-doer` | 10 | retire; launch a productivity meeting-prep Automation with a focus param | |
| `person-researcher`, `domain-researcher` (productivity, route `agent`) | n/a | launch productivity Automations ("person brief", "domain brief"), or copy their method as sections run by `chief-of-staff-worker` for the interactive agent | Copying gives the front door quick research in-session; launching keeps one source. |

**Reviewer:** `chief-of-staff-reviewer`, for the interactive agent only, when the owner asks for a finished deliverable to be checked. It is briefed with the copied shared checklists `executive-red-team`, `fact-check` and `completeness-audit` (and `numbers-reviewer` if reporting packages stay in the front door's scope). The cycle needs none.

**Worker:** `chief-of-staff-worker`. Slices: the produce-work draft (while in-cycle), research slices for the interactive agent, and `work-survey`'s gatherers and analysts, which today are general-purpose sub-agents with a model override.

**Skills**

| skill | change | `## Steps`? | scripts → commands |
|---|---|---|---|
| `chief-of-staff-cycle` | keep. Fold `briefs/*` into sections "Decide the cycle", "Produce one draft", "One improvement", "Write the receipt". Rewrite steps 7 to 12 so doers become launches. Point the launch at Sentinel. | has it (23 steps); shrinks to about 15 | `chief_of_staff_cycle.py` → `chief-of-staff-cycle`; `chief_of_staff_fleet.py` → `chief-of-staff-fleet`; `chief_of_staff_decide_check.py` → `chief-of-staff-decide-check`; `chief_of_staff_produce_work.py` → `chief-of-staff-produce-work`; `chief_of_staff_improve.py` → `chief-of-staff-improve`; `chief_of_staff_receipt.py` → `chief-of-staff-receipt`; `chief_of_staff_records.py` → `chief-of-staff-records`; `chief_of_staff_notify.py` → `chief-of-staff-notify`; `cos_watch.py` → `chief-of-staff-watch` |
| `orchestrator-fleet` | keep for now as the catalogue and launch layer: `fleet_status` over `sentinel runs`, `fleet_launch` over `sentinel launch`. Merge into `chief-of-staff-cycle` later. | no (a reference) | `fleet_registry.py` → `chief-of-staff-fleet-registry`; `fleet_status.py` → `chief-of-staff-fleet-status`; `fleet_launch.py` → `chief-of-staff-fleet-launch` |
| new `chief-of-staff-routing` | the interactive agent's routing table moved out of the agent file, rewritten as "read the catalogues; launch or hand over"; the agent file drops to about 40 lines | no | none (reads `catalogue.json` files) |
| `start-session` | move to recurring-summaries | n/a | uses `recurring-summaries-daily-plan-pull` there |
| `quick-capture` | move to productivity (it uses `task-stack-capture`, `task-stack-apply` and `portal-write-safety`, all productivity's) | n/a | none |
| `project-status-update` | move to projects (with a copy of `portal-write-safety`) | n/a | none |
| `work-survey` | keep; its sub-agents become `chief-of-staff-worker` slices | no (owner-started, phased) | none |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| ~20 skills and single agents in the routing table (productivity, projects, reporting, process-engineering, strategy, software, toolbox-maintenance) | in | drop the dispatch; route by catalogue: launch or hand over |
| main agents of other departments (month-end, process-flow, crm-*, meeting-prep, time-study, project-health, daily-plan, toolbox-audit, software-developer, weekly-reporter) | in | launch through Sentinel (`sentinel launch`) or the owner starts them; already "hand it over" today |
| `meeting-prep`, `task-stack-produce` skills; `person-researcher`, `domain-researcher` (productivity) | in (cycle doers) | become Automation launches; produce-work optionally copied in |
| `task_stack_check.py --precheck` (fleet snapshot) | in (script by path) | copy `task-stack-workstream` in (`task-stack-check`) |
| `notify_owner.py` (comms-reply-to-email) | in (script by path) | copy the one script into `chief-of-staff-cycle`, or use Sentinel's own notify; prefer copying the script |
| `outbound_check.py` (comms-draft-check) | in (routing rule) | drop from the front door; drafting lives in productivity |
| `daily_plan_pull.py` (start-session) | in | goes away when start-session moves |
| `executive-red-team`, `fact-check`, `completeness-audit`, `numbers-reviewer` | in | copy as checklists for `chief-of-staff-reviewer` |
| `activity-auditor` (toolbox-maintenance) via the routing row "the automation checked on itself" | in | launch toolbox-maintenance's audit |

**Automations to update**
- `chief-of-staff-skill`:
  - Agent: `chief-of-staff-cycle-orchestrator` → `chief-of-staff-cycle`, with `--plugin-dir <toolbox>/chief-of-staff`.
  - Every `Bash(python3 …/chief_of_staff_*.py:*)` rule → `Bash(chief-of-staff-<verb>:*)`.
  - The `Agent(...)` grant: the 8 names → `Agent(chief-of-staff-worker)`.
  - The owner's `[orchestrator-fleet]` settings: `runs_command` = Sentinel's runs JSON, `launch_command` = `sentinel launch {automation_path}`.
  - The doer registry: `skill`- and `agent`-route doers become launch entries.
  - The Monitor's check command `cos_watch.py` → `chief-of-staff-watch`. Sentinel's `watch.py` names "the chief of staff's `fleet-launch`"; that mention must follow the rename.

**Merge candidates for later**
- **`orchestrator-fleet` into `chief-of-staff-cycle`.** Once Sentinel is the only runner, the registry is mostly a copy of Sentinel's Automation list. Risk: the per-entry authority and param patterns have no Sentinel home yet.
- **The improvement step into toolbox-maintenance's audit.** Both propose toolbox edits on a branch. Risk: the cycle's "improve the doer it just used" feedback loop gets slower.

**Risks and open questions**
1. With doers as launches, a cycle's receipt reports launches, not results. Is a one-cycle lag acceptable to the owner?
2. An agent's `sentinel launch` is refused for a "Run once" target and counted against the daily cap. Every launchable thing must be a real Automation folder. A few new small Automations (meeting-prep focus, person brief, domain brief, produce-work) are needed before the doers retire.
3. The improver's `improve_repo` edits a doer skill's `SKILL.md`. With copied skills, editing a copy fails the identity check. `chief_of_staff_improve.py check` must map a skill name to its one source folder.
4. Where the fleet registry's `authority`, `inputs` patterns and `triggers` live: in each Automation's `sentinel.yaml` (a `launchable_by` key), or in the owner's registry file as today.
5. The catalogue: generated per plugin (`scripts/build_catalogue.py`, checked like `bin/`), or read live from Sentinel's library loader. Sentinel already parses agents from Libraries (`engine/libraries.py`).
6. Sentinel's sealed session must be able to read the other plugins' `catalogue.json` files (read roots), and `sentinel` must be an allowed command in the cycle's tools.
7. Moving `quick-capture`, `project-status-update` and `start-session` out changes where the owner finds them interactively. Each target plugin must be enabled where the owner works.

**Effort:** L. It depends on a design change rather than a 1:1 conversion: the catalogue generator, re-pointing the fleet at Sentinel, new small Automations to replace the doers, 9 plus 3 commands, the routing table rewrite, three skills moving out, and the improver's source mapping.

**Order:**
1. The 1:1 conversion of the cycle (sections, commands, `chief-of-staff-worker`) with doers unchanged.
2. Re-point the fleet at `sentinel runs` and `sentinel launch`.
3. Create the doer Automations, switch the doers to launches, and retire the 3 doer agents.
4. The catalogue and the interactive agent's rewrite.
5. Move out the three daily tools.

---

### strategy

**Today:** 5 agents (1 main), 4 skills, 5 scripts (plus `_common.py`).
- **The monthly goal alignment:** sets the owner's Portal goals against projects and the time study's hours, pre-fills the strategic-goals pulse (and the quarterly review), and puts one numbered approval list to the owner. A later pass applies the approved task-stack ops.
- **The pre-mortem:** an owner-started skill that stress-tests a strategic plan in two gates, with an assumptions investigator and a web researcher.

**Plugin:** `strategy`, one plugin.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| `goal-alignment-orchestrator` | `strategy-goal-alignment` | Each month: judge every gap between goals, projects and time, write `review.json` and the note with one approval list; in the approve pass, report how the answers resolve. | **worker**: the goal audit, split by domain for a large portfolio (parallel slices). Small portfolios: main does it. **reviewer**: none; `goal-alignment-pack` validates and the owner approves every op. | `goal-alignment` |
| (none) `pre-mortem` skill | optional `strategy-pre-mortem` (owner-started, `claude --agent`) | Run a two-gate pre-mortem on one plan. | **worker**: assumptions and external research (isolated context; research needs web tools). | none |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `goal-auditor` | 138 | section "Audit goals against work" of `goal-alignment-workstream`, run by main, or by worker per domain when the portfolio is large. Its standalone mode becomes a copyable skill `goal-audit` (source here) for projects' `project-landscape`. | Its in-alignment mode and its walk-the-Portal mode differ; split them. |
| `goal-alignment-strategy` | 34 | section "Pulse the strategic goals" of `goal-alignment-workstream`, run by main | Keep its rule that nothing from the private goals document beyond domain names, goal numbers and short titles enters the note. |
| `pre-mortem-investigator` | 83 | section "Surface the assumptions" of `pre-mortem` (from `pre-mortem-investigator-method`), by worker | Writes `gate-1-pending.md`, so the worker needs Write. |
| `pre-mortem-researcher` | 67 | section "Gather external evidence" of `pre-mortem` (from `pre-mortem-researcher-method`), by worker | WebSearch and WebFetch on the worker. Today it runs on sonnet; dispatch with that model. |

**Reviewer:** `strategy-reviewer` is not needed today: nothing in strategy has an independent checker, and the owner approves everything. Optional later: the pre-mortem brief checked with a copied `executive-red-team` checklist before Gate 2.

**Worker:** `strategy-worker`: Read, Glob, Grep, Write, Skill, WebSearch, WebFetch, and the Portal reads (`whoami`, `get`, `search`, `list_entities`, `hierarchy`, `priority_review`, `briefing`, `activity_stream`, `dereference`). Slices: per-domain goal audit, pre-mortem assumptions, pre-mortem research.

**Skills**

| skill | change | `## Steps`? | scripts → commands |
|---|---|---|---|
| `goal-alignment-workstream` | keep; add sections "Audit goals against work", "Pulse the strategic goals", "The pack pass", "The approve pass" | **yes**: orient → audit (main or worker per domain) → pulse → decide items → write review.json → [script] `strategy-goal-alignment-pack RUN` (→ not VALID: back to decide, max 2) → report; approve pass branch → report | `goal_alignment_gather.py` → `strategy-goal-alignment-gather`; `goal_alignment_pack.py` → `strategy-goal-alignment-pack`; `goal_alignment_check.py` → `strategy-goal-alignment-check`; `goal_alignment_changes.py` → `strategy-goal-alignment-changes`; `goal_alignment_publish.py` → `strategy-goal-alignment-publish` |
| `pre-mortem` | keep; merge both method skills in as sections; convert "The workflow" to `## Steps` with `[ask]` at the two gates | **yes** (it is a job even without an Automation) | none |
| `pre-mortem-investigator-method`, `pre-mortem-researcher-method` | merge into `pre-mortem`; retire | n/a | none |
| new `goal-audit` | source of the standalone audit, copied into projects | no | none |
| copied in: `orchestration-workstream`, `task-stack-workstream` | copies | no | `task-stack-apply`, `task-stack-check` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `task_stack_check.py` and `task_stack_apply.py`, called by path from `_common.py` (productivity) | in | copy `task-stack-workstream` in; `_common.py` calls the plugin's own `task-stack-*` command, not `~/.claude/skills/...` |
| time-study tables (productivity's `report-time-study`) read by `goal_alignment_gather.py` | in (a file contract, setting `time_study_home`) | keep as a data contract |
| `calendar-steward-method`'s `calendar_time.py` and `project-landscape`'s `project_scoreboard.py`, named as optional inputs in `goal-auditor` | in (standalone mode only) | in the copied `goal-audit`, the caller supplies them. Projects already owns the scoreboard; the calendar hours become an input or are dropped. |
| `project-landscape` (projects) dispatches `goal-auditor` | out | copy `goal-audit` into projects, run by `projects-worker` |
| `pre-mortem` routed by chief-of-staff; "lessons-learned" format used by projects' engagement workstream | out | the chief-of-staff hand-off; the format is a file contract |

**Automations to update:** `goal-alignment`:
- Agent → `strategy-goal-alignment`, with the plugin dir.
- Prepare: `goal_alignment_gather.py` → `strategy-goal-alignment-gather`.
- Finish: `goal_alignment_changes.py`, `task_stack_apply.py` and `goal_alignment_publish.py` → their commands.
- In-session rules: `…goal_alignment_pack.py` and `…goal_alignment_check.py` → `Bash(strategy-goal-alignment-pack:*)` and `Bash(strategy-goal-alignment-check:*)`.
- `subagents:` (`goal-auditor`, `goal-alignment-strategy`) → `strategy-worker`.

**Merge candidates for later**
- **Goal alignment with productivity's weekly review in a quarterly month.** Both put one approval list over goals and projects. Risk: it crosses departments and mixes cadences.

**Risks and open questions**
1. `goal-auditor` is the toolbox's longest specialist at 138 lines, and it serves two callers in two modes. Splitting it into a section plus a copyable `goal-audit` skill is the cleanest; check that projects really still needs the standalone mode.
2. Is `pre-mortem` worth a main agent with no Automation? Under decision 3 a job is an Automation, so it can stay a skill with `## Steps`.
3. The pre-mortem's state machine is pausable (it detects `gate-1-pending.md` and `brief.md` and resumes). `## Steps` must express "resume at step N", for example a first `[judgment]` step with branches by the files present.

**Effort:** S to M. It depends on: one orchestrator, the 138-line auditor split, the scripts' `SKILLS_HOME` path rewrite in `_common.py`, and the projects copy.

**Order:** copy `task-stack-workstream` in → goal alignment (main agent, worker, commands, Automation) → retire the two goal agents → pre-mortem sections and Steps → retire the two pre-mortem agents and method skills → `goal-audit` copy into projects.

---

### decision-playbooks

**Today:** 3 agents (1 main), 5 skills, 3 scripts. It writes down how the owner decides:
- it mines real decisions from sent mail into cited cases and harvests recorded narrations;
- it distills both into a cited playbook proposal, conflicts between what the owner says and does first;
- it puts the proposal to the owner a few questions at a time.

A weekly pass keeps one ratification packet waiting and tops up the pipeline only when the queue runs short.

**Plugin:** `decision-playbooks`, one plugin.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| `playbook-orchestrator` | `decision-playbooks-curator` | Each week: file or re-surface one ratification packet, and when the queue is short, mine cases and draft one cited, fact-checked playbook proposal into the inbox. | **worker**: case mining, one batch of sent mail per worker (parallel; many email bodies). **reviewer**: the proposal's bullets against the case files (independence: fact-check). | `knowledge-doctrine` |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `decision-case-miner` | 18 | section "Mine one batch" of `playbook-workstream` (from `decision-case-mining`, with the two Run-mode changes: brief-given window, no `decision_store.py`), by worker | Writes only its output file. |
| `playbook-distiller` | 16 | section "Distill one category" of `playbook-workstream` (from `playbook-distilling` in Run mode), run by main | One category per Run; no need for isolation. |
| `fact-check` (reporting) | n/a | reviewer checklist, copied in from the shared `fact-check` checklist skill | An unsupported bullet is cut. |

**Reviewer:** `decision-playbooks-reviewer`. It checks each proposal bullet against the cited cases only: supported, unsupported, or overstated. It is briefed with the copied `fact-check` checklist. The proposal-specific lines (each bullet cites a case id; conflicts carry both quotes) go in a short section "Check the proposal" of `playbook-workstream`.

**Worker:** `decision-playbooks-worker`: Read, Write, Skill, Portal `whoami`, `get`, `list_entities`, `email_bodies`. Slice: one batch of sent mail.

**Skills**

| skill | change | `## Steps`? | scripts → commands |
|---|---|---|---|
| `playbook-workstream` | keep as the job's skill; add sections "Mine one batch", "Distill one category", "Check the proposal"; move the orchestrator's 5 steps here | **yes**: 1 [judgment] orient (→ packet standing and unanswered within limit: step 2; else step 3) · 2 [judgment] re-surface the packet → step 5 · 3 [judgment] write the next packet (→ open items at or above the threshold: step 7) · 4 [hand-off: decision-playbooks-worker] mine per batch · 5 [judgment] distill · 6 [hand-off: decision-playbooks-reviewer] check the proposal (→ FAIL: cut the bullet, step 5, max 1) · 7 [judgment] the ratification task op unless one is open · 8 [judgment] DONE checklist and report → done | none |
| `decision-case-mining` | keep (owner-started by hand; the store's owner); convert `### 1.` to `## Steps` tags | yes (convert) | `decision_store.py` → `decision-playbooks-store` |
| `playbook-distilling` | keep (by hand); convert Steps | yes (convert) | none |
| `playbook-ratification` | keep (the owner's session) | optional | `playbook_index.py` → `decision-playbooks-index` |
| `recording-harvest` | keep (by hand); convert Steps | yes (convert) | `loom_harvest.py` → `decision-playbooks-loom-harvest` |
| copied in: `orchestration-workstream`, `task-stack-workstream`, `fact-check` checklist | copies | no | `task-stack-apply` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `fact-check` agent (reporting) | in (dispatch) | copy the checklist; `decision-playbooks-reviewer` runs it |
| `task-stack-workstream` / `task_stack_apply.py` (productivity) | in (finish step) | copy in |
| `orchestration-workstream` (software) | in | copy in |
| chief-of-staff | none | no route today |

**Automations to update:** `knowledge-doctrine`:
- Agent → `decision-playbooks-curator`.
- `Agent(decision-case-miner, playbook-distiller, fact-check)` → `Agent(decision-playbooks-worker, decision-playbooks-reviewer)`.
- Finish step: `task_stack_apply.py` → `task-stack-apply`.
- Any finish step that records cases into the store (`decision_store.py add-case` from the Run's case files) → `decision-playbooks-store`.
- Read access to the playbook folder and the queue stays a Context or settings matter.

**Merge candidates for later:** none inside the department. `recording-harvest` could become a mode of the curator, using the same "top up when short" rule. Risk: Loom cookies and downloads in an unattended run.

**Risks and open questions**
1. The four by-hand skills write to the store and to ratified folders. They must stay owner-started, and the curator's "Never" list must keep forbidding those paths.
2. Is the fact-check reviewer worth its cost for a draft that the owner ratifies line by line anyway? It is the department's only independence, so keep it 1:1 and measure.

**Effort:** S. One small orchestrator, 3 commands, a handful of Steps conversions.

**Order:** plugin and commands → `playbook-workstream` sections and Steps → curator with worker and reviewer → Automation → retire the 3 agents → convert the four by-hand skills' Steps.

---

### toolbox-maintenance

**Today:** 8 agents (2 main), 3 skills, 8 scripts (plus `_common.py`).
- **The weekly audit** judges the whole toolbox against its design, check and lints. It makes narrow frontmatter fixes on a review branch and gives the owner one ranked list. An activity auditor covers the Portal side: runs, cost, drafts, contact pressure.
- **The monthly skill harvest** mines past Claude Code and Codex sessions for repeated manual work and stages drafts of the owner's picks on a review branch.

Neither job merges, pushes or edits the live checkout.

**Plugin:** `toolbox-maintenance`, one plugin.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| `toolbox-audit-orchestrator` | `toolbox-maintenance-auditor` | Each week: judge the scan, merge and rank the findings, have the narrow fixes made in the Run's worktree, check them, file the owner's top tasks. | **worker**: three judging slices in parallel, the activity audit (isolated Portal reading), and the fix in the worktree (keeps Edit out of the main agent). **reviewer**: every finding and fix (independence). | `estate-audit` |
| `skill-harvest-orchestrator` | `toolbox-maintenance-skill-harvester` | Each month: mine each scope's sessions into one candidate list and review the skills inbox; in the draft pass, draft and check the owner's picks for a review branch. | **worker**: one per scope, one per pick (parallel). **reviewer**: each draft (independence). | `skill-harvest` |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `toolbox-audit-analyst` | 25 | section "Judge a group of sections" of `toolbox-audit-workstream`, by worker (3 in parallel) | |
| `activity-auditor` | 100 | section "Audit the automation's activity" of `toolbox-audit-workstream`, by worker | Also usable alone. Chief-of-staff gets it by launching the audit, not by dispatch. |
| `toolbox-audit-fixer` | 29 | section "Fix within the rule" of `toolbox-audit-workstream`, by worker | `toolbox_audit_fix.py verify` stays the guard. |
| `toolbox-audit-checker` | 32 | reviewer checklist "Check findings and fixes" of `toolbox-audit-workstream` | Keep "fable for a description it judges close". |
| `skill-harvest-worker` | 22 | sections "Mine one scope" (skills-extract steps 1 to 4) and "Draft one pick" of `skill-harvest-workstream`, by worker | |
| `skill-harvest-checker` | 24 | reviewer checklist "Check a skill draft" of `skill-harvest-workstream` | Needs `toolbox-maintenance-name-check` in the reviewer's tools. |

**Reviewer:** `toolbox-maintenance-reviewer`. Read-only, plus `Bash(toolbox-maintenance-audit-fix verify:*)` and `Bash(toolbox-maintenance-name-check:*)`. It checks audit findings (evidence against `scan.json`, one fix each, the fix diff against the fix rule) and skill drafts (house format, privacy, coverage). Briefed with "Check findings and fixes" and "Check a skill draft". No shared checklist needed.

**Worker:** `toolbox-maintenance-worker`: Read, Glob, Grep, Write, Edit, Skill, the skills-extract commands, `toolbox-maintenance-audit-fix verify`, and the Portal reads the activity audit needs (`agent_run_stats`, `list_agent_runs`, `list_entities`, `get`, `search`, `activity_stream`). Slices: 3 judging groups, the activity audit, the fix, per-scope mining, per-pick drafting.

**Skills**

| skill | change | `## Steps`? | scripts → commands |
|---|---|---|---|
| `toolbox-audit-workstream` | keep; add the sections above; move the orchestrator's 7-step session here. **Rewrite "The agent file standard" and "The design pattern" judging for the new pattern** (see risk 1). | **yes**: 1 orient → 2 [hand-off: worker] judge ×3 plus activity, in parallel → 3 [judgment] merge and rank → 4 [hand-off: worker] fix (→ dry run: step 5) → 5 [hand-off: reviewer] check (→ FAIL: step 4, max 1) → 6 [judgment] tasks → 7 [script] `toolbox-maintenance-audit-check AUDIT --run RUN` (→ fails: step 3, max 1) → 8 report → done | `toolbox_audit_scan.py` → `toolbox-maintenance-audit-scan`; `toolbox_audit_fix.py` → `toolbox-maintenance-audit-fix`; `toolbox_audit_check.py` → `toolbox-maintenance-audit-check`; `toolbox_audit_record.py` → `toolbox-maintenance-audit-record` |
| `skill-harvest-workstream` | keep; add sections "Mine one scope", "Draft one pick", "Check a skill draft"; move the orchestrator's 4 steps here | **yes** | `skill_harvest_branch.py` → `toolbox-maintenance-skill-harvest-branch` |
| `skills-extract` | keep (owner-started; already in the Sentinel step format). Update `rules.md`'s house format to the new pattern (plugin department, `## Steps`, `bin/` wrappers, no `-orchestrator`). | has it | `session_pack.py` → `toolbox-maintenance-session-pack`; `skill_inventory.py` → `toolbox-maintenance-skill-inventory`; `name_check.py` → `toolbox-maintenance-name-check` |
| copied in: `orchestration-workstream`, `task-stack-workstream` | copies | no | `task-stack-apply` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `orchestrator-scaffold` lint (software), run by `toolbox_audit_scan.py` via a glob over the toolbox repo | in (reads the repo as data) | keep: the scan reads the checkout as data, not as a plugin. Retarget it to the new standard. |
| `scripts/toolbox_check.py` at the toolbox root | in (data) | keep; it already checks `bin/` against the scripts |
| `task-stack-apply` (productivity), called by `toolbox_audit_record.py` / finish | in | copy in |
| `orchestration-workstream` (software) | in | copy in |
| chief-of-staff routes "the automation checked on itself" here | out | the chief-of-staff hand-off (launch) |
| chief-of-staff's improvement step | overlap | merge candidate (below) |

**Automations to update**
- `estate-audit`:
  - Agent → `toolbox-maintenance-auditor`.
  - Prepare: `toolbox_audit_scan.py`, `toolbox_audit_fix.py open` → commands. Finish: `toolbox_audit_record.py`, `toolbox_audit_fix.py commit`, `task_stack_apply.py` → commands.
  - Precheck: `toolbox_audit_check.py --precheck` → command.
  - In-session rules → `Bash(toolbox-maintenance-audit-check:*)` and `Bash(toolbox-maintenance-audit-fix verify:*)`.
  - `Agent(4 names)` → worker and reviewer.
- `skill-harvest`:
  - Agent → `toolbox-maintenance-skill-harvester`.
  - Finish: `skill_harvest_branch.py` → command.
  - The workers' `Bash(python3 …/skills-extract/scripts/*.py:*)` rules → the three commands.
  - `subagents:` → worker and reviewer.

**Merge candidates for later**
- **Skill harvest as a mode of the auditor.** The architecture review proposes it: same repo, both stage work on review branches. Risk: different cadence, rules files and folders (harvest folder vs audit folder). By the review's own merge rule ("same folder and rules file") they are still two jobs.
- **Chief-of-staff's improvement into the audit.** Risk: covered in chief-of-staff.

**Risks and open questions**
1. **The audit judges against the old pattern.** `toolbox_audit_scan.py` finds orchestrators by the `-orchestrator` suffix. It lints them with the scaffold's ADR 0003 standard (`## Team`, stages A to E, `## Context`/`## Approach`), and its `SCRIPT_REF` regex expects `~/.claude/skills/<skill>/scripts/...`. Once departments convert, every new main agent goes unrecognised, every specialist that became a section disappears from `teams`, and script use through `bin/` commands reads as "unused". The scan, `toolbox-audit-workstream`'s "agent file standard" and "design pattern" sections, and the software `orchestrator-scaffold` standard must be updated to the new pattern:
   - one plugin manifest per department;
   - main agents of about 40 lines with Goal, Inputs, Done, Never, `skills:` and `tools:`;
   - `<dept>-reviewer` and `<dept>-worker`;
   - `## Steps` in each main job's skill;
   - `bin/` matching the scripts;
   - copied skills identical to their source;
   - no `skills:` entry or `Agent(...)` grant naming another department's piece.

   Do this early so the audit can police the migration instead of filling with false findings.
2. `skill_inventory.py` looks in the user, project, plugin and Codex skills folders. After `~/.claude/skills` is unlinked it must read the department plugins' `skills/` too, or every toolbox skill reads as not installed.
3. `skill_harvest_branch.py` hard-codes `~/.claude/skills/skills-extract/scripts/name_check.py`. It should call the sibling script by its own path, or `toolbox-maintenance-name-check`.
4. The fix rule's paths (`<department>/agents/<name>.md`, `<department>/skills/<name>/SKILL.md`) still fit. A fix to a copied skill must go to its source, or the copy check fails.
5. The skill harvest's drafts land as `<department>/skills/<name>/`. A new skill with scripts also needs `build_bins.py` run on the branch, or `toolbox_check.py` fails the commit.

**Effort:** M to L. The 1:1 conversion is M (two orchestrators, six specialists, 8 commands). The scan and standard rewrite for the new pattern adds the L, and the rest of the migration depends on it.

**Order:**
1. Update the scan and standard to the new pattern, as soon as the software department settles the pattern, before the other departments convert.
2. Plugin and commands, worker and reviewer.
3. The auditor, then dry and live runs, then retire the 4 audit agents.
4. The skill harvester, then retire the 2 harvest agents.
5. Fix `skill_inventory.py` and `skill_harvest_branch.py` for plugin layouts.

---

### Suggested order across these five
1. **toolbox-maintenance's scan update**, so the audit checks the new pattern.
2. **recurring-summaries**: the planned next department and trial 1. It needs the copy mechanism, so build that alongside.
3. **decision-playbooks**: small; it confirms the reviewer-with-copied-checklist shape.
4. **strategy.**
5. **The rest of toolbox-maintenance.**
6. **chief-of-staff last**: it needs every other department's catalogue and Automations to exist.

---

I edited nothing. Every agent file in these five departments was read in full, along with each skill's headings, the productivity agents and skills that sales and learning dispatch, the unslop family and brand-guide. Every unslop and brand-guide reference across the toolbox was then checked by hand.

## Findings that apply to all five departments

1. **Sentinel draws only one `## Steps` per skill, and only for one agent.** `engine/skillsteps.py` matches exactly `## Steps`, and Sentinel draws from the first of an agent's skills that has one. Two places have one skill serving two jobs: `bd-workstream` (pipeline and lead intake) and `marketing-content-workstream` (posts and case study). For these, I propose a thin job skill per main agent that holds `## Steps` and that job's DONE list. The shared conduct and shapes stay in the existing workstream skill, which gets no Steps. The other option is a Sentinel change, such as `## Steps` scoped to one agent.
2. **Copies get the department's prefix on their commands.** `build_bins.py` prefixes every script with the department name. So a copied `task_stack_apply.py` becomes `compliance-task-stack-apply`, `sales-task-stack-apply` and so on, and two plugins never collide on PATH. A whole-skill copy also wraps scripts the department never uses: copying `office-files` adds a `*-powerpoint-handler` command too. **Open question:** do copies always take the whole skill?
3. **The unslop sub-skills need the router.** Each sub-skill starts with "apply the five universal principles from the router" and relies on the router's `symptoms.md`. Any department that copies a sub-skill also copies `unslop` and `symptoms.md`.
4. **Specialists' model tiers.** Several specialists run on opus today: the nudge drafter, pursuit analyst, proposal drafter and community writer. `software-worker` runs on sonnet. Before moving drafting in the owner's voice to a `<dept>-worker`, either give the worker opus or pass a model on each dispatch.
5. **`Agent(...)` rules.** Today's agents grant either bare `Agent` (compliance, sales, marketing, learning) or a named list (personal). New main agents should grant `Agent(<dept>-worker, <dept>-reviewer)`, or only the reviewer where there is no worker.

The shared reviewers become checklist skills copied into each department that uses them. I call them `fact-check`, `executive-red-team`, `completeness-audit` and `numbers-review` below. Plugin namespacing keeps them apart, for example `personal:fact-check`.

---

### compliance

**Today:** 8 agents (3 main), 3 skills, 0 scripts. The department keeps an organisation's legal deadlines from slipping, in three jobs:
- A weekly compliance calendar: every filing, renewal and registration is placed on evidence, and owner tasks are proposed as a task-stack change set.
- IT and AI governance in three modes: control evidence per period, a review of one third-party AI tool, and the annual policy refresh gap list.
- Driving one legal entity's wind-down to dissolution, with filing packets prepared but never filed.

It borrows `task_stack_apply.py` (after the session) and `office-files` (`pdf_handle`, `excel_handle`) from productivity. Its `compliance-evidence-checker` also serves accounting's audit support.

**Plugin:** `compliance`, one plugin. IT governance has a different folder and rules file, but the same buyer (the controller or operations lead) and the same "evidence, not claims" stance. Two plugins would buy nothing.

**Main agents**

| current | proposed | what it does | dispatch after | Automation |
|---|---|---|---|---|
| compliance-calendar-orchestrator | `compliance-calendar-keeper` | Each week, places every calendar item's current occurrence on evidence and proposes owner tasks and calendar changes. | **worker** (batches of about 15 items by entity, in parallel); **reviewer** (evidence check on every `filed`, `not-applicable` and `complete` claim, for independence) | compliance-calendar |
| it-governance-orchestrator | `compliance-it-governance` | Places a period's controls on artifacts, reviews one AI tool, or writes the policy-refresh gap list, as the mode says. | **worker** (batches of about 15 controls by owner role, in parallel); **reviewer** (evidence check, fact-check of the tool review, completeness audit plus two fact-checks for the refresh) | it-governance |
| wind-down-orchestrator | `compliance-entity-wind-down` | Places each step of one entity's wind-down on evidence, prepares the next filing packets and proposes owner tasks. | **reviewer** only (completeness against the reference sequence; fact-check of dates, amounts and file numbers); there is one entity per Run, so no worker | entity-wind-down (possibly one per entity) |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| compliance-calendar-tracker | 19 | Section "Place a batch" of `compliance-calendar-workstream`, run by the worker | Read-only Portal tools, including `email_bodies`, go to the worker. |
| compliance-evidence-checker | 18 | Reviewer checklist: a new small skill, `evidence-check` (the four questions plus the return), whose source lives in compliance and is copied to accounting | Today it is shared across three workstream skills. The bar stays each workstream's own evidence standard. |
| it-governance-collector | 19 | Section "Place a batch of controls" of `it-governance-workstream`, run by the worker | It ran on sonnet; the worker's default fits. |
| it-governance-tool-reviewer | 17 | Section "Review an AI tool" of `it-governance-workstream`, run by the main agent | Needs WebSearch and WebFetch. See risk 2: a worker may be safer. |
| wind-down-planner | 25 | Section "Plan the wind-down" of `wind-down-workstream` (it uses the existing "The filing packet"), run by the main agent | `pdf_handle` and `excel_handle` move onto the main agent as `compliance-pdf-handle` and `compliance-excel-handle`. |

**Reviewer: `compliance-reviewer`.** It works from the sources alone and edits nothing. It is briefed with:
- `evidence-check` (new; compliance is the source);
- the copied `fact-check` and `completeness-audit` checklists;
- the job skill's evidence standard: `compliance-calendar-workstream` "Placing an occurrence" and `it-governance-workstream` "Control states".

Its tools are Read, Glob and Grep; Portal `get`, `search` and `email_bodies`; `compliance-pdf-handle` (filed copies are usually PDFs); and WebFetch, needed to fact-check a tool review's vendor URLs.

**Worker: `compliance-worker`.** It is needed for the calendar batches and the control batches, both parallel. It is not needed for wind-down.

**Skills**

| skill | action | `## Steps`? | scripts → commands |
|---|---|---|---|
| compliance-calendar-workstream | Keep. Add "Place a batch". Move the agent's six steps here. | Yes. Orient → worker per batch → reviewer on claims, with "→ FAIL: item back to due" → record → DONE. | None. The planned "Later tools" names `compliance-check` and `compliance-record` already fit the prefix rule. |
| it-governance-workstream | Keep. Add "Place a batch of controls", "Review an AI tool" and "Refresh the policy library". | Yes. One list, with branches on `governance_mode` after step 1. | None. Planned `governance-check` and `governance-record` would become `compliance-governance-*`; rename them in "Later tools". |
| wind-down-workstream | Keep. Add "Plan the wind-down". | Yes. Orient → plan (judgment) → reviewer completeness and fact-check in parallel, with "→ gap: step 2 (max 1)" → task ops → record → DONE. | None. Planned `wind-down-check` and `state-filing-lookup` would become `compliance-wind-down-check` and `compliance-state-filing-lookup`. |
| evidence-check (new) | New checklist skill | No | None |
| copies: `orchestration-workstream`, `task-stack-workstream`, `office-files`, `fact-check`, `completeness-audit` | Copies, made by the build step | No | `compliance-task-stack-apply`, `-check`, `-queue`, `-report`; `compliance-pdf-handle`, `compliance-excel-handle` (plus `compliance-powerpoint-handler` if whole skills are copied) |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `orchestration-workstream` | software → compliance | Copy in. |
| `task-stack-workstream` and `task_stack_apply.py` | productivity → compliance | Copy in. The finish step calls `compliance-task-stack-apply`. |
| `office-files` | productivity → compliance | Copy in. |
| fact-check, completeness-audit | reporting, process-engineering → compliance | Copy the checklist skills in. |
| `compliance-evidence-checker` used by `audit-support-orchestrator` | compliance → accounting | Copy `evidence-check` into accounting; `accounting-reviewer` uses it. |
| "Not for 1099s (vendor-1099-orchestrator)" and "use audit-support-orchestrator" pointers | text only | Reword to "the accounting plugin's 1099 job", or drop. |

**Automations to update**
- **compliance-calendar:** change the agent line to `compliance-calendar-keeper`; add the `compliance` plugin dir; set subagents to `compliance-worker` and `compliance-reviewer`. The finish step's by-path `task_stack_apply.py` becomes `compliance-task-stack-apply`. The `rules_file` input is unchanged.
- **it-governance:** change the agent line; set the same subagents. The main session (or the worker; see risk 2) must now be allowed WebSearch and WebFetch for tool-review mode. The `governance_mode` input is unchanged.
- **entity-wind-down:** change the agent line. The by-path `pdf_handle` and `excel_handle` rules, which were on the planner, become `Bash(compliance-pdf-handle:*)` and `Bash(compliance-excel-handle:*)` on the main session; keep `mkdir -p`. The finish step becomes `compliance-task-stack-apply`. Subagents: `compliance-reviewer`.

**Merge candidates for later**
- **Calendar plus wind-down into one `compliance` agent with modes** (the architecture review's idea). Reason: both are entity filings placed on evidence, ending in a task-stack change set. Risk: different rules files and folders, and wind-down is episodic and per entity while the calendar is weekly across entities.
- **Accounting's vendor-1099 job as a season of the calendar keeper.** Reason: the 1099 deadline is itself a calendar item. Risk: this crosses departments, and the 1099 job needs AP data and `numbers-review`.

**Risks and open questions**
1. `evidence-check` will exist in two plugins. The build-step copy and the identity check have to cover a checklist that compliance owns, not only productivity and software skills.
2. Running the AI tool review on the main session puts untrusted vendor web pages into a session that has Write and Portal tools. Dispatching the "Review an AI tool" section to `compliance-worker` would isolate it, at the cost of a dispatch. **Owner's call.**
3. The wind-down planner wrote into the wind-down folder's `agent/prepared/`. With the main agent doing that work, the Never list must still say "write beside the owner's files, never edit them".
4. The calendar keeper's Steps live in the agent file today. Moving them into the skill must not lose "a FAIL drops the op; record why".
5. Is the entity-wind-down Automation one per entity? If so, it is several sidecars to update.

**Effort: M.** There are no scripts of its own. The work is three jobs, five copied skills, and the new `evidence-check` that accounting also needs. **Order:** compliance-calendar-keeper first (it exercises worker, reviewer and the finish command), then compliance-it-governance (three modes), then compliance-entity-wind-down.

---

### personal

**Today:** 11 agents (5 main), 6 skills, 0 scripts. The department runs the owner's private household domains:
- a weekly health check-in against their own goals (draft);
- a weekly home-infrastructure health read, with at most one retirement proposal (draft);
- a household "chief of staff" for one household member's one pain point, which starts with an interview;
- a monthly household finance review prepared from a local review engine;
- tax season worked like a PBC list.

Nothing goes to the Portal and no one is messaged. `personal-workstream` holds the privacy fences.

**Plugin:** `personal`, one plugin, never enabled in work sessions. No split is needed: all five jobs share the same privacy conduct and folder shape.

**Main agents**

| current | proposed | what it does | dispatch after | Automation |
|---|---|---|---|---|
| health-routine-orchestrator | `personal-health-check-in` | Sets the week's metrics against the owner's targets with trend, and lists dates due in 30 days. | **reviewer** (fact-check every value against the saved source copies) | health-routine |
| home-infrastructure-orchestrator | `personal-home-infrastructure-check` | Gives each host a fine or needs-attention verdict from granted read-only commands and exports, with at most one retirement proposal. | **reviewer** (the retirement proposal only, when there is one) | home-infrastructure |
| household-orchestrator | `personal-household-keeper` | Writes the interview first; then each week keeps one pain point's obligations ledger and writes a half-page page. | **reviewer** (fact-check every new or changed row's date) | family-household (possibly one per member) |
| personal-finance-review-orchestrator | `personal-finance-review-prep` | Answers the month's checks from the engine's derived outputs and writes the one-page agenda. | **reviewer** (numbers review re-derives every figure) | personal-finance-review |
| personal-tax-season-orchestrator | `personal-tax-season-checklist` | Builds and matches the document checklist and lists what is still owed. | **reviewer** twice in parallel (fact-check of matches; completeness against the prior year) | personal-tax-season |

None of the five needs a worker. Every specialist is a single, sequential slice.

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| health-routine-analyst | 23 | Section "Read the week" of `health-routine-method`, run by the main agent | Draft. The private export paths or command grants move to the main session. |
| home-infrastructure-analyst | 23 | Section "Read the estate" of `home-infrastructure-method`, run by the main agent | Draft. Same point about private grants. |
| home-infrastructure-checker | 19 | Reviewer checklist "Check the retirement proposal" in `home-infrastructure-method` | The reviewer needs the same private read-only grants to re-run the command. |
| household-steward | 20 | Section "Keep the ledger" of `household-method`, run by the main agent | Its "propose rows, orchestrator records" split collapses. |
| personal-finance-review-analyst | 20 | Section "Answer the checks" of `personal-finance-review-method`, run by the main agent | |
| personal-tax-season-analyst | 20 | Section "Build and match the checklist" of `personal-tax-season-method`, run by the main agent | |

**Reviewer: `personal-reviewer`.** It has Read, Glob and Grep only: no Portal, no web, no shell beyond private grants the owner adds per Automation. It loads `personal-workstream` first, because the fenced folders bind the reviewer too. Its checklists are the copied `fact-check`, `numbers-review` and `completeness-audit`, plus `home-infrastructure-method` "Check the retirement proposal". **Worker:** not needed.

**Skills**

| skill | action | `## Steps`? | scripts → commands |
|---|---|---|---|
| personal-workstream | Keep. Rewrite "a worker returns; the orchestrator records" as "the main agent records; the reviewer never writes". | No (shared conduct) | None. Planned `personal-folder-check` already fits. |
| health-routine-method | Keep. Add "Read the week". | Yes | None |
| home-infrastructure-method | Keep. Add "Read the estate" and "Check the retirement proposal". | Yes. Includes "→ no proposal: step 5". | None |
| household-method | Keep. Add "Keep the ledger". | Yes. "→ interview empty: stop" after step 2. | None |
| personal-finance-review-method | Keep. Add "Answer the checks". | Yes. "→ FAIL: step 3 (max 1)". | None |
| personal-tax-season-method | Keep. Add "Build and match the checklist". | Yes | None |
| copies: `orchestration-workstream`, `fact-check`, `numbers-review`, `completeness-audit` | Copies | No | None |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `orchestration-workstream` | software → personal | Copy in. |
| fact-check, numbers-reviewer, completeness-audit | reporting, process-engineering → personal | Copy the checklists in. |
| `comms-confirm` | productivity | Drop. It is already forbidden here, because it writes to the Portal. Do not copy it. |
| "Not for a company's 1099s (vendor-1099-orchestrator)" pointer | text only | Reword or drop. |

**Automations to update.** All five change the agent line, take the `personal` plugin dir, and set subagents to `personal-reviewer` (today they name the analyst plus fact-check, numbers-reviewer or completeness-audit). For health-routine and home-infrastructure, the owner's private read-only command or export grants, which today sit on the analyst and checker, move to the main session. For home-infrastructure, the reviewer also needs them. No script paths change.

**Merge candidates for later**
- **Finance review plus tax season** (the architecture review's `personal-finance`). Reason: same owner, a financial archive, PBC-style checking. Risk: different rules files, folders and cadence (monthly versus seasonal), and different checklists.
- **Household plus home infrastructure plus health** (the review's `household`). Reason: all weekly, private and with the same shape. Risk: one agent with read access to health exports, a household member's domain and the home estate widens what a mistake can reach. The privacy fences argue against this merge.

**Risks and open questions**
1. Health and home infrastructure are `maturity: draft` and need private grants, so they cannot be tested end to end after the conversion.
2. Is the household Automation one per household member? If so, there are several sidecars.
3. The reviewer must be told the fenced-folder list explicitly, since it judges from sources and could otherwise open a fenced path that a claim cites.
4. Should the `maturity: draft` frontmatter carry over to the new main agents?

**Effort: S–M.** Five uniform jobs, no scripts, three checklist copies. **Order:** finance review (runnable, exercises numbers review), then tax season, then household, then the two drafts (health, home infrastructure).

---

### sales

**Today:** 6 agents (3 main), 2 skills, 0 scripts. Business development, in three jobs:
- A weekly pipeline pass: every pursuit gets a dated next step, and each stuck one gets a drafted, checked nudge.
- Same-day inbound lead intake: research, a one-page brief with a fit score, and a staged reply.
- One pursuit's proposal or SOW drafted from the owner's precedent, with its contract documents audited.

Five productivity agents do the research, drafting and draft checking today, about 430 lines of agent text: `person-researcher`, `email-researcher`, `domain-researcher`, `email-drafter` and `comms-draft-checker`.

**Plugin:** `sales`, one plugin. The `bd-` prefix gives way to `sales-` for agents.

**Main agents**

| current | proposed | what it does | dispatch after | Automation |
|---|---|---|---|---|
| bd-pipeline-orchestrator | `sales-pipeline-review` | Reads the pipeline from the system of record, gives every pursuit a dated next step, drafts a nudge per stuck pursuit and proposes task ops. | **worker** (pursuit batches of about 10 in parallel; one nudge draft each, in parallel; a person or thread research pass when a batch asks); **reviewer** (each staged draft, for independence) | bd-pipeline |
| bd-lead-intake-orchestrator | `sales-lead-intake` | Pins one inbound lead, researches person and thread, writes the brief with a fit score, stages the reply and proposes the pursuit. | **reviewer** (the reply draft). No worker: it is one lead, and the two research reads are small. | bd-lead-intake (event-triggered) |
| bd-proposal-orchestrator | `sales-proposal-writer` | Drafts one proposal or SOW from discovery notes and the owner's precedent, with price and terms left as placeholders, and revises once; pass `audit` audits documents only. | **reviewer**, three in parallel (contract audit, fact-check, red team), then the contract audit again on the revision. No worker. | bd-proposal |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| bd-pursuit-analyst | 21 | Sections "Judge a batch of pursuits" (run by the worker) and "Write the lead brief" (run by the main agent in lead intake) of `bd-workstream` | |
| bd-proposal-drafter | 24 | Section "Draft the proposal" of `bd-proposal-workstream`, run by the main agent | Loads the `unslop-proposal` copy. |
| bd-contract-auditor | 22 | Reviewer checklist: "The contract audit" in `bd-proposal-workstream`, renamed "Audit the contract documents" | Also the whole job in `pass: audit`. |
| domain-researcher (productivity) | 120 | Section "Read the pipeline" of `bd-workstream` (BD domain hierarchy → open pursuits), run by the main agent | Keep only the BD-relevant query recipe, not the general domain brief. |
| person-researcher, email-researcher (productivity) | 90 + 85 | Section "Research a person and a thread" of `bd-workstream`, run by the main agent (lead intake) or the worker (pipeline, when a batch asks) | Prefer a copy if productivity turns them into a method skill (see risk 1). |
| email-drafter (productivity) | 118 | A copy of `email-drafter-method` plus `unslop` and `unslop-email`, used through a new section "Draft a message", run by the worker for pipeline nudges and the main agent for the lead reply | The section holds the BD brief: recipient, thread ref, nudge or reply intent, copy rules from BD-RULES.md, `agent_slug`. Needs `draft_create` and `draft_update`. |
| comms-draft-checker (productivity) | 19 | A copy of `comms-draft-check` as the reviewer checklist | Brings `outbound_check.py` as `sales-outbound-check`. |

**What sales needs of its own** (the part of the brief that asks for a design):
- In `bd-workstream`: "Read the pipeline", "Judge a batch of pursuits", "Research a person and a thread", "Write the lead brief" and "Draft a message".
- Two thin job skills, `sales-pipeline` and `sales-lead-intake`, each with `## Steps` and its own DONE list, moved out of `bd-workstream`.
- Copies: `email-drafter-method`, `comms-draft-check`, `unslop`, `unslop-email`, `unslop-proposal`, `orchestration-workstream`, `task-stack-workstream`, `office-files`, `comms-confirm`, `fact-check`, `executive-red-team`.
- Before every nudge draft, the drafter (main or worker) runs `sales-outbound-check`. This replaces the prose rule "not inside relationship tending's cooldown": the cooldown days go in BD-RULES.md and the check runs in code.

**Reviewer: `sales-reviewer`.** It is briefed with `comms-draft-check` (copied), `bd-proposal-workstream` "Audit the contract documents", and the copied `fact-check` and `executive-red-team`. Its tools are Read, Glob and Grep; Portal `get`, `search`, `list_entities` and `email_bodies`; `sales-pdf-handle`; and `sales-outbound-check`.

**Worker: `sales-worker`.** It is needed for the pipeline only: pursuit batches, nudge drafts and research passes. It needs Portal read tools plus `draft_create` and `draft_update`, and opus or a per-dispatch model for drafting in the owner's voice.

**Skills**

| skill | action | `## Steps`? | scripts → commands |
|---|---|---|---|
| bd-workstream | Keep as the shared reference (renaming it `sales-bd-workstream` is optional). Add the five sections above. Move both DONE lists out. | No | None |
| sales-pipeline (new, thin) | New job skill | Yes. Orient → [judgment] read the pipeline → [hand-off: sales-worker] judge the batches → [hand-off: sales-worker] draft the nudges → [hand-off: sales-reviewer] check, "→ FAIL: step 4 (max 1)" → record → [ask] questions → DONE. | None |
| sales-lead-intake (new, thin) | New job skill | Yes. Pin, "→ already a pursuit: stop" → research → brief → draft → [hand-off: sales-reviewer], "→ FAIL: step 4 (max 1)" → propose pursuit → DONE. | None |
| bd-proposal-workstream | Keep (renaming it `sales-proposal-workstream` is optional). Add "Draft the proposal". Rename the audit section. | Yes. "→ pass audit: step 3" after orient. | None |
| copies (listed above) | Copies | No | `sales-outbound-check`; `sales-task-stack-apply` (+ `-check`, `-queue`, `-report`); `sales-pdf-handle` (+ excel, powerpoint); `sales-confirm`, `sales-confirm-portal`, `sales-waiting` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| email-drafter, comms-draft-checker | productivity → sales | Copy `email-drafter-method` and `comms-draft-check`, with its script. |
| person-, email- and domain-researcher | productivity → sales | Sales-owned sections now; switch to a copy if productivity publishes a research method skill. |
| `unslop`, `unslop-email`, `unslop-proposal` | marketing → sales | Copy in. |
| `task-stack-workstream` and apply | productivity → sales | Copy in. Change sets are proposed in `changes.json`. |
| `comms-confirm` | productivity → sales | Copy in to stay 1:1, or drop in favour of the report's numbered list or Sentinel's own asks (open question). |
| `office-files` | productivity → sales | Copy in. |
| fact-check, executive-red-team | reporting → sales | Copy the checklists in. |
| Relationship-tending cooldown (`crm-relationship-tending-orchestrator`) | productivity → sales (rule) | Drop the reference. `sales-outbound-check` plus a cooldown in BD-RULES.md enforce it. |
| Pipeline "sends new leads to intake" | inside sales, main → main | Hand-off: the pipeline lists each new lead as a `for_owner` item ("launch sales-lead-intake for portal://…"), or files a Portal task that the lead-intake Automation's trigger picks up. It never dispatches. |

**Automations to update**
- **All three:** change the agent line; take the `sales` plugin dir.
- **bd-pipeline:** subagents become `sales-worker` and `sales-reviewer`, replacing six named agents. The `draft_create` and `draft_update` grants move from email-drafter to the worker's session allowlist. If the sidecar runs `task_stack_apply.py` or `confirm.py` by path, change them to `sales-task-stack-apply` and `sales-confirm`.
- **bd-lead-intake:** subagents become `sales-reviewer`. The main session now needs `draft_create` and `draft_update` plus `email_bodies`. Keep its inbound-lead trigger.
- **bd-proposal:** subagents become `sales-reviewer`. By-path `pdf_handle` rules become `Bash(sales-pdf-handle:*)`.

**Merge candidates for later**
- **Pipeline plus lead intake.** Reason: lead intake calls itself "a mode of the weekly pipeline pass, kept separate for its event trigger". Risk: one agent then serves both a weekly schedule and a same-day event trigger, and the event path must stay fast.
- **All three into one `sales-bd` agent** (the architecture review's idea). Risk: the proposal job has a different folder, office files and three checkers. I do not recommend merging it.

**Risks and open questions**
1. The research sections are written from about 300 lines of productivity agent text. If productivity converts its researchers into a skill, sales should copy it rather than keep a fork. This needs coordinating with the productivity plan.
2. Drafting in the owner's voice moves from one agent (`email-drafter`, "the only place drafts are made") to sales' own section. The voice-guide procedure stays identical only if `email-drafter-method` is an exact copy.
3. Today, `draft_create` sits only on email-drafter. The worker or the main agent will now hold a Portal write, so its session allowlist matters.
4. Should `comms-confirm` (three commands, Portal writes) be copied, or replaced by Sentinel's asks?
5. Every draft in the owner's voice ran on opus. A sonnet worker would be a quality step down.

**Effort: M–L.** It is driven by eleven copied skills, five sections written from productivity agents, and Portal write tools moving. **Order:** `sales-proposal-writer` first (fewest productivity dependencies), then `sales-lead-intake` (one draft, exercises the draft check), then `sales-pipeline-review` (worker in parallel).

---

### marketing

**Today:** 4 agents (2 main), 8 skills, 0 scripts. The owner's public writing: an editorial run that mines finished work for candidate posts and drafts them anonymised and sourced, and one case study from a closed engagement, held as internal until the owner records consent. Marketing is also the home of the unslop writing cleaners (a router plus five reader-specific sub-skills) and `brand-guide`, which most departments use.

**Plugin:** `marketing`, one plugin. **Decision needed:** where the source of the shared family lives. Marketing's own jobs use only `unslop`, `unslop-editorial` and `brand-guide`. I recommend the build step's single source sit in a neutral non-plugin folder (for example `shared/skills/`), with marketing taking copies like everyone else. Otherwise the marketing plugin carries four sub-skills it never uses.

**Main agents**

| current | proposed | what it does | dispatch after | Automation |
|---|---|---|---|---|
| marketing-content-orchestrator | `marketing-post-writer` | Refreshes the candidate list from finished work and drafts the Run's posts, sourced and anonymised. | **worker** (one post each in parallel when the count is above 1; one post is drafted by the main agent); **reviewer** (anonymity and voice check plus fact-check, in parallel) | marketing-content |
| marketing-case-study-orchestrator | `marketing-case-study-writer` | Turns a closed engagement's closeout into an anonymised, sourced case study, internal until consent. | **reviewer** (public-draft check, fact-check, red team as a prospective buyer). No worker. | marketing-case-study |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| marketing-content-writer | 23 | Sections "Mine candidates" (main), "Draft a post" (worker or main), "Draft a case study" (main) and "Revise on findings" of `marketing-content-workstream` | Loads the `unslop-editorial` copy. |
| marketing-content-checker | 23 | Reviewer checklist "Check a public draft" in `marketing-content-workstream` (anonymity, topic rule, voice and length, no promise) | |
| content-scout (obsidian, optional) | 20 | Drop the dispatch. Marketing reads the scout's distillations in the research folder as a source the rules allow. | A file hand-off; no agent crosses. |

**Reviewer: `marketing-reviewer`.** It is briefed with "Check a public draft" plus the copied `fact-check` and `executive-red-team`. It must get the client list the rules name and never the writer's notes. Tools: Read, Glob, Grep.

**Worker: `marketing-worker`.** It is needed only for posts drafted in parallel. Drafting needs opus or a per-dispatch model.

**Skills**

| skill | action | `## Steps`? | scripts → commands |
|---|---|---|---|
| marketing-content-workstream | Keep as the shared reference. Add the sections above. Move both DONE lists to the job skills. | No | None |
| marketing-posts (new, thin) | New job skill | Yes. Orient → mine → pick → [hand-off: marketing-worker] draft → [hand-off: marketing-reviewer] check, "→ FAIL: step 4 (max 1)" → DONE. "→ dry run: done" after the pick. | None |
| marketing-case-study (new, thin) | New job skill | Yes. Orient, "→ not closed: stop" → consent → draft → check ×3 → revise once → DONE. | None |
| unslop (+ `symptoms.md`) | Shared source; copied to every user of a sub-skill | No | None |
| unslop-deliverable, -email, -proposal, -technical | Shared source; not used by marketing's own jobs | No | None |
| unslop-editorial | Shared source; marketing uses it | No | None |
| brand-guide (+ `voice-and-tone.md`, `worked-example.md`) | Shared source; marketing uses it | No | None |

**Which copies each department needs** (verified by reading each reference; a copy of any sub-skill always includes `unslop` and `symptoms.md`):

| department | copies | why |
|---|---|---|
| accounting | unslop, unslop-email | `firm-billing-preparer` loads unslop-email for the invoice cover note. |
| finance | unslop, unslop-deliverable | `forecast-bridge-writer` |
| process-engineering | unslop, unslop-deliverable, brand-guide | `process-flow-mapper`; the visual-system reference names brand-guide. |
| reporting | unslop, unslop-deliverable, brand-guide | `board-package-writer`, `client-update-writer`; brand tokens in comms-client-status-update. |
| projects | unslop, unslop-deliverable, unslop-email, unslop-editorial, unslop-proposal | Client-delivery prose (deliverable); engagement comms set (email); closeout case-study draft (editorial); runbook contract set (proposal). |
| productivity | unslop, unslop-email | `email-drafter` |
| sales | unslop, unslop-email, unslop-proposal | The proposal draft, plus the email-drafter-method copy for nudges and replies. |
| learning | unslop, unslop-email, brand-guide; unslop-editorial recommended | Invitation via the email-drafter-method copy; the seminar voice and deck-kit tokens use brand-guide; the router assigns teaching decks to editorial, but no learning file names it today. |
| software | unslop, unslop-technical | `software-pr`, `software-clean-docs` |
| chief-of-staff | unslop and all five sub-skills | It routes "everything drafted" through the router. |
| marketing | unslop, unslop-editorial, brand-guide | Its own jobs. |
| compliance, personal | none | No drafted prose that is meant to go out. |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| unslop family, brand-guide | marketing → 10 departments | One source; copies by the build step; an identity check (map above). |
| `orchestration-workstream` | software → marketing | Copy in. |
| fact-check, executive-red-team | reporting → marketing | Copy the checklists in. |
| content-scout | obsidian → marketing | Drop the dispatch; read its output files. |
| Closeout's `Case Study <date>.md` (projects' `project-engagement-closeout-orchestrator`) | projects → marketing | Hand-off: the closeout leaves a `for_owner` item to launch the case-study Automation for that engagement. The case-study writer reads the draft file. |

**Automations to update**
- **marketing-content:** change the agent line; take the plugin dir; subagents become `marketing-worker` and `marketing-reviewer`. Remove any content-scout grants (yt-dlp, by-path scout scripts) if the sidecar carries them.
- **marketing-case-study:** change the agent line; subagents become `marketing-reviewer`. It still needs the `engagements_dir` setting and the engagement input.

**Merge candidates for later**
- **Posts plus case study in one `marketing-writer` with a mode.** Reason: same rules file, same writer and checker, and a case study is one lane of the content library. Risk: the case study is event-triggered after a closeout and has the consent gate. Keep the gate as a step that cannot be skipped.

**Risks and open questions**
1. Where the shared source lives (see Plugin above). This decision also unblocks every other department's unslop copies.
2. The identity check must treat `symptoms.md`, `voice-and-tone.md` and `worked-example.md` as part of their skills.
3. `brand-guide` names the owner's own brand as its worked example; ten copies multiply that in a public repo. That is fine as long as it stays the owner's own brand.
4. The anonymity check is the critical gate. The reviewer must get the client list and the consent register, never the writer's notes.

**Effort:** S for marketing's two jobs. M including the shared-family copy mechanism, which marketing is the natural first user of. **Order:** settle the source location and build the copy step on the unslop family first, then `marketing-post-writer`, then `marketing-case-study-writer`.

---

### learning

**Today:** 4 agents (2 main), 2 skills, 3 scripts. Teaching, in two jobs:
- Builds or revises one seminar, workshop or lab deck as self-contained HTML, in passes: outline and questions, then build and browser-verify after approval, then a red team.
- Runs one learning-community session: before it, the agenda and an invitation staged as a Portal draft; after it, a recap traced to the transcript and fact-checked, plus the session record.

`writing-seminar-builder` holds a large deck kit (presentation library, slide types, CSS and JS) that other departments also build decks with.

**Plugin:** `learning`, one plugin.

**Main agents**

| current | proposed | what it does | dispatch after | Automation |
|---|---|---|---|---|
| learning-community-orchestrator | `learning-community-host` | Prepare pass: the agenda from members' topics and the invitation staged as a draft. Recap pass: the recap and record from the recording. | **reviewer** twice in parallel (fact-check over disjoint transcript halves). No worker. | learning-community |
| learning-seminar-orchestrator | `learning-seminar-builder` | Outline pass (content map, outline, one numbered question list); build or revise pass after approval, verified in a browser. | **reviewer** (red team as a participant, at most two rounds). No worker. | learning-seminar |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| community-writer | 22 | Sections "Write the agenda and invitation" and "Write the recap and record" of `community-workstream`, run by the main agent | The text-matched dispatch of fact-check is a mention only. |
| seminar-builder | 22 | The existing "Run by learning-seminar-orchestrator" section of `writing-seminar-builder` (outline, build and revise passes), run by the main agent | The Playwright tools move to the main agent. The text-matched dispatch of the orchestrator is a mention only. |
| meeting-analyst (productivity) | 99 | A copy of `meeting-analyst-method`, used as section "Read the recording" of `community-workstream`, run by the main agent | Use `learning-worker` only if transcripts flood the context. |
| email-drafter (productivity) | 118 | A copy of `email-drafter-method` plus `unslop` and `unslop-email`, run by the main agent for the one invitation | The main agent needs `draft_create`. |

**Reviewer: `learning-reviewer`.** It is briefed with the copied `fact-check` (two instances over disjoint halves) and `executive-red-team` (silent read first, then "starting from (a), did it deliver (b)?"). It gets the scroll view and nothing of the builder's reasoning or the content map. Its tools are Read, Glob, Grep, plus Playwright navigate and snapshot so it can read the deck as rendered.

**Worker:** not needed for the 1:1 conversion.

**Skills**

| skill | action | `## Steps`? | scripts → commands |
|---|---|---|---|
| community-workstream | Keep. Add "Read the recording", "Write the agenda and invitation" and "Write the recap and record". | Yes. "→ pass prepare: step 2 / recap: step 4" after orient; "→ CONTRADICTED: step 5 (max 1)". | None. Planned `community-pack` and `community-check` become `learning-community-pack` and `learning-community-check`. |
| writing-seminar-builder | Keep the method. **Split the deck kit out** into a new skill, `html-deck-kit` (`presentation/`: deck-kit CSS/JS, slide types, elements, learnings), sourced in learning and copied to its users. | Yes, for the orchestrated passes. The existing "The workflow" stays the interactive method. | `render_previews.py` → `learning-render-previews`. `deckbuilder.py` and `flowkit.py` are imported libraries with no main, so a wrapper would be useless: move them to `scripts/lib/` (`build_bins` skips that) and fix the import in `build-deck-howto.md`, or retire the old PPTX pipeline. The planned `seminar-check` becomes `learning-seminar-check`. |
| html-deck-kit (new) | Split from the seminar skill | No | None |
| copies: `orchestration-workstream`, `brand-guide`, `unslop`, `unslop-email` (and recommended `unslop-editorial`), `email-drafter-method`, `meeting-analyst-method`, `fact-check`, `executive-red-team` | Copies | No | None |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `orchestration-workstream` | software → learning | Copy in. |
| brand-guide, unslop, unslop-email | marketing → learning | Copy in. |
| email-drafter, meeting-analyst | productivity → learning | Copy the method skills in. |
| fact-check, executive-red-team | reporting → learning | Copy the checklists in. |
| The deck kit, used by reporting (`project-status-deck`), projects (engagement decks template), process-engineering (`workshop-design` slides) | learning → 3 departments | Copy `html-deck-kit` in; it is far smaller than copying the whole seminar skill. |
| chief-of-staff routes "a seminar built" to `writing-seminar-builder` | learning → chief-of-staff | Hand-off: chief-of-staff files a task or a `for_owner` item to launch the learning-seminar Automation. It does not copy the seminar skill. |

**Automations to update**
- **learning-community:** change the agent line; take the plugin dir; subagents become `learning-reviewer`. The main session gains `draft_create` (from email-drafter) and recording or transcript access (from meeting-analyst). `COMMUNITY-RULES.md` stays an input.
- **learning-seminar:** change the agent line; subagents become `learning-reviewer`. The Playwright MCP tools move to the main session, and the reviewer gets read-only Playwright. `training_dir` is unchanged. Add `Bash(learning-render-previews:*)` only if the PPTX path is still used.

**Merge candidates for later**
- **Community plus seminar into one `learning` agent** (the architecture review's idea). Reason: one department, one agent. Risk: different folders, rules, tools (Portal draft versus Playwright) and cadence; little is gained. I do not recommend it.

**Risks and open questions**
1. Splitting `html-deck-kit` out touches references inside `writing-seminar-builder` (DESIGN-PRINCIPLES, deck-styling, the README tokens note). Paths must be fixed in the same change.
2. Retire the PPTX pipeline (`deckbuilder`, `flowkit`, `render_previews`)? The README says the HTML deck needs none of them.
3. With the builder on the main session, the outline-approval gate ("refuse to build without approval") must be a `## Steps` branch ("→ no approval: stop"), not only prose.
4. Does the red team need a rendered view? If so, the reviewer's Playwright grant must be read-only.

**Effort: M.** It is driven by the deck-kit split and its three consumer departments, plus four copied productivity and marketing skills. **Order:** `learning-community-host` first (small, exercises the draft and fact-check flow), then the `html-deck-kit` split, then `learning-seminar-builder`.

---

### accounting

**Today:** 22 agents (9 main), 20 skills, 29 scripts (plus 7 `_common.py` helpers). Accounting keeps a company's books from one close to the next. It runs a company's month-end close the way a controller runs a close team, and a small firm's own close on the same pattern. Around the close it reconciles intercompany balances, prepares the AR and collections review, and drafts the owner's firm's monthly client invoices. It also answers routine coding questions from the transactional-definitions rulebook, runs the manufacturer's monthly product-costing review, works the W-9 backlog and builds the 1099 register, and answers the auditor's request list (PBC). Agents draft import files, invoices, registers and indexes; a person uploads, posts, sends and files.

**Plugin:** `accounting`, one plugin. The nine jobs share one core: a ledger pull, the import-file and reconciliation rules, the conduct of `month-end-workstream`, and the numbers bar. Firm-billing and firm-books serve the owner's firm while the other jobs serve client companies. That is a Context split (which folder and which rules file), not a reason for a separate plugin.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| month-end-orchestrator (141 lines) | `accounting-month-end-close` | Closes one company's month from its Month-End folder, with done computed by the check script. | **worker**: Cash, AR and Accruals run in parallel and each reads a lot. Set up and Curate run on sonnet, plus the results memo and flux investigations (today these go to `general-purpose`). **reviewer**: each item on opus, the close sign-off on fable, and the numbers review of the memo. | month-end (probably per-client Automations) |
| firm-books-orchestrator | `accounting-firm-books-close` | Closes the owner's firm's own books on the month-end pattern, with revenue tied to firm billing. | **worker**: the same three month-end sections plus Set up a month. **reviewer**: Review an item, and the sign-off on fable. | firm-books |
| intercompany-orchestrator | `accounting-intercompany-reconciliation` | Brings every entity pair's intercompany balance to zero, or a dated, explained item, before consolidation, and writes a hand-off file for the close. | **worker**: one per batch of pairs, plus one for the allocations, in parallel. **reviewer**: Review an item. | intercompany |
| collections-orchestrator | `accounting-collections-review` | Prepares each AR review: every past-due invoice gets an owner, a next action and a date in the register, plus the agenda. | **none** for the aging; the main agent works it itself, since it is one slice. **worker**: only for billing completeness when the close has not proved it (an isolated slice). **reviewer**: numbers review of the agenda and register. | collections |
| firm-billing-orchestrator | `accounting-firm-billing` | Drafts the firm's monthly invoices, each tied to `BILLING.yaml` and the pull, with a cover email. Nothing is sent. | **worker**: one per 1 to 3 contracts, in parallel. **reviewer**: each draft, and the period sign-off on fable. | firm-billing |
| accounting-questions-orchestrator | `accounting-questions` | Answers the accounting questions held as Portal tasks, each with the rule cited, and writes a change set of comments plus rule proposals. | **worker**: one per batch of about 10, in parallel (a single named task is done by the main agent itself). **reviewer**: medium-confidence answers and answers over the amount. | finance-ops |
| audit-support-orchestrator | `accounting-audit-support` | Works the auditor's PBC list from finished close work: support indexes, schedules, and questions by role. | **worker**: one per area batch, in parallel. **reviewer**: twice, once for the numbers in the schedules and once on Check the support. | audit-support |
| product-costing-orchestrator | `accounting-product-costing-review` | Builds or refreshes the per-product standard-versus-actual P&L as a controlled revision, tied per factory, and drafts the memo. | **none** for the build; the main agent does it, since it is one slice and runs sequentially. **reviewer**: numbers review. | product-costing (probably per-client) |
| vendor-1099-orchestrator | `accounting-vendor-1099` | Runs the W-9 backlog pass in the fall and the year-end register pass. | **worker**: one per about 50 vendors, in parallel. **reviewer**: Check the register (with the numbers review). | vendor-1099 |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| month-end-cash | 28 | section "Cash" of `month-end-workstream`, by worker | |
| month-end-ar-billing-revenue | 48 | section "AR, billing and revenue" of `month-end-workstream`, by worker | Also briefed by collections (billing completeness only) and firm-books (beside `firm-books-workstream`). |
| month-end-accruals | 29 | section "Accruals and AP" of `month-end-workstream`, by worker | Points to `month-end-accrual-drafts` ## Steps, which already exists. |
| month-end-keeper | 61 | sections "Set up a month" and "Curate a month" of the new `month-end-close`, by worker (model sonnet); "Record a learned fact", by main | The `dispatches: month-end-orchestrator` in the data is a false text match. |
| month-end-reviewer | 52 | reviewer checklist: sections "Review an item" and "Sign off the close" of `month-end-workstream` | Also used by firm-books and intercompany. |
| intercompany-reconciler | 25 | section "Reconcile a batch of pairs" of `intercompany-workstream`, by worker | |
| collections-analyst | 23 | section "Work the aging" of `collections-workstream`, by main | |
| firm-billing-preparer | 27 | section "Prepare contracts" of `firm-billing-workstream`, by worker | |
| firm-billing-reviewer | 26 | reviewer checklist: sections "Check a draft invoice" and "Sign off the period" of `firm-billing-workstream` | |
| accounting-questions-analyst | 20 | section "Answer a batch" of `accounting-questions-workstream`, by worker | |
| audit-support-preparer | 19 | section "Prepare a batch" of `audit-support-workstream`, by worker | |
| product-costing-analyst | 24 | section "Build the month" of `product-costing-workstream`, by main | |
| vendor-1099-analyst | 26 | section "Work a vendor batch" of `vendor-1099-workstream`, by worker | |
| month-end-results-writer (reporting) | 20 | skill `month-end-results-report` moves into accounting; run by worker | Only month-end dispatches it. |
| numbers-reviewer (reporting) | 84 | reviewer checklist: copied skill `numbers-review`, which is `numbers-reviewer-method` plus the agent's rules and output shape | |
| compliance-evidence-checker (compliance) | 18 | reviewer checklist: section "Check the support" of `audit-support-workstream` | |
| general-purpose (flux, investigations) | – | worker briefed with `month-end-flux` | |

**Reviewer:** `accounting-reviewer`, with a fresh context. It judges from the sources alone, PASS or FAIL with numbered fixes, and edits nothing. It is briefed with one of these:
- `month-end-workstream` Review an item or Sign off the close (fable)
- `firm-billing-workstream` Check a draft invoice or Sign off the period (fable)
- `accounting-questions-workstream` Check an answer
- `audit-support-workstream` Check the support
- `vendor-1099-workstream` Check the register
- `numbers-review`, for the results memo, the collections agenda, audit schedules, the costing pack and the 1099 totals

Shared checklists to copy in: `numbers-review` (from reporting's `numbers-reviewer-method` plus the agent body), which needs `report-tieout` (already in accounting). Tools: read-only, plus `accounting-je-import-check`, `accounting-trial-balance`, `accounting-report-tieout`, `accounting-excel-handle` and `accounting-firm-billing-draft` (for `--verify`).

**Worker:** `accounting-worker` is needed. Its slices:
- the three close sections, in parallel
- Set up and Curate a month (sonnet)
- the results memo
- flux investigations
- intercompany pair batches
- firm-billing contract batches
- question batches
- PBC area batches
- vendor batches

Its tools are the union of the department's commands plus Portal get, search and email_bodies.

**Skills**

| skill | action | add `## Steps`? | scripts → commands |
|---|---|---|---|
| month-end-close (new) | New, from the orchestrator body and the keeper. Sections: Steps, The folder, Done is computed, Recording a return, Questions, Set up a month, Curate a month, Record a learned fact, Authority, When no one is present. | yes | none |
| month-end-workstream | keep, plus sections Cash, AR billing and revenue, Accruals and AP, Review an item, Sign off the close | no (worker and reviewer skill) | `accounting-month-end-check`, `accounting-month-end-record` |
| month-end-accrual-drafts | keep | has it | `accounting-accruals`, `accounting-card-export`, `accounting-cc-accrual`, `accounting-service-period-accrual`, `accounting-recurring-je-scan` |
| month-end-journal-entry | keep | no | `accounting-je-import`, `accounting-je-import-check` |
| month-end-reconciliation | keep | no | `accounting-cash-walk` |
| month-end-flux | keep; `budget_detail_diff.py` moves out to `erp-ledger-pull` | no | `accounting-gl-sweeps` |
| month-end-expectations-brief | keep | no | none |
| month-end-results-report | move in from reporting; becomes the worker's "Write the results memo" | no | none |
| erp-ledger-pull | Keep and make it the one source for the copies. Merge `sage-intacct-reference` in as a reference file; move in `ar_ap_hygiene.py` and `budget_detail_diff.py`. | no | `accounting-month-end-pull`, `accounting-intacct-snapshot`, `accounting-trial-balance`, `accounting-intacct-gl-detail`, `accounting-gl-normalize`, `accounting-ar-ap-hygiene`, `accounting-budget-detail-diff` |
| sage-intacct-reference | merge into erp-ledger-pull | – | – |
| report-tieout | keep (source; copied to reporting and finance) | has it | `accounting-report-tieout` |
| collections-workstream | keep, plus Work the aging; the script moves to erp-ledger-pull | yes | (see erp-ledger-pull) |
| firm-billing-workstream | keep, plus Steps (from the orchestrator), The folder, Prepare contracts, Check a draft invoice, Sign off the period | yes | `accounting-firm-billing-pull`, `-draft`, `-record`, `-check`, `-deliver` |
| firm-books-workstream | keep | yes | none |
| intercompany-workstream | keep, plus Reconcile a batch of pairs | yes | none |
| accounting-questions-workstream | keep, plus Answer a batch and Check an answer | yes | none |
| transactional-definitions | keep (the owner also uses it by hand) | no | none |
| audit-support-workstream | keep, plus Prepare a batch and Check the support | yes | none |
| product-costing-workstream | Keep, plus Build the month, plus "The cost review memo": the Voice rules copied from reporting's `comms-client-status-update`. | yes | `accounting-sap-extract-normalize`, `accounting-prodqty-check`, `accounting-routing-rollup`, `accounting-fg-pl-extract`, `accounting-costmodel-audit` |
| product-costing-variance | keep (merge candidate) | no | none |
| product-costing-revision | keep; finance stops using it | no | none |
| vendor-1099-workstream | keep, plus Work a vendor batch and Check the register | yes | none |
| numbers-review (copy) | new copy | no | uses `accounting-report-tieout` |
| orchestration-workstream, comms-confirm, office-files, task-stack-workstream, unslop-email (copies) | copied in by the build step | no | `accounting-confirm`, `accounting-confirm-portal`, `accounting-waiting`, `accounting-excel-handle`, `accounting-pdf-handle`, `accounting-powerpoint-handler`, `accounting-task-stack-apply`, `-check`, `-queue`, `-report` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| orchestration-workstream (software) | in | copy in |
| comms-confirm (productivity), with scripts | in | copy in |
| office-files (productivity), with scripts | in | copy in |
| task-stack-workstream (productivity): the changes.json shape and the apply after the session | in | copy in; the finish step runs `accounting-task-stack-apply` |
| unslop-email (marketing) | in | copy in |
| comms-client-status-update voice (reporting) | in | copy the Voice section into product-costing-workstream |
| numbers-reviewer agent and numbers-reviewer-method (reporting) | in | becomes the copied checklist `numbers-review`, used by `accounting-reviewer` |
| month-end-results-writer and month-end-results-report (reporting) | in | move into accounting; reporting has no other user |
| compliance-evidence-checker (compliance) | in | replaced by Check the support; compliance's checker drops `audit-support-workstream` from its list |
| `firm_billing_deliver.py` calls productivity's `email_deliver.py` by path | in, at script level | copy `email_deliver.py` and its helper into firm-billing-workstream by the build step, or run the deliver step outside the plugin. Decide which. |
| erp-ledger-pull | out (finance; reporting only through the results writer, which moves) | finance copies it |
| month-end-flux | out (finance, reporting) | Finance drops it. The variance rule gets folded into forecast-method, and `budget_detail_diff` moves to erp-ledger-pull. Reporting's use leaves with the results report. |
| collections-workstream | out (finance's cash-forecaster, which uses only `ar_ap_hygiene.py`) | the script moves to erp-ledger-pull |
| product-costing-revision | out (finance's forecast modeler) | finance drops it; forecast-method's "Versions are submissions" gains the correction-versus-business-change rule |
| month-end-workstream: board-package scripts call `month_end_check.py` by path (the close gate) | out (reporting) | Copy the check script and its helper into reporting's board-package skill, kept identical by the build check. Or have the board-package prepare step run `accounting-month-end-check`. |
| report-tieout | out (reporting's board package and numbers review; finance's numbers review) | copy |
| audit-support-workstream | out (compliance) | drop from compliance |
| Mentions only: month-end-orchestrator (chief-of-staff routing table, orchestrator-scaffold design doc), vendor-1099-orchestrator (compliance-calendar and personal-tax-season descriptions), audit-support-orchestrator (it-governance description) | out | rename the references; no dependency |

**Automations to update** (I cannot read the sidecars, so these are the kinds of change):
- **month-end** (likely per-client):
  - `agent:` `accounting-month-end-close`.
  - prepare `month_end_pull.py --live` → `accounting-month-end-pull`.
  - Tool rules: the `confirm.py`, the erp-ledger-pull scripts, `je_import_check`, `month_end_check` and `month_end_record` paths → `accounting-*` commands.
  - Overlay `subagents:`: month-end-cash, -ar-billing-revenue, -accruals, -keeper and -reviewer, month-end-results-writer, numbers-reviewer and general-purpose → `accounting-worker`, `accounting-reviewer`.
  - `--plugin-dir` set to accounting; add the `Skill` tool.
- **firm-books**: `accounting-firm-books-close`; subagents become worker and reviewer. Add `accounting-month-end-check` and `-record`: today the agent has no Bash, yet it is meant to write the evidence file.
- **intercompany**: `accounting-intercompany-reconciliation`; subagents.
- **collections**: `accounting-collections-review`. The main agent now needs the analyst's commands (`accounting-ar-ap-hygiene`, `-intacct-snapshot`, `-intacct-gl-detail`, `-trial-balance`) and Portal `email_bodies`. Subagents.
- **firm-billing**: `accounting-firm-billing`. Prepare `firm_billing_pull` → `accounting-firm-billing-pull`; finish `firm_billing_deliver` → `accounting-firm-billing-deliver`; tool rules for `check`, `draft` and `record`; subagents.
- **finance-ops**: `accounting-questions`; finish `task_stack_apply` → `accounting-task-stack-apply`; subagents.
- **audit-support**: `accounting-audit-support`; remove compliance-evidence-checker and numbers-reviewer from subagents.
- **product-costing** (likely per-client): `accounting-product-costing-review`. The main agent gains the five costing commands and `Bash(sha256sum:*)`; the subagent is the reviewer only.
- **vendor-1099**: `accounting-vendor-1099`; subagents.

**Merge candidates for later**
1. **Intercompany into month-end-close** (a mode). They share the Month-End folder and period, and the HANDOFF file exists only because the two are separate. Risk: intercompany has its own `INTERCOMPANY-RULES.md` and its cadence before consolidation, and the close session grows.
2. **Firm-books into month-end-close.** Identical pattern and sections. Risk: a different folder, rules file and ledger source (an export, not the ERP), and the owner's firm against a client's books, which is a Context separation.
3. **Firm-billing with firm-books.** Same firm, monthly, run in sequence (bill, then close), and firm-books already reads firm-billing's folder. Risk: two folders and two rules files, and firm-billing has a strong computed check of its own.
4. **Accounting-questions into month-end-close** (the review's next merge). Both use the same ledger pulls. Risk: a weekly cadence, a Portal intake and a change-set output; little shared.
5. **Moves, not merges:** vendor-1099 and audit-support into compliance (the architecture review), against the owner's nine-job accounting list.
6. **Skills:** product-costing-variance into product-costing-workstream (only this job uses it); month-end-expectations-brief as a section of month-end-flux.

**Risks and open questions**
1. `accruals.py` finds `je_import.py` and `je_import_check.py` through the old skills-folder path, or through `ACCRUALS_SKILLS_DIR`. In a plugin it must call `accounting-je-import` on PATH or resolve the sibling skill from the plugin root. Its tests use the env var.
2. `firm_billing_deliver.py` hard-codes productivity's `email_deliver.py`, which needs the Portal config and bearer. It is the one script-level cross-department call.
3. Reporting's board-package `_common.py` has `MONTH_END_CHECK` at the old path. It breaks as soon as paths move, so fix it in the same change.
4. The month-end reviewer, the firm-billing reviewer and the forecast reviewer write their own review notes, and `month-end-record --review-file` and `firm-billing-record --review-file` expect a file. `software-reviewer` has Write disallowed. Decide: either the reviewer may Write only its notes, or it returns the note and the main agent writes it.
5. Models change per dispatch: the keeper sections on sonnet, the sign-offs on fable, and the analyst on fable for hard ones. Confirm Sentinel's `subagent_definition` lets a dispatch pass a model, or the tiers are lost.
6. The worker's tool list becomes the union of about 20 commands plus Portal tools. That is wider than any single specialist has today, a small loosening of least privilege.
7. The intercompany HANDOFF file is not consumed in the current month-end steps. Add "record intercompany's HANDOFF if present" to `month-end-close` Steps.
8. Folding the 141-line orchestrator plus the keeper into `month-end-close` gives about 200 lines, and `month-end-workstream` grows to about 200 with five sections. Check whether a worker loading all of it costs more than today's separate agents.
9. Owner and client files may name the old agents: rules files, `LOG.md` headers ("by month-end-orchestrator"), `BILLING-RULES.md`, chief-of-staff's routing table. Check that no check script parses those names.
10. Every SKILL.md frontmatter `allowed-tools`, every body that cites `python3 <path>`, and `month-end-accrual-drafts/rules.md` need rewriting to command names. The tests that call scripts by path must keep working.
11. The firm-books and intercompany orchestrators have no Bash today. Their "done" is walked by hand while month-end's is computed. Conversion is the moment to give them `accounting-month-end-check`.
12. Whether vendor-1099 stays in accounting (decision 7) or goes to compliance (review section 5) is open.

**Effort:** L. What drives it:
- the month-end family: the 141-line orchestrator, six specialists, three main agents sharing sections, and per-client Automations;
- two moves in from reporting (the results report and the numbers checklist);
- three script-level path couplings (accruals, firm-billing deliver, the board-package gate);
- 36 commands.

**Suggested order:**
1. The copy build step and the `bin/` commands. Include the erp-ledger-pull consolidation, and fix the accruals, deliver and board-package paths.
2. `accounting-firm-billing`. It is self-contained with a computed check, and it is the review's trial 2.
3. `accounting-questions`, `accounting-vendor-1099` and `accounting-audit-support`: simple, one analyst each.
4. `month-end-close` plus the `month-end-workstream` sections, then `accounting-month-end-close`.
5. `accounting-firm-books-close`, `accounting-intercompany-reconciliation` and `accounting-collections-review`, which reuse the close sections.
6. `accounting-product-costing-review`.

### finance

**Today:** 13 agents (5 main), 5 skills, 8 scripts (plus 1 helper). Finance is FP&A:
- a bridge from each forecast revision to the one before it, plus the monthly rolling vintage, with done computed by `forecast-check`;
- the annual three-way budget, built in passes;
- the weekly 13-week direct-method cash forecast;
- one-off analyses asked for by leadership;
- staging of contractual investor data-room postings.

It reads the books through accounting's ERP scripts and has every number re-derived before a person sends anything.

**Plugin:** `finance`, one plugin, kept separate from accounting by the owner's decision. The five jobs share the Forecast folder (forecast, budget, cash) or the finished outputs (analysis, posting), not a ledger workflow, so there is no reason to split further.

**Main agents**

| current | proposed | what it does | dispatch after | Automation(s) |
|---|---|---|---|---|
| forecast-orchestrator (83 lines) | `finance-forecast` | Bridges a new forecast revision to the prior one (or builds the rolling vintage), with every material line cited and done computed by `forecast-check`. | **worker**: the hypotheses, isolated so the writer never sees the new forecast; the rolling model, so the main agent does not explain its own numbers; the flags, in parallel with the main agent writing reasons and summary. **reviewer**: Check a vintage, with the sign-off on fable. | fpa-forecast |
| budget-orchestrator | `finance-budget` | Builds the annual budget over several sessions: assumptions, three statements that tie, then the board draft. | **none** for building; the main agent builds each pass, one slice at a time. **reviewer**: numbers review of the statements, red-team review of the board draft. | fpa-budget |
| cash-forecast-orchestrator | `finance-cash-forecast` | Rolls the 13-week cash forecast weekly, explains last week's misses and states the low point. | **none** for the roll. **reviewer**: numbers review, or "Check the week". | cash-forecast |
| analysis-orchestrator | `finance-analysis` | Drafts a one-off analysis from its Portal task: intake, workbook, memo and figure ledger. | **none** for writing. **reviewer**, twice: numbers review, and red-team review of the memo. | fpa-analysis |
| investor-posting-orchestrator | `finance-investor-posting` | Stages each owed data-room posting from approved finals, with a manifest, an upload checklist and a draft notice. | **worker**: only when several periods are owed (catch-up). **reviewer**: Check a packet. | investor-posting |

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| forecast-drivers-analyst | 30 | sections "Write the hypotheses" and "Answer the flags" of `forecast-method`, by worker | Hypotheses need isolation: the brief must never carry new-forecast paths. |
| forecast-modeler | 28 | section "Propose the rolling forecast" of `forecast-method`, by worker | Its `product-costing-revision` use becomes forecast-method's own rule. |
| forecast-bridge-writer | 30 | section "Explain the bridge and write the summary" of `forecast-method`, by main | It applies the copied `unslop-deliverable`. |
| forecast-reviewer | 32 | reviewer checklist: sections "Check a vintage" and "Sign off the vintage" of `forecast-method` | |
| budget-builder | 22 | section "Build a pass" of `budget-method`, by main | |
| cash-forecaster | 25 | section "Roll the week" of `cash-forecast-method`, by main | |
| analysis-writer | 24 | section "Write the analysis" of `analysis-workstream`, by main | |
| investor-posting-preparer | 23 | section "Stage a period" of `investor-posting-workstream`, by main (worker for catch-up) | |
| numbers-reviewer (reporting) | 84 | reviewer checklist: copied `numbers-review` | |
| executive-red-team (reporting) | 64 | reviewer checklist: copied `red-team-review` (the agent body as a skill) | |
| general-purpose (forecast reading) | – | worker | |

**Reviewer:** `finance-reviewer`, with a fresh context, judging from the sources alone. It is briefed with one of these:
- `forecast-method` Check a vintage, or Sign off the vintage (fable)
- `cash-forecast-method` Check the week (DONE items 2, 3, 5)
- `budget-method` Check the statements
- `investor-posting-workstream` Check a packet: each file identical to its approved source, and the notice figures in the package
- `analysis-workstream` Check the analysis
- `numbers-review`
- `red-team-review`

Shared checklists to copy in: `numbers-review`, `red-team-review`, and `report-tieout` (which numbers-review uses). Tools: read-only, plus `finance-forecast-check`, `finance-report-tieout`, `finance-excel-handle`, `Bash(diff:*)`.

**Worker:** `finance-worker` is needed for the forecast job's three slices (hypotheses, the rolling model, flags) and for an investor-posting catch-up. Its tools: `finance-forecast-check`, `finance-forecast-extract`, `finance-trial-balance`, `finance-gl-normalize`, `finance-excel-handle`, `finance-pdf-handle`, `Bash(cp:*)`, `Bash(diff:*)`.

**Skills**

| skill | action | add `## Steps`? | scripts → commands |
|---|---|---|---|
| forecast-method (114 lines, plus `contract.md`) | Keep. Move the orchestrator's session into Steps. Add the five sections above, plus "Explaining a variance" (about five lines from month-end-flux), plus a line on labelling corrections versus business changes. | yes | `finance-forecast-prepare`, `-extract`, `-bridge`, `-sense-check`, `-score`, `-revise`, `-record`, `-check` |
| budget-method | keep, plus Build a pass and Check the statements | yes | none |
| cash-forecast-method | keep, plus Roll the week and Check the week | yes | none |
| analysis-workstream | keep, plus Write the analysis and Check the analysis | yes | none |
| investor-posting-workstream | keep, plus Stage a period and Check a packet | yes | none |
| erp-ledger-pull (copy from accounting, with the Intacct reference, `ar_ap_hygiene` and `budget_detail_diff`) | copy | no | `finance-trial-balance`, `finance-gl-normalize`, `finance-intacct-gl-detail`, `finance-intacct-snapshot`, `finance-month-end-pull` (unused; the build could skip it), `finance-ar-ap-hygiene`, `finance-budget-detail-diff` |
| numbers-review, red-team-review, report-tieout (copies) | copy | no | `finance-report-tieout` |
| orchestration-workstream, comms-confirm, office-files, unslop-deliverable (copies) | copy | no | `finance-confirm`, `finance-confirm-portal`, `finance-waiting`, `finance-excel-handle`, `finance-pdf-handle`, `finance-powerpoint-handler` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| erp-ledger-pull scripts (accounting): the analysis writer, budget builder and cash forecaster | in | copy in |
| month-end-flux (accounting): budget builder, drivers analyst and orchestrator | in | Drop. `budget_detail_diff` arrives through the erp-ledger-pull copy; the variance rule becomes a forecast-method section. |
| collections-workstream `ar_ap_hygiene` (accounting): cash forecaster | in | through the erp-ledger-pull copy |
| product-costing-revision (accounting): modeler and orchestrator | in | Drop. Its `costmodel_audit` reference and `Bash(python3:*)` would not travel anyway; forecast-method already holds "Versions are submissions". |
| numbers-reviewer, executive-red-team (reporting) | in | copied checklists, used by finance-reviewer |
| comms-confirm, office-files (productivity), orchestration-workstream (software), unslop-deliverable (marketing) | in | copy in |
| investor-posting-orchestrator mentioned in board-package's description (reporting) | out | rename the reference |
| Investor posting stages reporting's approved board package | file-level | no change; it reads finished files by path from the rules |

**Automations to update:**
- **fpa-forecast**:
  - `agent:` `finance-forecast`.
  - prepare `forecast_prepare.py` → `finance-forecast-prepare`.
  - Tool rules: the eight forecast script paths and `confirm.py` → commands.
  - Subagents: the drivers analyst, modeler, bridge writer, reviewer and general-purpose → `finance-worker`, `finance-reviewer`.
  - Plugin dir; the `Skill` tool is already there.
- **fpa-budget**: `finance-budget`. The main agent gains the builder's commands (`finance-forecast-extract`, `-budget-detail-diff`, `-trial-balance`, `-excel-handle`). The subagent is the reviewer only.
- **cash-forecast**: `finance-cash-forecast`. The main agent gains `finance-ar-ap-hygiene`, `-trial-balance`, `-gl-normalize`, `-excel-handle` and `-pdf-handle`. Reviewer only.
- **fpa-analysis**: `finance-analysis`. The main agent gains the Intacct commands and `excel-handle`, and keeps its Portal tools. Reviewer only.
- **investor-posting**: `finance-investor-posting`. The main agent gains `Bash(cp:*)`, `Bash(diff:*)` and `pdf-handle`; the subagents are worker and reviewer. The four Automations above that drop their worker also need `Skill` and `Agent` added.

**Merge candidates for later**
1. **Budget into finance-forecast** (as a mode). The budget is "a vintage in the Forecast folder" under the same `FORECAST-RULES.md`. Risk: an annual, multi-pass calendar against a monthly eleven-test check, and the budget's planned `budget-check` does not exist yet.
2. **Cash-forecast into finance-forecast** (the review's choice). It uses the same Forecast folder. Risk: a weekly cadence, its own `CASH-FORECAST-RULES.md` (which fails the "same rules file" test), and a different done.
3. **Investor-posting into reporting's board-package** (the review's choice). Same period and the same approved package. Risk: it moves a job across departments, and the posting schedule (contractual dates) differs from the board calendar.

**Risks and open questions**
1. Hypotheses isolation: a worker under the session's allowlist can still Read `new.json`, as today. The main agent must also not open new-forecast files before step 1 completes. Put that in Steps.
2. If the main agent writes reasons and summary itself, the context that ran the bridge also explains it. Independence rests on `finance-reviewer` alone, where today the bridge writer and the reviewer are both separate from the orchestrator. Confirm that is acceptable, or keep it as a worker slice.
3. The forecast reviewer writes its review note under `vintages/<V>/reviews/`. Same Write question as accounting's reviewer.
4. Copying erp-ledger-pull brings the Intacct credential-reading scripts and an unused `month-end-pull` into finance. Decide whether the build copies whole skills or a file list.
5. `numbers-review` depends on `report-tieout`, so finance carries three copied numbers skills. Every fix to them must flow through the single source and pass the identical-copy check.
6. `budget-method` and `cash-forecast-method` are also owner-started ("with or without that orchestrator"). The new Steps sections must not assume an Automation.
7. Today only forecast-orchestrator has the `Skill` tool; the other four read skills by path. All five need `Skill`, and their first instruction must be to load their skills.
8. Rules files in the owner's Forecast and Reporting folders, and `LOG.md` headings ("by forecast-orchestrator"), name the old agents. Check that `forecast-check` does not parse them.

**Effort:** M. `finance-forecast` drives it: the 83-line session, four specialists, the eleven tests, isolation, and eight commands. The other four are a main agent plus a reviewer each, with no worker.

**Suggested order:**
1. The copies (erp-ledger-pull, numbers-review, red-team-review, report-tieout, core) and the `bin/` commands.
2. `finance-investor-posting` and `finance-cash-forecast`.
3. `finance-analysis`.
4. `finance-budget`.
5. `finance-forecast`, last, after accounting's erp-ledger-pull consolidation has settled.

Note on counts: accounting's agents fall from 22 to 11 (9 main, plus reviewer and worker), but its skills rise from 20 to about 27 because of the copies. Finance's agents fall from 13 to 7, and its skills rise from 5 to about 13.

---

Two findings change the picture from `brief.json`:

- **No main agent in these departments dispatches another main agent or another department's main agent.** Every such match is a "Hand-offs:" line in the agent's Returns, or a "Not for X" line.
- **The real cross-department couplings are in scripts.** Six scripts call other skills' scripts through hard-coded skill-folder paths, which will break once the code runs as a plugin:
  - `delivery_pack.py` and `client_update_pack.py` call report-weekly's `report_collect.py`.
  - `delivery_apply.py` calls productivity's `task_stack_apply.py`.
  - board-package `_common.py` calls accounting's `month_end_check.py`.
  - `client_update_deliver.py` calls productivity's `email_deliver.py`.
  - `process_flow_prepare.py` reads its reference models from the reference-process-models skill folder by default.

Projects' project-health also really dispatches three productivity agents: `task-clarify-worker`, `waiting-on-tracker` and `task-reconcile-checker`.

## The four shared reviewers as copied checklist skills

**Form.** Four skills, one per reviewer, each with the same sections:
- `## When to use` (and when not)
- `## What the reviewer is given` (and what it must refuse: the author's reasoning)
- `## Checklist` (the method, in order)
- `## Return` (the default return block)
- `## Briefing` (for the main agent: what to pass, two-halves splitting, diff passes)

| Today | Checklist skill | Absorbs | Needs in the department |
|---|---|---|---|
| `numbers-reviewer` (84 lines) | `review-numbers` | `numbers-reviewer-method` (its seven steps become `## Checklist`); the tie-out script | the reviewer gets `Write` limited to the scratch folder the brief names (as today); command `<dept>-report-tieout` |
| `fact-check` (55) | `review-facts` | the three verdicts, omissions, the two-halves and late-source diff briefs | read only |
| `executive-red-team` (64) | `review-red-team` | silent-read test, ten tests, grades, the one change | read only |
| `completeness-audit` (57, process-engineering) | `review-completeness` | `reference-process-models` (its five model files become `references/`) | read only |

**Rules for the copies:**
- The job skill's check section names the checklist and may override the return. Process-flow's `claim_ledger.py record` parses its own fact-check, completeness and red-team blocks (`contract.md`), and client-update parses a verdict JSON. So the department reviewer follows the job section's return. It does not force PASS/FAIL. Process-flow's red-team grades and fact-check ledgers must survive unchanged.
- **One source with marked copies.** Proposed layout: a `shared/skills/<name>/` folder at the toolbox root. It is not a plugin. `shared/manifest.yaml` lists which departments get which skill. A build step (beside `build_bins.py`) copies the skill into `<dept>/skills/<name>/` and writes a "generated, do not edit" marker. `toolbox_check.py` fails when a copy drifts.
- Command names inside copied text differ per department (`reporting-report-tieout`, `projects-report-tieout`). The copy step substitutes a `{dept}` placeholder, and the identity check compares after that substitution.
- **Who needs copies (verified by reading the dispatchers):**
  - `review-numbers`: accounting, finance, personal, process-engineering, projects, reporting.
  - `review-facts`: compliance, decision-playbooks, learning, marketing, personal, process-engineering, projects, reporting, sales.
  - `review-red-team`: finance, learning, marketing, process-engineering, projects, reporting, sales.
  - `review-completeness`: compliance, personal, process-engineering.
  - Chief-of-staff only names them to route requests. Productivity's `pressure-test-method` and strategy's `pre-mortem` mention the red team only in a description. Neither needs a copy.
- The same mechanism carries the other shared skills these three departments need: `orchestration-workstream`, `comms-confirm` (with `confirm.py`), `unslop-deliverable`, `transcript-tools`, and two new small ones (`engagement-context` and `automation-backlog-format`, both described below).

---

### reporting

**Today:** 16 agents (3 main orchestrators, plus the interactive main agent `weekly-reporter`), 7 skills, 25 scripts (plus 6 helper modules). Reporting drafts reports that leave the building:
- the executive's weekly report to the leadership team (collected Thursday, gates on the owner's task list, drafted and rendered Friday);
- a company's monthly board package, tied to the closed books;
- one engagement's weekly client update (deck or memo, a source on every claim);
- the month-end results memo (dispatched by accounting).

It also holds the shared fact, numbers and red-team reviewers.

**Plugin:** `reporting`, one plugin.
- `month-end-results-writer` and `month-end-results-report` move to accounting. Only accounting's `month-end-orchestrator` dispatches the writer, and it needs accounting's `erp-ledger-pull`, `month-end-flux` and `month-end-workstream`.
- No split. The board package leans toward finance (it reads accounting's close, and finance's investor posting follows it); see the open questions.

**Main agents**

| Current | Proposed | What it does | Dispatch after | Automation(s) |
|---|---|---|---|---|
| `board-package-orchestrator` | `reporting-board-package` | Drafts one company's monthly board deck, script and cover email with every figure tied to the closed books. | reporter, twice: numbers, then red team (independence). It drafts itself; the writer becomes a section. | `board-package` (per company) |
| `client-update-orchestrator` | `reporting-client-update` | Drafts one engagement's weekly client update, every claim sourced, plus the proposed context revision. | worker: one reader per source batch (parallel). Reviewer: two fact halves, red team, cover-email check. It writes itself. | `client-weekly-update` (per-client Automations) |
| `weekly-report-orchestrator` | `reporting-weekly-report` | Runs the leadership weekly report: collect phase (judge, gates to the owner), assemble phase (write, verify, render, approval), keep. | worker: intake per direct report, harvester (keeps mail out of the main context), continuity and audience editor in parallel, writer (one turn from the inlined digest). Reviewer: facts, when more than five figures are untied. | `report-weekly-collect`, `report-weekly-assemble` (same agent; the phase is an input) |
| `weekly-reporter` (interactive, 66 lines) | folded into `reporting-weekly-report` as `mode: interactive` | Runs the same week with the executive present: gates asked live. | as above | none |

**Specialists: where their know-how goes**

| Agent | Lines | Becomes | Note |
|---|---|---|---|
| `board-package-writer` | 24 | section "Draft the package" of `board-package-workstream`, run by the main agent | The writer's five steps already fit a section. |
| `client-update-reader` | 18 | section "Read a batch" of `client-update-workstream`, run by the worker | It already has `extra.facts` in the skill. |
| `client-update-writer` | 24 | section "Write the update" of `client-update-workstream`, run by the main agent | It loads `project-status-deck` or `comms-client-status-update` by variant. |
| `report-continuity` | 29 | `report-weekly` `workers/continuity.md`, run by the worker | These five agents are already one-line pointers to `workers/*.md`. Keep the files (the inline runtime reads them) and brief the worker with the file. Turning them into sections is optional. |
| `report-audience-editor` | 29 | `workers/audience-editor.md`, run by the worker | |
| `report-writer` | 31 | `workers/writer.md`, run by the worker | Context isolation is the point: it sees only the digest. |
| `report-intake` | 30 | `workers/intake.md`, run by the worker | |
| `report-harvester` | 38 | `workers/harvester.md`, run by the worker | It needs a mail and calendar connector and `Write` for `ledger.json`. |
| `month-end-results-writer` | 20 | moves to accounting: a section of `month-end-results-report`, run by accounting's worker | It never served reporting's own jobs. |
| `numbers-reviewer` | 84 | `review-numbers` checklist (shared source), for the reviewer | |
| `fact-check` | 55 | `review-facts` checklist (shared source), for the reviewer | |
| `executive-red-team` | 64 | `review-red-team` checklist (shared source), for the reviewer | |
| `email-drafter` / `email-checker` (productivity, used by client update) | n/a | the cover email becomes a file. Copy productivity's `comms-draft-check` into reporting as a checklist for `reporting-reviewer`. Portal staging moves to the finish step (see the dependencies table). | |

**Reviewer:** `reporting-reviewer` (opus by default; fable for the board package's final pass when it carries an exception or a figure a person stated). It checks:
- board package: figures re-derived, cross-document agreement, the deck read cold;
- client update: two disjoint source halves verified, the draft read as the client;
- leadership weekly: claims against the pack when the verifier flags untied figures;
- client-update cover email: the draft check.

It is briefed with the job sections "Check the package" (board-package-workstream), "Check the update" (client-update-workstream) and "Check the draft" (report-weekly). Copies needed: `review-numbers`, `review-facts`, `review-red-team`, `comms-draft-check`. The tools are read-only, plus `Write` to the scratch folder and `Bash(reporting-report-tieout:*)` and `Bash(reporting-board-package-tieout:*)`.

**Worker:** `reporting-worker`, needed for:
- client-update reader batches;
- the weekly report's intake, harvester, continuity, audience editor and writer.

**Skills**

| Skill | Action | `## Steps`? | Scripts → commands |
|---|---|---|---|
| `board-package-workstream` | keep; add sections "Draft the package" and "Check the package" | yes (reporting-board-package) | `board_package_pack/check/figures/render/record/tieout` → `reporting-board-package-pack`, `-check`, `-figures`, `-render`, `-record`, `-tieout` |
| `client-update-workstream` | keep; add "Read a batch", "Write the update", "Check the update"; move the engagement-context sections to the shared `engagement-context` | yes | `client_update_pack/check/record/deliver` → `reporting-client-update-pack`, `-check`, `-record`, `-deliver` |
| `report-weekly` | keep; turn Steps 1 to 18 plus `unattended.md` into one `## Steps` with phase branches; add "Check the draft"; take the interactive gate rules from `weekly-reporter` | yes (`→ phase assemble: step N`) | 15 scripts. The default names get a double prefix (`reporting-report-collect`). Either rename `report_*.py` to `weekly_*.py` (`reporting-weekly-collect`, `-organize`, `-ledger`, `-render`, `-record`, `-verify`, `-facts`, `-pack`, `-profile`, `-questions`, `-workorder`; `report_weekly_check/gates/prepare` → `reporting-weekly-check`, `-gates`, `-prepare`), or add a name-override map to `build_bins.py`. `build_reference_docx` → `reporting-build-reference-docx`. |
| `comms-client-status-update` | keep; becomes the shared source for its Voice section (accounting's product-costing writes in that voice) | no (method) | none |
| `project-status-deck` | keep | no | none |
| `numbers-reviewer-method` | merge into `review-numbers` | no | none (uses `report-tieout`) |
| `month-end-results-report` | move to accounting | moves with it | none |
| new copies | `orchestration-workstream`, `comms-confirm`, `unslop`, `unslop-deliverable`, `office-files` (only `powerpoint_handler`), `report-tieout`, `review-*`, `comms-draft-check`, `transcript-tools`, `engagement-context` | no | `reporting-confirm`, `reporting-report-tieout`, `reporting-powerpoint-handler`, `reporting-srt-transcript-collapse` |

**Cross-department dependencies**

| What | Direction | Resolution |
|---|---|---|
| `month-end-results-writer` and `month-end-results-report` | accounting → reporting | move to accounting |
| `month_end_check.py`, called from board-package `_common.py` to test the Close gate | reporting → accounting | **change** to a file contract: board-package-pack reads the close's DONE or evidence file, whose format is documented in the copied `month-end-close-state` section, or the Automation's precheck runs accounting's command. Not a code call. |
| `report-tieout` (accounting skill and script) | reporting → accounting | copy in (shared source) |
| `office-files` `powerpoint_handler.py` | reporting → productivity | copy in (deck read and write only) |
| `email-drafter`, `email-checker`, `find_contact`, `find_email`, `email_draft_show`, `email_deliver.py` | reporting → productivity | **hand-off.** The session writes the cover email file and `delivery.json` (recipient), and the reviewer checks it with the copied `comms-draft-check`. The finish step calls productivity's delivery command, so the Automation needs both plugins but the session does not. Alternative: copy a small `outlook-draft` script set. |
| `comms-confirm`, `orchestration-workstream`, `unslop*` | reporting → productivity, software, marketing | copy in |
| `report_collect.py`, called by client_update_pack (same department) and delivery_pack (projects) | projects → reporting | see projects |
| `board-package-workstream`, used by finance's `investor-posting-workstream` | finance → reporting | the deck spec is not needed; investor posting reads the package files. Turn it into a file contract and drop the name. |
| `weekly-reporter`, `report-writer`, `report-tieout`, named by chief-of-staff | chief-of-staff → reporting | routing text only: update the names; drop it |
| `calendar-steward-method`, named in `weekly-report-spec.md` | reporting → productivity | reference only: drop, or reword as a profile input |

**Automations to update:**
- **`board-package`** (per company):
  - `agent:` becomes `reporting-board-package`;
  - the prepare `board_package_pack.py` becomes `reporting/bin/reporting-board-package-pack`;
  - tool rules become `Bash(reporting-board-package-*:*)`, `Bash(reporting-report-tieout:*)` and `Bash(reporting-powerpoint-handler:*)`;
  - drop the `month_end_check.py` rule;
  - set `subagents:` to `reporting-reviewer`;
  - add `--plugin-dir`.
- **`client-weekly-update`** (per-client):
  - `agent:` becomes `reporting-client-update`;
  - the prepare `client_update_pack.py` becomes `reporting-client-update-pack`;
  - the finish `client_update_deliver.py` becomes `reporting-client-update-deliver`, which needs productivity's email-deliver command on PATH or by path;
  - drop the `find_contact`, `find_email` and `email_draft_show` rules if the hand-off is adopted;
  - `subagents:` become `reporting-worker` and `reporting-reviewer`.
- **`report-weekly-collect`** and **`report-weekly-assemble`**:
  - `agent:` becomes `reporting-weekly-report` (the phase input stays);
  - `report_weekly_prepare.py` becomes `reporting-weekly-prepare`;
  - the 13 script rules become command rules;
  - `subagents:` become `reporting-worker` and `reporting-reviewer`;
  - the harvester tier needs the mail connector allowed for the worker.

**Merge candidates for later**
1. `reporting-weekly-report` with `reporting-client-update`, which the architecture review suggested. The reason is the same weekly cadence and the same Portal collection. The risk is that they have different folders, rules files and audiences, and a per-client Context next to the owner's own store invites leaks. I would not merge them.
2. Board package with finance's investor posting. The reason is that the posting consumes the package. The risk is that it moves an agent across buckets.

**Risks and open questions**
1. The hard-coded skill-folder paths in `client_update_pack.py`, `client_update_deliver.py` and board-package `_common.py` break once `~/.claude/skills` is no longer populated. They must resolve inside the plugin (relative to `__file__`) or become file contracts.
2. Should the board package live in finance, next to investor posting and closer to the close? If it stays, its only accounting coupling should be a file contract.
3. Does the reviewer agent get `Write` (scratch only) because of `review-numbers`, unlike `software-reviewer`, which disallows it? Recommended: yes, scoped by the checklist text.
4. `report-weekly`'s `workers/*.md` files are designed as the single copy for the inline runtime too. Keep them as files the worker is pointed at, rather than turning them into `##` sections.
5. `weekly-reporter` is interactive and has no model set. Folding it into the main agent as a mode needs the interactive gate rules (Teams heads-up, live questions) written into report-weekly.
6. Weekly-reporter's covering email through `email-drafter` has no place once that agent is in another plugin. Drop it (the unattended path already drafts no email) or copy the drafting section.
7. The double-prefix command names need the rename or a `build_bins.py` override map.

**Effort:** L. The work is driven by report-weekly (15 scripts and their tests, two Automations, five worker files, the mode fold), the email delivery hand-off, the month-end move (which coordinates with accounting), and fixing hard-coded paths.

**Suggested order:**
1. The shared checklist copies (they unblock every department).
2. `reporting-board-package`, the smallest, after the month-end move and the close-state contract.
3. `reporting-client-update`.
4. `reporting-weekly-report` last.

---

### projects

**Today:** 13 agents (5 main), 11 skills, 8 scripts (plus 3 helper modules). The department does two kinds of work:
- **Client engagements, start to finish:** kickoff from a signed SOW, delivery (plan, milestones, RAID, tasks) twice a week, closeout (acceptance, invoice check, lessons, case-study draft), and a client's technology-portfolio steering pack.
- **The owner's own Insights Portal project list:** the weekly health pass, plus interactive check-in and landscape skills.

**Plugin:** `projects`, one plugin for now. The jobs fall into two buckets, client engagements and the owner's Portal portfolio. The second (`project-health`, `project-checkin`, `project-landscape`) depends mostly on productivity's task-stack and strategy's goal alignment. Moving those out is a better fix than a second plugin; see the open questions.

**Main agents**

| Current | Proposed | What it does | Dispatch after | Automation(s) |
|---|---|---|---|---|
| `client-delivery-orchestrator` | `projects-client-delivery` | Keeps one engagement's plan, milestones, RAID log and Portal tasks true against the SOW, in plan, check or milestone-review mode. | worker: risk log and task reconcile in parallel (each reads the whole window); it plans itself. Reviewer: task ops of medium confidence, red team on PLAN and STATUS. | `client-delivery` (per-client) |
| `project-engagement-kickoff-orchestrator` | `projects-engagement-kickoff` | Turns a signed SOW into rules files, context, briefs, client notes, a folder plan and the first two weeks of tasks, all as drafts. | reviewer: SOW tracing and assignments, red team on the brief. It writes the pack itself. | `engagement-kickoff` |
| `project-engagement-closeout-orchestrator` | `projects-engagement-closeout` | Closes an engagement: acceptance evidence, the final invoice check, lessons, an anonymous method harvest, a case-study draft and closing task ops. | reviewer: numbers (invoice check), acceptance and harvest anonymity, red team on the case study | `engagement-closeout` |
| `project-health-orchestrator` | `projects-health-review` | Weekly pass over the owner's Portal projects: a diagnosis word and the smallest step each, buckets drained, dead projects closed, one change set. | worker: diagnoser batches, the bucket drain and the waiting-on scan (parallel). Reviewer: medium task ops, completes and cancels. | `project-health` |
| `tech-portfolio-orchestrator` | `projects-tech-portfolio` | Builds a client portfolio's weekly steering pack from project owners' own updates, with slips as questions. | worker: collector per batch of about 5 projects. Reviewer: two fact halves, red team. It writes the pack itself. | `tech-portfolio-review` (per-client) |

**Specialists: where their know-how goes**

| Agent | Lines | Becomes | Note |
|---|---|---|---|
| `project-delivery-planner` | 30 | section "Plan the engagement" of `client-delivery-workstream`, run by the main agent | Its return shape is already in the skill. |
| `project-risk-analyst` | 29 | section "Keep the RAID log", run by the worker | |
| `project-task-steward` | 29 | section "Reconcile the tasks", run by the worker | |
| `project-engagement-writer` | 23 | sections "Write the kickoff pack" and "Write the closeout pack" of the engagement skills, run by the main agent | |
| `project-engagement-checker` | 25 | sections "Check the kickoff pack" and "Check the closeout pack" (SOW tracing, assignments, acceptance, harvest anonymity), reviewer checklist | |
| `project-health-diagnoser` | 22 | section "Diagnose a batch" of `project-health-diagnose`, run by the worker | |
| `tech-portfolio-collector` | 18 | section "Collect a batch" of `tech-portfolio-workstream`, run by the worker | |
| `tech-portfolio-writer` | 17 | section "Write the steering pack", run by the main agent | |
| `task-clarify-worker` (productivity) | n/a | section "File bucket tasks" in a copied `task-stack-clarify`, run by the worker | |
| `waiting-on-tracker` (productivity) | n/a | section "What the stalled projects wait on" in a copied `waiting-on-tracker-method`, run by the worker | |
| `task-reconcile-checker` (productivity) | n/a | section "Check a task op" in the copied `task-stack-workstream`, reviewer checklist | |
| `executive-red-team`, `fact-check`, `numbers-reviewer` | n/a | `review-red-team`, `review-facts`, `review-numbers` copies, for the reviewer | |

**Reviewer:** `projects-reviewer` (opus by default; fable for a close acceptance or late-milestone call). It checks:
- task ops (evidence, authority, assignable people only);
- kickoff and closeout packs (every baseline, milestone, acceptance and fee line traced to an SOW section; anonymity);
- the closeout invoice check against the SOW and billing;
- the steering pack against two source halves;
- delivery status, the kickoff brief, the case study and the steering pack read cold.

Copies needed: `review-numbers`, `review-facts`, `review-red-team`, `task-stack-workstream` (for "Check a task op").

**Worker:** `projects-worker`, needed for the delivery risk log and task reconcile, health diagnoser batches, the bucket drain, the waiting-on scan, and tech-portfolio collector batches.

**Skills**

| Skill | Action | `## Steps`? | Scripts → commands |
|---|---|---|---|
| `client-delivery-workstream` | keep; add the three sections | yes | `delivery_pack/check/record/apply` → `projects-delivery-pack`, `-check`, `-record`, `-apply` |
| `project-engagement-workstream` | **split** into `engagement-kickoff` and `engagement-closeout` (each with Steps, a write section and a check section). Sentinel reads one `## Steps` per skill, so two jobs cannot share one. The shared parts (the engagement, conduct, returns) stay in `project-engagement-workstream`. | yes, on the two new skills | `engagement_folders` → `projects-engagement-folders` |
| `project-health-diagnose` | keep; add "Diagnose a batch" | yes (projects-health-review) | `project_health_check` → rename to `health_check.py`, giving `projects-health-check` (default: `projects-project-health-check`) |
| `tech-portfolio-workstream` | keep; add "Collect a batch", "Write the steering pack", "Check the pack" | yes | none |
| `project-engagement-runbook` | keep (lifecycle reference); refer to other departments' steps by Automation name, not skill | no | none |
| `project-engagement-onboarding` | keep | no | uses `projects-register` |
| `review-register` | keep | no | `register` → `projects-register` |
| `engagement-comms-set` | keep; drop the `workshop-design` and `comms-draft-email` names (reference only) | no | none |
| `project-engagement-baseline` | **move** to process-engineering (discovery-synthesis drafts the BASELINE by it) | n/a | none |
| `project-checkin` (interactive) | keep for now; candidate to move with health | no | none (calls `projects-health-check`) |
| `project-landscape` (interactive, 334 lines) | keep for now; candidate to move to strategy | no | `project_scoreboard` → rename to `scoreboard.py`, giving `projects-scoreboard` |
| new copies | `orchestration-workstream`, `comms-confirm`, `task-stack-workstream` (with `task_stack_apply/check/report`), `task-stack-clarify`, `waiting-on-tracker-method`, `unslop-deliverable`, `unslop-editorial`, `unslop-email`, `review-*`, `transcript-tools`, `engagement-context` | no | `projects-task-stack-apply`, `-check`, `-report`, `projects-confirm`, `projects-srt-transcript-collapse` |

**Cross-department dependencies**

| What | Direction | Resolution |
|---|---|---|
| `task-clarify-worker`, `waiting-on-tracker`, `task-reconcile-checker` dispatched by project-health and client-delivery | projects → productivity | copy in their method skills as sections (above). An agent dispatch across plugins is not allowed. |
| `task_stack_apply.py` called by `delivery_apply.py`; `task-stack-check`, `task-stack-apply` and `task-stack-report` run by the project-health Automation before and after the session | projects → productivity | copy in `task-stack-workstream` with its scripts (it is a "core" candidate anyway). Fix `delivery_apply.py`'s hard-coded path. |
| `report_collect.py` called by `delivery_pack.py` (about 900 lines plus about 2,000 of helper modules) | projects → reporting | **phase 1:** `delivery_pack.py` takes `--collected FILE`, and the Automation's prepare runs `reporting-report-collect` first (an Automation-level dependency; the session stays standalone). **Later:** extract a shared `portal-collect` source copied into both. |
| `ENGAGEMENT-CONTEXT.md` sections (defined in reporting's `client-update-workstream`); kickoff writes `UPDATE-RULES.md` and `DISCOVERY-RULES.md` | projects → reporting, process-engineering | new shared skill `engagement-context`: the Context YAML and Sources, the ENGAGEMENT-CONTEXT sections, templates for the three rules files. Copy it into projects, reporting and process-engineering. |
| Kickoff's hand-off to delivery, the client update and discovery | projects → projects, reporting, process-engineering | already a Returns line. Make it a `for_owner` item: "adopt these files; then arm Automation `client-delivery` / `client-weekly-update` / `assessment-intake` for engagement X". Never a dispatch. |
| Closeout's hand-off to `marketing-case-study-orchestrator` and to firm billing | projects → marketing, accounting | already a Returns line. A `for_owner` item ("consent given → launch the marketing case-study Automation with drafts/case-study.md"); amounts owed become a `for_owner` item for firm billing. Drop the agent name. |
| `client-update-workstream` and `comms-client-status-update`, named by the engagement writer and runbook | projects → reporting | the writer only needs the context sections (`engagement-context` copy) and the UPDATE-RULES template; drop the rest |
| `interview-synthesis`, `workshop-design`, `transcript-tools`, `discovery-synthesis-orchestrator` named in the runbook, baseline and comms set | projects → process-engineering | `project-engagement-baseline` moves to process-engineering; copy in `transcript-tools`; other names are references to drop |
| `project-landscape` dispatches strategy's `goal-auditor`, runs `calendar_time.py` (productivity) and `goal_alignment_check.py` (strategy) | projects → strategy, productivity | **move `project-landscape` to strategy** (it is used by chief-of-staff and strategy's goal-auditor). Until then, it is an interactive skill whose cross-plugin calls fail in a sealed session. |
| `project-health-orchestrator` named by productivity's weekly review and strategy's goal alignment; `diagnoses.json` read by the weekly review | productivity, strategy → projects | a file contract (`RUN/diagnoses.json`): keep its shape documented in `project-health-diagnose`; readers find it by Run folder, not agent |
| `software-grill-with-docs`, `pre-mortem`, `quick-capture`, `writing-seminar-builder`, `unslop-proposal` mentions | projects → others | reference only: drop, or copy `unslop-proposal` if the runbook's proposal step stays |

**Automations to update:**
- **`client-delivery`** (per-client):
  - `agent:` becomes `projects-client-delivery`;
  - the prepare `delivery_pack.py` becomes `projects-delivery-pack` (preceded by `reporting-report-collect` in phase 1);
  - the finish `delivery_apply.py` becomes `projects-delivery-apply`;
  - command rules for check and record;
  - `subagents:` become `projects-worker` and `projects-reviewer`.
- **`engagement-kickoff`**: `agent:` becomes `projects-engagement-kickoff`; the rule becomes `Bash(projects-engagement-folders:*)`; `subagents:` becomes `projects-reviewer`.
- **`engagement-closeout`**: `agent:` becomes `projects-engagement-closeout`; `subagents:` becomes `projects-reviewer`.
- **`project-health`**:
  - `agent:` becomes `projects-health-review`;
  - the prepare and finish `project_health_check.py`, `task_stack_check.py`, `task_stack_apply.py` and `task_stack_report.py` become `projects-health-check`, `projects-task-stack-check`, `-apply` and `-report`;
  - `subagents:` become worker and reviewer.
- **`tech-portfolio-review`** (per-client): `agent:` becomes `projects-tech-portfolio`; `subagents:` become worker and reviewer.

**Merge candidates for later**
1. Kickoff, delivery and closeout as stages of one `projects-engagement` agent, which the architecture review suggested. The reason is the same engagement Context, DELIVERY-RULES and folders. The risks are three different cadences (one-off, twice weekly, one-off), different review sets, and a long agent. Do it only if the stages share a `## Steps` with a stage branch.
2. `projects-health-review` with productivity's weekly review or task-stack jobs. The reason is that it is Portal task-stack work over the owner's own projects. The risk is that it moves across buckets and productivity is already the largest.

**Risks and open questions**
1. Should project-health, check-in and landscape leave projects (health and check-in to productivity, landscape to strategy)? Today they make projects depend on three productivity agents and two strategy commands.
2. The copied `task-stack-workstream` with `task_stack_apply.py` is a writer to the Portal. Copies must stay identical, or two plugins will apply change sets differently. This is the strongest case for the drift check (or for decision 3's `core`).
3. The phase-1 `report_collect` hand-off makes the client-delivery Automation need the reporting plugin installed. Acceptable?
4. Splitting `project-engagement-workstream` touches the kickoff and closeout DONE checklists that the agents cite by item number (items 2, 3, 1, 4). Keep the numbering.
5. The hard-coded skill-folder paths in `delivery_apply.py` and `delivery_pack.py`.

**Effort:** M to L. The work is driven by the task-stack copies and the project-health Automation's productivity scripts, the engagement skill split, and the report_collect hand-off. The client-engagement jobs themselves are clean.

**Suggested order:**
1. `projects-tech-portfolio` (no cross-department code).
2. `projects-engagement-kickoff` and `projects-engagement-closeout` (after the skill split and the `engagement-context` copy).
3. `projects-client-delivery`.
4. `projects-health-review` last, after deciding where it lives.

---

### process-engineering

**Today:** 12 agents (6 main), 7 skills, 9 scripts (plus 1 helper module). This is the front half of a client engagement:
- an anonymized assessment summary from survey exports;
- the interview Read-Out, Feedback by Topic and BASELINE;
- a reviewed swim-lane map of one process, as-is and to-be, every box traced to a quote;
- workshop preparation and summary;
- a ranked automation backlog with business cases;
- running a client survey season behind a data fence.

**Plugin:** `process-engineering`, one plugin. Open question: rename the plugin to `process`. `build_bins.py` would then give `process-flow-check` and `process-claim-ledger` instead of `process-engineering-process-flow-check`.

**Main agents**

| Current | Proposed | What it does | Dispatch after | Automation(s) |
|---|---|---|---|---|
| `assessment-intake-orchestrator` | `process-engineering-assessment-intake` | Turns assessment exports into an anonymized summary, interview topics and candidate opportunities. | reviewer: recount and anonymity, red team. It writes itself. | `assessment-intake` |
| `discovery-synthesis-orchestrator` | `process-engineering-discovery-synthesis` | Turns interview transcripts into the Read-Out, Feedback by Topic and BASELINE. | worker: one per transcript (parallel). Reviewer: two fact halves, counts and anonymity, red team. It writes itself. | `discovery-synthesis` |
| `process-flow-orchestrator` | `process-engineering-process-flow` | Maps one process as-is and to-be from transcripts, done when `process-flow-check` passes. | worker: one per transcript (parallel). Reviewer: two fact halves, completeness, red team on the render. It maps itself. | `process-flow` |
| `workshop-orchestrator` | `process-engineering-workshop` | Prepare mode builds the run of show, cards and pre-read; summarize mode turns the workshop into priorities, owners and dates. | worker: one per transcript (summarize). Reviewer: time box and pre-read screen, facts, red team. | `discovery-workshop` |
| `automation-scoping-orchestrator` | `process-engineering-automation-scoping` | Turns a reviewed to-be map into a ranked automation backlog with business cases from stated inputs only. | reviewer: numbers, completeness (pains with no item), tracing, red team | `automation-scoping` |
| `survey-analytics-orchestrator` | `process-engineering-survey-analytics` | Keeps a survey season's checklist current from pipeline logs, and drafts and checks the readout from aggregate tables only. | reviewer: numbers plus minimum cell size, red team. It writes the readout itself, inside the fence. | `survey-analytics` |

**Specialists: where their know-how goes**

| Agent | Lines | Becomes | Note |
|---|---|---|---|
| `transcript-reader` | 105 | section "Read one transcript" of `transcript-tools` (claim inventory, leading flag, pains, wishes, numbers, json block), run by the worker | `transcript-tools` is already copied to projects and reporting. Productivity's `meeting-analyst` only mentions it. |
| `discovery-writer` | 29 | sections "Write the summary", "Write the synthesis", "Write the workshop pack or summary" and "Write the backlog" of the per-job skills, run by the main agent | The method skills stay as they are. |
| `discovery-checker` | 25 | section "Check a discovery draft" (counts, anonymization, tracing, arithmetic) in `discovery-workstream`, reviewer checklist | |
| `process-flow-mapper` | 26 | section "Draw a map version" of `process-flow-workstream`, run by the main agent | It runs check and render itself. |
| `survey-analytics-writer` | 22 | section "Write the readout" of `survey-analytics-workstream`, run by the main agent | The fence binds the main agent already. |
| `completeness-audit` | 57 | `review-completeness` (shared source, absorbing `reference-process-models`), for the reviewer | Copied to compliance and personal too. |
| `fact-check`, `executive-red-team`, `numbers-reviewer` | n/a | `review-*` copies, for the reviewer | |

**Reviewer:** `process-engineering-reviewer` (opus by default). It checks:
- assessment: recounts and anonymity;
- synthesis: interview counts and anonymity;
- process flow: two fact halves and a reference-model audit, returned in the `contract.md` json blocks so `claim-ledger record` keeps working;
- workshop: time box and pre-read screen;
- automation scoping: values and ranking recomputed, every item traced to a map step and pain;
- survey: figures re-derived and cells at or above the minimum.

It is briefed with "Check a discovery draft", the job skills' check sections and the copies `review-numbers`, `review-facts`, `review-red-team` and `review-completeness`.

**Worker:** `process-engineering-worker` (sonnet), needed for transcript reading only: synthesis, process flow, workshop summarize.

**Skills**

| Skill | Action | `## Steps`? | Scripts → commands |
|---|---|---|---|
| `discovery-workstream` (141 lines, four products) | **split.** Keep the shared parts (engagement, rules file, Run folder, conduct, returns, "Check a discovery draft"). Move each product's checklist and writer section into new job skills `assessment-intake`, `discovery-synthesis`, `workshop` (modes as branches) and `automation-scoping`. | yes, on the four new skills; none on the shared one | none |
| `process-flow-workstream` | keep; add "Draw a map version", "Check the map"; a Run-mode `## Steps` (the interactive Phases 0 to 7 stay as method) | yes | `claim_ledger`, `process_flow_check`, `_prepare`, `_publish`, `_render`, `_template`, `swimlane_generator` → `process-engineering-claim-ledger`, `-process-flow-check`, and so on (or `process-claim-ledger`, `process-flow-check`, `process-flow-prepare` under the rename) |
| `survey-analytics-workstream` | keep; add "Write the readout", "Check the readout" (numbers plus the cell-size line) | yes | none |
| `interview-synthesis` | keep (method); drop the productivity references (`meeting-*`, `task-stack-capture`, `portal-write-safety`) or keep them as words | no | none |
| `workshop-design` | keep (method, already has Steps for the hand path); the job skill `workshop` holds the Run Steps | the existing Steps stay | none |
| `transcript-tools` | keep as the shared source; add "Read one transcript" | no | `srt_transcript_collapse`, `transcript_hygiene` → `process-engineering-srt-transcript-collapse`, `-transcript-hygiene` |
| `reference-process-models` | merge into `review-completeness` (`references/`). Point `process_flow_prepare.py` at the plugin's copy. | no | none |
| `project-engagement-baseline` (from projects) | move in; the BASELINE is a discovery product | no | none |
| new copies | `orchestration-workstream`, `comms-confirm`, `unslop-deliverable`, `brand-guide` (process-flow's visual system cites it), `review-*`, `engagement-context`, `automation-backlog-format` | no | `process-engineering-confirm` |

**Cross-department dependencies, and the hand-offs between main agents**

| What | Direction | Resolution |
|---|---|---|
| Assessment intake → discovery synthesis (summary as `A01`, topics as tags) | inside the department, main → main | **already file-based:** discovery-synthesis picks up a summary filed in the `working` Source. The hand-off is the `for_owner` item "adopt the topics; arm `discovery-synthesis` for engagement X once the interviews are done". Remove the agent name from Returns. |
| Assessment intake → automation scoping (candidate opportunities) | inside the department | file only: scoping reads the summary from `working` when one is filed (step 1 already does); no item needed |
| Discovery synthesis → process flow (a process the BASELINE names) | inside the department | a `for_owner` item per process: "launch `process-flow` for engagement X, process `<slug>`", with the launch inputs spelled out so the owner can copy them |
| Workshop summarize → discovery synthesis (transcript as a source) | inside the department | the transcript is already in the transcripts Source; the next synthesis run picks it up with `since`. A `for_owner` line only. |
| Process flow → automation scoping (once the owner has reviewed the to-be map) | inside the department | add to process-flow's single "drafts ready to review" item: "after review, launch `automation-scoping` for `<process>`". The owner's review is the gate, so no automatic chaining. |
| Automation scoping → `bd-proposal-orchestrator` (sales) | process-engineering → sales | **hand-off by file and owner:** the backlog CSV and business cases go to the engagement's `working` Source; a `for_owner` item reads "chosen items → launch the sales `bd-proposal` Automation with the backlog path". The CSV columns and business-case headings move to a small shared `automation-backlog-format` skill, copied into process-engineering and sales, so the producer and reader cannot drift. |
| Automation scoping → `software-developer` (software) | process-engineering → software | **hand-off through the Portal, which the issue harvest already reads:** on the owner's yes (the comms-confirm task), each chosen item is recorded as a Portal note in the issue standard (step, pain, value, acceptance). Software's issue collector turns it into a GitHub issue, which the factory works. The process-engineering session never touches GitHub and names no software agent. |
| `fact-check`, `executive-red-team`, `numbers-reviewer` (reporting) | process-engineering → reporting | copy in `review-*` |
| `project-engagement-baseline` (projects) | process-engineering → projects | move in |
| `client-update-workstream` (ENGAGEMENT-CONTEXT sections) | process-engineering → reporting | `engagement-context` copy |
| `report-tieout` named in `claim-ledger.md`; `brand-guide` in `visual-system.md`; `unslop-deliverable` | process-engineering → accounting, marketing | words only for report-tieout (drop); copy `brand-guide` and `unslop-deliverable` |
| `learning-seminar-orchestrator`, `writing-seminar-builder` (learning) | named in workshop "Not for" and Never lines | drop, or reword ("a training seminar is the learning plugin's") |
| `transcript-tools`, `interview-synthesis`, `workshop-design` used by projects, reporting, productivity, learning, chief-of-staff | others → process-engineering | `transcript-tools` is a shared source copied out. The others are mentions only. If learning's seminar builder really uses `workshop-design` templates, copy it. |
| `completeness-audit` used by compliance and personal | others → process-engineering | `review-completeness` copies |

**Automations to update:**
- **`process-flow`**:
  - `agent:` becomes `process-engineering-process-flow`;
  - the prepare `process_flow_prepare.py` and finish `process_flow_publish.py` become the matching commands;
  - the rules for check, claim-ledger and render become command rules;
  - change the `reference_models_dir` default;
  - `subagents:` become worker and reviewer.
- **`discovery-synthesis`** and **`discovery-workshop`**: new agent names; the `srt_transcript_collapse.py` rule becomes `Bash(process-engineering-srt-transcript-collapse:*)`; worker and reviewer.
- **`assessment-intake`**, **`automation-scoping`**, **`survey-analytics`**: new agent names; `subagents:` becomes reviewer only.
- Survey: make sure the sidecar still keeps client text away from hosted models. The fence is a rule in the skill, and the Automation may also restrict reads.

**Merge candidates for later**
1. Assessment intake, discovery synthesis and workshop as one `discovery` agent with a product input, which the architecture review suggested. The reason is one rules file (DISCOVERY-RULES), one Context, the same writer and checker. The risk is that each product's checklist and Steps then hang off one skill, and Sentinel reads one `## Steps` per skill, so it needs a mode branch at step 1.
2. Automation scoping into the same `discovery` agent. The reason is the same rules file. The risk is that it depends on a reviewed process-flow map and has a heavier review set (numbers and completeness).
3. Keep survey analytics and process flow separate. Each has its own rules file, and survey has its own data fence.

**Risks and open questions**
1. Rename the plugin to `process` for usable command and agent names?
2. The reviewer's return must keep `contract.md`'s fact-check, completeness and red-team blocks, because `claim_ledger.py record` rejects anything else. Test this first with a dry-run process-flow.
3. Folding `reference-process-models` into `review-completeness` means process-flow prepare reads models from a copied skill. Keep a stable relative path in every copy.
4. Recording scoping's chosen items as Portal notes needs a writer. Either the comms-confirm close plus a small finish-step script (`process-engineering-backlog-post`, new), or the owner pastes the item. Decide which, and check that the issue harvest's repo map can match a client process to a repository.
5. The `bd-proposal` hand-off needs sales to adopt `automation-backlog-format` in its rules-first intake.
6. The transcript worker is sonnet today. Keep `process-engineering-worker` on sonnet and raise the model in the brief where needed.

**Effort:** M. The work is driven by splitting `discovery-workstream` into four job skills with Steps, keeping the process-flow reviewer blocks compatible, and the backlog hand-offs (which need small changes in sales). Internally the department is self-contained: one hard-coded path and no cross-department dispatch beyond the shared reviewers.

**Suggested order:**
1. `transcript-tools` with "Read one transcript", and `review-completeness` (both shared sources).
2. `process-engineering-process-flow`, the most script-backed and the best test of the reviewer return compatibility.
3. `process-engineering-discovery-synthesis`.
4. `process-engineering-assessment-intake` and `process-engineering-workshop`.
5. `process-engineering-automation-scoping`, with the sales and software hand-offs.
6. `process-engineering-survey-analytics`.

---

### productivity

**Today:** 39 agents (13 main), 37 skills, 54 scripts (45 plus 9 `_common.py`). Productivity runs one person's working week through the Insights Portal. It replies to email in the owner's voice, chases follow-ups and the owner's own promises, routes clerical mail to the assistant, keeps professional relationships warm, cleans CRM data, prepares meetings and turns Fellow transcripts into notes and tasks. It also captures, clarifies and reconciles the task stack, prepares the GTD weekly review, keeps the calendar in order and runs a monthly time study. Nothing is sent: replies are drafts, and changes are change sets that `task_stack_apply.py` (or `calendar_apply.py`, or `meeting_publish.py`) applies after the session. Productivity is also the source of the most widely shared skills in the toolbox: `task-stack-workstream` (8 departments), `comms-confirm` (7), `office-files` (5), `email-drafter-method`, `comms-draft-check`, `waiting-on-tracker-method`, `meeting-analyst-method` and the researchers.

**Plugin:** `productivity`, as **one plugin. I recommend against splitting it.**

The obvious split is communications (reply, follow-up, clerical, relationships), meetings (prep, transcripts), tasks (capture, clarify, reconcile, weekly review, calendar) and CRM (hygiene). The jobs don't fall cleanly into those buckets. What they share cuts across all four:
- **Change set and rules file.** `task-stack-workstream`'s change-set contract and `TASK-STACK-RULES.md` are used by follow-up (promise tasks), clerical routing (the assistant's task), calendar-steward (`calendar_apply.py` calls `task_stack_apply.py`), weekly review (`weekly_review_changes.py` then `task_stack_apply.py`) and all three task jobs.
- **Waiting-on tracker.** `waiting-on-tracker-method` serves follow-up (comms), meeting-prep (meetings) and weekly-review (tasks).
- **Task-stack checker.** `task-reconcile-checker` serves reconcile, clarify, capture and follow-up.
- **Email drafting and draft checks.** The email drafter and `comms-draft-check` serve follow-up, clerical, relationship tending and reply. Relationship tending is filed under CRM but is really an email-drafting job.
- **Feeds between jobs.** The time study's said-but-not-seen file feeds task capture and the weekly review. Meeting transcripts create tasks and "Enrich contact:" tasks that `crm-context-enrichment` works.

Under decision 1 (copies, not shared skills), a four-way split would copy `task-stack-workstream` into 3 or 4 plugins, `waiting-on-tracker-method` into 3, and the drafter and draft check into 2, and add four reviewers. Every job reads the same owner's Portal under the same rules folder. The review's own rule is that "jobs merge when they share a folder and a rules file", which puts these in one bucket. CRM alone would hold one job, and meetings two.

The one real cost of a single plugin is listing size: about 33 skill descriptions in every productivity session. That is handled by moving out the skills productivity does not itself use (below), not by a split. If the listing still proves heavy in the trials, the only defensible fallback is two plugins: "people" (email, relationships, CRM, meetings) and "work" (task stack, weekly review, calendar, time study), with `task-stack-workstream` and `waiting-on-tracker-method` copied into both.

**Main agents**

| current name | proposed name | what it does | dispatch after | Automation |
|---|---|---|---|---|
| `email-reply-orchestrator` | `productivity-email-replier` | Replies to one person's email as a checked draft in Outlook Drafts, asking the owner only their decisions. | worker (Research the email: isolates the pack reading); reviewer (Check a reply: independence; `email_deliver.py` refuses without the PASS record and content hash) | email-reply |
| `comms-follow-up-orchestrator` | `productivity-follow-up` | Gives every open commitment a state, drafts the clear nudges and deliveries, and proposes promise tasks. | worker (Find what is waiting, isolated; Draft one email, one per item in parallel); reviewer (Check a staged draft; Check task-stack ops) | follow-up |
| `comms-clerical-routing-orchestrator` | `productivity-clerical-router` | Routes the day's clerical mail to the assistant as one batched task, with cover notes as drafts. | worker (Triage the day's mail, which would flood the main context; cover-note drafts); reviewer (Check routed threads; Check a staged draft) | clerical-routing |
| `crm-relationship-tending-orchestrator` | `productivity-relationship-tender` | Picks the week's outreach, finds one reason to write to each contact, and stages checked drafts. | worker (Research a person, haiku, per pick; Draft one email per pick); reviewer (Check a staged draft) | relationship-tending |
| `crm-data-hygiene-orchestrator` | `productivity-crm-hygiene` | Weekly CRM pass: evidenced fixes, approved merges, defect drafts and a metrics note. | worker (Analyse a slice, up to 4 in parallel); reviewer (Check fixes and merges) | crm-hygiene |
| `meeting-prep-orchestrator` | `productivity-meeting-preparer` | Picks the day's external meetings and writes one checked prep note per meeting that search can find. | worker (Find what is waiting, scoped to the attendees, per meeting in parallel; Research a person for thin attendees); reviewer (Check a pack) | meeting-prep |
| `meeting-transcript-orchestrator` | `productivity-transcript-processor` | Turns unprocessed Fellow recordings into Portal notes and tasks, a few per run, by marker. | worker (Analyse a transcript: one full transcript each, and it keeps the analyst apart from the checker); reviewer (Check a meeting plan; `meeting_publish.py` requires the PASS for that `plan_hash`) | meeting-worker |
| `task-capture-orchestrator` | `productivity-task-capturer` | Turns said-but-not-seen commitments and quick-capture lines into tasks, never twice. | worker (Decide a batch, parallel); reviewer (Check task-stack ops, medium-confidence creates) | task-capture |
| `task-clarify-orchestrator` | `productivity-task-clarifier` | Daily GTD clarify: files, retitles, dates and sets WAITING on open tasks, as a change set. | worker (Clarify a batch of 25, parallel); reviewer (Check task-stack ops) | task-clarify |
| `task-reconcile-orchestrator` | `productivity-task-reconciler` | Nightly pass that closes done, duplicate and dead tasks on evidence, as a change set. | worker (Prove a batch, about 4 in parallel); reviewer (Check task-stack ops: every cancel, merge and medium op) | task-reconcile |
| `weekly-review-orchestrator` | `productivity-weekly-review` | Prepares the GTD weekly review as one numbered approval list; the approve pass reports what will apply. | worker (Triage a batch of about 10, parallel; Find what is waiting, threads lens); reviewer: none (the owner approves every item, and `weekly_review_pack.py` and `weekly_review_check.py` compute done) | weekly-review |
| `calendar-steward-orchestrator` | `productivity-calendar-steward` | Proposes two weeks of focus blocks, conflict fixes, declines and prep as one approval list. | reviewer only (Check the proposals); the analyst becomes the main agent's own section, since it is one slice from a precomputed scan | calendar-steward |
| `time-study-orchestrator` | `productivity-time-study` | Rebuilds where the owner's time went in 10-minute slots, with evidence tiers and said-but-not-seen. | worker (Segment a recording, per recording; Assemble a day and Classify a day's topics, per day; up to 8 at once); reviewer (Check sampled slots) | time-study |

Text-match "dispatches" that are false: `weekly-review-orchestrator` only points to the goal alignment (`goal-alignment-orchestrator`) for cadence. The time-study specialists, `email-drafter` and `email-triager` only mention their callers. `domain-researcher` recommends follow-up passes to the caller and runs none itself. No productivity main agent dispatches another main agent or another department's agent.

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `calendar-steward-analyst` | 28 | section "Propose the changes" of `calendar-steward-method`, run by main | One analyst over a precomputed scan; dispatching it buys nothing. |
| `calendar-steward-checker` | 24 | reviewer checklist "Check the proposals" in `calendar-steward-method` | Free slot, real event, decline justified, move touches no attendee. |
| `comms-draft-checker` | 19 | reviewer checklist: `comms-draft-check` "The tests, in order" | Also used by sales; the skill is copied there. |
| `comms-routing-checker` | 14 | reviewer checklist "Check routed threads" in `comms-clerical-routing-workstream` | |
| `crm-hygiene-analyst` | 20 | section "Analyse a slice" of `crm-hygiene-workstream` (from "The analyst's return" and `references/hygiene-method.md`), by worker | |
| `crm-hygiene-checker` | 14 | reviewer checklist "Check fixes and merges" in `crm-hygiene-workstream` | |
| `domain-researcher` | 120 | section "Research a domain" of new skill `portal-research`, by worker | No productivity job uses it (chief-of-staff and sales do); it lives here as the source to copy. |
| `email-checker` | 11 | reviewer checklist "Check a reply" in `comms-reply-to-email` (keeps `briefs/checker.md` and `checker.schema.json`) | Must return the JSON record with the content hash. Reporting's `client-update-orchestrator` uses it too. |
| `email-context-researcher` | 11 | section "Research the email" of `comms-reply-to-email` (`briefs/researcher.md`), by worker (sonnet) | Writes `brief.md` in `~/.local/state/comms-reply/`. |
| `email-drafter` | 118 | `email-drafter-method` (plus `unslop-email`), by worker (model opus in the dispatch), one per draft; the replier may draft its single reply itself | Copied to sales, reporting, learning and chief-of-staff. |
| `email-researcher` | 85 | section "Research email history" of `portal-research`, by worker (haiku) | No productivity job uses it; source for sales and chief-of-staff. |
| `email-triager` | 123 | `email-triager-method`, by worker (context isolation) | Clerical routing; interactive `comms-inbox-replies`. |
| `meeting-analyst` | 99 | `meeting-analyst-method` with `briefs/analyst.md`, by worker | Copied to learning, process-engineering (`transcript-reader`) and chief-of-staff. |
| `meeting-checker` | 13 | reviewer checklist "Check a meeting plan" in `meeting-scheduled-worker` (`briefs/checker.md`) | Return must match `checker.schema.json` with `plan_hash`. |
| `meeting-prep-checker` | 14 | reviewer checklist "Check a pack" in `meeting-prep-workstream` | |
| `person-researcher` | 90 | section "Research a person" of `portal-research`, by worker (haiku) | Used by relationship tending and meeting prep; copied to sales and chief-of-staff. |
| `task-capture-worker` | 33 | section "Decide a batch" of `task-stack-capture`, by worker | |
| `task-clarify-worker` | 31 | section "Clarify a batch" of `task-stack-clarify`, by worker | Projects' `project-health-orchestrator` dispatches it today. |
| `task-reconcile-checker` | 26 | reviewer checklist "Check task-stack ops" in `task-stack-workstream` | Goes wherever that skill is copied: projects and recurring-summaries' daily-plan use it today. |
| `task-reconcile-evidence` | 41 | section "Prove a batch" of new skill `task-stack-reconcile`, by worker | Needs `git -C` for commit evidence. |
| `time-study-checker` | 30 | reviewer checklist "Check sampled slots" in `report-time-study` (`briefs/checker.md`) | Read-only, sonnet. |
| `time-study-day-assembler` | 40 | section "Assemble a day" of `report-time-study` (`briefs/day-assembler.md`), by worker (opus) | Needs `productivity-time-study-day-lint`. |
| `time-study-meeting-segmenter` | 35 | section "Segment a recording" (`briefs/meeting-segmenter.md`), by worker (sonnet) | |
| `time-study-topic-classifier` | 39 | section "Classify a day's topics" (`briefs/topic-classifier.md`), by worker (sonnet) | |
| `waiting-on-tracker` | 148 | `waiting-on-tracker-method`, by worker (sonnet) | The agent body mostly repeats the 146-line method; fold the difference in. Copied to projects and chief-of-staff. |
| `weekly-review-triage` | 24 | section "Triage a batch" of `weekly-review-workstream`, by worker | |

**Reviewer:** `productivity-reviewer` (opus; read-only Portal tools plus `Bash(productivity-email-draft-show:*)`). It judges from the sources alone, never from the maker's notes. It is briefed with one of these checklists:
- "Check a reply" (`comms-reply-to-email`, JSON plus content hash)
- "The tests, in order" (`comms-draft-check`)
- "Check routed threads" (clerical)
- "Check task-stack ops" (`task-stack-workstream`)
- "Check a meeting plan" (`meeting-scheduled-worker`, schema with `plan_hash`)
- "Check a pack" (`meeting-prep-workstream`)
- "Check the proposals" (`calendar-steward-method`)
- "Check fixes and merges" (`crm-hygiene-workstream`)
- "Check sampled slots" (`report-time-study`)

None of the four shared reviewers (`numbers-reviewer`, `fact-check`, `executive-red-team`, `completeness-audit`) is used by a productivity job, so none needs copying in. Only `pressure-test-method` mentions one, and it is moving out.

**Worker:** needed (`productivity-worker`, sonnet by default, with the model given in the dispatch: opus for drafting, analysing a transcript and assembling a day; haiku for the researchers). It covers these slices:
- task batches (capture, clarify, reconcile, weekly triage)
- CRM slices
- one draft per item
- one person-research per pick or attendee
- the waiting-on pass
- the day's mail triage
- one transcript analysis
- the reply research
- the time study's per-recording and per-day work

**Skills**

| skill | decision | add `## Steps`? | scripts → commands |
|---|---|---|---|
| `comms-reply-to-email` | keep; add sections "Research the email" and "Check a reply"; move `email_deliver.py` and `email_draft_show.py` to `comms-draft-check`, and `notify_owner.py` to `comms-confirm` (see cross-department table) | has Steps (update hand-offs to `productivity-worker` and `productivity-reviewer`) | `productivity-find-contact`, `productivity-find-email`, `productivity-email-context-pack` |
| `comms-draft-check` | keep, grows into the self-contained outbound skill: checklist plus the gate, show and deliver commands, so copies work alone | no (a checklist) | `productivity-outbound-check`, `productivity-email-draft-show`, `productivity-email-deliver` |
| `comms-follow-up-workstream` | keep (merging into `comms-follow-ups` is a later option) | yes | none |
| `comms-follow-ups` | keep (interactive); rewrite dispatches to the worker sections | no | none |
| `comms-clerical-routing-workstream` | keep; add "Check routed threads" | yes | none |
| `comms-inbox-replies` | keep (interactive); dispatch the worker with `email-triager-method` and `email-drafter-method` | no | none |
| `comms-draft-email` | keep (interactive) | no | none |
| `comms-log-call`, `meeting-log` | keep (merging into one `portal-log` is a later option) | no | none |
| `comms-confirm` | **move the source out** (no productivity job uses it); productivity takes a copy for `notify_owner` | has Steps | in the copy: `productivity-confirm`, `productivity-confirm-portal`, `productivity-waiting`, `productivity-notify-owner` |
| `office-files` | **move the source out** (no productivity agent uses it); productivity takes no copy | no | none here |
| `email-drafter-method` | keep (copy source for 4 departments) | has Steps | none |
| `email-triager-method` | keep | has Steps | none |
| `waiting-on-tracker-method` | keep (copy source); fold in the agent's extras | has Steps | none |
| new `portal-research` | new, from the three researcher agents: "Research a person", "Research email history", "Research a domain" | no (sections) | none |
| `crm-relationship-workstream` | keep | yes | none |
| `crm-hygiene-workstream` | keep; add "Analyse a slice" and "Check fixes and merges" | yes | `productivity-portal-issue-file` |
| `crm-contact-update`, `crm-data-review`, `crm-context-enrichment` | keep (interactive or reference) | no | none |
| `meeting-prep-workstream` | keep; add "Check a pack" (merging into `meeting-prep` is a later option) | yes | none |
| `meeting-prep` | keep (single meeting; copied to chief-of-staff) | no | none |
| `meeting-scheduled-worker` | keep the name (the settings table `[meeting-scheduled-worker]` and `enrichment_agent` depend on it); add "Check a meeting plan" | has Steps | `productivity-meeting-pending`, `-meeting-existing`, `-meeting-fetch`, `-meeting-validate`, `-meeting-publish`, `-meeting-acknowledge`, `-meeting-skip` |
| `meeting-analyst-method` | keep (copy source) | has Steps | none |
| `meeting-followup`, `meeting-summary`, `meeting-summary-style-guide` | keep | no | none (`meeting-summary-to-pdf` is external) |
| `meeting-portal-notes` | keep; rename its scripts, whose current names are vague | no | `productivity-meeting-notes-prepare`, `-meeting-notes-read`, `-meeting-notes-check` (today `prepare_transcript.py`, `portal_read.py`, `check_evidence.py`) |
| `task-stack-workstream` | keep (copy source for 8 departments); add "Check task-stack ops" | no (conduct and contract) | `productivity-task-stack-apply`, `-task-stack-check`, `-task-stack-queue`, `-task-stack-report` |
| `task-stack-capture` | keep; add "Decide a batch" | yes | `productivity-task-capture-queue`, `-task-capture-record`, `-task-capture-check` |
| `task-stack-clarify` | keep; add "Clarify a batch" | yes | none |
| new `task-stack-reconcile` | new; the reconcile procedure now in the 69-line agent file plus "Prove a batch" | yes | none (uses task-stack commands) |
| `task-stack-produce` | **move to chief-of-staff** (its only user, `chief-of-staff-producer`) | n/a | none |
| `weekly-review-workstream` | keep; add "Triage a batch" | yes | `productivity-weekly-review-gather`, `-pack`, `-check`, `-changes`, `-publish` |
| `calendar-steward-method` | keep; add "Propose the changes" and "Check the proposals"; split off `calendar_time.py` | yes | `productivity-calendar-steward-scan`, `-calendar-apply`, `-calendar-steward-check` |
| new `calendar-time` | split from `calendar-steward-method` (projects and strategy use only this script) | no | `productivity-calendar-time` |
| `report-time-study` | keep; sections from `briefs/` (Segment a recording, Assemble a day, Classify a day's topics, Check sampled slots) | has Steps | `productivity-time-study-collect`, `-time-study-tool`, `-time-study-day-lint`, `-time-study-said-not-seen`, `-time-study-check` |
| `portal-write-safety`, `portal-note-types` | keep (copy sources) | no | none |
| `pressure-test-method` | **move out** (open question 9); no productivity job uses it | n/a | none |
| copied in: `orchestration-workstream` (software), `unslop-email` (marketing) | copies | no | none |

Net: about 34 skills in the plugin (37, minus 4 moved out, plus 3 new, with `comms-confirm` held as a copy), and 15 agents (13 main, worker, reviewer) instead of 39.

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `task-stack-workstream` with apply, check and "Check task-stack ops" | productivity → accounting, chief-of-staff, compliance, decision-playbooks, projects, recurring-summaries, sales, strategy | **copy in** (build step). Scripts that call `task_stack_apply.py` or `task_stack_check.py` by path (`delivery_apply.py`, `chief_of_staff_fleet.py`, `calendar_apply.py`, the goal-alignment finish step) call their own plugin's copy. |
| `task-reconcile-checker` agent | → projects (client-delivery, project-health), recurring-summaries (daily-plan) | **copy in** via the checklist section; each department's reviewer runs it |
| `task-clarify-worker` agent | → projects (project-health's bucket drain) | **copy in** `task-stack-clarify` for projects' worker, or **hand off**: leave the tasks in their buckets and let the daily clarify pass file them (my preference: fewer copies) |
| `comms-confirm` (calls `notify_owner.py`) | → accounting, finance, personal, process-engineering, projects, reporting, sales | **copy in**; move the source to a non-plugin shared-source folder; move `notify_owner.py` into it (chief-of-staff's `_common.py` calls it by path too) |
| `office-files` | → accounting, compliance, finance, reporting, sales | **copy in**; source to the shared-source folder; productivity drops it |
| `email-drafter` agent and `email-drafter-method` (with `unslop-email`) | → sales (bd-pipeline, bd-lead-intake), reporting (client-update, `weekly-reporter`), learning (community), chief-of-staff | **copy in**; each department's worker runs it |
| `comms-draft-checker` agent | → sales | **copy in** `comms-draft-check`; sales-reviewer |
| `email-checker` agent, `email_deliver.py` | → reporting (`client-update-orchestrator`, `client_update_deliver.py`), accounting (`firm_billing_deliver.py`) | **copy in** the enlarged `comms-draft-check` (checklist plus outbound, show and deliver) |
| `person-researcher`, `domain-researcher`, `email-researcher` | → sales, chief-of-staff | **copy in** `portal-research` |
| `meeting-analyst` and its method | → learning (community), process-engineering (`transcript-reader`), chief-of-staff | **copy in** `meeting-analyst-method` (plus `meeting-summary-style-guide`) |
| `waiting-on-tracker` | → projects (project-health), chief-of-staff | **copy in** `waiting-on-tracker-method` |
| `calendar_time.py` | → projects (`project-landscape`), strategy (`goal-auditor`) | **copy in** the new `calendar-time` |
| calendar proposal file and `calendar_apply.py` | ↔ recurring-summaries (daily-plan's focus-block proposals are published and applied by calendar-apply) | **copy** `calendar-steward-method` into recurring-summaries for now; later, the cross-department merge candidate below |
| `meeting-prep` | → chief-of-staff (`meeting-prep-doer`); nightly sweep's calendar preparer mentions the job | **copy in** for chief-of-staff; the nightly sweep only defers to the Automation (**drop**) |
| `task-stack-produce` | → chief-of-staff | **move** to chief-of-staff |
| `portal-write-safety`, `portal-note-types` | → chief-of-staff, process-engineering, projects, reporting | **copy in** |
| `task-stack-capture`, said-but-not-seen file | → chief-of-staff `quick-capture`, process-engineering `interview-synthesis` (mentions), chief-of-staff `work-survey` (reads the file) | **drop** (file contracts and hand-off text, no skill needed) |
| chief-of-staff fleet launches productivity Automations by name | chief-of-staff → productivity | **hand-off** stays (it launches Automations); update the names it reads |
| `orchestration-workstream` | software → productivity | **copy in** |
| `unslop-email` | marketing → productivity | **copy in** |

**Automations to update** (all 13). Each needs the same changes:
- the agent line changes to the new name
- the run gets `--plugin-dir <toolbox>/productivity`
- `Bash(python3 ~/.claude/skills/<skill>/scripts/x.py:*)` rules become `Bash(productivity-x:*)`
- the overlay's `subagents:` becomes `productivity-worker` and `productivity-reviewer`
- `Skill` and `Agent` are allowed
- the `orchestrator` and `agent_slug` values are kept or aliased (risk 1)

Job-specific changes:
- **task-reconcile:** prepare `task_stack_check.py` → `productivity-task-stack-check`; finish → `productivity-task-stack-apply`, `-task-stack-check`, `-task-stack-report`.
- **task-clarify:** prepare check and `task_stack_queue.py` → `-task-stack-check`, `-task-stack-queue`; finish as reconcile.
- **task-capture:** prepare `task_capture_queue.py` (and the stack check) → `-task-capture-queue`; finish → `-task-stack-apply`, `-task-capture-record`, `-task-capture-check`.
- **weekly-review:** prepare `-weekly-review-gather`; the session runs `-weekly-review-pack` and `-check`; finish → `-weekly-review-changes`, `-task-stack-apply`, `-weekly-review-publish`.
- **calendar-steward:** prepare `-calendar-steward-scan`; finish `-calendar-apply apply` and `publish`, then `-calendar-steward-check`.
- **meeting-worker:** the session runs the seven `-meeting-*` commands; keep `Write(~/.local/state/meeting-processing/**)`.
- **email-reply:** the session runs `-find-contact`, `-find-email`, `-outbound-check`, `-email-context-pack`, `-email-draft-show`, `-email-deliver`, `-notify-owner`; keep `Write(~/.local/state/comms-reply/**)` and `mkdir -p`.
- **time-study:** prepare `-time-study-collect`; the session runs `-time-study-*`; replace today's `Agent(time-study-...)` restriction with the worker and reviewer; the external `timestudy` program is unchanged.
- **follow-up, clerical-routing:** if the finish applies `changes.json`, use `-task-stack-apply`; no session scripts.
- **crm-hygiene:** finish files defects with `productivity-portal-issue-file`.
- **relationship-tending, meeting-prep:** no scripts; only the agent, plugin and subagent changes.

**Merge candidates for later**
1. **task-capture, task-clarify and task-reconcile into `productivity-task-steward`, with a mode input.** Reason: same rules file, same change set, apply, check and report commands, same checklist; they differ only in the queue and the cadence. Risk: `task_stack_apply.py`'s `CHECKED_CANCELS` and the change-set `orchestrator` field key on the reconcile agent's name; the combined skill grows long.
2. **follow-up, clerical-routing and relationship-tending (and perhaps email-reply) into `productivity-comms`.** Reason: all stage drafts that one draft check gates. Risk: three different rules files and gates (clerical's go switch, relationship's cooldown and sent count by `agent_slug`), and email-reply is interactive and asks the owner.
3. **meeting-prep and meeting-transcript into `productivity-meetings`.** Reason: same attendees, notes and Portal. Risk: different cadence and write path (prep writes notes in the session; the transcript job writes only through `meeting_publish.py` by marker). Small gain.
4. **calendar-steward into daily-plan (recurring-summaries).** Reason: a shared proposal file and `calendar_apply.py`; the architecture review proposed it. Risk: moves a job across departments, and the approval task's marker uses `calendar-steward-orchestrator`.
5. **time-study into weekly-review** (the review's suggestion). Weak: monthly, heavy fan-out, its own home folder. I'd keep them apart.

**Risks and open questions**
1. **Hard-coded orchestrator names.** `task_stack_apply.py` holds `CHECKED_CANCELS = ("task-reconcile-orchestrator",)`. `ORCHESTRATOR` constants in the `_common.py` of `calendar-steward-method` and `weekly-review-workstream` mark approval tasks and change sets. Relationship tending finds last week's drafts by `agent_slug`, and daily-plan checks a tool name. A rename needs an alias period that accepts the old and new names, or the old values kept as constants.
2. **Script-to-script calls by path:** `calendar_apply.py` → `task_stack_apply.py`, `email_deliver.py` → `outbound_check.py`, `confirm.py` → `notify_owner.py`, plus the other departments' `firm_billing_deliver.py`, `client_update_deliver.py`, `delivery_apply.py` and `chief_of_staff_fleet.py`. `build_bins.py` prefixes each copy's command with its own department (`projects-task-stack-apply`), so a copied script must find its sibling relative to its own file, not through `~/.claude/skills` or a fixed command name.
3. **Settings tables are keyed by skill name** (`[task-stack-workstream]`, `[calendar-steward-method]`, `[meeting-scheduled-worker]`, `[comms-reply-to-email]`). Any skill rename breaks the owner's settings, which is why the table above keeps the names.
4. **Shared state across copies:** `~/.local/state/task-stack` (apply logs, undo) and the comms-reply state folder are written by every copy. If the copy-build check is skipped, two versions write one ledger.
5. **One generic reviewer, exact return shapes.** It must return each checklist's exact shape (`checker.schema.json` with content hash for replies, `plan_hash` for meeting plans), or `email-deliver` and `meeting-publish` refuse. The first runs need watching.
6. **Model tiers are lost** unless each section states its tier: haiku researchers, sonnet tracker and segmenter, opus drafter and assembler.
7. **Interactive skills name agents directly** (`comms-inbox-replies`, `comms-follow-ups`, `crm-data-review`); they must be rewritten to dispatch `productivity-worker` with a section name.
8. **Listing cost** of one plugin of about 34 skills; this decides between one plugin and the two-way fallback, and is measured in the trial.
9. **Where `pressure-test-method` goes.** It red-teams the owner's systems from a rotation ledger and has no agent or Automation in the toolbox; toolbox-maintenance or chief-of-staff is the likely home. The owner may run it from an Automation I cannot see.
10. **Time-study workers today have no Portal tools.** A generic worker would, so the time-study Automation's allowlist must stay narrow.
11. **Command naming for shared copies:** `projects-task-stack-apply` and `productivity-task-stack-apply` are the same script under two names. Does the owner accept that, or want one unprefixed name for copied commands?
12. **email-reply as an Automation** has to ask the owner; check that its sidecar's "When no one is present" behaviour survives the rewrite.

**Effort:** L. The work is driven by:
- 13 jobs and 26 specialists
- productivity being the copy source for about 10 skills feeding 10 departments
- hard-coded names in four scripts
- four other departments' scripts calling productivity scripts by path

**Suggested order:**
1. Set up the shared-source and copy build (`task-stack-workstream`, `comms-confirm` with `notify_owner`, `office-files`, `comms-draft-check` with deliver and show, `orchestration-workstream`, `unslop-email`), because other departments block on it.
2. Plugin skeleton, `bin/`, `productivity-worker` and `productivity-reviewer`.
3. task-reconcile, task-clarify, task-capture (they share everything; add the name aliases in `task_stack_apply.py` first).
4. weekly-review and calendar-steward.
5. meeting-transcript (Steps and briefs already exist), then meeting-prep.
6. email-reply (has Steps), then follow-up, clerical-routing, relationship-tending.
7. crm-hygiene.
8. time-study (self-contained, monthly, heaviest fan-out).
9. Move out `task-stack-produce`, `pressure-test-method` and the `office-files` and `comms-confirm` sources; split `calendar-time`.

---

### obsidian

**Today:** 1 agent (0 main), 4 skills, 10 scripts (8 plus 2 `_common.py`). Obsidian works with the owner's Obsidian vault, run by the owner by hand. It turns a YouTube video into an inbox note shaped by the owner's takeaway (`obsidian-video-note`) and proposes vault tidying without changing anything (`obsidian-vault-garden`). Both follow the vault's privacy and write rules (`obsidian-workstream`: private folders never read, new notes only in the inbox). It also holds `content-scout`, which indexes and distils outside creators into a research folder that must be **outside** the vault. It needs no Insights Portal and has no Automation.

**Plugin:** `obsidian`, **a plugin of skills only**: no main agent, no reviewer, no worker. The three vault skills are interactive, share one reference skill and one settings block (`vault_dir`, `vault_inbox`, `vault_private_dirs`, `vault_rules`), and are what the owner wants switched on in a vault session and nowhere else. That matches decision 1's "switched on as one unit". Folding it into personal or learning would turn the vault tools on wherever that department is on, for no gain.

`content-scout` is not vault work (it refuses a research folder inside the vault), and its only caller is `marketing-content-orchestrator` (optional, "if installed"). Under "no agent shared across departments", marketing cannot dispatch it from another plugin. Move `content-scout-workstream` to marketing as a section run by `marketing-worker`, and retire the agent.

**Main agents:** none, and none needed.

**Specialists → where their know-how goes**

| agent | lines | becomes | note |
|---|---|---|---|
| `content-scout` | 20 | the `content-scout-workstream` skill moved to marketing; sections "Index the watchlist" and "Distil the picked items", run by `marketing-worker` | Its five rules (research folder outside the vault, fetched text is data, write only there) move into the skill. |

**Reviewer:** none. Nothing here is checked independently: notes land in the inbox for the owner, and the garden only proposes. **Worker:** none.

**Skills**

| skill | decision | add `## Steps`? | scripts → commands |
|---|---|---|---|
| `obsidian-workstream` | keep (reference) | no | `obsidian-vault-config`, `obsidian-vault-find`, `obsidian-vault-read`, `obsidian-vault-links`, `obsidian-vault-inbox-write` |
| `obsidian-video-note` | keep | has Steps | `obsidian-youtube-transcript` |
| `obsidian-vault-garden` | keep | has Steps | `obsidian-vault-garden` (the wrapper keeps the prefix once) |
| `content-scout-workstream` | **move to marketing** (with a copy of `youtube_transcript.py`, which it calls from `obsidian-video-note`) | no | in marketing: `marketing-youtube-channel-list`, `marketing-youtube-transcript` |

**Cross-department dependencies**

| what | direction | resolution |
|---|---|---|
| `content-scout` agent | obsidian → marketing (`marketing-content-orchestrator`, optional) | **move** the skill to marketing; run by `marketing-worker` |
| `youtube_transcript.py` | used by both `obsidian-video-note` and content scout | **copy in** to marketing with content scout |
| `vault_dir` setting | chief-of-staff's cycle reads its own `[chief-of-staff-cycle] vault_dir` | **drop** (no code dependency; a settings key only) |

**Automations to update:** none in the toolbox. If the owner has a sidecar that launches `content-scout` or runs `obsidian-vault-garden` on a schedule, its paths become `obsidian-*` or `marketing-*` commands, and a content-scout Automation becomes a marketing one.

**Merge candidates for later:** none inside obsidian. Folding the whole plugin into personal is possible if the owner wants fewer plugins. The cost is vault tools in every personal session.

**Risks and open questions**
1. Skill-only plugins have no agent to start with `--agent`; the owner uses them by name (`obsidian:obsidian-video-note`) in a session with the plugin on. Confirm that is how the owner works.
2. `YT_DLP` and the yt-dlp install are needed by both obsidian and marketing after the move. Settings docs must list both.
3. `content-scout-workstream`'s settings table `[content-scout-workstream]` (`research_dir`, `watchlist`) keeps its name in marketing so the owner's settings still apply.

**Effort:** S. Driven by 8 commands, the content-scout move and rewriting script paths in four `SKILL.md` files. **Suggested order:** plugin skeleton and `bin/`; repoint the three vault skills to commands; move content scout to marketing with the marketing migration.
