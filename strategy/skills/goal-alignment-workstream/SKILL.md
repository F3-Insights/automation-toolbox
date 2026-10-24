---
name: goal-alignment-workstream
description: "The monthly goal alignment's method, loaded by strategy-goal-alignment and by the strategy-worker it dispatches, not for a user request; adds to orchestration-workstream, task-stack-workstream and goal-audit. Covers the pack and approve passes as Steps, the sections Audit goals against work and Pulse the strategic goals, the item contract (one line the owner reads, the verbs ok, park, close and letters, and the task-stack-apply ops each makes) and how to judge a goal starved of time, time serving nothing stated and a candidate to stop. For the monthly pass, start strategy-goal-alignment."
---

# Working on the goal alignment

This skill extends `orchestration-workstream`, `task-stack-workstream` and `goal-audit`: follow them. Load them if they are not loaded. What follows is only what the goal alignment adds.

Once a month the owner sees their goals set against their projects and against where the month's time actually went, and settles the gaps by answering one numbered list, "1) ok 2) park 3) close 4) no". Nothing they do not approve is written: after they answer, the finish step applies exactly the ops of the verb they answered, through `task-stack-apply`. So the proposals are the whole value. A proposal they cannot judge from one line is a proposal they answer `no`. Bias to action: propose what the record supports without hedging. A good note is short: at most about forty items, worst first; the weekly project-health pass handles project hygiene (next actions, owners, unambiguous goal links), and the note says what it left to it.

The owner's strategic goals document (for example one written in the TELOS format; its path is in `cadence.json`) sits above the Portal goals: a set of domains, each with numbered strategic goals (`Operations 1`), and the owner's review cadence. Only section Pulse the strategic goals reads it, and only the domains the rules let agents read.

## What the Run has

- `RUN/pass.json`: the month, the pass (`pack`, `approve` or `auto`, resolved before the session), the goal-alignment home and the month's folder.
- `RUN/inputs/` (pack pass), gathered by `strategy-goal-alignment-gather` read only: `goals.json` (each active goal, the projects driving it, what finished and moved under it this month, its domain's hours, and the flags `no_project`, `starved`, `quiet`; parked goals apart), `projects.json` (each active project, its goal or none, activity, the goals it could serve, `stop_candidate`), `domains.json` (hours and share per domain, goals and projects, `unserved`), `time.json` (hours by domain, topic and evidence tier; coverage), `stack.json` (the trust score's goal and project components), `cadence.json` (monthly or quarterly, the pulse domains, `readable` and `owner_only` domains, the goals document and template paths), `goalmap.json` (approved and missing strategic-goal mappings), `carried.json` (last month's unsettled items).
- `RUN/answers.json` and `RUN/review.json` (approve pass): the published review and a preview of how each answer resolves.
- The owner's `TASK-STACK-RULES.md` and `GOAL-ALIGNMENT-RULES.md` (paths in the Run's inputs). Read both first; they override this skill.
- The Portal, read only. `RUN` is the working folder; only the main agent writes there, by absolute path.

The note shows, in this order: where the month's time went, by domain and topic, against each domain's goals; goals starved of time; time and work that serve no stated goal; projects with no goal; goals with no active project; candidates to stop; priorities to restate; the Portal goals and the strategic goals; the monthly pulse of the domains in rotation (every readable domain in a quarterly month); in a quarterly month, the quarterly review template pre-filled; the decisions only the owner can make.

## Steps

For `strategy-goal-alignment`.

1. [judgment] Orient. Read the rules files, `RUN/pass.json` and every input. Note the time study's coverage, the domains whose hours and goal priorities disagree, the goals with no project, the projects with no goal. Items in `carried.json` come first: put each back where it still matters.
   → approve pass: step 7
2. [judgment] Audit goals against work yourself, by the section of that name, from the inputs folder.
   → a large portfolio (more than about forty active goals and projects together): step 3
   → audited: step 4
3. [hand-off: strategy-worker] One worker per group of domains, in parallel, on section Audit goals against work, each with the inputs folder, its domains, the month, the cadence, the owner's contact id and the rules files' paths; never one goal or project in two briefs, nothing of your own view. Save each return as `RUN/returns/audit-<n>.json` as it arrives.
4. [judgment] Pulse the strategic goals yourself, by the section of that name.
5. [judgment] Decide and write `RUN/review.json`: the audit's items with your edits where a proposal is weak, the `map` items (at most about eight a month, the active P1 and P2 goals first), `decisions` for what only the owner can settle; `schema`, `month`, `cadence` (as `cadence.json` says), `dry_run`, `summary` (three to five lines: the month in one breath, the largest gap between time and priorities, the one thing that most needs them; at the turn of the year, the annual review), `notes` per section (what the numbers mean, never a repeat of them), `pulse`, `quarterly` (a quarterly month only), `items`.
6. [script] Render: `strategy-goal-alignment-pack RUN`. Fix `review.json` until it prints `VALID`, then read `RUN/NOTE.md` once as the owner would: cut what they do not need, sharpen what they cannot judge.
   → problems: step 5 (max 3)
   → VALID: step 8
