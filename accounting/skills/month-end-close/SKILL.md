---
name: month-end-close
description: "The job skill of accounting-month-end-close, not for a user request: one session of a company's month-end close, run the way a controller runs a close team. Holds the Steps, the Month-End folder, done computed by accounting-month-end-check, recording a return with accounting-month-end-record, questions through comms-confirm, the worker sections Set up a month and Curate a month, learned facts, authority and the unattended rules. The workstream sections and reviewer checklists are in month-end-workstream. Not for one entry (month-end-journal-entry), the owner's firm (firm-books-workstream) or intercompany (intercompany-workstream)."
---

# Running a month-end close

One session of the close for one company and period. The main agent reads the Month-End folder, works out what is done and open, has `accounting-worker` do the workstreams, has `accounting-reviewer` check every item, has the results memo written last, and keeps `STATUS.md` and `LOG.md` current so any session can resume. `orchestration-workstream` and `month-end-workstream` are the conduct and the return block every slice keeps; `MONTH-END-RULES.md` in the folder overrides all of it.

The standard is accurate books under GAAP, accepted only with evidence. The close is done when four tests hold, each with its evidence in the period folder:

1. **Entries.** Every recurring and necessary journal entry is booked and confirmed in the GL (seen posted in a fresh ledger pull), with its backup saved in `journal-entries/`.
2. **Reconciliations.** Every balance-sheet account is reconciled, the reconciliation final and saved in `reconciliations/`, the GL balance tied to support within the tolerance in `MONTH-END-RULES.md`.
3. **Flux.** Every significant variance against budget or forecast (thresholds in `MONTH-END-RULES.md`) is explained in `reporting/MONTH-END-FINDINGS-{yyyy-mm}.md`.
4. **Questions.** Every question to a person is answered, or its effect on 1 to 3 is stated.

## Steps

1. [judgment] Orient. Read the standing documents (The folder), then the period's `STATUS.md`, the last `LOG.md` entries, `CONFIRMATIONS.md` and the procedures copy, and look at the prior month's folder for how the same work was done. Note each answered question; it is input to this session.
   → the period is not set up: step 2
   → set up: step 3
2. [hand-off: accounting-worker] Set up the month: one worker (model sonnet) told to follow this skill's section Set up a month, with the folder and the period. Record its return as Recording a return says.
3. [script] Facts from the ERP. When the launch's prepare line says `FRESH` or `STALE`, the pull is already refreshed (STALE: work from the older pull and say so). Otherwise read the date in `work/source/pulled.md` and, when entries were booked since, run `month-end-pull FOLDER --period P --live`. Read the trial balance, and the budget or forecast where `SYSTEMS.md` says it is.
   → the trial balance does not balance: stop
4. [script] Run `accounting-month-end-check FOLDER --period P --format json` to see what is open.
   → every test met and the sign-off passed: step 11
5. [judgment] Plan. When `reconciliations/intercompany/HANDOFF-{yyyy-mm}.md` exists and is newer than its rows in the evidence file, record each of its rows as Recording a return says. List the open checklist rows and accounts by workstream (Cash, AR billing and revenue, Accruals and AP), what is blocked on a person or an input, and what is due today or overdue. Work only what is unblocked; never redo what a person did.
   → nothing unblocked: step 12
6. [hand-off: accounting-worker] Dispatch each workstream with unblocked work, in parallel, one worker each (model opus), told to follow `month-end-workstream`'s section Cash, AR billing and revenue, or Accruals and AP, with the folder, the period, the rows and accounts assigned, the answers to its earlier questions and any reviewer fixes. Write a `LOG.md` line and set the `STATUS.md` row to in progress before each dispatch; record each return at once (Recording a return). Flux and one-off investigations go to a worker briefed with `month-end-flux` (model fable for a hard investigation or a close judgment, sonnet for reading a lot, opus otherwise).
7. [hand-off: accounting-reviewer] Review every new or changed entry, reconciliation and finding, told to use `month-end-workstream`'s section Review an item, with the files and their sources only, never the worker's reasoning. Write its note as `reporting/REVIEW-{yyyy-mm}-{subject}.md` and record each verdict with `--review PASS|FAIL --review-file`.
   → FAIL: step 6 (max 2)
8. [judgment] Findings and questions. In the last week of the month have leadership's expectations collected with `month-end-expectations-brief`. Put what is unusual, surprising or material in the findings file as succinct bullets (account, amount, what explains it). Ask a person only what the folder, the prior months and the ledger cannot answer (Questions); a FAIL that came back twice is a question too.
9. [script] Run `accounting-month-end-check FOLDER --period P --format json`.
   → a test not met: step 12
