---
name: project-status-deck
description: "Build, review or revise a client status deck as a self-contained HTML slide deck in the engagement's house style: full-sentence headlines, eyebrows, timed speaker notes, a hidden source comment on every claim, slides chosen by what happened since the last deck, and a ten-minute review note for the owner. Client specifics live in the engagement's rules (playbook, deck guides, reference deck). Use for \"build this week's status deck\", \"review the deck\", \"apply the feedback\". Not for a memo (comms-client-status-update) or a teaching deck (writing-seminar-builder)."
argument-hint: "[build | review | apply-feedback] [engagement rules file or folder] [date]"
allowed-tools: Read, Glob, Grep, Write, Edit
---

# Project status deck

A recurring client update presented as slides: a weekly update, a steering committee, a leadership or sponsor update. The deck keeps the sponsor and leadership confident in the direction and gives them what they need to unblock the work. It is not a sales document, not a findings report and not a log of activity.

Everything specific to one client lives outside this skill, in the engagement's rules: a rules file (for the client-update orchestrator, `UPDATE-RULES.md`) that names the client's playbook, deck guides and reference deck, and says which wins where they disagree. Read all of them in full before writing a slide, every time. The newest deck the owner approved is the standard for format and patterns and wins over any written rule; its content is never a source for new facts.

## Modes

| Mode | Asked as | Produces |
|---|---|---|
| Build | "build this week's deck" | a new draft deck and its review note |
| Review | "review the deck" (the owner) | the owner's answers written into the review note; the deck untouched |
| Apply feedback | "apply the feedback" (the builder) | the revised draft, the list of changes, proposed rule changes |

## The standard

The arc, every time: **what we did, what we heard or learned, the direction and how each decision was reached, what happens next and what we need.** Detail goes to an appendix.

