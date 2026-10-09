---
name: accomplishment-synthesizer-method
description: "Reference loaded by the accomplishment-synthesizer agent, not for a user request: the step-by-step procedure for turning the per-domain candidate bullets into the day's done list, from the user prime, through pooling and scoring, picking up to the cap with a slot per active domain, the one-line header and the bullet quality pass, to the strict markdown format, with a worked example of the return. Not for one domain's candidates; use accomplishment-gatherer-method. Not for planning or closing the day; use daily-plan-method."
---

# Synthesizing the day's done list

This is the procedure the `accomplishment-synthesizer` agent works through, in order, over the gatherers' candidates. The agent file holds the goal, the judgment, the boundaries and the exact return format; this skill holds the steps and a worked example.

## Steps

### Step 1: Read the user prime carefully

If the owner said "today was mostly about X," that frames the whole recap. The header should reflect it; the top of the bullet list should surface X-related items.

### Step 2: Pool and score all candidates

Combine all bullets across all domains into a single pool. Each carries an `importance` from the gatherer. Adjust with your judgment:
- **Boost** items that align with the owner's stated prime.
- **Boost** items tagged `advances_goal` or `advances_mission`.
- **Boost** items tagged `thread: new` over `thread: ongoing`: novelty is worth more than ongoing progress, all else equal.
- **Demote** obvious duplicates: if two domains reported the same underlying accomplishment (shared project spanning domains), pick one and flag in the meta line.

### Step 3: Pick up to the cap

Rules:
- **Cap at 20 total, or the brief's lower cap.** If fewer quality candidates exist, emit fewer; do not pad.
- **Minimum 1 per ACTIVE domain.** If a domain is active but its best bullet lost all tiebreakers, reserve one slot for its top candidate.
- **THIN domains may be skipped entirely** if their candidates don't crack the top 20 once ACTIVE domains have their minimums.
- **QUIET domains** contribute nothing (never reach you).

### Step 4: Write the 1-line header

Distill what was *novel, surprising, or important* about the day in ≤25 words. Not a summary of the day: the through-line. Examples of good headers:

- "Closed the Acme pricing loop and unlocked Q2 renewal conversations across two more client accounts."
- "Most of the day went to the vendor selection; client work quieter than usual."
- "Broad-front day: real progress in three domains but no single breakthrough."

Avoid: "Today the owner did a lot of things" or "Productive day." The header must carry actual information.

### Step 5: Enforce bullet quality

Before emitting, re-read every bullet:
- **≤20 words**: count them.
- **Lead verb**: closed, aligned, drafted, decided, unblocked, escalated, killed, kicked off, landed.
- **Specific**: names, numbers, decisions, not "worked on."
- **No filler**: strip "continued to," "had a productive," "as expected."
- **Voice register**: plain business verbs in the owner's register (the owner's voice guide, setting `voice_guide`, when the brief names it). Avoid jargon the owner's voice guide rules out.
- **No silent rewrites that change meaning**: if a gatherer bullet is bad, drop it rather than invent a better version.

### Step 6: Format output (STRICT)

Output pure markdown, exactly the shape in the agent's Output section.

## Example Output

```markdown
# Daily Recap, 2026-04-19

> Closed the Acme pricing debate and lined up Q2 renewal; the vendor selection is down to two.

## Domain: Clients (domain_id=d1)
- Closed Acme pricing debate; aligned Dana and Sam on tiered model for Q2 renewal. [9]
- Completed revised Acme pricing task; proposal going out tomorrow morning. [7]
- Logged Q2 Review meeting notes with decisions on renewal terms. [6]

## Domain: Operations (domain_id=d2)
- Narrowed the payroll vendor shortlist to Northwind and Contoso; reference calls booked. [8]
- Completed the vendor comparison task; scoring sheet shared with Jordan. [5]

## Meta
- Bullets: 5 across 2 domains (of 2 active)
- Bullet types: 1 decision, 2 completed_task, 1 created_note, 1 drafted
- User prime ("Acme renewal") aligned with top 3 bullets.
- Orchestrator fired 2 follow-ups on Acme thread; coverage judged complete.
```
