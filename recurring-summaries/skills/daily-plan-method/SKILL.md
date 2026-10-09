---
name: daily-plan-method
description: "How the owner's day is planned and closed: the pick-three rubric (goal leverage, time decay, top of mind), fitting work to free calendar slots and focus blocks, conflicts and meetings that need prep, focus-block proposals the owner approves, and the evening accounting of each planned item with evidence, its re-date or carry-over, and tomorrow's three. Loaded by the daily-plan agents after orchestration-workstream and task-stack-workstream. Use it by hand for \"what should I do today\", for today's brief (the plan note's morning block) or for the day's recap (its evening block); unattended, start daily-plan-orchestrator. Not for the weekly review; use weekly-review-orchestrator."
---

# Planning and closing the owner's day

Load `orchestration-workstream`, then `task-stack-workstream`, from `~/.claude/skills/<name>/SKILL.md` if they are not loaded. This skill is only what a day plan adds: the standard, the method, and the plan file.

One Portal note per day holds the plan (`Daily Plan - <date>`, private, tagged `briefing` so the Portal dashboard's Daily Brief card shows it), with a morning block and an evening block. It serves as the morning brief and the daily recap. Its commands are `daily-plan-pull` (the facts, computed before the session), `daily-plan-publish` (the note, after it), `daily-plan-check` (whether it is done) and `task-stack-apply` (the re-dates and carry-overs). The daily-plan commands hold the plan file's contract.

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

- The pull's `calendar.free` lists the gaps in working hours of at least the minimum focus length; meetings and holds are busy, existing focus blocks (titled Deep Work, Focus) are free and are the first place for a top item. Put each top item in a slot that is free for its whole length, the hardest thinking earliest. A slot never overlaps a meeting or a hold (`daily-plan-check` tests it). An item with no slot that fits says why (`no_slot`).
- **Conflicts.** Every pair in `calendar.conflicts` goes in the plan with a suggested fix (which one to decline, shorten or send a delegate to: an optional or large-audience meeting gives way to a decision meeting). The plan never moves a meeting itself.
- **Prep.** Every external meeting in `calendar.needs_prep` goes in `prep` with what to prepare (one line), and every other external meeting with its prep note's reference as `prepped`. Back-to-back runs of three or more meetings are worth a line.
- **Focus-block proposals.** Where a top item's slot is not already a focus block, propose one (`kind: focus-block`, start, end, the task it is for). The owner approves calendar changes in one place: the calendar steward's scan reads these proposals from the daily plan's state folder (`<state_dir>/daily-plan/<date>/morning.json`, or the steward's `daily_plan_state` setting) and carries each onto its numbered approval list (`calendar-steward-method`, same shape with `date` added), and `calendar-apply` makes the ones they answer ok. Never more than three a day.

## Evening: closing the day

Account for every item in the morning's top three (the pull's `morning_plan`), then the also-today list where something happened:

- **done**: on evidence a person would accept, cited by reference: the task completed today, the owner's sent mail that does what the task says, a meeting note that records it, a document. Topic overlap is not evidence. A task done on high-confidence evidence and still open gets a `complete` op; medium confidence goes to the checker first.
- **moved**: not done and still wanted. Give it the next working day or a later date that is honest (`new_date`), and an `edit` op setting `due_date` to it. Do not move the same item a third day without saying so in the reason; that is a question for the owner (drop it, delegate it, or block time).
- **carried**: progressed but not finished, date unchanged (its due date is already right). One line of where it stands.
- **dropped**: overtaken or no longer wanted, with the reason. Cancelling is the nightly reconciliation's call under the rules; propose it as a question, never an op.

Commitments the day made with no task (a promise in sent mail, an action from a meeting note) become `create` ops: verb-first title, the project, a due date, the evidence. Check the open tasks first; a duplicate is worse than none.

Done today: the accomplishment bullets, at most ten, grouped by domain, weighted to the goals.

Tomorrow's three: picked by the morning rubric from what moved, what is due tomorrow and the pull's `tomorrow` calendar. The morning pass re-plans; naming them tonight is what lets the evening stop at the evening.

## Coverage

Say when a source was not readable (a `STALE` pull, an `unreadable` line, a calendar that did not sync). An unread inbox or calendar is unknown, never "nothing pending".

## The plan file

The orchestrator writes `RUN/plan.json` (the daily-plan commands hold its contract); a worker returns its part in `extra.plan` of its return block, in the same shape:

- morning: `summary`, `top_three` (`rank`, `title`, `ref`, `reason`, `slot` `{start, end}` or `no_slot`, `score` `{goal, decay, mind}`), `also_today` (`title`, `ref`, `why`), `conflicts` (`a`, `b`, `a_title`, `b_title`, `when`, `suggest`), `prep` (`ref`, `title`, `when`, `state`, `note`, `suggest`), `proposals` (`id`, `kind`, `title`, `start`, `end`, `for`, `why`), `questions`;
- evening: `summary`, `close` with `items` (`ref`, `title`, `outcome`, `evidence`, `new_date`, `op`, `reason`), `done` (bullets), `tomorrow` (`title`, `ref`, `reason`), and `questions`.

Every `ref` is a `portal://` reference the pull or the Portal returned, never made up. Times are local `HH:MM` on the plan's date. Task writes go in `extra.ops` as `task-stack-apply` ops (`task-stack-workstream` has the shape), each op's `id` named on its item's `op`.
