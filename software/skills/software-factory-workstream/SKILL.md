---
name: software-factory-workstream
description: "Reference loaded after orchestration-workstream by the software-factory agents, and the method for onboarding a repository to the factory. Covers working offline with no route to GitHub, one issue or one task at a time, the repo's own conventions over habit, reproduce before fixing, never touching the ledger, manifest or outbox, the return shape the agent file gives, SOFTWARE-FACTORY.md (the factory's contract), and onboarding: writing a repo's .software-factory/ commands.yaml and SOFTWARE-FACTORY-RULES.md on the onboarding branch, proven by running every command. Use when writing or changing a factory agent, or when a repo has no .software-factory/commands.yaml with a test command (or one needs revising) before software-factory-orchestrator works it. Not for fixing issues by hand; start software-factory-orchestrator. For the testing bar alone use software-verify; for a PR body, software-pr."
---

# Working in the software factory

This skill extends `orchestration-workstream`: follow its conduct. Load it if it is not loaded. What follows is only what the factory adds.

The software factory turns a repository's issues into verified, reviewed pull requests. `SOFTWARE-FACTORY.md` beside this file is the contract: the phases, the repo's `.software-factory/` files, the files that pass between phases, the ledger, the tools and the guards. Read it when you need a file's exact shape.

## Conduct in the factory

- **Always offline.** You have no GitHub access and must not try to get it: no `gh`, no `git push`, `fetch` or `pull`, no token. Everything GitHub said is in the sync snapshot your brief points to.
- **The repo's way.** Read its `CONTEXT.md`, `docs/adr/`, `CONTRIBUTING`, `AGENTS.md` or `CLAUDE.md` when present, and match its naming, idiom and test style. A recorded decision (an ADR) stands until a new one replaces it; if a change needs to break one, stop and say so.
- **Reproduce before fixing.** No fix without a failing test or a recorded command first (`software-verify`).
- **One thing.** Change only what the issue needs. Note anything else you notice; don't fix it.
- **No bookkeeping.** The state you never write is the ledger, the manifest and the outbox.
- **Commands.** Prefer the repo's declared commands.

## The return in the factory

Each factory agent file gives its own return block (the builder's outcome and head SHA, the reviewer's verdict, the triager's classifications). Return that shape: its fields are the factory's domain fields, which the orchestrator reads at the top level of the block. Every field present; lists may be empty; no prose inside the block that the orchestrator would have to interpret.

## Onboarding a repository

The factory cannot build in a repo until the repo says how to check itself. When the integration branch has no `.software-factory/commands.yaml` with a real `test` command, the session's only work is onboarding, the factory's issue 0: on branch `software-factory/onboard`, find the repo's commands, make them work offline from a clean worktree, write `.software-factory/commands.yaml` and `SOFTWARE-FACTORY-RULES.md`, and prove them with `python3 ~/.claude/skills/software-factory-workstream/scripts/software_factory_verify.py --commands-from head`. A person reviews and merges that pull request. The steps, the rules file's field lines and the proof are in `onboard.md` in this skill; read it before onboarding.
