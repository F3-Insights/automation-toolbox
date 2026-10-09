---
name: month-end-journal-entry
description: "Prepare one month-end journal entry the way a reviewer expects to receive it: check it is not already booked, calculate it from sources, write the ERP import file a person uploads (STATE Posted) with its backup beside it, lint it, and know when it counts as booked. Use whenever a close needs an accrual, reclass, correction or recurring entry drafted, or for \"is this JE booked\". For the card and post-cutoff vendor accruals, use month-end-accrual-drafts."
argument-hint: "[Month-End folder] [period yyyy-mm] [what the entry is for]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import.py:*), Bash(python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import_check.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/intacct_gl_detail.py:*)
---

# A month-end journal entry

A journal entry is two files, never one: the import file a person uploads, and the backup that proves every line. Both go in the period's `journal-entries/` folder. `MONTH-END-RULES.md` says how an entry may reach the ERP; today that is an import file a person uploads (STATE Posted). That person's upload is the human review, so the file says Posted. Agents never upload or post. STATE Draft is kept for an entry an agent creates in the ERP through its API with no person involved, which a person then posts there; no workstream does that today.

## Before drafting

- **Already booked?** Search the ledger pull for an entry dated in the period on the same accounts, with a matching description or amount, and look in `journal-entries/` for an earlier draft. If one exists, record its JE number or file and stop. A draft in the ledger ("entered", not posted) is waiting on a person, not missing.
- **Recurring?** Look at the prior three months for the same entry, and use its accounts, dimensions, description and reversal pattern unless the facts changed. A change from the pattern is called out in the backup.

## The entry

- **Calculate from sources.** The backup states each amount's source (file, sheet, row or JE key) and the arithmetic, so a reviewer re-derives every line without asking.
- **Code from the company's rules.** Accounts and dimensions follow `METADATA_FIELDS.md`. Something it does not cover is a question, not a guess.
- **One entry per purpose,** dated the period's last day unless the rules say otherwise. Reversing when it is an accrual, with the reversal dated the 1st of the next month.
- **The description says what and why** in words a reader of the ledger understands next year: "To accrue September 2026 legal fees billed in October", not "accrual".

## The files

- **Import file:**
  - for Sage Intacct, build it with `je-import` from a proposals JSON (one object per entry with its lines; `python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import.py --help` shows the shape); STATE is Posted, the default; the layout it writes is in the `sage-intacct-reference` skill's `import-format.md`;
  - the file name follows the pattern in `METADATA_FIELDS.md`, or `{yyyy-mm} JE {short name} DRAFT.csv`;
  - for another ERP, its own import layout, with the same lint by hand: balanced, valid accounts, dates in the period.
- **Lint:** `python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import_check.py FILE` (it requires STATE Posted by default). A file that fails is never handed to a person.
- **Backup:** the same name with ` backup` and `.md` (or `.xlsx` when the calculation is a table). It holds:
  - the purpose;
  - the sources with their dates;
  - the calculation;
  - the already-booked check and what it found;
  - who prepared it and when;
  - anything a reviewer should look at.
- **Never overwrite.** A corrected entry is a new file with ` v2`, and the backup says why.

## When it counts as booked

An entry is booked when a fresh ledger pull shows it **posted**, with the same total as the draft (tolerance in `MONTH-END-RULES.md`). Record the JE number and the pull date as its evidence. Until then it is drafted, and the evidence says so.
