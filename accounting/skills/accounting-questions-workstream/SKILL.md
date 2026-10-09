---
name: accounting-questions-workstream
description: Reference loaded by accounting-questions-analyst and accounting-questions-orchestrator, not for a user request; what answering routine accounting questions between closes adds to orchestration-workstream. Covers the intake (Portal tasks the rules mark as accounting questions), the answer shape (a coding or treatment citing the transactional-definitions rule and the ledger history, or an escalation naming the conflict), rule proposals and the DONE checklist. For one coding question by hand, use transactional-definitions.
---

# Finance operations workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. The method for a coding decision is `transactional-definitions` (read, cite, escalate, write back, propose); the method for what the ledger holds is `erp-ledger-pull`. This skill adds only the intake, the answer and done.

## Conduct here

- **The rules file first.** `FINANCE-OPS-RULES.md` in the company's close workspace says which Portal tasks are accounting questions (a tag, a project, or both), who may be answered, the amount above which an answer needs the controller, and where the transactional-definitions file is. It overrides this skill.
- **Cite or escalate.** An answer names the rule (section and number) and shows the ledger history that agrees with it (JE ids, dates, amounts). No rule, two rules that disagree, or history that contradicts the rule: an escalation, with the two or three plausible treatments.
- **Answer, never act.** No entry is drafted for import, no ledger change made, no colleague messaged. An answer that needs an entry says so and names the close workstream that would draft it.
- **One question, one answer.** A task that holds two questions gets two answers.

## The answer

`RUN/answers/<task id>.md`, read by a person who asked a short question:

```
Question: <the question as asked, one line>
Answer: <the coding or treatment, one or two sentences>
Rule: <file section and rule number>, or "no rule covers this"
Ledger: <JE ids, dates and amounts that show the same treatment; or the history that conflicts>
Confidence: high | medium
Needs: <nothing | the controller's sign-off (over the rules' amount) | the owner's decision>
```

## The return here

The shared block with item test `question` (item: `portal://task/<id>`; state `answered`, `escalated` or `unclear`), `files` the answer files, `proposals` the new rules or rule changes for the definitions file (each with its evidence), and `extra.ops` holding one `comment` op per answered task in the `task-stack-workstream` change-set shape.

## DONE (the orchestrator checks each item and cites its evidence)

1. Every queued task has an answer file, an escalation, or a note why it is not an accounting question.
2. Every answer cites a rule and ledger history; every escalation names the conflict and the plausible treatments.
3. Every medium-confidence answer, and every answer over the rules' amount, has the checker's PASS.
4. Every owner answer from an earlier Run is written back as a proposed rule.
5. `RUN/changes.json` holds the comment ops; nothing was written to the Portal or the ledger.

## Later tools

- `accounting-questions-queue`: pick the queued tasks in code from the rules' tag and project, before the session, so the precheck says NOTHING when there are none.
- Run `task-stack-apply` (`python3 ~/.claude/skills/task-stack-workstream/scripts/task_stack_apply.py`) after the session so the comment ops post the answers.
