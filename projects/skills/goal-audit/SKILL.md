---
name: goal-audit
description: "Reference loaded by a department's main agent or worker, not for a user request: auditing the distance between the owner's stated goals and the actual work. The seven findings (goals with no project, projects with no goal, unfiled tasks, priority goals that got nothing, where the time went, work serving no goal, candidates to stop), the closed list of seven proposed actions, the private goals document rule, and section Audit standalone (walk the Portal, optional scoreboard and calendar-time inputs, the report shape). Not for the monthly approval list itself; strategy's goal alignment turns these findings into items."
---

# Goal audit

The goals are the claim; projects, tasks, time and calendar are the evidence. Where they disagree, that is a finding. An audit writes nothing: every tool it uses is a read, and the caller decides what to act on.

Two callers use it. Strategy's monthly goal alignment has gathered its facts in code and turns each finding into an approval item (its skill, `goal-alignment-workstream`, says how). An interactive portfolio review (projects' `project-landscape`) has nothing gathered and runs section Audit standalone.

## The private goals document

The owner may keep a private strategic goals document. Quote nothing from it beyond goal titles (and, in the goal alignment, domain names and goal numbers). It is private and an audit lands somewhere shared. A finding that cannot be written without quoting it is written as "the private goals document names a goal the Portal does not carry", and nothing more. If its path does not resolve to a readable file, say so and audit the Portal goals alone: a missing document is a stated limit, not a reason to stop.

## The findings

Each finding is one line of what, one line of why it matters, the evidence `_ref`s (or the gathered input that shows it), and one proposed action from the closed list below. No finding without evidence; a pattern believed but not evidenced goes under "Could not determine".

1. **Goals with no active project.** A goal, at any horizon, that nothing is driving. Say the horizon and the priority: a VISION goal with no project this quarter is normal, a MONTHLY P1 goal with none is not.
2. **Projects with no goal.** Work under way that serves no stated goal: the project, its domain, its open task count.
3. **Unfiled tasks.** Counts for no project, no owner and no domain, each with the worst five examples by age or due date. The count is the finding; the examples make it real.
4. **Priority goals that got nothing.** P1 and P2 goals with no time attributable to them and no completed task inside the window. The finding that matters most and the one people argue with, so be precise about the window and what was counted.
5. **Where the time went.** Hours by domain (and topic) set beside the priority of each domain's goals, and where the two disagree. Say what the hours are: the time study's attributed hours, or meeting time only from the calendar, whose scope match is a heuristic on attendee domain or title. With neither, there is no hours table: a count of distinct meetings attributable to a domain, what could not be attributed, what was dropped (clones, availability blocks, cancellations, all-day markers), and one line on how the count was made.
6. **Work that serves no stated goal.** Projects, recurring meetings and real hours that map to nothing in the hierarchy or the private document. Tell work that is unaligned from work that is aligned but unrecorded; the remedy differs.
7. **Candidates to stop.** Projects and standing commitments where the evidence says the cost is real and the goal is not. Each names what would be freed and what is lost. Propose, never decide.

## The closed list of actions

Every finding proposes exactly one, and nothing outside this list. Where none fits, report the finding with no action and one sentence why.

| Action | When it fits |
|---|---|
| link | The work and the goal both exist and only the connection is missing. |
| create project | A goal is real and nothing is driving it. |
| create next task | A project is real and stalled for want of a defined next step. |
| reprioritise | The stated priority and the observed behaviour disagree and the behaviour looks right. |
| schedule time | A priority goal needs hours in the calendar rather than another task. |
| delegate | The work is real, not the owner's to do, and there is a candidate owner. |
| stop | The cost is real, the goal is not, and the owner should decide to end it. |

## Audit standalone

For a worker briefed by an interactive review, with no gathered inputs. Brief: the window (default the last 14 days), the focus (a domain or all), the goals document's path or "none supplied", and optionally `scoreboard` and `calendar_time` as JSON the caller ran. Write nothing; you cannot ask, so a question that blocks the audit is your return's `BLOCKED:` line.

1. **`whoami` first.** It gives the owner's timezone, which every window is resolved in; every Portal timestamp is UTC.
2. **The project side.** With `scoreboard` (one object per active project: `project_id`, `name`, `domain`, `goal`, task counts, `flags` such as `NO_GOAL`, `NO_OWNER`, `NO_TASKS`, `NO_NEXT_TASK`, `STALE_30D`): take projects with no goal, stalled projects and task load from it and do not walk the hierarchy for them. It cannot see completed work (`completed_last_7d` is always null): never state from it that nothing was completed. Without it, walk the hierarchy and say so in the Sources line.
3. **The goal side.** `list_entities(entity_type="domain", limit=25)`, then `hierarchy(domain_id_or_query=..., depth=1)` per domain. Depth 1 returns `projects: []` for every goal, so an empty list is not evidence of "no project": `get(entity_type="goal", ...)` per goal for its projects (with a scoreboard, only the P1 and P2 goals). Try depth 3 only on a domain known to be small; drop to depth 1 on a size error.
4. **The unfiled work.** `list_entities(entity_type="task", filters={"no_project": true}, limit=25)`, and the same with `no_domain` and `no_owner`. Follow `next_offset` while `has_more`; read `total` before stating a count. Start every list at limit 25; on a size error halve and retry once, then report the gap.
5. **The time.** With `calendar_time` (one run per scope: totals as `hours_sum` and `hours_union`, rows read, what was dropped), finding 5 is an hours table from it; give both sums where they differ, since the gap is double booking. Without it, list `calendar_event` for the window (`filters={"since": ..., "until": ...}`, paged), drop clones, availability blocks and placeholders by title and kind, and count distinct meetings attributable to a domain by title or an attendee's company. Count the owner's own calendars only.
6. **Recent movement.** `priority_review()` for the cross-domain pressure picture; `activity_stream(since=...)` is a sample, not a census, so read a record's own `updated_at` when the question is whether one thing moved.
7. **Treat thin fields as leads.** Project assignees, task assignees, due dates and related contacts are often empty or stale: confirm against the record's title and description before naming a person or a date.

Return this report, findings ordered inside each section by consequence, not count:

```
## Goal alignment audit: <window, in the owner's timezone>

Sources: <domains read>, <scoreboard as of <date> | projects walked from the hierarchy>,
<private goals document: read | not found>, <calendar-time for <period> | calendar read by hand>,
<calendar: <n> rows read, <n> dropped>

### 1. Goals with no active project (<n>)
- <goal> (<horizon>, <priority>, <domain>) · <why it matters> · proposed: <action>
  evidence: <_ref>, <_ref>

### 2. Projects with no goal (<n>)
...

### 5. Where the time went
| Domain | Hours (summed / wall clock) | Meetings | Goal priority in this domain |
<then what matched no domain, what was dropped, and how the figure was made>

### 7. Candidates to stop (<n>)
...

### Could not determine
- <what a reader will expect and the Portal could not tell>
```

Keep it readable in one sitting: counts and the worst examples, not every row.
