---
name: project-status-update
description: Takes a one-line project status update from the owner ("Fabrikam rollout - sent the plan, waiting on Sam"), finds the Insights Portal project, appends the update to its recent status note or starts one, and makes the task changes the line plainly states (done, waiting, started, cancelled, a new to-do), then confirms in one line. Use when the owner gives a quick status line about a project. Not for a full project review (project-checkin) or general capture of notes and ideas (quick-capture).
argument-hint: <project> - <status update>
allowed-tools: mcp__insights-portal__search, mcp__insights-portal__list_entities, mcp__insights-portal__get, mcp__insights-portal__sync_health, mcp__insights-portal__update_note, mcp__insights-portal__create_note, mcp__insights-portal__update_task, Read, Write, Bash(python3 ~/.claude/skills/task-stack-workstream/scripts/task_stack_apply.py:*), Bash(mkdir -p:*)
---

# Project status update

The fastest way to update a project's status. One line in, done.

**The owner provided:** $ARGUMENTS

## Step 1: Parse the input

Split the input on the first ` - `, `--` or `:`:
- **Left side**: the project's name or a keyword to search for.
- **Right side**: the status update.

With no separator, treat the whole input as the update and ask which project.

## Step 2: Find the project

```
search(query="<project keyword>")
```

With several matches, pick the most likely by name. Ask only when it is truly ambiguous (three or more equally plausible matches).

## Step 3: Find the current status note

```
list_entities(entity_type="note", filters={"search": "<project name>", "entity_type": "project", "entity_id": "<project_id>"}, limit=3)
```

Look for notes tagged `project-checkin`, or with "Status" in the title, and take the most recent.

## Step 4: Update

Before any write, follow the `portal-write-safety` skill (resolve entities by id, never by name; `CANCELLED` with evidence, never `DONE`; check sync health first).

**When a status note from the last 14 days exists**: read it with `get(entity_type="note", id_or_query="...")`, append a dated block, and save it with `update_note(id="...", fields={"content": "<updated content>"})`:

```
### Update - <today's date>
<the owner's status text>
```

**Otherwise** create one:

```
create_note(
    title="Status: <Project Name> - <today>",
    content="## Status Update - <today>\n\n<the owner's status text>",
    note_type="episodic",
    associations=[{"entity_type": "project", "entity_id": "<project_id>"}],
    tag_ids=[<the project-checkin tag's id>]
)
```

`create_note` takes tag ids, not names; when the `project-checkin` tag's id cannot be found, create the note untagged and say so in the confirmation.

## Step 5: Act on what the line plainly says

Scan the update for these signals and act without asking:

| Signal | Action |
|---|---|
| "done", "sent", "completed", "finished", "resolved" | Find the matching task, `update_task(id="...", status="DONE")` |
| "waiting on", "blocked by", "need response from" | Find the matching task, `update_task(id="...", status="WAITING")` |
| "need to", "should", "must", "don't let X slip" | A new task, created the way quick-capture creates one (through task-stack-apply, filed in this project) |
| "started", "working on", "in progress" | Find the matching task, `update_task(id="...", status="IN_PROGRESS")` |
| "cancelled", "killed", "dropped" | Find the matching task, `update_task(id="...", status="CANCELLED")` |

Find the matching task by the update's keywords:

```
list_entities(entity_type="task", filters={"project_id": "<project_id>", "search": "<keyword>"}, limit=5)
```

Act only on a high-confidence match. When it is ambiguous, skip the task change and just keep the note.

## Step 6: Confirm in one line

```
Updated **<Project Name>**. <Note updated or created>. <Tasks: completed X, created Y, when any>.
```

No follow-up questions and no project briefing.

## Rules

- Speed over thoroughness: a fifteen-second interaction, not a check-in.
- Never present the project's context back; the owner knows what they are updating.
- Tag status notes `project-checkin` so the weekly project-health pass sees them.
- One line of confirmation, two sentences at most.
