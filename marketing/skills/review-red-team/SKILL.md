---
name: review-red-team
description: "Reference loaded by a department's reviewer, not for a user request: the red-team checklist. The reviewer reads a finished deck, memo, readout, diagram or report as a skeptical, time-poor executive in its audience, runs a silent-read test and ten tests (ten-second, narrative, so-what, catchphrases, jargon, earns the non-obvious, AI tells, over-claim, what is missing, visual noise), and returns per-section grades where every criticism carries a concrete fix. Not for verifying facts (review-facts) or numbers (review-numbers)."
---

# Review: red team

The checklist a department's `<department>-reviewer` is briefed with once an artifact is complete and before it reaches its audience. The reviewer takes the part of a skeptical, time-poor senior executive in that audience, who has not seen the maker's notes, outline or reasoning and must not ask for them, and judges only what the audience will experience. The job's own check section may add lines or set the bar; where it does, it wins.

## Inputs

- **The artifact** (required): a file (HTML deck, Markdown memo, PDF, diagram screenshots) or a folder. Read it fully; a deck in order, scroll view or slide files.
- **One of** (required):
  - **For a teaching artifact**: (a) the audience's assumed knowledge and (b) the expected outcomes. The central question is formal: starting from (a), did this artifact deliver (b)? Name exactly where (b) falls short.
  - **For any other artifact**: a one-line purpose. Nothing else.

Anything more (the maker's outline, intent, a summary of what they meant) contaminates the test: set it aside and say so in the return.

## The checks

**First, the silent-read test.** Experience the artifact without any spoken track or speaker notes. Write, in two sentences each, what you learned and what you would do Monday morning because of it. "Nothing specific" is the headline finding. Value that lives only in notes the audience never reads is a defect of the artifact.

**Then every test below.** Quote the offending line or name the slide or section for each hit.

1. **Ten-second test.** From the first screen alone, can you say what this is and why you should care? If not, what is missing from the opening?
2. **Narrative test.** Does it move from a situation you recognize to a conclusion you did not have, or is it a sequence of topics?
3. **So-what test.** For every recommendation, comparison or before-and-after: what changes for the audience in money, time, risk or headcount? Flag it where the artifact does not say.
4. **Catchphrases and sales language.** Any title, sub-line or body line that sounds clever but is empty, or reads as a pitch rather than insight. A title that is a topic label rather than a conclusion is a defect.
5. **Jargon.** Every term the audience would not use themselves, at first use, without a plain-English translation.
6. **Earns the non-obvious.** Does it hold at least one real artifact or wired system (not a description of one), one number or lived example, one "what everyone gets wrong" insight, and one action small enough to do on Monday? Name every section that is pure taxonomy with nothing to do.
7. **AI tells.** All definition and no demonstration, generic enough to have come from an article. Hunt for: sections interchangeable with another artifact on the same topic; peer sets in perfect parallel grammar; category nouns where a named instance belongs ("stakeholders" for a job title, "tools" for a product name); a framework with no named friction it resolves; option grids with no starred first move; a Monday action too large for a Monday.
8. **Condescension, over-claim, burial.** Where does it talk down, promise more than it shows, or bury the most important point below something less important?
9. **What is missing.** Money, time, volumes, who does the work, what it costs to be wrong.
10. **Visual noise** (decks and diagrams only). What could be deleted with no loss?

Be harsh about the work and useful about the fix. Expect to give a C: a C with twelve concrete fixes is worth more than a B with none. A criticism without a fix is not finished; do not send it. Do not rewrite the artifact; the maker revises.

## Verdict

- **PASS** when the silent-read test yields a specific Monday action, a teaching artifact's (a) delivers its (b), and no section grades below C, unless the job's check section sets another bar.
- **FAIL** otherwise. The numbered fixes are the findings, numbered, with the one change first.

## Return

The verdict line (`PASS` or `FAIL`), then:

- **Silent-read result**: what you learned and what you would do Monday, in the audience's words.
- **Verdict on the contract** (teaching artifacts): did (a) deliver (b)? Where exactly not?
- **Per-section grades**, A to F, one line of reason each.
- **Findings**, grouped by test and numbered, each with the quoted line or section reference and a specific rewrite or fix.
- **The one change**: if the maker could do only one thing, what it is.

## Briefing this check (for the main agent)

- **A teaching artifact:** give the reviewer the scroll view without speaker notes, then (a) and (b), so it can answer whether (a) delivered (b).
- **Any other artifact:** the artifact and its one-line purpose only, plus any specific hunt the job needs (process vocabulary, employee names, a number it cannot trace).
