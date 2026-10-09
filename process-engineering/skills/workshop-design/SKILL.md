---
name: workshop-design
description: "Assemble a facilitated workshop's run of show from eight exercise cards, given a goal, a time box and who is in the room: the timed agenda, materials per exercise, facilitator notes and the pre-read ask. Use when planning a discovery day, a prioritisation or roadmap session or a multi-day kickoff, or when a client asks \"what will we actually do in the workshop\". Not for a deck someone presents; use writing-seminar-builder. For prep and summary as a reviewed Run, start workshop-orchestrator."
argument-hint: "[goal] [time box, e.g. 1 day | 2 x half day] [who is in the room] [client]"
allowed-tools: Read, Glob, Grep, Write, AskUserQuestion
---

# Workshop designer

The cards are the parts; this skill is the assembly. Read `references/workshop-exercise-cards.md` in this skill's folder first: eight exercises, each with a duration, an output, mechanics, why it works and what it is best for. A run of show is a sequence of cards whose outputs feed each other, that fits the time box with transitions, and that ends with the artifact the goal names.

## Steps

1. **Pin the goal as an artifact.** Ask (or read from the argument) what the room must hold at the end: a ranked opportunity list, a business case for the top three, a phased roadmap with owners, a risk and change plan. If the answer is "alignment" or "awareness", push back once: which document would prove it? Then pick the card whose **Output** is that artifact; it is the last exercise.
2. **Work backwards through the dependencies.** Each card's mechanics name what it consumes. Opportunity Identification harvests from Day in the Life, Information Flow and What If; Complexity and ROI score the ranked list; Roadmap places scored opportunities; Risk and Change reads the roadmap. Add the cards the last one needs, and nothing it does not.
3. **Fit the time box.** Total the durations, add 10 minutes per transition, 45 minutes for lunch on a full day, 5 minutes to open and 10 to close. Apply the two hard rules from the template: never two 90-minute exercises back to back; if it does not fit, drop a discovery card (Day in the Life *or* Information Flow, not both are required) before shortening a convergence card. Ask before removing anything the goal depends on.
4. **Match cards to the room.** Day in the Life needs the people whose day it is; Information Flow needs someone from each desk the artifact crosses; ROI needs whoever the CFO will ask; Risk and Change needs the people who will live with the change, not only the sponsor. Where the room lacks the right people for a card, say so and propose the pre-read or a pre-interview (`interview-synthesis`) that substitutes.
5. **Write the run of show.** Table: `H:MM to H:MM · Exercise · Output produced · Who leads · Materials`. Under it, per exercise, the facilitator notes: the mechanics from the card in the order they happen, the one thing that goes wrong (from the card's "why"), and the sentence that opens the exercise. Then the materials list (wall space, cards, dot votes, the ROI sheet, the rubric weights agreed in advance) and the pre-read ask for the sponsor to send, under 120 words, with no threatening metric words: not "utilisation", "efficiency", "productivity", "headcount" or "optimisation", but "where the time goes", "what gets in the way", "what you would hand off".
6. **Check it against the goal.** Read the last row's output; it must be the artifact from step 1 by name. Read every other row; each must feed a later one. A row that feeds nothing is cut.

## Rules

- **Durations are the card's.** Shortening a 90-minute exercise to 45 produces the shape of the output without the content; if time is short, run fewer cards.
- **Weights before scores, silent placement before discussion, ranges not points.** These three mechanics are what make the outputs defensible; the notes must say when each happens.
- **One owner per phase, one messenger per affected group.** Carry the Roadmap and Risk rules into the notes verbatim.
- **No fee figures anywhere.** The ROI card projects the client's numbers, not ours.
- The default shapes in the template's last paragraph (discovery day, then Complexity and ROI, then Roadmap and Risk) are starting points; the goal decides.

## Output

`workshop-run-of-show.md` in the engagement folder (or the path given): the table, the facilitator notes, the materials list, the pre-read ask. When the workshop needs slides, hand the run of show to `writing-seminar-builder` as a consulting deck whose beats are the exercises; the deck holds instructions and timers, never content the room is meant to produce.

## Other templates in this skill

- `references/discovery-workshop-pack.md`: the four documents of a paid leadership discovery workshop (collected ideas, the internal prep brief, the facilitation plan, the post-workshop summary).
- `references/session-log.md`: the same-day record of a delivered session (workshop, seminar, lab or talk).
