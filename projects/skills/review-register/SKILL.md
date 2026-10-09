---
name: review-register
description: The review register, a folder of YAML tables that holds what is open, at risk, reconciled, owed by the owner and proposed for one review (a close, an engagement, a portfolio). Other skills record their open items, risks and proposals in it and read it back for status, briefs and memos. Use to add, list, close or render register rows.
argument-hint: "[register folder] [summary|list|render|add|close]"
allowed-tools: Read, Bash(python3 ~/.claude/skills/review-register/scripts/register.py:*)
---

# The review register

One folder per review, one YAML file per table, written only by `python3 ~/.claude/skills/review-register/scripts/register.py --dir <folder> <subcommand>`. Never edit the files by hand: every write stamps `updated_at` and appends to the row's `history`.

## Tables

Every row has `id`, `key` (a stable id for rows a check creates), `status`, `evidence` (a list), `created_at`, `updated_at`, `closed_at`, `closed_by`, `history` and `portal_task_id`.

| Table | Ids | Its own fields | Statuses (first is the default) |
|---|---|---|---|
| `open_items` | OI-001 | period, source, check, description, owner, due, amount | open, waiting, done, dropped |
| `risk_register` | RR-001 | opened_period, description, severity (low, medium, high), estimate_booked, estimate_note, research_owner, follow_up, resolution | open, monitoring, closed |
| `rec_status` | REC-001 | account, account_name, period, preparer, reviewer, difference, oldest_open_item, workbook, note | not_started, prepared, reviewed, tied, exception |
| `owed_by_owner` | OBO-001 | handoff_no, group, title, detail, blocks, due, answer | open, answered, done, dropped |
| `proposals` | P1 | title, rationale, source, reason, decided_at | proposed, approved, rejected, applied |

A field the table does not have is refused, so a typo fails instead of adding a column.

## Subcommands

- `summary`: row counts per table and status, as JSON.
- `list TABLE`: one JSON row per line, open rows only; `--status S` for one status, `--all` for every row.
- `render [--period YYYY-MM]`: the open items, live risks, reconciliations, owed items and pending proposals as Markdown for a memo or brief. The owed heading names the owner from the setting `owner_name` in `[review-register]`.
- `add TABLE --by WHO --field key=value ...`: adds a row and prints its id. `evidence` takes a comma-separated list.
- `close TABLE ID --by WHO --status S --reason TEXT`: closes a row with done, dropped, closed, tied, rejected, applied or answered. Closing a risk fills its resolution, answering an owed item fills its answer, and deciding a proposal stamps `decided_at`.

## Rules

- **Only a person closes a row**, or the ledger proves it closed (`--by gl:JE1234`). A `--by` naming a tool or an agent is refused. An agent proposes the closing; a person runs it. `add` refuses a row with a closing status or with `closed_at` or `closed_by` set, so `close` is the only way a row becomes closed.
- Nothing is deleted. A row that no longer applies is closed as `dropped` with the reason.
- The register is client data: keep its folder with the client's work, never in a shared repository.
- Exit 0 on success, 1 when a row is refused (the reason is on stderr), 2 on a bad argument.
