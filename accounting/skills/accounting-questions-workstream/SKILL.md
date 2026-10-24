---
name: accounting-questions-workstream
description: "The job skill of accounting-questions, and the sections its accounting-worker and accounting-reviewer follow, not for a user request: answering routine accounting questions between closes. Covers the intake (Portal tasks the rules mark as accounting questions), the Steps, section Answer a batch (a coding or treatment citing the transactional-definitions rule and the ledger history, or an escalation naming the conflict), section Check an answer, rule proposals, the change set of task comments and the DONE checklist. For one coding question by hand, use transactional-definitions."
---

# Accounting questions

Every accounting question asked of the team gets an answer a person can act on, with the rule it rests on, or reaches the owner as a clear decision; every decision the owner makes becomes a rule, so the same question is not asked twice. `orchestration-workstream` is the conduct and the return block. The method for a coding decision is `transactional-definitions` (read, cite, escalate, write back, propose); the method for what the ledger holds is `erp-ledger-pull`. This skill adds the intake, the answer, the checks and done.

## Conduct

- **The rules file first.** `FINANCE-OPS-RULES.md` in the company's close workspace says which Portal tasks are accounting questions (a tag, a project, or both), who may be answered, the amount above which an answer needs the controller, and where the transactional-definitions file is. It overrides this skill.
- **Cite or escalate.** An answer names the rule (section and number) and shows the ledger history that agrees with it (JE ids, dates, amounts). No rule, two rules that disagree, or history that contradicts the rule: an escalation, with the two or three plausible treatments.
- **Answer, never act.** No entry is drafted for import, no ledger change made, no colleague messaged. An answer that needs an entry says so and names the close workstream that would draft it.
- **One question, one answer.** A task that holds two questions gets two answers.
- **Nothing reaches the Portal from the session.** The answers become `comment` ops in `RUN/changes.json`; `task-stack-apply` posts them in the Automation's finish step, after the session.

## Steps

The main agent (`accounting-questions`) runs these.

1. [judgment] Orient. `whoami`; read the rules file, then the transactional-definitions file in full, and the last Run's `rule-proposals.md` for owner answers to write back.
2. [judgment] Queue. Take the one task the inputs name, or list the open tasks the rules mark (`list_entities`, by tag or project). Write `RUN/queue.json`; cut it into batches of about ten.
   → nothing queued: step 6
   → one named task: step 3
   → otherwise: step 4
3. [judgment] Answer the one task yourself, following section Answer a batch, with `intacct-gl-detail`, `trial-balance` or `gl-normalize` for the ledger history.
   → answered: step 5
4. [hand-off: accounting-worker] Answer each batch (section Answer a batch, model opus), in parallel, briefed with the tasks, the rules file's path, the definitions file's path and the Month-End folder for ledger pulls. Save each return as `RUN/returns/<batch>.json` at once; a reply without its json block goes back once for it.
5. [hand-off: accounting-reviewer] Check every medium-confidence answer and every answer over the rules' amount (section Check an answer), with the answer file, the definitions file and the ledger pull it cites, never the worker's reasoning. A FAIL turns the answer into an escalation.
6. [judgment] Write `RUN/changes.json` in the `task-stack-workstream` shape with `"orchestrator": "accounting-questions"` and `dry_run` as this Run is: one `comment` op per answered task carrying the answer, and the escalations as `questions`. Write `RUN/rule-proposals.md`: each proposed rule or rule change with its evidence, and each owner answer from an earlier Run as a proposed rule, for the owner to approve into the definitions file.
7. [judgment] Close. Walk the DONE checklist into `RUN/done.md`, citing evidence per item, and report: tasks queued, answered, escalated and not accounting questions; the reviewer's verdicts; the rule proposals; and the escalations as one numbered list the owner can answer "1) ok 2) no", each with the recommended treatment.
   → reported: done

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

An escalation uses the definitions file's Escalations shape inside the same file: the conflict, the evidence, the two or three plausible treatments and the recommended one.

## Answer a batch

For an `accounting-worker` given one batch of tasks (or the main agent, for one named task). Read the rules file, then the definitions file in full, before the first question. You may run only `intacct-gl-detail`, `trial-balance`, `gl-normalize` and `mkdir -p`; read the Portal with `get`, `search` and `email_bodies`; write only answer files.

For each task: read it and its linked mail; restate the question in one line; find the rule; pull the GL detail that shows how the same kind of transaction was treated before; write `RUN/answers/<task id>.md` in the shape above, or an escalation. A question that is not about accounting (a payment status, a vendor's contact) gets a one-line note and no answer.

Return the `orchestration-workstream` block with `workstream: "accounting-questions"`: `items` with test `question` (item `portal://task/<id>`; state `answered`, `escalated` or `unclear`; `note` the confidence and the amount), `files` the answer files, `proposals` the new rules or rule changes for the definitions file (each with its evidence), and `extra.ops` holding one `comment` op per answered task in the `task-stack-workstream` change-set shape.

## Check an answer

The checklist for `accounting-reviewer`, per answer, from the answer file, the definitions file and the ledger pull it cites alone:

1. **The rule exists and says that.** The cited section and rule number are in the definitions file, and the rule, read in full, gives the answer's coding or treatment for this kind of transaction. "No rule covers this" is true when it is claimed.
2. **The ledger history re-derives.** Each JE id, date and amount cited is in the pull or the GL detail and shows the same treatment; no later entry in the cited window shows a different one.
3. **The amount threshold.** An answer over the rules' amount says it needs the controller's sign-off.
4. **Conflicts named.** Where two rules or the history disagree, the answer is an escalation naming both and the plausible treatments, not a choice between them.
5. **It answers the question asked,** in a form the asker can act on, with nothing drafted for import and no one messaged.

Return the `orchestration-workstream` block with `workstream: "accounting-questions-review"`: one `items` row per answer, `state` `PASS` or `FAIL`, `note` the numbered fixes.

## DONE (the main agent checks each item and cites its evidence)

1. Every queued task has an answer file, an escalation, or a note why it is not an accounting question.
2. Every answer cites a rule and ledger history; every escalation names the conflict and the plausible treatments.
3. Every medium-confidence answer, and every answer over the rules' amount, has the reviewer's PASS.
4. Every owner answer from an earlier Run is written back as a proposed rule.
5. `RUN/changes.json` holds the comment ops; nothing was written to the Portal or the ledger.

## Later tools

- `accounting-questions-queue`: pick the queued tasks in code from the rules' tag and project, before the session, so the precheck says NOTHING when there are none.
