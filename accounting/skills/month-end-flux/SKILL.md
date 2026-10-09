---
name: month-end-flux
description: "Explain a month's results the way a CFO will be asked about them: compare each P&L line and balance-sheet account with budget or forecast and the prior month, explain every variance above the thresholds from the GL detail, and write the material ones into the month's findings file. Use near the end of a close, before the reporting package, or for \"why is X up this month\". Not for product margin against standard (product-costing-variance) or a forecast-to-forecast bridge (forecast-method)."
argument-hint: "[Month-End folder] [period yyyy-mm]"
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/trial_balance.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/intacct_gl_detail.py:*), Bash(python3 ~/.claude/skills/month-end-flux/scripts/budget_detail_diff.py:*), Bash(python3 ~/.claude/skills/month-end-flux/scripts/gl_sweeps.py:*), Bash(python3 ~/.claude/skills/office-files/scripts/excel_handle.py:*)
---

# Flux: explaining the month

A variance is explained when a reader could repeat the explanation to a board member, with the transactions that cause it named. "Timing" and "higher activity" are not explanations unless they name which timing and which activity.

## Inputs

- **Actuals.** The month's trial balance from the ledger pull, with its date. A PRELIMINARY pull gives preliminary flux, so say so at the top of the findings.
- **Budget and forecast.** Where `SYSTEMS.md` says they are, such as a budget in the ERP or a forecast workbook. Use the version the rules name. If there is none, compare with the prior month and the same month last year, and say there is no budget comparison.
- **Prior month.** That month's trial balance.

## Method

Read `references/variance-classification-method.md` in this skill's folder first. It holds:
- calibrating against the prior closed month;
- segmenting revenue by entity first;
- the classification loop (real, timing, mapping, misclassification, needs business input);
- the drill-down tests.

Every variance is provisional until it traces to ledger rows.

## Before explaining: the sweeps

Run `gl-sweeps` over the month's pull (`--help` for its inputs). It catches what a variance table hides:
- accounts running far below their trailing level (a missing accrual looks like a saving);
- negative expense;
- stuck drafts;
- prior-period postings;
- entity imbalance;
- reclass dates;
- duplicates.

Favourable surprises get the same suspicion as unfavourable ones: missing expense masquerades as savings. Each sweep finding is either explained in the findings or handed to the workstream that owns the account as a question.

If the month has an expectations brief (`reporting/EXPECTATIONS-{yyyy-mm}.md`, the `month-end-expectations-brief` skill), reconcile it at the end: what leadership expected and saw is said as such, not re-explained.

## The work

1. **Line up the comparisons.** Group the P&L by the lines the company reports, using `METADATA_FIELDS.md` for the mapping. Compare actual with budget or forecast and with the prior month, in dollars and percent. Compare balance-sheet accounts with the prior month.
2. **Pick what needs explaining.** Use the thresholds in `MONTH-END-RULES.md`. A line past either test is explained. Also explain any line whose sign flipped, and any line that is zero this month but was not last month.
3. **Explain each one** from the GL detail for the line: the largest entries, new vendors or customers, one-time items, entries in the wrong period, accruals that reversed without replacement. Name the JE keys, vendors or customers and amounts. An entry that looks wrong is a finding for the workstream that owns the account, not something to fix here.
4. **Write the findings.** Add the material ones to `reporting/MONTH-END-FINDINGS-{yyyy-mm}.md`:
   - one succinct bullet each: the line, actual against budget or forecast and prior month, and the explanation with the account and amounts;
   - lead with what a reader of the financial report most needs.

   Keep the full table as `reporting/flux-{yyyy-mm}.xlsx` (or `.md`).

## Return

The findings added, anything unexplained (with what was looked at), and anything that looks like an error, with the account it belongs to.
