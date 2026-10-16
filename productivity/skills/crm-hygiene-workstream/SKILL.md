---
name: crm-hygiene-workstream
description: "The weekly CRM hygiene pass's method, loaded by crm-hygiene and by the productivity-worker and productivity-reviewer it dispatches, not for a user request; adds to orchestration-workstream. Covers CRM-HYGIENE-RULES.md first, the scope (contacts, companies, their links and facts, duplicates, Portal defects, the metrics block; tasks belong to the task-stack jobs), fixes only on evidence, merges only on the owner's yes, defects as issue drafts, the three-pass flag rule, the sections Analyse a slice and Check fixes and merges, the DONE checklist and the pass note."
---

# CRM hygiene

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it if it is not loaded. The method behind it is `references/hygiene-method.md` in this skill's folder: its evidence sources in order of authority, its integrity and errors duties, its metrics block and its failure modes all apply. This skill narrows the scope and makes the pass a Run.

The goal: a CRM every other agent can rely on. Contacts and companies hold the facts the record states, no person is split across two records, sync damage does not go unseen, and a weekly metrics line shows whether the Portal is getting more trustworthy or less.

## Steps

For `crm-hygiene`. `RUN` is the working folder; only the main agent writes there.

1. [judgment] Orient. `whoami`; read the rules file; find last week's pass note (`search` "[CRM Hygiene] CRM Hygiene Pass") for the trend and the flag counts.
2. [judgment] Slice the work into at most four slices (by domain, plus one for duplicates and one for errors) and write `RUN/plan.json`.
3. [hand-off: productivity-worker] One worker per slice, in parallel, told to follow section Analyse a slice, with the slice, the rules path, the owner's contact id and last week's note ref. Save each return to `RUN/returns/<slice>.json` as it arrives.
4. [hand-off: productivity-reviewer] Every medium-confidence fix and every approved merge, the items only (section Check fixes and merges).
5. [judgment] Write, unless dry run: each high fix and each passed medium fix (`update_contact`, `update_company`, `add_contact_fact`), then each approved merge that passed (`merge_contacts`). Re-read each record after its write. Record every write in `RUN/writes.json` with its evidence and result. A dry run writes what would be written there instead.
6. [judgment] Draft defects into `RUN/defects.json` (the issue shape below). Never file them.
7. [judgment] Write the pass note (`create_note`, the shape below), then `search` its title and confirm it is found. Dry run: `RUN/pass-note.md` only.
8. [judgment] Tick the DONE checklist into `RUN/done.json`, each item with its evidence, and report: the metrics line against last week, fixes and merges made, duplicate pairs for the owner as one numbered list ("ok" to merge), defects drafted, flags, questions, what was not covered.
   → reported: done

## The rules file first

`CRM-HYGIENE-RULES.md` (path in the inputs as `hygiene_rules`) says which fields an agent may set without asking, which domains to cover, and the metrics baseline. It wins.

## Scope

- **In:** contacts and companies (title, company link, relationship context, facts), duplicate contacts and companies, records changed by something no person did, Portal defects, and the metrics block.
- **Out:** task status, filing, owners and dates. The task-stack jobs (task-steward, project health) own those through `task-stack-apply`. Count tasks for the metrics; never fix one here.
- **Out:** enrichment research. A gap worth researching is a proposal in the pass note for the enrichment queue (`crm-context-enrichment`), not a pass of its own.

## Fix, propose or flag

- **Fix** a missing or wrong factual field when the fact is stated in the Portal (a signature, a company record, a note that says it plainly). Cite the ref. Never infer a title from a domain or an industry. Prefer `add_contact_fact` with its source over rewriting a free-text field.
- **Propose** every duplicate pair for the owner's merge: both ids, which side holds the history, the evidence they are one person. A merge happens only in a later Run whose `approved_merges` input names the pair.
- **Flag** what evidence cannot settle, saying what would. An item flagged on three consecutive passes with no new evidence becomes one question for the owner instead, and leaves the flag list.
- **Defects** in Portal software (a tool returning the wrong records, contacts deactivated by sync) are issue drafts: title `IR-<yyyymmdd>-<slug>`, evidence (the call, actual and expected), impact, ask. Check the issue numbers the rules list as open first; cite one rather than draft a duplicate.

