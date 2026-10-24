---
name: client-delivery-workstream
description: "Client delivery's method, loaded by projects-client-delivery and by the projects-worker and projects-reviewer it dispatches, not for a user request; adds to orchestration-workstream and task-stack-workstream. Covers DELIVERY-RULES.md first, the SOW baseline never invented, the pack's sources by id, the Steps of one plan, check or milestone-review session, the sections Plan the engagement, Keep the RAID log, Reconcile the tasks and Check the delivery status, the owner's questions in CONFIRMATIONS.md, and the milestone, change, RAID and task shapes recorded with projects-delivery-record. For a session, start projects-client-delivery."
---

# Working on client delivery

This skill extends `orchestration-workstream` and `task-stack-workstream`: keep their conduct and return their block. Load them if they are not loaded. What follows is only what client delivery adds.

Client delivery keeps one engagement's delivery true: the plan against the SOW, milestones and their acceptance, the RAID log, the engagement's Portal tasks. The facts were gathered before the session (`projects-delivery-pack`); the session judges them; only the main agent records, and nothing reaches the Portal except the task change set `projects-delivery-apply` makes after the session.

## Conduct here

- **The rules first.** `DELIVERY-RULES.md` (its path is `rules_file` in `pack.json`) holds the scope baseline, the thresholds, who may be assigned work and what never to open. It wins over this skill and over any brief.
- **The baseline is the owner's.** The `## Scope baseline` table comes from the signed SOW, in the owner's hand. Never fill a missing baseline from a deck, a transcript or a reading of the work: a milestone committed without a SOW goes in the plan with no Baseline due and with the Source where it was committed. A missing SOW is the owner's question.
- **Sources by id.** `pack.json` lists every source with its id (`S004`), role (`sow`, `folder`, `portal`, `repo`), date and path; `sources/S004.md` holds the text of the SOW, each Portal item and the repo log. Cite a source by its id, or by a Portal ref (`portal://note/<uuid>`) or a file path when it is not in the pack. Every claim carries one.
- **Already done?** A milestone a person already delivered, a risk already in `RAID.csv`, a task already open: say so and cite it; never propose it again.
- **Never open** a file the rules' Never open list matches, even when a path leads to one.
- **Dates** are `yyyy-mm-dd`. A client date is one the client was told (a steering deck, a status memo, a meeting with the client): moving it is the owner's decision.
- **Nobody is contacted.** Not the client, not a teammate. Nothing is sent. A scope question, a client-date move, an assignment to a teammate and an acceptance are the owner's, asked in `CONFIRMATIONS.md`.

## What the session has

