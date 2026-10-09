---
name: numbers-reviewer-method
description: "Reference loaded by the numbers-reviewer agent, not for a user request: the step-by-step method for an independent numbers review of a reporting package, from the inventory and the claim ledger of every quoted figure, through re-deriving each figure from its source, the arithmetic inside each document, the cross-document tie-out with report-tieout, the diff against the prior version, to the report checked against itself. Not for a quick cross-report figure match alone; use report-tieout. Not for qualitative claims; use the fact-check agent."
---

# The numbers review, step by step

This is the method the `numbers-reviewer` agent works through, in order, over a reporting package. The agent file holds the goal, the judgment, the tool rules, the boundaries and the exact findings format; this skill holds the steps. The cross-document half (step 5) runs the `report-tieout` skill's script.

## Method

### 1. Inventory

List every file you were given: type (memo, deck, workbook, PDF export), the run date the file states if any, and its modified time. A file modified after the general ledger's close time is a candidate for being the current one. Say so; do not assume it.

### 2. Extract every quoted figure into the ledger

One CSV row per figure per file: `file, period, metric, value, location`. `period` is `YYYY-MM`, `YYYY-Qn` or `YYYY YTD`. `metric` is the name this engagement uses, with one spelling chosen and the rest mapped to it, and the mapping recorded in your report. "Adj. EBITDA" and "Adjusted EBITDA" are the same metric; "EBITDA" and "Adjusted EBITDA" are not. `value` as printed, so `$1.2M` and `(450)` are both fine. `location` is the page, slide or cell, so the author can go straight to it.

Every figure goes in, including the ones you expect to match. A report that quotes a metric for eight months and not the ninth is a finding, because the reader will assume the ninth exists. Read a workbook at the cell, not at the chart. Read a deck or a PDF page by page; a figure in a footnote counts.

### 3. Re-derive

For each figure, go to the source and derive it yourself. Not "does the source contain this number" but "does the source produce this number". Name the derivation in one line: which accounts, which periods, which filter, which sign convention.

A figure you cannot derive is a finding, whether or not it looks right.

### 4. Check the arithmetic inside each document

- Every subtotal equals the sum of its parts, and every total equals the sum of its subtotals.
- A variance column equals actual minus the comparison, with the sign consistent down the page and the same direction as the column heading claims.
- A percentage equals its numerator over its denominator, at the precision shown, and the denominator is the one the label names.
- A bridge or waterfall starts at the stated opening figure, and the steps sum to the stated closing figure.
- Offsetting entries offset: a reclass moves the same amount out of one line and into another, and an accrual and its reversal are equal and opposite.
- A total that is stated in two places in the same document agrees with itself.
- Units and scale are consistent: thousands in one table and units in the next is a finding, not a formatting preference.
- Periods are what the heading says: a year-to-date column that covers eleven months, a quarter that includes a thirteenth week, a prior-year column drawn from the wrong year.

### 5. Tie the documents to each other

Run the kit on the ledger:

```bash
python3 ~/.claude/skills/report-tieout/scripts/report_tieout.py <scratch>/tieout-ledger-YYYY-MM-DD.csv --metric "<metric>" --tolerance <n>
```

Tolerance is the rounding the reports themselves use: 1 for a workbook, 500 when a deck rounds to the nearest thousand, 50000 when it rounds to the nearest tenth of a million. Run once per metric that matters, or with no `--metric` for all of them. It exits 1 when it finds something, which is a result and not an error.

A tie within tolerance is a tie. Do not raise a spread of twelve dollars on a deck rounded to thousands; do raise it if the workbook shows it. For every period the kit flags, name which figure is right by going back to the source, and mark each document current or stale against it. The kit finds the spread. Only you, with the source open, say which end is correct.

### 6. Diff against the prior version

Where a prior version exists, list every figure that moved, however small, with both values and the difference. State every movement rather than filtering by materiality: the author decides what is worth explaining, and a small unexplained move is often the interesting one. Then say, for each move, whether the sources explain it, and flag any narrative sentence the movement has made untrue.

Also check the other direction: a figure that did **not** move but should have, because the source behind it changed.

### 7. Check the report against itself

- Every number quoted in prose matches the table it refers to.
- Every narrative claim about direction ("down from last month", "ahead of budget") matches the figures on the page.
- Every reference to a page, exhibit, appendix or footnote resolves.
- Nothing is labelled draft, placeholder, TBD, XX or highlighted for follow-up.
- Nothing internal has survived into a document going outside: an employee name where a role belongs, a working note, a process aside, a comment.
- Dates, period labels and entity names are right and consistent across every document in the package, including headers, footers and file names.

Then return the findings list in the agent's output format.
