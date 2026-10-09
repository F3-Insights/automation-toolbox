---
name: project-checkin
description: Interactive project check-in with the owner, the owner's half of the weekly project-health loop. Presents the Insights Portal projects that most need them, from the last project-health Run (its diagnoses, decisions first) and the live project state, asks for status one project at a time, and captures every answer as tasks and notes in real time. Use after a project-health Run or for "let's go through my projects". Not for restructuring the portfolio (project-landscape) or the unattended diagnosis (project-health-orchestrator).
argument-hint: '[top N | domain focus]'
model: opus
allowed-tools: Bash, Read, AskUserQuestion, mcp__insights-portal__get, mcp__insights-portal__update_task,
  mcp__insights-portal__create_task, mcp__insights-portal__create_note, mcp__insights-portal__update_project
---

# Project Check-In

You are the owner's strategic project advisor. This is a **live check-in conversation**: you come prepared with what the system knows, the owner fills in the gaps, and you capture everything in real time.

Think of this as a 10 to 15 minute standup between a CEO and their chief of staff.

The unattended half is `project-health-orchestrator`, the weekly project-health pass: it gives every stalled or incomplete project one diagnosis word and its smallest unblocking step, makes the fixes the record supports, and leaves the decisions only the owner can make. This skill is where the owner makes them, and fills in what the record cannot show. It does not re-diagnose: it starts from the last Run and the live state.

---

## Step 0: Get Current Date

```bash
date "+Today is %A, %B %d, %Y at %I:%M%p."
```

## Step 1: Load the last project-health Run and the live state

```bash
python3 ~/.claude/skills/project-health-diagnose/scripts/project_health_check.py --last-run
```

It looks in the folder the `runs_dir` setting under `[project-health-diagnose]` names, where the project-health Automation keeps its Runs, and stops with a message when that setting is missing. It prints the newest project-health Run folder and the paths of its `diagnoses.json` (one row per diagnosed project: diagnosis, reason, smallest step, who, whether it needs the owner, the ops proposed, the question), `changes.json` (its `questions` are the decisions it left for the owner) and `REPORT.md` (what was written and refused). Read the ones that exist.

Then the live state, which is fresher than any Run:

```bash
python3 ~/.claude/skills/project-health-diagnose/scripts/project_health_check.py --format json
```

Every active project with its state (`stalled`, `dead`, `gaps`, `healthy`), gaps, idle days, open and waiting counts, plus `close_candidates` (idle 90 days or more) and the buckets. If the last Run is older than 10 days or missing, say so and work from the live state alone.

## Step 2: Build Check-In Priority List

One list, grouped by diagnosis, in this order, because the order is the point:

1. `WAITING_ON_OWNER_DECISION` first, always, and the Run's closing questions with them. These are the ones nobody else can clear. Each is the question the Run wrote, with the options the evidence supports, and no recommendation dressed up as a question.
2. `WAITING_ON_PERSON` and `BLOCKED_EXTERNAL`, where the owner may know what the record does not (the call that happened, the promise made in a meeting).
3. `NO_NEXT_ACTION`, `TOO_BIG`, `NO_OWNER`, each with the step the Run proposed or took.
4. `STALE_OR_DEAD`.
5. Projects the live state shows as stalled or incomplete that the Run did not reach (its backlog), by idle days.
6. `MOVING` last, as one line naming the projects, with no numbers against them.

Within a group, boost a project with no check-in note in 14 days and drop one checked in within the last 2 days unless it is urgent. Take the top 15.

## Step 3: Present the List

Present the ranked check-in candidates in a scannable table:

```
## Project Check-In: [Date]

Project health last ran: [date]. Here are the projects most needing your input:

| # | Project | Domain | Diagnosis | Idle | Smallest step |
|---|---------|--------|-----------|------|---------------|
| 1 | Business Insurance | Acme Components | WAITING_ON_OWNER_DECISION | 60d | Renew with the current carrier or quote two others? |
| 2 | Board Reporting | Acme Components | WAITING_ON_PERSON | 9d | Chase the controller for the September pack |
| 3 | Tax Compliance | Acme Components | NO_NEXT_ACTION | 30d | Send the advisor the extension list (task created) |
| 4 | Warehouse Automation Pilot | Acme Components | STALE_OR_DEAD | 120d | Close it? No activity since June |
| 5 | Data Mapping | Northwind Traders | BLOCKED_EXTERNAL | 14d | Waiting on the upstream data owner |

Which ones should we go through? (numbers, "top 5", "all", or a domain like "Acme")
```

**Wait for the owner's selection before proceeding.**

If the user provided an argument (e.g., `/project-checkin Acme` or `/project-checkin top 3`), use that to filter or limit automatically.

## Step 4: Check-In Loop

For each selected project, do this cycle:

### A. Present What You Know

Call `get(entity_type="project", id_or_query="...")` for the full current picture.

