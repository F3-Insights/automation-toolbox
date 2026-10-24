---
name: investor-posting-workstream
description: "The finance-investor-posting job's Steps and standard for contractual investor data-room postings: POSTING-RULES.md (the schedule of what is owed by when, where approved finals live, the data room's folders and naming, proof of posting), the posting status table, approved finals copied unmodified, the staged packet and upload checklist, a draft notice quoting only the approved package, and the DONE checklist. Sections Stage a period (finance-investor-posting, or finance-worker for a catch-up) and Check a packet (finance-reviewer). Use for \"what do we owe investors this month\", with or without finance-investor-posting. Not for building the board package; that is the reporting department's."
argument-hint: "[Reporting folder] [period]"
allowed-tools: Read, Glob, Grep, Bash(cp:*), Bash(diff:*), Bash(pdf-handle:*), Bash(excel-handle:*)
---

# Investor posting

Investor agreements often require monthly and quarterly results in a data room by a date. The work is not hard; it is late because nobody owns the reminder and the last mile. Agents do everything but the upload and the send. The goal: no posting the agreements require is late or wrong; every owed period has a staged packet a person can upload in minutes, made only of approved final files, and the owner sees at a glance what is owed, staged and posted. Keep `orchestration-workstream`'s conduct.

The board package itself is the reporting department's board-package job; this work only posts what was approved, reading the finished files by path from the rules. That file contract does not change.

## Inputs

- **Reporting folder** and `POSTING-RULES.md` (required, from the caller).
- **Period** (optional): yyyy-mm or yyyy-Qn. Default: every period owed and not posted.
- **Instructions** (optional): override the defaults here, never the rules.
- **Dry run**: stage in the Run folder (or a scratch folder by hand); write nothing in the Reporting folder and ask no one.

## Steps

For `finance-investor-posting`, and by hand; without an Automation the questions go in the report.

1. [judgment] Orient. Read POSTING-RULES.md and `investor-posting/POSTING-STATUS.md`. List every posting the schedule requires up to today, with its due date.
   → the rules have no schedule: stop
2. [judgment] Already posted? For each, look for the proof the rules name (a saved posting receipt, a dated confirmation, the person's line in POSTING-STATUS.md). Posted with proof is done.
   → nothing owed: step 7
3. [judgment] Stage each owed period (section Stage a period) yourself, one period at a time.
4. [hand-off: finance-worker] Catch-up only: when three or more periods are owed, hand each period beyond the first to the worker (section Stage a period), on sonnet, each with its period, the rules' path and the folder, in parallel.
   → fewer than three periods owed: step 5
5. [hand-off: finance-reviewer] Check a packet (section Check a packet), on opus, per staged packet, with the packet, the approved package it came from and the rules, never the preparer's reasoning. Write its return to the period's `reviews/`.
   → FAIL: step 3 (max 1)
6. [script] Ask. A period whose package is not yet approved, or a document the rules require that does not exist, goes to its role with `confirm new` and `confirm task`, then one message with `confirm relay`. Skip on a dry run.
7. [judgment] Record and close. Update POSTING-STATUS.md: one row per owed posting with its state and evidence. Walk the DONE checklist with evidence; report the postings by state with due dates, each staged packet with its files and verdict, the owner's upload steps as one list, and the questions as one numbered list.
   → reported: done

Nobody watches a scheduled session: never end with `needs_owner` unless POSTING-RULES.md has no schedule.

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
                           (finance-investor-posting's only)
  <period>/staged/         the copies, renamed
  <period>/MANIFEST.md  UPLOAD-CHECKLIST.md  NOTICE-DRAFT.md  reviews/
```

States: `posted` (proof saved), `staged` (packet ready, reviewer PASS), `blocked` (a required file missing or unapproved), `late` (past due and not posted).

## Approved finals only

A staged file is a byte-for-byte copy of the approved final; the manifest records the `diff` that proves it. Never stage a draft, a file with "DRAFT" or "v<n>" past the approved one, or a re-export. A correction to an approved file is a new approval, not a new copy.

## Stage a period

Done by `finance-investor-posting` itself, or by `finance-worker` for a catch-up period. One period: a packet a person can upload without opening anything else, made only of approved finals, with proof of which version each file is.

1. **What is owed.** From the rules' schedule, the documents this period requires.
2. **Find the approved finals.** For each document, the file the rules say is approved (the board package the owner approved, a final financial statement), never a draft or a working file. When two versions exist, the approval record decides; when there is none, it is a question.
3. **Stage.** Copy each with `cp` into `investor-posting/<period>/staged/` under the data room's file name, never altering its content, and prove the copy with `diff` against the source. Write `MANIFEST.md`: data-room folder, file name, source path, approval evidence, size, and the `diff` result (identical).
4. **Checklist and notice.** Write `UPLOAD-CHECKLIST.md` (where each file goes, in order, and the proof to save afterwards) and `NOTICE-DRAFT.md`, the investor notice in the rules' template, quoting only figures printed in the approved package (read with `pdf-handle` or `excel-handle`), each with its page.

A worker returns the `orchestration-workstream` block with `workstream: "investor-posting"`: `items` one row per required document (`test` `document`, `state` staged, missing or unapproved, `evidence` the manifest line); `files`; `findings` for a required document that does not exist; `questions` for an unclear approval, `of` a role; `extra` `{"period": "...", "due": "yyyy-mm-dd", "packet": "investor-posting/<period>/staged/"}`.

## Check a packet

For `finance-reviewer`, per staged packet, given the packet folder, the approved files it came from and the rules; never the preparer's reasoning. Each line a blocker:

1. Every file the schedule requires for the period is in `staged/` or named as missing or unapproved; nothing else is staged.
2. Each staged file is identical to its approved source: run `diff` on the pair yourself; the manifest's word is not enough.
3. Each source is the approved final: the approval evidence the manifest cites exists and names that file and version.
4. Each file name and data-room folder follows the rules' convention.
5. Every figure in `NOTICE-DRAFT.md` is printed in the approved package at the page it cites (read with `pdf-handle` or `excel-handle`); load `review-numbers` for how a figure is matched.
6. Nothing in the packet was uploaded or sent.

Return PASS or FAIL with numbered fixes, each naming the file and line.

## DONE checklist

`finance-investor-posting` checks each item with evidence; items 3 and 4 count only with `finance-reviewer`'s PASS (Check a packet).

1. Every posting the schedule requires up to today has a row in `POSTING-STATUS.md`.
2. Every `posted` row cites the proof the rules name.
3. Every staged file is identical to its approved source (`diff`), and its approval is cited.
4. Every figure in `NOTICE-DRAFT.md` is printed in the approved package.
5. Every `blocked` or `late` row has a question with an owner or a waiting item.
6. Nothing was uploaded or sent by an agent.

## Later tools

- `posting-stage`: copy approved finals into the packet under the data room's names and write the manifest with SHA-256 checksums of source and copy.
- `posting-check --precheck`: list postings due within their lead time and not posted, from the schedule and `POSTING-STATUS.md`; a cheap precheck for a scheduled run.
