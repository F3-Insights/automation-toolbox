---
name: personal-tax-season-method
description: How the owner's personal tax season is run like a PBC list, on top of personal-workstream. The prior year's tax folder is the template (every form type filed last year becomes a row), "already have it?" is a match on form type in this year's folder, estimated payments and filing dates become reminders, and the output is the checklist for the outside tax advisor with every row's evidence and the documents still owed. The rules file, the DONE checklist and the return fields. Loaded by personal-tax-season-orchestrator and personal-tax-season-analyst. Use when gathering the year's tax documents by hand. Not for the monthly household review; use personal-finance-review-method. Not for a company's 1099s; use vendor-1099-workstream.
---

# Tax season as a PBC list

This skill extends `personal-workstream`. Read it, and `orchestration-workstream`, from `~/.claude/skills/<name>/SKILL.md` if they are not loaded.

## The rules file: `TAX-SEASON-RULES.md`

The owner's. It holds: the tax folder's layout (one folder per year), the returns in scope (and any that are only listed, not worked), the advisor's own request list when there is one, where documents the folder never holds come from (a statement the issuer only posts online, for example), the naming convention for new files, the estimated-payment and filing dates, and what the advisor receives and how (the owner sends it).

## Method

1. **Build the list.** The advisor's request list wins when the rules file has one. Otherwise list the prior year's folder: every distinct form type, per payer or account and per person by role, becomes a row (`form, issuer, for, expected by, last year's file`). Add a row for each estimated payment and each entity filing the rules name. An invented example row: `1099-INT, Example Credit Union, the owner, 2031-01-31, 2029/1099-INT-lakeview.pdf`.
2. **Already have it?** For each row, look for this year's file by form type and issuer, not by file name: names drift between years. A match cites the file. Two candidates is a question.
3. **Expected by.** Use the date the form arrived last year (the file's date) or the statutory date; never guess one.
4. **New this year.** Note income, accounts or events the household review engine or the rules show that last year's folder has no row for (a new employer, a new account, a sale); each is a row in state `missing` with why it is expected.
5. **Write** `runs/<date>/CHECKLIST.md` (one row per document: state `have`, `missing`, `not-expected`, `question`; the evidence file or the reason) and `runs/<date>/STILL-OWED.md` (what is missing, from whom by role, and since when).

## DONE (the orchestrator checks each item and cites its evidence)

1. Every form type in the prior year's folder (or the advisor's list) has a row.
2. Every `have` row cites one file in this year's folder; the checker (`fact-check`) confirmed each: PASS.
3. Every `missing` row says who issues it and when it is expected, with the source.
4. The completeness review (`completeness-audit` against the prior year's list) is answered: each question is a row, a `not-expected` with reason, or a question to the owner.
5. Estimated-payment and filing dates in the next 90 days are in `REMINDERS.md`.
6. No file in the tax folder was renamed, moved or edited; a proposed rename is a question.

## The return here

`items` with test `document` (item: `form issuer for`, states `have`, `missing`, `not-expected`, `question`), `extra.rows` in the checklist shape, `extra.reminders`.

## Later tools

- `tax-folder-list`: a `prepare:` that lists the prior and current year folders into the Run folder, so the session needs no route to where the archive is kept.
- `tax-season-check`: compute DONE items 1, 2 (file exists) and 5 from the checklist and the listing.
