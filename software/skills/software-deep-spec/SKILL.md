---
name: software-deep-spec
description: Writes a ten-dimension feature specification, researching best practice and the codebase first and reviewing each dimension with the owner before moving on. Use when a feature needs a written spec before anyone builds it. It writes a file into the repo, so only the owner starts it. Not for fixing filed issues; start software-factory-orchestrator.
argument-hint: '"feature description"'
disable-model-invocation: true
---

# Deep spec

You are the deep-spec orchestrator. Research, explore, sketch the test seams, write each of the ten dimensions interactively, review the whole, save.

## Launching a worker

The `workers/` folder beside this file holds prompt files, not registered agents. Nothing in `agents/` corresponds to them. To run one:

1. Read `workers/<name>.md` from this skill's own directory.
2. Start a `general-purpose` sub-agent with the model the phase names.
3. The sub-agent's prompt is that file's full text, followed by a `## Task inputs` heading and the inputs the phase lists.

Every phase below reads `Run worker <name> (<model>)` and then lists its inputs. Keep each worker bounded to the question its own phase asks. Sub-agents cannot start sub-agents, so every launch happens from this session, including the two that run in parallel in Phase 1.

The ten dimensions and the guidance for each live in the `software-spec-dimensions` skill. Read it yourself before Phase 2 and pass the relevant dimension's guidance into each write.

## Arguments

**Feature description** (required): a quoted string, for example `"combat system"`, `"user authentication flow"`, `"real-time notifications"`. Without one, print the usage line from the frontmatter and stop.

## What a spec contains, and what it does not

A spec holds decisions, in the language of the domain. It holds no file paths and no code snippets: both go stale within weeks and then mislead the person who trusts them. Name the module and its interface instead of the file that happens to hold it today.

One exception. Where a prototype produced a snippet that encodes a decision more precisely than prose can, a state machine, a reducer, a schema, a type shape, inline it inside the decision it belongs to and say in one line that it came from a prototype. Trim it to the decision-rich part; it is not a working demo.

## Clarification over guessing

A spec built on wrong assumptions is worse than no spec.

Ask when the feature description is vague, when you do not know the target users or the scale before writing the scalability dimension, when the scope boundary could sit in several places, when research turns up conflicting best practice, or when an integration point in the codebase is ambiguous. If writing one dimension reveals that a decision in an earlier one was wrong, surface it rather than writing around it.

The per-dimension loop exists so the owner can correct course early instead of discovering a wrong assumption in a finished document. Invite questions at each one.

---

## Phase 0: Setup

### 0.1 Save location

```bash
bash scripts/find-spec-dir.sh "{feature_name}"
```

The path is relative to this skill's own directory. It prints the spec directory, the filename and any existing spec for the same feature. The spec lands at `docs/specs/YYYY-MM-DD-{feature-name-kebab}.md`.

### 0.2 Project type

```bash
bash ~/.claude/skills/software-portfolio-review/scripts/detect_project_type.sh
```

`detect-project-type` is a command (listed in the department README). Store the output as `PROJECT_META`.

### 0.3 Orient

Read `CONTEXT.md` and `docs/adr/` at the repo root where they exist. Use their vocabulary for entities, states and operations throughout the spec, and do not re-litigate a decision an ADR already records. Where the feature requires superseding one, say so explicitly in the spec and name the ADR by number.

---

## Phase 1: Research and explore, in parallel

Dispatch both in a single message.

**`workers/research-agent.md` (sonnet).** Inputs: the feature description, and `PROJECT_META.language` / `PROJECT_META.framework`. It researches best practice, patterns and known pitfalls. Store as `RESEARCH`.

**`workers/codebase-explorer.md` (haiku).** Inputs: the feature description, `PROJECT_META`, and the domain glossary from `CONTEXT.md` where it exists. It maps integration points, existing data models and relevant patterns. Store as `CODEBASE_CONTEXT`.

---

## Phase 2: Sketch the test seams

Before writing any dimension, sketch the seams at which this feature will be tested. A seam is a place behaviour can be altered without editing code in place, which makes it the place a test can attach.

- Prefer a seam that already exists to a new one.
- Use the highest seam that still reaches the behaviour, so one test covers the most.
- Where a new seam is needed, propose it at the highest point you can.
- Fewer seams across the codebase is better. One is the ideal.

