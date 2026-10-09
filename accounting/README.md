# Accounting

The books, close to close: the month-end close run like a controller runs a close team, and the recurring accounting work around it (collections, intercompany, routine coding questions, product costing, vendor 1099s, audit support, and a small firm's own billing and books). For a controller, fractional CFO or close lead who wants agents to prepare the work and prove it, while a person still uploads every entry and sends every message.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `month-end-orchestrator` | Runs a company's month-end close from its Month-End folder: dispatches the workstreams, keeper and reviewer, keeps STATUS and LOG | commands `month-end-check`, `month-end-record`, `month-end-pull`; Sage Intacct |
| `month-end-keeper` | Sets up, curates and records learned facts in the Month-End folder | none |
| `month-end-cash` | Bank, processor and investment cash reconciliations, cash movement, debt and leases | commands `cash-walk`, `trial-balance`, `je-import` |
| `month-end-ar-billing-revenue` | Billing completeness, revenue and cut-off, deferred revenue, AR and the allowance | commands `ar-ap-hygiene`, `trial-balance`, `je-import` |
| `month-end-accruals` | Card and vendor accruals, accrued expenses, AP, payroll liabilities | commands `card-export`, `cc-accrual`, `service-period-accrual`, `je-import` |
| `month-end-reviewer` | Independent PASS or FAIL on each entry, reconciliation and finding, and the close sign-off | commands `je-import-check`, `report-tieout` |
| `collections-orchestrator` | Prepares each AR and collections review: every past-due invoice owned with a next action | Insights Portal |
| `collections-analyst` | Pulls the aging and works each past-due invoice into a register row | Insights Portal; Sage Intacct; command `ar-ap-hygiene` |
| `intercompany-orchestrator` | Reconciles intercompany balances to zero each month before consolidation | none |
| `intercompany-reconciler` | Ties each entity pair, traces differences, drafts true-ups | commands `intacct-gl-detail`, `je-import` |
| `accounting-questions-orchestrator` | Answers routine accounting questions held as Portal tasks, with the rule cited | Insights Portal |
| `accounting-questions-analyst` | Answers one batch of questions from the transactional definitions and ledger history | Insights Portal; command `intacct-gl-detail` |
| `product-costing-orchestrator` | Runs a manufacturer's monthly product-costing review | none |
| `product-costing-analyst` | Builds or refreshes the per-finished-good P&L as a controlled revision, drafts the memo | commands `fg-pl-extract`, `sap-extract-normalize`, `prodqty-check`, `routing-rollup`, `costmodel-audit` |
| `firm-billing-orchestrator` | Drafts a small firm's monthly client invoices, each tied to its rate basis and reviewed | commands `firm-billing-pull`, `firm-billing-draft`, `firm-billing-record`, `firm-billing-check` |
| `firm-billing-preparer` | Drafts the invoices and cover emails for its contracts | command `firm-billing-draft` |
| `firm-billing-reviewer` | Independent PASS or FAIL on each draft invoice | command `firm-billing-draft` |
| `firm-books-orchestrator` | Closes a small firm's own books on the month-end pattern | none |
| `vendor-1099-orchestrator` | Works the W-9 backlog in the fall and builds the 1099 register at year end | none |
| `vendor-1099-analyst` | Decides each vendor's 1099 state and box, drafts W-9 requests | command `intacct-gl-detail` |
| `audit-support-orchestrator` | Works the auditor's request list (PBC) like a close checklist | Insights Portal |
| `audit-support-preparer` | Answers one batch of requests from finished close work | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `month-end-workstream` | Conduct and return block shared by every month-end workstream | none |
| `month-end-accrual-drafts` | Drafts the card and post-cutoff vendor accruals, with a missing-accrual scan | Python 3.8+; commands `card-export`, `cc-accrual`, `service-period-accrual`, `je-import`, `je-import-check` |
| `month-end-journal-entry` | Prepares one journal entry: import file, backup, lint, booked test | commands `je-import`, `je-import-check` |
| `month-end-reconciliation` | Reconciles one balance-sheet account | command `trial-balance` |
| `month-end-flux` | Explains the month's variances from the GL detail | commands `trial-balance`, `gl-sweeps`, `budget-detail-diff` |
| `month-end-expectations-brief` | Collects leadership's expectations and reconciles them to the month | none |
| `erp-ledger-pull` | Reads what the ERP holds for a period, read only | Sage Intacct; commands `month-end-pull`, `trial-balance`, `gl-normalize` |
| `sage-intacct-reference` | How the Sage Intacct API behaves, and the import CSV layout | none |
| `report-tieout` | Checks a package of reports quote the same figures | command `report-tieout` |
| `collections-workstream` | Collections: the AR register row, disputes, nudges, the review agenda | none |
| `intercompany-workstream` | Intercompany: the pair matrix, causes of a difference, true-ups | none |
| `accounting-questions-workstream` | Routine accounting questions: intake, answer shape, done | none |
| `transactional-definitions` | Keeps and applies a client's coding rulebook | none |
| `product-costing-workstream` | The monthly product-costing review: folder, pack, done | none |
| `product-costing-variance` | Standard-versus-actual P&L per finished good, tied to the TB per factory | commands `fg-pl-extract`, `costmodel-audit` |
| `product-costing-revision` | Re-issues a workbook the client has seen as a controlled revision | commands `costmodel-audit`, `sha256sum` |
| `firm-billing-workstream` | Firm billing: BILLING.yaml, the pull, lines files, states (contract in `BILLING.md`) | firm-billing commands |
| `firm-books-workstream` | What a small firm's own close adds to the month-end pattern | none |
| `vendor-1099-workstream` | Vendor states, complete W-9s, TINs to last four, the two passes | none |
| `audit-support-workstream` | Request states, support indexes, done for audit support | none |

Several pieces load skills from other departments by name: `orchestration-workstream` (software), `comms-confirm` and `task-stack-workstream` (productivity), `unslop-email` (marketing), `numbers-reviewer`, `month-end-results-writer` and `month-end-results-report` (reporting), `compliance-evidence-checker` (compliance) and `comms-client-status-update`.

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`erp-ledger-pull`**
- `month_end_pull.py`: refreshes one month's read-only ledger pull in a Month-End folder.
- `intacct_snapshot.py`: pulls a period and a trailing baseline from Sage Intacct into JSON snapshots.
- `intacct_gl_detail.py`: GL detail for one account and date range from Sage Intacct, read only.
- `trial_balance.py`: a trial balance as of a date, computed from posted GL lines.
- `gl_normalize.py`: maps another accounting system's exports onto the standard ledger shape.

**`month-end-workstream`**
- `month_end_check.py`: whether the month's close is done, computed from the Month-End folder.
- `month_end_record.py`: records one row of the close evidence file, the only writer of it.

**`month-end-journal-entry`**
- `je_import.py`: builds and lints the Sage Intacct journal-entry import CSV from proposed entries.
- `je_import_check.py`: lints an import CSV already on disk, as a person will upload it.

**`month-end-reconciliation`**
- `cash_walk.py`: classifies a month's cash movements by the account on the other side.

**`month-end-flux`**
- `gl_sweeps.py`: ten detection sweeps over the month's GL; each flags, a person confirms.
- `budget_detail_diff.py`: compares Intacct's budget detail with the upload sheet and finds the freshest forecast.

**`month-end-accrual-drafts`**
- `accruals.py`: drafts the month's card and post-cutoff vendor accruals from a Month-End folder.
- `card_export.py`: turns a bank's card download (xlsx) into the period's card CSV.
- `cc_accrual.py`: codes a month of card transactions into a reversing accrual entry, queuing what it cannot code.
- `service_period_accrual.py`: drafts the post-cutoff vendor accrual from next month's bills and arrears estimates.
- `recurring_je_scan.py`: checks every ratified standard monthly entry is in the period's ledger.

**`collections-workstream`**
- `ar_ap_hygiene.py`: sanity checks over a folder of AR and AP snapshots, read only.

**`report-tieout`**
- `report_tieout.py`: checks a set of reports quote the same figure for the same metric and period.

**`product-costing-workstream`**
- `sap_extract_normalize.py`: turns a recurring SAP CO/PP extract into one long table with provenance.
- `prodqty_check.py`: sanity checks on production and sales quantities before they enter a cost model.
- `routing_rollup.py`: routing minutes per finished good, its own and its components', by factory.
- `fg_pl_extract.py`: reads a per-finished-good P&L workbook into long tables and ties revenue to the TB.
- `costmodel_audit.py`: audits a cost model workbook (ties, margins, month references) without editing it.

**`firm-billing-workstream`**
- `firm_billing_pull.py`: computes what each contract owes for the period from BILLING.yaml, issued invoices and time records.
- `firm_billing_draft.py`: writes one contract's draft invoice from a lines file, or verifies a draft.
- `firm_billing_record.py`: records one contract's billing state, the only writer of the evidence file.
- `firm_billing_check.py`: whether the period's billing is done, computed from the files.
- `firm_billing_deliver.py`: places reviewed cover emails in the owner's mail Drafts folder through `email_deliver.py` in `comms-reply-to-email` (productivity); never sends.

`excel_handle.py` and `pdf_handle.py` (`excel-handle`, `pdf-handle`) live in `office-files`, and `task_stack_apply.py` (`task-stack-apply`) in `task-stack-workstream`, both in productivity.

Planned and named in the skills, not written yet: `ar-aging-check`, `collections-record`, `intercompany-matrix`, `intercompany-match`, `intercompany-check`, `accounting-questions-queue`, `costing-check`, `firm-books-pull`, `firm-books-check`, `billing-ledger-tie`, `vendor-1099-register`, `w9-scan`, `tin-match-file`, `audit-support-assemble`, `audit-support-check`, `work-record`, `work-check`.

### Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Sage Intacct** (`month_end_pull.py --live`, `intacct_snapshot.py --live`, `intacct_gl_detail.py`): all four of `SAGE_INTACCT_CLIENT_ID`, `SAGE_INTACCT_CLIENT_SECRET`, `SAGE_INTACCT_COMPANY_ID` and `SAGE_INTACCT_API_USER` are required, from the environment only. The company id and API user may instead be `intacct_company_id` and `intacct_api_user` under `[erp-ledger-pull]`. A sandbox pull reads each name with `_SANDBOX` first.
- **Product costing**: `cost_model_layout` under `[product-costing-workstream]` (or `--layout`) for `fg_pl_extract.py` and `costmodel_audit.py`; `extract_synonyms` is optional.
- **Firm billing**: its settings live in the billing folder's `BILLING.yaml`, not the settings file. `firm_billing_deliver.py` reaches the Portal through `email_deliver.py`, which needs `portal_mcp_config` and the Portal bearer (`INSIGHTS_PORTAL_ASSISTANT_TOKEN`, or a `${VAR}` in the MCP config).
- **Month-End folder**: the close scripts read `SYSTEMS.md` and the folder's own settings, not the settings file. `ACCRUALS_SKILLS_DIR` moves where `accruals.py` looks for the other skills' scripts (default `~/.claude/skills`).
- Python 3.11 or later for the `erp-ledger-pull` and `product-costing-workstream` scripts, which read the settings file; 3.8 or later for the rest. `openpyxl` (Excel inputs) and `pyyaml` (BILLING.yaml, rules files), declared in each script's `# /// script` block.
