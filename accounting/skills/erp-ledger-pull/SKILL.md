---
name: erp-ledger-pull
description: "Read what the ERP holds for a period, read-only, so close work starts from the books: a dated ledger pull into the month folder, the trial balance from it, GL detail for one account or date range, and any system's export normalized to the one ledger shape the finance tools read. Use before deciding what is open in a close, for \"what is in account X\" or \"is that entry posted\", and to refresh a pull after people book entries. Intacct API behavior is in sage-intacct-reference."
argument-hint: "[Month-End folder] [period yyyy-mm] [optional: account or question]"
allowed-tools: Read, Glob, Write, Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/month_end_pull.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/intacct_snapshot.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/trial_balance.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/intacct_gl_detail.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/gl_normalize.py:*)
---

# Reading the ERP

The ERP is the source of truth for a close, and a pull is a snapshot of it. Every figure you take from a pull carries the pull's date. "Not in the ledger" always means "not in the pull of that date".

`SYSTEMS.md` in the Month-End folder names the ERP, how data comes out, and where the pull lands, normally `{yyyy}/{yyyy-mm}/work/source/` with a `pulled.md` that states:
- the date and time of the pull;
- the row counts;
- whether the period was still open (PRELIMINARY);
- any gap.

## What to read

1. **The existing pull first.** Read `work/source/pulled.md`. If it is recent enough for the question, use it, and say its date.
2. **Refresh** when people have booked entries since the pull, the pull says PRELIMINARY and you need final numbers, or the question needs a month not yet pulled. Run `python3 ~/.claude/skills/erp-ledger-pull/scripts/month_end_pull.py <Month-End folder> --period yyyy-mm --live`. It reads the ERP and the trial-balance inputs from `SYSTEMS.md`'s `## Close inputs`, pulls the headers, lines, AP bill lines and AR invoice lines read-only, gates them, moves the earlier pull to `superseded-<date-time>/`, rebuilds the trial balance when configured and writes `pulled.md`. Its first line is `FRESH: ...` or `STALE: <reason>; using the pull of <date>`; on STALE the earlier pull is untouched, so quote its date. A person's export goes in with `--offline-from DIR`. `intacct-snapshot` remains for a pull outside a Month-End folder.
3. **The trial balance**: `trial-balance` builds it from posted lines (the opening balances, any bridge, and the current lines), as a workbook and JSON beside the pull. `month-end-pull` gives it its own lines pull from the day after the history (at most thirteen months back, or from `- Trial balance pull from:`) through the period end, so entries booked late into earlier months are in it; a gap the bridge does not cover leaves the trial balance unbuilt and says so. When its first line reports accounts changed against the previous trial balance, look at the swing before using the numbers. A trial balance that does not balance is a stop: report it.
4. **One account or a date range**: `python3 ~/.claude/skills/erp-ledger-pull/scripts/intacct_gl_detail.py --account N --start yyyy-mm-dd --end yyyy-mm-dd`, for a question the period pull does not cover.
5. **Another ERP**: export the GL detail to CSV or Excel, then `gl-normalize` it with the map for that system into the standard ledger shape. Every finance tool reads that shape. Record the export's source and date in `pulled.md`.

Run any of these with `--help` for the full options.

On Sage Intacct, load the `sage-intacct-reference` skill first: it holds how the API behaves (objects, fields, sign conventions, report services) for any company.

## Rules

- **Read only.** Nothing here writes to the ERP.
- **Credentials.** The Sage Intacct scripts read them from the environment only, and all four are required: `SAGE_INTACCT_CLIENT_ID`, `SAGE_INTACCT_CLIENT_SECRET`, `SAGE_INTACCT_COMPANY_ID` and `SAGE_INTACCT_API_USER`. The company id and API user may instead be the settings `intacct_company_id` and `intacct_api_user` under `[erp-ledger-pull]`. A sandbox pull tries each name with a `_SANDBOX` suffix first. A script missing one names it and stops. Never read, print or copy a credential, and never write one into the folder.
- **Snapshots, not truth.** A figure that matters is quoted with the pull date and the file it came from.
- **Gaps.** A gap the pull reports (a service the API user cannot run, an object with no headers) stays a gap. Say so; do not fill it from another source without saying which.
