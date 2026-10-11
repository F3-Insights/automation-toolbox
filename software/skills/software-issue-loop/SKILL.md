---
name: software-issue-loop
description: "Reference loaded by software-orchestrator and its workers, not for a user request: the shared facts of the issue loop (inputs, branch names, the five-line worker return) and repo_status.py, which prints a repository's open issues and pull requests as one compact page. The rules themselves are the F3-AGENT and F3-BRANCH families of the design rules; this skill only points at them."
user-invocable: false
---

# The issue loop

One lead (`software-orchestrator`) works one repository: it reads the repo's state from GitHub, picks the next thing, and hands it to one worker with a short brief. GitHub holds all state (F3-AGENT-2). How agents work is the design rules' `F3-AGENT` family; branches and merging are `F3-BRANCH`; what a repo writes down is `F3-DOC`. In a repo that vendors the design rules they are in `core/rules/`; otherwise the lead's inputs name where they are.

## The snapshot

```bash
python3 ~/.claude/skills/software-issue-loop/scripts/repo_status.py OWNER/REPO [--trusted login,login] [--limit 50]
```

Prints the default branch, open PRs (base, head, checks, review state) and open issues grouped by status label, each with its latest status marker (`<!-- f3i: status=... -->`). Issues not opened by a trusted login and carrying no status label are listed as untrusted and must not be worked (F3-AGENT-1). Trusted defaults to the repo owner and the signed-in `gh` user.

## Names

- Branch: `issue/N-slug`, cut from the integration branch (default `development`).
- Plan: `docs/plans/N-slug.md`.
- Every PR an agent opens carries the label `ai-agent` (create it if missing); agents work only on PRs with it.
- PR title: the issue title; body starts `Closes #N`, then what changed and how it was verified.

## The worker return

Every worker ends with exactly these five lines and nothing after them:

```
outcome: done | blocked | needs-info | failed
ref: #N or PR #M
what: one line
verified: one line (what ran and passed, or "not run: why")
next: one line (what should happen next, or a question for the lead)
```

Details belong in the PR, the plan or the code, not in the return.