## Analyse a slice

For `productivity-worker`. Your slice is a set of domains or one duty (duplicates, errors). Use `references/hygiene-method.md` for the integrity, errors and metrics duties; the writes and the pass note are the main agent's. Page every listing at 100 or less. You make no writes.

Return the `orchestration-workstream` block with `workstream: "crm-hygiene-slice"`. `extra.fixes`: `{"id", "entity": "portal://contact/<id>", "op": "update_contact | update_company | add_contact_fact", "set": {...} or "fact": "...", "evidence": "portal://email/<id>", "confidence": "high | medium"}`. `extra.duplicates`: `{"a", "b", "history": "a | b | both", "evidence"}`. `extra.defects`: the issue drafts. `extra.metrics`: the metrics block, a value or `unavailable` with the reason, never an unmeasured zero. `findings`: the flags.

## Check fixes and merges

For `productivity-reviewer`, given the proposed fixes and merges only, the rules path and the owner's contact id. For each fix: open the entity and the evidence ref; PASS only when the evidence states the fact for this entity, the field does not already hold it, and no person edited that field in the last seven days. For each merge: PASS only when the pair is the one the owner approved and the two records are one person by address, name and history.

Return the `orchestration-workstream` block, `workstream: "crm-hygiene-check"`, one `items` row per fix or merge: `test` `fix` or `merge`, `item` its id, `state` PASS or FAIL, `evidence` the ref read, `note` one line.

## Never

- Change a task, delete anything, or merge a pair the owner did not approve.
- Fix a field from inference, or overwrite a person's edit of the last seven days.
- Reach GitHub or file an issue in the session; defects are drafts for the finish step.
- Report a metric as zero that was not measured.

## DONE checklist

- [ ] The metrics block is complete (each value measured or `unavailable` with why) and compared with last week's pass note: overdue, untouched-30d, ownerless, duplicate pairs, data_health totals not worse, or the reason they are.
- [ ] Every fix made cites its evidence ref, and every medium-confidence fix passed the checker (checked).
- [ ] Every approved merge named in the inputs was made or reported with the reason; no other merge was made (checked).
- [ ] Duplicates, flags, defects and questions are each listed or "none".
- [ ] One pass note exists and is findable by search on its title.
- [ ] No task was changed and nothing was deleted.

## The pass note

One Portal note, `note_type` `research`, title `[CRM Hygiene] CRM Hygiene Pass <yyyy-mm-dd> (weekly)`, so every pass is found by one search, in this section order: a metrics line (`**Metrics:** overdue N | untouched-30d N | ownerless N | duplicate-pairs N | data_health N | open questions N`), a pass line (fixes, flags, issue drafts, questions), Fixed (one line per change with its evidence), Flags, Duplicates for merge (both ids, which side holds the history), Errors and anomalies, Questions, Not covered. Under 1200 words, factual, nothing a colleague should not read.

## Filing the defect drafts

The finish step files each draft in `RUN/defects.json` after the session, one call per draft, so the session never reaches GitHub:

```bash
productivity-portal-issue-file --title "..." --body "..." [--label bug] [--dry-run]
```

It files only on the repository the `portal_issue_repo` setting under `[crm-hygiene-workstream]` names (owner/name), refuses a draft holding a home-folder path, a secret-shaped string or any of the `private_terms` setting's words, and answers `duplicate` when an open issue has the same title. `$GH` names another `gh` program, for tests.

Later, in code before the session: the metrics block (`crm-hygiene-metrics`) and approved merges with an undo record (`crm-merge-apply`).