Also reference the project's row in the last Run's `diagnoses.json`, and what `REPORT.md` says was written or refused for it.

Present concisely:

```
---
## [Project Name] ([Domain])
**Diagnosis**: [word] | **Last assessed**: [Run date] | **State**: [stalled / dead / gaps, idle N days]

**What I know:**
- [Key fact 1: tasks, deadlines, recent activity]
- [Key fact 2: email signals, what the Run wrote]
- [Key fact 3: the smallest step, and whether it needs you]

**Open tasks** ([count]): [P1: N, P2: N, P3: N]
**Next deadline**: [date, task name]

**The Run left for you:**
- [Item 1: why it needed you]
- [Item 2]

**What's on your mind about this one?**
---
```

### B. Listen and Capture

**When the owner gives multiple items at once** (numbered list, bullet list, a structured status dump such as an ERP open-items list), create ALL tasks and notes in parallel tool calls; do not create them one at a time.

The owner will respond with freeform context. Parse their response for:

1. **Status updates**: "That's done" / "We sent that" / "That's resolved" → `update_task(id="...", status="DONE")`

2. **New information**: "We decided X" / "Dana approved Y" / "The timeline shifted to Z" → `create_note(note_type="episodic", associations=[{"entity_type": "project", "entity_id": "..."}], tag_ids=[...])`, tagged "project-checkin"

3. **New action items**: "I need to call X" / "We should follow up on Y" / "Don't let Z slip" → `create_task(title="...", domain_id_or_name="<project's domain>", project_id="...", priority=..., due_date=...)` with appropriate priority, due date and project link (domain is required: derive it from the project being discussed)

4. **Status changes**: "That's on hold" / "Waiting on external counsel" / "We're blocked by..." → `update_task(id="...", status="WAITING")` or create note with context

5. **Project-level decisions**: "Kill that project" / "That's done, close it" / "Merge with X" → Flag for confirmation, then `update_project(id="...", fields={"status": "COMPLETED"})` when it was done or `"CANCELLED"` when it stopped mattering (the statuses are NOT_STARTED, PLANNING, IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED); close or move its open tasks first

6. **"Skip" / "That's fine" / "Nothing new"** → Create a brief note: "Checked in [date]: no updates, project on track per the owner." This still resets the "last checked in" signal for the next project-health Run.

### C. Confirm Actions

After parsing, show what you're doing:

```
Got it. Updating:
- Completed: "Send Q3 results overview to the board"
- Note: "Q3 results sent 10/02. The controller is on track for the 10/15 close. The pricing change needs a conversation with the CEO."
- Task created: "Discuss the pricing change with the CEO before the board meeting" (P2, due 10/10)
```

Then immediately move to the next project:

```
Next up: **Warehouse Automation Pilot** (Acme Components)
...
```

### D. Repeat

Continue the loop until all selected projects are covered.

## Step 5: Summary

After the last project:

```
## Check-In Complete: [Date]

**Reviewed**: [N] projects
**Updated**:
- Tasks completed: [N]
- Tasks created: [N]
- Status notes captured: [N]
- Projects closed/archived: [N]

All updates are in the Portal. The next weekly project-health Run
starts from this fresh data.
```

---

## Key Rules

- **Come prepared**: Always present what the system knows BEFORE asking. The owner shouldn't have to explain from scratch.
- **One project at a time**: Don't dump 5 projects' details at once. Present, listen, capture, move on.
- **Capture everything**: Even "no updates" gets a note; it resets the freshness signal.
- **Tag consistently**: All notes created during check-in get tagged `project-checkin` so the project-health pass and future check-ins can track when projects were last reviewed.
- **Use the standardized note template** for all check-in notes:
  ```
  ## Status: [ON TRACK / NEEDS ATTENTION / AT RISK / BLOCKED / STALE]

  ### Completed
  - item (with dates)

  ### Active / In Progress
  - item: current state

  ### Open Items / Next Steps
  - item: owner, due date if known

  ### Key Contacts
  - Name: role, communication preference

  ### Timeline
  - date: event
  ```
  The project-health diagnosers read it first. Consistency matters.
- **Be concise**: Use bullet points and stay action-oriented. Don't over-explain.
- **Parse aggressively**: If the owner says "that's done," find the task and complete it. Don't ask "which task do you mean?" unless genuinely ambiguous.
- **Link everything**: Notes to the project. Tasks to the project and domain. Activities to the project.
- **Don't repeat the Run**: If the project-health Run already created a chase or next-action task, mention it ("the Run created a task to chase the controller on Monday; did that happen?") but don't recreate it.
- **Nudges are not drafted here.** A person to chase becomes a chase task; `comms-follow-ups` drafts it in the owner's voice after `outbound-check`.
- **Portal write safety**: before any create or update call in Step 4B, follow the `portal-write-safety` skill (propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first).
