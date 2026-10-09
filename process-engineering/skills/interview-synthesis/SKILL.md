---
name: interview-synthesis
description: Turn three or more stakeholder interview transcripts into two documents, a per-interview Read-Out and an anonymized Feedback by Topic, with (Nx) counts, Notable flags and a leading-question caveat, so the sponsor sees what people said without seeing who said it. Use after discovery interviews on an engagement. Not for a single meeting; use meeting-portal-notes or meeting-followup. For the reviewed discovery pack with the BASELINE, start discovery-synthesis-orchestrator.
argument-hint: "[folder of transcripts] [engagement or topic name]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/transcript-tools/scripts/srt_transcript_collapse.py:*)
---

# Interview synthesis

You are given a folder of interview transcripts from one engagement and produce two files next to them. The first is for the consultant; the second is for the client sponsor.

1. **Interview Read-Out YYYY-MM-DD.md**: one section per interview, attributed, with topic sub-sections, dense bullets, Notable flags, and action items. Internal.
2. **Interview Feedback by Topic YYYY-MM-DD.md**: one section per topic across all interviews, unattributed, deduplicated, with `(Nx)` counts. Shareable with the sponsor.

Both documents are dense: a Read-Out runs to dozens of bullets per interview, and the Feedback by Topic condenses them to roughly two-thirds as many across twelve to sixteen topics. Match that density; do not pad.

## Step 0: collapse the transcripts

Subtitle exports are half noise. Before reading, run each `.srt` or `.vtt` through `python3 ~/.claude/skills/transcript-tools/scripts/srt_transcript_collapse.py <file> --out <same folder>` (the `transcript-tools` skill) so you read `MM:SS Speaker: text` lines, one turn per line. Meeting-tool `.txt` exports are usually already in that form. If the folder holds both the raw export and a collapsed `.txt` of the same meeting, read the `.txt` and ignore the export; do not double-count a meeting.

## Step 0b: fan out the reading

With three or more transcripts, do not read them yourself. Once they are collapsed, dispatch one `transcript-reader` agent per transcript, all in a single message so they run in parallel, and give every one of them the same topic tag list so the inventories merge. Each returns a numbered claim inventory with speaker roles, verbatim quotes, locations and leading-question flags, then pain points, stated wishes, numbers mentioned and the contradictions inside that transcript.

Work from the inventories after that. The per-interview sections in Step 1 come from each reader's inventory and its pain and wishes lists; the `(Nx)` counts in Step 2 come from matching claims across inventories, which is exactly what the shared tag list makes possible. Open a transcript yourself only to settle a question an inventory raised, and say which ones you opened. The leading-question flags feed the caveat block directly: a point four people volunteered is stronger evidence than one four people agreed to.

## Step 1: per-interview Read-Out

For each transcript, in date order:

- **Heading**: `## N. <Meeting title or interviewee role> · <participants> · <YYYY-MM-DD>`. Use the role when the person's name would be the only identifier, e.g. "shift supervisor, night shift". Take the date from the filename; it is authoritative.
- **Topic sub-sections** (`###`): five to eight per interview, named for what was discussed, not for the agenda. Recurring examples from discovery work: definitions and metrics, data quality and systems, incentives and tension, process and cadence, adoption and change management, tooling approach, handoffs and gaps.
- **Bullets**: about 16 words each. Every bullet is one fact, one opinion, or one request, with the number, system name, or quote that makes it specific. Two bullets that say the same thing become one.
- **Notable**: prefix `**Notable:**` on a bullet that is surprising, contradicts another interview, or names a decision the sponsor has not heard. Expect five to eight per interview, not fifty.
- **Action items** (`###`, last): who said they would do what, by when, if stated.

Open the file with `## Cross-transcript patterns`: eight to twelve bullets on what several interviews said, written after all sections are drafted. Name the pattern and how many interviews carried it, e.g. "Four of six named the handoff from sales to fulfilment as the gap."

## Step 2: Feedback by Topic

Read the finished Read-Out, not the transcripts. Then:

- **Topics** (`##`): twelve to sixteen across the whole set. Merge topics that only one interview raised into a neighbour unless the sponsor asked about that topic.
- **Bullets**: about 17 words, unattributed. Strip every name, role that identifies one person, team name smaller than about eight people, and any detail that would let the sponsor work out who said it. "One respondent" is fine; "the supervisor who runs the night shift" is not.
- **`(Nx)` counts**: when N interviews made the same point, write it once and append `(Nx)`. Count interviews, not mentions; one person saying it three times is `(1x)` and gets no tag. Only tag N of 2 or more.
- **Order within a topic**: most-repeated first, then most consequential.
- **Caveat block** at the top, verbatim in spirit: counts reflect how often a point was raised, and interview questions steered some topics; a `(4x)` on a topic the interviewer asked everyone about is weaker evidence than a `(2x)` nobody was prompted on.

Do not add analysis, recommendations, or a summary. The sponsor reads what their people said. The consultant's view goes in the findings readout, a different document.

## Anonymization check before writing the Feedback file

Grep your draft for every participant name and role string from the Read-Out headings. A hit is a defect. Then read it as the most junior person interviewed and ask whether any bullet could only have come from them. If yes, generalize or drop it.

## Output convention

Both files land in the transcripts folder, named as above with today's date. Say which transcripts were read, which were skipped and why (duplicate, not an interview, unreadable), and the two bullet counts. Do not summarize the content in your reply; the files are the deliverable.

## Portal write safety

This skill does not write to the Insights Portal. If a follow-on asks you to file the action items, hand them to `task-stack-capture` and follow the `portal-write-safety` skill.
