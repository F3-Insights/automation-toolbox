---
name: home-infrastructure-method
description: "How the owner's weekly home infrastructure check is made, on top of personal-workstream: only the read-only health commands or exports the owner's rules list, compared with the inventory, and at most one retirement a week with evidence the reviewer confirms. Read-only on every device; a draft that ships without commands. The Steps, Read the estate, the reviewer's Check the retirement proposal, and DONE. Loaded by personal-home-infrastructure-check and personal-reviewer. Use when checking the home estate by hand. Not for household chores and dates; use household-method."
maturity: draft
---

# The weekly home infrastructure check

This skill is a draft: it ships without commands and is not yet runnable as is, because the owner grants the read-only commands privately once they are audited.

This skill extends `personal-workstream`, which extends `orchestration-workstream`. Load both with the Skill tool if they are not loaded.

## Steps

For `personal-home-infrastructure-check`. `RUN` is `runs/<date>/` in the home folder, or the Run folder on a dry run.

1. [judgment] Orient. Read the rules file, `STATUS.md`, `QUESTIONS.md` and last week's report, so a proposal the owner declined is not proposed again.
2. [judgment] Set up `RUN` with `LOG.md`; log each command before running it and record its exit state.
3. [judgment] Read the estate (section Read the estate): each output saved under `RUN/source/`, one line per host, the flags, at most one retirement candidate, and `RUN/HEALTH.md` as a draft.
   → no proposal: step 5
4. [hand-off: personal-reviewer] Check the retirement proposal (section Check the retirement proposal), given the proposal, the saved outputs it rests on, the inventory, the job monitor's registry and the rules file only. Save its return as `RUN/review-proposal.md`. A FAIL drops the proposal; record why.
5. [judgment] Record. Write `HEALTH.md` in its final form, the questions in `QUESTIONS.md`, and `STATUS.md` (the proposal and its state, so next week knows).
6. [judgment] Close. Walk the DONE checklist below, citing the evidence for each item, and report: one line per host, the flags, the proposal and the reviewer's verdict or "none this week", each command run with its exit state, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The sources

- The read-only health commands the rules file lists, or the exports it names (files a command or a device wrote earlier). This repository ships no command and grants none: the owner grants each one to the session outside it. A command or export that cannot be read is a `source` item in state `missing` with the error's first line.
- The latest report of the owner's local job monitor, if there is one (whatever checks that each scheduled job produced its output), at the path the Context names. A report older than two days is `stale`.
- The inventory (what should be running, and where) and the incident notes the Context binds, read only.

Nothing here changes a device. Only read commands are run; a restart, stop, removal or configuration change is never made, even where a granted command has a subcommand that would. A fix is a proposal the owner makes.

## The rules file: `HOME-INFRA-RULES.md`

The owner's. It holds: the hosts and what runs on each, the read-only commands or exports to use for each, the thresholds, the known exceptions (services stopped on purpose), what must never be proposed for retirement, any workload that must never run at home (data a work agreement keeps off home hardware, for example), and the standing lessons (settings that must stay as they are because changing them broke something before). Host names, addresses, products and commands live in this file, never in this skill. An invented example line: `host-a: file storage, backups; storage alert at 85 percent; never retire: backups`.

## Read the estate

Done by `personal-home-infrastructure-check` itself.

1. Run the listed read-only commands, or read the listed exports; save each output under `RUN/source/` so the reviewer reads exactly what you read. Read the job monitor's report and the inventory.
2. Flag: a service down or restarting, storage over threshold, a job the monitor says produced nothing, a device the inventory does not know, a service the inventory lists and nothing shows, a setting that contradicts a standing lesson, and anything the rules forbid at home (first line of the report).
3. Pick at most one retirement candidate: the item down longest with nothing depending on it, not on the never-retire list, and not one the owner declined. Evidence: since when, what depends on it (the inventory, the monitor's registry), what retiring it frees, and the exact steps the owner would take, saying whether each is reversible.
4. Draft `RUN/HEALTH.md`: one line per host (fine, or what needs attention), the flags each with the output line it rests on, and the one proposal with its evidence and steps.

## Check the retirement proposal

For `personal-reviewer`, given the proposal, the saved outputs it rests on, the inventory, the job monitor's registry and the rules file, never the reasoning that picked it. Re-read the evidence yourself; you run nothing. PASS only when every line holds:

1. **Really down or unused** for as long as the proposal claims, on the saved outputs or the monitor's report.
2. **Nothing depends on it**: no inventory entry and no registered job names it.
3. **Not protected**: it is not on the rules' never-retire list, nor a known exception kept on purpose.
4. **Steps honest**: each step is one the owner could take, and says whether it can be undone.

Return the `orchestration-workstream` block with `workstream: "home-infrastructure-check"`: one `items` row with test `proposal`, `state` PASS or FAIL, `evidence` what you re-read, and `note` one line of why; on a FAIL, the fix in `findings`.

## DONE (the main agent checks each item and cites its evidence)

1. Every command or export the rules list was read, or its failure is recorded.
2. The job monitor's report was read and its date stated, or the rules say there is none.
3. Every flag cites the output or report line it rests on.
4. At most one retirement is proposed, and the reviewer confirmed it (section Check the retirement proposal): PASS, in `RUN/review-proposal.md`.
5. Nothing was changed on any device: `LOG.md` shows only read commands.
6. Nothing the rules forbid at home appears among what runs, or it is the first line of the report.

## The record of the Run

`items` with tests `source`, `host`, `service`, `job`, `device` (states `ok`, `attention`, `not-found`, and `missing` for a source), and the proposal (`{item, since, depends_on, frees, steps, evidence}` or none), as `LOG.md` records them.

## Later tools

- `home-infra-pull`: a `prepare:` that runs the owner's listed read commands and copies their outputs and the job monitor's report into the Run folder, so the session needs no network route and no command grant.
- `home-infra-check`: compute DONE items 1, 2 and 5 from the Run folder.
