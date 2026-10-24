# Executive Reporting

Reports that leave the building: an executive's weekly update to the leadership team, a company's monthly board package, and a consulting engagement's weekly client update. Every one is drafted from sourced facts, checked by a reviewer that never sees the maker's reasoning, and handed to a person who sends it. For department heads, finance leads and consultants who report on a cadence and want every figure traced and nothing sent without approval.

## The plugin

This folder is a standalone Claude Code plugin named `reporting` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job, one `reporting-worker` and one `reporting-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py reporting`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/reporting --agent reporting:weekly-reporter
```

From Sentinel, an Automation launches a main agent by name; the overlay's `subagents:` lists `reporting-worker` and `reporting-reviewer`.

## Jobs and agents

| Agent | Automation | What it does |
|---|---|---|
| `reporting-board-package` | board-package (one per company) | One company's monthly board deck, commentary script and cover email from the finished close; every figure tied to the results file or the closed trial balance, re-derived and read cold by the reviewer; one review task. Nothing is sent or uploaded |
| `reporting-client-update` | client-weekly-update (one per engagement) | One engagement's weekly client update, a status deck or a Word memo with cover email: workers read the sources in batches, every claim sourced, two fact-checks over disjoint halves, a cold read as the client, the cover email staged and checked; the finish step puts a checked cover email in Outlook Drafts. Nothing is sent |
| `reporting-weekly-report` | report-weekly-collect (Thursday), report-weekly-assemble (Friday) | The leadership weekly unattended, one job in two phases: collect judges the week and puts Gates 1 and 2 on the owner's task list; assemble applies the answers or defaults, writes, verifies, renders and asks for approval; an approved week is kept |
| `weekly-reporter` | none (interactive) | The same weekly flow with the executive present, started as the main session; asks the gates live |
| `reporting-worker` | | One slice: a batch of client-update sources, the cover email staged, or one weekly-report worker prompt (intake, harvester, continuity, audience editor, writer) |
| `reporting-reviewer` | | Independent check against the named checklist section; edits nothing |
| `fact-check`, `numbers-reviewer`, `executive-red-team` | | Kept only while other departments' agents still dispatch them by name; no reporting job uses them. Their checklists are `review-facts`, `review-numbers` and `review-red-team`, which `reporting-reviewer` follows |

Both client updates are one job on a different engagement, so they share one main agent. The weekly report's two Automations are one job in two phases (the owner answers the gates between them), so they share one main agent with the phase as an input.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `board-package-workstream` | reporting-board-package | Steps; Done is computed; the close gate and results-file contracts; sections Draft the package, The deck spec, The figure ledger; checklists Check the numbers, Read the deck cold |
| `client-update-workstream` | reporting-client-update | Steps; the standards, the engagement context and its proposed revision; sections Read a batch, Write the update, Stage the cover email; checklists Check the facts, Read the update cold, Check the cover email |
| `report-weekly` | reporting-weekly-report, weekly-reporter | Steps (both phases), the Stages in detail, `unattended.md`, the gates, the five worker prompts in `workers/`, the house style; checklist Check the draft |
| `comms-client-status-update` | the client update's memo; the owner | The client status memo, weekly or full length, in a matter-of-fact voice |
| `project-status-deck` | the client update's deck; the owner | Building, reviewing and revising a client status deck as self-contained HTML |
| `review-facts`, `review-numbers`, `review-red-team` | reviewer (shared copies) | The fact, numbers and cold-read checklists |
| `orchestration-workstream`, `comms-confirm`, `office-files`, `report-tieout`, `unslop`, `unslop-deliverable`, `brand-guide` | shared copies | Worker conduct; questions to the owner as tasks; reading decks and workbooks; cross-document tie-out; plain writing; the house brand |

## Commands

In `bin/`, one per script, each printing `--help`:

- **report-weekly**: `reporting-report-profile`, `-report-workorder`, `-report-collect`, `-report-organize`, `-report-pack`, `-report-ledger`, `-report-questions`, `-report-facts`, `-report-verify`, `-report-render`, `-report-record`, `-build-reference-docx`, and for the unattended run `reporting-report-weekly-prepare`, `-report-weekly-gates`, `-report-weekly-check`. The scripts keep their `report_*.py` names (projects' delivery pack and the client update's pack call `report_collect.py` by file name), so the commands carry `report` twice.
- **board-package-workstream**: `reporting-board-package-pack`, `-check`, `-figures`, `-render`, `-tieout`, `-record`.
- **client-update-workstream**: `reporting-client-update-pack`, `-check`, `-record`, `-deliver`, `-draft-show`.
- **Shared copies** keep one unprefixed name: `confirm`, `confirm-portal`, `waiting` (comms-confirm), `report-tieout`, `powerpoint-handler`, `excel-handle`, `pdf-handle`.

## Contracts with other departments

- **Accounting's close (board package).** The `month-end-check` Close gate runs accounting's command `accounting-month-end-check <close folder> --period P --format json` (on PATH, else accounting's script in this toolbox checkout) and reads `done`, `met` and the tests not met. The **results file**, the month's results memo accounting's close writes, is read by its glob in `BOARD-RULES.md` and never written here. The results memo itself (`month-end-results-report` and its writer) moved to accounting.
- **Productivity's email delivery (client update).** The finish step `reporting-client-update-deliver` puts the checked cover email in Outlook Drafts through comms-reply-to-email's `email_deliver.py`, and the reviewer reads the staged draft's content hash through `reporting-client-update-draft-show`, which runs comms-reply-to-email's `email_draft_show.py`. Both find productivity's script in this toolbox checkout, so the hash the reviewer records is the one delivery compares.
- **Projects** reads `report_collect.py` from `report-weekly` for its delivery pack (unchanged).
- **Finance's investor posting** reads the board package's files; it names no reporting skill.

## Settings and environment

- Owner settings, described in [docs/settings.md](../docs/settings.md): the weekly report's Portal tier, the client update's Portal reads and its cover-email commands need `portal_mcp_config` (and `portal_server` when the server entry is not `insights-portal`), with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config. `reference_docx` under `[report-weekly]` and under `[client-update-workstream]` names each one's Word reference document (optional). `contexts_dir` under `[board-package-workstream]` or `[client-update-workstream]`, else the top-level key, is where a Context named by its name is found. The weekly report store is a folder the executive names (`--store` or `REPORT_STORE_DIR`); there is no default.
- A harvester-tier author (no Portal, mail and calendar through a connector) adds that connector's read tools to `reporting-worker`'s `tools:` on their machine; the toolbox names none.
- pandoc and LibreOffice make the Word and PDF files. The scripts need Python 3.11 or later, with `pyyaml`, `python-pptx`, `openpyxl` and `pypdf`, declared in each script's `# /// script` block.

