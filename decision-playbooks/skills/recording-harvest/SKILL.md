---
name: recording-harvest
description: Harvest the transcripts of the owner's recorded narrations (screen recordings in which they explain how and why they handle something; Loom is the source scripted today) into a local archive and the decision store, then triage and classify each one so the narrations that state the owner's rules reach playbook-distilling. Transcripts only, never video. Use for "harvest my Loom videos", "classify the new recordings". Not for meeting transcripts to be filed as notes and tasks; use meeting-scheduled-worker.
allowed-tools: Bash(python3 ~/.claude/skills/recording-harvest/scripts/loom_harvest.py:*), Bash(python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py:*), Read, Write, AskUserQuestion
---

# Harvest recordings

Pull transcripts from the owner's recording library into the archive, register each in the decision store, then classify them. Narrations in which the owner explains how they decide are playbooks spoken aloud: the top-down half of the evidence, beside the cases mined from sent mail. Loom is the source with a script today (`scripts/loom_harvest.py`); another platform needs its own harvester writing the same archive shape.

## Before you start (ask the owner for what is missing)

1. **The video list.** One share link or video id per line, in the file the setting `video_list` under `[recording-harvest]` names (or `--videos`). Loom has no API to list a library, so the owner copies the links from their library page; scrolling the library and copying links in bulk beats one at a time.
2. **The archive folder.** The setting `archive_dir` under `[recording-harvest]` (or `--archive`), where each video's files are kept. It holds the owner's spoken words: keep it outside every repository and in the owner's backup.
3. **Cookies, for private videos.** A Netscape-format cookies.txt exported from a browser tab signed in to Loom (a "cookies.txt" browser extension does this), named by the environment variable `LOOM_COOKIES_FILE` or `--cookies`. It is a credential: never in a repository, never shown.
4. **The decision store.** `decision-case-mining` owns it; run its `init` once if `decision_store.py stats` says there is no database.

## Steps

`loom_harvest.py` below is `python3 ~/.claude/skills/recording-harvest/scripts/loom_harvest.py`; `decision_store.py` is `python3 ~/.claude/skills/decision-case-mining/scripts/decision_store.py`.

### 1. Check run, always first

The harvester uses Loom's undocumented web endpoint, so check it still works on a small sample before running the whole list:

```
loom_harvest.py --limit 3
```

If all three fail, stop. Open one share page in the signed-in browser, find the transcript and caption requests, update `transcript_links()` or the headers in the script, and check again. Never run the full list against a broken endpoint.

### 2. Full harvest

```
loom_harvest.py
```

The default three-second pause between videos stays; this is a polite, mostly one-time job. Each video lands in `ARCHIVE/<video_id>/` (transcript.json, captions.vtt, meta.json) and is upserted into the store as a `recording` source with its content hash. Re-runs are safe; a video that came back `NO_TRANSCRIPT_FOUND` can be retried later.

### 3. Triage, then classify each transcript

**Why transcripts first.** A transcript is a few kilobytes and a video hundreds of megabytes. The transcript is the cheap scan that decides whether a video is worth anything more. This skill never downloads a video or extracts a frame; that happens later, if ever, only for narrations with noted visual moments. Expect most of a library to be set aside at this step, because most recordings are meetings, not narration. That is the triage working.

**Triage cheaply, in this order, stopping at the first clear answer:**

1. Title and duration (from meta.json). "Meeting with ...", "Weekly sync", or recordings over 30 minutes are almost always meetings.
2. The first 50 or so lines of the transcript. Several speakers trading turns is a meeting; the owner speaking alone in the second person ("so what you'll want to do is ...") is narration. Do not read deeply what triage settles in seconds.

Classify each into exactly one:

- **meeting-recording**: a recorded call, not made to explain anything. Set aside for good: record the class so it is never triaged again, and read no further. The transcript stays archived; meeting content may become a case source later, outside this skill.
- **playbook-narration**: the owner explains how or why they handle a category of decision or process. The valuable kind. Note the category (one of the case categories in `decision-case-mining`, or propose a new one).
- **app-walkthrough**: the mechanics of a tool or spreadsheet. Useful as a procedure, not as a rule for deciding.
- **one-off**: about a single past situation. Set aside.

Only `playbook-narration` transcripts, and borderline `app-walkthrough` ones, get a full read and `visual_moments` notes. Record the class by upserting the source with its meta (the upsert keeps the hash and the path):

```
decision_store.py add-source --json '{"type": "recording", "external_ref": "<video_id>",
  "url": "https://www.loom.com/share/<video_id>", "title": "<title>",
  "content_hash": "<from meta.json>", "raw_path": "<from meta.json>",
  "meta": {"platform": "loom", "classification": "playbook-narration", "category": "spend-approvals",
           "duration": <seconds>, "visual_moments": ["t=272: shows the approval screen"]}}'
```

`visual_moments` are the timestamps where the narration points at the screen ("as you can see here ..."), the only frames worth extracting later.

### 4. Wrap up

Run `decision_store.py stats` and `decision_store.py audit` (0 violations). Report to the owner: harvested and failed counts, the class breakdown, and which categories now have narration. Cross-check `cases_by_category`: a category with both narration and mined cases is ready for `playbook-distilling`.
