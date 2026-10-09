# Mechanics for report-time-study

The commands, the window's layout, the workers, the checks and the privacy rules: how the steps run. The owner's own rules are not here. They live in the tool's home folder H, in `H/mapping.md` (standing rules and the domain map) and `H/*.csv` (domains, groups, topics, modes), and the steps say when to read them. Never copy anything from H into this repository.

## The tool and its home

The tool is a separate time-study program, standard-library Python 3.11 or later, run as `python -m timestudy`. Its home H holds the owner's data and is ignored by that program's git as a whole; by default it is `private/` inside the program's folder. The Run is given H as the Time-study home input, and every call goes through a command that takes H as an argument, so no path is written here and every call is one plain command: `python3 ~/.claude/skills/report-time-study/scripts/time_study_tool.py H
<command>` runs the tool from the checkout `--repo` names, else the `repo` setting under
`[report-time-study]`, else the folder beside H. Read the tool's `README.md` for the data model when a check below is not enough.

## The commands

| Command | Writes | Used at |
|---|---|---|
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_check.py H [--period P] [--window W] [--format json] [--precheck] [--out FILE]` | nothing (or `--out`) | step 1, step 14, a scheduler's precheck and finish |
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_collect.py H [--period P] [--window W] [--dry-run-if true]` | `W/signals/`, `recordings.json`, segmenter inputs and transcripts, `coverage.md` for each window not yet collected, through the tool's `collect` | a scheduler's prepare step; step 1 when started by hand |
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_tool.py H build` | `H/data/*.csv`, `H/out/mapping_changes.csv` | steps 7 and 11 |
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_tool.py --save FILE H summary` | FILE | step 11 |
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_tool.py H dashboard` | `H/out/dashboard.html` | step 11 |
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_day_lint.py W/days/D --domains H/domains.csv [--topics H/topics.csv]` | nothing | the day assembler and the topic classifier, before they return |
| `python3 ~/.claude/skills/report-time-study/scripts/time_study_said_not_seen.py W [--review FILE]` | `H/out/said-not-seen-<window>.json` | step 12 |

The Run's scope (`time-study-check` and `time-study-collect` share it): the period, by default the last full month, widened back to the day after the latest window when that window ended before the period began, and never past yesterday; or the one window named. The days of the span that no window holds become new windows of at most 14 days, cut evenly, at most 45 days in one Run (the newest; the rest are named in the notes). A window that already exists keeps its dates, even across a month's edge.

The tool's `collect` reads, for each day: Claude Code prompts (entrypoint `cli`, origin human), file saves in the owner's repositories and synced folders, git commits by the owner, Chrome visits (titles and domains), PC sleep, wake and restart events and webcam call-leave events from the Windows event logs, Teams calls and the owner's messages from the Teams IndexedDB of every tenant, Zoom and Meet join and post-meeting pages from browser history, Claude chat opens from Chrome history and the Claude Desktop cache, the Portal's calendar and outgoing mail, and the meeting recordings with their transcripts (Fellow through the Portal, Loom from the owner's library). It says per source per day what it read and what it could not, with the reason, in `coverage.md`; a source it could not read is never written as a zero. It runs on the owner's machine only, so a scheduled Run needs that machine on.

## The window

```
H/data/raw/<D1>_to_<D2>/          W, one folder per window, both dates inclusive
  run-log.md                      what each run did and left open; read at step 2, appended at 2, 10, 13
  coverage.md, coverage.json      per source per day: a count, or null and why (collect)
  signals/<date>/*.tsv            local and Portal signals (collect)
  recordings.json                 the window's recordings (collect)
  work/<worker>-<id>/             one folder per worker: its input file and any scratch
  meetings/<recording_id>.md      one per recording (segmenters)
  days/<date>/slots.csv           144 rows (assemblers)
  days/<date>/day.md              done, said but not seen, conflicts, questions (assemblers)
  days/<date>/topics.csv          one row per slot per domain share (classifiers)
  owner_stated.md                 one-off facts from the owner, by date
  calls_confirmed.csv             call spans confirmed by evidence or the owner
  check.json                      the checker's result
  questions.md, answers-<date>.md the numbered list and the owner's answers, verbatim
  said-not-seen-review.json       the orchestrator's review of said but not seen (step 12)
```

A date may sit in only one window. Name a window by its first and last dates. `meetings/` must hold no file named `*_summary.md` for a recording: the build skips those.

## Portal sources

The tool's `collect` reads the Insights Portal with the configuration in the home's `sources.toml` and writes, per day, `signals/<date>/calendar.tsv` (the owner's events, clones, busy blocks and cancellations removed), `family_calendar.tsv` (calendars other people share in, kept apart; evidence only where `mapping.md` says so) and `sent_email.tsv` (time, inbox, recipients, words of new text and a gist of six words at most, never a body), and for the window `recordings.json` with one `work/segmenter-<recording_id>/input.json` and `transcript.json` per recording. The orchestrator reads no Portal source itself and never fetches a transcript; a segmenter fetches its own only when `transcript.json` is absent.

Each segmenter's input file holds that one recording's entry plus `output` (`W/meetings/<recording_id>.md`), `domains` (the path of `H/domains.csv`), `mapping` (the path of `H/mapping.md`) and `transcript`. Nothing is shared between workers.

## Workers

| Worker | Agent | Brief | Model | Tools | One per | Writes |
|---|---|---|---|---|---|---|
| meeting segmenter | `time-study-meeting-segmenter` | `briefs/meeting-segmenter.md` | sonnet | Read, Grep, Write, the Portal's `get_fellow_recording` and `get` | recording | `meetings/<recording_id>.md` |
| day assembler | `time-study-day-assembler` | `briefs/day-assembler.md` | opus | Read, Grep, Glob, Write, `time-study-day-lint` | day | `days/<date>/slots.csv`, `days/<date>/day.md` |
| topic classifier | `time-study-topic-classifier` | `briefs/topic-classifier.md` | sonnet | Read, Grep, Write, `time-study-day-lint` | day | `days/<date>/topics.csv` |
| checker | `time-study-checker` | `briefs/checker.md` | sonnet | Read, Grep, Glob; no Write, no Edit | window | nothing; returns one JSON block |

Each worker is a registered agent, because each meets the tests for one in `DESIGN.md`: the segmenter reads a whole transcript (bulk reading), the segmenters, assemblers and classifiers run one per item (fan-out), the checker must not see the assemblers' reasoning (independence), and each has an allowlist the harness enforces (a tool boundary). The agent file pins the model and the tools and points at the brief; the brief is the single copy of the instructions. The dispatch prompt is the worker's own input paths only. A runtime without these agents runs the same brief as a general-purpose sub-agent whose prompt is the brief's full text followed by those paths. A worker writes only the files in its row and its own `work/<worker>-<date or recording_id>/` folder, runs no script it did not write, and returns BLOCKED with the exact denial when a hook or a permission rule refuses a call. The orchestrator runs on the session's model (Opus).

The workers' Write is fenced by the session, not by the agent files: a scheduled run should grant Write and Edit on the home and nothing else, so a write outside it is refused and the worker returns BLOCKED naming the path. Started by hand, the session's own permissions are the fence. The segmenter, assembler and classifier load `orchestration-workstream` for its conduct; their return is still the brief's fixed block.

## Limits

- **Days per window:** at most 14. A longer span is several windows; one Run takes at most 45 days.
- **Retention:** Claude Code keeps its transcripts for the number of days its `cleanupPeriodDays` setting says (about 30 by default). A day older than that is short of its main typing signal; `coverage.md` shows it as null, and the report says so rather than reading the gap as idle time.
- **Fan-out:** at most 8 workers dispatched at once. More recordings or days wait for the next batch.
- **Re-runs:** each loop in the steps runs at most once more, and the checker's flags and the owner's answers share one re-run of the day assemblers. What is still wrong after that is a question for the owner.
- **One Run per home at a time.**

## Checking a segment file

Step 6, per file, against `recordings.json`:

- The heading carries `(recording <id>)` with the same id, and the `Date:` line the same date. The date to check against is the recording's `date` in `recordings.json`, never a date found inside the segment file's text: booking dates and dates people mention appear there too.
- The recorded start in the file is within 2 minutes of `recorded_start`.
- Blocks are numbered in order, each `N. HH:MM:SS-HH:MM:SS | topic | domain | M.M min`, inside the recorded span, not overlapping.
- Every domain is a name in `domains.csv`, spelled exactly, or `unmapped`.
- The attendance section says whether the owner attended and from when to when.
- The segmenter's return names the same recording id and file.

## Checking a day

`build` checks the shape (step 7). The orchestrator reads each assembler's return and the day's `day.md` for: a said-but-not-seen section and a questions section, present even when empty; every conflict between an owner-stated and a verified time listed, not resolved; and no slot inside a recording where the segmenter found the owner absent attributed to that call.

## The questions

`W/questions.md` holds the full set for the whole window, numbered, in this order, each with the evidence in a few words and a proposed answer:

1. Gaps over 30 minutes in waking hours (the owner's waking hours are in `mapping.md`; without them, 06:00 to 22:00).
2. Conflicts between an owner-stated time and a verified one.
3. Domains the assemblers or the classifier marked low confidence, and unmapped signals worth more than 30 minutes in the window.
4. Recurring events whose attendance is unconfirmed (for example, an optional recurring meeting).
5. Said but not seen: did it happen, and when.
6. Checker flags that the evidence could not settle.

Each question that would recur every week says so and proposes a standing rule for `mapping.md`.

The owner sees one short numbered list, not the full set: the handful of questions only the owner can settle, each with its proposed answer, then one final item, "accept every other proposed answer and every checker flag". Nobody asks it live: the list ends `questions.md`, closes the window's report, and is the Run's questions for the owner. The owner answers in a line ("1) ok 2) no, it was a client call 3) ok") when they choose, as the Answers of the next launch (with the window named) or in a file `W/answers-<date>.md`; either makes the precheck see work. The final item's "ok" accepts everything in `questions.md` and `check.json` the list did not ask. The answers and the accepted flags then go to the day assemblers together in the one re-run of step 5.

## The report

`H/out/report-<window>.md`, in this order: a five-line answer to "where did the time go"; the day timeline, merged runs of identical slots; the meeting topic blocks per call; hours by domain, by tier, by mode and by topic, copied from `summary` and the tables in `H/data/`; what got done; said but not seen; patterns (context switches per hour, meeting against focus hours, first and last activity, share of each call on its booked topic, personal time by topic); the questions still open. Arithmetic comes from the tool. A figure the tool does not produce is left out, not computed by the model.

## The said-but-not-seen file

`H/out/said-not-seen-<window>.json`, written by `time-study-said-not-seen` from the days' said-but-not-seen sections and the orchestrator's review (step 12). It is the time study's output for other orchestrators: task capture reads it for commitments to file, and follow-up reads it for promises to chase. Its shape:

```json
{"schema": "time-study/said-not-seen@1", "window": "D1_to_D2", "since": "D1", "until": "D2",
 "generated_at": "...", "report": "report-D1_to_D2.md",
 "counts": {"items": 0, "open": 0, "seen": 0, "dropped": 0, "structured": 0, "days_read": 0},
 "days_without_section": [],
 "items": [{"id": "12 hex, stable across re-runs", "ref": "YYYY-MM-DD#n", "date": "YYYY-MM-DD",
            "time": "HH:MM:SS", "source": "meetings/<recording_id>.md", "recording_id": "...",
            "quote": "...", "commitment": "...", "to": "...", "by": "...", "domain": "...",
            "why_not_seen": "...", "status": "open | seen | dropped",
            "review_evidence": null, "review_note": null, "structured": true, "text": "the line"}]}
```

A reader acts only on `open` items, keys what it has done on `id`, and treats an item with `structured: false` (an older day file's free text) as a lead to confirm, not a commitment to file as written. The file names people the owner spoke with; it stays in H like everything else.

## Privacy

- Everything a run produces is personal data and stays under H. Never commit it, publish it, paste it into a file of this repository, an issue, a commit message or a message, or put it on a hosted page unless the owner asks for something shareable.
- Browser: page titles and domains only, never page content. SMS: counts and direction only. Email and chat: a gist of six words at most; a body is read only where the effort estimate needs it, and never copied.
- Other people's speech in a transcript is for segmenting only; the report carries short quotes at most.
- Refer to the person studied as the owner in anything outside H.
- The claude.ai headless-browser route was tried and rejected (forced logouts, unofficial endpoints, a stored credential). Claude chat activity comes from Chrome history and the Claude Desktop cache only.

## Lessons from the pilot

Each is a rule now; the briefs repeat the ones their worker needs.

- **Shared scratch folders crossed workers.** Two workers read the wrong transcript from a shared tool-results folder. Pass each worker its own input path, and have the segmenter check that the recording id and start it fetched match its input before reading.
- **Fellow mislabels short lines** to people who have already left. Presence comes from substantive speech and explicit goodbyes.
- **Teams text logs rotate daily.** The IndexedDB is the lasting source for calls and messages.
- **Chrome `visit_duration` is tab time, not attention.** Page opens are the activity signal.
- **Synced workbook saves can be other people's.** Check `lastModifiedBy` before counting a save as the owner's; a save during a gap is inferred at most.
- **The webcam re-initialises within 5 seconds** of leaving any call: the leave time for Teams and Zoom.
- **Phone Link may have stopped syncing.** Check its newest row before reading an empty day as no texts.
- **A recurring optional event is never taken from the calendar.** Attendance is confirmed per occurrence.
- **Owner-stated times that conflict with verified ones are reported, not overwritten.**

From the first full week, where the independent checker's flags were the evidence. The day assembler's brief carries each of these.

- **A call slot is verified only for the minutes the owner was present.** Where presence covers under half the slot, the remainder is inferred or unaccounted and the shares say so. Shares were normalised over the evidenced minutes and the whole slot credited; that is not allowed.
- **Presence and domain are separate tiers, and the slot takes the weaker.** A domain resting only on the Teams tenant, the organizer or a calendar overlap is inferred, or corroborated with a second independent signal, never verified, even when presence is verified.
- **Tab visits are tab time, not attention.** A share resting on browser tabs alone is inferred. `primary_domain` is the largest share.
- **A merge or commit under the owner's identity marked `owner=no`**, plus a page visit, is corroborated at best.
- **Outlook activity logs (`olk`) are on a UTC clock.** Convert to local time before citing.
- **Every typed owner action in a slot** (a prompt, a message, a sent email) gets a share or is named in `concurrent` with a reason. A typed action in another domain must not vanish.
- **A standing split for a person** applies only to calls and chats with no recording and no clear content. A recorded session keeps its topic blocks.
- **The owner's own words about leaving** (breakfast, a workout, a pickup) in a recording set the slots that follow to the personal domain or unaccounted.
- **Content decides over the account.** A chat about a home matter on a work account is personal.
- **A re-run revises, it does not restart.** With the checker's flags and the owner's answers, the assembler revises the previous files, applies every flag, folds the accepted answers in and keeps only the questions still genuinely open.
- **`mapping.md` is long.** The segmenter and the classifier read only the sections they need, found with Grep on the headings, and say which; a worker never reports a partial read as complete.
- **A segment check uses the recording date from `recordings.json`,** never a date found inside the file; booking dates appear in the text.
- **The owner prefers one short list.** The handful of questions that need the owner, then "accept every other proposed answer and every checker flag", and one re-run that applies the flags and the answers together.

From the pilot's worker runs. Every brief and every worker agent file carries these.

- **A worker's scratch lives only in its own folder.** Scratch files and scripts go in `W/work/<worker>-<date or recording_id>/`, never in a shared scratch folder, where one worker can run another day's script and rewrite that day's file.
- **A worker never runs a script it did not write.** A script found in `work/` or anywhere else belongs to another worker and another day.
- **A blocked tool call stops the worker.** When a hook or a permission rule blocks a call, the worker stops and returns BLOCKED with the exact denial, and never reroutes the same action through another tool or a script (a refused shell write redone from Python is the same write).
