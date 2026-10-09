---
name: month-end-reconciliation
description: "Reconcile one balance-sheet account for a month-end close: the GL balance from the ledger pull, the support balance from its source document, each reconciling item explained and dated, the difference within tolerance, rolled forward from last month, saved as the final reconciliation in the month folder. Use for any account a close must prove (cash, AR, prepaids, accruals, deferred revenue, debt) or \"does account N reconcile\". For intercompany pairs, start intercompany-orchestrator."
argument-hint: "[Month-End folder] [period yyyy-mm] [account]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/trial_balance.py:*), Bash(python3 ~/.claude/skills/erp-ledger-pull/scripts/intacct_gl_detail.py:*), Bash(python3 ~/.claude/skills/office-files/scripts/excel_handle.py:*), Bash(python3 ~/.claude/skills/office-files/scripts/pdf_handle.py:*)
---

# Reconciling a balance-sheet account

A reconciliation proves that the GL balance is what it should be by tying it to something outside the GL: a bank statement, a subledger aging, a schedule, a contract, a third party's statement. A list of the GL's own transactions is not support.

## Before starting

- **Already reconciled?** Look in the period's `reconciliations/` folder and where `SYSTEMS.md` says the company keeps its own reconciliation workbooks. If a person has reconciled the account, check that their file ties to the ledger pull. Record it as the evidence and stop.
- **Last month.** Open the prior month's reconciliation. This month starts from its closing balance and its open reconciling items.

## The reconciliation

1. **GL balance.** From the ledger pull's trial balance at the period's last day, with the pull date. The balance must match the trial balance exactly; a mismatch means the pull is stale, so refresh it.
2. **Support balance.** From the source document, quoted with its name, date and the line it came from. When the support is a schedule (prepaid amortization, deferred revenue, a loan), roll it forward: opening, additions, releases, closing. Each line traces to an invoice, contract or entry.
3. **Reconciling items.** Each difference between the two, listed with:
   - date and amount;
   - what it is;
   - why it is a timing difference or an error;
   - what clears it (a deposit in transit clears on the next statement; an error needs an entry).

   An item older than the rules' stale limit needs a reason it is still valid.
4. **Difference.** GL balance less support balance less reconciling items. Zero, or within the tolerance in `MONTH-END-RULES.md`. An unexplained difference is never plugged. It is a finding and a question.
5. **Entries.** A correction or adjustment the reconciliation shows is drafted through the `month-end-journal-entry` skill and listed in the reconciliation as proposed, with the balance after it.

## The file

Save it in `reconciliations/` as `{account} {account name} recon {yyyy-mm}.xlsx` (or `.md` for a simple account). When the company keeps its own workbook for the account, roll that workbook forward as a new file for the month in the same layout, and leave the original alone.

At the top of the file:
- the account;
- the GL balance and pull date;
- the support balance and source;
- total reconciling items;
- the difference;
- prepared by and when;
- the state: draft, or final once the reviewer has passed it.

Then the reconciling items, then the roll-forward or the detail behind the support balance.
