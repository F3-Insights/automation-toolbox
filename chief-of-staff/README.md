# Chief of Staff

An AI chief of staff for one owner, in two jobs. The interactive front door finds where any request is served in the live catalogue of every department, launches a recurring job through the orchestrator fleet or hands over the exact line that starts the right department's session, and does research, a deep work survey, an independent review or one private draft itself. The unattended cycle reads the owner's own documents and the Insights Portal whenever it is started, picks the day's priorities, launches registered orchestrators off schedule, runs at most two bounded doers, proposes or commits one small improvement on a branch, and files one verified receipt with any decisions only the owner can make. Everything private (profile, charter, goals, principles, roster, ledger, the doer registry, the fleet registry, the runner) is a file or command the owner names in their settings; nothing is sent to anyone but the owner.

## The plugin

This folder is a standalone Claude Code plugin named `chief-of-staff` (`.claude-plugin/plugin.json`), on the pattern of [ADR 0004](../docs/adr/0004-a-department-is-a-plugin.md) and [converting a department](../docs/converting-a-department.md). One short main agent per job; the procedure is in the job's skill under `## Steps`; `chief-of-staff-worker` does parallel or isolated slices and `chief-of-staff-reviewer` does the front door's independent checks. Commands are in `bin/`, written by `python3 scripts/build_bins.py chief-of-staff`.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/chief-of-staff --agent chief-of-staff:chief-of-staff
```

From Sentinel, the cycle's Automation launches `chief-of-staff-cycle-runner` with `--plugin-dir <toolbox>/chief-of-staff`, which puts the commands on PATH; its overlay's `subagents:` lists `chief-of-staff-worker`.

## Jobs and agents

| Agent | Job | Dispatches | Needs |
|---|---|---|---|
| `chief-of-staff` | The front door, started by hand as the main session: route, launch or hand over, research, review, report | `chief-of-staff-worker` (`portal-research` sections, `work-survey` slices, one `task-stack-produce` draft), `chief-of-staff-reviewer` (`review-*`) | Insights Portal; settings `owner_profile`, `[orchestrator-fleet]` |
| `chief-of-staff-cycle-runner` | One unattended cycle (Automation `chief-of-staff-skill`, scheduled and woken by its Monitor): decide, launch, dispatch, improve, receipt | `chief-of-staff-worker` (section Run one doer, then the registry doer's skill and section) | Insights Portal; settings `state_dir`, `[chief-of-staff-cycle]`, `[orchestrator-fleet]` |
| `chief-of-staff-worker` | One slice a main agent hands it, following the skill section it is told to use; reads only | none | Portal reads |
| `chief-of-staff-reviewer` | Independent check of a finished deliverable against a `review-*` checklist, from the sources alone; edits nothing | none | Portal reads; `report-tieout` |

The two jobs stay separate: one is hand-started and talks to the owner, the other runs unattended and never asks. The cycle needs no reviewer: `chief-of-staff-decide-check`, `chief-of-staff-receipt publish` and `verify` are its independent checks, in code.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `chief-of-staff-cycle` | chief-of-staff-cycle-runner, worker | Steps; sections Decide the cycle, Produce one draft, Run one doer, One improvement, Write the receipt; Finishing; `rules.md` (settings, mechanics, the receipt's shape) |
| `chief-of-staff-routing` | chief-of-staff | Steps; where requests go, department by department; what needs the owner's go-ahead; fan-out rules |
| `orchestrator-fleet` | both main agents | The owner's orchestrator registry: list, validate, status, launch through the runner |
| `task-stack-produce` | chief-of-staff-cycle-runner, worker | The standard for one private, review-ready draft from a source packet. A builder in the owner's private library models its own task producer on this skill, so its sections keep their names |
| `work-survey` | the owner, through chief-of-staff | A full survey of a working life against what is owed and wanted, with an operating plan and build specs |
| `portal-research` | worker (shared copy) | Research a person, Research email history, Research a domain |
| `review-facts`, `review-numbers`, `review-red-team`, `review-completeness` | reviewer (shared copies) | The four reviewer checklists |
| `orchestration-workstream`, `task-stack-workstream`, `report-tieout`, `unslop` | shared copies | Worker conduct; the task-stack score the fleet snapshot reads; the figure tie-out; plain writing |

## Commands

Each runs a script in its skill's `scripts/` folder and prints `--help`.

| Command | Script | What it does |
|---|---|---|
| `chief-of-staff-cycle` | `chief-of-staff-cycle/scripts/chief_of_staff_cycle.py` | Opens (`start`), records (`record`) and closes (`finish`) one cycle |
| `chief-of-staff-fleet` | `chief_of_staff_fleet.py` | The fleet snapshot (`snapshot`) and the cycle's one launch path (`launch`) |
| `chief-of-staff-decide-check` | `chief_of_staff_decide_check.py` | Checks the decision against the doer registry and the snapshot; writes `decision.json` |
| `chief-of-staff-produce-work` | `chief_of_staff_produce_work.py` | The produce-work packet (`pack`, with `--add` for related records) and the checked save (`save`) |
| `chief-of-staff-improve` | `chief_of_staff_improve.py` | The improvement's guard (`check`) and its edit and commit on a branch of a separate linked worktree (`apply`); never the live checkout, never a push |
| `chief-of-staff-receipt` | `chief_of_staff_receipt.py` | The day's receipt note and decision tasks (`read`, `publish`, `verify`); `publish` refuses a local path, an em dash or text copied from the owner's private documents |
| `chief-of-staff-records` | `chief_of_staff_records.py` | The roster's health cells, one ledger line, one draft principle (`apply`) |
| `chief-of-staff-notify` | `chief_of_staff_notify.py` | The receipt link and the decision count to the owner, within daily caps |
| `chief-of-staff-watch` | `chief_of_staff_watch.py` | The Monitor's check (`--since=<cursor>`): what is new and material in the Portal since the last check, as `{items, cursor}`; read-only and stateless |
| `chief-of-staff-fleet-registry`, `-fleet-status`, `-fleet-launch` | `orchestrator-fleet/scripts/fleet_*.py` | List and validate the registry; where every registered orchestrator stands; queue one Run through the runner, or say why not |
| `chief-of-staff-catalogue` | `chief-of-staff-routing/scripts/catalogue.py` | What every department can do, read live from this toolbox checkout: main agents with their Inputs, start lines and Automations, owner-started skills, commands; `--query` ranks them |
| `task-stack-apply`, `-check`, `-queue`, `-report`; `report-tieout` | shared copies | The task-stack commands (the snapshot runs `task_stack_check.py --precheck`); the figure tie-out |

One script is found outside this plugin, in the same toolbox checkout: `chief-of-staff-notify` runs productivity's `comms-reply-to-email/scripts/notify_owner.py`, as the shared `comms-confirm` does.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Shared**: `state_dir`; `portal_mcp_config` and `portal_server` (bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config); `voice_guide` and `owner_profile`, read when set.
- **`[chief-of-staff-cycle]`**: the owner's documents `charter`, `owner_profile`, `goals_doc`, `principles`, `doer_roster`, `event_ledger`, `vault_dir`, `health_probe`, `autonomy_policy`, `principles_inbox`; `doer_registry` (the only doers a cycle may dispatch; `chief-of-staff-cycle/references/doer-registry.example.toml` is a start); `display_name`, `former_names`; `fleet_launches` (`"on"` or off, default off); `launch_backstop` (default 12); `improvements` (`"off"`, `"propose"` default, `"commit"`), `improve_repo`, `improve_branch` (default `chief-of-staff/improvements`); `portal_web_url`; `state`.
- **`[orchestrator-fleet]`**: `registry`, `agents_dir`, `automations_dir` (also where the catalogue finds each Automation's agent), `runs_command`, `launch_command`, `param_args`, `reserved_params`. With Sentinel: `runs_command = ["sentinel", "runs", "--format", "json"]`, `launch_command = ["sentinel", "launch", "{automation_path}", "--source", "agent"]`, `param_args = ["--params", "{key}={value}"]`.
- **Runner switches**: `F3I_TOOLBOX_DRY_RUN=1` makes the receipt and records writes refuse a call without `--dry-run`; `NOTIFY_OWNER_MODE` (`off`, `dry-run`) quiets the messages.
- Python 3.11 or later; `pyyaml` for the fleet registry. `git` for a committed improvement. A work survey over Microsoft 365 needs that connector's read tools added to `chief-of-staff-worker` on the owner's machine; the toolbox names none.

## The owner's private documents

The cycle reads the charter, profile, goals, principles, roster, ledger and autonomy policy to decide, and they must never reach the Portal. Before the conversion a worker boundary kept them out (the receipt writer and producer held only Read and were told not to copy). Now the decision, the draft and the receipt are the cycle agent's own sections, so the rule moved to two places: the agent's `## Never`, and `chief-of-staff-receipt publish`, which refuses a receipt or decision task that repeats a run of eight words from any of those documents (it names the document, never the words) and files a proposed improvement that repeats one without its text. The produce-work draft stays in the private artifact folder; only its status reaches the receipt.

