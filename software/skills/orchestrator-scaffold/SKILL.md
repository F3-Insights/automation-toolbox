---
name: orchestrator-scaffold
description: Build a new orchestrator (an agent that runs one recurring workflow end to end through sub-agents, a reviewer and a check tool) from a short spec instead of by hand, or lint one that exists. Holds the design the pattern follows, the agent file standard with its two templates (orchestrator and sub-agent), the rule for when a piece is an agent rather than a skill, and a worked example spec. Use for "build an orchestrator for X", "write a new agent" or "check this orchestrator against the design". How each worker behaves is orchestration-workstream; drift across the whole toolbox is toolbox-audit-orchestrator.
argument-hint: "[spec.yaml] or [lint orchestrator-name]"
---

# Building an orchestrator

`references/orchestrator-design.md` is the pattern: the engagement folder, the orchestrator, its workstreams, reviewer and keeper, the shared skills, the tools, the launcher, authority, models, done and questions to people. Read it before building. This skill turns the pattern into files in one pass, so the time goes into the parts that need judgment: the rules file, the check's real tests of done, and each agent's goal. A skeleton is never a finished orchestrator.

Use it at step 6 of the design's build checklist, after the rules and procedures are written, the workstreams are listed, and the department READMEs have been searched for what already exists. Lint every orchestrator, new or old, before its dry run.

## The agent file standard

Every agent, generated or written by hand, follows `references/agent-standard.md`, and starts from one of its two templates: `references/templates/orchestrator.md` or `references/templates/sub-agent.md`. In short:

- Frontmatter `name`, `description` (what it does, when to use it, when not, naming the sibling to use instead), `tools` (the narrowest set) and `model`.
- One opening sentence saying what the agent owns, never "You are an expert". Then `## Goal`, `## Inputs`, `## Context`, `## Approach`, `## Boundaries`, `## Done when`, `## Output`, in that order.
- An orchestrator's `## Approach` is five stages, `### A. Gather`, `### B. Plan & clarify`, `### C. Build`, `### D. Test & review`, `### E. Deliver`, each with its Goal, Who and "Move on when". Questions to the owner are batched in B; D's reviewer never sees the builder's reasoning and a failed review returns to B with the findings, at most two rounds; E never sends or posts without a person. A `## Team` section after Approach lists each sub-agent, what it is given and when it is dispatched.
- A sub-agent's `## Approach` is the principles and judgment calls for its slice and the skills it uses, never the five stages and never a step script.

**Agent or skill.** Make it an agent when it needs its own context window (a lot to read), to run in parallel, a different model, independence (a reviewer) or different tool access. Otherwise it is a skill, a written procedure an agent follows. Stage contents belong to the agent; skills hold the step-by-step procedures.

The toolbox audit's scan reports any agent file that drifts from the standard.

## 1. Write the spec