1. **Headlines are full sentences that state the point** ("Three causes make the delivery forecast inaccurate, and each needs a different fix"), never a label. Sentence case, consistent.
2. **Eyebrows** say where the slide sits in the story ("Since the last update", "Workstream 2", "Next steps", "Appendix A").
3. **Every slide has speaker notes** with a timing (`Speaker notes · 1:45`) and two to four bullets that coach the presenter: what not to do, how a number was counted, what to say out loud, and a **parking line** for the slide's most likely tangent. The timings add up to two or three minutes under the slot; the middle slide's notes carry a halfway checkpoint.
4. **Every claim has a hidden source comment** right after it, so anyone can trace any number or finding. Non-negotiable.
5. **Counts come with their method** in the notes; **illustrative figures are labelled** on the slide and in the notes.
6. **Open items are shown** with a visible "Open item" or "Timing" label, and the notes give the question to ask the room.
7. **Status is honest:** "being built", "not received yet", "still to be chosen". Never state a plan or a precondition as done; never drop a hedge the source kept ("where possible").
8. **Technical terms** get a one-line plain definition as the slide subtitle.
9. **Next steps** puts decisions first (only when one is needed, and only decisions the owner's brief or the latest leadership meeting stated), then the timing constraint, then item, owner and date. Its notes say what is not being asked today and list what was parked.
10. **Interview evidence goes in the appendix**, aggregated and unattributed.
11. About **80 words of visible text per slide**, not counting tables, and one sentence per table cell. Detail moves to the notes or the appendix. Dense slides get tighter wording before smaller text.
12. The title footer shows the audience, the date and "Draft" until the owner removes it.

Never: names or identifying detail tied to interview feedback; remarks made in confidence; anything recorded after the firm's people left a meeting; the firm's commercial matters (fees, margins, rates, internal methods, running costs); promises of savings ("will save", "will reduce", "ROI of"; a value signal is a baseline: "today it takes", "we will measure"); a single-person anecdote that shocks; criticism of a leadership decision; a decision invented for the room. Hedge claims about behaviour ("some believe", "at times"). On a sensitive theme drop the "raised in N interviews" counts. The engagement's rules add their own list; apply both.

Writing: matter of fact, no taglines, no two-beat contrasts, no rule-of-three cadence, no sales language, no em-dashes, and none of the characters the engagement's rules ban. Run the `unslop-deliverable` pass on every word before the owner sees it.

## Sources and the pre-flight

A deck built on partial context looks finished and is wrong. Before gathering facts:

1. **Since date and carry-forward.** Find the previous deck and its review note. Its date is the since date, its next-steps table is the carry-forward list, and its review note records each workstream's phase and what was parked.
2. **Meeting inventory.** Every client meeting since the since date, from the calendar, the meeting recorder and the engagement folders. Take a meeting's date from inside the file.
3. **A readable source per meeting.** A recording held in another organisation's tenant, or a raw caption file, does not count. A fact that leans on an unreadable meeting goes in the review note as "please confirm".
4. **The brief.** The owner's outline or notes for this deck, when there is one: its order, its slide count and its wording are the spine. Map every point to a slide before writing; a point that lands only in the notes does not count.
5. **Stop rule.** If a source the rules mark required is missing, say exactly what is missing and who can supply it. Unattended, build only from what is present, label every slide that leans on the gap "Open item", and put the gaps first in the review note.

Read the standing read-outs and topic documents first, then the new material. Never open a raw export the rules list; figures come from the firm's own summaries.

## Build

1. Choose slides by what happened, with the rules' trigger table: core slides every time (title, since the last update, next steps), a conditional slide only when its trigger is true. Never keep a slide because last week had one. A workstream with nothing new gets one line on the since slide.
2. Start from the reference deck's file: keep its CSS, navigation, notes and theme code exactly, and delete every pattern you do not use. Update the slide counter and the `<title>`.
3. Write each slide to the standard, with its notes and its source comments.
4. Account for every carry-forward item: done, moved (reason and new date) or dropped (reason).
5. Write the review note, then run the checklist and fix what fails.

The source comment, one per claim, placed right after the element that makes it:

```html
<p>Two outcomes moved into build this week.</p>
<!-- Source: C4 · S012, S015 · Pilot Review 2026-09-22.md, "Decisions", 2026-09-22 -->
```

`C4` is the claim's id in the claim inventory and `S012` the source's id in the week's `sources.json` when the client-update orchestrator drafts the deck; by hand, the file, section and date alone. A claim is any number, name, date, decision, ownership, status or cause-and-effect statement a reader could challenge, on a slide or in the notes. Opinions, recommendations and transitions are not claims.

## The review note

Beside the deck, named as the rules say (`<date> review-notes.md` by default):
- the pre-flight result: sources found, meetings matched, gaps and who can fill them;
- every default taken because no one was there to ask;
- how the brief maps to slides; which conditional slides are in or out, and why; each workstream's phase;
- **facts to confirm**, numbered, including every statement only the owner can stand behind;
- **judgement calls**, numbered; carry-forward items moved or dropped; anything left out on purpose; items parked;
- value signals: proposed rows for the engagement's baselines ledger, marked "needs the owner's approval" before any appears on a slide;
- the fact-check and red-team results, and what changed because of them;
- an empty `## Owner's feedback` heading at the end.

## The checklist (before the owner sees it)

- Every point of the brief is on a slide; decisions come from the owner or the brief.
- Every conditional slide meets its trigger; the arc holds; every headline is a full sentence.
- Every slide has timed notes with a parking line; the total is two or three minutes under the slot; the next-steps notes list what was parked and what is not being asked.
- Every claim has a source comment, every count its method, every illustrative figure its label; every carry-forward item is accounted for; every next-steps row has an owner and a date, with the source's hedges kept.
- No `{{`, no `[owner]`-style blank, nothing from the never list, no banned word or character.
- The slide count equals the notes blocks; the arrow keys and the notes key work; it renders at the presenter's real viewport (the rules give the zoom), at phone width, light and dark, with no orphaned words or overflow. Check the rendered slides, not the source.

## Review mode

For the owner, in about ten minutes. Summarise the deck in five lines (headline, decisions for the room, slide list, how many items to confirm). Walk the facts to confirm one at a time (confirmed, corrected with the fact, remove), then the judgement calls (keep, or change how), then each slide (OK, change what, cut), asking for every change whether it is "this deck only" or "always". Ask what to park and whether the deck is approved. Write the answers under `## Owner's feedback (yyyy-mm-dd)` in the review note, and change nothing in the deck:

```
Confirm items:
- <item>: confirmed | corrected: <fact> | remove
Judgement calls:
- <call>: keep | change: <how>
Slide changes:
- Slide <n>: <change> [this deck only | always]
Parked for follow-up:
- <item>
Approved: yes | yes after these changes | no
```

## Apply-feedback mode

Read the feedback section; if it is empty, stop and say so. Apply every item and nothing else, update the source comments and the counter, and re-run the checklist. Revise the draft in place only where the rules allow it (the folder's version history keeps the earlier one); otherwise write a new file. Once approved, remove "Draft" and save under the final name the rules give, and remind the owner to file it as the new reference where the rules say so. For every "always" item, draft the exact rule change with a dated changes line, as a proposal for whoever owns the rules; never edit the rules yourself.

## Files

- The deck: self-contained HTML in the engagement's folder, named as the rules say, with a draft marker in the name until approved. Never a hosted page.
- A PDF only after approval: 16:9 pages at 1280x720, light theme, navigation and notes hidden, the desktop grid forced in print CSS; look at every page before saving.
- Never overwrite an earlier deck, never edit a file the client has seen, never edit another person's draft. A new version is a new dated file.
