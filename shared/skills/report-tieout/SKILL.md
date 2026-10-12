---
name: report-tieout
description: "Check that a set of monthly reports (results memo, board deck, lender package, variance report, dashboard export) quote the same consolidated figures for the same months: reads each file, writes a CSV ledger of every quoted figure and runs `report-tieout`; the judgment is which figure is right. Use for \"do the reports all match\", after one report was re-run, or as the last step before a package is sent. To re-derive figures from source, use the numbers-reviewer agent."
argument-hint: "[folder or files] [metric, e.g. Consolidated EBITDA] [tolerance]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/report-tieout/scripts/report_tieout.py:*), Bash(python3:*)
---

# Report tie-out

The usual failure: several documents each quote EBITDA by month, some were re-run after a late journal and some were not, and nobody can say which are current. This skill is the procedure that answers that in one pass, and `report-tieout` is the part of it that does not need a person.

## Steps

1. **Inventory the package.** List every file in the argument (or the folder). For each, record type (memo, deck, workbook, PDF export), the run date if the file states one, and the file's modified time. A file modified after the general ledger's close time is a candidate for "the current one"; say so, do not assume it.
2. **Extract every quoted figure into the ledger.** One CSV row per figure per file: `file, period, metric, value, location`. `period` is `YYYY-MM` (or `YYYY-Qn`, `YYYY YTD`); `metric` is the name as this engagement uses it (pick one spelling and map the rest: "Adj. EBITDA" and "Adjusted EBITDA" are the same metric, "EBITDA" and "Adjusted EBITDA" are not); `value` as printed, `$1.2M` and `(450)` are fine; `location` is the page, slide or cell so the reader can go straight to it. Read workbooks with the cell, not the chart. Read PDFs and decks page by page; a figure in a footnote counts.
3. **Run the kit.**

   ```bash
   python3 ~/.claude/skills/report-tieout/scripts/report_tieout.py ledger.csv --metric "Consolidated EBITDA" --tolerance 500
   ```

   Tolerance is the rounding the reports themselves use: $1 for a workbook, $500 when the deck rounds to the nearest thousand, $50,000 when it rounds to the nearest $0.1M. Run once per metric that matters, or with no `--metric` for all of them.
4. **Decide which is right, per disagreement.** For every period the kit flags, name the source of truth (the GL export or the model that feeds the reports), state its figure, and mark each report as current or stale against it. The kit finds the spread; only a person with the ledger open says which end is correct.
5. **Write the tie-out note.** One page: the matrix from the kit (period by file), the disagreements with the ruling for each, the files that must be re-run and the figure they must show, and the files that are clean. If every period ties, the note is three lines and the matrix.

## Rules

- **Every figure in the package goes in the ledger**, including the ones you expect to match. A report that quotes EBITDA for eight months and not the ninth is a finding (`missing`), because the reader will assume the ninth exists.
- **Never edit a client report to make it tie.** The note says what to re-run; the model owner re-runs it. Re-issuing a shared file follows `product-costing-revision`.
- **Name the metric the way the client does** and keep the mapping you used in the note, so the next month's run reuses it.
- **A tie within tolerance is a tie.** Do not report a $12 spread on a deck rounded to thousands as a finding; do report it if the workbook shows it.

## Output

`ledger.csv` beside the package (dated, `tieout-ledger-YYYY-MM-DD.csv`), the kit's output pasted into the note, and the note itself, in the `comms-client-status-update` voice when it goes to the client and plain when it stays internal.
