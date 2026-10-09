# Owner settings

The scripts inside the skills read the owner's settings from `~/.config/f3i-toolbox/settings.toml`. When the environment variable `F3I_TOOLBOX_SETTINGS` names another file, they read that file instead. A missing file counts as an empty one.

The file is TOML. Top-level keys are shared by several skills. Each skill that has settings of its own reads one table named after the skill, such as `[daily-plan-method]`. A script asks for the whole file or for its own table, so a key placed in the wrong table is not seen. A few keys are read from a skill's table first and from the top level second; the tables below say where.

Some keys are read by agents and skill instructions rather than by a script: the agent opens the file or folder the key names. The tables list those keys too, and the "Read by" column names the agent where no skill's script reads the key.

Secrets never go in this file. Tokens and credentials come only from environment variables, and the scripts never print them. When a setting a command needs is missing, the script says which setting it needs (and usually the flag that can stand in for it) and stops.

Some skills also read settings kept beside the work, such as the Month-End folder's settings, a Forecast folder's settings file, a snapshot config passed with `--config`, or a rules file. Those belong to the work folder and are described in each skill, not here.

## Top-level keys

| Key | Required | Default | What it is for | Read by |
|---|---|---|---|---|
| `portal_mcp_config` | Yes, when a command that reads or writes the Portal runs | none | Path to the MCP config file (JSON) whose `mcpServers` entry gives the Insights Portal URL and Authorization header. | calendar-steward-method, chief-of-staff-cycle, client-delivery-workstream, client-update-workstream, comms-confirm, comms-draft-check, comms-reply-to-email, daily-plan-method, goal-alignment-workstream, issue-harvest-workstream, meeting-portal-notes, meeting-scheduled-worker, nightly-sweep-workstream, project-health-diagnose, project-landscape, report-weekly, task-stack-capture, task-stack-workstream, weekly-review-workstream |
| `portal_server` | No | `"insights-portal"` | The name of the Portal's entry under `mcpServers` in that config file. | the same skills as `portal_mcp_config` |
| `state_dir` | Yes, for a command that keeps state, unless a `--state` or `--home` flag or the skill's own setting names the folder | none | The folder that holds each skill's state in a subfolder: `calendar-steward`, `chief-of-staff`, `comms-reply`, `daily-plan`, `goal-alignment`, `issue-harvest`, `meeting-processing`, `nightly-sweep`, `software-factory`, `task-stack`, `weekly-review`. | calendar-steward-method, chief-of-staff-cycle, comms-reply-to-email, daily-plan-method, goal-alignment-workstream, issue-harvest-workstream, meeting-scheduled-worker, nightly-sweep-workstream, project-landscape, quick-capture, software-factory-workstream, task-stack-capture, task-stack-workstream, weekly-review-workstream |
| `contexts_dir` | Yes, when a Context is named rather than given by its path | none | The folder of Context YAML files, found by name (`<name>.yaml` or `.yml`). | board-package-workstream, client-delivery-workstream, client-update-workstream, process-flow-workstream |
| `engagements_dir` | Yes, when engagement-folders runs without `--root` | none | The parent folder under which a new engagement's folders are created. | project-engagement-workstream, project-engagement-runbook, marketing-case-study-orchestrator (agent) |
| `private_terms` | No | none | A list of private words refused in any filed issue, matched as whole words ignoring case; used only when `[issue-harvest-workstream]` has no `private_terms` of its own. | issue-harvest-workstream |
| `voice_guide` | Yes, for any agent that drafts in the owner's voice | none | Path to the owner's voice guide: openings, closings, framing rules, forbidden phrases and register by recipient. A drafter with no voice guide says so and stops. The chief of staff's cycle reads `[chief-of-staff-cycle] voice_guide` first. | chief-of-staff-cycle, comms-reply-to-email, comms-draft-email, comms-draft-check, comms-follow-ups, comms-inbox-replies, meeting-followup, marketing-content-workstream, brand-guide, writing-seminar-builder, community-workstream, email-drafter, email-checker, community-writer, accomplishment-gatherer and accomplishment-synthesizer (agents) |
| `owner_profile` | No | none (read only when set) | Path to the owner's profile: facts about the owner and their standing instructions, read and never quoted into a draft or message. The chief of staff's cycle reads `[chief-of-staff-cycle] owner_profile` first. | chief-of-staff-cycle, comms-reply-to-email, pressure-test-method, chief-of-staff (agent) |
| `goals_doc` | No | none | Path to the owner's strategic goals document. The chief of staff's cycle reads `[chief-of-staff-cycle] goals_doc` first; its `--goals` flag overrides both. | chief-of-staff-cycle, pressure-test-method |
| `audience` | No | none (the skill asks for one) | One sentence describing who the owner writes and presents for, such as "operations heads at regional hospitals". An audience the caller names for one piece wins. | writing-seminar-builder, brand-guide, unslop-editorial |
| `training_dir` | Yes, for a seminar run unless the caller names a folder | none | The training folder where seminars live, laid out as writing-seminar-builder's "The training folder" section defines. | writing-seminar-builder, learning-seminar-orchestrator and seminar-builder (agents) |
| `playbooks_dir` | Yes, for playbook work; playbook-index needs it when no folder is passed | none | The owner's playbook folder of ratified decision rules, with its `_inbox/` for proposals and `meta/` for the queue. | playbook-ratification, playbook-workstream, playbook-distilling, pressure-test-method, playbook-orchestrator (agent) |
| `ratification_queue` | No | `meta/RATIFICATION-QUEUE.md` inside `playbooks_dir` | The ratification queue file, each item tagged with its function. | playbook-ratification, playbook-workstream, playbook-orchestrator (agent) |
| `vault_dir` | Yes, for any command that reads the vault, unless `--vault` is given | none | The owner's Obsidian vault. Scripts that write elsewhere refuse an output path inside it. The chief of staff's cycle reads `[chief-of-staff-cycle] vault_dir` first, as a folder of strategy notes its decider may follow links into. | obsidian-workstream, obsidian-video-note, obsidian-vault-garden, content-scout-workstream, chief-of-staff-cycle |
| `vault_inbox` | Yes, to write to the vault | none (nothing is written) | The folder inside the vault, relative to `vault_dir`, where agents may put new notes for the owner to review; `--inbox` overrides it. | obsidian-workstream, obsidian-video-note, obsidian-vault-garden |
| `vault_private_dirs` | No | none | A list of folders inside the vault that no agent reads or writes; the scripts never index them. | obsidian-workstream, obsidian-vault-garden |
| `vault_rules` | No | none (the skill's own defaults) | Path to the owner's `VAULT-RULES.md`: note kinds, frontmatter keys, title prefixes and tags. | obsidian-workstream |

## Per-skill tables

### [board-package-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `contexts_dir` | No | the top-level `contexts_dir` | The folder of Context files for this skill, read before the top-level key. |

### [calendar-steward-method]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `home` | No | `<state_dir>/calendar-steward` | The steward's home folder (item ledger, journal, one folder per list); `--home` overrides it. |
| `daily_plan_state` | No | `<state_dir>/daily-plan` | The daily plan's state folder, which calendar-steward-scan reads; `--daily-plan-state` overrides it. |
| `timezone` | No | `"UTC"` | The IANA zone used when no zone is passed on the command line. |

### [chief-of-staff-cycle]

Every key here except `state` is read from this table first and from the top level second, so `owner_profile`, `goals_doc`, `vault_dir` and `voice_guide` set once at the top level serve the cycle too. The cycle also reads `[orchestrator-fleet] reserved_params`.

| Key | Required | Default | What it is for |
|---|---|---|---|
| `charter` | No (the decider names it missing) | none | The chief of staff's charter: its role, authority and limits. |
| `owner_profile` | No | the top-level `owner_profile` | The owner's profile, facts and not preferences; never written by the cycle. |
| `goals_doc` | No | the top-level `goals_doc` | The strategic goals; `--goals` on `start` overrides it. |
| `principles` | No | none | The owner's decision principles and hard rules; never written by the cycle. Produce-work also packs it as guidance. |
| `doer_roster` | No | none | Markdown roster with an `## Active doers` table (trust rung, cost and health per doer); the records script rewrites only the trust and health cells of doers dispatched this cycle. |
| `event_ledger` | No | none | The event ledger of dated lines; the records script appends one line per cycle. |
| `vault_dir` | No | the top-level `vault_dir` | A folder of strategy notes the decider may follow links into; `--vault` overrides it. |
| `health_probe` | No | none | An estate health probe's latest output; `--health` overrides it. |
| `autonomy_policy` | No | none | The standing autonomy policy; `--autonomy` overrides it. |
| `principles_inbox` | No | none (no draft principle is written) | The folder where one draft principle per cycle may be written for the owner to ratify. |
| `doer_registry` | Yes, for any doer to run | none (no doer may run; only launches remain) | A TOML file of `[[doer]]` entries, the only doers a cycle may dispatch; `references/doer-registry.example.toml` in the skill is a start. |
| `voice_guide` | No | the top-level `voice_guide` | The voice guide produce-work packs as guidance with the source. |
| `display_name` | No | `"Chief of Staff"` | The name on the receipt title, the decision-task prefix and the messages; a value with brackets, a newline or over 40 characters falls back to the default. |
| `former_names` | No | none | A list of earlier display names, so a rename never duplicates today's receipt or an open decision. |
| `portal_web_url` | No | none (messages carry no link) | The Portal's web address, used for the receipt link in the message to the owner. |
| `fleet_launches` | No | off | `"on"` lets the cycle launch registered orchestrators; anything else reads off, and launches are only shown as what would have run. |
| `launch_backstop` | No | `12` | The most fleet launches a day across live cycles; a value that is not a whole number reads 12. |
| `improvements` | No | `"propose"` | `"off"`, `"propose"` (the change is filed as a decision) or `"commit"` (the change is made and committed in a worktree of `improve_repo`). |
| `improve_repo` | Yes, for `improvements = "commit"` | none (the change is proposed) | The toolbox repository whose linked worktree takes a committed improvement. |
| `improve_branch` | No | `"chief-of-staff/improvements"` | The branch the improvement worktree commits on. |
| `state` | No | `<state_dir>/chief-of-staff` | The cycle's state folder; `--state` overrides it. |

### [client-update-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `contexts_dir` | No | the top-level `contexts_dir` | The folder of Context files for this skill, read before the top-level key. |
| `reference_docx` | No | none (pandoc's own styles) | A Word reference document that client-update-record passes to pandoc for the update's styles. |

### [content-scout-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `research_dir` | Yes, unless the caller names a folder | none | The research folder of creator and channel folders; a working folder outside the vault, and the scout stops if it sits inside `vault_dir`. Read by the agent, not a script. |
| `watchlist` | No | `<research_dir>/_watchlist.md` | The owner's watchlist file naming each creator, a folder slug and each channel with its link. Read by the agent, not a script. |

### [crm-hygiene-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `portal_issue_repo` | Yes, when portal-issue-file runs | none | The Portal's GitHub repository as `owner/name`, where Portal defects are filed. |
| `private_terms` | No | none | A list of private words that stop an issue from being filed (whole word, any case); this skill does not read the top-level key. |

### [daily-plan-method]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `timezone` | Yes, when neither `--tz` nor the Portal gives a zone | none | The owner's IANA zone for the day's plan. |

### [decision-case-mining]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `database` | Yes, unless `--db` is given | none | The decision store's SQLite file of sources, cases, playbooks and bullets. recording-harvest registers recordings in the same store. |

### [erp-ledger-pull]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `intacct_company_id` | No | none | The Sage Intacct company id, used when `SAGE_INTACCT_COMPANY_ID` is not set. |
| `intacct_api_user` | No | none | The Sage Intacct API user, used when `SAGE_INTACCT_API_USER` is not set. |

### [goal-alignment-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `rules_file` | Yes, for the pack pass of goal-alignment-gather, unless `--rules` is given | none | Path to GOAL-ALIGNMENT-RULES.md. |
| `telos_note` | No | none | The strategic goals document, used when the rules file does not name one. |
| `quarterly_template` | No | none | The quarterly review template, used when the rules file does not name one. |
| `time_study_home` | No | none (the pack has no hours) | The time study's home folder, whose tables give the month's hours; `--time-home` overrides it. |
| `alignment_project` | Yes, for goal-alignment-publish's pack pass, unless `alignment_domain` or a flag is given | none | The Portal project (uuid) the alignment approval task goes in; `--alignment-project` overrides it. |
| `alignment_domain` | No | none | The Portal domain (uuid) whose catch-all project takes the alignment task when no project is set; `--alignment-domain` overrides it. |

### [issue-harvest-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `repos_file` | Yes, unless `--repos-file` is given | none | The repo map (YAML, JSON or TOML) listing the repositories the harvest may file on. |
| `state` | No | `<state_dir>/issue-harvest` | The harvest's state folder (ledger and run log); `--state` overrides it. |
| `horizon_days` | No | `14` | The furthest back, in days, a Run reads. |
| `closed_days` | No | `30` | How many days back a closed issue counts as recently closed for the duplicate check. |
| `public_denylist_files` | No | none | A list of files of private names refused in a public repository. |
| `private_terms` | No | the top-level `private_terms` | A list of private words refused on every repository (whole word, any case). |
| `source_links` | No | none | A sub-table of link templates per source, with `{id}` replaced by the item's id. |
| `sources.portal_notes` | No | enabled | Sub-table with `enabled` (default true), `exclude_titles` (patterns) and `max_fetch` (default `300`). |
| `sources.portal_email` | No | enabled | Sub-table with `enabled` (default true), `exclude_senders` and `exclude_subjects`. |
| `sources.portal_tasks` | No | enabled | Sub-table with `enabled` (default true). |
| `sources.said_not_seen` | No | not read unless the sub-table exists | Sub-table with `enabled` (default true) and `path`, the folder of `said-not-seen-*.json` files, which is needed once the sub-table exists. |

### [meeting-scheduled-worker]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `since` | Yes, when meeting-pending runs without `--since` | none | The earliest meeting start, as an ISO time, that the worker processes. |
| `state_dir` | No | `<state_dir>/meeting-processing` | This skill's state folder; `--state` and `MEETING_PROCESSING_STATE` come before it. |
| `enrichment_agent` | No | `"deep-researcher"` | The slug of the Portal agent that takes the enrichment tasks meeting-publish files; `--agent-slug` overrides it. crm-context-enrichment reads it to find that agent's backlog. |
| `relayed_answer_head` | No | `""` (none) | The first line a runner puts on an answer it posts for the owner, so that comment is read as the owner's words. |

### [nightly-sweep-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `timezone` | Yes, unless `--tz` is given | none | The owner's IANA zone; a date is the owner's local day, midnight to midnight. |
| `state` | No | `<state_dir>/nightly-sweep` | The sweep's state folder (the ledger of dates swept, and its lock); `--state` overrides it. |
| `assistant_email` | No | none | The executive assistant's address, whose mail is never noise and is read first; leave empty with no assistant. |
| `portal_brief_email` | No | none | The sender of the Portal's own generated Brief, which is treated as noise. |
| `owner_names` | No | none | A list of the owner's names: never distinctive words for matching, and they end a sent message's own words as a signature. |
| `firm_names` | No | none | A list of the firm's names, never distinctive words for matching. |
| `vip_stale_days` | No | `30` | Days after which a VIP or High contact counts as stale for the relationship phase; a value that is not a whole number from 1 to 3650 falls back to 30. |
| `daily_note_private` | No | `false` | `true` writes the Daily Note as a private note that must read back private. |

### [orchestrator-fleet]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `registry` | Yes, unless `--registry` is given | none | The owner's orchestrator registry (YAML) with its `orchestrators:` list. |
| `agents_dir` | No | `~/.claude/agents` | Where `validate` looks for each orchestrator's agent file; `--agents-dir` overrides it. |
| `automations_dir` | No | the registry's own `automations_dir` | The folder of Automation definitions; `--automations-dir` overrides it, and it is needed when `launch_command` uses `{automation_path}`. |
| `runs_command` | Yes, for Run columns in the status and for a capped launch | none | The runner's command that prints its recent Runs as JSON, as a list of words or one string; run without a shell. |
| `launch_command` | Yes, to launch | none | The runner's command that queues one Run, with `{automation}`, `{automation_path}` and `{by}` filled in. |
| `param_args` | No | `["--param", "{key}={value}"]` | The words appended to `launch_command` for each launch param. |
| `reserved_params` | No | none (`dry_run` is always reserved) | Param names the runner fills itself, which a launch may not carry. The chief of staff's cycle reads it too. |

### [playbook-ratification]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `function_labels` | No | none | A table of function folder to heading for the playbook index, in index order, such as `finance = "Finance: accounting, treasury, controls"`. |

### [pressure-test-method]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `rotation_ledger` | No (a missing setting is named in the note and the audit goes on) | none | A YAML list of audit targets, each with `name`, `last_audited` and `findings`. Read by the agent, not a script. |

### [process-flow-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `client_subfolder` | No | `"Process Flows"` | The folder inside the client's folder where process drafts are delivered. |
| `delivery_dir` | No | none (no delivery folder) | The owner's own delivery folder, used when the Context names no client folder; it must already exist. |
| `reference_models_dir` | No | `"~/.claude/skills/reference-process-models"` | The library of reference process models that process-flow-prepare looks in. |
| `screenshot_command` | No | headless Chrome or Chromium from PATH | A command template for process-flow-render's screenshot, with `{url}`, `{out}`, `{width}` and `{height}` filled in. |

### [product-costing-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `cost_model_layout` | Yes, when fg-pl-extract or costmodel-audit runs without `--layout` | none | Path to the cost-model layout JSON. |
| `extract_synonyms` | No | none | Path to a JSON file of extra header synonyms for sap-extract-normalize; `--synonyms` overrides it. |

### [project-engagement-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `general_subfolders` | No | the built-in list in engagement-folders | A list of folder names created once per engagement. |
| `workstream_subfolders` | No | the built-in list in engagement-folders | A list of folder names created in each workstream's month folder. |
| `repo_prefix` | No | `"f3i"` | The prefix of the working repository folder engagement-folders creates; `--repo-prefix` overrides it. |

### [project-health-diagnose]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `runs_dir` | Yes, when project-health-check runs with `--last-run` | none | The folder of the project-health Runs, searched for the last one. |

### [recording-harvest]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `video_list` | Yes, unless `--videos` is given | none | A file of Loom share links or video ids, one per line, `#` for a comment. |
| `archive_dir` | Yes, unless `--archive` is given | none | The folder where transcripts and captions are kept (never video). |

### [report-time-study]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `home` | Yes, when time-study-check, time-study-collect or time-study-tool runs without a home argument | none | The time study's home folder. |
| `repo` | No | the home's parent folder, when it holds the `timestudy` package | The time-study tool's checkout; `--repo` overrides it. |
| `domains_csv` | Yes, when time-study-day-lint runs without `--domains` | none | Path to the owner's domains CSV. |

### [report-weekly]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `reference_docx` | No | none (report-render builds one in its scratch folder) | The Word reference document report-render uses for the report's styles. |

### [review-register]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `owner_name` | No | `"the owner"` | The name in the register's "Owed by" heading. |

### [skill-harvest-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `repo` | Yes, unless `--repo` is given | none | The toolbox checkout the harvest's review branch is cut from. |

### [skills-extract]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `claude_session_dirs` | No | `["~/.claude/projects"]` | A list of folders holding past Claude Code sessions (one string is read as a list of one); `--claude-dir` overrides it. |
| `codex_session_dirs` | No | `["~/.codex/sessions"]` | A list of folders holding past Codex sessions; `--codex-dir` overrides it. |

### [software-factory-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `repos_dir` | Yes, unless `SOFTWARE_FACTORY_REPOS_DIR` is set | none | The folder holding the local clones and the factory's worktrees. |

### [software-portfolio-review]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `repos_root` | Yes, when repo-sweep runs without a ROOT argument | none | The folder repo-sweep searches for repositories. |

### [task-stack-capture]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `sources` | Yes, unless `sources_file` is set or `--sources` is given | none | The list of capture sources, each with `name`, `kind` and `path`; used before `sources_file`. |
| `sources_file` | No | none | A YAML, TOML or JSON file holding the capture sources, read when `sources` is not set. |

### [task-stack-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `assignable_contacts` | No | none (only the owner) | Portal contact ids, besides the owner, to whom task-stack-apply may assign work. |
| `lead_words` | No | none | Extra words that may come before a task's verb, such as the owner's first name, added to the built-in list. |

### [toolbox-audit-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `repo` | Yes, unless `--repo` is given | none | The toolbox checkout the audit scans and cuts its fix branch from; the Run folder must sit outside it. |

### [weekly-review-workstream]

| Key | Required | Default | What it is for |
|---|---|---|---|
| `review_project` | Yes, for weekly-review-publish's pack pass, unless `review_domain` or a flag is given | none | The Portal project (uuid) the weekly review's approval task goes in; `--review-project` overrides it. |
| `review_domain` | No | none | The Portal domain (uuid) whose catch-all project takes the review task when no project is set; `--review-domain` overrides it. |

## Environment variables

| Variable | Required | Default | What it is for | Read by |
|---|---|---|---|---|
| `F3I_TOOLBOX_SETTINGS` | No | `~/.config/f3i-toolbox/settings.toml` | The settings file to read in place of the default. | every skill that reads settings |
| `INSIGHTS_PORTAL_ASSISTANT_TOKEN` | Yes, when the MCP config entry has no Authorization header | none | The Portal bearer token; when set it is used in place of the config's Authorization header. | every skill that reads `portal_mcp_config` |
| Any `${VAR}` in the MCP config | Yes, when the config's URL or Authorization header names it | none | Each `${VAR}` in the Portal entry's URL or Authorization header is expanded from the environment; an unset one stops the script. | every skill that reads `portal_mcp_config` |
| `SAGE_INTACCT_CLIENT_ID` | Yes, for a live Intacct pull (intacct-gl-detail, intacct-snapshot `--live`, month-end-pull) | none | The web-services app's client id. | erp-ledger-pull |
| `SAGE_INTACCT_CLIENT_SECRET` | Yes, for a live Intacct pull | none | The web-services app's client secret. | erp-ledger-pull |
| `SAGE_INTACCT_COMPANY_ID` | Yes, for a live Intacct pull, unless `[erp-ledger-pull] intacct_company_id` is set | none | The Intacct company id. | erp-ledger-pull |
| `SAGE_INTACCT_API_USER` | Yes, for a live Intacct pull, unless `[erp-ledger-pull] intacct_api_user` is set (month-end-pull also accepts the Month-End folder's ERP API user) | none | The Intacct API user. | erp-ledger-pull |
| `SAGE_INTACCT_*_SANDBOX` | No | the same name without the suffix | For the SANDBOX environment, each of the four names above is read with `_SANDBOX` first, then without it; PROD reads only the plain names. | erp-ledger-pull |
| `INTACCT_USER_AGENT` | No | `f3i-toolbox-intacct/1.0 (read-only)` | The User-Agent header sent to Intacct. | erp-ledger-pull |
| `ACCRUALS_SKILLS_DIR` | No | `~/.claude/skills` | Where accruals.py finds the other skills whose commands it runs. | month-end-accrual-drafts |
| `MEETING_PROCESSING_STATE` | No | none | The meeting worker's state folder, after `--state` and before the settings. | meeting-scheduled-worker |
| `F3I_TOOLBOX_DRY_RUN` | No | unset | Set by a runner (`1`, `true`, `yes` or `on`) to mark a dry run; any write called without `--dry-run` is then refused. | chief-of-staff-cycle, meeting-scheduled-worker, nightly-sweep-workstream |
| `NOTIFY_OWNER_MODE` | No | unset (sends) | `off` sends nothing; `dry-run` (also `dryrun` or `rehearsal`) rehearses; anything else sends. | chief-of-staff-cycle, comms-reply-to-email |
| `CONFIRM_DELIVERY` | No | `relay` | How a confirmation request reaches the person, `relay` or `direct`, when `--delivery` is not given. | comms-confirm |
| `CONFIRM_PORTAL_CMD` | No | python3 with confirm_portal.py beside confirm.py | A command to run in place of the Portal half of comms-confirm. | comms-confirm |
| `CONFIRM_NOTIFY_CMD` | No | python3 with comms-reply-to-email's notify_owner.py | A command to run in place of notify-owner. | comms-confirm |
| `REPORT_STORE_DIR` | Yes, unless `--store` is given | none | The executive's report store folder; there is no default path. | report-weekly |
| `SOFTWARE_FACTORY_REPOS_DIR` | No | `[software-factory-workstream] repos_dir` | The folder of local clones, read before the setting. | software-factory-workstream |
| `SOFTWARE_FACTORY_STATE_DIR` | No | `<state_dir>/software-factory`, else `~/.local/state/software-factory` | The factory's state folder, holding one subfolder per repository. | software-factory-workstream |
| `GH` | No | `gh` | The GitHub CLI command to run, split into words. | crm-hygiene-workstream, issue-harvest-workstream, software-factory-workstream |
| `F3I_TOOLBOX_DENYLIST` | No | none (`~/.config/f3i-toolbox/denylist.txt` is still read when it exists) | Files of private names, separated by `:`, checked before scaffolded files, harvested skills or audit fixes are written, and used to withhold names from output; the repository's own checker reads it too. | orchestrator-scaffold, skills-extract, skill-harvest-workstream, toolbox-audit-workstream |
| `YT_DLP` | No | `yt-dlp` from PATH, else `python3 -m yt_dlp` | The command that runs yt-dlp, split into words. | content-scout-workstream, obsidian-video-note |
| `LOOM_COOKIES_FILE` | No | none (public videos only) | Path to a cookies.txt exported from a signed-in Loom tab, for private videos; `--cookies` overrides it. A credential: keep it out of every repository. | recording-harvest |

## Example

A minimal settings file. Every value is a placeholder to replace with the owner's own.

```toml
# Shared by several skills
portal_mcp_config = "~/path/to/mcp-config.json"
portal_server = "insights-portal"
state_dir = "~/path/to/state"
contexts_dir = "~/path/to/contexts"
engagements_dir = "~/path/to/engagements"
voice_guide = "~/path/to/voice-guide.md"
owner_profile = "~/path/to/owner-profile.md"
goals_doc = "~/path/to/goals.md"
playbooks_dir = "~/path/to/playbooks"
vault_dir = "~/path/to/vault"
vault_inbox = "_inbox"

[daily-plan-method]
timezone = "UTC"

[nightly-sweep-workstream]
timezone = "UTC"

[task-stack-workstream]
assignable_contacts = ["00000000-0000-0000-0000-000000000000"]
lead_words = ["dana"]

[chief-of-staff-cycle]
doer_registry = "~/path/to/doer-registry.toml"

[orchestrator-fleet]
registry = "~/path/to/orchestrators.yaml"

[erp-ledger-pull]
intacct_company_id = "example-company"
intacct_api_user = "api-user"
```