One YAML file that records every design decision before any file is written. `references/example-spec.yaml` is a complete worked example (Acme Components' widget review); copy it. Keys:

| Key | What it is |
|---|---|
| `name` | `<domain>-<thing>-orchestrator`, the agent's name |
| `domain` | Kebab slug; the check is `<domain>-check` |
| `department` | The department folder the agents and skills go in |
| `title`, `purpose`, `goal`, `standard` | Words for the agent and the launcher; `purpose` is one sentence, required |
| `not_for` | The description's last sentence, naming the sibling to use instead ("Not for X; use Y."); a spec without it warns |
| `work` | The folder-file prefix in capitals (`MONTH-END`; default the domain in capitals) |
| `periods` | `true` (default) for `{yyyy}/{yyyy-mm}/` period folders |
| `inputs` | The launch form, in order: `name`, `label`, `default`, `required`, `empty_means`, `pattern` (a regex the value must match), `description`. A `dry_run` input is always added |
| `record` | `system` (words), and `folder` (and `delivery`): `{param, label, description}`, a fixed input whose value is private and lives in the launcher |
| `workers` | New: `name`, `kind` (`workstream`, `reviewer`, `keeper`), `model`, `role`, `owns` (the opening sentence's "You own ..."), `skills`, `tools` (commands or rules), optional `description` and `not_for`. Existing: `{agent: <name>, kind, role, model}` |
| `skills` | `new` (`name`, `description`, `workstream: true` for a domain extension of `orchestration-workstream`) and `load` (existing skills the work uses) |
| `tools` | `existing` (commands the orchestrator runs) and `new` (`name`, `description`: stubbed as commands) |
| `done` | `check` (default `<domain>-check`), `scope` (the input passed as SCOPE), `options` (inputs passed as options), `tests` (each `name` and `text`, written as a block, not a `{...}` flow mapping), `skill` (the skill whose `scripts/` folder holds the check and the stubs; default the first new skill) |
| `authority` | `level` (`dry-run-only`, `propose`, `trusted`), `may`, `may_not` |
| `triggers` | `schedule`, `tz`, `precheck` (true: the check's `--precheck`), `cadence`, `events`, `manual` |
| `prepare`, `finish` | Commands the launcher runs before and after the session: argv lists, or `{argv, skip_on_dry_run}` |
| `locks` | One input that two Runs must not share at once (the folder, the repository) |
| `network` | `online` or `offline` (offline: the session has no route to the system of record) |
| `limits` | `max_turns`, `timeout_s` |

Nothing private goes in the spec: client names, folder paths and machine-specific rules belong in the launcher's settings, outside the toolbox.

## 2. Generate or write the files

The `orchestrator-scaffold` command, this skill's `scripts/orchestrator_scaffold.py`, does this in one step:

```
python3 ~/.claude/skills/orchestrator-scaffold/scripts/orchestrator_scaffold.py generate SPEC.yaml [--dry-run [--show]] [--update] [--launcher FILE --set PARAM=VALUE ...]
python3 ~/.claude/skills/orchestrator-scaffold/scripts/orchestrator_scaffold.py lint NAME [--launcher FILE] [--format json]
```

`--dry-run` prints every file it would write and the lint results, `--show` adds each file's text; always dry-run first. A file that exists is refused by name, and `--update` replaces it only while it still carries the scaffold's marker line. Any lint error writes nothing at all. The check script, the command stubs and the check's test go in the `scripts/` folder of the skill `done.skill` names (default the first new skill). The launcher's settings are printed, or written to `--launcher FILE` (outside the toolbox, with the owner's private settings), which needs every fixed input's value through `--set PARAM=VALUE`. `--root DIR` points it at another toolbox checkout.

The orchestrator and every new worker are filled from the two templates, so they meet the standard as generated: the orchestrator's Context carries the folder tables and which source wins, its Approach the five stages, its Team one row per sub-agent (objective, given, boundaries, returns, when dispatched, model), its Done when the check, and its Output the session report and status word.

Without the command, write the same files by hand from the spec:
- the orchestrator agent, from a copy of `references/templates/orchestrator.md`: each `{{slot}}` replaced, the check named under Done when, the authority pointer to `<WORK>-RULES.md` in the bound folder under Boundaries, the skills-from-file and one-command rules, and the dry run input;
- one agent per new worker from a copy of `references/templates/sub-agent.md` (workstreams load `orchestration-workstream` first, then the domain skill), and one `SKILL.md` per new skill;
- the check script `<domain>_check.py` in the `scripts/` folder of the skill `done.skill` names, with `--precheck` and `--record TEST:ITEM` (its evidence ledger written only through `--record`), and a test in `scripts/tests/` that includes a blank launch-form value;
- a stub per new tool;
- the launcher's settings (agent, folder, fixed inputs, Write and Edit on the folder, the form, prepare and finish, the schedule shipped disabled, the precheck with the folder written out), kept with the owner's private settings.

Every generated file carries a marker line. Write it goal-first, then delete the marker.

## 3. Lint

Check, on every generation and on any orchestrator before its dry run:
- an agent's description is at most 700 characters and its `name` equals its file name;
- no "follow the <x> skill" phrase in an orchestrator;
- no bare interpreter rule such as `Bash(python3:*)`;
- no launch input that the launcher fills itself, and no `{placeholder}` left in a precheck;
- no private name and no absolute home path in a toolbox file (run the repository's check);
- every `skills:` entry exists;
- every command in an agent's tools, prepare, finish and the precheck exists, or is generated in the same run.

## After generating

1. Write the rules file and procedures in the folder with the owner (the design's step 1).
2. Replace the check skeleton's tests with the domain's real ones, keeping the result's shape; build each stubbed tool; run the generated test and the whole suite.
3. Write each agent and skill goal-first, keeping the template's sections and their order, then delete its marker. A stage's detailed procedure goes in a skill the stage names, not in the agent file.
4. Point the launcher's prepare and finish steps at the scripts by path, review the launcher settings, and prove it with a dry run.
