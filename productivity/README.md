# Personal Productivity

Keeps one person's working week under control: email answered in their voice, meetings prepared and written up, tasks captured, clarified and closed on evidence, the week planned, the calendar defended, relationships tended. Goal alignment moved to [strategy](../strategy/). The daily plan (its orchestrator, planner, closer, the two accomplishment workers and `daily-plan-method`) moved to [recurring-summaries](../recurring-summaries/), beside the nightly sweep. Almost everything here reads and writes through the Insights Portal MCP server. Nothing is ever sent: replies land as drafts and changes land as change sets the owner approves.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `email-reply-orchestrator` | Replies to one person's email by the comms-reply-to-email skill; checked draft to Outlook Drafts, never sends | Insights Portal; commands `find-contact` `find-email` `outbound-check` `email-context-pack` `email-draft-show` `email-deliver` `notify-owner`; setting `state_dir` |
| `comms-follow-up-orchestrator` | Chases what the owner is owed and closes what they owe; checked nudges and promise tasks as a change set | Insights Portal |
| `comms-clerical-routing-orchestrator` | Routes clerical mail to the executive assistant as one batched task a day, once the assistant has agreed | Insights Portal |
| `meeting-prep-orchestrator` | Picks, ranks and preps the day's external meetings, one checked note each, proved findable by search | Insights Portal |
| `meeting-transcript-orchestrator` | Processes unprocessed Fellow transcripts a few per run by the meeting-scheduled-worker skill | Insights Portal; commands `meeting-*` (7) |
| `email-context-researcher` | Writes the sourced brief for one pinned email before it is answered | Insights Portal; command `email-context-pack`; setting `state_dir` |
| `email-drafter` | Writes one email in the owner's voice and stages it as a Portal draft; never sends | Insights Portal; setting `voice_guide` |
| `email-checker` | Independent PASS or FAIL on one reply draft against the brief and answers | command `email-draft-show`; setting `voice_guide` |
| `email-triager` | Classes recent inbound mail REPLY, DELEGATE, FYI or NONE with a context packet per REPLY | Insights Portal |
| `comms-draft-checker` | Independent PASS or FAIL on drafts staged by unattended orchestrators | Insights Portal |
| `comms-routing-checker` | Independent PASS or FAIL on each thread headed to the assistant | Insights Portal |
| `waiting-on-tracker` | Finds what the owner waits on (and, when asked, what they promised), with one next action each | Insights Portal |
| `meeting-prep-checker` | Independent PASS or FAIL on each meeting-prep pack | Insights Portal |
| `meeting-analyst` | Reads one transcript and proposes summary, decisions, actions and attendee matches, each quoted | Insights Portal |
| `meeting-checker` | Independent PASS or FAIL on one meeting plan against its transcript | Insights Portal |
| `person-researcher` | Brief on one person: facts, recent interactions, open items, talking points | Insights Portal |
| `email-researcher` | Email history on a topic, person or company, summarized with a timeline | Insights Portal |
| `domain-researcher` | Briefing on one domain's goals, projects, people, open items and blockers | Insights Portal |
| `task-reconcile-orchestrator` | Nightly pass that closes done, duplicate and dead tasks on evidence, as one change set | Insights Portal, commands `task-stack-check`, `task-stack-apply`, `task-stack-report` |
| `task-clarify-orchestrator` | Daily GTD clarify pass: files, retitles, dates and sets WAITING on open tasks | Insights Portal, commands `task-stack-queue`, `task-stack-apply` |
| `task-capture-orchestrator` | Turns said-but-not-seen commitments and quick-capture lines into tasks, never twice | Insights Portal, commands `task-capture-queue`, `task-stack-apply`, `task-capture-record` |
| `weekly-review-orchestrator` | Prepares the GTD weekly review as one numbered approval list | Insights Portal, commands `weekly-review-gather`, `weekly-review-pack`, `weekly-review-check` |
| `calendar-steward-orchestrator` | Two-week calendar pass: focus blocks, conflict fixes, declines, prep, for approval | Insights Portal, commands `calendar-steward-scan`, `calendar-apply` |
| `crm-relationship-tending-orchestrator` | Weekly outreach drafts to cooling professional contacts; nothing sent | Insights Portal |
| `crm-data-hygiene-orchestrator` | Weekly CRM hygiene: evidenced fixes, approved merges, defect drafts, metrics note | Insights Portal |
| `time-study-orchestrator` | Where the owner's time went, 10-minute slots with evidence tiers, unattended | commands `time-study-*`, the `timestudy` program |
| `task-reconcile-evidence` | Proves a batch of tasks done, duplicate, overtaken or still open | Insights Portal |
| `task-reconcile-checker` | Independent PASS or FAIL on doubtful task-stack changes (reconcile, clarify, capture) | Insights Portal |
| `task-clarify-worker` | Clarifies one batch of tasks into edits or questions | Insights Portal |
| `task-capture-worker` | Decides one batch of captured items: create, exists, skip or ask | Insights Portal |
| `weekly-review-triage` | One review item per overdue, stale, WAITING or someday task | Insights Portal |
| `calendar-steward-analyst` | Proposes the calendar changes and dismisses the rest | Insights Portal |
| `calendar-steward-checker` | Independent PASS or FAIL on each calendar proposal | Insights Portal |
| `crm-hygiene-analyst` | One slice of the CRM: fixes, duplicates, defects, metrics | Insights Portal |
| `crm-hygiene-checker` | Independent PASS or FAIL on CRM fixes and merges | Insights Portal |
| `time-study-meeting-segmenter` | Splits one recorded meeting into topic blocks and commitments | Insights Portal |
| `time-study-day-assembler` | Attributes one day's 144 slots with evidence tiers | command `time-study-day-lint` |
| `time-study-topic-classifier` | A topic for every slot of one day | command `time-study-day-lint` |
| `time-study-checker` | Independent re-derivation of sampled slots | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `comms-reply-to-email` | Replies to one email end to end: pinned ids, sourced brief, owner's decisions only, independent check, Outlook Drafts; never sends | Insights Portal; commands `find-contact` `find-email` `outbound-check` `email-context-pack` `email-draft-show` `email-deliver` `notify-owner`; settings `voice_guide`, `state_dir` |
| `comms-draft-email` | Drafts a new email (one that answers nothing received) in the owner's voice, delivered to Outlook Drafts | Insights Portal; command `outbound-check`; setting `voice_guide` |
| `comms-draft-check` | How a checker passes or fails a staged draft: recipient, duplicates, facts, commitments, the ask, voice, privacy | Insights Portal; setting `voice_guide` |
| `comms-follow-ups` | Interactive: finds what the owner waits on, asks which to chase, drafts approved nudges | Insights Portal; command `outbound-check`; setting `voice_guide` |
| `comms-follow-up-workstream` | The unattended follow-up pass: four lenses, one state per commitment, promise tasks as change-set ops | Insights Portal |
| `comms-inbox-replies` | Triages a batch of inbound mail, asks which to answer, fans out drafters, delivers to Drafts | Insights Portal; command `outbound-check`; setting `voice_guide` |
| `comms-clerical-routing-workstream` | Rules for routing clerical mail to the executive assistant as one task a day | Insights Portal |
| `comms-confirm` | Asks a person to confirm something the work needs, records it, and notices the answer later without a model | Insights Portal; commands `confirm-portal` `find-contact` `notify-owner` |
| `comms-log-call` | Logs a phone call as an activity and a note, and offers follow-up tasks | Insights Portal |
| `meeting-prep` | Prepares one upcoming meeting's context and writes a prep note on the event | Insights Portal |
| `meeting-prep-workstream` | The daily meeting-prep pass: selection, ranking and cap, the pack, done checklist | Insights Portal |
| `meeting-followup` | Turns one meeting's notes or transcript, in any format and with or without a calendar event, into an activity, a note, matched or new contacts and companies, tasks, contact updates and an optional follow-up draft | Insights Portal; setting `voice_guide` |
| `meeting-log` | Logs that a meeting happened, with a note, new contacts and offered tasks | Insights Portal |
| `meeting-summary` | Writes a one-to-two page summary in the house style, renders a PDF, saves it as a note | Insights Portal; command `meeting-summary-to-pdf` |
| `meeting-portal-notes` | Source-checked meeting summary and action catalog, every action quoted to its turn, independently reviewed | Insights Portal |
| `meeting-scheduled-worker` | Processes unprocessed Fellow transcripts a few per run; one failure never stops the run | Insights Portal; commands `meeting-pending` `meeting-existing` `meeting-fetch` `meeting-validate` `meeting-publish` `meeting-acknowledge` `meeting-skip` |
| `email-drafter-method` | Reference: the email-drafter agent's step-by-step procedure, from the voice guide to draft_create and the summary | Insights Portal; setting `voice_guide` |
| `email-triager-method` | Reference: the email-triager agent's step-by-step procedure, from whoami to the context packet per REPLY thread | Insights Portal |
| `meeting-analyst-method` | Reference: the meeting-analyst agent's step-by-step procedure, from the transcript to one line per person | Insights Portal |
| `waiting-on-tracker-method` | Reference: the waiting-on-tracker agent's step-by-step procedure, lenses A to D, grouping and the five next actions | Insights Portal |
| `portal-write-safety` | Reference: the rules before any Portal write (propose first, sync_health, UUIDs, CANCELLED with evidence) | Insights Portal |
| `meeting-summary-style-guide` | Reference: house style for meeting summaries (anonymization modes, structure, length, checklist) | none |
| `portal-note-types` | Reference: the four Portal note types, their structure, content rules and associations | none |
| `task-stack-workstream` | Task-stack conduct and the change-set contract for task-stack-apply | Insights Portal, command `task-stack-apply` |
| `task-stack-clarify` | GTD clarify method for one open task | Insights Portal |
| `task-stack-capture` | Capture method for one committed item | Insights Portal |
| `weekly-review-workstream` | Weekly review item contract, verbs and park | Insights Portal |
| `calendar-steward-method` | What each calendar proposal must satisfy, and the proposal file | Insights Portal, command `calendar-apply` |
| `crm-relationship-workstream` | Weekly relationship pass: who to pick, one reason per pick, drafts, sent count | Insights Portal |
| `crm-hygiene-workstream` | CRM hygiene scope, fix, propose or flag, DONE checklist, CRM hygiene method | Insights Portal |
| `crm-contact-update` | Updates one contact from a one-line instruction, diff first, and always logs an activity | Insights Portal |
| `crm-data-review` | Interactive: walks the owner through contacts, companies and descriptions that are missing, five at a time | Insights Portal |
| `crm-context-enrichment` | How a thin contact or company record is researched from its own evidence, routed to the right field and queued | Insights Portal; setting `enrichment_agent` under `[meeting-scheduled-worker]` |
| `pressure-test-method` | Red-teams one of the owner's systems per run from a rotation ledger: steelman, goal fit, external practice, ranked verdict | Insights Portal; settings `goals_doc`, `playbooks_dir`, `owner_profile`, `rotation_ledger` under `[pressure-test-method]` |
| `task-stack-produce` | Produces one review-ready deliverable for a selected task from a source packet; returns prepared or blocked JSON | none |
| `office-files` | Reads Excel, PDF and PowerPoint files without changing them, and merges PDFs; used by other departments' agents | commands `excel-handle`, `pdf-handle`, `powerpoint-handler` |
| `report-time-study` | Executive time study procedure, mechanics and worker briefs | commands `time-study-*`, the `timestudy` program |

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`comms-reply-to-email`**
- `find_contact.py`: a name or an email address, to the Portal contacts it could mean.
- `find_email.py`: a contact id, to the latest email that person sent the owner.
- `email_context_pack.py`: one email, to the data pack a reply is researched from.
- `email_draft_show.py`: one Portal draft as the checker reads it, with its content hash.
- `email_deliver.py`: puts one checked reply draft in the owner's Outlook Drafts folder; never sends.
- `notify_owner.py`: tells the owner, in their Teams chat with the Portal bot, that something needs them.

