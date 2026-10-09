---
name: goal-alignment-workstream
description: Reference loaded last by the goal-alignment agents, not for a user request; adds to orchestration-workstream and task-stack-workstream. Covers the item contract (one line the owner reads, the verbs ok, park, close and letters, the task-stack-apply ops each makes for a project link, a goal parked, closed, restated or re-prioritised, a project stopped, a strategic-goal mapping) and how to judge a goal starved of time, time serving nothing stated and a candidate to stop. For the monthly pass, start goal-alignment-orchestrator.
---

# Working on the goal alignment

This skill extends `orchestration-workstream` and `task-stack-workstream`: follow both. Read them at `~/.claude/skills/<name>/SKILL.md` if they are not loaded. What follows is only what the goal alignment adds.

Once a month the owner sees their goals set against their projects and against where the month's time actually went, and settles the gaps by answering one numbered list. Nothing they do not approve is written: the approve pass applies exactly the ops of the verb they answered, through `task-stack-apply`. So the proposals are the whole value. A proposal they cannot judge from one line is a proposal they answer `no`.

The owner's strategic goals document (for example one written in the TELOS format; its path is in the rules file) sits above the Portal goals: a set of domains, each with numbered strategic goals (`Operations 1`), and the owner's review cadence. The `goal-alignment-strategy` worker reads it; the other workers do not.

## The questions

1. **Every active goal has an active project.** A goal nothing drives is waiting its turn (park it), done (close it ACHIEVED, with the evidence), dead (close it CANCELLED), or real and neglected (a decision: start a project for it, named). A VISION goal with no project this quarter can be normal; a P1 or P2 goal with none is not.
2. **Every project serves a goal.** A project with no goal is linked to the goal it plainly serves; when two goals could fit, the owner chooses with letters. The weekly project-health pass links the unambiguous ones on its own, so what reaches this list is what it left to them, and the projects whose goal was closed.
3. **The month's time sits where the priorities say.** The time study's hours by domain (and by topic) against each domain's goals and their priorities. A P1 or P2 goal in a domain that got almost no time, with nothing finished under it, is starved: re-prioritise it if the time was right, or say what has to give if the goal was. A work domain that took real time with no goal is time serving nothing stated: a goal is missing (a decision, naming it), or the work should stop.
4. **Candidates to stop.** A project with no live goal and no activity for the rules' window, or one whose hours are real while its goal is not: propose to stop it (park it ON_HOLD, or close it when no open task is left), naming what is freed and what is lost.
5. **Goals to retire or restate.** A goal whose wording no longer says what the work is: offer the restated title as a choice. The owner's words are theirs; restate only when the record (the projects under it, their own notes) says what the goal has become.

Every finding rests on a Portal ref or a time-study figure from the gathered inputs. Hours are the time study's, never the calendar's alone, and partial coverage is said.

## The item

Each thing proposed is one item, returned in `extra.items`:

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

## The return

The `orchestration-workstream` block, with the items in `extra.items` and, from the strategic-goals worker (`goal-alignment-strategy`), `extra.pulse` (one row per strategic goal: `domain`, `goal` such as `Operations 1`, `title`, `status` one of on track, drifting, stalled, done, retire, not read, and `line`) and, in a quarterly month, `extra.quarterly` (the template's parts `balance`, `goal_status`, `contradictions`, `subtraction`, `parked`, `emphasis`, each a list of lines). `items` holds one row per goal or project judged (`test` the section, `item` its ref, `state` `proposed` or `skipped`, `evidence`, `note`). What could not be judged is a `findings` line.

## The scripts

In `scripts/`, run as `python3 ~/.claude/skills/goal-alignment-workstream/scripts/<name>.py`: `goal_alignment_gather.py` (before the session), `goal_alignment_pack.py` and `goal_alignment_check.py` (in it), `goal_alignment_changes.py` and `goal_alignment_publish.py` (after it, around `task_stack_apply.py`). Every task write, the alignment task included, goes through `task_stack_apply.py`. Settings: `state_dir`, `portal_mcp_config`, `[goal-alignment-workstream] rules_file`, and `alignment_project` or `alignment_domain` in the same table for the alignment task.
