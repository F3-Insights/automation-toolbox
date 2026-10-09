---
name: comms-client-status-update
description: "Write the periodic status memo a client executive actually reads, matter-of-fact, from the week's transcripts, notes and register, in two lengths: the one-page weekly update, or the full status memo with analysis sections, clarifications, open actions with owner and date, and open items. Use whenever a client update, engagement status or client executive memo is due. Not for slides (project-status-deck), the unattended sourced weekly update (client-update-orchestrator) or a report to the owner's own leadership team (report-weekly)."
argument-hint: "[client] [period] [weekly | full] [sources: folder or notes]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/transcript-tools/scripts/srt_transcript_collapse.py:*)
---

# Client status update

One document, two lengths. Both open with what was done, never with a judgment about how it is going. Both are read by someone with three minutes who will forward it to someone with one.

- **Weekly update** (one page): Weekly Progress, one short section per workstream, Next Steps. For a cadence where the reader saw last week's.
- **Full status memo** (two to four pages): Weekly Progress, one or more Analysis sections named for their content, Clarifications when one happened, Open Actions, Open Items to Discuss. For a monthly or milestone read, or a reader who skipped a few weeks.

Ask which length if not told. Default to weekly when the previous update was under ten days ago.

## Voice

Six principles, each of which has been violated in a draft that a client then corrected:

1. **Matter-of-fact, not promotional.** No "on track," "great progress," "successfully completed," "key milestone." Say what was done.
2. **Factually precise.** Every statement defensible. If a thing is not ready, do not say it is ready. If a finding is preliminary, say so.
3. **Not alarmist.** A surprising finding is presented as normal project work. No "discovered," "uncovered," "critical," "alarming." Use "the analysis showed" or "we identified."
4. **Explanatory without condescension.** When a technical concept matters to the finding, explain it in one sentence for a reader who does not know it, without signalling that they should.
5. **Consultative, not directive.** You are external. "We are recommending X because Y," not "X must be done."
6. **Measured confidence.** Confirmed things stated plainly; uncertain things marked "under review." No hedging on things that are known, no false certainty on things that are not.

**Phrases that get cut on sight**: on track · ahead of schedule · great progress · successfully completed · key milestone achieved · critical finding · alarming · major concern · discovered · uncovered · going forward · it should be noted that · as previously discussed · leverage · robust · seamless · deep dive (as a noun) · circle back.

**Phrases that carry the memo**: "Completed [activity] this week." · "The analysis showed [finding]." · "Initial findings indicate…" · "This is consistent with [expectation]." · "We are recommending [action] because [reason]." · "The next step is [action], due [date]." · "This remains under review." · "[Person] confirmed that [fact]."

## Structure

Every section is a **bold heading**, a **narrative paragraph of two to five sentences**, then **bullets**. The paragraph explains and connects; the bullets are discrete facts a skimmer can take alone. They do not repeat each other.

1. **Weekly Progress.** Opens the memo. What work was performed: analyses run, meetings held, decisions made, materials delivered. Include any recommendation that changes the timeline. Never opens with a status word.
2. **Analysis section(s)** (full memo only). Named for the content, e.g. "Slotting findings," "Handoff process gaps," never "Analysis." When items are examined individually, bold the item name, colon, one-line finding. When a finding has a cause-and-effect chain, walk it step by step with the numbers. **Attribute every finding**: who flagged it, who confirmed it, by name and role.
3. **Clarifications** (only when one happened). A definition or concept the team aligned on this period, with why it was needed: "Some team members understood X to mean Y; it means Z."
4. **Open Actions.** Bullets. Owner is a **person's name**, not a department; if someone coordinates while another executes, say both. Specific task. **Specific due date** ("Due Sep 20", "target early next week"), never "ASAP" or "TBD" unless genuinely unknown, and then say why.
5. **Open Items to Discuss** (when any). Not yet actions; things to raise with leadership. Framed as follow-ups: "Follow up with [person] regarding [topic]."

The weekly update uses sections 1, one per workstream in place of 2, and a **Next Steps** list in place of 4 and 5.

## Bullets

- **Twenty words maximum.** Over that, split it or move the detail into the paragraph. Open-action bullets and item findings may reach thirty when the specificity needs it.
- One fact, decision, action, or finding per bullet. No bullet that restates the paragraph.
- Item findings: `**Item name:** finding, with the number.`

## Include, and omit

Always: specific work this period; item-level findings with names, numbers, sources; every decision or clarification; recommendations that affect timing; every open action with owner and date; items pending leadership.

When relevant: a one-sentence method explanation tied to a specific finding; why a clarification was needed; implications beyond this workstream, framed neutrally.

Never: status judgments; background unchanged since last time (do not re-explain the engagement); how the analysis was built (spreadsheet mechanics, formulas, prompts); speculation (say "under review"); anything the bullets and paragraph both say.

## Two examples, one good and one bad, per pattern

Opening paragraph. Good: "Completed the slotting review for the main warehouse. Walked the results through with the operations manager and the site lead, and agreed which zones move first." Bad: "Great progress this week. The slotting work is on track and we are ready for the next phase. The team has been highly engaged."

Finding. Good: "**Zone C:** the fastest-moving items sit at the far end of the building, so pickers walk about twice as far per order as in Zone A; the site lead is confirming the order data." Bad: "We discovered some areas of the warehouse are laid out inefficiently, which is slowing things down."

Open action. Good: "Warehouse team ([Person C], coordinated by [Person D]): confirm the move list for the 40 items in Zone C. Due early next week." Bad: "The warehouse team should look into the zones that have issues when they have time."

## Sources and process

Read, in this order: the previous update (so you know what is background now); the period's transcripts (run `srt-transcript-collapse` on any `.srt`/`.vtt` first); meeting notes; the register or task list for open actions. Draft. Then run the cut list above as a grep, then read once as the recipient. The `unslop-deliverable` skill is the second pass when the memo goes beyond a page.

Write the file as markdown next to the sources, named `<Client> Status Update YYYY-MM-DD.md` (or `Weekly Update`). Rendering to HTML or PDF is a separate step; the brand tokens live in the `brand-guide` skill. You do not send anything; the owner reviews and sends.
