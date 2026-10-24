---
name: personal-tax-season-method
description: "How the owner's personal tax season is run like a PBC list, on top of personal-workstream: the prior year's tax folder as the template, matches by form type in this year's folder, payment and filing dates as reminders, and the checklist for the outside advisor with what is still owed. The Steps, Build and match the checklist, the reviewer's Check the matches and Check completeness, and DONE. Loaded by personal-tax-season-checklist and personal-reviewer. Use when gathering the year's tax documents by hand. Not for the monthly household review; use personal-finance-review-method. Not for a company's 1099s; that is the accounting plugin's 1099 job."
---

# Tax season as a PBC list

This skill extends `personal-workstream`, which extends `orchestration-workstream`. Load both with the Skill tool if they are not loaded.

## Steps

For `personal-tax-season-checklist`. `RUN` is `runs/<date>/` in the tax folder, or the Run folder on a dry run.

1. [judgment] Orient. Read the rules file, `STATUS.md`, `QUESTIONS.md` and the last checklist (rows already matched need only a recheck that the file is still there).
   → the tax archive cannot be read at all: stop
2. [judgment] Set up `RUN` with `LOG.md`; log a line before each dispatch and record each return.
3. [judgment] Build and match the checklist (section Build and match the checklist): `RUN/CHECKLIST.md` and `RUN/STILL-OWED.md` as drafts, and the claims "row X is file Y" for every `have` row.
4. [hand-off: personal-reviewer] Confirm every match (section Check the matches), given the claims, this year's folder and the fenced list only. Dispatch it together with step 5. Save its return as `RUN/review-matches.md`.
5. [hand-off: personal-reviewer] Look for what the list misses (section Check completeness), given the draft checklist, the prior year's folder listing and the advisor's list when the rules name one. Save its return as `RUN/review-completeness.md`.
   → a match FAIL: step 3 (max 1)
6. [judgment] Record. A match that fails a second time becomes a question. Each completeness question becomes a row, a `not-expected` with its reason, or a question. Write `CHECKLIST.md` and `STILL-OWED.md` in their final form, the new reminders, the questions in `QUESTIONS.md`, and `STATUS.md`.
7. [judgment] Close. Walk the DONE checklist below, citing the evidence for each item, and report: rows by state against the last Run, what is still owed and from whom by role, the reviewer's verdicts, the dates of the next 90 days, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The rules file: `TAX-SEASON-RULES.md`

The owner's. It holds: the tax folder's layout (one folder per year), the returns in scope (and any that are only listed, not worked), the advisor's own request list when there is one, where documents the folder never holds come from (a statement the issuer only posts online, for example), the naming convention for new files, the estimated-payment and filing dates, and what the advisor receives and how (the owner sends it).

## Build and match the checklist

Done by `personal-tax-season-checklist` itself, from the rules file, the prior and current year folders, the tax year and the last checklist.

1. **Build the list.** The advisor's request list wins when the rules file has one. Otherwise list the prior year's folder: every distinct form type, per payer or account and per person by role, becomes a row (`form, issuer, for, expected by, last year's file`). Add a row for each estimated payment and each entity filing the rules name. An invented example row: `1099-INT, Example Credit Union, the owner, 2031-01-31, 2029/1099-INT-lakeview.pdf`.
2. **Already have it?** For each row, look for this year's file by form type and issuer, not by file name: names drift between years. A match cites the file. Two candidate files for one row, or a document whose issuer is unclear, is a question.
3. **Expected by.** Use the date the form arrived last year (the file's date) or the statutory date; never guess one.
4. **New this year.** Note income, accounts or events the household review engine or the rules show that last year's folder has no row for (a new employer, a new account, a sale); each is a row in state `missing` with why it is expected.
5. **Write** `RUN/CHECKLIST.md` (one row per document: state `have`, `missing`, `not-expected`, `question`; the evidence file or the reason) and `RUN/STILL-OWED.md` (what is missing, from whom by role, and since when). Keep the claims list `{row, file}` per `have` row for the reviewer.

On a revision after a FAIL, fix exactly the reviewer's numbered findings and change nothing else.

## Check the matches

For `personal-reviewer`, with `review-facts` as the checklist (load it). The claims are "row X is file Y", one per `have` row; the only source is this year's folder. Lines this job adds:

- Open each cited file and confirm it is the form type and issuer the row names, for the right tax year and the right person by role. A file of the wrong form, issuer or year is CONTRADICTED.
- A file that is not in this year's folder is NOT IN MY SOURCES, and fails: you hold the whole source.
- Never rename, move or edit a file; a name that misleads goes in your fixes as a proposed rename for the owner.

Return the `review-facts` return block.

## Check completeness

For `personal-reviewer`, with `review-completeness` as the checklist (load it). The artifact is the draft checklist; the reference model is the prior year's folder listing, and the advisor's request list when the rules name one (it wins where the two differ). Lines this job adds:

- Every form type in the reference has a row, a `not-expected` with a reason, or a question.
- Questions are for the owner, phrased as the owner would answer them ("Did the brokerage account stay open all year?"), never for the advisor or an issuer.

Return the `review-completeness` return block.

## DONE (the main agent checks each item and cites its evidence)

1. Every form type in the prior year's folder (or the advisor's list) has a row.
2. Every `have` row cites one file in this year's folder; the reviewer confirmed each (section Check the matches): PASS, in `RUN/review-matches.md`.
3. Every `missing` row says who issues it and when it is expected, with the source.
4. The completeness review (section Check completeness) is answered: each question is a row, a `not-expected` with reason, or a question to the owner.
5. Estimated-payment and filing dates in the next 90 days are in `REMINDERS.md`.
6. No file in the tax folder was renamed, moved or edited; a proposed rename is a question.

## The record of the Run

`items` with test `document` (item: `form issuer for`, states `have`, `missing`, `not-expected`, `question`), the rows in the checklist shape, and the reminders, as `LOG.md` records them.

## Later tools

- `tax-folder-list`: a `prepare:` that lists the prior and current year folders into the Run folder, so the session needs no route to where the archive is kept.
- `tax-season-check`: compute DONE items 1, 2 (file exists) and 5 from the checklist and the listing.
