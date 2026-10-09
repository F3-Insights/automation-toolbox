---
name: crm-data-review
description: Walks the owner through filling the gaps in their Insights Portal data, one area at a time and five items at a batch (contacts and companies with no background, goals and projects with no description, relationships gone stale), asking what they know and writing it as linked notes. Use for "review my Portal data" or "help me fill in my contacts". Not for the unattended weekly cleanup of wrong facts and duplicates (crm-data-hygiene-orchestrator) or for tasks (task-clarify-orchestrator).
argument-hint: '[area: contacts, companies, domains, stale, or all]'
allowed-tools: mcp__insights-portal__*, AskUserQuestion, Read
---

# Data review

Find the incomplete or stale data in the Portal and fill it in with the owner, one area at a time. The owner is the source here: this review records what they know. The unattended `crm-data-hygiene-orchestrator` fixes what the record already states; this skill captures what only the owner can say.

**User provided:** $ARGUMENTS

Before any write, load the `portal-write-safety` skill and follow it. Notes follow the `portal-note-types` skill.

## Step 1: The overview

```
data_health(scope="summary")
```

Then pull the incomplete-entity detail once and keep it for the session; every area below slices this one payload instead of making its own call:

```
data_health(scope="incomplete")
```

If it returns counts but no items, build the area's list with `list_entities` instead (contacts and companies, filtered locally) and say so.

Present it:

```
## Portal data health

| Issue | Count |
|---|---|
| Contacts without notes | X |
| Contacts without background | X |
| Companies without notes | X |
| Projects without description | X |
| Goals without description | X |
| Stale contacts (90+ days) | X |
| **Total** | X |
```

## Step 2: The area

Use the area in the arguments. Otherwise ask:

```
Which area would you like to review?

1. Contacts: background on people you know
2. Companies: what the companies you work with do
3. Domain hierarchy: goal and project descriptions
4. Stale relationships: reconnect with neglected contacts
```

## Step 3: Review, five at a time

### Contacts

From the cached payload, the contacts with no background note, five at a time. For each:

1. Show the name, the company if known, and when the record was created.
2. Ask what the owner knows, referring to what the record holds: "Dana works at Acme Components. What is her role? How do you know her?" or "You last emailed Sam 45 days ago about the renewal. Any update?"
3. With an answer, write a background note linked to the contact.
4. On "skip", move on.
5. Keep count: "Reviewed 3 of 15 contacts."

### Companies

From the cached payload, the companies with no notes, five at a time. Show the name and how many contacts the Portal holds there, ask "What does Northwind Traders do? What is your relationship?", and write a background note linked to the company.

### Domain hierarchy

`list_entities(entity_type="domain")`; let the owner pick one, then `hierarchy(domain_id_or_query="...", depth=3)`. The hierarchy is domain, goal (with sub-goals), project, task. Walk it:

1. Show the domain's description, or that it has none (`get(entity_type="domain", ...)`).
2. For each goal, check its description.
3. For each project, check its description.
4. Offer to add the missing ones.

### Stale relationships

From the cached payload, the contacts flagged stale, five at a time. Show the name and the last activity date, ask "Should we reach out to Priya? Any recent interaction to log?", and offer to log an activity, create a follow-up task, or skip.

## Step 4: Progress

After every five items:

```
**Progress: reviewed 5 items**

- Continue with [this area]
- Switch to [another area with issues]
- Stop here (run this again to carry on)
```

## Step 5: Summary

When the owner stops:

```
## Session summary

Reviewed:
- 8 contacts (6 background notes written)
- 3 companies (2 notes written)

Remaining:
- 7 contacts still need background
- 2 companies still need notes
```

## Rules

- **Tasks are not this review's.** Filing, owners, next actions and WAITING follow-up dates belong to the daily clarify pass (`task-stack-clarify`); completion and staleness to the nightly task reconciliation. Both write through `task-stack-apply`. This review covers contacts, companies and the hierarchy's descriptions.
- **Abstention is a real answer.** Many "I don't know"s in one domain means the domain needs a project, not more guessing.
- **Repeated skips.** Offer to narrow ("Just the VIP contacts?") or to defer the rest.
- **Note quality.** Bullets, filler stripped, specific facts and dates, `background` for standing context and `episodic` for an event.
- **Link everything.** Associate each note with its contact or company, any project the owner mentions, and note any person they name as a connection.
