---
name: orchestrator-fleet
description: The owner's orchestrator fleet. A registry file the owner keeps lists every orchestrator (status, the Automation that starts it, its triggers, its launch params, who may launch it), and three scripts list and validate the registry, report where every orchestrator stands (last Run, live, queued, waiting on the owner, its check's headline), and launch one through the owner's runner with authority, params and a daily cap enforced. Use when someone asks "run the weekly review now", "what is the state of my orchestrators" or "is the registry valid", or when the chief-of-staff cycle snapshots and launches. Not for running an orchestrator's work in this session, since a launch only queues a Run.
---

# The orchestrator fleet

Whole recurring jobs (the task stack's nightly and weekly passes, the daily plan, the close, the weekly review and the rest) belong to registered orchestrators, each run as its own Run from an Automation by whatever runner the owner uses. The registry is the list, so read it when a request comes in rather than from memory.

The commands:

- `chief-of-staff-fleet-registry list [--domain D] [--status S] --format json`: each orchestrator's `name`, `domain`, `purpose`, `status`, `authority`, `triggers`, `inputs` (launch param to the pattern its value must match) and `outputs`.
- `chief-of-staff-fleet-registry validate`: checks every entry against the schema (in `fleet_registry.py`'s docstring); exit 1 when it finds an error.
- `chief-of-staff-fleet-status --format json [--no-checks]`: per orchestrator, its last Run and outcome, whether one is live or queued now, what waits on the owner, and its check's headline (the check run with `--precheck`).
- `chief-of-staff-fleet-launch NAME [--params k=v ...] [--dry-run] [--authority dry-run-only|propose|trusted] [--cap N] [--by AGENT] [--format json]`: queues one Run, or says why not. It refuses a name the registry does not hold, an entry not built (status `spec`, or no Automation), an entry whose authority is above the caller's, a param the entry does not declare or whose value its pattern does not match, a `propose` caller with no cap and no `--by`, and a launch past the day's cap counted from the runner's records. A `dry-run-only` entry or caller always runs dry. Exit 0 queued, 1 refused, 2 an error.

## Launching one for a person

1. `chief-of-staff-fleet-registry list --format json` (add `--domain D` when the domain is clear). Match the request to the entry whose purpose and outputs serve it. Only an entry past status `spec` with an Automation can run; a `spec` entry is a plan, so say the orchestrator is not built yet and route to the skill that does the work by hand.
2. `chief-of-staff-fleet-status --format json` for where it stands. A Run already live or queued is the answer to "start it": say so, do not launch a second.
3. `chief-of-staff-fleet-launch NAME --authority trusted --params k=v ... [--dry-run]`. The owner asking in person is the trusted caller (the script defaults to `propose`). The owner asking is the go for an entry at status `live`; for any other, its first live Run is the owner's own decision, so launch it as a dry run unless they said live; an entry at `dry-run-only` runs dry whatever is asked. The launch only queues the Run: report its queue line and that the result arrives in the Run's own outputs.

Never dispatch an orchestrator as a sub-agent: it must be the main session of its own Run to dispatch its workers.

## Settings

All in the table `[orchestrator-fleet]` of the owner settings:

- `registry`: the registry file (YAML). Required unless `--registry` is passed; there is no default path.
- `agents_dir`: where `validate` looks for agent files, default `~/.claude/agents`.
- `automations_dir`: the folder of Automation definitions; optional (the registry's own `automations_dir` is the fallback). When known, `validate` checks each Automation's folder exists and `chief-of-staff-fleet-launch` refuses one that does not.
- `runs_command`: the runner's command that prints its recent Runs as JSON (the shape is in `_common.py`'s docstring). Without it, the status has no Run columns and a capped launch is refused.
- `launch_command`: the runner's command that queues one Run, with `{automation}`, `{automation_path}` and `{by}` filled in; each param is appended as the words of `param_args` (default `["--param", "{key}={value}"]`). Required to launch.
- `reserved_params`: param names the runner fills itself, which a launch may not carry (`dry_run` is always reserved).

The registry's top-level `launch_cap_per_day` is the default `--cap`. Since the departments became plugins (ADR 0004), each entry's `name` is the main agent's new name (`task-steward`, `meeting-steward`, `accounting-month-end-close`); `validate` looks for that agent file in `agents_dir`. With Sentinel as the runner, `runs_command` is `sentinel runs --format json` and `launch_command` is `sentinel launch {automation_path} --source agent`. Commands are a TOML list of words, or one string split as a shell would; they are never run through a shell.
