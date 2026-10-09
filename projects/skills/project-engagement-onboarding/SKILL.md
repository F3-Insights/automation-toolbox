---
name: project-engagement-onboarding
description: "Write the two-page brief that lets a teammate join an engagement mid-stream and be useful in their first meeting: a linked outline of who, what, where things stand and what is next, with appendices for the org chart, the history and the outcomes sought. Use when someone new joins, when a subcontractor is brought in for one workstream, or when the consultant has been away long enough to need it. Not for a newly signed engagement; start project-engagement-kickoff-orchestrator."
argument-hint: "[client] [for whom] [engagement repo]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/review-register/scripts/register.py:*), mcp__insights-portal__get, mcp__insights-portal__search, mcp__insights-portal__list_entities
---

# Engagement onboarding brief

Two pages, linked, plus appendices. The test: after reading it, could the newcomer sit in tomorrow's client meeting, know who is speaking, know what was promised, and not ask a question that was settled last month?

## Sources, in order

1. The engagement repo: `docs/RUNBOOK.md` (which steps are ticked), `docs/BASELINE_*`, `docs/CONCEPT_*`, the decisions log.
2. The register (`python3 ~/.claude/skills/review-register/scripts/register.py --dir <workspace> summary` and `list open_items`).
3. The Portal: the client company, its contacts, the project and its open tasks.
4. The last two client status updates.
5. The research reports, only for the roster and the glossary.

Do not read transcripts. If the brief needs a fact that is only in a transcript, that fact should have been in a research report; note the gap and move on.

## The two pages

**Page 1**

- **The client in four lines.** What they do, size, the systems that matter, the sponsor.
- **The engagement in four lines.** What was signed, when, the workstreams, where each stands (link to the runbook step).
- **Who you will meet.** Table: name, role, what they own, what they told us they want, how they like to be communicated with. Eight rows at most; the rest are in the appendix.
- **What we have promised and by when.** The open commitments, from the register and the last status update, with owner and date.

**Page 2**

- **Decisions already made.** Numbered, one line each, with the date and who decided. These are the questions the newcomer must not reopen.
- **Open tensions.** From the baseline, the ones still unresolved, one line each.
- **What happens next.** The next three dated events and what the newcomer's role in each is.
- **How we work here.** Folder discipline (From Client and Shared with Client), the register, the status-update cadence, who sends what, the write-approval rule.
- **Vocabulary.** Ten client terms and what they mean, from the glossary.

## Appendices, linked from the pages

- **A. Org chart** as the client draws it, with the people we deal with marked.
- **B. History.** The engagement timeline from first contact, one line per event.
- **C. Outcomes sought.** The SOW goals verbatim, and the sponsor's own words for success from the workshop or kickoff.
- **D. Full roster.** Everyone we have met or been told about.

## Rules

- Every fact on the two pages links to where it came from; a newcomer who doubts a line can check it in one click.
- Names and roles are fine; quotes are not, except the sponsor's success statement in appendix C.
- Write it for the person named in the argument. An engineer needs the systems and the access status first; a second consultant needs the people and the promises first.
- Regenerate rather than patch: when the runbook ticks a new step, the brief is rewritten from sources, and the old one is kept with its date.
