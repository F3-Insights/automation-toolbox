---
name: quick-capture
description: Universal capture into the Insights Portal. The owner says anything (a fact, a to-do, a call summary, an idea, a follow-up) and it is classified, linked to the right people and companies, and filed as a note, an activity or a task, with embedded action items pulled out and a visible receipt of what was filed where. Tasks go through task-stack-apply so the owner's task rules hold and nothing is duplicated. Use when the owner says "capture this", "note that", "remind me to". Not for a project's status line (project-status-update) or logging a call in detail (comms-log-call).
argument-hint: '[anything: notes, tasks, ideas, call summaries]'
allowed-tools: mcp__insights-portal__*, AskUserQuestion, Read, Write, Bash(python3 ~/.claude/skills/task-stack-workstream/scripts/task_stack_apply.py:*), Bash(mkdir -p:*)
---

# Capture

One behavior for all capture. The owner says it and forgets it; this skill handles the routing.

**The owner provided:** $ARGUMENTS

## What this handles

The owner's job is one thing: capture information. This skill handles:
- classification (note, task, activity or idea);
- entity linking (who and what it is about);
- routing (where it goes);
- action extraction (what follow-ups it holds).

## Step 1: Accept the input

With arguments, use them as the raw input and go on to classification. With none, ask "What do you want to capture?" and accept any format; messy is fine.

## Step 2: Classify the intent

| Classification | Signals | Action |
|---|---|---|
| **Information** | facts, insights, observations | Create a note |
| **Task** | "I need to", "should", action verbs | Create a task (below) |
| **Call or meeting** | "just spoke with", "had a call", "met with" | Create an activity |
| **Idea** | "thought about", "what if", "could we" | A note with an idea tag |
| **Follow-up** | "need to follow up", "waiting on", "check back" | An activity and a reminder flag |
| **Question** | "find out", "research", "what is" | A note as a research item |

Do not ask which type; infer it. Confirm only when it is truly ambiguous.

Honour self-corrections: "call Sam, no wait, email him" yields only the email. Backdate a capture through `occurred_at_hint` rather than stamping it now.

## Step 3: Extract the entities

Identify the people, companies, dates and deadlines, and domains in the input.

## Step 4: Match to the CRM

For people: `search(query="<name>")`; when a single clear match surfaces, hydrate it with `get(entity_type="contact", id_or_query="<name or id>")`. For companies: `search(query="<company>")`, then `get(entity_type="company", id_or_query="<company>")` for a clear match.

- An exact match: use it without asking.
- Several matches: ask which one.
- No match: offer to create it, but keep the flow moving.

## Step 5: Route to action

Before any create, update or draft call, follow the `portal-write-safety` skill: propose by default, resolve entities by id never by name, `CANCELLED` with evidence never `DONE`, check sync health first.

By classification:
- **Information**: a note.
- **Task**: the task flow below, through task-stack-apply, never `create_task`.
- **Call or meeting**: an activity, and a note when it is substantial.
- **Idea**: a note with an idea tag.
- **Follow-up**: an activity and a flag.

### Tasks go through task-stack-apply

A task is created the way every task-stack orchestrator creates one, so the owner's task rules (`TASK-STACK-RULES.md`: a verb-first title, an owner, a project or the domain's catch-all, no duplicate of an open task) hold here too and the scheduled task capture can never make a second copy. Never call `create_task` for a task.

1. Write it the `task-stack-capture` way (load that skill if it is not loaded): verb first, filed, dated only from what was said. Search the owner's open tasks for the same commitment first; if one holds it, say so and offer to add a comment instead.
2. Make a folder `<state_dir>/task-stack/capture/interactive/<yyyymmdd-hhmmss>/` (the setting `state_dir`) and write `changes.json` there:

   ```json
   {"tool": "task-stack-changes", "version": 1, "orchestrator": "quick-capture",
    "dry_run": false,
    "ops": [{"id": "n1", "op": "create", "title": "<verb-first title>", "project": "<uuid>",
             "due_date": "<YYYY-MM-DD or omit>", "description": "<the capture in the owner's words>",
             "source": "interactive:<yyyymmdd-hhmmss>-1", "reason": "Captured by the owner"}]}
   ```

   (`domain` instead of `project` files it in the domain's catch-all project.)
3. Run `python3 ~/.claude/skills/task-stack-workstream/scripts/task_stack_apply.py --run <that folder>` and read its outcome: `applied` gives the new task's ref; `refused` gives the rule and the reason (a duplicate names the task that already is it). Show the owner either one plainly; `task_stack_apply.py --undo <that folder>/undo.jsonl` takes it back.

Notes, activities and contact updates still go through the Portal tools directly.

## Step 6: Extract action items

Scan for embedded actions:
- "I need to send them X": a task for the owner.
- "They'll get back to me about Y": a waiting-on flag.
- "We agreed to meet on Z": a calendar note.

## Step 7: Confirm the capture

Every capture produces a visible receipt, including on error: if a write fails, say so plainly rather than closing quietly.

```
Captured as <type>: "<title>"

Linked to:
- Dana Whitfield (Acme Components)
- Acme Components

Extracted:
- 1 task identified (create it?)
- Deadline: next Friday

Anything to add?
```

## Smart behaviors

- **Domain inference.** A contact linked to a domain, or a company in one, sets the domain; otherwise ask only when the routing matters.
- **Duplicate prevention.** Before creating, check for very recent notes on the same topic: "You captured something about Acme Components two hours ago; add to that instead?"
- **Input size.** An input too large to process is said so; never truncate it silently.
- **Minimal friction.** Do not ask for what can be inferred; investigate before asking, and ask a metadata question only after an empty investigation. Questions carry no ids and never ask for a priority opinion. Accept incomplete data, default to a note when the classification is unclear: something captured beats nothing captured.

## Remember

One reliable behavior: the owner captures, you route. Trust through visibility: always show what was captured and where. Fast capture beats perfect capture.
