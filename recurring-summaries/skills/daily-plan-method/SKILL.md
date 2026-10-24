---
name: daily-plan-method
description: "The daily plan's job skill, run by daily-planner and the worker and reviewer it dispatches. Morning: pick the top three by goal leverage, time decay and top of mind, fit them to free slots, name conflicts and prep, propose focus blocks. Evening: account for each planned item on evidence, re-date or carry what moved, capture the day's commitments as task ops, name tomorrow's three. Holds the Steps, sections Check the plan, Gather one domain and Done today, and the plan file's shape. Use by hand for \"what should I do today\"; unattended, start daily-planner. Not for the weekly review (gtd-weekly-review) or the two-week calendar (calendar-steward)."
---

# Planning and closing the owner's day

`orchestration-workstream` is the conduct and the return block, and `task-stack-workstream` is the task stack's rules, change set and the reviewer's checklist Check task-stack ops; load both first. This skill is what a day plan adds: the standard, the method, the Steps and the plan file.

One Portal note per day holds the plan (`Daily Plan - <date>`, private, tagged `briefing` so the Portal dashboard's Daily Brief card shows it), with a morning block and an evening block. It serves as the morning brief and the daily recap. Nobody in the session writes the Portal: `recurring-summaries-daily-plan-pull` computes the day's facts before the session; after it, `recurring-summaries-daily-plan-publish` writes the note (by marker, once per pass), `task-stack-apply` applies the evening's change set under the owner's task rules with an undo log, and `recurring-summaries-daily-plan-check` says whether the pass is done. The daily-plan commands hold the plan file's contract.

## What the Run has

- `RUN/pull.json` from the pull: the cleaned calendar (`events`, `free`, `conflicts`, `needs_prep`, focus blocks), the candidate tasks with their lenses, projects, domains and goals, the active goals, whether the day's note exists, and the owner's timezone; in the evening also `done_today`, `sent`, `notes`, `morning_plan` (its `source` says where it came from; `null` means there was no morning plan), `packets` (the day by domain, for Gather one domain) and `tomorrow`'s calendar. The prepare line says `STALE` when the pull failed.
- The owner's `TASK-STACK-RULES.md` and `DAILY-PLAN.md` (paths in the Run's inputs). They override this skill.
- Inputs: date (default today in the owner's timezone), pass (default by the clock, morning before noon; the prepare line names the day and pass it pulled, use those), instructions (the owner's top-of-mind item outranks the rubric, never the rules), dry run.

## Steps

1. [judgment] Orient. `whoami`; read TASK-STACK-RULES.md and DAILY-PLAN.md, then RUN/pull.json: the pass, the date, free minutes, conflicts, external meetings without prep, the candidate count.
   → the prepare line says STALE, or pull.json is missing: step 2
   → pass morning: step 3
   → pass evening: step 7