**`comms-draft-check`**
- `outbound_check.py`: whether a new draft to this person about this thread may be created now.

**`comms-confirm`**
- `confirm.py`: asks a person to confirm something, records it, and notices the answer (`new`, `check`, `close`, `remind` and others).
- `confirm_portal.py`: the Portal half of `confirm.py`, JSON in and out.
- `waiting.py`: the `## Waiting on` table of an engagement folder's period STATUS.md, for `confirm.py`.

**`meeting-scheduled-worker`**
- `meeting_pending.py`: the stored Fellow recordings still to process, oldest first.
- `meeting_existing.py`: what the Portal already holds for one recording, found by marker.
- `meeting_fetch.py`: one exact recording, its transcript and context, into its folder.
- `meeting_validate.py`: checks a meeting plan against its transcript.
- `meeting_publish.py`: writes one checked plan to the Portal, then acknowledges the recording.
- `meeting_acknowledge.py`: tells the Portal one recording revision is processed.
- `meeting_skip.py`: records why a recording was skipped, or clears it for another try.

**`meeting-portal-notes`**
- `prepare_transcript.py`: keeps a UTF-8 transcript and adds stable line and turn locators.
- `portal_read.py`: reads the Portal through a local client's MCP transport and saves receipts.
- `check_evidence.py`: checks each action's evidence references against the transcript.

