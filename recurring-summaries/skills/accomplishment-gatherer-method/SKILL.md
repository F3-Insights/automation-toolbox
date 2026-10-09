---
name: accomplishment-gatherer-method
description: "Reference loaded by the accomplishment-gatherer agent, not for a user request: the step-by-step procedure for compressing one domain's day into five to eight candidate accomplishment bullets, from the strategic context first, through grouping, objective weighting, running themes and the user prime, to at most one follow-up query and the bullets themselves, with a worked example of the return. Not for picking the day's done list across domains; use accomplishment-synthesizer-method. Not for planning or closing the day; use daily-plan-method."
---

# Gathering one domain's accomplishments

This is the procedure the `accomplishment-gatherer` agent works through, in order, for one domain packet. The agent file holds the goal, the judgment, the boundaries and the exact return format; this skill holds the steps and a worked example.

## Steps

### Step 1: Skim the strategic context first

Read the missions and goals for this domain. These define what *matters* here. Every bullet you propose should be legible as advancing (or failing to advance) one of these.

### Step 2: Scan the items

Go through meetings, completed tasks, sent emails, notes, drafts. Group related items: if 3 sent emails all concern the same thread/project, that's one bullet, not three.

### Step 3: Weight by objective alignment

An item that advances an active mission/goal is worth more than an item that doesn't. A completed P1 task on the critical path to the Q2 renewal goal beats five routine sent emails.

### Step 4: Check the running themes

If today's activity continues a multi-day thread ("closing the Acme renewal"), the bullet should frame it as *progress on an ongoing thread*, not a standalone accomplishment. Novelty only applies when today's work is genuinely new.

### Step 5: Check the user prime (if present)

If the owner said "today was mostly about the Acme renewal," that's a hint to surface Acme-related bullets even if other items had higher raw volume. Their stated priority wins tiebreakers.

### Step 6: Optional follow-up queries (USE SPARINGLY)

If an item is ambiguous and you genuinely cannot tell what happened without more context, you *may* fire one targeted query:
- `get(entity_type="email", id_or_query="...")` to understand an outbound email's thread (use `email_bodies(ids=[...])` if you need the raw body text of one or more messages)
- `get(entity_type="project", id_or_query="...")` to understand a project reference

Budget: **max 1 follow-up per gatherer run.** If you can write a coherent bullet without the follow-up, skip it.

### Step 7: Produce 5–8 candidate bullets

Each bullet:
- **≤20 words.** Count them. "Sent three emails" is not a bullet; "Closed pricing debate with Acme; aligned Dana and Sam on tiered model for Q2 renewal" is.
- **Lead with the accomplishment verb**: closed, drafted, decided, shipped, escalated, unblocked, aligned, set up, killed, agreed, kicked off.
- **Specific**: name the contact, project, number, decision. No generic "worked on X."
- **No filler**: strip "continued to," "had a good," "as planned," "productive."

Then return them in the agent's output format.

## Example Output

```
<bullets>
[
  {
    "text": "Closed Acme pricing debate; aligned Dana and Sam on tiered model for Q2 renewal.",
    "importance": 9,
    "type": "decision",
    "project_id": "p1",
    "mission_id": "m1",
    "goal_id": "g1",
    "source_item_ids": ["mt1", "e1", "n1"],
    "thread": "ongoing",
    "alignment": "advances_goal"
  },
  {
    "text": "Completed revised Acme pricing task; proposal going out tomorrow morning.",
    "importance": 7,
    "type": "completed_task",
    "project_id": "p1",
    "mission_id": "m1",
    "goal_id": "g1",
    "source_item_ids": ["t1"],
    "thread": "ongoing",
    "alignment": "advances_goal"
  }
]
</bullets>

<notes>
One sent email unattributed to a project; flagged for orchestrator review.
</notes>
```
