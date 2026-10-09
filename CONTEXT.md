# Context

The words this repository uses, and what each one means here.

**Department.** A top-level folder named for a business function: accounting, finance, strategy, reporting, projects, process-engineering, compliance, software, sales, marketing, learning, productivity, recurring-summaries, chief-of-staff, decision-playbooks, obsidian, toolbox-maintenance, personal. Everything in the repository belongs to exactly one department. There is no shared or common folder.

**Agent.** One Markdown file, `<department>/agents/<name>.md`, with frontmatter (`name`, `description`, `tools`, `model`, and optionally `color`, `skills`) and a prompt as its body. Claude Code runs it as a subagent, or as the main session with `claude --agent <name>`. A piece is an agent only when it needs its own context window, to run in parallel, a different model, independence or different tool access; otherwise it is a skill.

**Agent file standard.** The one template every agent follows ([ADR 0003](docs/adr/0003-agent-files-follow-one-template.md)): an opening sentence saying what the agent owns, then `## Goal`, `## Inputs`, `## Context`, `## Approach`, `## Boundaries`, `## Done when`, `## Output`. The templates are in the `orchestrator-scaffold` skill; the toolbox audit reports drift from them.

**Orchestrator.** An agent whose name ends in `-orchestrator`. It runs one workflow end to end by dispatching sub-agents and checking what they return. Its Approach is the five stages and it has a `## Team` section.

**Stage.** One of an orchestrator's five fixed parts of a Run: A. Gather, B. Plan & clarify, C. Build, D. Test & review, E. Deliver. Each states its Goal, Who does it and when to move on.

**Sub-agent.** Any agent that is not an orchestrator: an analyst, a writer, a checker, a reviewer, a keeper. Its Approach is the principles and judgment calls for its slice of the work, never the five stages or a step script.

**Worker.** A sub-agent as its orchestrator sees it: the agent dispatched for one slice of a Run.

**Checker.** A worker that reviews another worker's output from the output and its sources only, never the maker's reasoning, and returns PASS or FAIL with fixes.

**Skill.** A folder, `<department>/skills/<name>/`, holding `SKILL.md` and anything only that skill uses (scripts, templates, reference notes, worker prompts). A skill is a method: how a piece of work is done well.

**Loading a skill by name.** Agents and skills name the skills they need. In a cloned and linked install every skill, whatever its department, is at `~/.claude/skills/<name>/SKILL.md`, so a file may give that path as the place to read a named skill when it is not already loaded. A path into another department's folder is never used.

**Reference skill.** A skill that holds knowledge other skills load, such as a style guide or a file format, rather than steps to follow. It exists when two or more skills need the same reference. A reference used by one skill lives inside that skill's folder instead.

**Command.** A command-line program a skill or agent runs, such as `trial-balance`. Each is one plain script in the `scripts/` folder of the skill that owns it, its hyphens written as underscores: `trial-balance` is `erp-ledger-pull/scripts/trial_balance.py`, run as `python3 ~/.claude/skills/erp-ledger-pull/scripts/trial_balance.py`. Nothing is installed. A script imports only the standard library, a few named packages, and files in its own folder ([ADR 0002](docs/adr/0002-commands-live-inside-skills.md)).

**Run.** One execution of an orchestrator, and the folder it works in. Whatever starts the orchestrator (a person at the terminal, or a scheduler) creates the Run folder and passes its path; the orchestrator writes its drafts, change sets and report there.

**Automation.** A saved, scheduled way to start one orchestrator: when it runs, with which inputs, and which commands run around the session. The **prepare** step runs commands before the session (pulling data, picking a queue) so the agent starts with facts in hand; the **finish** step runs commands after it (applying an approved change set, filing a note), so writes happen in code the owner can trust rather than inside a model turn. Any scheduler can play this role; the files here never depend on a particular one.

**Context.** A small file of inputs one Automation passes to an orchestrator: the folders, rules files and ids for one client, engagement or company. It lets the same orchestrator serve many clients without any client detail living in this repository.

**Rules file.** A Markdown file the owner keeps beside the work (for example `MONTH-END-RULES.md`, `BD-RULES.md`, `TASK-STACK-RULES.md`) holding that owner's thresholds, folders and preferences. Skills say what a rules file must contain; the file itself is never part of this repository.

**Change set.** A file of proposed writes (create, edit, complete, cancel) an orchestrator leaves for the finish step to apply after the owner approves, so no model writes to a live system directly.

**Model tiers.** Agents name a model in their frontmatter. `sonnet` is used for bulk reading and routine work, `opus` for most building and reviewing, and `fable` for the final sign-off or the hardest judgment, where the strongest available model is worth its cost. Substitute your own models freely.

**Owner.** The person the agents work for. Anything specific to one owner (their voice guide, their profile, their folders) is a setting outside this repository, never a fact written into it.

**Owner settings.** `~/.config/f3i-toolbox/settings.toml`. Skills name a setting (`voice_guide`, `engagements_dir`) instead of a path. A skill whose setting is missing says what it needs and stops. Every key the scripts read, and every environment variable, is in [docs/settings.md](docs/settings.md).

**Needs.** What a piece requires to run beyond Claude Code: nothing, the Insights Portal MCP server, Sage Intacct, a command, or an owner setting. Every department README lists it.
