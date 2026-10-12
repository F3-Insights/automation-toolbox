# Converting a department to a plugin

This is how the `software` department was converted, made general, so each department after it goes the same way. The target is [ADR 0004](adr/0004-a-department-is-a-plugin.md): one standalone plugin per department, one short main agent per job, one `<department>-reviewer`, at most one `<department>-worker`, the procedure in the job's skill under `## Steps`, and scripts as named commands in `bin/`. The `software` department is the worked example: read its six agents before you start.

Convert one department per branch. If the department needs a change in the runtime that launches its Automations (Sentinel), make it on a second branch in that repository. Each step below names its check; do not start the next step until the check passes.

## What the department looks like when it is done

```
<department>/
  .claude-plugin/plugin.json      name = the folder, a description, a version
  agents/
    <job-name>.md                 one main agent per job, from templates/main-agent.md
    <department>-reviewer.md      from templates/reviewer.md; read-only
    <department>-worker.md        from templates/worker.md; only where a job needs parallel or isolated slices
  skills/
    <job-skill>/SKILL.md          the job's ## Steps, its sections (each former specialist's brief and return), its checklists
    <copied skill>/               a shared skill copied in by the copy build, identical to its source
  bin/                            one wrapper per script, written by scripts/build_bins.py
  README.md
```

- **A main agent** is about 40 lines: an opening sentence, `## Goal`, `## Inputs`, `## How to work`, `## Done`, `## Never`, with `skills:` and `tools:` in its frontmatter and `Skill` among its tools. It is named for what it does, never `-orchestrator`. It is found by what it does: it holds the `Agent` tool or dispatches its department's worker or reviewer.
- **The reviewer** judges from the sources alone, never the maker's reasoning, against the checklist section its brief names, and returns PASS or FAIL with numbered fixes. It has no Write, Edit or bare Bash; the main agent writes any review file.
- **The worker** does one slice following the section its brief names and returns that section's block. It cannot dispatch.
- **A specialist** (any other agent) has no place in the pattern. Its know-how becomes a `##` section of the job's skill, run by the main agent itself, by the worker for parallel or isolated slices, or by the reviewer as a checklist where independence matters.
- **Nothing reaches another department.** A `skills:` entry names only this department's skills; an `Agent(...)` grant and a `[hand-off: ...]` step name only this department's worker or reviewer. A hand-off between jobs is a launch the owner makes, a filed task, or a file another job reads.

## The checklist

1. **Read before cutting.**
   - Read the department's design (its section of the migration plan, if it has one) and settle its open questions with the owner.
   - Note each Automation's sidecar: its agent, prepare, precheck, finish, rules and inputs.
   - Note the baseline from the runtime's trace: the last Runs' tokens, turns and time.
   - Check the owner's own folders (rules files, logs) for agent names that the conversion will change.

   Check: a written list of the jobs, the specialists each uses, and the names that change.
2. **The plugin skeleton.** Write `.claude-plugin/plugin.json`. Add the department to `shared/manifest.yaml` for the shared skills it needs, and run the copy build.

   Check: `python3 scripts/toolbox_check.py`.
3. **Commands.** Run `python3 scripts/build_bins.py <department>`, then rewrite every `python3 <path>` in the department's skills and agents to the command name, and every tool rule to `Bash(<command>:*)`.

   Check: `python3 scripts/build_bins.py --check <department>`, and the department's script tests (`python3 scripts/run_tests.py <department>`).
4. **Skills.** Give each job's skill its sections (each specialist's brief and return shape), its checklist sections and a `## Steps` list in the format Sentinel draws (`N. [script|judgment|hand-off: <department>-worker|ask] text`, branch lines `   → condition: step N|stop|ask|done (max N)`). Where two jobs shared one skill, give each a thin job skill of its own to hold its Steps; the shared conduct stays in the shared one. Start from [templates/skill.md](../templates/skill.md).

   Check: Sentinel's Steps parser reports no problems for each job's skill, and the toolbox audit's scan reports no `pattern-steps` or `pattern-handoff` item.
5. **Agents.** Write one main agent per job from [templates/main-agent.md](../templates/main-agent.md), then the reviewer from [templates/reviewer.md](../templates/reviewer.md) and the worker from [templates/worker.md](../templates/worker.md) (the worker only if a job needs parallel or isolated slices). Delete the specialists and the old main agents in the same commit; other departments' references to them follow in that commit. Keep the old names working where a script or record names them (an alias period) and update the department README.

   Check: `python3 scripts/toolbox_check.py`, that nothing in the repository names a deleted agent, and that the toolbox audit's scan reports the department clean (below).
6. **The runtime's config on the machine** (back it up first):
   - the overlays move to the new names, with `subagents:` set to the worker and reviewer and tools set to named commands;
   - each Automation's `agent:`, its script paths (now commands) and its folder name follow;
   - an old owner field becomes `for_owner:`.

   Check: `sentinel agents`, each Automation's preview shows no missing item, and How it works draws each job.
7. **Dry run each job,** launched by the owner. Read its trace for tool calls refused or failing, whether the reviewer and worker were dispatched as the Steps say, whether the check passed, and tokens, turns and time against the baseline.
8. **Live run each job** once, on a real but low-stakes input. The old agents are already gone (step 5); if a live run fails, fix forward or revert the branch.
9. **Write it down.** Update the department's README, the getting-started guide, the record of what was renamed, and Sentinel's docs if it needed an engine change. Then merge.

A department is done when every job has passed a dry run and a live run and the audit reports it clean.

## The audit's view

The toolbox audit judges each department by the pattern it is on: a department with `.claude-plugin/plugin.json` by the plugin pattern, every other one by the agent file standard ([ADR 0003](adr/0003-agent-files-follow-one-template.md)). Run its scan from the toolbox audit's skill (`toolbox_audit_scan.py --root <toolbox checkout>`) and look for items whose `where` starts with the department:

| Kind | What it means |
|---|---|
| `check/plugin` | The manifest, `bin/` against the scripts, or a command run by a path, from the toolbox check |
| `lint/pattern-main` | A main agent missing Goal, Inputs, Done or Never, over about 60 lines, named `-orchestrator`, with no `skills:`, without `Skill`, or with bare `Bash` |
| `lint/pattern-steps` | A main agent whose skills hold no `## Steps`, or Steps Sentinel cannot read |
| `lint/pattern-handoff` | A step that hands off to anything but the department's worker or reviewer |
| `lint/pattern-reviewer`, `lint/pattern-worker` | A reviewer that can write, or a worker that can dispatch |
| `lint/pattern-role` | A specialist left over: neither a main agent nor the reviewer or worker |
| `lint/pattern-department` | No reviewer, or no main agent |
| `lint/pattern-script-path` | A script run by its path rather than its command |
| `drift/cross-department` | A `skills:` entry or `Agent(...)` grant naming another department's piece |
| `drift/copy` | A copied skill that differs from its source in `shared/skills/` (edit the source, rebuild the copies) |
