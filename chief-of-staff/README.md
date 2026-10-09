# Chief of Staff

An AI chief of staff for one owner: an interactive front door that routes any request to the right skill or agent, and an unattended cycle that reads the owner's own documents and the Insights Portal whenever it is started, picks the day's priorities, launches registered orchestrators off schedule, dispatches a few bounded doers, proposes or commits one small improvement on a branch, and files one verified receipt with any decisions only the owner can make. Also the owner's quick daily tools: start the session, capture anything, log a project status, and a one-off survey of where a working life's hours go. Everything private (profile, charter, goals, principles, roster, ledger, the doer registry, the fleet registry, the runner) is a file or command the owner names in their settings; nothing is sent to anyone but the owner.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `chief-of-staff` | Main-session front door: routes a request to the skill or agent that serves it, checks the result, reports | the agents and skills it routes to; skill `orchestrator-fleet` |
| `chief-of-staff-cycle-orchestrator` | Runs one unattended cycle by the chief-of-staff-cycle skill: decide, launch, dispatch, improve, receipt | Insights Portal; the chief-of-staff-cycle scripts; settings `state_dir`, `[chief-of-staff-cycle]` |
| `chief-of-staff-decider` | Reads the owner's documents and the Portal and returns the cycle's one decision object | Insights Portal; settings `charter`, `owner_profile`, `goals_doc`, `principles`, `doer_roster`, `event_ledger` |
| `chief-of-staff-producer` | Writes one private, review-ready draft from a source packet | skill `task-stack-produce` (productivity) |
| `chief-of-staff-readonly-doer` | Runs one read-only skill headless and reports | Insights Portal |
| `chief-of-staff-meeting-prep-doer` | Runs meeting-prep headless and writes its one prep note | Insights Portal; skill `meeting-prep` |
| `chief-of-staff-improver` | Turns the cycle's one improvement into an exact edit for the script to commit on a branch | setting `improve_repo` (to commit) |
| `chief-of-staff-receipt-writer` | Writes the cycle's receipt and proposes decisions and record lines | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `chief-of-staff-cycle` | The unattended cycle: decide, launch, dispatch, one improvement, one verified receipt | Insights Portal; skills `orchestrator-fleet`, `task-stack-workstream`, `task-stack-produce`, `comms-reply-to-email` (notify_owner.py); settings below |
| `orchestrator-fleet` | The owner's orchestrator registry: list, validate, status, launch through the owner's runner | settings `[orchestrator-fleet]`; `pyyaml` |
| `start-session` | Starts the day from today's daily plan note, or plans the morning by hand | Insights Portal; skill `daily-plan-method` |
| `quick-capture` | Universal capture: classify, link, file; tasks through task-stack-apply | Insights Portal; skills `task-stack-workstream`, `task-stack-capture`, `portal-write-safety`; setting `state_dir` |
| `project-status-update` | One status line in: the project's status note updated, stated task changes made | Insights Portal; skill `portal-write-safety` |
| `work-survey` | A full survey of a working life against what is owed and wanted, with an operating plan and build specs | Microsoft 365 or Insights Portal MCP |

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`.

**`chief-of-staff-cycle`**
- `chief_of_staff_cycle.py`: opens (`start`), records (`record`) and closes (`finish`) one cycle.
- `chief_of_staff_fleet.py`: the fleet snapshot (`snapshot`) and the cycle's one launch path (`launch`).
- `chief_of_staff_decide_check.py`: checks the decider's reply against the doer registry and the snapshot.
- `chief_of_staff_produce_work.py`: the produce-work packet (`pack`) and the checked save (`save`).
- `chief_of_staff_improve.py`: the improvement's guard (`check`) and its edit and commit on a branch of a separate linked worktree (`apply`); never the live checkout, never a push.
- `chief_of_staff_receipt.py`: the day's receipt note and decision tasks (`read`, `publish`, `verify`).
- `chief_of_staff_records.py`: the doer roster's health cells, one ledger line, one draft principle (`apply`).
- `chief_of_staff_notify.py`: the receipt link and the decision count to the owner, within daily caps.
- `cos_watch.py`: the check a runtime's Monitor trigger runs (`--since=<cursor>`): what is new and material in the Portal since the last check (a task newly overdue or due today, VIP mail, a meeting new inside 24 hours), as `{items, cursor}`. Read-only and stateless; needs `portal_mcp_config` and the Portal token.

**`orchestrator-fleet`**
- `fleet_registry.py`: lists and validates the registry.
- `fleet_status.py`: where every registered orchestrator stands.
- `fleet_launch.py`: queues one Run through the runner, or says why not.

Scripts from other departments these call: `task_stack_check.py` and `task_stack_apply.py` (`task-stack-workstream`), `notify_owner.py` (`comms-reply-to-email`), `outbound_check.py` (`comms-draft-check`), `daily_plan_pull.py` (`daily-plan-method`).

## Settings and environment

- **Shared**: `state_dir`; `portal_mcp_config` and `portal_server` (bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config); `voice_guide` and `owner_profile`, read when set.
- **`[chief-of-staff-cycle]`**: the owner's documents `charter`, `owner_profile`, `goals_doc`, `principles`, `doer_roster`, `event_ledger`, `vault_dir`, `health_probe`, `autonomy_policy`, `principles_inbox`; `doer_registry` (the only doers a cycle may dispatch; `chief-of-staff-cycle/references/doer-registry.example.toml` is a start); `display_name`, `former_names`; `fleet_launches` (`"on"` or off, default off); `launch_backstop` (default 12); `improvements` (`"off"`, `"propose"` default, `"commit"`), `improve_repo`, `improve_branch` (default `chief-of-staff/improvements`); `portal_web_url`; `state`. Each key is read from the table first and the top level second.
- **`[orchestrator-fleet]`**: `registry`, `agents_dir`, `automations_dir`, `runs_command`, `launch_command`, `param_args`, `reserved_params`. Commands are run without a shell.
- **Runner switches**: `F3I_TOOLBOX_DRY_RUN=1` makes the receipt and records writes refuse a call without `--dry-run`; `NOTIFY_OWNER_MODE` (`off`, `dry-run`) quiets the messages.
- Python 3.11 or later; `pyyaml` for the fleet registry, declared in the scripts' `# /// script` blocks. `git` for a committed improvement.

## Agent grants

`chief-of-staff-cycle-orchestrator` may dispatch only the agents its `Agent(...)` grant names: its six workers and `person-researcher` and `domain-researcher`, the `agent`-route doers of the example registry. A doer the owner adds with route `agent`, or a new `worker`, needs its agent's name added to that grant. Its `Write` grant is not limited to a folder because the state folder is a setting; the skill confines its writes to the cycle folder. `chief-of-staff` is the interactive front door and keeps every tool.

## Left out

- The registrar and red-team doers of the source repository. Each ran a skill about one owner's own Portal and private records (the red team also wrote into their private principles and searched the web from that context). The registrar's job is the `crm-data-hygiene-orchestrator`, which the cycle launches through the fleet; the red team has no general equivalent here.
