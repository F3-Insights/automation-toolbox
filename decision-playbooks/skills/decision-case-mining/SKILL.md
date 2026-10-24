---
name: decision-case-mining
description: Mine the owner's sent email into decision cases, each a real judgment call (an approval, a refusal, a price, a choice with reasons) cited to its Portal email id with the owner's reasoning quoted or left empty, and record them in the decision store. Owns decision-playbooks-decision-store, the case and playbook database the other playbook skills use. Use for "mine my sent mail for decisions", "add cases for spend approvals". Not for drafting rules from cases; use playbook-distilling.
allowed-tools: mcp__insights-portal__list_entities, mcp__insights-portal__get, mcp__insights-portal__email_bodies, Bash(decision-playbooks-decision-store:*), Read, AskUserQuestion
---

# Mine decision cases

Extract decision cases from the owner's sent email into the decision store. A case is one real decision: the inbound situation, what the owner did, and the reasoning they stated. Cases are the ground truth every playbook rests on, so mine conservatively. This is the inverse of triage: read sent mail for decisions made, not received mail for obligations.

## Hard rules

1. **Every case cites its source.** Each case carries the Portal email id it came from. `decision-playbooks-decision-store add-case` refuses a case with no source; never work around that. If you cannot cite it, drop it.
2. **Decisions only.** A sent email is a case only if the owner made a judgment call: approved or rejected something, chose between options, set a price, declined a request, gave a direction with a reason. Logistics ("see attached", "works for me", scheduling confirmations) are not cases.
3. **Reasoning is quoted, never invented.** The `reasoning` field holds what the owner actually wrote, lightly trimmed. If they gave no reason, leave it null: a thin true case beats a rich invented one.
4. **Batch size.** At most about 50 cases per run, in one or two categories. Quality beats volume.

## The decision store

`decision-playbooks-decision-store` keeps sources, cases, playbooks and bullets in one SQLite file, the setting `database` under `[decision-case-mining]` (or `--db`). Subcommands: `init`, `add-source`, `add-case`, `add-playbook`, `add-bullet` (each `--json` or `--file`), `stats`, `cases --category`, `sources [--type] [--category]`, `audit` and `export-playbook --category`. `audit` is the provenance check and must report 0 violations after every write session.

## Steps

1. [script] Run `decision-playbooks-decision-store stats`; when the database does not exist, run `decision-playbooks-decision-store init` first. Note `cases_by_category`: continue under-populated categories rather than starting new ones, unless the owner says otherwise.
2. [ask] Ask the owner which category to mine and over what window, if the request did not say (section Categories).
   → given: step 3
3. [judgment] Pull the window's sent mail and read each candidate's whole thread, by section Pulling sent mail. Keep only real decisions (hard rule 2).
   → no decision found: step 6
4. [script] Record the cases, each with its email as an inline source, by section Recording a case: `decision-playbooks-decision-store add-case --file CASES.json`.
5. [script] Run `decision-playbooks-decision-store stats` and `decision-playbooks-decision-store audit`.
   → the audit reports a violation: step 4 (max 1)
6. [judgment] Report to the owner: cases mined per category, the patterns noticed (they become bullet candidates for `playbook-distilling`), and the emails skipped because they held a decision but no reasoning to quote.
   → reported: done

## Categories

Starter categories, to refine as cases accumulate:

- `spend-approvals`: approve or reject purchases, invoices, expenses
- `pricing-and-scope`: what is offered, at what price, and what is left out
- `delegation`: what is handed to others and what the owner keeps
- `inbound-requests`: how unsolicited requests and introductions are answered
- `time-and-priorities`: what gets time and what is declined

## Pulling sent mail

```
list_entities(entity_type="email", filters={"direction": "sent", "since": "<ISO time, the window ago>"}, limit=100)
```

Scan the summaries for decision signals ("approve", "decline", "I think we should", "let's go with", "my recommendation", "the reason"). For each candidate, read the whole thread with `get(entity_type="email", id_or_query=<id>, detail="full")`: the thread gives the inbound situation and the owner's reply with its reasoning. Read enough of the thread to summarize the situation honestly. If the thread text looks cut short, fetch full bodies with `email_bodies(ids=[...])`, at most ten ids per call, because a larger batch can exceed the response limit and fail whole.

## Recording a case

Each case names its email as an inline source, so one call records both (the source is upserted by type and id). The file (or `--json`) holds a list:

```json
[{
  "category": "spend-approvals",
  "situation_summary": "<what was asked, one to three sentences, names and amounts included>",
  "context_snapshot": {"client": "...", "amount": "...", "requester": "..."},
  "action_taken": "<what the owner did>",
  "reasoning": "<the owner's words, trimmed, or null>",
  "sources": [{"type": "email", "external_ref": "<Portal email id>", "url": "portal://email/<id>",
               "title": "<subject>", "locator": "<message id of the owner's reply>"}]
}]
```

## When no one is present

Run unattended by `decision-playbooks-worker` for `decision-playbooks-curator`, this skill asks nothing and writes nothing to the decision store: the category and window come from the brief, and the cases go to a file in the Run folder in the `add-case` shape above. `playbook-workstream`'s section Mine one batch says how; the hard rules hold unchanged.
