---
name: investor-posting-workstream
description: Reference loaded by investor-posting-preparer and investor-posting-orchestrator, not for a user request; what contractual investor data-room posting adds to orchestration-workstream. Covers POSTING-RULES.md (the schedule of what is owed by when, where approved finals live, the data room's folders and naming, proof of posting), the posting status table, approved finals copied unmodified, the staged packet and upload checklist, a draft notice quoting only the approved package, and the DONE checklist.
---

# Investor posting

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. The board package itself is `board-package-workstream`'s; this work only posts what was approved.

Investor agreements often require monthly and quarterly results in a data room by a date. The work is not hard; it is late because nobody owns the reminder and the last mile. Agents do everything but the upload and the send.

## The rules file

`POSTING-RULES.md` (in the Reporting folder, or wherever the caller points) names:
- the schedule: each document (monthly package, quarterly statements, annual audited statements), the period it covers, the due rule ("within 30 days of month end");
- where each approved final lives and what records its approval (the owner's approval task, a "Final" file name, a reviewer note);
- the data room's folders and file naming;
- what proves a posting (a saved confirmation, a dated screenshot, the person's line);
- the notice template and who sends it.

It wins over this skill.

## The folder

```
<Reporting folder>/investor-posting/
  POSTING-STATUS.md        one row per owed posting: period, document, due, state, evidence
                           (the orchestrator's only)
  <period>/staged/         the copies, renamed
  <period>/MANIFEST.md  UPLOAD-CHECKLIST.md  NOTICE-DRAFT.md  reviews/
```

States: `posted` (proof saved), `staged` (packet ready, reviewer PASS), `blocked` (a required file missing or unapproved), `late` (past due and not posted).

## Approved finals only

A staged file is a byte-for-byte copy of the approved final; the manifest records the `diff` that proves it. Never stage a draft, a file with "DRAFT" or "v<n>" past the approved one, or a re-export. A correction to an approved file is a new approval, not a new copy.

## DONE checklist

The orchestrator checks each item with evidence; the reviewer confirms 3 and 4.

1. Every posting the schedule requires up to today has a row in `POSTING-STATUS.md`.
2. Every `posted` row cites the proof the rules name.
3. Every staged file is identical to its approved source (`diff`), and its approval is cited.
4. Every figure in `NOTICE-DRAFT.md` is printed in the approved package.
5. Every `blocked` or `late` row has a question with an owner or a waiting item.
6. Nothing was uploaded or sent by an agent.

## Later tools

- `posting-stage`: copy approved finals into the packet under the data room's names and write the manifest with SHA-256 checksums of source and copy.
- `posting-check --precheck`: list postings due within their lead time and not posted, from the schedule and `POSTING-STATUS.md`; a cheap precheck for a scheduled run.