**`task-stack-workstream`**
- `task_stack_check.py`: the trust score of the owner's task stack.
- `task_stack_queue.py`: one Run's work queue, from the check's JSON.
- `task_stack_apply.py`: the one writer of the task stack; `--undo LOG` reverses an apply.
- `task_stack_report.py`: the short report of one Run, from its Run folder.

**`task-stack-capture`**
- `task_capture_queue.py`: one capture Run's work, gathered before the session.
- `task_capture_record.py`: records what the Run did with each source item in the capture ledger.
- `task_capture_check.py`: whether capture is done, from the sources and the ledger.

**`calendar-steward-method`**
- `calendar_steward_scan.py`: the read-only two-week calendar scan the steward starts from.
- `calendar_apply.py`: publishes the approval list, makes exactly the approved changes, and undoes them.
- `calendar_steward_check.py`: whether the steward's pass is done.
- `calendar_time.py`: where the owner's meeting time went over a period, and how much belongs to one scope.

**`weekly-review-workstream`**
- `weekly_review_gather.py`: reads the week's facts before the session and picks the pass.
- `weekly_review_pack.py`: checks the session's review and renders the pack.
- `weekly_review_check.py`: whether the week's review is done.

**`crm-hygiene-workstream`**
- `portal_issue_file.py`: files one GitHub issue on the Insights Portal's repository, and only there.