## What was renamed (2026-10-24)

The department became a plugin. Neither job had run unattended on the live machine under these names, so there is no alias period, except that the cycle's scripts still recognise `chief-of-staff-cycle-orchestrator` in a registry or a runner's records.

| Now | Was |
|---|---|
| `chief-of-staff-cycle-runner` | `chief-of-staff-cycle-orchestrator` (the plan's name `chief-of-staff-cycle` is the skill's; an agent may not share it) |
| `chief-of-staff` (40 lines, skill `chief-of-staff-routing`) | `chief-of-staff` (a 95-line routing table that dispatched other departments' agents) |
| section Decide the cycle, by the main agent | `chief-of-staff-decider` (`briefs/decider.md`) |
| section Produce one draft, by the main agent | `chief-of-staff-producer` (`briefs/producer.md`), which returned "blocked" when its packet was thin; the main agent may now repack once with `--add` |
| section One improvement, by the main agent | `chief-of-staff-improver` (`briefs/improver.md`) |
| section Write the receipt, by the main agent | `chief-of-staff-receipt-writer` (`briefs/receipt-writer.md`) |
| section Run one doer, by `chief-of-staff-worker`, on a skill this plugin holds | `chief-of-staff-readonly-doer` and the doer brief; the registry's `person-researcher` and `domain-researcher` agent doers |
| a launch of the meeting-prep Automation (`meeting-steward`) with `instructions` naming the meeting | `chief-of-staff-meeting-prep-doer` |
| `chief-of-staff-reviewer` with `review-facts`, `review-numbers`, `review-red-team`, `review-completeness` | `fact-check`, `numbers-reviewer`, `executive-red-team` (reporting) and `completeness-audit`, which the routing table named; the three reporting agents are deleted |
| the commands above | each script run by its path in the shared skills folder; `cos_watch.py` is `chief_of_staff_watch.py` |
| `start-session` in recurring-summaries | `start-session` here |
| `quick-capture` in productivity | `quick-capture` here |
| `project-status-update` in projects | `project-status-update` here |
| `portal-research`, `portal-write-safety` in `shared/skills/`, copied out | productivity's own skills |

Decided in the conversion, following the migration plan (D7, option A) and the departments already converted:

- decided: the front door routes over a catalogue and launches or hands over, never dispatching another department's agent (D7 option A). The catalogue is read live by `chief-of-staff-catalogue` from the toolbox checkout and the owner's Automation folders, not generated beside `build_bins.py`, so it can never go stale and needs no check of its own.
- decided: the cycle dispatches only `chief-of-staff-worker`. A registry doer's route `agent` is refused with the reason, and route `skill` runs only a skill this plugin holds. Person and domain briefs stay in-cycle as `portal-research` sections (so their results reach the same cycle's receipt); meeting prep, which writes a note, becomes a launch of the meeting-prep Automation.
- decided: the producer, improver and receipt writer, which held only Read and returned JSON, are folded into the main agent's sections; the decider too. The decide check, `publish` and `verify` remain the gates in code, and the decision's output contract is unchanged.
- decided: the improvement surface is the doer skills this department owns (today `task-stack-produce`). A shared skill's copy is refused by the decide check, because its source lives in `shared/skills/` and a change there is rebuilt into every copy; that is a decision for the owner (plan risk 3).
- decided: `chief-of-staff-notify` keeps finding productivity's `notify_owner.py` through the checkout, like `comms-confirm`, rather than a second copy of the script and its helpers.
- decided: `orchestrator-fleet` stays a skill of its own for now (the plan's later merge into the cycle waits until Sentinel holds the registry's authority and param patterns).
- decided: the one-cycle lag the plan names (a launch's result reaches the next cycle's fleet status) is accepted; a launch is reported as queued, never done.
- decided: the interactive front door keeps `unslop`'s principles only; an audience-specific edit is the `unslop-*` skill of the department that owns the text.
