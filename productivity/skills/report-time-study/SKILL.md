---
name: report-time-study
description: Where did the owner's time actually go. Reconstructs every day of a period (the last full month by default) in ten-minute slots from local signals, meeting transcripts, the calendar and sent mail; tags each slot to domains and topics with an evidence tier; lists what got done and what was said but not seen done; batches the owner's questions into the report and applies the answers; rebuilds the tables, dashboard, report and a said-but-not-seen JSON. Unattended; local files only, nothing sent or published. Use for "where did my time go last month", "run the time study for September", "apply my answers to the time study"; run it as the time-study agent.
argument-hint: "[home folder] [period yyyy-mm, default the last full month] [or one window D1_to_D2] [answers]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Agent, Bash(productivity-time-study-check:*), Bash(productivity-time-study-collect:*), Bash(productivity-time-study-tool:*), Bash(productivity-time-study-said-not-seen:*), Bash(productivity-time-study-day-lint:*), Bash(mkdir -p:*)
---

# Executive time study

The procedure the `time-study` agent follows, for one owner and one period: every day of the period, ten-minute slot by slot, with the evidence for each. Run it as that agent, the main session, because it fans out many workers; a sub-agent cannot. It reads nothing in bulk itself; workers read transcripts and signal files, and code does every sum.

It runs unattended. Nothing is asked live: the questions only the owner can settle go into each window's `questions.md`, its report and the Run's report as one numbered list with proposed answers, and the owner answers when they choose, through the next launch's Answers or a file in the window. Nothing the owner has not said is written into their rules.

**The home (H)** is the time-study tool's private home folder, given as the Time-study home input. It holds the owner's `domains.csv`, `groups.csv`, `topics.csv` and `mapping.md` (the standing rules, and the map from people, repositories and folders, email domains, Teams tenants, websites and recurring meetings to domains), one folder per window under `H/data/raw/<D1>_to_<D2>/` (W below), the built tables in `H/data/`, and the dashboard, reports and said-but-not-seen files in `H/out/`. Nothing the owner owns is kept in this repository.

**The tool** is a separate time-study program (`python -m timestudy`): it collects, validates, builds the tables and draws the dashboard. Its home is normally `private/` inside its own folder, and `productivity-time-study-tool H <command>` runs it from there (or from the checkout `--repo` or the `repo` setting under `[report-time-study]` names; H itself can come from the `home` setting there), so every call is one plain command. The commands around it:

```bash
productivity-time-study-check H [--period P] [--window W] --format json   # done, test by test; --precheck for the scheduler
productivity-time-study-collect H [--period P] [--window W]                # collect every window not yet collected
productivity-time-study-tool H build | summary | dashboard                 # the tool itself; --save FILE keeps the output
productivity-time-study-day-lint H/data/raw/W/days/D --domains H/domains.csv [--topics H/topics.csv]
productivity-time-study-said-not-seen H/data/raw/W [--review W/said-not-seen-review.json]
```

`rules.md` beside this file holds the mechanics: the window layout, the worker models and fan-out limits, the verification checks, the questions, the report, the said-but-not-seen file and the privacy rules. The workers' instructions are the four sections at the end of this skill, each pointing at its brief in `briefs/` with a fixed return format. Why the study has this shape is `DESIGN.md`.

**User provided:** $ARGUMENTS

## Steps

