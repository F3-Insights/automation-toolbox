---
name: playbook-distilling
description: Distill one category's evidence (mined decision cases and recorded narration) into a draft playbook of typed, cited bullets (policy, principle, procedure, pitfall, escalation), with the conflicts between what the owner says and what they do on top, the gaps, the exceptions and a proposed risk tier, for the owner to ratify. Use for "draft the playbook for spend approvals", "distill the cases we mined". Not for mining cases; use decision-case-mining. Not for the owner's review; use playbook-ratification.
allowed-tools: Bash(python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py:*), Read, Write, AskUserQuestion
---

# Distill a playbook

Distill one category's evidence (mined cases and recorded narration) into a draft playbook of cited bullets, exported as Markdown for the owner to review and ratify. A playbook is a short set of cited rules for how the owner decides one category of matter; it becomes the owner's rule only when they ratify it.

## Hard rules

1. **One category per run.** Distil lazily and have a person validate it. Never bulk-extract.
2. **Every bullet cites its evidence.** Each bullet cites at least one case or one recording moment. `decision_store.py add-bullet` refuses an uncited bullet. A rule you cannot cite is dropped: an unattributable rule is worse than no rule.
3. **Bullets, not essays.** Each bullet is one small rule, concrete enough to act on ("approve recurring vendor payments under the agreed limit for Acme Components without re-verification"), not a mood ("be careful with payments").
4. **Conflicts are findings, not problems to smooth over.** Where what the owner says in narration and what they do in the cases disagree, write the conflict up. These are the most valuable review items.
5. **Status stays draft** until the owner approves it in review. Never activate a playbook yourself.
6. **One category per run, at most 25 cases.** "There was nothing new" is an honest result. Padding with restated old cases is worse than a short draft.
7. **A changed draft gets backtested.** Check the draft against the category's historical cases: for each case, would the draft have proposed what the owner did? Flag every regression for the owner; never apply a fix on your own.

## Steps

`decision_store.py` below is `python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py`; `decision-case-mining` describes it.

### 1. Gather the category's evidence

Run `decision_store.py stats`. Pick, or confirm with the owner, a category that has both cases and classified narration if possible. Then:

- Cases: `decision_store.py cases --category <cat>`.
- Narration: `decision_store.py sources --type recording --category <cat>`, then read each source's `raw_path` transcript (`recording-harvest` archives and classifies them).

### 2. Distill into typed bullets

From the evidence, derive 5 to 15 candidate bullets, each with a `kind`:

- `policy-ref`: a codified rule. If a rule is policy-shaped but no policy document exists, draft one (status DRAFT, evidence cited, gaps marked) as `policies/<slug>.md` beside the review draft, register it with `decision_store.py add-source` as a `manual` source with its sha256 hash, and cite it from the bullet.
- `principle`: the why. Dig beneath each decision rule to the weighing that produced it (what the owner was trading off, and why that side won). Where the owner's behaviour departs from what they say, the principle that licenses the departure is the most valuable thing to capture.
- `procedure`: the mechanics, usually from narration.
- `pitfall`: where a principle does not apply (an unusual pattern, a new counterparty).
- `escalation`: when to stop and ask the owner.

**Altitude, meaning how specific a bullet is, set per kind:**

- Principles are as general as possible: they must carry over to cases never seen. A named company or person in a principle is a defect.
- Procedures are legitimately specific: account numbers and system names are their content.
- Policies name a specific only when the name is the rule itself.
- **Demote instances to evidence.** State the rule at the altitude it actually holds, and leave the named party or amount in the cited case. ("Take an early-payment discount when it beats the return on idle cash", citing the case that carries "Northwind Traders, 2% for payment in ten days"; not "Pay Northwind early.")
- **Prefer roles to people.** "The designated approver", not a person's name: roles outlive staff and keep the playbook shareable. The person is in the cited case.
- **Altitude is earned.** Write faithful to the evidence (specific) and let a bullet earn generality as confirming cases accumulate, broadening it with a new bullet that supersedes the old and cites both the original and the new cases. Early generalization is a guess; generalization after several cases is a finding.
- **Err specific when unsure.** Too specific is safe (a gap the owner's questions will catch); too general is dangerous (it fires where it does not hold and the wrong thing is done).

For each bullet, record which cases, recording moments and policy documents support it. Separately list:

- **Conflicts**: what the owner says against what they do, citing both sides. Each resolves into either a policy fix or a stated principle; propose which.
- **Gaps**: missing policies or unanswered situations (candidates for the owner to record a narration on).
- **Exceptions**: one-off cases that should not generalize.

### 3. Risk tier

Propose a risk tier: `financial` (money moves; a person always approves), `high` (with a final human pass when a relationship is at stake), `medium`, or `low`. When in doubt, tier up.

### 4. Record the draft

```
decision_store.py add-playbook --json '{"category": "<cat>", "title": "<title>", "risk_tier": "<tier>",
  "human_final_pass": <true|false>, "status": "draft"}'
decision_store.py add-bullet --json '[
  {"playbook_id": <id>, "kind": "principle", "text": "<bullet>",
   "sources": [{"case_id": 12}, {"source_id": 4, "locator": "t=272"}]}
]'
```

### 5. Export for review

Run `decision_store.py export-playbook --category <cat>` and `decision_store.py audit` (0 violations). Write the export plus the Conflicts, Gaps and Exceptions sections to `<function>/drafts/<category>-playbook-draft.md` in the owner's playbook folder (the setting `playbooks_dir`), where `playbook-ratification` reads drafts. Tell the owner it is ready and flag the two or three items most worth their attention, conflicts first. The hand-off to `playbook-ratification` is one or two questions at a time, in queue order, each answerable in about three minutes of dictation.

Ratification is the owner's alone, because the playbook is their judgment.

## When no one is present

Run by `playbook-orchestrator`, this skill asks nothing and writes nothing to the decision store: the category comes from the brief, the evidence is the case files and the existing draft it is given, and the output is one proposal file in the Run folder. `playbook-workstream` says how; the hard rules hold unchanged.
