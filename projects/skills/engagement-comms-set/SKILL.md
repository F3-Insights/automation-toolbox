---
name: engagement-comms-set
description: "Reference template loaded by project-engagement-workstream at kickoff and by workshop-design, not for a user request: the four notes a consulting engagement sends between signature and the first interview (sponsor framing note, technical stakeholder invite, all-staff announcement, interview invite), each with its sender, purpose, contents and tone rules."
user-invocable: false
---

# Engagement comms set

A default set of four notes an engagement sends between signature and the first interview, in the order they go out. The consultant drafts; the named sender sends. The word counts, meeting lengths and windows below are starting defaults for any consultancy; change them, or add and drop notes, to fit the firm and the client. Produced through `comms-draft-email` and edited with `unslop-email`; the runbook is `project-engagement-runbook` step 4.

## 1. Sponsor framing note (consultant to sponsor, first)

Purpose: give the sponsor the words to use with their own people, so the announcement sounds like them. Short bullets (16 to 20 words is a good default), every word load-bearing.

- What the engagement is, in one line the sponsor would say.
- What it is not (the fear you already heard in the workshop, answered once).
- What happens in the next two weeks, as three dated events.
- What we need from the sponsor this week (one thing).
- The line for anyone who asks "is this about cutting people."

Short (under 150 words is a good default). No attachments.

## 2. Technical stakeholder invite (sponsor to IT or systems owner)

Purpose: the IT one-to-one happens before anyone else is interviewed.

- Why we want a short meeting (30 minutes is usually enough) with them first (access, auth, sandbox, what can be exported).
- The three questions we will ask, so they can prepare.
- A link to the asks list (the IT access asks in `project-engagement-workstream`'s `templates/it-access-asks.md`) as a preview, not a demand.
- Two proposed times.

## 3. All-staff announcement (sponsor sends; consultant drafts)

Purpose: everyone hears it from their leader, once, before the interview invites land.

- One paragraph: what is happening, who is doing it, for how long.
- One paragraph: why, in terms of the work getting easier, not the numbers getting better.
- One paragraph: what will be asked of people (an hour, honesty, nothing else) and what will not happen (no recording without consent, no individual reporting).
- Who to ask.

**No threatening metric words.** Not "utilisation," "efficiency," "productivity," "headcount," "optimisation." Say "where the time goes," "what gets in the way," "what you would hand off."

## 4. Interview invite (coordinator sends, consultant cc'd)

Purpose: a recorded interview (sixty minutes inside a two-week window is a sensible default), with a technical member of the team present where the work touches systems (some firms call this role a forward-deployed engineer).

- The window and the booking link or the ask to reply with two slots.
- The length, recorded for the consultant's notes only, transcript anonymised before anyone else sees it.
- Who will be in the room and why the engineer is there (to hear the systems, not to judge the work).
- Three things to think about beforehand, phrased as their day, not our project.
- cc the coordinator so scheduling never routes through the consultant.

## Rules for every note

- Each note has exactly one sender, and it is never the consultant for notes 2 to 4.
- Nothing in any note promises an outcome; everything promises a process and a date.
- The framing note goes first and alone; give the sponsor a day with it before drafting the announcement in their voice.
