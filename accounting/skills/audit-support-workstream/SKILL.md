---
name: audit-support-workstream
description: "The job skill of accounting-audit-support, not for a user request: working the external auditor's request list (PBC) like a close checklist. Covers \"already provided?\" first, each request mapped to its source in the close folders, support indexed per request, any schedule built from the ledger tied out, the request states, the audit folder's files, the Steps, the sections Prepare a batch (accounting-worker) and Check the support (accounting-reviewer, with the evidence-check checklist), and the DONE checklist. Not for internal control evidence."
---

# Audit support workstream

The external auditor's list of requests (provided by client, PBC) is answered like a close checklist, so fieldwork waits on nothing an agent could have found. Each request is checked against what was already provided, mapped to where its support lives (usually the month-end close folders), and indexed in a support folder a person uploads from. The close binder should make most requests a lookup; what is not a lookup is a question for a named role. `accounting-audit-support` runs it; keep `orchestration-workstream`'s conduct and return its block.

## The folder

The launch supplies the audit folder and, read only, the close folders it draws on.

- `AUDIT-RULES.md` (root): the audit firm's role, the fieldwork dates, the year-end, where support is drawn from (close folders, the delivery folder, systems), who answers which kind of request, what an agent may write, and what never leaves (anything the rules mark sensitive). It wins over this skill.
- `{yyyy}/PBC-{yyyy}.csv`: the request list as exported from the auditor's portal. Columns as exported; the rules name which column is the id, the description, the due date and the status. A person's file: read only. A newer export is a new file.
- `{yyyy}/STATUS.md` and `{yyyy}/LOG.md`: written by the main agent only.
- `{yyyy}/support/<request id>/INDEX.md`: per request, written by the worker: the request, each support file by path with one line on what it shows and the figure it ties to, and any schedule built for the request beside it.

## Request states

| State | When |
|---|---|
| `provided` | The export or the record shows it already went to the auditor; cite it |
| `assembled` | Support is indexed in `support/<id>/` and passed review |
| `needs-person` | Only a person can produce it (a signature, a representation, a third-party confirmation, a judgment); names the role |
| `question` | The request is unclear or its source cannot be found; one question to a role |
| `not-applicable` | The entity has none of what is asked; with the source that shows it |

## Building support

- "Already provided?" first: the export's status column, then last year's folder for a roll-forward request, then the record.
- Draw from finished work: a reviewed reconciliation, a posted journal entry's backup, the closed trial balance, a signed contract. Never a draft, never a preliminary pull.
- A schedule the request asks for (a listing, a rollforward) is built from the ledger pull or the closed trial balance and ties to it; say which figure it ties to and the difference (zero).
- Index, never move. The person's files stay where they are; `INDEX.md` points to them.

## Inputs

