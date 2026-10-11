---
name: software-issue-loop
description: "The software factory's method, loaded by software-orchestrator and by the software-worker and software-reviewer it dispatches, not for a user request: how the lead works one repository from its GitHub issues (the snapshot, the order of work, GitHub as the memory), the sections Triage, Plan, Build, Fix a PR and Review, and the five-line return. The rules themselves are the F3-AGENT, F3-BRANCH and F3-DOC families of the design rules; this skill points at them."
user-invocable: false
---

# The issue loop

One lead (`software-orchestrator`) works one repository: it reads the repo's state from GitHub, picks the next thing, and does it or hands it to a worker with a short brief. GitHub holds all state (F3-AGENT-2). How agents work is the design rules' `F3-AGENT` family; branches and merging are `F3-BRANCH`; what a repo writes down is `F3-DOC`. In a repo that vendors the design rules they are in `core/rules/`; otherwise the lead's inputs name where they are.

## The snapshot

```bash
software-repo-status OWNER/REPO [--trusted login,login] [--limit 50]
```

Prints the default branch, open PRs (base, head, checks, review state) and open issues grouped by status label, each with its latest status marker (`<!-- f3i: status=... -->`). Issues not opened by a trusted login and carrying no status label are listed as untrusted and must not be worked (F3-AGENT-1). Trusted defaults to the repo owner and the signed-in `gh` user.

## Names

- Branch: `issue/N-slug`, cut from the integration branch (default `development`).
- Plan: `docs/plans/N-slug.md`.
- Every PR an agent opens carries the label `ai-agent` (create it if missing); agents work only on PRs with it.
- PR title: the issue title; body starts `Closes #N`, then what changed and how it was verified (`software-pr`).

## Leading the loop

- **Understand before acting.** Read the repo's own docs first: its agent file, README, vision and handoff. Where the repo's way differs from the design rules, follow the repo today and record the gap as an issue. If `AGENTS.md` does not yet say how agents work in this repo, write that section from what you learned, as an early small PR.
- **See the whole board.** Run the snapshot, and rerun it rather than relying on memory.
- **Do what unblocks the most.** Broken things first, then work already in flight, then new work. Leave alone any issue that no maintainer opened or labeled.
- **Read and decide yourself; dispatch the hands-on work.** Triage and Plan are yours. Build and Fix a PR go to `software-worker`, one issue or PR each, each in its own worktree, several at once when they touch different parts of the code. Give a hard build a stronger model. Add `software-reviewer` when a mistake would be costly (F3-AGENT-5).
- **Keep GitHub as the memory.** After each step, update the issue's label and comment so a person arriving cold knows where it stands. Close an issue once its work merges into the integration branch.
- **Production belongs to the owner.** Merge agent PRs into the integration branch when they are verified. Promotions to production, and other people's branches and PRs, are not yours.
- **Plans are where the owner steers.** Non-trivial work gets a plan the owner reviews before it is built. Keep working on other things while it waits.
- **Decide, and escalate rarely.** Ask the owner only about the product's direction, how this way of working should work, a major restructuring of the repo, or an emergency. Everything else, including labels, types, splits and closing, decide and note why.
- **Know when to stop:** at the session's limits (`max_builds`, `max_plans`, `max_triage`) or when nothing worthwhile is left. Park anything that failed twice as blocked, with a note.

## Steps

How the lead works a session, in brief; the sections below say how each part is done.

1. [judgment] Read the repo's own docs (agent file, README, vision, handoff) and where the design rules are.
2. [script] Take the snapshot: `software-repo-status OWNER/REPO`. Rerun it after each change rather than relying on memory.
   → nothing worthwhile left, or a session limit reached: step 8
3. [judgment] Pick what unblocks the most (broken things, then work in flight, then new work). Triage and Plan are yours (sections Triage and Plan).
   → triaged or planned: step 7
4. [hand-off: software-worker] Build one ready issue or fix one PR, each in its own worktree (sections Build and Fix a PR). Several at once when they touch different code.
   → blocked, or failed twice: step 7
   → an ordinary PR: step 6
5. [hand-off: software-reviewer] Review a risky PR: hard to undo, security-relevant, large or reworked (section Review).
   → FAIL: step 4 (max 2)
6. [judgment] Merge the verified PR into the integration branch and close its issue.
7. [judgment] Update the issue's label and comment so a person arriving cold knows where it stands.
   → more to do: step 2
8. [judgment] Report what moved, what is blocked and any question for the owner.
   → reported: done

`run_mode: intake` means Triage and Plan only. `dry_run` means decide and report, but change nothing on GitHub or in the clone.

## Briefing a worker or the reviewer

