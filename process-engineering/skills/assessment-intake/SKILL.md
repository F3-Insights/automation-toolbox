---
name: assessment-intake
description: "The assessment intake job, run by process-engineering-assessment-intake, not for a user request: its Steps, the section Write the summary and its DONE checklist. Turns a pre-engagement assessment's saved CSV exports into an anonymized Assessment Summary (who answered against who was invited, the systems, data and recurring processes named with the hours stated, ideas ranked by how many raised them), the proposed interview topics and candidate opportunities, recounted and red-teamed by process-engineering-reviewer. Adds to discovery-workstream. Not for interview transcripts (discovery-synthesis)."
user-invocable: false
---

# Assessment intake

Before the interviews, the engagement knows what the client's people reported: their systems and data, the recurring work and what it costs them in hours, and their ideas, counted and anonymized. The summary proposes the interview topics and points scoping at the likeliest opportunities. This skill adds to `discovery-workstream` (the engagement, the rules file, the Run folder, conduct, claims and checks, questions); read it first.

## Inputs

- **Engagement** (required): the name of its private Context. Its `assessment` Source holds the exports.
- **Export date** (optional): which export to summarize. Default: the newest.
- **Instructions** (optional): the owner's words for this Run; they override the defaults, never `DISCOVERY-RULES.md`.
- **Dry run** (optional): list the exports, the counts you would check and the questions; dispatch nothing and write only `STATUS.md`.

## Steps

1. [judgment] Orient. Read the Context, `DISCOVERY-RULES.md`, `ENGAGEMENT-CONTEXT.md`, and the `working` Source for an earlier summary of the same export.
   → no rules file: stop
   → the export is already summarized and nothing is newer: done
2. [judgment] Register the exports. Each Responses and Ideas CSV becomes a source (`A01`, `A02`) in `sources.json` with its date and row count.
   → no export saved (the question "save the assessment export into the engagement folder" goes in the report): stop
   → dry run: step 5
3. [judgment] Write the summary and `drafts/assessment-topics.md` (section Write the summary), with `drafts/claims.json`.
4. [hand-off: process-engineering-reviewer] Two checks at once, each with the sources only, never your reasoning: `discovery-workstream`, section Check a discovery draft, items 2 and 4, with the draft, `sources.json`, the CSV exports and the rules file's path; and `review-red-team` with only the summary, the `Sponsor` as reader, one line of purpose and the rules' bar. Save each return to `reviews/`.
   → a FAIL or a section under the bar: step 3 (max 1)
5. [judgment] Close. Write `DONE.md` item by item with evidence, `STATUS.md` and `LOG.md`. Report: the summary's path, responses against invited by role group, the top ideas by count, DONE items open, and as one numbered list the questions (the invited count if the rules lack it; whether to adopt the proposed topics, as the `Topics` line) and the hand-offs: "arm `discovery-synthesis` for this engagement once the interviews are done, with the summary as `A01` and the topics as its tags", and that automation scoping reads the candidate opportunities from `working` once the summary is filed.
   → reported: done

## Write the summary

`drafts/Assessment Summary <yyyy-mm-dd>.md`, from the CSV rows only:

- **Who answered**: counts by role group against `Assessment invited`, never names; a missing invited count is a question.
- **Systems and data** they named, each with the row ids.
- **Recurring processes** with the hours stated, each figure with its row id; an hour no row states is not written.
- **Ideas** ranked by how many respondents raised them, each with its row ids.
- **Contradictions** between respondents.
- **Hand-offs**: the topic tags and interviewees by role proposed for the interviews, and the candidate opportunities proposed for scoping, each citing its rows.

Then `drafts/assessment-topics.md`: the proposed `Topics` line for the rules file. No free-text answer is quoted if only one person could have written it; no role so specific that it names one person appears.

## DONE

Copy into `DONE.md` and mark each item `met`, `open` or `n/a` with a reason, citing the file, line or review that proves it. Items marked (checker) rest on the reviewer's PASS.

1. Every export the `assessment` Source holds is in `sources.json`, dated, or skipped with a reason.
2. Every count and ranking recomputes from the CSV rows (checker).
3. The response rate is stated against `Assessment invited`, or the missing count is a question.
4. No respondent can be identified from the summary: no name, no unique role, no quote that only one person could have written (checker).
5. Every idea, process and opportunity cites its row ids.
6. The red-team check, reading as the `Sponsor`, grades every section at or above the bar.
