---
name: decision-case-mining
description: Mine the owner's sent email into decision cases, each a real judgment call (an approval, a refusal, a price, a choice with reasons) cited to its Portal email id with the owner's reasoning quoted or left empty, and record them in the decision store. Owns decision_store.py, the case and playbook database the other playbook skills use. Use for "mine my sent mail for decisions", "add cases for spend approvals". Not for drafting rules from cases; use playbook-distilling.
allowed-tools: mcp__insights-portal__list_entities, mcp__insights-portal__get, mcp__insights-portal__email_bodies, Bash(python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py:*), Read, AskUserQuestion
---

# Mine decision cases

Extract decision cases from the owner's sent email into the decision store. A case is one real decision: the inbound situation, what the owner did, and the reasoning they stated. Cases are the ground truth every playbook rests on, so mine conservatively. This is the inverse of triage: read sent mail for decisions made, not received mail for obligations.

## Hard rules

1. **Every case cites its source.** Each case carries the Portal email id it came from. `decision_store.py add-case` refuses a case with no source; never work around that. If you cannot cite it, drop it.
2. **Decisions only.** A sent email is a case only if the owner made a judgment call: approved or rejected something, chose between options, set a price, declined a request, gave a direction with a reason. Logistics ("see attached", "works for me", scheduling confirmations) are not cases.
3. **Reasoning is quoted, never invented.** The `reasoning` field holds what the owner actually wrote, lightly trimmed. If they gave no reason, leave it null: a thin true case beats a rich invented one.
4. **Batch size.** At most about 50 cases per run, in one or two categories. Quality beats volume.

## The decision store

`python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py` (below, `decision_store.py`) keeps sources, cases, playbooks and bullets in one SQLite file, the setting `database` under `[decision-case-mining]` (or `--db`). Subcommands: `init`, `add-source`, `add-case`, `add-playbook`, `add-bullet` (each `--json` or `--file`), `stats`, `cases --category`, `sources [--type] [--category]`, `audit` and `export-playbook --category`. `audit` is the provenance check and must report 0 violations after every write session.

## Steps

### 1. Set up

Run `decision_store.py stats`. If the database does not exist, run `decision_store.py init` first. Note `cases_by_category`: continue under-populated categories rather than starting new ones, unless the owner says otherwise.

### 2. Pick the window and the category

Ask the owner which category to mine this run if it was not given. Starter categories, to refine as cases accumulate:

- `spend-approvals`: approve or reject purchases, invoices, expenses
- `pricing-and-scope`: what is offered, at what price, and what is left out
- `delegation`: what is handed to others and what the owner keeps
- `inbound-requests`: how unsolicited requests and introductions are answered
- `time-and-priorities`: what gets time and what is declined

### 3. Pull sent mail

```
list_entities(entity_type="email", filters={"direction": "sent", "since": "<ISO time, the window ago>"}, limit=100)
```

Scan the summaries for decision signals ("approve", "decline", "I think we should", "let's go with", "my recommendation", "the reason"). For each candidate, read the whole thread with `get(entity_type="email", id_or_query=<id>, detail="full")`: the thread gives the inbound situation and the owner's reply with its reasoning. Read enough of the thread to summarize the situation honestly. If the thread text looks cut short, fetch full bodies with `email_bodies(ids=[...])`, at most ten ids per call, because a larger batch can exceed the response limit and fail whole.

### 4. Record the cases

Each case names its email as an inline source, so one call records both (the source is upserted by type and id):

```
python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py add-case --json '[{
  "category": "spend-approvals",
  "situation_summary": "<what was asked, one to three sentences, names and amounts included>",
  "context_snapshot": {"client": "...", "amount": "...", "requester": "..."},
  "action_taken": "<what the owner did>",
  "reasoning": "<the owner's words, trimmed, or null>",
  "sources": [{"type": "email", "external_ref": "<Portal email id>", "url": "portal://email/<id>",
               "title": "<subject>", "locator": "<message id of the owner's reply>"}]
}]'
```

A list records many cases in one call, and `--file` reads the same JSON from a file.

### 5. Wrap up

Run `decision_store.py stats` and `decision_store.py audit`; the audit must report 0 violations. Report to the owner: cases mined per category, patterns you noticed (they become bullet candidates for `playbook-distilling`), and emails skipped because they held a decision but no reasoning to quote.

## When no one is present

Run by `playbook-orchestrator`, this skill asks nothing and writes nothing to the decision store: the category and window come from the brief, and the cases go to a file in the Run folder in the `add-case` shape above. `playbook-workstream` says how; the hard rules hold unchanged.