- Year: the audit year (the year-end being audited). Requests (optional): only these request ids.
- The audit folder and the close folders, from the launch; `AUDIT-RULES.md` at the audit folder's root.
- Instructions (the owner's words for this Run) and dry run (write support, STATUS.md and LOG.md under `RUN/` only).

## Steps

1. [judgment] Orient. Read `AUDIT-RULES.md`, the newest `{yyyy}/PBC-{yyyy}.csv`, and `{yyyy}/STATUS.md` and `LOG.md` if a Run has been here. Requests already `provided` or `assembled` stay as they are unless the export changed them.
   → no open request: step 6
2. [judgment] Group the open requests by area (cash, revenue, payroll, debt, equity, controls, other) into batches of about ten. Write `RUN/plan.json`.
3. [hand-off: accounting-worker] Prepare. One worker per batch, in parallel, model opus, told to follow this skill's section Prepare a batch, with the batch, the year, the audit and close folder paths, the rules file's path and whether this is a dry run. Save each return as `RUN/returns/<batch>.json`; a reply without the block goes back once for it.
4. [hand-off: accounting-reviewer] Check the numbers: every schedule the workers built, with its source pull or the closed trial balance only, told to use `review-numbers`. Save each note under `RUN/reviews/`.
   → FAIL: step 3 (max 1)
5. [hand-off: accounting-reviewer] Check the support: every `provided` and `assembled` claim, with the INDEX.md and the files it cites only, told to use this skill's section Check the support. Save the note under `RUN/reviews/`. A second FAIL on a request makes it a `question` to the role the rules name.
   → FAIL: step 3 (max 1)
6. [judgment] Write `{yyyy}/STATUS.md` (one row per request: id, area, state, evidence, owner role, due) and a `LOG.md` entry; on a dry run under `RUN/` instead.
7. [judgment] Walk the DONE checklist into `RUN/done.md`, each line with its evidence, and report: counts by state, requests due before fieldwork that are not ready, review FAILs, the DONE result, and the questions by role as one numbered list, requests due before fieldwork first.
   → reported: done

## Prepare a batch

For an `accounting-worker` given one batch of requests. Read `AUDIT-RULES.md` first. Your goal: every request in the batch answered from finished work, or routed to the role who can answer it.

For each request:
1. Already provided? Check the export's status and last year's folder. If so, cite it and stop.
2. Find the finished work that answers it, by the rules' source map: a reviewed reconciliation, posted entries and their backup, the closed trial balance, contracts.
3. Write `{yyyy}/support/<request id>/INDEX.md`: the request text, each file by path with what it shows and the figure it ties to.
4. Where the request asks for a schedule, build it beside the index from the ledger pull or the closed trial balance (`trial-balance`, `excel-handle`, `pdf-handle` to read), and state the tie and the difference.
5. Where only a person can produce it, or the source cannot be found, return a question to the role the rules name, with what you looked at.

Write only under `{yyyy}/support/` (under `RUN/support/` when the brief says dry run). Never edit, move or delete a person's file or the request export. Put nothing the rules mark sensitive in an index or a question.

Return the `orchestration-workstream` block with `workstream: "audit-support"`: `items` one row per request in the batch (`test` `request`, `item` the id, `state`, `evidence` the INDEX.md path or the provided reference, `amount` the tied figure or null); `files` the INDEX.md files and schedules written; `questions` by role, each with `why` and `blocks` (`request:<id>`).

## Check the support

For `accounting-reviewer`. Load `evidence-check` and apply its four checks (exists and readable, right kind, right scope, whole claim) to each claim, with this skill's evidence standard winning where it says more:

- A `provided` claim cites where it went: the export's status, a dated transmittal, last year's folder for a roll-forward. A claim with no such record fails.
- An `assembled` claim's INDEX.md points to finished work that answers the whole request: a reviewed reconciliation, a posted entry's backup, the closed trial balance, a signed contract. A draft, a preliminary pull, or a file that answers part of the request fails.
- Every file INDEX.md names exists at its path and shows what the index says it shows, for the entity and the year-end audited.
- Nothing the rules mark sensitive appears in the index.

Return `evidence-check`'s block, one row per claim (`item` the request id), PASS or FAIL with the fix, and the note text the main agent saves.

## DONE checklist

Checked by the main agent against `STATUS.md` and the support folder; the starred ones are confirmed by `accounting-reviewer` with section Check the support, and every schedule with figures by `accounting-reviewer` with `review-numbers`.

1. Every request in the latest export has a state in `{yyyy}/STATUS.md`.
2. * Every `provided` state cites where it went.
3. * Every `assembled` request's INDEX.md points to finished work that answers the whole request.
4. Every schedule built for a request ties to the ledger or the trial balance, and the reviewer passed it with `review-numbers`.
5. Every `needs-person` and `question` names a role and is in the owner's question list, with requests due before fieldwork first.
6. Nothing was uploaded, sent to the auditor, or written outside the audit folder.

## Later tools

- `audit-support-assemble`: copies the indexed files into an upload folder with the auditor's naming, and checks the copies are byte-identical.
- `audit-support-check --precheck`: requests due within N days that are not `provided` or `assembled`.
- `work-record` and `work-check` from the shared layer, for the evidence file and done.