2. [judgment] Read the Portal yourself for what the pull lacks (`list_entities` tasks and events, `priority_review`, today's calendar) and note the gap for the report.
   → pass morning: step 3
   → pass evening: step 7
3. [judgment] Pick three, by section Morning: picking three: score each candidate, apply the five overrides, and add at most five "also today" items.
4. [judgment] Fit the day, by section Morning: fitting the day: a free slot or focus block for each top item, every conflict with a fix, every `needs_prep` meeting with a prep line, at most three focus-block proposals.
5. [judgment] Check the plan, by section Check the plan.
   → a gap: step 3 (max 1)
   → clean: step 6
6. [judgment] Write RUN/plan.json (the morning shape with `"tool": "daily-plan"`, `version` 1, `date`, `pass` and `dry_run`) and RUN/changes.json (a `task-stack-changes` set, `"orchestrator": "daily-planner"`, with no ops: the morning moves no task).
   → written: step 12
7. [judgment] Close each planned item, by section Evening: closing the day: done, moved, carried or dropped, on evidence, each with its op. A `null` `morning_plan` means you account for the day's top work instead. Name tomorrow's three.
8. [judgment] Capture the day's commitments: search the open tasks first, then a `create` op for each promise or assigned action in the day's sent mail and notes with no task.
9. [hand-off: recurring-summaries-worker] Gather the done-list candidates: one worker per packet in the pull's `packets` (at most six, active ones first), in parallel, with `model: haiku`, each told to follow this skill's section Gather one domain, with its packet and the date. With one or two packets, gather them yourself by the same section. Save each return as RUN/returns/gather-<n>.json.
   → no packets: step 10
10. [judgment] Done today, by section Done today: pool the candidates, pick at most ten, group by domain, write the one-line header; the bullets become `close.done`.
11. [hand-off: recurring-summaries-reviewer] Check every `complete` op of `medium` confidence, told to use `task-stack-workstream`'s section Check task-stack ops, with the ops, their evidence refs, the rules file's path and the owner's contact id only, never your reasoning. A FAIL drops the op and its item becomes `carried`, with the reviewer's line as the reason.
   → no medium op: step 12
12. [script] Write RUN/plan.json and RUN/changes.json for the pass (evening: the close with its done list; at most 20 ops, high confidence and reviewer-passed, signed by daily-planner, each op's id on its item, the questions with them), then run `recurring-summaries-daily-plan-check DATE --pass P --run RUN --offline`.
   → a test not met, morning: step 5 (max 1)
   → a test not met, evening: step 7 (max 1)
   → all met: step 13
13. [judgment] Report: the top three or the close in a few lines, the conflicts and prep, the calendar proposals and questions as one numbered list the owner answers by number, and what could not be read. Never claim the note was written or a task moved: the finish step does that and the check reports it.
   → reported: done

The `--offline` check reads only the Run's files; the finish step's check also reads the published note and `apply.json`.

## The standard

Three items a chief of staff would defend, each with the reason it is today's and the slot it fits; every meeting conflict and every external meeting without prep named, with a suggested fix; and, at the end of the day, every planned item accounted for on evidence, with what moves re-dated so tomorrow's list is true. The owner reads the plan in a minute and starts work.

## Morning: picking three

Rank by objectives, never by volume. Read the active goals in the pull first, then the candidate tasks. Score each candidate on three axes, 1 to 3 each:

| Axis | 1 | 2 | 3 |
|---|---|---|---|
| Goal leverage | serves no active goal | advances a goal indirectly | directly advances a goal the owner is pushing now |
| Time decay | could wait a week at no cost | costs something if it slips past this week | the window closes today or tomorrow: a due date, another person blocked, an irreversible step |
| Top of mind | unrelated to what the owner said | related | the thing the owner named in the instructions |

With instructions, a total of 7 or more is a candidate. Without them nobody named anything, so top of mind is left out and 5 or more of the other two (6) is a candidate. Take the top three, ties broken by time decay; with no candidate, take the best one and say it is weak. Then the rules that override the score:

1. **What the owner names comes first.** A top-of-mind item in the instructions is item 1, phrased as a concrete action with why today.
2. **People over tickets.** A reply or decision that unblocks someone beats an internal task of the same score. A WAITING task whose follow-up date has come (`waiting_due`) is a nudge to send, and a nudge takes minutes: it goes in also-today unless the other party is now blocking something in the top three.
3. **Overdue alone is not a reason.** Many overdue tasks are stale captures (a call that happened, a weekend chore). An overdue item earns a place on goal leverage and real consequence, not on its date. Say so in the reason.
4. **A standing meeting is never a top item.** Meetings go in the schedule; their prep can be a top item when the meeting matters and nothing is prepared.
5. **Three at most, and no more than the day can hold.** Plan only as many items as the free slots can each give a real block of time (two sixty-minute gaps hold two items, not three); say why when it is fewer than three.

Also today: at most five more, each with one line of why (follow-ups due, quick replies, small deadlines). Anything else is not mentioned.

## Morning: fitting the day

- The pull's `calendar.free` lists the gaps in working hours of at least the minimum focus length; meetings and holds are busy, existing focus blocks (titled Deep Work, Focus) are free and are the first place for a top item. Put each top item in a slot that is free for its whole length, the hardest thinking earliest. A slot never overlaps a meeting or a hold (`recurring-summaries-daily-plan-check` tests it). An item with no slot that fits says why (`no_slot`).
- **Conflicts.** Every pair in `calendar.conflicts` goes in the plan with a suggested fix (which one to decline, shorten or send a delegate to: an optional or large-audience meeting gives way to a decision meeting). The plan never moves a meeting itself.
- **Prep.** Every external meeting in `calendar.needs_prep` goes in `prep` with what to prepare (one line), and every other external meeting with its prep note's reference as `prepped`. Back-to-back runs of three or more meetings are worth a line.
- **Focus-block proposals.** Where a top item's slot is not already a focus block, propose one (`kind: focus-block`, start, end, the task it is for). The owner approves calendar changes in one place: the calendar steward's scan reads these proposals from the daily plan's state folder (`<state_dir>/daily-plan/<date>/morning.json`, or the steward's `daily_plan_state` setting) and carries each onto its numbered approval list (`calendar-steward-method`, same shape with `date` added), and productivity's `productivity-calendar-apply` makes the ones they answer ok. That folder is a file contract between the two departments: the publish step writes it, the steward reads it. Never more than three a day.

## Evening: closing the day

Account for every item in the morning's top three (the pull's `morning_plan`), then the also-today list where something happened:

