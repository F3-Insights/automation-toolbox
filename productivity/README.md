# Personal Productivity

Keeps one person's working week under control: email answered in their voice, follow-ups chased, clerical mail routed, relationships kept warm, meetings prepared and written up, the task stack captured, clarified and reconciled on evidence, the week reviewed, the calendar defended, the CRM kept clean and the month's time accounted for. Almost everything reads and writes through the Insights Portal MCP server. Nothing is ever sent: replies land as drafts, and changes land as change sets the owner approves or a finish step applies. Goal alignment lives in [strategy](../strategy/), the daily plan in [recurring-summaries](../recurring-summaries/).

## The plugin

This folder is a standalone Claude Code plugin named `productivity` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job (or per family of jobs, with a `mode`), one `productivity-worker` and one `productivity-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py productivity`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/productivity --agent productivity:task-steward
```

From Sentinel, an Automation launches a main agent by name and its brief names the mode; the overlay's `subagents:` lists `productivity-worker` and `productivity-reviewer`. Prepare and finish steps still run scripts by path (`{skills_dir}/<skill>/scripts/<script>.py`) until Sentinel puts plugin commands on PATH outside the session.

## Jobs and agents

| Agent | Mode | Automation | What it does |
|---|---|---|---|
| `task-steward` | `capture` | task-capture | Turns said-but-not-seen commitments and quick-capture lines into tasks, never twice |
| | `clarify` | task-clarify | Daily GTD clarify: files, retitles, dates and sets WAITING on open tasks |
| | `reconcile` | task-reconcile | Nightly: closes done, duplicate and dead tasks on evidence; every cancel reviewer-passed |
| `comms-steward` | `follow-up` | follow-up | Chases what the owner is owed and closes what they promised: checked nudges, promise tasks |
| | `clerical` | clerical-routing | Routes clerical mail to the assistant as one batched task a day, once the assistant has agreed |
| | `relationships` | relationship-tending | Weekly outreach drafts to cooling professional contacts, one reason each |
| `meeting-steward` | `prep` | meeting-prep | One checked, findable prep note per external meeting of the day |
| | `transcripts` | meeting-worker | Unprocessed Fellow recordings to Portal notes and tasks, a few per run, written only by `productivity-meeting-publish` |
| `email-replier` | | email-reply | One reply as a checked draft in Outlook Drafts, asking the owner only their decisions |
| `gtd-weekly-review` | | weekly-review | The GTD weekly review as one numbered approval list |
| `calendar-steward` | | calendar-steward | Two weeks of focus blocks, conflict fixes, declines and prep, for approval |
| `crm-hygiene` | | crm-hygiene | Weekly CRM pass: evidenced fixes, approved merges, defect drafts, metrics note |
| `time-study` | | time-study | Where the month's time went, in ten-minute slots with evidence tiers |
| `productivity-worker` | | | One slice a main agent hands it (a batch, a draft, a research pass, a transcript, a day), following the named section |
| `productivity-reviewer` | | | Independent PASS or FAIL against the named checklist section; edits nothing |

Change sets are signed with the agent and mode (`task-steward-reconcile`, `comms-steward-clerical`); `task-stack-apply` maps each to the old orchestrator name so existing markers and records still match.

Departments not yet converted (sales, reporting, learning, projects, recurring-summaries, chief-of-staff, process-engineering) dispatch `productivity-worker` and `productivity-reviewer` with a skill section and its `SKILL.md` path, until they become plugins with their own copies.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `task-stack-workstream` | task-steward, gtd-weekly-review, comms-steward (shared copy) | Task-stack conduct, the change-set contract, checklist Check task-stack ops |
| `task-stack-capture`, `task-stack-clarify`, `task-stack-reconcile` | task-steward | Each mode's Steps; sections Decide a batch, Clarify a batch, Prove a batch |
| `comms-follow-up-workstream`, `comms-clerical-routing-workstream`, `crm-relationship-workstream` | comms-steward | Each mode's rules, Steps and shapes; checklist Check routed threads |
| `comms-draft-check` | reviewer | Checklist The tests, in order, and the outbound gate `productivity-outbound-check` |
| `email-drafter-method`, `email-triager-method`, `waiting-on-tracker-method` | worker | Drafting one email, triaging inbound mail, finding what the owner waits on |
| `comms-reply-to-email` | email-replier | Steps; sections Research the email, Draft the reply, Check a reply |
| `meeting-prep-workstream` | meeting-steward (prep) | Steps; checklist Check a pack |
| `meeting-scheduled-worker` | meeting-steward (transcripts) | Steps; sections Analyse a recording, Check a meeting plan |
| `meeting-analyst-method` | worker | Reading one transcript into a proposed record |
| `portal-research` | worker (shared copy; the source is in `shared/skills/`, also copied to chief-of-staff) | Research a person, Research email history, Research a domain |
| `weekly-review-workstream` | gtd-weekly-review | Steps, the item contract; section Triage a batch |
| `calendar-steward-method` | calendar-steward | Steps; sections Propose the changes, Check the proposals |
| `calendar-time` | projects, strategy, weekly review | Where meeting time went over a period, and how much to one scope |
| `crm-hygiene-workstream` | crm-hygiene | Steps; sections Analyse a slice, Check fixes and merges |
| `report-time-study` | time-study | Steps; sections Segment a recording, Assemble a day, Classify a day's topics, Check sampled slots |
| `comms-follow-ups`, `comms-inbox-replies`, `comms-draft-email`, `comms-log-call` | the owner | Interactive: chase follow-ups, triage and reply, draft a new email, log a call |
| `meeting-prep`, `meeting-followup`, `meeting-log`, `meeting-summary`, `meeting-portal-notes` | the owner | Interactive: prep one meeting, file its follow-up, log it, summarize it, source-check its notes |
| `crm-contact-update`, `crm-data-review`, `crm-context-enrichment` | the owner | Interactive: update a contact, fill data gaps, enrich a thin record |
| `quick-capture` | the owner | Interactive: classify anything captured, link it and file it; tasks go through `task-stack-apply`. Moved here from chief-of-staff on 2026-10-24 |
| `portal-write-safety` (shared copy), `portal-note-types`, `meeting-summary-style-guide` | reference | Portal write rules, note types, summary house style |
| `orchestration-workstream`, `unslop`, `unslop-email` | shared copies | Worker conduct and return block; plain writing |

## Commands

In `bin/`, one per script: `productivity-find-contact`, `-find-email`, `-email-context-pack`, `-email-draft-show`, `-email-deliver`, `-outbound-check`, `-notify-owner`; `-meeting-pending`, `-existing`, `-fetch`, `-validate`, `-publish`, `-acknowledge`, `-skip`; `-prepare-transcript`, `-portal-read`, `-check-evidence` (meeting-portal-notes); `-task-capture-queue`, `-record`, `-check`; `-weekly-review-gather`, `-pack`, `-check`, `-changes`, `-publish`; `-calendar-steward-scan`, `-calendar-apply`, `-calendar-steward-check`, `-calendar-time`; `-portal-issue-file`; `-time-study-collect`, `-tool`, `-day-lint`, `-said-not-seen`, `-check`. The shared copy's commands keep one unprefixed name: `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report`. Each prints `--help`.

Not in this repository: `meeting-summary-to-pdf` (`meeting-summary`) and the `timestudy` program, a separate checkout `productivity-time-study-tool` runs.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Portal**: `portal_mcp_config` (and `portal_server`) for every script that reads or writes the Portal, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- **State**: `state_dir` for the task stack, capture, calendar steward and weekly review. The meeting worker's state is `--state`, else `MEETING_PROCESSING_STATE`, else `state_dir` under `[meeting-scheduled-worker]`, else `<state_dir>/meeting-processing`.
- **Per skill**: `[calendar-steward-method] home`, `daily_plan_state`, `timezone` (also read by `calendar-time`); `[task-stack-workstream] assignable_contacts`, `lead_words`; `[task-stack-capture] sources` or `sources_file`; `[meeting-scheduled-worker] since`, `enrichment_agent`, `relayed_answer_head`; `[crm-hygiene-workstream] portal_issue_repo`, `private_terms`; `[report-time-study] home`, `repo`, `domains_csv`.
- **Runner switches**: `F3I_TOOLBOX_DRY_RUN=1` makes the meeting worker's writes refuse a call without `--dry-run`; `NOTIFY_OWNER_MODE` (`off`, `dry-run`) quiets `productivity-notify-owner`; `GH` names another `gh` for `productivity-portal-issue-file`.
- `voice_guide` is read by the agents, not by a script.
- Python 3.11 or later; `pyyaml` (capture sources), declared in each script's `# /// script` block.
