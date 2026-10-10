# Roadmap

Where the toolbox stands, what is next, and what has not been proven yet. Design decisions, once made, are recorded in [docs/adr/](adr/).

## Where it stands

- **18 departments, 198 agents, 152 skills and 67 orchestrated workflows**, every agent on one template ([ADR 0003](adr/0003-agent-files-follow-one-template.md)).
- **222 plain Python scripts** inside the skills that own them ([ADR 0002](adr/0002-commands-live-inside-skills.md)), with **1,448 tests** on invented data and fake Portal and GitHub servers, all passing.
- **A link script** builds the flat install Claude Code reads, and git hooks keep it in step with the clone.
- **A pre-commit check**, `scripts/toolbox_check.py`, guards names, frontmatter, imports and secrets on every commit.

## Not yet proven

- The scripts are tested against invented data and fake servers, not against live Sage Intacct, Portal or GitHub accounts. Treat a first live run of any workflow as a supervised one.
- The chief of staff's cycle, the nightly sweep and the playbook pipeline have been tested against fakes, never end to end against a live Portal and scheduler.
- `home-infrastructure-method` and `health-routine-method` ship as method drafts without commands.
- Plugin packaging has not been checked with `claude plugin validate`.

## Next

1. **Workers record their state in files.** Each worker writes `state.json`, `result.json` and `result.md` in its own folder in the Run and returns a pointer; the orchestrator stays the only writer of shared state. The proposal is in [docs/design/worker-state-in-files.md](design/worker-state-in-files.md).
2. **A stage contract for every worker**: Inputs, Process and Outputs sections, checked by the toolbox audit.
3. **Context budgets per layer**, so an orchestrator and its workers stay within a known reading load.
4. **A root router file**: which piece to use for which request.
5. **Narrower tool grants.** Skills that allow any `python3` command will name their own scripts instead.
6. **Declared tool scope for every skill.** Each `SKILL.md` lists the tools and capabilities its scripts use (environment, files, shell, network) in `allowed-tools`, which also answers SkillSpector's least-privilege findings ([scan results](security/skillspector.md)).

## Later

- **Hooks per agent**, enforcing "write only in the Run folder" and "never send" in each orchestrator's frontmatter. This needs runtime support for passing hooks to sub-agents; the reasoning is in [TOOLBOX-DESIGN-SUGGESTIONS.md](../TOOLBOX-DESIGN-SUGGESTIONS.md).
- **A Codex compatibility pass**: plain wording in place of Claude-only tool names, a "without subagents, do this step yourself" line in every dispatch step, and a neutral skills folder linked into both runtimes.
- **Departments as Claude Code plugins**, each with a manifest that declares the departments it depends on.

Ideas and requests are welcome as GitHub issues.
