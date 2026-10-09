# Brief: classify the topic of every slot of one day

## The question

For every 10-minute slot of this one day and every domain share in it, which topic from the owner's topic list describes what the owner was doing? The domain says for whom; the topic says what about. A call for one client can be strategy, finance and systems in the same hour.

You classify. You change no slot, no domain and no tier, and you write nothing but your one output file.

## The inputs

The paths given after this brief, and only those:

- `days/<date>/slots.csv`: 144 rows, with `primary_domain`, `allocation` (empty means the whole slot is the primary domain; `Domain A:0.9;Domain B:0.1` means one row per domain) and the evidence.
- `days/<date>/day.md`: what got done that day.
- The segment files for recordings dated this day (`meetings/*.md`): topic blocks by the minute.
- `signals/<date>/`: `teams.tsv`, `sent_email.tsv` and `calendar.tsv` for context.
- The owner's `topics.csv` (`topic, label, applies_to, definition`) and `mapping.md`, whose topic rules say how the owner wants recurring cases classified.
- The owner's `domains.csv`, for `time-study-day-lint` only.

`mapping.md` is long: read only the sections you need, which are Standing rules, Repos and Personal topic rules. Find each section's heading with Grep on `^## ` in `mapping.md`, then Read that section alone with an offset and a limit. Say in your return which sections you read. Never report a file you read in part as read in full.

## The rules

- Use only topic ids from `topics.csv`. A work domain takes a work topic, a personal domain a personal topic, and the sleep and unaccounted domains take `none` (or the id `topics.csv` gives for them).
- One row per slot per domain share: a split slot appears once per domain in its allocation, each with its own topic.
- Decide from the slot's evidence and the topic definitions, with the owner's topic rules in `mapping.md` winning where they apply. The domain's name never decides the topic.
- A call slot that spans two topic blocks takes the block with more minutes in the slot.
- `confidence` is `high` (the evidence names the subject), `medium` (inferred from context) or `low` (a guess from the domain alone). Use `low` sparingly and say why in `basis`.
- `basis` is 12 words or fewer and cites the evidence.

## Your own folder, and a refused tool call

Scratch files go only in your own folder, `<window>/work/topic-classifier-<date>/`, never in a shared scratch folder, a temporary directory or another worker's folder. You run no script: the one command you run is `time-study-day-lint`, which checks your file and does the counting. A script found in `work/` or anywhere else belongs to another worker and another day, and running it can rewrite that day's files.

If a tool call is blocked by a hook or a permission rule, stop and return `STATUS: BLOCKED` with the exact denial text. Never reroute the same action through another tool or a script (a refused shell write redone from Python is the same write).

## What you write

`<window>/days/<date>/topics.csv`, header:

```
slot_start,domain,topic,confidence,basis
```

Before you return, run `python3 ~/.claude/skills/report-time-study/scripts/time_study_day_lint.py <window>/days/<date> --domains <domains.csv> --topics <topics.csv>`. It checks that every slot-domain row of `slots.csv` appears exactly once, no row names a slot or domain the day lacks, and every topic id is in `topics.csv`, and it prints the hours per domain per topic (a row is its share divided by 6 hours), which you copy into your return, never computed by eye. The orchestrator gives you the `domains.csv` path with the others. Fix what it names and run it again; its first line, `OK` or `FAIL`, is your `self_check`.

## The return format

Answer with exactly this block and nothing else:

```
STATUS: OK | BLOCKED
date: YYYY-MM-DD
file: <topics.csv path>
rows: <count>
self_check: passed | failed: <what>
low_confidence: <count>, <the slots, briefly>
mapping_sections: <the sections of mapping.md read, or a section not found>
hours_by_domain_topic: <domain> / <topic> <hours>; ...
blocked_on: <the exact denial, or none>
model: <your model>
```