10. [hand-off: accounting-reviewer] Sign off: the reviewer on model fable, told to use `month-end-workstream`'s section Sign off the close, with the whole month folder. Write its note and record it as in step 7.
   → FAIL: step 12
11. [hand-off: accounting-worker] The results memo, once the four tests are met and the sign-off passed (or the owner asks for a preliminary version): a worker (model opus) told to follow `month-end-results-report`'s section Write the results memo, then `accounting-reviewer` told to use `review-numbers` with the memo, its figures ledger and the ledger pull only. Write the reviewer's note beside the memo; a FAIL goes back to a worker once, then it is a question. Walk that skill's DONE checklist and put the review request on the owner's list. Never send the memo.
   → the memo already exists and passed: step 12
12. [script] Close the session. Update the period's and the root `STATUS.md` (where it stands, what waits on whom, the next action with its date), write the session's `LOG.md` entry, and run `accounting-month-end-check FOLDER --period P` last. Report its result; the close is done only when it says every test is met and the sign-off passed.
   → reported: done

## The folder

The root holds the standing documents. Read all of them at the start of every session.

| File | Holds |
|---|---|
| `MONTH-END-RULES.md` | Authority (what an agent may and may not do), thresholds, tolerances, naming, the definition of done. It overrides everything else. |
| `MONTH-END-PROCEDURES.md` | The standing checklist: every task, its owner, due day, done-check and workstream; and the balance-sheet accounts with their workstream. |
| `BACKGROUND.md` | The entity, the people and their roles, the calendar. |
| `SYSTEMS.md` | The ERP and other systems, how data comes out, where inputs land. |
| `METADATA_FIELDS.md` | Accounts, dimensions, coding rules, the accrual maps. |
| `STATUS.md` | The handoff: current period, where it stands, what is waiting, the next action. |

Each month lives in `{yyyy}/{yyyy-mm}/`:

| Path | Holds |
|---|---|
| `STATUS.md` | One row per workstream (not started, in progress, waiting, done), and the Waiting on table. |
| `LOG.md` | One dated entry per dispatch and per session, headed `## yyyy-mm-dd HH:MM by WHO`. |
| `MONTH-END-PROCEDURES-{yyyy-mm}.md` | This month's copy of the checklist, with each row's status and evidence. |
| `CONFIRMATIONS.md` | Every question asked of a person, and the answer. |
| `journal-entries/` | Import files a person uploads (STATE Posted; agents never upload or post) and their backup. |
| `reconciliations/` | One reconciliation per balance-sheet account; `intercompany/` holds the intercompany job's work and its HANDOFF file. |
| `reporting/` | `MONTH-END-FINDINGS-{yyyy-mm}.md`, the review notes, the results memo's figures ledger and QA log. |
| `MONTH-END-EVIDENCE-{yyyy-mm}.csv` | One row per entry, account and flux item: state, evidence, amount and review. Written only with `accounting-month-end-record`; read by `accounting-month-end-check`. |
| `work/` | Working files; `work/source/` is the read-only ledger pull. |

The main agent is the only writer of `STATUS.md`, `LOG.md`, the procedures copy and the evidence file. Workers return what they did; the main agent records it, so parallel work never overwrites itself.

## Done is computed

`accounting-month-end-check FOLDER --period P --format json` computes the four tests from the folder and the ledger pull, so done is never an opinion: every import file compared with the pull (posted and matching, posted but different, or not posted), the reconciliations against every balance-sheet account in the trial balance, the flux, and the open questions. `--precheck` prints `WORK: ...` or `NOTHING: ...` for a scheduler. When an entry was posted at a different amount from its draft, a person changed it: find out why from the ledger and record the lesson (Record a learned fact) so next month's draft is right.

This check's command line and its json (`met`, `of`, `tests`) are also the board package's close gate in the reporting department; keep both unchanged.

## Recording a return

A worker returns the `month-end-workstream` block. Record what came back at once, never batched, because the next session resumes from these records:

- each of `items` with `accounting-month-end-record FOLDER --period P --test T --item I --state S --evidence E --amount N --pull-date D --note TEXT --by accounting-worker`;
- each of `rows` in the procedures copy, and the workstream's row in `STATUS.md`;
- each of `questions` through comms-confirm (Questions);
- each of `proposals` as a learned fact or a rules proposal (Record a learned fact);
- each of `findings` into the findings file.