- **done**: on evidence a person would accept, cited by reference: the task completed today, the owner's sent mail that does what the task says, a meeting note that records it, a document. Topic overlap is not evidence. A task done on high-confidence evidence and still open gets a `complete` op; medium confidence goes to `recurring-summaries-reviewer` first (Steps, step 11).
- **moved**: not done and still wanted. Give it the next working day or a later date that is honest (`new_date`), and an `edit` op setting `due_date` to it. Do not move the same item a third day without saying so in the reason; that is a question for the owner (drop it, delegate it, or block time).
- **carried**: progressed but not finished, date unchanged (its due date is already right). One line of where it stands.
- **dropped**: overtaken or no longer wanted, with the reason. Cancelling is the nightly reconciliation's call under the rules; propose it as a question, never an op.

Commitments the day made with no task (a promise in sent mail, an action from a meeting note) become `create` ops: verb-first title, the project, a due date, the evidence. Check the open tasks first; a duplicate is worse than none.

Done today: the accomplishment bullets, at most ten, grouped by domain, weighted to the goals (sections Gather one domain and Done today).

Tomorrow's three: picked by the morning rubric from what moved, what is due tomorrow and the pull's `tomorrow` calendar. The morning pass re-plans; naming them tonight is what lets the evening stop at the evening.

## Coverage

Say when a source was not readable (a `STALE` pull, an `unreadable` line, a calendar that did not sync). An unread inbox or calendar is unknown, never "nothing pending".

## The plan file

The main agent writes `RUN/plan.json` in this shape (`recurring-summaries-daily-plan-check --help` and the publish command hold the contract):

- morning: `summary`, `top_three` (`rank`, `title`, `ref`, `reason`, `slot` `{start, end}` or `no_slot`, `score` `{goal, decay, mind}`), `also_today` (`title`, `ref`, `why`), `conflicts` (`a`, `b`, `a_title`, `b_title`, `when`, `suggest`), `prep` (`ref`, `title`, `when`, `state`, `note`, `suggest`), `proposals` (`id`, `kind`, `title`, `start`, `end`, `for`, `why`), `questions`;
- evening: `summary`, `close` with `items` (`ref`, `title`, `outcome`, `evidence`, `new_date`, `op`, `reason`), `done` (bullets), `tomorrow` (`title`, `ref`, `reason`), and `questions`.

