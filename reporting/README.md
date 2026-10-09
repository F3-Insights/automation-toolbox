# Executive Reporting

Reports that leave the building: an executive's weekly update to the leadership team, a monthly board package, the month-end results memo, and a consulting engagement's weekly client update, plus the independent checkers (fact-check, red team, finance review) that every one of them passes before a person sends it. For department heads, finance leads and consultants who report on a cadence and want every figure traced and nothing sent without approval.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `weekly-reporter` | Main-session admin for one executive's weekly report: runs the flow, owns the three gates, hands back Word and PDF | the `report-*` commands |
| `weekly-report-orchestrator` | Runs the weekly report unattended: gates as one numbered list on the owner's task list, then draft, verify, render, keep | Insights Portal (for the task); the `report-*` commands; `comms-confirm` |
| `report-continuity` | Decides which open items from earlier reports this week must answer | none |
| `report-audience-editor` | Applies the leadership test: Keep, Leave out and Misfiled, with a reason each | none |
| `report-writer` | Writes one weekly report in one turn from the inlined digest | none (optional Insights Portal reads) |
| `report-intake` | Turns a direct report's prose update into evidence rows | none |
| `report-harvester` | Builds the evidence ledger from mail and calendar when there is no work tracker | a mail and calendar connector; command `report-collect` |
| `board-package-orchestrator` | Drafts a monthly board package from a finished close, every figure tied out | the `board-package-*` commands; `comms-confirm` |
| `board-package-writer` | Drafts the deck, commentary script, cover email and the figure ledger | commands `board-package-render`, `board-package-figures`, `board-package-tieout`, `powerpoint-handler` |
| `month-end-results-writer` | Writes the month's versioned HTML results memo, figures ledger and QA log | Sage Intacct (commands `trial-balance`, `intacct-gl-detail`, `budget-detail-diff`); command `report-tieout` |
| `client-update-orchestrator` | Drafts one engagement's weekly client update (deck or memo) with a source on every claim | Insights Portal; commands `client-update-check`, `client-update-record`; `comms-confirm` |
| `client-update-reader` | Reads a batch of the week's sources and returns dated, quoted facts | none |
| `client-update-writer` | Writes the client update draft, claims file, review note and proposed context revision | none |
| `fact-check` | Verifies a claim inventory against an assigned half of the sources | none |
| `executive-red-team` | Reads a finished artifact cold as a skeptical executive and grades it with fixes | none |
| `numbers-reviewer` | Re-derives every figure in a reporting package and ties documents to each other | command `report-tieout` |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `report-weekly` | The weekly report method: the role profile interview, then collect, organise, continuity, audience test, three gates, write, verify, render, record; holds the Weekly Highlights house style, the pasteable consolidation prompt and the profile template | its own `report-*` commands; pandoc and LibreOffice for Word and PDF; the setting `portal_mcp_config` for the Portal tier |
| `board-package-workstream` | What a board-package worker does: rules first, the deck spec, the figure ledger | the `board-package-*` commands |
| `month-end-results-report` | The results memo phase of a close, with its format and QA references | Sage Intacct pull; command `report-tieout` |
| `client-update-workstream` | What a client-update worker does: standards, engagement context, source comments, claim shapes | none |
| `comms-client-status-update` | Writing the client status memo, weekly or full length, in a matter-of-fact voice | command `srt-transcript-collapse` for caption files |
| `project-status-deck` | Building, reviewing and revising a client status deck as self-contained HTML | none |
| `numbers-reviewer-method` | The numbers reviewer's seven-step method: inventory, claim ledger, re-derive, arithmetic, tie-out, prior-version diff, the report against itself | command `report-tieout` |

## Settings and other departments

- Owner settings, described in [docs/settings.md](../docs/settings.md): the weekly report's Portal tier and the client update's Portal reads need `portal_mcp_config` (and `portal_server` when the server entry is not `insights-portal`), with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config. `reference_docx` under `[report-weekly]` and under `[client-update-workstream]` names each one's Word reference document (optional; `report_render.py` otherwise builds one with `build_reference_docx.py`). `contexts_dir` under `[board-package-workstream]` or `[client-update-workstream]`, else the top-level key, is where a Context named by its name is found. The weekly report store is a folder the executive names (`--store` or `REPORT_STORE_DIR`); there is no default.
- Environment: the results memo's Sage Intacct pull needs all four of `SAGE_INTACCT_CLIENT_ID`, `SAGE_INTACCT_CLIENT_SECRET`, `SAGE_INTACCT_COMPANY_ID` and `SAGE_INTACCT_API_USER` (accounting's README). pandoc and LibreOffice make the Word and PDF files. The scripts need Python 3.11 or later, with `pyyaml`, `python-pptx`, `openpyxl` and `pypdf`, declared in each script's `# /// script` block.
- Uses by name from other departments: `orchestration-workstream` (software), `comms-confirm` and `portal-write-safety` (productivity), `email-drafter` and `email-checker` (productivity), `unslop` and `unslop-deliverable` and `brand-guide` (marketing), `month-end-workstream`, `month-end-flux`, `report-tieout` and `month-end-orchestrator` (accounting or finance).

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`report-weekly`**
- `report_profile.py`: writes, checks and shows the role profile a weekly report is written from.
- `report_workorder.py`: each week's report as a work order that can be resumed.
- `report_collect.py`: reads one author's week once and writes the evidence ledger.
- `report_organize.py`: sorts the evidence ledger into the profile's categories, in code.
- `report_pack.py`: collects and organises one scope's week in one command.
- `report_ledger.py`: continuity as a ledger: the open items earlier reports left.
- `report_questions.py`: the workers' questions as one numbered list, and the audience editor's lists.
- `report_facts.py`: the report's figures and tables, kept in one facts set.
- `report_verify.py`: checks a drafted report against the pack it was written from.
- `report_render.py`: renders the approved report and its facts into the Word and PDF files.
- `build_reference_docx.py`: builds the Word reference document the report renders through.
- `report_record.py`: keeps the week's record and proposes what later weeks should change.
- `report_weekly_prepare.py`: collects and organises the week before an unattended session.
- `report_weekly_gates.py`: Gates 1 and 2 as one numbered list, and the answers.
- `report_weekly_check.py`: whether the week's leadership report is done, from its files.

**`board-package-workstream`**
- `board_package_pack.py`: gathers one company's board-package period before the session, read only.
- `board_package_figures.py`: lists every figure printed in a board-package file, with where it is.
- `board_package_render.py`: builds a board deck as a new .pptx from a deck spec.
- `board_package_tieout.py`: ties every figure in the package to the closed books.
- `board_package_record.py`: records a review or an owner-approved exception in the period's evidence file.
- `board_package_check.py`: whether the period's board package is done, test by test.

**`client-update-workstream`**
- `client_update_record.py`: records a week's claims, verdicts, reviews and carried items, the only writer of its evidence file.
- `client_update_check.py`: whether the week's client update is drafted and checked, test by test.

The other commands named above live in accounting (`report-tieout` in `report-tieout`; `trial-balance`, `intacct-gl-detail` in `erp-ledger-pull`; `budget-detail-diff` in `month-end-flux`; `month-end-check` in `month-end-workstream`), productivity (`powerpoint-handler` in `office-files`; `find-contact`, `find-email`, `email-draft-show`, `email-deliver` in `comms-reply-to-email`; `outbound-check` in `comms-draft-check`) and process-engineering (`srt-transcript-collapse` in `transcript-tools`).
