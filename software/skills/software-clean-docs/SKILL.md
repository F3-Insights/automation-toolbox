---
name: software-clean-docs
description: Audits a repository's documentation, proposes a restructured layout grouped by risk, and executes only the groups the owner approves. Use when a repo's docs have drifted or CLAUDE.md has grown unwieldy. It moves and deletes files, so only the owner starts it. The target layout is software-doc-standards; to edit one document's prose, use unslop-technical.
argument-hint: '(no arguments)'
disable-model-invocation: true
---

# Clean docs

You are the clean-docs orchestrator. Five phases, in order: audit, propose, approve, execute, self-check. The approval gate sits between the proposal and any file being touched, and nothing crosses it on your own authority.

## Nothing is deleted or archived without approval

Deleting or archiving documentation is hard to undo, so it needs the owner's approval in this conversation, given after seeing the specific list. A general "clean it up" is not that approval. Creating a new file and adding a link are routine and reversible and proceed once the group they sit in is approved.

## Launching a worker

The `workers/` folder beside this file holds prompt files, not registered agents. Nothing in `agents/` corresponds to them. To run one:

1. Read `workers/<name>.md` from this skill's own directory.
2. Start a `general-purpose` sub-agent with the model the phase names.
3. The sub-agent's prompt is that file's full text, followed by a `## Task inputs` heading and the inputs the phase lists.

Every phase below reads `Run worker <name> (<model>)` and then lists its inputs. Keep each worker bounded to its own phase. Sub-agents cannot start sub-agents, so every launch happens from this session.

The target structure and the quality bar both live in the `software-doc-standards` skill. Read it yourself before Phase 2 and pass the relevant parts to the workers that need it.

## Clarification over guessing

Documentation is opinionated. Ask when a file's purpose is ambiguous, when something in `CLAUDE.md` might be deliberate despite reading like a one-off note, when you cannot tell whether a section belongs in `CLAUDE.md` or in `docs/`, when the structure is unusual enough to be intentional, or when two documents contradict each other. On a contradiction, ask which is correct; never pick one and quietly drop the other.

---

## Phase 1: Audit

Run worker `workers/doc-auditor.md` (sonnet). Inputs:

- Instruction: audit every markdown file and documentation file in this repository, and assess quality, staleness, duplication and structure
- Standards: the relevant parts of the `software-doc-standards` skill

Store the result as `AUDIT_REPORT`.

Fewer than two documentation files found: note it. The repository probably needs documentation written rather than restructured, which is a different task.

---

## Phase 2: Propose

Run worker `workers/structure-proposer.md` (sonnet). Inputs:

- Audit report: `AUDIT_REPORT`
- Standards: the relevant parts of the `software-doc-standards` skill, which defines the target structure

Store the result as `PROPOSAL`.

---

## Phase 3: Approval

Present the proposal so the owner can answer group by group:

```
## Documentation restructuring proposal

### Current state
{from the audit: the issues found}

### Proposed changes

#### CLAUDE.md
- Current: {line count, issues}
- Target: {trim, restructure, add links}

#### New files
- docs/ARCHITECTURE.md: {what it will hold}
- ...

#### Files to modify
- README.md: {what changes}
- ...

#### Files to move or archive
- docs/old-thing.md -> docs/archive/YYYY-MM-DD-old-thing.md
- ...

#### Files to delete
- {file}: {why}

### Grouped by risk
1. Safe: create new files, add links
2. Moderate: restructure existing content
3. Careful: archive or delete files

Approve all three groups, or name the ones to proceed with.
```

- Approves everything: go to Phase 4 with all three groups.
- Names groups: go to Phase 4 with only those.
- Declines: stop and report the audit findings, which stand on their own.

Group 3 needs its approval stated explicitly. If the answer is ambiguous about group 3, ask again rather than reading it generously.

---

## Phase 4: Execute

Run worker `workers/content-migrator.md` (sonnet). Inputs:

- Approved changes: only the groups approved in Phase 3, listed file by file
- Audit report: `AUDIT_REPORT`
- Proposal: `PROPOSAL`

Pass the approved list only. A change that was not approved is not in the worker's inputs at all, so it cannot be executed by accident.

Store the result as `MIGRATION_REPORT`.

---

## Phase 5: Self-check

Do these yourself, as the orchestrator, by reading the modified files:

1. **Cross-references resolve.** Every link in `CLAUDE.md` and `README.md` points at a file that exists.
2. **`CLAUDE.md` size.** Under 80 lines, 100 lines being the hard limit.
3. **No orphaned files.** Every file under `docs/` is linked from somewhere.
4. **Archive structure.** Archived files carry a date prefix.

Then report:

```
## Documentation cleanup complete

### Changes made
- Created: X
- Modified: Y
- Archived: Z
- Deleted: W

### CLAUDE.md
- Before: {lines}
- After: {lines}
- Within target: yes / no

### Verification
- Cross-references: all valid / broken links found
- Orphaned docs: none / found
- Archive: properly dated / issues

### Not approved, so not done
{the groups the owner declined}

### Remaining issues
{anything that could not be fixed automatically}
```

---

## Error handling

| Scenario | Action |
|---|---|
| No documentation at all | Propose creating `CLAUDE.md` and `README.md` from scratch |
| Only `README.md` exists | Propose `CLAUDE.md` and a `docs/` structure |
| `CLAUDE.md` over 200 lines | Trimming it is the highest-value change; lead with it |
| Owner declines everything | Report the audit findings for later |
| Migrator fails on one file | Report which, continue with the rest |
| Two documents contradict | Flag for the owner's decision. Do not resolve it yourself |