Every `ref` is a `portal://` reference the pull or the Portal returned, never made up. Times are local `HH:MM` on the plan's date. Task writes go in `extra.ops` as `task-stack-apply` ops (`task-stack-workstream` has the shape), each op's `id` named on its item's `op`.

## Check the plan

The main agent's own test of the morning plan before it is written, against the pull and nothing else:

- every `ref` is in the pull or reads back from the Portal (`get`);
- every slot lies inside a `free` slot or an existing focus block, and no slot overlaps a meeting or hold;
- every pair in `calendar.conflicts` and every meeting in `calendar.needs_prep` appears in `conflicts` or `prep`;
- at most three top items, no more than the free slots can each give a real block, and at most three proposals;
- each top item's reason says the goal it moves, what slips if it waits, or who is blocked.

A gap goes back to step 3 once; what is still open after that is named in the report.

## Gather one domain

For a `recurring-summaries-worker` given one domain packet from the pull (`domain`, `density` active or thin, `items` by kind: `meeting`, `completed_task`, `started_task`, `created_note`, `sent_email`, `created_draft`; `strategic_context` with the domain's goals; optionally `user_prime`, the owner's words) and the date. Your goal is five to eight candidate bullets that capture what the owner actually did in this domain today, weighted to the domain's goals, not to activity volume. Read only; write nothing.

1. Read the goals in `strategic_context` first: they define what matters here, and every bullet should read as advancing (or failing to advance) one of them.
2. Scan the items and group related ones: three sent emails on one thread are one bullet.
3. Weight by goal alignment: a completed task on a goal's critical path beats five routine sent emails.
4. Continuity over novelty: work that continues a multi-day thread is framed as progress on it; novelty only when today's work is new.
5. The owner's `user_prime`, when present, wins ties.
6. At most one follow-up read (`get` an email or project, `email_bodies` for a body), and only when an item cannot be read otherwise.
7. Write the bullets: at most 20 words each, led by an accomplishment verb (closed, drafted, decided, unblocked, aligned, agreed, kicked off), specific (the person, project, number or decision), no filler ("continued to", "productive"), in the owner's plain business register. Fewer bullets when the signal is thin; never invent detail. An item that belongs to another domain is flagged in `notes`, never silently moved.

Return the `orchestration-workstream` block with `workstream: "gather-one-domain"`, and in `extra.bullets` the candidates, each:

```json
{"text": "Closed the pricing debate with the client; aligned both leads on the tiered model.",
 "importance": 9, "type": "decision", "project_id": "p1", "goal_id": "g1",
 "source_item_ids": ["e1", "t1"], "thread": "ongoing", "alignment": "advances_goal"}
```

`importance` is 1 to 10 (9 to 10 a major loop closed or a strategic decision; 6 to 8 real progress on a goal or a high-priority task done; 3 to 5 routine but visible; 1 to 2 noise), `type` one of `meeting`, `completed_task`, `sent_email`, `created_note`, `decision`, `progress`, `thread` `ongoing` or `new`, `alignment` `advances_goal` or `neutral`. One line in `notes`: what felt thin or surprising.

## Done today

Run by the main agent over the gatherers' candidates (and its own, for one or two packets). The goal is the day's done list the owner reads in the plan note's evening block: what was new, surprising or important about the day, not a log.

1. Pool every candidate across domains. Adjust each `importance` with judgment: up for the owner's instructions, for `advances_goal`, for `thread: new` over `ongoing`; down for a duplicate reported by two domains (keep one).
2. Pick at most ten. Every active domain keeps its best bullet; thin domains may drop out.
3. Re-read each bullet against the rules in Gather one domain, step 7. A bad bullet is dropped, never rewritten into something its sources do not say.
4. Write one header line of at most 25 words naming the day's through-line ("Most of the day went to the vendor selection; client work quieter than usual"), never "a productive day".

The header opens the evening `summary`; `close.done` holds the bullets, each as `<domain>: <bullet>`, in domain order.
