---
name: review-numbers
description: "Reference loaded by a department's reviewer, not for a user request: the numbers checklist for a package before it leaves (results memo, board deck, lender package, variance report, forecast, schedule). Every quoted figure is re-derived from the sources, sums and offsets tested, the same figure checked across documents with report-tieout, and every movement since the prior version listed, returned as a findings list by severity with what was not checked. Not for qualitative claims (review-facts); for a quick cross-report figure match alone, report-tieout."
---

# Review: numbers

The checklist a department's `<department>-reviewer` is briefed with for the last read before a reporting package goes out: every number the sources do not support, every internal sum that does not add, every place where two documents in the package quote the same thing differently. The cross-document half runs the `report-tieout` command from the `report-tieout` skill, which every department holding this skill also holds; the reviewer is granted `Bash(report-tieout:*)` for it. The job's own check section may add lines; where it does, it wins.

## Inputs

- **The artifacts under review** (required): files or a folder. Read all of them, fully.
- **The sources** (required): the trial balance or ledger export, the model, the schedules, the subledger detail, the prior period's actuals: whatever the figures should come from.
- **The prior version of the package** (optional).
- **A scratch directory** (optional): the one place the ledger CSV may be written, and only when the reviewer has been granted a write there. A read-only reviewer has none.
- **A materiality threshold and each document's rounding** (optional). Absent those, use the rounding each document displays and say what you assumed.

Never the maker's reasoning. If the brief explains why a figure is what it is, set the explanation aside and say so under Assumptions: a number that survives only because someone explained it has not been checked. The sources win over the artifacts; where two documents disagree, the source says which end is right.

## The checks

Work through them in order, over every file given.

1. **Inventory.** List every file: type (memo, deck, workbook, PDF export), the run date it states, and its modified time. A file modified after the ledger's close time is a candidate for the current one; say so, do not assume it.
2. **Extract every quoted figure into the ledger.** One row per figure per file: `file, period, metric, value, location`. `period` is `YYYY-MM`, `YYYY-Qn` or `YYYY YTD`. `metric` is the name this engagement uses, one spelling chosen and the rest mapped to it, with the mapping recorded ("Adj. EBITDA" and "Adjusted EBITDA" are one metric; "EBITDA" and "Adjusted EBITDA" are not). `value` as printed (`$1.2M` and `(450)` are both fine). `location` is the page, slide or cell. Every figure goes in, including the ones expected to match; a metric quoted for eight months and not the ninth is a finding. Read a workbook at the cell, not the chart; a deck or PDF page by page, footnotes included.
3. **Re-derive.** For each figure, produce it yourself from the source: not "does the source contain this number" but "does the source produce it". Name the derivation in one line (accounts, periods, filter, sign convention). A figure you cannot derive is a finding, whether or not it looks right.
4. **Arithmetic inside each document.**
   - Every subtotal is the sum of its parts and every total the sum of its subtotals.
   - A variance equals actual minus the comparison, its sign consistent down the page and in the direction the heading claims.
   - A percentage equals its numerator over the denominator its label names, at the precision shown.
   - A bridge or waterfall starts at the stated opening figure and its steps sum to the stated closing figure.
   - Offsetting entries offset: a reclass moves the same amount out and in; an accrual and its reversal are equal and opposite.
   - A total stated twice in one document agrees with itself.
   - Units and scale are consistent; thousands in one table and units in the next is a finding.
   - Periods are what the heading says (a year-to-date of eleven months, a quarter with a thirteenth week, a prior-year column from the wrong year).
5. **Tie the documents to each other.** With a scratch directory, write the ledger there as `tieout-ledger-YYYY-MM-DD.csv` and run `report-tieout <scratch>/tieout-ledger-YYYY-MM-DD.csv --metric "<metric>" --tolerance <n>`, once per metric that matters or with no `--metric` for all. Exit 1 means it found something, which is a result, not an error. Without one, lay the ledger out in your reasoning and compare period by file by hand under the same tolerance, and say so under Assumptions. Tolerance is the rounding the reports use: 1 for a workbook, 500 for a deck rounded to thousands, 50000 for tenths of a million. A tie within tolerance is a tie. For every period that does not tie, go back to the source, name which figure is right, and mark each document current or stale against it.
6. **Diff against the prior version.** List every figure that moved, however small, with both values and the difference; the maker decides what is worth explaining. Say whether the sources explain each move, and flag any sentence the move has made untrue. Also look the other way: a figure that did not move although the source behind it changed.
7. **The report against itself.**
   - Every number quoted in prose matches the table it refers to.
   - Every claim about direction ("down from last month", "ahead of budget") matches the figures.
   - Every reference to a page, exhibit, appendix or footnote resolves.
   - Nothing is labelled draft, placeholder, TBD, XX or highlighted for follow-up.
   - Nothing internal survives into a document going outside: an employee name where a role belongs, a working note, a comment.
   - Dates, period labels and entity names agree across every document, headers, footers and file names included.

Rules that hold throughout: re-derive, never verify; every finding names a source the maker can open; you cannot ask a question, so a figure whose input is missing goes in Not checked with the input named; you edit no artifact and no source; no view on the business, only what the numbers are.

## Verdict

- **PASS** when there is no WRONG, UNSUPPORTED, INCONSISTENT or STALE finding. PRESENTATION findings ride with a PASS unless the label, unit or period would mislead a reader. Not checked figures do not fail by themselves unless the job's check section requires every figure re-derived.
- **FAIL** otherwise. The numbered fixes are the findings below, in the same order.

## Return

The verdict line (`PASS` or `FAIL`) and the counts first, then the findings list, ordered by severity, then by the size of the difference. Nothing else: no summary of the package, no view on whether the numbers are good news, no rewrite. Each finding in this shape:

```
<n>. <SEVERITY> · <document>, <location>
   Quoted:     <the figure as printed>
   Re-derived: <what the source produces>
   Source:     <file, tab, account range, cell or page>
   Derivation: <one line: what you did to get there>
   Note:       <one line where the difference is explained by rounding, scope or timing>
```

Severity is one of **WRONG** (not what the source produces), **UNSUPPORTED** (no source given produces it either way), **INCONSISTENT** (two documents disagree, or a document disagrees with itself), **STALE** (right against an earlier source, wrong against the current one) or **PRESENTATION** (the figure is right; the label, unit, period or reference around it is wrong).

Then, in this order:

- **Ties clean**: the metrics and periods that checked out, as counts.
- **Movements since the prior version**: every one, with both values.
- **Not checked**: every figure you could not re-derive because no source was given, named one by one. Do not let it be empty because you were resourceful.
- **Assumptions**: the metric spellings merged, the tolerances used, the rounding inferred, anything the brief sent that you set aside.

If nothing is wrong, say so in one line and still give Ties clean and Not checked.
