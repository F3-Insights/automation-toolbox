# Templates

Start here to write a new agent or skill by hand. Copy a template, replace every `<...>`, and
delete the guidance lines.

Two patterns stand side by side while the departments convert (ADR 0003 as amended on
2026-10-11, and [ADR 0004](../docs/adr/0004-a-department-is-a-plugin.md)). A department whose
folder holds `.claude-plugin/plugin.json` is a plugin and follows the plugin pattern; every other
department follows the agent file standard until it converts. The toolbox audit judges each
department by the pattern it is on.

## The plugin pattern (a department with `.claude-plugin/plugin.json`)

Drawn from the software department's six agents. How to convert a department is
[docs/converting-a-department.md](../docs/converting-a-department.md).

| File | Use it for |
|---|---|
| [main-agent.md](main-agent.md) | One main agent per job (what one Automation runs): about 40 lines of goal, inputs, done and never; its procedure is the `## Steps` of its job's skill |
| [reviewer.md](reviewer.md) | The department's one `<department>-reviewer`: read-only, judges from the sources against the checklist section it is told to use |
| [worker.md](worker.md) | The department's one `<department>-worker`, only where a job needs parallel or isolated slices |
| [skill.md](skill.md) | A skill: a written procedure, with `## Steps` in Sentinel's format for a job's skill |

A main agent dispatches only its own department's worker and reviewer, and loads only its own
department's skills (a shared skill is copied in). Scripts run as named commands from the
plugin's `bin/` (`python3 scripts/build_bins.py <department>`), never by a path.

## The agent file standard (a department not yet converted)

| File | Use it for |
|---|---|
| [orchestrator-agent.md](orchestrator-agent.md) | An orchestrator agent: runs one job end to end through the five stages |
| [sub-agent.md](sub-agent.md) | A sub-agent: does one focused piece for an orchestrator |
| [examples/](examples/) | A small worked example: one orchestrator and one sub-agent |

The full rules are in the orchestrator-scaffold skill's agent standard
(`references/agent-standard.md` in that skill), and `orchestrator_scaffold.py generate` builds a
whole orchestrator and its sub-agents from a spec.

Every orchestrator's Approach is the same five stages, in order: **A. Gather**, **B. Plan &
clarify**, **C. Build**, **D. Test & review**, **E. Deliver**. Each says its goal, who does it,
and when to move on. Questions go to the owner once, in B. A failed review in D goes back to B,
at most twice. Nothing is sent or posted in E without a person.

Nothing in this folder is installed: the link script reads only department folders.

## Agent or skill

Make it an agent when the work needs at least one of these:

- its own focus, because there is a lot to read;
- to run in parallel with other work;
- a different model from its caller;
- independence from whoever made the work (a reviewer);
- different tool access from its caller.

Otherwise it is a skill. In the plugin pattern those needs are met by the department's worker
(parallel or isolated slices) and reviewer (independence); everything else a specialist did is a
`##` section of the job's skill, run by the main agent itself.