## What changed in the plugin conversion (2026-10-23)

| Was | Now |
|---|---|
| board-package-orchestrator | `reporting-board-package` |
| board-package-writer | section Draft the package of `board-package-workstream`, run by the main agent |
| client-update-orchestrator | `reporting-client-update` |
| client-update-reader | section Read a batch, run by `reporting-worker` |
| client-update-writer | section Write the update, run by the main agent |
| weekly-report-orchestrator | `reporting-weekly-report` |
| report-continuity, report-audience-editor, report-writer, report-intake, report-harvester | `reporting-worker`, briefed with `report-weekly`'s `workers/<name>.md` |
| fact-check, numbers-reviewer, executive-red-team (for reporting's jobs) | `reporting-reviewer` with `review-facts`, `review-numbers`, `review-red-team` |
| numbers-reviewer-method | merged into `review-numbers` |
| month-end-results-writer, month-end-results-report | moved to accounting |
| productivity's worker and reviewer for the cover email | sections Stage the cover email and Check the cover email |
| scripts run by their path in the shared skills folder | the named commands above |

Decided in the conversion, by the migration plan's recommendations:

- `weekly-reporter` stays its own interactive main agent (not folded into `reporting-weekly-report` as a mode): it is started by hand and must ask live.
- The weekly report keeps its five worker prompts as files in `workers/`, which `reporting-worker` is pointed at; a runtime without sub-agents still runs them inline.
- The weekly report stages no covering email in either mode: the writer's covering note goes to the executive, who sends the report from their own mail.
- The engagement-context sections stay in `client-update-workstream` (no shared `engagement-context` skill yet); the memo skill reads caption files directly (no `transcript-tools` copy).
- `reporting-reviewer` is read-only (plan D5); with `review-numbers` it runs `report-tieout` on the tie-out ledger the main agent's tie-out wrote.
- The board package stays in reporting; its only accounting couplings are the close-gate command and the results file above.
