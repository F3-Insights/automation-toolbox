---
name: home-infrastructure-method
description: How the owner's weekly home infrastructure check is made, on top of personal-workstream. Runs only the read-only health commands the owner's rules file lists, or reads the exports they name, compares what runs against the hand-kept inventory, and proposes at most one retirement a week (a service left stopped, a dead device) with evidence the checker confirms. Read-only on every device. A draft that ships without commands. The rules file, the DONE checklist and the return fields. Loaded by home-infrastructure-orchestrator and its analyst and checker. Use when checking the home estate by hand. Not for household chores and dates; use household-method.
maturity: draft
---

# The weekly home infrastructure check

This skill is a draft: it ships without commands and is not yet runnable as is, because the owner grants the read-only commands privately once they are audited.

This skill extends `personal-workstream`. Read it, and `orchestration-workstream`, from `~/.claude/skills/<name>/SKILL.md` if they are not loaded.

## The sources

- The read-only health commands the rules file lists, or the exports it names (files a command or a device wrote earlier). This repository ships no command and grants none: the owner grants each one to the analyst and checker outside it. A command or export that cannot be read is a `source` item in state `missing` with the error's first line.
- The latest report of the owner's local job monitor, if there is one (whatever checks that each scheduled job produced its output), at the path the Context names. A report older than two days is `stale`.
- The inventory (what should be running, and where) and the incident notes the Context binds, read only.

Nothing here changes a device. Only read commands are run; a restart, stop, removal or configuration change is never made. A fix is a proposal the owner makes.

## The rules file: `HOME-INFRA-RULES.md`

The owner's. It holds: the hosts and what runs on each, the read-only commands or exports to use for each, the thresholds, the known exceptions (services stopped on purpose), what must never be proposed for retirement, any workload that must never run at home (data a work agreement keeps off home hardware, for example), and the standing lessons (settings that must stay as they are because changing them broke something before). Host names, addresses, products and commands live in this file, never in this skill. An invented example line: `host-a: file storage, backups; storage alert at 85 percent; never retire: backups`.

## Method

1. Run the listed read-only commands, or read the listed exports; read the job monitor's report and the inventory.
2. Flag: a service down or restarting, storage over threshold, a job the monitor says produced nothing, a device the inventory does not know, a service the inventory lists and nothing shows, a setting that contradicts a standing lesson.
3. Pick at most one retirement candidate: the item down longest with nothing depending on it, not on the never-retire list. Evidence: since when, what depends on it (the inventory, the monitor's registry), what retiring it frees.
4. Write `runs/<date>/HEALTH.md`: one line per host (fine, or what needs attention), the flags, the one proposal with its evidence and the exact steps the owner would take.

## DONE (the orchestrator checks each item and cites its evidence)

1. Every command or export the rules list was read, or its failure is recorded.
2. The job monitor's report was read and its date stated, or the rules say there is none.
3. Every flag cites the output or report line it rests on.
4. At most one retirement is proposed, and the checker (`home-infrastructure-checker`) confirmed it: PASS.
5. Nothing was changed on any device: the Run log shows only read commands.
6. Nothing the rules forbid at home appears among what runs, or it is the first line of the report.

## The return here

`items` with tests `source`, `host`, `service`, `job`, `device` (states `ok`, `attention`, `not-found`, and `missing` for a source), `extra.proposal` (`{item, since, depends_on, frees, steps, evidence}` or null).

## Later tools

- `home-infra-pull`: a `prepare:` that runs the owner's listed read commands and copies their outputs and the job monitor's report into the Run folder, so the session needs no network route and no command grant.
- `home-infra-check`: compute DONE items 1, 2 and 5 from the Run folder.
