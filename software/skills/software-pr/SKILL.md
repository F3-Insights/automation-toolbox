---
name: software-pr
description: "How a change is packaged for review: branch naming, commit shape, and a pull request body a reviewer can act on (the problem, the change, the evidence, the risk, how to check it by hand). Use when writing a PR body or a commit for a change, in the software factory or by hand. For the prose itself use unslop-technical; for release notes, software-release-orchestrator."
---

# Packaging a change

## Branch and commits

- In the software factory: `software-factory/issue-<n>-<slug>`, made by `software-factory-worktree`. By hand: the repo's own convention, else `<kind>/<short-slug>`.
- Stage files by name. Commits are imperative ("Fix ISO week date parsing"), with a body that says why. One commit per logical step; the fix and its tests may be one commit.
- Never commit generated files, secrets, local config or anything the repo ignores.

## The pull request body

Write it to the file the brief names, in this shape:

```markdown
## Problem
<the issue in two or three sentences, linking it: Fixes #42>

## Change
<what changed and why this way, in a few bullets; name anything deliberately left out>

## Evidence
- Repro: `<command>`, failed before (exit 1), passes after
- Tests: <command> - <summary>; new tests: <list>
- Checks: lint, typecheck, build - pass (from the repo's declared commands)
- UI: before / after screenshots (paths), or "no visible change"

## Risk
<low | normal | one-way door>, and why. What could break, and where to look.

## Assumptions
<each place the issue was silent and what was assumed, so the reviewer knows what to read
closely; or "None">

## Check it by hand
1. <steps a person can follow in a minute>
```

Plain language, no marketing words, no emojis. The reviewer must be able to judge the change from the body and the diff alone.
