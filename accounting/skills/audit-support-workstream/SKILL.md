---
name: audit-support-workstream
description: "Reference loaded by audit-support-preparer and audit-support-orchestrator, not for a user request; adds to orchestration-workstream. Covers working the auditor's request list (PBC) like a close checklist: \"already provided?\" first, each request mapped to its source in the close folders, support indexed per request, any schedule built from the ledger tied out, the request states, the audit folder's files and the DONE checklist. Read it when writing or changing either agent."
---

# Audit support workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. What follows is only what audit support adds.

The work: the external auditor's list of requests (provided by client, PBC) is answered like a close checklist. Each request is checked against what was already provided, mapped to where its support lives (usually the month-end close folders), and indexed in a support folder a person uploads from. The close binder should make most requests a lookup; what is not a lookup is a question for a named role.

## The folder

The caller supplies the audit folder and, read only, the close folders it draws on.

- `AUDIT-RULES.md` (root): the audit firm's role, the fieldwork dates, the year-end, where support is drawn from (close folders, the delivery folder, systems), who answers which kind of request, what an agent may write, and what never leaves (anything the rules mark sensitive). It wins over this skill.
- `{yyyy}/PBC-{yyyy}.csv`: the request list as exported from the auditor's portal. Columns as exported; the rules name which column is the id, the description, the due date and the status. A person's file: read only. A newer export is a new file.
- `{yyyy}/STATUS.md` and `{yyyy}/LOG.md`: written by the orchestrator only.
- `{yyyy}/support/<request id>/INDEX.md`: per request, written by the preparer: the request, each support file by path with one line on what it shows and the figure it ties to, and any schedule built for the request beside it.

## Request states

| State | When |
|---|---|
| `provided` | The export or the record shows it already went to the auditor; cite it |
| `assembled` | Support is indexed in `support/<id>/` and passed review |
| `needs-person` | Only a person can produce it (a signature, a representation, a third-party confirmation, a judgment); names the role |
| `question` | The request is unclear or its source cannot be found; one question to a role |
| `not-applicable` | The entity has none of what is asked; with the source that shows it |

## Building support

- "Already provided?" first: the export's status column, then last year's folder for a roll- forward request, then the record.
- Draw from finished work: a reviewed reconciliation, a posted journal entry's backup, the closed trial balance, a signed contract. Never a draft, never a preliminary pull.
- A schedule the request asks for (a listing, a rollforward) is built from the ledger pull or the closed trial balance and ties to it; say which figure it ties to and the difference (zero).
- Index, never move. The person's files stay where they are; `INDEX.md` points to them.

## What the preparer returns

The `orchestration-workstream` block: `items` one row per request (`test` `request`, `item` the id, `state`, `evidence` the INDEX.md path or the provided reference, `amount` the tied figure or null); `files` the INDEX.md and schedules written; `questions` by role.

## DONE checklist

Checked by the orchestrator against `STATUS.md` and the support folder; the starred ones are confirmed by `compliance-evidence-checker`, and every schedule with figures by `numbers-reviewer`.

1. Every request in the latest export has a state in `{yyyy}/STATUS.md`.
2. * Every `provided` state cites where it went.
3. * Every `assembled` request's INDEX.md points to finished work that answers the whole request.
4. Every schedule built for a request ties to the ledger or the trial balance, and `numbers-reviewer` passed it.
5. Every `needs-person` and `question` names a role and is in the owner's question list, with requests due before fieldwork first.
6. Nothing was uploaded, sent to the auditor, or written outside the audit folder.

## Later tools

- `audit-support-assemble`: copies the indexed files into an upload folder with the auditor's naming, and checks the copies are byte-identical.
- `audit-support-check --precheck`: requests due within N days that are not `provided` or `assembled`.
- `work-record` and `work-check` from the shared layer, for the evidence file and done.
