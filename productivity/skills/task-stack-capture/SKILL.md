---
name: task-stack-capture
description: "Method loaded after orchestration-workstream and task-stack-workstream by the task-capture agents, not for a user request: capturing one source item (a spoken commitment the time study found unkept, a line in the quick-capture inbox, any captured note) into the owner's Insights Portal task stack. Decide whether it is an action the owner owes and whether a task already holds it; if not, propose one task-stack-apply create op carrying the item's source key, filed, titled, owned and dated the clarify way, or ask one question. For the pass, start task-capture-orchestrator."
---

# Capturing a commitment

This skill is the method. `orchestration-workstream` is the conduct and the return block; `task-stack-workstream` is the task stack's rules (read only, the owner's own tasks, the change-set op shape); `task-stack-clarify` is how a task is filed, titled and dated. Read them first, at `~/.claude/skills/<name>/SKILL.md` if they are not loaded. The owner's `TASK-STACK-RULES.md` wins over all of them.

## The standard

Each source item ends in exactly one of four places, and a reader of the item and the record would agree with the choice:

- **create**: a new task, written as the owner would write it, verb first, filed, owned and dated, so the clarify pass has nothing left to do with it;
- **exists**: a task already holds this commitment, open or recently done; that task is the answer and no second one is made;
- **skip**: not an action the owner owes (a remark, a wish, another person's commitment, done already, overtaken);
- **ask**: only the owner can say, as one line they can answer "ok" or with a word.

A missed commitment costs the owner a broken promise; a junk task costs them trust in the list. Weigh both. Something plainly theirs to do is captured; something doubtful is asked, not guessed.

## What an item gives you

- `text`: what was said or written. For the time study it is the assessor's line: the commitment, often with the quote, a recording hash and what was or was not seen after. For the inbox it is the owner's own words.
- `quote`, `to`, `by`, `domain`, `why_not_seen` when the source has them; `date` the day it was said or written.
- `already`: a task already carries this item's marker. Then the decision is `exists` with that task; nothing else to read.
- `candidates`: the owner's tasks whose titles are close, open or closed in the last 60 days, with a score. A hint, not a verdict: read the likely ones.
- `domain_hint`: the Portal domain the source named, with its catch-all project.

## The decisions, in order

1. **Is it the owner's action?** A commitment is something the owner said they would do ("I'll send it today", "let me look at the file"), or a line they wrote to themselves. Not one: something someone else said they would do (that is a WAITING on them: say so in `findings` for the follow-up loop, decision `skip`), a wish or an opinion, a household remark with no action the task list should carry, a question they asked. The assessor's words around the quote say who acted; trust the quote over the gloss.
2. **Is it already done or overtaken?** The time study often says what it saw after ("Seen, same day", "a new revision exists"). Seen done, or the moment has passed (the call was that day, the event is over): `skip`, with the reason. Partly seen: capture the part not seen, if it still matters.
3. **Does a task already hold it?** Read each likely candidate (`get`) and, when none fits, `search` the item's key words (the counterparty, the deliverable). The same commitment, same owner, is `exists` with that task's `portal://task/<id>`, even when the wording differs, and even when the task is done. Different numbers, periods or counterparties are different commitments. Email and meetings feed the list through other orchestrators, so a commitment from a recorded meeting may already be a task the meeting worker made.
4. **Write the task.** As `task-stack-clarify` says for project, title, owner, dates and WAITING:
   - the project the record points at (the counterparty's open tasks, the domain the source named), else the domain's catch-all project (`domain` in the op instead of `project`), never another client's domain;
   - a title that starts with a verb and keeps the specifics (who, what, which period): "Send Dana the freight summary", not "Freight item";
   - owner: the owner (leave `owner` out; the apply fills the token's contact);
   - `due_date` only when the item or the record gives one ("today" on the item's date is that date; "by Friday" is that Friday). A promised date that has passed still goes in: the task is overdue, which is the truth;
   - `description`: the quote and where it came from (`ref`, the date, the recording hash), so the owner recognises it;
   - `source`: the item's `key`, always. It is the marker that makes a re-run find this task instead of making another.
5. **Ask** when the domain is unclear (two clients plausible), when you cannot tell whether it is their action or still wanted, or when it would be a task for someone else. Offer your best choice: "Capture 'Send the pallet forecast to the controller' under Acme Finance? Or skip."

## What you propose

One `create` op per item you capture:

```json
{"id": "b1-1", "op": "create", "title": "Send Dana the inventory summary",
 "domain": "<domain uuid>", "due_date": "2030-03-04", "source": "said-not-seen:0a1b2c3d4e5f",
 "description": "\"I'll get the summary over to her today.\" (said 2030-03-04 09:15, 2030-03-04#2)",
 "reason": "Said on 3/4 they would send it that day; no mail to her was seen", "confidence": "high"}
```

- `project` (a uuid) or `domain` (a uuid, for its catch-all project), never both guessed.
- `evidence` only when there is a Portal record of the commitment itself (a meeting note, an email): a `portal://<note|email|...>/<uuid>`, full uuid. A recording hash is not one; it goes in the description.
- Confidence: `high` when the item plainly is the owner's commitment and the project is plain; `medium` when you chose between projects or read the commitment from an assessor's gloss without a clear quote. Medium creates go to the checker.

## Items

`items` rows: `test` `capture`; `item` the item's key; `state` one of `create`, `exists`, `skip`, `ask`; `evidence` the task found or the record that decided it; `note` one line.