A reply without the json block goes back once for it. The reviewer writes nothing: its note is saved by the main agent as `reporting/REVIEW-{yyyy-mm}-{subject}.md`, and the verdict recorded with `accounting-month-end-record ... --review PASS|FAIL --review-file reporting/REVIEW-{yyyy-mm}-{subject}.md --by accounting-reviewer`. Only reviewed work counts toward done.

## Questions

Ask a person only after the folder, the prior months and the ledger cannot answer it. One question per item, through the `comms-confirm` skill's `confirm` command (`confirm new`, then `confirm task`, then one `confirm relay` at the end of the session), recorded in `CONFIRMATIONS.md` and the Waiting on table. Then move on to other work. Never build on an assumption about a missing input.

## Set up a month

For an `accounting-worker` on model sonnet, given the folder and the period. Housekeeping, not accounting: decide nothing about the numbers, never touch the ERP, never delete a file. Read `MONTH-END-RULES.md` and `MONTH-END-PROCEDURES.md` first.

Create what is missing in `{yyyy}/{yyyy-mm}/`, never overwriting a file that exists:

- the subfolders `journal-entries/`, `reconciliations/`, `reporting/`, `work/source/`;
- `MONTH-END-PROCEDURES-{yyyy-mm}.md`: the root procedures with due days turned into dates for this month, written `ME+3 = yyyy-mm-dd` (business days Monday to Friday, skipping the company's holidays in `BACKGROUND.md`, or US federal holidays when it lists none; "weekly" and other non-dates stay as written), plus the columns Status (open, waiting or done) and Evidence, with the Status of anything the month's files already show;
- `STATUS.md`: a header line `Last updated: yyyy-mm-dd HH:MM by accounting-worker`; `## Phases`, a table `| Phase | State | Files | Note |` with one row per workstream in the procedures' `## Phases` list, each not started; `## Waiting on`, a table `| Id | Phase | Question | Asked of | How | Asked at | State | Answer | Answered at |`;
- `LOG.md`, headed `# {yyyy-mm} log`, with a first entry saying the month was set up; every entry is headed `## yyyy-mm-dd HH:MM by WHO` with the lines `- Done:`, `- Files:`, `- Decisions:` and `- Open:`;
- `reporting/MONTH-END-FINDINGS-{yyyy-mm}.md`, with a heading and nothing else.

Then carry forward from the prior month every open Waiting on row (as a new row naming the old id), every checklist row left open, and every reconciling item the prior reconciliations marked as clearing next month. Set the root `STATUS.md` current period, and the month's Setup phase to done, linking the procedures copy.

Return the `orchestration-workstream` block with `workstream: "set-up"`: `files` what you created, `notes` what you carried forward, `questions` what needs a person.

## Curate a month

For an `accounting-worker` on model sonnet, given the folder and the period, when the month has grown untidy:

- check that `STATUS.md`, the procedures copy and the files in the folder agree: every linked file exists, and every file in `journal-entries/` and `reconciliations/` is linked from somewhere;
- flag any Waiting on row older than the stale days in `MONTH-END-RULES.md`;
- when `LOG.md` passes about 300 lines, add a dated summary of the older entries at the top and leave the entries in place.

Never move or rename a person's file; report it. Return the `orchestration-workstream` block with `workstream: "curate"`: `files` what you changed, `findings` what a person should look at.

## Record a learned fact

The main agent does this itself, from an answer in `CONFIRMATIONS.md`, a file or a ledger entry. Put the fact in the one standing document it belongs in, as a dated line naming its source:

| Kind of fact | Document |
|---|---|
| people and calendar | `BACKGROUND.md` |
| systems and inputs | `SYSTEMS.md` |
| accounts and coding | `METADATA_FIELDS.md` |
| tasks | `MONTH-END-PROCEDURES.md` |

A change to `MONTH-END-RULES.md` is the owner's alone: write it as a proposal at the end of the month's `STATUS.md`, never into the rules.

## Authority

`MONTH-END-RULES.md` says what an agent may do in each system; read it each session and follow it over anything here. Whatever it allows, a change to a system goes only through the deterministic command built for that change, never by hand. A person uploads every import file. Credentials are never read, printed or written into the folder. One command per call, with no pipes, redirects, `&&` or variables.

## When no one is present

The Steps run the same. A question goes on the owner's task list through comms-confirm rather than being asked live, and the session ends with the Waiting on rows that say what the next session needs. A missing input early in the month is normal: record it and move on. On a dry run, orient and plan only: read everything, report what is done, what is open, what would be dispatched and what would be asked, and dispatch, ask and write nothing in the Month-End folder.
