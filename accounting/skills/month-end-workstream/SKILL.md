---
name: month-end-workstream
description: Reference loaded after orchestration-workstream (the shared conduct and return block) by the month-end workstream agents, not for a user request. Covers the rules file first, "already done?" from the ledger pull and the folder, never editing an import file, the evidence tests for entries, reconciliations, flux and questions, and the states the orchestrator records with month-end-record. To run a close, start month-end-orchestrator. Read it when writing or changing a month-end agent.
---

# Working as a month-end workstream

This skill extends `orchestration-workstream`: follow its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. What follows is only what a month-end close adds.

A workstream owns a set of checklist rows and balance-sheet accounts for one month, assigned by the orchestrator from `MONTH-END-PROCEDURES-{yyyy-mm}.md`. It does the work or proves that a person did.

## Conduct in a close

- **Read the rules first.** `MONTH-END-RULES.md` says what you may do and the thresholds and tolerances you work to. It overrides your own instructions.
- **Already done?** Check every row and account from the ledger pull and the folder. A person's evidence is a JE number or a file.
- **Check a tool's output against its source before it counts.** A script's or command's result is a claim. Tie its totals to the source, trace a sample of its rows to the source columns and the maps it used, and carry every gap it reports into your return, not just the first. A figure you did not tie is reported as not tied.
- **Import files.** Never edit an import file after it is written; a correction is a new file.
- **No bookkeeping.** The state you never write is `STATUS.md`, `LOG.md`, the procedures copy and the evidence file.

## The return in a close

The shared block, with `period` (yyyy-mm) and `pull_date` (the ledger pull you used, yyyy-mm-dd) beside `workstream` at the top, and each finding naming its `account`:

```json
{
  "workstream": "cash",
  "period": "2026-09",
  "pull_date": "2026-10-05",
  "items": [
    {"test": "reconciliations", "item": "1010", "state": "reconciled",
     "evidence": "reconciliations/1010 Operating checking recon 2026-09.xlsx",
     "amount": 125400.00, "note": "GL equals statement; 3 outstanding checks, all cleared 10/2"},
    {"test": "entries", "item": "cc-accrual", "state": "drafted",
     "evidence": "journal-entries/(ACME) GL upload - September 2026 card accrual (reversing) DRAFT.csv",
     "amount": 4210.50, "note": "lint PASS; 2 unmapped merchants coded to 6999"},
    {"test": "entries", "item": "payroll-accrual", "state": "booked",
     "evidence": "JE 1234", "amount": 32500.00, "note": "booked by a person; agrees to the register"}
  ],
  "rows": [
    {"task": "Reconcile the bank accounts", "status": "done", "evidence": "reconciliations/"}
  ],
  "files": ["reconciliations/1010 Operating checking recon 2026-09.xlsx"],
  "findings": [
    {"account": "1050", "amount": -100000.00, "text": "Money market down 100k on the month; transfer to operating checking, matched on both statements"}
  ],
  "questions": [
    {"ask": "Can the September statement for account 1020 be saved to the 2026-09 folder?",
     "of": "controller", "why": "No statement in the folder; the reconciliation cannot tie", "blocks": ["reconciliations:1020"]}
  ],
  "proposals": [
    {"document": "METADATA_FIELDS.md", "change": "Map merchant NEWCO SOFTWARE to 6120 Software",
     "source": "card report line 14; coded the same way in July and August"}
  ],
  "notes": [],
  "extra": {}
}
```

- `items` are the evidence rows the orchestrator records with `month-end-record`:
  - `test` is one of entries, reconciliations, flux or questions;
  - `state` is one of open, waiting, drafted, booked, reconciled, explained, answered or not-needed (drafted and booked belong to entries, reconciled to reconciliations, explained to flux, answered to questions; the rest fit any test);
  - `amount` is the GL balance a reconciliation tied to, or an entry's total debits;
  - an account range from the procedures table uses the table's Account text as its `item`.
- `rows` are the checklist rows you were assigned, by their Task text, with status open, waiting or done.
