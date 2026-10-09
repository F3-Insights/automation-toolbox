---
name: toolbox-audit-workstream
description: What is specific to a toolbox-audit worker, on top of orchestration-workstream. The scan's sections, the finding shape with its key, evidence, rank and one fix, how to judge unused and duplicate candidates and an orchestrator's fit to the design pattern, how to rank by consequence, and the narrow fix rule the fixer works under. Carries the audit's scripts (scan, fix branch, check, record). Loaded by the toolbox audit's analyst, fixer and checker; not for a user request on its own. To run an audit, use toolbox-audit-orchestrator.
user-invocable: false
---

# Toolbox audit workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. What follows is only what the toolbox audit adds.

The subject is the machinery, not the owner's work: the departments, orchestrators, agents, skills and scripts of an agent toolbox laid out by department (`<department>/agents/<name>.md`, `<department>/skills/<name>/`, each command a script inside the skill that owns it), measured against the toolbox's own design (`CONTEXT.md`, the ADRs in `docs/adr/`, `TOOLBOX-DESIGN-SUGGESTIONS.md`) and the orchestrator design in the `orchestrator-scaffold` skill. The question is whether the toolbox is getting harder to run: things that break quietly, drift apart, leak something private, or pile up unused.

## The scripts

All four live in this skill's `scripts/` folder and need Python 3.11 with `pyyaml`. The toolbox checkout is the `repo` setting under `[toolbox-audit-workstream]` (or `--repo`, `--root`).

```bash
python3 ~/.claude/skills/toolbox-audit-workstream/scripts/toolbox_audit_scan.py --out RUN/scan.json
python3 ~/.claude/skills/toolbox-audit-workstream/scripts/toolbox_audit_fix.py open --run RUN
python3 ~/.claude/skills/toolbox-audit-workstream/scripts/toolbox_audit_fix.py verify --run RUN
python3 ~/.claude/skills/toolbox-audit-workstream/scripts/toolbox_audit_check.py AUDIT_FOLDER --run RUN
python3 ~/.claude/skills/toolbox-audit-workstream/scripts/toolbox_audit_fix.py commit --run RUN
python3 ~/.claude/skills/toolbox-audit-workstream/scripts/toolbox_audit_record.py --run RUN --folder AUDIT_FOLDER
```

The scan and `fix open` run before the session; `fix commit` and `record` after it. `toolbox_audit_check.py AUDIT_FOLDER --precheck` says whether an audit is due.

## Where the facts are

`scan.json` in the Run folder. Never re-derive what it computed; read it, and open the files it names when a finding needs judgment. The scan reuses the toolbox's own `scripts/toolbox_check.py` for privacy and structure and the `orchestrator-scaffold` lint for orchestrators, so a finding from either is the same finding a commit would hit.

| Section | What it holds | What it needs from you |
|---|---|---|
| `check` | The toolbox check's structure failures: names that are not the file's, missing descriptions, duplicate names, relative paths to another skill | Confirm; the fix is usually one edit to the file named |
| `guards` | The toolbox check's privacy hits (a denylisted name, a home path, an IP address, an email address, a secret-shaped string), one item per file and kind, file only | Confirm; never copy the name or the value |
| `lint` | Frontmatter that does not parse; descriptions over 700 characters (agents error, skills warning); the scaffold lint of each orchestrator; drift from the agent file standard (kinds `template-sections`, `template-team`, `template-stages`, `template-steps`, warnings) | Usually confirm. A lint can be wrong for a case: then the finding is about the lint. Template drift is never fixable (below) |
| `drift` | A script path or `skills:` entry naming something that does not exist; a department the toolbox check does not cover; a department README out of step with its folder; an environment variable or settings table that `docs/settings.md` does not describe | Say which side is right, the reference or the thing referred to |
| `scripts` | Departures from ADR 0002: code outside a skill's `scripts/`, a hyphen in a script name, no docstring, a package used without its `# /// script` block, imports from outside its folder, no test, `--help` failing under plain `python3` | Confirm; a missing test is a warning, a script that cannot start is an error |
| `unused`, `duplicates` | Candidates, level `info` | Judge each: most are dismissed, a few are real |
| `teams` | Each orchestrator's agents and the skills they load | The pattern review below |
| `template` | Per department, its agents and how many drift from the agent file standard | The trend, week to week, in the report |
| `sections` | What the scan could not read | Goes under gaps, never silently dropped |

## The finding

Every error and warning in the scan ends in a finding (kept or dismissed); `info` candidates become findings only when you judge them real. One finding may cover several scan items with one cause and one fix (eight agents whose frontmatter fails for the same unquoted colon): list them all in `keys`.

