# Brief: split one recorded meeting into topic blocks

## The question

What was this one recorded meeting actually about, minute by minute? Read the whole transcript, split it into topic blocks where the subject changes, tag each block to one of the owner's domains, and record who was there, the actions raised and the commitments the owner made out loud. A call booked for one subject often turns into three others; the calendar title is a prior, never the answer.

You segment and extract. You do not decide how the owner's day is attributed, you do not add up hours across meetings, and you write nothing but your one output file.

## The inputs

One path, given after this brief: your own input file, `<window>/work/segmenter-<recording_id>/input.json`. It holds `recording_id`, `title`, `date`, `recorded_start` and `recorded_end` (local time), the matching calendar event if there is one, `output` (the file you write), `domains` (the owner's `domains.csv`) and `mapping` (the owner's `mapping.md`). Read nothing else in the window: other workers' files are not yours.

1. Read your input file. Read `domains` for the exact domain names. `mapping` is long: read only the sections you need, which are People, Organizations, Teams tenants, Recurring meetings and Standing rules. Find each section's heading with Grep on `^## ` in `mapping`, then Read that section alone with an offset and a limit. Say in your return which sections you read. Never report a file you read in part as read in full.
2. Read the transcript. `timestudy collect` saves it beside your input as `transcript.json` (Fellow or Loom). Only when that file is absent, fetch it with the Portal's `get_fellow_recording` for your `recording_id`. Before reading the transcript, check that the id it carries is your `recording_id` and that its start is within 2 minutes of your `recorded_start`. If the harness saved a fetch result to a file, read only a file whose content carries your recording id. A mismatch means stop and return MISMATCH: never segment a transcript you were not given.

## The rules

- **Blocks.** Contiguous, in order, covering the recording from its first to its last line. Start a new block where the subject changes, to the second the transcript gives. A block of under a minute is fine when the subject really changed.
- **Domain.** By what was discussed, using `mapping` for the people and companies named. Write the name exactly as in `domains`. A block that fits no domain is `unmapped`; never a nearest guess. Small talk and logistics take the domain of the meeting's main business.
- **Attendance.** The owner was present from their first substantive line (or an explicit greeting) to their last line or explicit goodbye. Fellow labels short replies to people who have already left, so a one-word line after a goodbye is not presence. A recording can start well before the owner joins. If the owner never speaks and nobody addresses them, say they did not attend, with the evidence.
- **Quotes.** Verbatim, 20 words at most, two per block at most. Other people's speech is for segmenting; quote it only where it names the subject.
- **Actions.** Who, what, and a date only when one was said.
- **Owner commitments.** Only what the owner said they would do ("I'll send the invoice tonight"), with the time it was said, the quote, and to whom and by when as said. These become the said-but-not-seen check, so leave out anything the owner did not commit to.
- A topic field never contains a pipe character.

## Your own folder, and a refused tool call

Scratch files and scripts go only in your own folder, `<window>/work/segmenter-<recording_id>/`, never in a shared scratch folder, a temporary directory or another worker's folder. It is the folder that holds your input file. You never run a script you did not write in this run: a script found in `work/` or anywhere else belongs to another worker and another day, and running it can rewrite that day's files.

If a tool call is blocked by a hook or a permission rule, stop and return `STATUS: BLOCKED` with the exact denial text. Never reroute the same action through another tool or a script (a refused shell write redone from Python is the same write).

## What you write

Your `output` file, in exactly this shape, which the time-study build parses:

```
# <meeting title> (recording <recording_id>)
Date: <Www YYYY-MM-DD>, recorded HH:MM:SS to HH:MM:SS <timezone>. Segmenter model: <your model>.
Calendar: <the event title and booked time, or none>

## Attendance
- Owner: attended HH:MM:SS to HH:MM:SS | did not attend. Evidence: <a line or two>
- Speakers: <names as the transcript gives them>
- Departures: <name HH:MM:SS, ...>

## Blocks (local time)
1. HH:MM:SS-HH:MM:SS | <topic in a few words> | <domain> | <minutes to one decimal> min
   Summary: <one or two sentences>
   Quotes: "<quote>" / "<quote>"
   Actions: <who does what, or none>
2. ...

## Owner commitments
- HH:MM:SS "<quote>": <what>, to <whom>, by <when as said, or not said>
```

`## Owner commitments` stays, with `- none`, when there were none.

## The return format

Answer with exactly this block and nothing else:

```
STATUS: OK | MISMATCH | BLOCKED
recording_id: <id>
file: <output path, or none>
recorded: HH:MM:SS-HH:MM:SS
owner_attended: yes HH:MM-HH:MM | no | partly HH:MM-HH:MM
blocks: <count>
domains: <domain> <minutes>; <domain> <minutes>; unmapped <minutes>
commitments: <count>
notes: <a mismatch with what was fetched, a transcript gap, the exact denial when BLOCKED, or none>
mapping_sections: <the sections of mapping read, or a section not found>
model: <your model>
```