7. [judgment] Approve pass. Read the preview; report how many items each answer settled, what will be applied, which mappings will be recorded, and each item whose answer cannot be applied (modified, unclear, a verb it does not offer), quoting their words, so they can answer it again. Write nothing else.
8. [judgment] Report as the Automation asks. The finish step publishes the note (PRIVATE, on the owner's alignment task) and applies; you publish nothing.
   → reported: done

Done is computed: `strategy-goal-alignment-check MONTH` tests the note, its publication (PRIVATE, read back), the answers and what was applied. Before the session the Automation runs `strategy-goal-alignment-gather`; after it `strategy-goal-alignment-changes` (the change set, from the published review and the owner's answers only), `task-stack-apply` and `strategy-goal-alignment-publish` (keeps the month, makes the alignment task through `task-stack-apply`, writes the private note, records approved mappings in `goal-map.json`); each takes `--dry-run-if`. A dry run writes `"dry_run": true` in `review.json`, and nothing is published or applied. With no one present everything runs the same: what only the owner can decide is an item, never a wait.

## The questions

1. **Every active goal has an active project.** A goal nothing drives is waiting its turn (park it), done (close it ACHIEVED, with the evidence), dead (close it CANCELLED), or real and neglected (a decision: start a project for it, named). A VISION goal with no project this quarter can be normal; a P1 or P2 goal with none is not.
2. **Every project serves a goal.** A project with no goal is linked to the goal it plainly serves; when two goals could fit, the owner chooses with letters. The weekly project-health pass links the unambiguous ones on its own, so what reaches this list is what it left to them, and the projects whose goal was closed.
3. **The month's time sits where the priorities say.** The time study's hours by domain (and by topic) against each domain's goals and their priorities. A P1 or P2 goal in a domain that got almost no time, with nothing finished under it, is starved: re-prioritise it if the time was right, or say what has to give if the goal was. A work domain that took real time with no goal is time serving nothing stated: a goal is missing (a decision, naming it), or the work should stop.
4. **Candidates to stop.** A project with no live goal and no activity for the rules' window, or one whose hours are real while its goal is not: propose to stop it (park it ON_HOLD, or close it when no open task is left), naming what is freed and what is lost.
5. **Goals to retire or restate.** A goal whose wording no longer says what the work is: offer the restated title as a choice. The owner's words are theirs; restate only when the record (the projects under it, their own notes) says what the goal has become.

Every finding rests on a Portal ref or a time-study figure from the gathered inputs. Hours are the time study's, never the calendar's alone, and partial coverage is said.

## Audit goals against work

Run by the main agent, or by a `strategy-worker` per group of domains for a large portfolio. Read only; write nothing. The facts are the inputs folder: judge, do not gather. Spend Portal reads only on what the inputs cannot settle (a goal's description, a project's notes, the evidence for a close). The hours are the time study's, not the calendar's: say the coverage when it is partial. The private goals document is not read here.

Judge by `goal-audit`'s findings and its closed list of actions, and turn each finding into an item in the shape below, one per goal or project per section, worst first, at most about thirty:

| goal-audit finding | Item section |
|---|---|
| 1. Goals with no active project | `goals` |
| 2. Projects with no goal | `links` |
| 4. Priority goals that got nothing | `starved` |
| 5 and 6. Time and work that serve no stated goal | `unserved` |
| 7. Candidates to stop | `stop` |
| A priority the behaviour contradicts | `priority` |
| What only the owner can decide | `decisions` |

The actions become verbs and ops: link is `project_edit` `goal_id`; reprioritise is `goal_edit` or `project_edit` `priority`; stop is park or `project_close`; create project, schedule time and delegate are a `decisions` item with letters. Unfiled tasks (finding 3) are the weekly passes' work: count them in the notes only.

A worker returns the `orchestration-workstream` block with `workstream: "audit-goals-against-work"`, the items in `extra.items`, one `items` row per goal or project judged (`test` the section, `item` its ref, `state` `proposed` or `skipped`, `evidence`, `note`), and what could not be judged in `findings`.

## Pulse the strategic goals

The main agent does this itself. The strategic goals document names domains, each with numbered strategic goals, and sets a review cadence: typically a monthly pulse of two or three domains in rotation, one line of status per goal, and a quarterly full pass with a template whose status lines an assistant may pre-fill while the scores and decisions stay the owner's. A goals framework left unreviewed drifts and dies; these lines keep it reviewed.

- **What you read.** `cadence.json` gives the cadence, `pulse_domains`, `readable` (the domains you may read) and `owner_only` (the domains you must not read), and the document and template paths. In the document read only the sections of the `readable` domains, and the Cadence section; never the others, even to skim. The evidence for each line is `goals.json`, `projects.json`, `domains.json` and `time.json`.
- **Nothing from the document beyond domain names, goal numbers and short titles** enters `review.json` or the note. A title is at most eight words, your own, with no figures or names from the document.
- **The pulse.** For each strategic goal of each readable domain in `pulse_domains`: its number (`Operations 1`), a short title, a status (on track, drifting, stalled, done, retire) and one line of why from the evidence: the Portal goals and projects that serve it, what finished, the month's hours in its domains. A goal with no Portal goal, no project and no hours for the month is stalled, or a zombie candidate if it was quiet before. One row per owner-only domain: `goal` empty, status `not read`, line "Yours to write."
- **The mapping.** For each Portal goal `goalmap.json` lists as unmapped that you can place with confidence (its title, description and projects plainly serve a numbered strategic goal of a readable domain), a `map` item: `map.goal` the Portal goal, `map.telos` the number, the proposal "Record that <Portal goal> serves <number>", `why` one line of evidence, `options` `{"ok": []}`. P1 and P2 goals first, at most eight. A Portal goal that serves none of them is a note (it may be work no stated goal covers).
- **The quarterly pre-fill** (a quarterly month only). Read the template, then pre-fill as lists of lines: `goal_status` (one line per strategic goal of the readable domains, flagging any quiet two quarters running as a zombie candidate), `contradictions` (what the quarter's time or projects did against a stated goal or guardrail), `subtraction` and `emphasis` (candidates only), `parked` (the open and parked items now decidable), `balance` (one line per domain of the evidence beside it, never a score: scores are the owner's).

## The item

Each thing proposed is one item in `review.json` (and in a worker's `extra.items`):

```json
{"section": "goals", "goal": "portal://goal/<uuid>", "title": "Second warehouse: no project since June",
 "proposal": "Park the goal until the lease decision in January",
 "why": "No project, no task and 0 h this month; the lease talks are paused (note of 3/12)",
 "evidence": "portal://note/<uuid>", "default": "park",
 "options": {"close": [{"op": "goal_close", "goal": "portal://goal/<uuid>", "status": "CANCELLED"}]}}
```

- `section`: `starved`, `unserved`, `links`, `goals`, `stop`, `priority`, `map` or `decisions`.
- An item about a goal names it in `goal`; about a project, in `project`. One item per goal or project per section.
- `proposal` is one sentence with the goal, the project, the priority or the date in it. `why` is the fact that makes it right, in one line, with the hours where time is the point.
- `options` maps each verb to the task-stack-apply ops it would make (`task-stack-workstream` has the shapes; leave out `id` and `reason`, the note fills them):
  - `ok`: the proposal itself;
  - `park`: added for you when the item has a `goal` (`goal_edit` status DEFERRED) or only a `project` (`project_edit` status ON_HOLD); give your own only when it should differ;
  - `close`: `goal_close` (CANCELLED, or ACHIEVED with evidence) or `project_close` (CANCELLED; the project must have no open task left);
  - letters `a` to `f` for a choice, each labelled in `choices`. `no` is always offered and never writes; do not list it.
- **Link**: `{"op": "project_edit", "project": "...", "set": {"goal_id": "<uuid>"}}`; the goal is active and in the project's domain.
- **Re-prioritise**: `goal_edit` with `set: {"priority": "P2"}`, or `project_edit` with `priority` for a project.
- **Restate**: a letter whose option is `goal_edit` with `set: {"title": "<the new words>"}`.
- **Close a goal after its projects**: put the `project_close` or relinking ops in the same option before the `goal_close`; task-stack-apply refuses a goal something still serves.
- **Map** (section `map`): `"map": {"goal": "portal://goal/<uuid>", "telos": "Operations 1"}` and `"options": {"ok": []}`, where `telos` is the strategic goal's number. The approval records the mapping in the goal-alignment home folder, nothing in the Portal.
- **Decisions**: what only the owner can settle with no op behind it (start a project for a neglected P1 goal, name a missing goal): letters with `[]` options record their choice.
- `default` is the verb or letter `ok` means for the item.

## The return and review.json

`pulse` is one row per strategic goal: `domain`, `goal` (such as `Operations 1`), `title`, `status` (on track, drifting, stalled, done, retire, not read) and `line`. `quarterly` holds the template's parts `balance`, `goal_status`, `contradictions`, `subtraction`, `parked`, `emphasis`, each a list of lines. A worker's audit return is as section Audit goals against work says.

## Authority

`GOAL-ALIGNMENT-RULES.md` says what may change, and only on the owner's approval: goals re-prioritised, parked, restated or closed; projects linked, put on hold, re-prioritised or closed. Every change goes through `task-stack-apply` after the session, never by hand. The owner's strategic goals document is read, never written.

## The commands

`strategy-goal-alignment-gather` (before the session), `strategy-goal-alignment-pack` and `strategy-goal-alignment-check` (in it), `strategy-goal-alignment-changes` and `strategy-goal-alignment-publish` (after it, around `task-stack-apply`). Every task write, the alignment task included, goes through `task-stack-apply`. Settings: `state_dir`, `portal_mcp_config`, `[goal-alignment-workstream] rules_file`, and `alignment_project` or `alignment_domain` in the same table for the alignment task (or `--alignment-project` / `--alignment-domain` on the publish command).