```json
{"id": "lint:frontmatter:finance/agents/widget-reviewer.md", "rank": 3, "section": "lint", "level": "error",
 "title": "widget-reviewer's frontmatter does not parse, so a runtime reads no name or description",
 "where": "finance/agents/widget-reviewer.md", "evidence": ["scan.json lint:frontmatter:finance/agents/widget-reviewer.md",
 "finance/agents/widget-reviewer.md line 3: an unquoted ': ' in the description"],
 "fix": "Quote the description (fix rule)", "fixable": true,
 "keys": ["lint:frontmatter:finance/agents/widget-reviewer.md"], "files": ["finance/agents/widget-reviewer.md"],
 "owner_only": false, "state": "proposed"}
```

- `id`: the scan item's key when the finding is one item (so the ledger tracks it week to week), or the first key of the group; for a judgment of your own, `judgment:<section>:<slug>`, stable from week to week.
- `title`: one sentence a person reads first: what is wrong and what it costs.
- `evidence`: something a reader can open: a scan key, a file and line, a count.
- `fix`: one change, specific enough to act on: the file and the edit, the script, the test to add, the piece to retire. Where the right change is the owner's call, name the choice and set `owner_only: true`; do not choose for them.
- `fixable`: true only when the fix rule below allows the fixer to make it.
- `state`: `proposed`; `dismissed` with a `reason` when the scan item is not a problem. Only the orchestrator sets `fixed` (after the fixer and the checker) and `task`.

## The agent file standard

The standard is `references/agent-standard.md` in the `orchestrator-scaffold` skill (ADR 0003): every agent opens with what it owns, then `## Goal`, `## Inputs`, `## Context`, `## Approach`, `## Boundaries`, `## Done when`, `## Output` in that order; an orchestrator adds `## Team` after Approach and holds the five stages `### A. Gather` to `### E. Deliver` under Approach, each with its Goal, Who and Move on when; a sub-agent's Approach is principles, not a step script. The scan reports each departure per agent file and says nothing about whether the body is good.

Group template drift: one finding per department, its `keys` every template item of that department, its fix "bring these agents to the template", `owner_only: true`, `fixable: false`. Rank it with the lints, below anything that leaks, breaks or drifts toward a break. A rewrite of an agent body is a reviewed change on its own branch, never the fixer's.

## Ranking by consequence

Rank across sections, not within them; consequence is how the owner decides.

1. Anything that can leak or reach a person wrongly: a guard hit, contact pressure from the activity auditor, a script that writes without honouring a dry run.
2. Work that silently does not happen: a script that cannot start, a reference to a script or skill that does not exist, a department the check never covers.
3. Two pieces for one job, and spend with no deliverable.
4. Drift that will break the next change: README against folder, settings against `docs/settings.md`.
5. Lints and pattern gaps; then unused and duplicate weight.

## Judging candidates

- **Unused.** A name no other file mentions loads its description into every session and nothing calls it. Before calling it dead, remember what the scan cannot see: the owner invoking a skill by hand, a scheduler outside the toolbox. Say "no reference found" and propose retiring it only when its job is now done elsewhere (name where); otherwise dismiss.
- **Duplicates.** Judge on substance, not word overlap: two workers of one orchestrator that share a brief shape are a family, not duplicates. A real duplicate is two things that do the same job for the same caller; the fix names which one stays and what folds in.
- **The design pattern**, per orchestrator, from its agent file and its team in `teams`, against the `orchestrator-scaffold` skill's design: goal over steps; done computed by a check script with `--precheck`; workers load `orchestration-workstream` first and return the json block; one writer of state; a checker independent of the maker; writes to a live system only through a script in the finish step that honours a dry run; reads before the session; nothing about a client, person or machine in the toolbox. Report only what departs from it, with the line that shows it.

## The fix rule

The fixer may change, in the Run's worktree of the toolbox only, never the live checkout:

- the frontmatter `name` and `description` of `<department>/agents/<name>.md` and `<department>/skills/<name>/SKILL.md` files that exist;
- only to clear a lint the scan reported: frontmatter that does not parse (quote the value, wording unchanged), a description over 700 characters (shorten it, keeping what it does, when to use it, what it is not for, and the one briefing rule), a name that is not the file's;
- nothing else: not the body, not `tools`, `model`, `skills` or any other key, not a new or deleted file, no private name and no home path.

`toolbox_audit_fix.py verify --run RUN` checks a diff against the rule and reads the same private-name denylist files the toolbox check reads. `toolbox_audit_fix.py commit` refuses a diff that breaks the rule, a changed file with no finding marked fixed and passed by the checker, a commit message carrying a private name, and a worktree with no toolbox check or one that fails it. Both first prove the worktree is the Run's own, on its own `toolbox-audit/fixes-*` branch, never the live checkout, and every script writes a private name it meets as `(withheld)`. Everything outside the rule is a proposal, however small.