1. [script] Scope the Run. Under a scheduled Automation, `time-study-collect` has already collected every window the Run needs (its first line is in the inputs); started by hand, run `productivity-time-study-collect H --period P --window W` first. Then run `productivity-time-study-check H --period P --window W --format json`. Its `windows` and `new_windows` are the Run's windows, in date order, each with the tests still open. On a dry run, stop here and report the plan: each window, what it lacks, the dispatches it needs, and the collect line. → every test met and no answers given: stop → the check could not run: stop
2. [judgment] Frame each window, oldest first. Read W's `run-log.md` (what earlier runs did and left open), `coverage.md` (each source per day: a count, or null and why), H's `mapping.md`, `domains.csv` and `topics.csv`, and W's `owner_stated.md` and `calls_confirmed.csv`. A window the collect could not fill is recorded as a gap in its run log and the Run's report, and the Run goes on with the others. When the Answers input is given, save it verbatim as `W/answers-<today>.md` in the window it names (or the one window with open questions) before anything else. → no domains.csv in H: stop
3. [hand-off: productivity-worker] Dispatch one `productivity-worker` (model sonnet, section Segment a recording) per recording in `W/recordings.json` that has no `meetings/<recording_id>.md`, in parallel within the fan-out limit in `rules.md`, whose prompt is the path of its own `W/work/segmenter-<recording_id>/input.json` and nothing else. A MISMATCH or BLOCKED recording is a gap for the report, not a stop. → returns read: step 4
4. [judgment] Verify every new segment file against `recordings.json` with the checks in `rules.md` ("Checking a segment file"). Re-dispatch a failing recording once with the failure named; one that fails again is a gap in the report. → a file fails: step 3 (max 1)
5. [hand-off: productivity-worker] Dispatch one `productivity-worker` (model opus, section Assemble a day) per day that lacks `slots.csv` or `day.md`, in parallel within the limit, whose prompt is that day's input paths: `W/signals/<date>/`, the segment files dated that day, W's `owner_stated.md` and `calls_confirmed.csv`, and H's `mapping.md` and `domains.csv`. Each writes `W/days/<date>/slots.csv` and `day.md`. This step re-runs once for the days that step 10's answers or step 8's accepted flags change, in one pass carrying both, with the day's previous files to revise; neither loop re-runs a day on its own. → BLOCKED: step 6
6. [hand-off: productivity-worker] Dispatch one `productivity-worker` (model sonnet, section Classify a day's topics) per day that lacks `topics.csv` or whose slots changed, in parallel within the limit, with that day's paths and H's `topics.csv`, `mapping.md` and `domains.csv`. → BLOCKED: step 7
7. [script] Run `productivity-time-study-tool H build`. It stops on a day without 144 contiguous slots, a slot whose shares do not sum to 1, an unknown domain, or a topics file that misses a slot or names an unknown topic, and names the file and the row. → a slots.csv fails: step 5 (max 1) → a topics.csv fails: step 6 (max 1)
8. [hand-off: productivity-reviewer] Dispatch one `productivity-reviewer` (model sonnet, section Check sampled slots) per window that has no `check.json` or whose slots changed, whose prompt is the paths of each day's `slots.csv` and the raw evidence (W's `signals/`, `meetings/`, `owner_stated.md`, `calls_confirmed.csv`, H's `mapping.md` and `domains.csv`), never `day.md` or an assembler's return: the check is worth something only if the checker has not seen the reasoning. Save its JSON block as `W/check.json` and read every flag against the evidence it cites. A flag that holds up is applied in step 5's single re-run, with the owner's answers when there are any; a flag the evidence cannot settle becomes a question. → flags read: step 9
9. [judgment] Write the questions. Build the full set from every `day.md`, the checker's flags and the segmenters' returns, in the order `rules.md` ("The questions") gives, each with its evidence and a proposed answer, and save it as `W/questions.md`, ending with the short list: the handful only the owner can settle, then one final item, "accept every other proposed answer and every checker flag". Nobody is asked now; the list goes in the report and the Run's report. → answers saved for this window: step 10 → no answers: step 11
10. [judgment] Apply the owner's answers. The final item's "ok" is the owner's answer to every proposed answer and flag the list did not ask about. A standing rule (true every time: for example a person's calls split 70/30 between two projects, evening gaps are personal) becomes a row in H's `mapping.md`, in the table of its kind, marked confirmed by the owner with the answers' date. A one-off fact goes to W's `owner_stated.md`, and a call span the owner confirms to `calls_confirmed.csv` with the evidence in `note`. An owner-stated time that conflicts with a verified one is recorded as stated and the conflict stays in the report; it never overwrites the verified time. Note in `run-log.md` which days change. → answers or accepted flags change a day: step 5 (max 1) → no day changes: step 11
11. [script] Run `productivity-time-study-tool H build`, then `productivity-time-study-tool --save H/out/summary-<window>.txt H summary` and `productivity-time-study-tool H dashboard`. → build fails: stop
12. [judgment] Settle said but not seen across the window. For each item in the days' said-but-not-seen sections, look in the later days' `## Done` sections and signal files for the commitment being kept. Write `W/said-not-seen-review.json` (an item's `id` or `ref` to `status` seen or dropped, with the `evidence` or `note`; open items are left out), then run `productivity-time-study-said-not-seen W --review W/said-not-seen-review.json`. It writes `H/out/said-not-seen-<window>.json`, the file other orchestrators read. → written: step 13
13. [judgment] Write the report, `H/out/report-<window>.md`, in the order `rules.md` ("The report") gives. Every hour and count is copied from the summary or the built tables, never added up by the model. When questions are still open, the report's second line is "provisional: questions open" and the short list closes it. Append to W's `run-log.md` what ran, what each source gave, the answers applied and what is still open. → another window: step 2 → every window reported: step 14
14. [script] Run `productivity-time-study-check H --period P --window W` last and report its result: per window the report's path and the three findings that most change the owner's picture, the said-but-not-seen counts and file, and every window's short question list, numbered, as the Run's questions for the owner. Done when the check meets every test; a window waiting on answers is done for this Run. → reported: done

On a stop, say why in one line and what the owner can do about it: the source that failed with its reason, the window that already holds a date, or the build's own message.

## When the session runs short

A month is many dispatches. Finish the window in hand to a report (provisional, naming what is missing) before starting another, and never leave a window with day files newer than its report. The next Run starts from `time-study-check`, which shows what is left.

## Where the output goes

All of it under H, which the tool's repository ignores as a whole: the window's signals, segment files, day files, questions, answers, check, review and run log in W; the owner's standing rules in `H/mapping.md`; the built tables in `H/data/`; the dashboard at `H/out/dashboard.html`; the summary, the report and the said-but-not-seen JSON in `H/out/`. Never a hosted page, never a commit, never a message, unless the owner asks for something shareable.

## Segment a recording

For `productivity-worker`, dispatched with model sonnet, one recording each. Follow `briefs/meeting-segmenter.md` in this skill's folder as written: it is the single copy of the instructions and its return block is fixed. Your input is `W/work/segmenter-<recording_id>/input.json`. Write only `W/meetings/<recording_id>.md` and your own `work/` folder.

## Assemble a day

For `productivity-worker`, dispatched with model opus, one day each. Follow `briefs/day-assembler.md`. Write only `W/days/<date>/slots.csv`, `day.md` and your own `work/` folder; `productivity-time-study-day-lint` is your self-check.

## Classify a day's topics

For `productivity-worker`, dispatched with model sonnet, one day each. Follow `briefs/topic-classifier.md`. Write only `W/days/<date>/topics.csv` and your own `work/` folder; `productivity-time-study-day-lint` is your self-check.

## Check sampled slots

For `productivity-reviewer`, dispatched with model sonnet, one window each. Follow `briefs/checker.md`: re-derive the sampled slots from the raw evidence only, never `day.md` or an assembler's return. Write nothing; return the brief's JSON block, which the main agent saves as `W/check.json`.