- The prepare step's first line: `FRESH: ... pack at P; working folder W` or `STALE: <reason>; ...`. `P` is `RUN/delivery`; `W` is the working folder every command and file write uses (on a dry run, the copy in `P`). STALE means part of the record could not be read: carry on with what was packed and say so first in STATUS.md.
- `P/pack.json`: the rules file's path, the baseline, the SOW's state and its question, the current plan, evidence and RAID rows, the settings (Portal domain, lead time, Assignable), the owner's contact, the engagement's projects and open tasks with their gaps, and every source. `P/sources/S###.md` the texts; `P/check-before.json` the check before the session.
- In `W`: `PLAN.md`, `STATUS.md`, `LOG.md`, `CONFIRMATIONS.md`, `RAID.csv`, `DELIVERY-EVIDENCE.csv` (none of them before the first session).
- The mode: `plan` (Monday: the whole plan, the RAID log, the tasks and the next two weeks), `check` (Thursday: what is late and why, what moved, RAID items due for review, the tasks) or `milestone-review` (one milestone's acceptance evidence). The pack resolves a blank mode.

## Steps

For `projects-client-delivery`. Write a `W/LOG.md` line before each hand-off and record each return at once, so a session that stops part-way is resumed by the next.

1. [judgment] Orient. Read the rules file and every document it names, then `W/STATUS.md`, the end of `W/LOG.md`, `W/CONFIRMATIONS.md` (answers to earlier questions are input now: an approved change, an Assignable yes, a supplied SOW), `P/pack.json` and `P/check-before.json`. If a session already recorded today in this mode, resume from the first test not met; never redo what is recorded.
   → milestone-review mode: step 3
2. [hand-off: projects-worker] In parallel, two workers with the pack's path, the mode and the rules files' paths only: one on section Keep the RAID log, one on section Reconcile the tasks (with the task rules file). As each returns, save the RAID worker's `extra.raid` as `{"raid": [...]}` to `RUN/returns/raid.json` and the task worker's block to `RUN/returns/tasks.json`; a return without its json block goes back once.
3. [judgment] Plan the engagement yourself, by the section of that name: write `W/PLAN.md`, save the milestone states to `RUN/returns/milestones.json` and the plan changes to `RUN/returns/changes.json`.
4. [script] Record each ledger, one command per call: `projects-delivery-record ENGAGEMENT milestone --from RUN/returns/milestones.json --working W`, `projects-delivery-record ENGAGEMENT change --from RUN/returns/changes.json --working W`, `projects-delivery-record ENGAGEMENT raid --from RUN/returns/raid.json --working W`.
   → a row refused: step 3 (max 1)
5. [hand-off: projects-reviewer] The task ops of medium confidence only, with the task rules file and the owner's contact id, never a worker's reasoning: `task-stack-workstream`, section Check task-stack ops.
   → no medium ops: step 6
6. [judgment] Write `RUN/changes.json` in `task-stack-workstream`'s change-set shape: the high ops and the medium ones the reviewer passed, `"orchestrator": "projects-client-delivery"`, `"dry_run"` the session's mode, the task questions in `questions`. A FAIL drops the op; where the worker had a best guess it becomes a question.
7. [script] `projects-delivery-check ENGAGEMENT --pack RUN --working W --format json`. An authority gap means an op assigns work or reaches outside the engagement: move it to `questions`.
   → a test not met that this session can meet: step 3 (max 1)
8. [judgment] Write `W/STATUS.md` (section Questions and the status, below).
9. [hand-off: projects-reviewer] In `plan` and `milestone-review`: section Check the delivery status, with only `W/PLAN.md` and `W/STATUS.md`. Save the verdict to `RUN/returns/redteam.md`.
   → FAIL: step 8 (max 1)
   → check mode: step 10
10. [script] Record the session: `projects-delivery-record ENGAGEMENT session --mode MODE --working W` (`--state dry-run` on a dry run). Append the session to `W/LOG.md`, then run `projects-delivery-check ENGAGEMENT --pack RUN --working W --format json` last and report.
   → reported: done

Done is computed: the check's tests (sow, plan, milestones, changes, raid, tasks, authority, session) are met except those that wait on the owner (a missing SOW, a client-date change not yet answered), each of which is a question in `CONFIRMATIONS.md`. Before the session the Automation runs `projects-delivery-pack`; after it `projects-delivery-apply`, which refuses an op that assigns or reaches outside the engagement and applies the rest through `task-stack-apply`. With no one present everything runs the same; the session never waits and never ends with `needs_owner`.

## Plan the engagement

The main agent does this itself. The goal is a plan the engagement's sponsor would recognise and its delivery lead would sign: every milestone the SOW promised, each with an owner, a date and an acceptance test, its true state on evidence, every slip with its reason, and the next two weeks of work that move it.

- Start from the baseline and the current plan, then the window's sources for what happened: meetings, notes, mail, commits, files shared with the client. A milestone's state rests on a source a person would accept (a delivered file, a client's acceptance in a meeting note, a merged commit), never on a plan saying so.
- A milestone past its planned date and not delivered is late: say why, from a source, and propose a change to a realistic date, or say plainly that no date can be given yet and who can give one.
- No SOW: build the Milestones table from commitments the engagement actually made, each with the Source where it was made and no Baseline due. Do not dress that up as a baseline.
- Scope: anything the client asked for outside the baseline is a question for the owner, never a new milestone.
- Acceptance: `accepted` only on the owner's recorded confirmation; until then `delivered`.
- In `milestone-review`: one milestone, its acceptance test, the evidence for each part of it, and what is missing.

`W/PLAN.md`: a `## Milestones` table with the columns `Id | Milestone | Owner | Baseline due | Planned due | Client date | Acceptance | Source`, then `## Late and why`, `## Next two weeks`, `## Open questions`. A milestone with no SOW baseline has an empty Baseline due. Keep a client date's Planned due unchanged until the owner approves its change. If a person edited `PLAN.md` since the last LOG entry, keep their text and write yours beside it as `PLAN <date>.md`, and say so. Use `unslop-deliverable` for the prose.

The milestone states and changes, saved for `projects-delivery-record`:

```json
{"milestones": [{"id": "M1", "state": "in-progress", "evidence": "portal://note/<uuid>",
                 "source": "S014", "note": "Model drafted; review booked for 10-08"}],
 "changes": [{"id": "C1", "milestone": "M1", "to": "2026-10-23", "client_date": true, "state": "proposed",
              "reason": "The controller is out until 10-20", "source": "S014"}]}
```

- States: planned, in-progress, at-risk, delivered (needs `evidence`), accepted (needs `evidence` and the owner's confirmation as `source`; otherwise delivered).
- A change is a planned date that moves, with the new date, the reason and its source, `state` proposed. A change to a client date is also an owner question; one to an internal date is approved by the main agent only when the rules say so.

## Keep the RAID log

For a `projects-worker`. Brief: the pack's path, the mode, the rules file's path. Read the rules first. Read only; write nothing.

The goal is a RAID log a delivery lead would act on: every real risk, assumption, issue and dependency on the record, each with the source that raised it, an owner who can act on it, a review date and a mitigation where one exists; nothing stale left open; nothing invented. In `plan`, review the whole log; in `check`, the open items due for review and what the window's sources add.

- A risk may happen and would move a milestone, the scope or the client's confidence; an issue has happened; an assumption is something the plan rests on that nobody confirmed; a dependency is something the plan needs from someone else (the client's IT, a data export, a decision).
- Raise only what a source shows: a slipped date, a person who said they cannot, a system that failed, an answer still owed. Quote nothing longer than the line that shows it.
- Every open item whose review date has passed gets a decision: still open with a new review date and what changed, or closed with the evidence that resolved it.
- Assumptions the SOW or the plan rests on that nobody confirmed, and a missing SOW itself, are RAID items as well as questions.
- Personnel and commercial matters are recorded neutrally; anything said in confidence stays out and becomes a question for the owner.

Return the `orchestration-workstream` block with `workstream: "keep-the-raid-log"`, a short summary for a person first (what is new, what closed, the three that matter most), and:

```json
"extra": {"raid": [{"id": "R2", "type": "risk", "title": "Controller away in October",
                    "owner": "owner", "review_by": "2026-10-19", "state": "open", "severity": "medium",
                    "source": "S014", "mitigation": "Book the review before the 9th", "note": ""}]}
```

`type`: risk, assumption, issue or dependency. `id` only for a row already in `RAID.csv` (the record command numbers new ones). `owner` is a role or a name the engagement uses; the engagement's owner is "owner". `state`: open or closed (a closed row's `note` says why).

## Reconcile the tasks

For a `projects-worker`. Brief: the pack's path and the task-stack rules file's path. Read the delivery rules (in `pack.json`) and the task-stack rules first; the latter say what evidence closes a task and how sure you must be. Read only; write nothing.

The goal: every action the engagement agreed to has a task with an owner and a date, every task that is done is proposed complete on evidence, and nothing lands on a person who has not agreed to it.

- Read each meeting note and mail in the window for actions agreed. An action with no open task is a `create` in the engagement project that fits it; one already a task is left alone (the duplicate test is the task-stack rules').
- For each open task, look for proof it is done (sent mail, a meeting note, a commit, a file delivered): a `complete` with that evidence, at the confidence the task-stack rules ask. The repo log is in the pack; `git -C <repo> log` may read more of it.
- Only tasks in `pack.json` `tasks.items`, and creates in one of `pack.json` `projects`.
- A task in `tasks.gaps` (no owner, or the owner's with no due date) gets an edit (a due date the sources support; the owner as owner when it is plainly theirs) or a question.
- An owner other than `owner_contact` or the rules' Assignable ids is never set on a create or an edit: return it as a question ("Assign <task> to <person>?"); the first such question for a person also asks whether they agree to receive agent assignments. Another person's task is theirs: you may note it is late, never change it.
- Milestones due in the next two weeks with no task behind them are worth a create for the owner, or a question when it is someone else's work.

Return the `orchestration-workstream` block with `workstream: "reconcile-the-tasks"`, a short summary first, the ops in `extra.ops` exactly as `task-stack-workstream` gives them (with `evidence`, `reason` and `confidence` high or medium), and the questions in `questions`.

## Check the delivery status

For the `projects-reviewer`, given only `W/PLAN.md` and `W/STATUS.md`. Load `review-red-team` and read as the engagement's sponsor at the client, with the purpose "is this engagement on track, and what needs my decision". In addition to its checks: every milestone in STATUS.md appears in PLAN.md with the same state and date; nothing late is missing a why; no client-date move is stated as decided while the owner has not approved it. Return the checklist's verdict; FAIL names each fix.

## Questions and the status

**`W/CONFIRMATIONS.md`** is the owner's question ledger for this engagement. The main agent writes it; the owner answers in it (or in a later Run's Instructions). One line per question, never asked twice:

```markdown
## Open
- Q4 · 2026-10-08 · Move M2's client date to 2026-11-20? The controller is out until 10-20 (S014). · recommended: yes · blocks: changes · answer:

## Answered
- Q1 · 2026-09-28 · Is there a signed SOW? · answer: yes, S001 (2026-09-30)
```

An answer filled in under Open is taken up at step 1 and the line moves to Answered. Never ask what the folder, the pack or an earlier answer already settles. On a live Run each new question is also a `for_owner` item in the report; on a dry run, only the ledger in the Run folder.

**`W/STATUS.md`**: where the engagement stands in three lines, the milestones with state and date, what is late and why, the next two weeks, the RAID items that matter, the owner's numbered questions (answerable "1) ok 2) no"), and the next session's first action.

## The report

The check's result as it is, the milestones by state, what is late and why, the RAID changes, the change set by op, and the owner's questions as one numbered list.
