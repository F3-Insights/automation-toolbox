---
name: project-engagement-baseline
description: "Turn everything gathered on an engagement (transcripts, workshop outputs, client documents, existing systems) into three documents in sequence: per-source research reports with fixed sections, a one-page BASELINE of what exists and what is missing by target capability with the tensions ranked, and a CONCEPT with numbered positions ready to be grilled. Use once discovery is done, before design or a proposal, or for \"where does this engagement actually stand\". For the unattended interview read-out plus BASELINE, start discovery-synthesis-orchestrator."
argument-hint: "[engagement repo] [research | baseline | concept]"
allowed-tools: Read, Glob, Grep, Write, Agent, Bash(python3 ~/.claude/skills/transcript-tools/scripts/srt_transcript_collapse.py:*), Bash(python3 ~/.claude/skills/transcript-tools/scripts/transcript_hygiene.py:*)
---

# Engagement baseline

Three documents, written in order, each built only from the one before it. Output lands in the engagement repo: `research/`, `docs/BASELINE_YYYY-MM-DD.md`, `docs/CONCEPT_YYYY-MM-DD.md`.

## 1. Research reports, one per source group

Run `transcript-hygiene` on the transcript folders first so duplicates are not read twice, and `srt-transcript-collapse` on any raw exports. Then split the sources into groups (a discovery-conversation set, a workshop set, one per workstream, the client documents, each existing system or codebase) and dispatch one reader agent per group with the same brief:

> Read `<sources>` fully. Return a structured report with these sections. Preserve verbatim
> numbers, names and system names. Your final message is the deliverable; the parent will
> rely on it without reading the sources.

Fixed sections, in this order, lettered so a later document can cite `A §4`:

1. **Per-source detail.** One sub-section per transcript or document: what it is, who, when, what it covers.
2. **People roster.** Name, role, what they own, what they said they want.
3. **Business facts.** Numbers, systems, volumes, dates. Verbatim where possible.
4. **Pain points, verbatim.** Quoted, attributed, with location.
5. **Ideas raised, with strength.** Who proposed, how many agreed, how concrete.
6. **Topic deep-dives.** One per recurring theme in this group.
7. **Commercial terms and constraints** mentioned.
8. **Decisions already made**, with who made them.
9. **Contradictions** within the group.
10. **Glossary** of the client's own terms.

Name the files `research/A-<slug>.md`, `B-…`, in source-group order.

## 2. BASELINE, one document, about two pages

Read the research reports, not the sources. Headings:

1. **The client in one page.** What they do, size, systems, the people who matter.
2. **The engagement as it actually stands.** Signed scope, what has happened, what is in flight, what is stalled.
3. **What the raw material says, by target capability.** One sub-section per capability in the SOW. For each: what the evidence supports, what it contradicts, and a plain **exists / lacks** line.
4. **What we already have, and what we lack.** The consultant's side: tools, prior work, platform pieces that apply, and the gaps.
5. **The tensions to grill, ranked.** Each tension is two things the evidence supports that cannot both be true of the design, with the citations (`A §4`, `C §6`). Ranked by how much the design changes depending on the answer.
6. **Recommendation.** One paragraph. What to build first and why, stated as a position.
7. **Questions to answer in the grill.** Numbered, phrased ready to ask.

## 3. CONCEPT, numbered positions

Only after the tensions have been grilled (`software-grill-with-docs`). The concept states positions, not options:

1. **Thesis.** One sentence.
2. **Source-of-truth rule.** Which system owns which data, stated once.
3. **Platform positions.** Numbered. What is built where, what is reused, what is bought.
4. **Capabilities.** One sub-section each, with the module or component that owns it named, the verbs it exposes, and the position number it rests on.
5. **What this concept declines to do**, and why.

Every position cites the baseline section and research report that support it. A position with no citation is a preference, and the concept says so.

## Rules

- Research reports quote; the baseline paraphrases and cites; the concept decides and cites. Never skip a layer.
- Verbatim quotes and commercial notes stay in `research/`; the baseline and concept are written to be shown to the client's sponsor with names intact but no quotes.
- Re-run only the layer whose inputs changed: a new transcript means a new or updated research report and a diff to the baseline, not a rewrite of the concept.
