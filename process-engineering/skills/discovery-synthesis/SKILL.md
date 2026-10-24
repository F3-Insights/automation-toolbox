---
name: discovery-synthesis
description: "The discovery synthesis job, run by process-engineering-discovery-synthesis, not for a user request: its Steps, the section Write the synthesis and its DONE checklist. Turns an engagement's interview transcripts into the internal Read-Out, the anonymized Feedback by Topic for the sponsor and the one-page BASELINE: one process-engineering-worker per transcript, the drafts by interview-synthesis and project-engagement-baseline, then two facts halves, the recount and anonymity check and a red-team read by process-engineering-reviewer. Adds to discovery-workstream. By hand, use interview-synthesis."
user-invocable: false
---

# Discovery synthesis

After the interviews, the engagement gets three documents: a Read-Out the team works from, a Feedback by Topic the sponsor can read without learning who said what, and a BASELINE that says where the engagement stands and which tensions to settle next. Every statement traces to a transcript location; every count is a count of interviews. This skill adds to `discovery-workstream`; read it first.

## Inputs

- **Engagement** (required): the name of its private Context.
- **Since** (optional): only transcripts dated on or after this date. Default: every transcript.
- **Instructions** (optional): the owner's words for this Run; they override the defaults, never `DISCOVERY-RULES.md`.
- **Dry run** (optional): orient and plan only. List the sources, what you would dispatch and what you would ask; dispatch nothing and write only `STATUS.md`.

## Steps

1. [judgment] Orient. Read the Context, `DISCOVERY-RULES.md`, `ENGAGEMENT-CONTEXT.md` and the `working` Source for an earlier synthesis.
   → no rules file: stop
2. [script] Register the sources. Run `transcript-hygiene <folder>` on each transcripts Source so no meeting is read twice, then `srt-transcript-collapse <file> --out <RUN>/sources` for each `.srt` or `.vtt` in scope. Write `sources.json` with ids, dates and halves, an assessment summary filed in `working` as `A01`, and duplicates and non-interviews skipped with the reason.
   → fewer than three interviews and the instructions do not ask to continue: stop
   → dry run: step 6
3. [hand-off: process-engineering-worker] Read. One worker per transcript, all in one message, each told to follow `transcript-tools`, section Read one transcript, with its file, `Source id: <id>`, the rules' `Topics` and the transcript json block from `process-flow-workstream`'s `contract.md`. Save each return to `inventories/<id>.md` as received.
   → a return without its json block: step 3 (max 1)
4. [judgment] Write the synthesis (section Write the synthesis): the Read-Out and Feedback by Topic, then the BASELINE, with `drafts/claims.json`.
5. [hand-off: process-engineering-reviewer] Review, all in one message, each with the sources only: `review-facts` on half A's sources only and on half B's only, each with `drafts/claims.json`; `discovery-workstream`, section Check a discovery draft, items 3 and 4, with the drafts, the inventories and the rules file's path; `review-red-team` with only the Feedback by Topic and the BASELINE, the `Sponsor` as reader, one line of purpose and the rules' bar. Save each return to `reviews/`.
   → a CONTRADICTED verdict, a FAIL or a section under the bar: step 4 (max 2)
6. [judgment] Close. Write `DONE.md` item by item with evidence, `STATUS.md` and `LOG.md`. Report: transcripts read and skipped, the bullet counts of both documents, the DONE items open and why, that the drafts await the owner's review before anything is shared, and as one numbered list the questions (a planned interview never held, a contradiction only the owner can call) and the hand-offs: "launch `process-flow` for this engagement, process `<slug>`" for each process the BASELINE names, with the inputs spelled out.
   → reported: done

## Write the synthesis

From the inventories, not the transcripts:

1. By `interview-synthesis`, Steps 1 and 2 and its anonymization check: `drafts/Interview Read-Out <date>.md` (internal, attributed by role, every bullet citing its claim id) and `drafts/Interview Feedback by Topic <date>.md` (anonymized, `(Nx)` counts of interviews, the caveat block). The `(Nx)` counts come from matching claims across inventories by the shared tags; the leading flags feed the caveat.
2. By `project-engagement-baseline`, section 2: `drafts/BASELINE <date>.md`, about two pages, built from the two drafts and the inventories (they stand in for the research reports), with the tensions ranked and the questions for the grill. Every statement cites a source id and location.
3. Where the sources leave a gap (a planned interview never held, a contradiction between interviews), write the best supported version, mark the gap, and make it a question.

On a revision, answer every finding in a ` v2` of the draft it concerns.

## DONE

Copy into `DONE.md` and mark each item `met`, `open` or `n/a` with a reason, citing the file, line or review that proves it. Items marked (checker) rest on the reviewer's PASS.

1. Every transcript in scope has an inventory, or is listed as skipped with the reason (duplicate, not an interview, unreadable); every interview `Interviews` plans is accounted for.
2. Every Read-Out bullet and every BASELINE statement cites a source id and location.
3. Every `(Nx)` equals the number of distinct interviews whose inventories carry the point (checker).
4. The Feedback by Topic passes the anonymization check against `Anonymize` and the Read-Out headings (checker).
5. Both facts halves recorded; no CONTRADICTED left; every NOT IN MY SOURCES fixed or removed.
6. The red-team check, reading the Feedback by Topic and BASELINE as the `Sponsor`, at or above the bar.
7. The assessment summary, when one exists, is a source (`A01`) and its topics were the tags.
