---
name: personal-workstream
description: What is specific to work in the owner's personal domains (household finance review, tax season, home infrastructure, the household, health check-ins), on top of orchestration-workstream. Local processing only, outputs only in the private domain folder the Run's Context names, never a Portal note, task or draft, never a message to anyone, other people's records out of reach, the domain folder's shape, and the return's item tests. Loaded by every personal orchestrator and its workers before their method skill; not for a user request on its own. Not for the owner's work domains; use the department's own workstream skill.
user-invocable: false
---

# Working in the personal domains

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. Each personal orchestrator adds a method skill (`personal-finance-review-method`, `personal-tax-season-method`, `home-infrastructure-method`, `household-method`, `health-routine-method`) with its rules, its DONE checklist and its return fields.

## Why these are different

The personal domains hold the owner's sensitive data and other people's: other household members' records, medical and tax documents, account numbers and balances. Shared systems such as the Insights Portal are visible to people other than the owner, so nothing from this work goes there. These orchestrators run only for the owner: the owner or a schedule the owner set launches them, never another orchestrator.

## Conduct here

- **The rules file first.** The domain folder's rules file (named in the method skill, its path in the Run's Context) says what may be read, what must never be read, who sees the output and the cadence. It wins over this skill and over the method skill.
- **Local only.** Read only the folders and files the Run's Context binds. Write only in the domain folder the Context names, or in the Run folder on a dry run. Never copy personal data into any other folder, repository, note or log.
- **No Portal writes, no messages.** Never create or edit a Portal note, task, comment or draft, never send or draft mail, and never call a person. A reminder is a line in the domain folder's reminders file and in the Run report, which only the owner reads.
- **Questions go to the owner only.** A question for another household member, an advisor or anyone else is a question to the owner, saying whom they may want to ask. Never use `comms-confirm` here: it puts a task in the Portal.
- **Other people's records stay out of reach.** Folders the rules file fences (another household member's own folders, a minor's records, identity papers, medical records) are never read, listed or summarised, even when a path is at hand. If the work seems to need one, ask the owner.
- **Roles, not names, in anything that could travel.** Inside the private folder the owner's own words stand. In the Run report, say "a household member", "the advisor".
- **No secrets.** Never print a token, read a credential file or echo an account number in full; the last four digits identify an account.
- **Already done?** The owner keeps most of these records by hand. Before proposing anything, look for what the owner already did (a file saved, a payment made, a note written) and cite it.
- **Nothing guessed.** A figure, date or state the sources do not show is "not found", with the source that would settle it.

## The domain folder

Each personal Automation binds one private Context naming one domain folder:

```
<domain folder>/
  <DOMAIN>-RULES.md        the owner's rules (the method skill lists what it holds)
  STATUS.md                where the domain stands, the next action; the orchestrator only
  MEMORY.md                durable facts the owner confirmed, each dated with its source
  REMINDERS.md             date, what, why, source, state (open, done, dropped)
  QUESTIONS.md             every question to the owner, its answer and the date answered
  runs/<yyyy-mm-dd>/       one folder per Run: the outputs, LOG.md, the checker's note
```

Only the orchestrator writes `STATUS.md`, `MEMORY.md`, `REMINDERS.md`, `QUESTIONS.md` and `LOG.md`. A worker returns; the orchestrator records. A file the owner wrote is never edited: a correction is a new file beside it. Nothing is deleted.

## The return here

The shared block. Item tests used across the personal domains:

| Test | Item | States |
|---|---|---|
| `source` | a file, export or command read | `read`, `stale`, `missing`, `fenced` |
| `check` | one checklist line of the method skill | `ok`, `attention`, `not-found` |
| `reminder` | a dated obligation | `new`, `open`, `done`, `dropped` |
| `proposal` | a change for the owner to make | `proposed`, `not-needed` |

Put each reminder in `extra.reminders` as `{date, what, why, source}` and each fact for `MEMORY.md` in `proposals` with `document: MEMORY.md`. Questions go `of: owner`.

## Later tools

- `personal-folder-check`: compute the shared DONE items (Run folder written, every reminder sourced, nothing written outside the domain folder) from the folder and the Run log.
