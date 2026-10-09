---
name: crm-hygiene-workstream
description: Reference loaded by crm-data-hygiene-orchestrator, crm-hygiene-analyst and crm-hygiene-checker, not for a user request; what the weekly CRM hygiene pass adds to orchestration-workstream. Covers CRM-HYGIENE-RULES.md first, the scope (contacts, companies, their links and facts, duplicates, Portal defects, the metrics block; tasks belong to the task-stack orchestrators), fixes only on evidence, merges only on the owner's yes, defects as issue drafts, the three-pass flag rule, fix and finding shapes, the DONE checklist and the pass note.
---

# CRM hygiene

This skill extends `orchestration-workstream`. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. The method behind it is `references/hygiene-method.md` in this skill's folder: its evidence sources in order of authority, its integrity and errors duties, its metrics block and its failure modes all apply. This skill narrows the scope and makes the pass an orchestrated one.

## The rules file first

`CRM-HYGIENE-RULES.md` (path in the inputs as `hygiene_rules`) says which fields an agent may set without asking, which domains to cover, and the metrics baseline. It wins.

## Scope

- **In:** contacts and companies (title, company link, relationship context, facts), duplicate contacts and companies, records changed by something no person did, Portal defects, and the metrics block.
- **Out:** task status, filing, owners and dates. The task-stack orchestrators (reconcile, clarify, project health) own those through `task-stack-apply`. Count tasks for the metrics; never fix one here.
- **Out:** enrichment research. A gap worth researching is a proposal in the pass note for the enrichment queue (`crm-context-enrichment`), not a pass of its own.

## Fix, propose or flag

- **Fix** a missing or wrong factual field when the fact is stated in the Portal (a signature, a company record, a note that says it plainly). Cite the ref. Never infer a title from a domain or an industry. Prefer `add_contact_fact` with its source over rewriting a free-text field.
- **Propose** every duplicate pair for the owner's merge: both ids, which side holds the history, the evidence they are one person. A merge happens only in a later Run whose `approved_merges` input names the pair.
- **Flag** what evidence cannot settle, saying what would. An item flagged on three consecutive passes with no new evidence becomes one question for the owner instead, and leaves the flag list.
- **Defects** in Portal software (a tool returning the wrong records, contacts deactivated by sync) are issue drafts: title `IR-<yyyymmdd>-<slug>`, evidence (the call, actual and expected), impact, ask. Check the issue numbers the rules list as open first; cite one rather than draft a duplicate.

## The analyst's return

The `orchestration-workstream` block. `extra.fixes`: `{"id", "entity": "portal://contact/<id>", "op": "update_contact | update_company | add_contact_fact", "set": {...} or "fact": "...", "evidence": "portal://email/<id>", "confidence": "high | medium"}`. `extra.duplicates`: `{"a", "b", "history": "a | b | both", "evidence"}`. `extra.defects`: the issue drafts. `extra.metrics`: the metrics block, a value or `unavailable` with the reason, never an unmeasured zero. `findings`: the flags.

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
python3 ~/.claude/skills/crm-hygiene-workstream/scripts/portal_issue_file.py --title "..." --body "..." [--label bug] [--dry-run]
```

It files only on the repository the `portal_issue_repo` setting under `[crm-hygiene-workstream]` names (owner/name), refuses a draft holding a home-folder path, a secret-shaped string or any of the `private_terms` setting's words, and answers `duplicate` when an open issue has the same title. `$GH` names another `gh` program, for tests.

## Later tools

- `crm-hygiene-metrics`: the metrics block and last week's in code, before the session.
- `crm-merge-apply`: approved merges in code, with an undo record.