Present the sketch and confirm it with the owner before Phase 3:

```
## Test seams for {feature}

| Seam | Existing or new | What it lets a test assert |
|---|---|---|
| ... | ... | ... |

Do these match how you would test this? [Y / tell me what to change]
```

The confirmed seams are an input to every dimension that follows, and they are what the testing dimension is written against.

---

## Phase 3: Write the ten dimensions

For each dimension in order:

### 3.1 Write

Run worker `workers/spec-writer.md` (opus). Inputs:

- Dimension: the name of the dimension being written
- Feature: the feature description
- Research: `RESEARCH`
- Codebase context: `CODEBASE_CONTEXT`
- Test seams: the seams confirmed in Phase 2
- Previous dimensions: everything written so far
- Dimension guidelines: that dimension's section of the `software-spec-dimensions` skill
- Constraint: no file paths, no code snippets, except a prototype snippet that encodes a decision more precisely than prose

### 3.2 Present

```
## Dimension {N}/10: {name}

{drafted content}

---
Feedback? (approve / revise / skip as N/A)
```

### 3.3 Handle the answer

- **Approve**: save it and move on.
- **Revise**: feed the feedback back to `workers/spec-writer.md`, redraft, present again.
- **Skip**: mark the dimension `N/A` with a written reason. A dimension is never silently dropped; the reason is part of the spec, because a later reader needs to know it was considered rather than forgotten.

### The order

1. Functional requirements
2. UI and UX
3. Data model and schema
4. API design
5. Security
6. Scalability and performance
7. Deployment and infrastructure
8. Testing strategy
9. Edge cases and failure modes
10. Migration and backwards compatibility

Dimension 8, testing strategy, is written against the seams confirmed in Phase 2 and records three things:

- **What makes a good test here.** External behaviour only, never implementation detail. Say what counts as external behaviour for this feature.
- **Which modules get tested**, at which of the confirmed seams.
- **Prior art**: the tests already in this codebase that the new tests should look like, named by module and by the behaviour they assert, not by file path.

Some dimensions genuinely do not apply, UI and UX for a backend-only feature being the common case. Suggest `N/A` when you believe it, and let the owner decide.

---

## Phase 4: Review

Run worker `workers/spec-reviewer.md` (opus). Inputs:

- Feature: the feature description
- Full spec: all ten dimensions assembled
- Research: `RESEARCH`
- Codebase context: `CODEBASE_CONTEXT`
- Test seams: the seams confirmed in Phase 2

Present:

```
## Spec review

### Gaps
### Contradictions
### Scope creep
### Recommendations

Address these before finalising? [Y/n]
```

Yes: go back to the dimensions concerned and revise them through the same loop.

---

## Phase 5: Save

### 5.1 Assemble

```markdown
# Feature spec: {feature name}

> **Date**: YYYY-MM-DD
> **Status**: Draft
> **Repository**: {repo name}

## Summary
{two or three sentences}

## Test seams
{the table confirmed in Phase 2}

## 1. Functional requirements
...
## 2. UI and UX
{content, or "N/A: {reason}"}
...

## Open questions
{whatever the review left unresolved}
```

### 5.2 Write the file

Save to the path from Phase 0.

### 5.3 Report

```
## Spec complete

**Saved to**: {path}
**Dimensions**: X written, Y marked N/A
**Open questions**: Z
**Review**: {the reviewer's assessment}

Next: settle the open questions, then file the spec's work as GitHub issues for the software factory.
```

---

## Error handling

| Scenario | Action |
|---|---|
| No feature description | Print usage, stop |
| Research returns nothing useful | Note it, proceed on the codebase context alone |
| No relevant code exists | Greenfield feature. Say so; integration work will be needed |
| Owner stops mid-spec | Save what is written, status `INCOMPLETE`, list the dimensions not reached |
| Reviewer finds critical gaps | Present them, let the owner decide whether to fix or save as is |
| `docs/specs/` cannot be created | Save at the project root and say so |

---

Three parts of this skill, the seam sketch in Phase 2, the ban on file paths and code snippets, and the shape of dimension 8, are adapted from `skills/engineering/to-spec` in mattpocock/skills (MIT License, Copyright (c) 2026 Matt Pocock); see LICENSE in this folder.
