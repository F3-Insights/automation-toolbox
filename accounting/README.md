# Accounting

The books, close to close: the month-end close run like a controller runs a close team, and the recurring accounting work around it (collections, intercompany, routine coding questions, product costing, vendor 1099s, audit support, and a small firm's own billing and books). For a controller, fractional CFO or close lead who wants agents to prepare the work and prove it, while a person still uploads every journal entry, issues every invoice, sends every message and files every return.

## The plugin

This folder is a standalone Claude Code plugin named `accounting` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) and [productivity](../productivity/README.md) are: one short main agent per job, one `accounting-worker` and one `accounting-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py accounting`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/accounting --agent accounting:accounting-month-end-close
```

From Sentinel, an Automation launches a main agent by name with the plugin directory; the overlay's `subagents:` lists `accounting-worker` and `accounting-reviewer`. Prepare, precheck and finish steps run the same named commands (`accounting-month-end-check`, `month-end-pull`, `accounting-firm-billing-pull`, `task-stack-apply`), which Sentinel puts on PATH for code phases.

Every computed check the old agents had stays a command or a reviewer checklist: `accounting-je-import-check` on every import file, `accounting-month-end-check` and `accounting-firm-billing-check` for done, `accounting-firm-billing-draft --verify` for the billing reviewer's re-derivation, `report-tieout` and the `review-numbers` checklist for every package of figures, `accounting-costmodel-audit` for a costing revision. The reviewer is read-only (decision D5): it returns its note and the main agent writes the review file that `accounting-month-end-record --review-file` and `accounting-firm-billing-record --review-file` record.

## Jobs and agents

| Agent | Automation | What it does | Dispatches |
|---|---|---|---|
| `accounting-month-end-close` | month-end | A company's month-end close from its Month-End folder: workstreams in parallel, every item reviewed, the results memo last, STATUS and LOG kept; done is `accounting-month-end-check` | worker (Cash, AR billing and revenue, Accruals and AP, Set up and Curate a month, flux, the results memo); reviewer (Review an item, Sign off the close on fable, review-numbers on the memo) |
| `accounting-firm-books-close` | firm-books | The firm's own close on the month-end pattern, revenue tied to the firm's billing, owner and tax items set apart | worker (the close sections); reviewer (Review an item, Sign off the close) |
| `accounting-intercompany-reconciliation` | intercompany (one per company) | Every entity pair to zero or a dated, explained item before consolidation; true-ups drafted; a HANDOFF file for the close | worker (Reconcile a batch of pairs); reviewer (Review an item) |
| `accounting-collections-review` | collections (one per company) | Each AR review prepared: every past-due invoice owned with a next action and date, the agenda written | worker (billing completeness, when the close has not proved it); reviewer (review-numbers) |
| `accounting-firm-billing` | firm-billing | The firm's monthly invoices drafted, each tied to BILLING.yaml and the pull, with a cover email; nothing sent; done is `accounting-firm-billing-check` | worker (Prepare contracts); reviewer (Check a draft invoice, Sign off the period on fable) |
| `accounting-questions` | finance-ops (one per company) | Routine coding questions held as Portal tasks answered with the rule cited, as one change set of task comments plus rule proposals | worker (Answer a batch); reviewer (Check an answer) |
| `accounting-audit-support` | audit-support (one per company) | The auditor's request list worked like a close checklist: support indexed, schedules tied, questions by role | worker (Prepare a batch); reviewer (review-numbers, Check the support) |
| `accounting-product-costing-review` | product-costing (one per client) | The per-product standard-versus-actual P&L as a controlled revision tied per factory, and the cost memo | reviewer (review-numbers) |
| `accounting-vendor-1099` | vendor-1099 (one per company) | The W-9 backlog in the fall and the 1099 register at year end; TINs to the last four | worker (Work a vendor batch); reviewer (Check the register, review-numbers) |
| `accounting-worker` | | One slice a main agent hands it, following the named section | none |
| `accounting-reviewer` | | Independent PASS or FAIL against the named checklist section, from the sources alone; edits nothing | none |

Kept separate, though alike: firm-books and the client close share the month-end sections but differ in folder, rules file and ledger source (an export, not the ERP); intercompany has its own rules file and cadence before consolidation; firm billing has its own computed check. The migration plan lists these as merge candidates for later, after the converted jobs have run.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `month-end-close` | month-end close | Steps; the folder, done computed, recording a return, questions; sections Set up a month, Curate a month, Record a learned fact |
| `month-end-workstream` | worker, reviewer, the three close jobs | Close conduct and return block; sections Cash, AR billing and revenue, Accruals and AP; checklists Review an item, Sign off the close |
| `month-end-results-report` | worker | The results memo: format and QA references, section Write the results memo |
| `firm-books-workstream` | firm-books close | Steps; what a firm's own close adds; DONE |
| `intercompany-workstream` | intercompany | Steps; the pair matrix, causes of a difference, the HANDOFF; section Reconcile a batch of pairs |
| `collections-workstream` | collections review | Steps; the register row, disputes, nudges; section Work the aging |
| `firm-billing-workstream` | firm billing | Steps; billing bases, the cover email; sections Prepare contracts, Check a draft invoice, Sign off the period; contract in `BILLING.md` |
| `accounting-questions-workstream` | accounting questions | Steps; the answer shape; sections Answer a batch, Check an answer |
| `transactional-definitions` | accounting questions, the owner | Keeping and applying a client's coding rulebook |
| `audit-support-workstream` | audit support | Steps; request states, building support; sections Prepare a batch, Check the support |
| `product-costing-workstream` | product costing | Steps; sections Build the month, The cost review memo |
| `product-costing-variance`, `product-costing-revision` | product costing, the owner | The per-finished-good P&L pipeline; re-issuing a workbook as a controlled revision |
| `vendor-1099-workstream` | vendor 1099 | Steps; vendor states, the passes; sections Work a vendor batch, Check the register |
| `month-end-accrual-drafts`, `month-end-journal-entry`, `month-end-reconciliation`, `month-end-flux`, `month-end-expectations-brief` | worker, the owner | The close's methods: card and vendor accruals, one journal entry, one reconciliation, the flux, leadership's expectations |
| `erp-ledger-pull` | everyone (shared copy) | Reading the ERP: the pull, trial balance, GL detail, normalizer, AR/AP hygiene, budget detail; the Sage Intacct reference and import layout in `references/` |
| `review-numbers`, `evidence-check` | reviewer (shared copies) | The numbers checklist; the evidence checklist |
| `orchestration-workstream`, `comms-confirm`, `office-files`, `report-tieout`, `task-stack-workstream`, `unslop`, `unslop-email` | shared copies | Worker conduct; questions to people; Excel, PDF and deck reading; the cross-report tie; the change-set contract; plain writing |

A shared copy is never edited here: its source is `shared/skills/<skill>/`, copied by `python3 scripts/build_shared.py`.

## Commands

In `bin/`, one per script, each with `--help`:

- **Close**: `accounting-month-end-check`, `accounting-month-end-record`; `accounting-je-import`, `accounting-je-import-check`; `accounting-cash-walk`; `accounting-gl-sweeps`; `accounting-accruals`, `accounting-card-export`, `accounting-cc-accrual`, `accounting-service-period-accrual`, `accounting-recurring-je-scan`.
- **Firm billing**: `accounting-firm-billing-pull`, `-draft`, `-record`, `-check`, `-deliver`.
- **Product costing**: `accounting-sap-extract-normalize`, `accounting-prodqty-check`, `accounting-routing-rollup`, `accounting-fg-pl-extract`, `accounting-costmodel-audit`.
- **Shared copies** (one unprefixed name in every department that holds the skill): `month-end-pull`, `intacct-snapshot`, `trial-balance`, `intacct-gl-detail`, `gl-normalize`, `ar-ap-hygiene`, `budget-detail-diff` (erp-ledger-pull); `report-tieout`; `confirm`, `confirm-portal`, `waiting` (comms-confirm); `excel-handle`, `pdf-handle`, `powerpoint-handler` (office-files); `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report` (task-stack-workstream).

`accounting-firm-billing-deliver` runs only in the firm-billing Automation's finish step. It places a reviewed cover email in the owner's mail Drafts through productivity's `email_deliver.py`, which it finds in the same toolbox checkout; the session itself never delivers.

Planned and named in the skills, not written yet: `ar-aging-check`, `collections-record`, `intercompany-matrix`, `intercompany-match`, `intercompany-check`, `accounting-questions-queue`, `costing-check`, `firm-books-pull`, `firm-books-check`, `billing-ledger-tie`, `vendor-1099-register`, `w9-scan`, `tin-match-file`, `audit-support-assemble`, `audit-support-check`.

## File contracts with other departments

- **Reporting's board package reads the close.** Its close gate runs `month_end_check.py` (`accounting-month-end-check`) on the Month-End folder with `--format json` and reads `met`, `of` and `tests`; the board package's narrative reads the month's results memo in the report folder and `reporting/results-figures-{yyyy-mm}.csv` (figure, value, source). The command's options and JSON shape, the memo's location and name pattern, and the figures file's columns stay as they are; a change to any of them is a change to reporting's board package too.
- **Finance reads the books through `erp-ledger-pull`.** Its source is `shared/skills/erp-ledger-pull`; finance takes a copy when it converts (`shared/manifest.yaml`). `ar-ap-hygiene` (from collections) and `budget-detail-diff` (from month-end-flux) moved into it so finance gets them without accounting's skills.
- **Productivity's email delivery** is reached only by `accounting-firm-billing-deliver`, in the finish step, through the checkout.
- **The Portal task stack**: `accounting-questions` writes `RUN/changes.json` signed `accounting-questions`; `task-stack-apply` posts the comments after the session.

## Decisions taken in the conversion

The migration plan's open questions for this department, settled by its recommendations:

- `month-end-results-report` moved here from reporting (D10); its writer agent became the worker's section Write the results memo.
- `erp-ledger-pull` became a shared source with `sage-intacct-reference` merged into its `references/`, and `ar_ap_hygiene.py` and `budget_detail_diff.py` moved into it.
- The reviewer is read-only and the main agent writes every review file (D5); the numbers reviewer and the evidence checker became the copied checklists `review-numbers` and `evidence-check`.
- `firm_billing_deliver.py` keeps calling productivity's `email_deliver.py` through the checkout, in the finish step outside the session, rather than copying it.
- Vendor 1099s and audit support stay in accounting (the owner's nine-job list), not compliance.
- No jobs were merged; the plan's merge candidates wait until the converted jobs have run.

## What was renamed

The record of the conversion: each new name, and the old names it replaced.

| Now | Was |
|---|---|
| `accounting-month-end-close` (skill `month-end-close`) | `month-end-orchestrator` |
| `accounting-firm-books-close` | `firm-books-orchestrator` |
| `accounting-intercompany-reconciliation` | `intercompany-orchestrator` |
| `accounting-collections-review` | `collections-orchestrator` |
| `accounting-firm-billing` | `firm-billing-orchestrator` |
| `accounting-questions` (change sets signed `accounting-questions`; `task-stack-apply` maps it to the old name for its markers) | `accounting-questions-orchestrator` |
| `accounting-audit-support` | `audit-support-orchestrator` |
| `accounting-product-costing-review` | `product-costing-orchestrator` |
| `accounting-vendor-1099` | `vendor-1099-orchestrator` |
| `accounting-worker`, `month-end-workstream` sections Cash, AR billing and revenue, Accruals and AP | `month-end-cash`, `month-end-ar-billing-revenue`, `month-end-accruals` |
| `accounting-worker`, `month-end-close` sections Set up a month and Curate a month (Record a learned fact by the main agent) | `month-end-keeper` |
| `accounting-reviewer`, `month-end-workstream` checklists Review an item and Sign off the close | `month-end-reviewer` |
| `accounting-worker`, `month-end-results-report` section Write the results memo | `month-end-results-writer` (reporting) |
| `accounting-worker`, `intercompany-workstream` section Reconcile a batch of pairs | `intercompany-reconciler` |
| the main agent, `collections-workstream` section Work the aging | `collections-analyst` |
| `accounting-worker` and `accounting-reviewer`, `firm-billing-workstream` sections Prepare contracts, Check a draft invoice, Sign off the period | `firm-billing-preparer`, `firm-billing-reviewer` |
| `accounting-worker`, `accounting-questions-workstream` section Answer a batch | `accounting-questions-analyst` |
| `accounting-worker`, `audit-support-workstream` section Prepare a batch | `audit-support-preparer` |
| the main agent, `product-costing-workstream` section Build the month | `product-costing-analyst` |
| `accounting-worker`, `vendor-1099-workstream` section Work a vendor batch | `vendor-1099-analyst` |
| `accounting-reviewer` with `review-numbers`, `evidence-check` | `numbers-reviewer`, `compliance-evidence-checker` (as used here) |
| `erp-ledger-pull`'s `references/sage-intacct.md` and `references/import-format.md` | skill `sage-intacct-reference` |

Old names may still appear in folders people keep (`LOG.md` headings, rules files). No check script parses them.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Sage Intacct** (`month-end-pull --live`, `intacct-snapshot --live`, `intacct-gl-detail`): all four of `SAGE_INTACCT_CLIENT_ID`, `SAGE_INTACCT_CLIENT_SECRET`, `SAGE_INTACCT_COMPANY_ID` and `SAGE_INTACCT_API_USER` are required, from the environment only. The company id and API user may instead be `intacct_company_id` and `intacct_api_user` under `[erp-ledger-pull]`. A sandbox pull reads each name with `_SANDBOX` first.
- **Product costing**: `cost_model_layout` under `[product-costing-workstream]` (or `--layout`) for `accounting-fg-pl-extract` and `accounting-costmodel-audit`; `extract_synonyms` is optional.
- **Firm billing**: its settings live in the billing folder's `BILLING.yaml`, not the settings file. `accounting-firm-billing-deliver` reaches the Portal through `email_deliver.py`, which needs `portal_mcp_config` and the Portal bearer (`INSIGHTS_PORTAL_ASSISTANT_TOKEN`, or a `${VAR}` in the MCP config).
- **Month-End folder**: the close commands read `SYSTEMS.md` and the folder's own settings, not the settings file. `accounting-accruals` finds `je_import.py` and `je_import_check.py` in this checkout; `ACCRUALS_SKILLS_DIR` overrides that for tests.
- Python 3.11 or later for the `erp-ledger-pull` and `product-costing-workstream` scripts, which read the settings file; 3.8 or later for the rest. `openpyxl` (Excel inputs) and `pyyaml` (BILLING.yaml, rules files), declared in each script's `# /// script` block.