**`report-time-study`**
- `time_study_collect.py`: collects the local signals for every window not yet collected.
- `time_study_tool.py`: runs one command of the separate time-study program against its home folder.
- `time_study_day_lint.py`: checks one day's slots and topics files and counts hours by domain and topic.
- `time_study_said_not_seen.py`: writes a window's said-but-not-seen list as JSON for other orchestrators.
- `time_study_check.py`: whether the time study of a period or window is done, test by test.

**`office-files`**
- `excel_handle.py`: reads an Excel workbook without ever saving it.
- `pdf_handle.py`: reads a PDF's text and comments, or merges PDFs.
- `powerpoint_handler.py`: reads a deck's slide text, speaker notes and pictures.

`project-scoreboard` is `project_scoreboard.py` in `project-landscape` (projects). Not in this repository: `meeting-summary-to-pdf` (`meeting-summary`) and the `timestudy` program, which is a separate checkout `time_study_tool.py` runs. Named as later tools, not built anywhere yet: `promise-scan`, `clerical-carry`, `meeting-prep-pick`, `note-findable`, `crm-hygiene-metrics`, `crm-merge-apply`, `outreach-sent-count`, `relationship-pool`.

### Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Portal**: `portal_mcp_config` (and `portal_server`) for every script that reads or writes the Portal, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- **State**: `state_dir` for the task stack, capture, calendar steward, weekly review and goal alignment. The meeting worker's state is `--state`, else `MEETING_PROCESSING_STATE`, else `state_dir` under `[meeting-scheduled-worker]`, else `<state_dir>/meeting-processing`.
- **Per skill**: `[calendar-steward-method] home`, `daily_plan_state`, `timezone`; `[task-stack-workstream] assignable_contacts`, `lead_words`; `[task-stack-capture] sources` or `sources_file`; `[goal-alignment-workstream] rules_file`, `telos_note`, `quarterly_template`, `time_study_home`; `[meeting-scheduled-worker] since`, `enrichment_agent`, `relayed_answer_head`; `[crm-hygiene-workstream] portal_issue_repo`, `private_terms`; `[report-time-study] home`, `repo`, `domains_csv`.
- **Runner switches**: `F3I_TOOLBOX_DRY_RUN=1` makes the meeting worker's writes refuse a call without `--dry-run`; `NOTIFY_OWNER_MODE` (`off`, `dry-run`) quiets `notify_owner.py`; `CONFIRM_DELIVERY`, `CONFIRM_PORTAL_CMD` and `CONFIRM_NOTIFY_CMD` adjust `confirm.py`; `GH` names another `gh` for `portal_issue_file.py`.
- `voice_guide` in the tables above is read by the agents, not by a script.
- Python 3.11 or later; `openpyxl`, `pypdf`, `python-pptx` (office files) and `pyyaml` (capture sources), declared in each script's `# /// script` block.
