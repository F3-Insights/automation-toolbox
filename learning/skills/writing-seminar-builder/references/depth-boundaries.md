# Depth Boundaries: What to Give Away, What to Hold Back

The hardest editorial judgment in this seminar series is where to stop teaching. Too shallow and the seminar feels like a brochure; too deep and you've given away the engagement you sell. This file makes the line concrete.

---

## The test

A smart executive should leave the seminar able to:

- Explain the business problem and the reframe to their team
- Sketch the workflow on a whiteboard
- Identify whether they have the starting-line conditions in place
- Spot the obvious failure modes
- Brief a vendor or internal team on *what* to build

They should still need help to:

- Actually build it
- Configure the tools, write the prompts, wire the integrations
- Manage the rollout, train the team, handle the change
- Iterate it toward production quality
- Avoid the non-obvious failure modes that only show up at scale

If the deck does both, it's calibrated correctly. If it does only the first, you've under-taught. If it crosses into the second, you've given away the store.

---

## GIVE (these go in the deck)

**The business problem.** Stated in operational language. Specific enough that an executive nods.

**The reframe.** The "aha": what most teams get wrong, and the better way to think about it. This is the seminar's centerpiece.

**The governing principles.** 2–4 design principles that, if followed, make the workflow work and, if violated, predict failure. Stated as principles, not steps.

**The workflow shape.** A diagram showing the boxes and arrows: what happens, in what order, with what inputs and outputs. Enough that someone could redraw it on a napkin.

**One architectural layer beyond obvious.** This is the differentiator. Not "AI reads the email" (obvious), but "AI reads the email, classifies it against your existing taxonomy, drafts a response in your voice, and surfaces the edge cases to a human reviewer, with the taxonomy and the voice both maintained as separate, editable artifacts" (one layer deeper). Still no implementation specifics, but the shape has texture.

**Before/after comparisons.** Show the manual workflow and the AI-augmented workflow side by side. Make the gain visible.

**The failure modes to watch for.** Common ways the work goes sideways. Naming these makes the seminar feel honest and earned.

**The criteria for "done well."** What good looks like: how a leader would know the work succeeded.

**Directional tips.** "Design for X." "Watch for Y." "If you see Z, you've probably gotten this wrong." Principle-based, not step-based.

---

## HOLD (these stay reserved for paid engagement)

**The actual prompts.** Never show working prompts on slides. You can describe what a prompt needs to do; you don't show the prompt that does it.

**The specific tool configurations.** Don't walk through Claude Project setup, GPT configuration, n8n node parameters, MCP server connection strings, or any other "here's how to actually set it up" content.

**The integration plumbing.** How data moves between systems, authentication patterns, error handling, retry logic, monitoring. All paid territory.

**The data pipeline design.** If the workflow involves transforming or routing data, the design of that pipeline stays behind.

**The change-management playbook.** How to roll this out without breaking the team. How to handle the political resistance. How to train the people who'll use it. This is often where the real money lives, and it almost never belongs in a free seminar.

**The iteration loop.** How you take a v1 that kind of works and turn it into a v3 that's reliable in production. The testing approach, the metrics, the refinement cadence.

**The full reference architecture.** You can show a workflow diagram. You don't show a complete reference architecture with every component named, sized, and connected.

---

## Concrete examples of the line

**Topic: AI-augmented customer support triage**

- ✓ GIVE: "Route incoming tickets through a classifier that tags them against your existing categories, draft a response, and queue anything below a confidence threshold for human review."
- ✗ HOLD: The classifier prompt itself, the confidence threshold value, the integration with the helpdesk system, the human-review queue UI, the feedback loop that improves the classifier over time.

**Topic: Financial close acceleration**

- ✓ GIVE: "Three principles for AI in the close: never let the model write to your GL, always preserve the audit trail, and design for the auditor before you design for the controller."
- ✗ HOLD: The actual reconciliation prompt, the variance-detection logic, the specific hooks into the ERP.

**Topic: Executive briefing prep**

- ✓ GIVE: "The shape of a good briefing assistant: it reads the calendar, pulls the relevant CRM context, drafts a one-page brief, and learns the executive's preferences over time."
- ✗ HOLD: The CRM connector setup, the briefing prompt, the preference-learning mechanism, the deployment as a daily-running agent.

---

## When in doubt

Ask: **"Would I charge for this if a client asked me to deliver it?"**

- If yes → it's HOLD. Keep it for paid work.
- If no → it's a principle, a concept, or a piece of common knowledge. Safe to GIVE.

The seminar's job is to make the attendee want the paid work, not to deliver it.
