# Templates

Start here to write a new agent or skill by hand. Copy a template, replace every `<...>`, and
delete the guidance lines. The standard behind them is [ADR 0003](../docs/adr/0003-agent-files-follow-one-template.md);
the full rules are in the orchestrator-scaffold skill's agent standard
(`references/agent-standard.md` in that skill), and
`orchestrator_scaffold.py generate` builds a whole orchestrator and its sub-agents from a spec.

| File | Use it for |
|---|---|
| [orchestrator-agent.md](orchestrator-agent.md) | An orchestrator agent: runs one job end to end through the five stages |
| [sub-agent.md](sub-agent.md) | A sub-agent: does one focused piece for an orchestrator |
| [skill.md](skill.md) | A skill: a written procedure an agent follows |
| [examples/](examples/) | A small worked example: one orchestrator and one sub-agent |

Nothing in this folder is installed: the link script reads only department folders.

## Agent or skill

Think of it as a manager and specialists: the orchestrator agent runs the job, sub-agents do
focused pieces, and skills are the procedures they follow. Make it a sub-agent when the work needs
at least one of these:

- its own focus, because there is a lot to read;
- to run in parallel with other work;
- a different model from its caller;
- independence from whoever made the work (a reviewer);
- different tool access from its caller.

Otherwise it is a skill. Agents hold a role and its judgment; skills hold the steps.

## The five stages

Every orchestrator's Approach is the same five stages, in order: **A. Gather**, **B. Plan &
clarify**, **C. Build**, **D. Test & review**, **E. Deliver**. Each says its goal, who does it,
and when to move on. Questions go to the owner once, in B. A failed review in D goes back to B,
at most twice. Nothing is sent or posted in E without a person.
