---
name: review-facts
description: "Reference loaded by a department's reviewer, not for a user request: the facts checklist. Every claim an artifact makes is held against the sources the brief assigns and gets VERIFIED, NOT IN MY SOURCES or CONTRADICTED, with a verbatim quote and its location, then the significant facts the sources hold that the artifact leaves out. Run two reviewers on disjoint halves of the sources when there are many; for a late source, a diff against the earlier ledger. Not for re-deriving figures (review-numbers), missing standard elements (review-completeness) or how the audience will read it (review-red-team)."
---

# Review: facts

The checklist a department's `<department>-reviewer` is briefed with when an artifact (a process map, memo, readout, recap, report or proposal) must be traced to its sources before it goes out. For every claim it says whether the assigned sources support it, say nothing about it, or contradict it, and proves each answer with a quote and its location. The job's own check section may add lines or set a return of its own (a claim ledger file, a verdict JSON); where it does, it wins, and the three verdicts below keep their exact spelling because scripts read them.

## Inputs

- **The claim inventory** (required): a numbered list of the factual statements the artifact makes. Handed the artifact instead, extract the claims first: every number, name, system, sequence, ownership, timing, or cause-and-effect statement is a claim. Opinions and recommendations are not claims; skip them.
- **The assigned sources** (required): specific files, a folder, or record ids. Read all of them fully. Look for no others: another reviewer may hold them, and a clean NOT IN MY SOURCES is what lets two reports be cross-referenced.
- **An earlier ledger and open-questions list** (optional): when given, this is a diff pass. Report only claims whose verdict changes and facts that are new.
- **The job's check section** (optional): extra lines or a return shape of its own.

Never the maker's reasoning or summary. If the brief carries it, set it aside and say so in the return.

## The checks

1. **Every claim gets exactly one verdict.**
   - **VERIFIED**: quote the supporting passage verbatim and give its location (file, line, timestamp or page). Paraphrase does not count. Where two sources support it, quote the stronger and cite the other.
   - **NOT IN MY SOURCES**: the sources neither support nor deny it. Say so plainly; never soften it into "likely" or "probably".
   - **CONTRADICTED**: quote the contradicting passage and its location, and state the contradiction in one sentence. Do not resolve it; the maker decides.
2. **Primary over secondary.** A figure that appears in a secondary source (a summary, a slide, a prior report) but not in a primary one (a transcript, an export, a signed document) is VERIFIED with the caveat "secondary-sourced". Say which source.
3. **Omissions.** List the significant facts the sources contain that the artifact does not mention: numbers, decisions, exceptions, people, systems, constraints. Significant means a reader of the artifact would decide differently knowing it. Quote and locate each one.
4. **Stay in lane.** Do not summarize the sources, judge whether the artifact is good, or fix anything.

## Verdict

- **PASS** when no claim is CONTRADICTED, no significant omission is found, and no claim is NOT IN MY SOURCES while you hold every source. On a split (the brief says another reviewer holds the rest), NOT IN MY SOURCES does not fail by itself: the main agent cross-references the halves, and a claim no half verifies fails then.
- **FAIL** otherwise, with numbered fixes: for each CONTRADICTED claim, the correction the quote supports; for each unsupported claim, cut it or name the source that would carry it; for each omission, add it or say in the artifact why it is left out.

## Return

Start with the verdict line (`PASS` or `FAIL`) and the numbered fixes, then, in this order:

1. **Ledger**: a table, one row per claim: number, the claim as given, verdict, quote, location, caveat if any.
2. **Omissions**: numbered, each with quote and location.
3. **Counts**: how many VERIFIED, NOT IN MY SOURCES, CONTRADICTED.
4. **For a diff pass only**: changed verdicts and new facts, nothing else.

The return is the deliverable; the main agent relies on it without reading the sources.

## Briefing this check (for the main agent)

- **Many sources:** dispatch two reviewers on this checklist with the same claim inventory and disjoint halves of the sources, then cross-reference their NOT IN MY SOURCES lists. Each reviewer's reading load stays bounded, and "not found" becomes a signal rather than a dead end.
- **A source that arrives late:** give one reviewer the existing ledger and open-questions list with the new source, and ask for changed verdicts and new facts only, not a fresh summary.