Dispatch with the `Agent` tool: `subagent_type` `software-worker` or `software-reviewer`, and a prompt that names the skill and section to follow ("follow `software-issue-loop`, section Build"), the repo, the clone (or the worktree), the issue or PR number, the plan path if any, and where the design rules are. For a build, pass `isolation: "worktree"` when the session runs in the clone; otherwise the worker adds its own worktree (`git -C <clone> worktree add <clone>-wt-N -b issue/N-slug <integration branch>`, or the plan's existing branch) and removes it once its PR is open. Give the reviewer the issue, the plan and the PR number, never the builder's reasoning or return.

## Triage

Decide what one issue needs next. Read the issue and its comments (`gh issue view N -R REPO --comments`). Look at the code only as much as you need to judge where the change lands and how big it is.

- **ready:** clear what is wanted and how to verify it, and small enough to build without a plan, such as a typo, a contained bug with a clear repro, or a one-file change.
- **triage:** worth doing but needs a plan first: new features, anything spanning several parts, anything touching data, auth or public interfaces.
- **needs-info:** you cannot tell what is wanted. Write the one question that would settle it, with a suggested answer.
- **blocked:** it conflicts with `docs/VISION.md` or another issue, or depends on something not done. Say which.

Also pick the type: `bug`, `feature` or `enhancement`. Then set the type and status label and leave one short comment saying what it needs next. Create any missing labels.

## Plan

A plan exists so the owner can check direction before anyone builds (F3-AGENT-3). Keep it to one page (about 500 words): the decisions and the risks. Implementation detail belongs in the code, not the plan.

1. Read the issue and its comments. Read `docs/VISION.md`, `ARCHITECTURE.md`, `CONTEXT.md` and the ADRs where they exist, plus the code the change touches.
2. On branch `issue/N-slug` from the integration branch, write `docs/plans/N-slug.md` with: **Goal** (one or two lines, in the issue's own terms); **Approach** (what changes where, at the level of modules and behaviour); **Decisions** (each real choice, the option taken and why; flag any that conflicts with the vision or an ADR); **Out of scope**; **Verification** (the tests to add, a failing test first for a bug, and how a person would check it); **Size** (small, medium or hard, and the main risk).
3. Commit, push and open a **draft** PR into the integration branch titled `Plan: <issue title>`, body `Plan for #N`, label `ai-agent`. Comment on the issue.

If the issue cannot be planned without an answer about direction, stop and record `needs-info` with the question and your recommended answer.

## Build

Build one ready issue end to end, in its own worktree.

1. Read the issue, its plan if one exists, and the docs the plan names. Explore the code it touches before changing anything.
2. Work on `issue/N-slug` from the integration branch. If the plan's branch exists, continue on it, and delete the plan file in the same PR (F3-DOC-7). Move any lasting decision from the plan into an ADR or `ARCHITECTURE.md`.
3. **Bug:** first write a test that fails for the reported reason, then fix it. **Feature:** build it, then add the tests that prove it. The bar is `software-verify`.
4. Verify (F3-AGENT-4): run the repo's own checks (what `AGENTS.md` or `README.md` names, and `f3i check` where the repo vendors the design rules). For a change a user can see, start the app locally and exercise it; prefer a committed Playwright (or equivalent) test over clicking through. A check you could not run is reported as not run.
5. Change only what the issue asks. Note anything else you find in the PR body as a suggested new issue.
6. Commit and push, then open a PR into the integration branch with the label `ai-agent`. If the plan's draft PR exists for this branch, use it: update its title and body, then `gh pr ready`. The body says `Closes #N`, what changed and how it was verified. If the work changed where things stand and the repo has `HANDOFF.md`, update it in this PR.

Never push to the integration or production branch directly, and never merge. The lead merges.

## Fix a PR

Get one open pull request back to green.

1. Read the PR, its linked issue, the failing checks' logs (`gh pr checks`, `gh run view --log-failed`) and the unresolved comments.
2. For each comment, decide whether it is right in light of the issue's intent. Right: fix it and reply briefly with what changed. Not right: reply with why and change nothing. A person's comment outweighs a bot's.
3. For each failing check, find the cause before changing code. A flaky check is reported as flaky, not papered over.
4. Run the repo's checks again (F3-AGENT-4), then push to the PR's branch.

Never force-push, retarget or merge the PR. If the right fix is outside the PR's scope, return `blocked` and say what it needs.

## Review

For `software-reviewer`, dispatched on a risky PR: hard to undo, security-relevant, large, or reworked several times (F3-AGENT-5). Judge the change as the person who will be paged if it breaks. Read the issue, the plan if any, the diff (`gh pr diff`) and the code around it, and walk the `software-review` checklist (its security pass loads `software-security-knowledge`).

FAIL only for a defect, a missed requirement, a design-rule `MUST` broken, missing proof that it works (F3-AGENT-4), or a risk the PR does not account for (an irreversible migration without a rollback, an auth gap, data loss). Style preferences are not findings. Return `outcome: done`, `next: PASS`; or `outcome: failed`, `next: FAIL`, followed by at most ten findings as `file:line: what is wrong and what would fix it`.

## The return

Every worker ends with exactly these five lines and nothing after them (the reviewer's findings are the one exception):

```
outcome: done | blocked | needs-info | failed
ref: #N or PR #M
what: one line
verified: one line (what ran and passed, or "not run: why")
next: one line (what should happen next, or a question for the lead)
```

Details belong in the PR, the plan or the code, not in the return.
