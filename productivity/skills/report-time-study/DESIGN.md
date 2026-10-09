# Executive time study: design record

`SKILL.md` is the procedure, `rules.md` the mechanics; this file is why they have that shape.

Where things live:

- **The tool** is a separate time-study program, standard-library Python run as `python -m timestudy`. It writes runtime state (every window, table and dashboard) into its own home folder, so it does not belong in this repository. It builds, validates and draws; it holds no model calls.
- **The procedure** is this skill, with its orchestrator agent `time-study-orchestrator`. It runs unattended under a scheduler or in a plain session.
- **The owner's specifics** (domains, topics, the mapping from people, repositories, folders, email domains, Teams tenants, websites and recurring meetings to domains, and the owner's standing rules) live in the tool's private home folder, `private/` by default: `mapping.md` and the `*.csv` config. Never here.

## The question it answers

"Where did my time actually go?" at 10-minute resolution, over a day or a window of days, and aligned to the owner's domains of work and life (mostly clients). An executive often feels busy but cannot say what they did or finished. The study reconstructs the day from evidence, tags each slot to a domain and a topic, and lists what got done and what was promised but not seen done.

It never invents. A slot with no evidence is "unaccounted" and becomes a question, not a guess.

## What the owner gets

All output is a local file the owner keeps. Never a hosted page, never committed, never posted.

1. **Day timeline.** One row per 10-minute slot, from first to last activity. Each row has a primary activity and domain, any concurrent activity (people multitask during calls), the evidence behind it and an evidence tier.
2. **Meeting topic blocks.** Each recorded call split into topics by the minute, since a call booked for topic A often turns into B, C and D. Each block is tagged to a domain, with short quotes as evidence and the action items raised.
3. **Domain roll-up.** Hours per domain per day and per window, split into live calls, focused work and concurrent work. Also hours of personal time, and hours unaccounted. The tool computes it; the model never adds up hours.
4. **Work modes and topics.** What kind of work each hour was (formal meeting, ad hoc call, technical, messaging, focused work) and what it was about (a topic under each domain), both from the tool's `build`.
5. **What got done.** Verified outputs: things sent, delivered, decided or presented.
6. **Said but not seen.** Commitments the owner made out loud on a call ("I have to send the invoice tonight"), checked against later evidence and listed where nothing shows they happened.
7. **Questions.** One numbered list covering the gaps and conflicts, for the owner to answer in a line each.
8. **Patterns** (window runs): context switches per hour, meeting hours against focus time, time of first and last activity, the share of each call spent on its booked topic, and personal time by topic.
9. **The dashboard**, one self-contained HTML file from `timestudy dashboard`, opened from disk.

## Evidence tiers

Every attribution carries one tier. The roll-up reports hours by tier so the owner sees how much of the picture is proven.

| Tier | Meaning | Example |
|---|---|---|
| verified | A system recorded the owner doing it at that time | Transcript shows the owner speaking; prompt typed; email sent; call joined |
| corroborated | Two indirect signals agree | PC asleep plus a personal block on the owner's calendar |
| owner-stated | The owner said so, in the run or in an answer | "Gym 7:00 to 8:00" |
| inferred | One indirect signal | Browser tab open; file saved in a shared folder |
| unaccounted | Nothing | Becomes a question |

An owner-stated time that conflicts with a verified one is reported, not overwritten: people misremember by minutes, and the transcript does not.

## Signals

Local sources are collected by `timestudy collect` into per-day signal files; the Portal sources (calendar, sent mail, recordings and their transcripts) are collected in code too. The lessons column records what each source teaches.

| Source | Gives | Precision | Lessons |
|---|---|---|---|
| Portal calendar (all scopes) | Booked time, attendees, meeting links, response status | Booked, not actual | Clone and duplicate events and calendars other people share in must be deduplicated and kept apart. An accepted meeting is not attendance. |
| Meeting recordings (Fellow, Loom) | Actual start and end, speakers, full transcript | Seconds | Recorders label short replies to people who have already left. Use substantive speech and explicit goodbyes for presence. A recording can start well before the owner joins. |
| Teams IndexedDB (new client, one profile per tenant) | Call start, end and length per meeting; the owner's own chat messages | Seconds | The text logs rotate within a day, so the IndexedDB is the only lasting source. Call length is for the whole call, not the owner's own stay. Join time comes from the launcher log plus the deep-link visit. |
| Zoom, Google Meet (browser history) | Join page and post-meeting page | Minutes | Zoom's own log is encrypted. A post-meeting page gives an upper bound on the leave time. |
| Sent mail (Portal, every inbox) | Send time, recipients, body | Seconds | Composing starts before the send. Estimate the effort from the length of the new text, not the quoted thread. A mobile-client signature means the owner was away from the PC. |
| Claude Code transcripts | Prompts the owner typed, with working directory and time | Seconds | Keep entrypoint `cli` with origin human. Drop `sdk-cli` (automated launches), sidechains, meta records and prompts one orchestrator injects into another. Claude Code keeps about 30 days. |
| Claude chat | Conversation opens | Minutes | From Chrome history and the Claude Desktop cache. A headless browser logged in to claude.ai is rejected: forced logouts, unofficial endpoints and a stored credential. |
| Codex sessions | Same as Claude Code | Seconds | Automated launches are not the owner's typing. |
| File saves (code repos, synced folders) | mtime per path | Seconds | Worktrees, checkouts and run logs swamp the count; flag them. Synced folders pick up other people's edits; a shared workbook saved during a gap is not proof it was the owner. |
| Git commits | Author, time, repo | Seconds | Commits pulled from other people show up in the same log; filter by author. |
| Chrome history (`visits`) | Page opens, titles, time on the page | Seconds | `visit_duration` is how long the tab stayed on the page, not attention. Opening new pages is the activity signal. Titles only; never page content. Check every profile and browser. |
| Windows System log | Modern Standby entry and exit (Kernel-Power 506/507), restarts | Seconds | Readable through `powershell.exe`. The Security log (lock events 4800/4801) may be denied. |
| Teams SlimCore log | Lock and unlock | Seconds | The clock can be UTC mislabelled as local. Cross-check against Windows Hello start times. |
| Teams chat (IndexedDB, V8-serialized records) | Messages the owner wrote, per chat and tenant | Seconds | An owner may hold a separate identity in each tenant, plus guest identities, and a cache can flag the owner's own messages "not current user". Drop call-event rows and notification-stream copies. Chat volume is often an unseen workload until counted. |
| Webcam device events (Windows event logs) | Leave time for any call | Seconds | The camera re-initialises within seconds of the owner leaving a call: the only per-person leave signal for Teams and Zoom. |
| Outlook activity (event logs) | Active and idle transitions, window focus | Seconds | Separates at the desk and idle within a slot better than sleep entries do. |
| Office file metadata (`lastModifiedBy`) | Who saved a synced workbook | Seconds | Settles "was that save the owner's". |
| Phone Link | Calls, SMS | Seconds | Its sync can stop silently, so it can neither confirm nor rule out texts. Check the newest row before trusting an empty day. SMS content is off limits; counts and direction only. |
| Owner answers | Anything | As stated | Standing rules go to `mapping.md`, one-off facts to the window's `owner_stated.md` and `calls_confirmed.csv`, so a re-run keeps them. |

Other sources worth adding: phone screen time, car or location history, and Office recent-files lists (to tell the owner's own saves from sync).

## How it is built

The portable unit is this skill with its commands and worker briefs, runnable in a plain session. The deterministic ends are commands; the judgment is the briefs.

### Pieces

| Piece | Kind | Job |
|---|---|---|
| `time-study-orchestrator` | Agent, main session (`claude --agent time-study-orchestrator`, or a scheduled Automation) | Follows this skill for a period, window by window, dispatches workers, checks what comes back against its source, batches the owner's questions into the report, applies answers when they come, writes the report and the said-but-not-seen file. Reads nothing in bulk. |
| `report-time-study` | Skill | The procedure as numbered `## Steps`; unattended, so questions are listed, never asked live, and the owner's answers are never guessed. |
| `time-study-check` | Command | The six tests of done for a period or a window, from the home's files; `--precheck` for a scheduler. |
| `time-study-collect` | Command | Plans the Run's windows and runs the tool's `collect` for each one not yet collected; a scheduler's prepare step. |
| `time-study-tool` | Command | Runs one tool command against a home, as one plain command a guarded session may run. |
| `time-study-day-lint` | Command | The workers' self-check of a day's slots and topics, and its hours, instead of a script of their own. |
| `time-study-said-not-seen` | Command | The window's said-but-not-seen list as JSON for other orchestrators. |
| `timestudy collect` | Command, time-study tool | Collects every local and Portal source for a date range into the window's per-day signal files. States what it could not read, never a silent zero. |
| `timestudy build` | Command, time-study tool | Validates every day (144 slots, shares summing to 1, 24.0 hours, known domains and topics), derives calls, modes and topics, applies `mapping.md`'s standing rules and mappings, writes the tables. |
| `timestudy summary`, `dashboard` | Commands, time-study tool | The terminal roll-up and the one-file dashboard. Arithmetic in code, never in a model. |
| meeting segmenter | Brief, `briefs/meeting-segmenter.md`, Sonnet, one per recording | Reads the whole transcript and writes topic blocks by the minute: domain, summary, short quotes, action items, who was present, and the commitments the owner made. |
| day assembler | Brief, `briefs/day-assembler.md`, Opus, one per day | Turns the day's signals, topic blocks, owner rules and domain map into 144 slot attributions with tiers, concurrent work, splits and tags, plus what got done, said but not seen, and that day's questions. |
| topic classifier | Brief, `briefs/topic-classifier.md`, Sonnet, one per day | A topic from the owner's topic list for every slot and domain share. |
| checker | Brief, `briefs/checker.md`, Sonnet, independent | Re-derives a sample of slots from the raw evidence without seeing the assembler's reasoning, and flags every attribution whose evidence does not support its tier or domain. |

The workers' instructions are briefs inside the skill, each run by a registered agent that pins its model and tools. A worker is a registered agent when it meets any of four tests: bulk reading, fan-out, independence from the author's reasoning, or a tool boundary the harness enforces. `meeting-analyst` and `transcript-reader` already read transcripts, but for other contracts (proposed Portal notes, a claim inventory); the segmenter's contract is the meeting file `timestudy build` parses.

Each worker gets its own input file path, and each writes its scratch files under its own name. Workers fanned out over a shared scratch folder can read one another's transcripts and overwrite one another's files. The segmenter checks that the recording id and start time it fetched match its input before reading, and stops if they differ. The orchestrator checks every segment file against its recording before assembling.

### Domain map

Domains are the owner's `domains.csv` in the tool's home folder, aligned by name with the owner's Portal domains. The map from a signal to a domain is owner data, kept in the owner's `mapping.md`, never in this repository:

- Email and calendar: recipient or attendee, then contact, then company, then domain.
- Claude Code and file saves: repository or folder, then domain (a client's synced folder, or an internal tools repository that maps to a technical domain).
- Browser: site, then domain (a client's SharePoint, the Portal, a vendor's site), with personal sites listed explicitly.
- Teams: tenant and identity, then person, then domain.
- Transcripts: the segmenter tags each block by content. The calendar title is only a prior.

A signal the map cannot place goes to the assembler as "unmapped", not given a default, and becomes a question when it holds more than a few slots.

### Attribution rules

- Priority within a slot: a live call the owner is on, then owner-stated off-PC activity, then typing (prompts, sent mail, chat messages), then page opens, then saves.
- Anything else active in the same slot is recorded as concurrent, not dropped. Working during calls is normal.
- The PC asleep or locked for most of a slot means off-PC unless another device shows activity. The last input is roughly the PC's idle-to-sleep delay before each sleep entry.
- A restart kills local sessions. Crash-recovery prompts afterwards are overhead, not new work.
- A slot where a synced file saves and there is no other signal stays inferred.
- A slot can carry a split across domains (for example, a call split 70/30 between two projects) and tags that run alongside its domain (for example `volunteering`, where the hours also count toward another tally). The roll-up weights by the split and reports tagged hours separately, so nothing is double-counted.
- Standing rules from the owner (evening gaps are personal, a given person's calls split a given way) are stored once in `mapping.md` and applied on every run.
- A recurring optional event (an optional recurring meeting that stays on the calendar when the owner does not attend) is never taken from the calendar. Attendance is confirmed per occurrence.

## Running it on a schedule

- A scheduled Automation launches `time-study-orchestrator` with the home as an input. Its form takes a period, one window, the owner's answers and instructions; a monthly schedule (early in the month, for the month before) is gated by `python3 ~/.claude/skills/report-time-study/scripts/time_study_check.py --precheck`.
- Its prepare step runs `time-study-collect` (a dry run only plans); its finish step runs `time-study-check`.
- One Run per home at a time. Fan-out, days per window and days per Run are limits the skill states, so a plain session keeps them without the runner.
- The questions step does not wait: the list goes in the report and the Run's report, and the owner's answers come back through the next launch or a file in the window.
- The report and the said-but-not-seen JSON stay local files in the owner's home folder. Nothing is sent.

## Cost and models

Collection, validation and the arithmetic are code at no model cost. The spend is one Sonnet segmenter per recording, one Opus assembler per day, one Sonnet topic classifier per day, one Sonnet checker per window, and the orchestrator's review. Discovery of log formats and database schemas is done once in `timestudy collect`, not by the models on every run.

## Privacy

- Every output and signal file is personal data. It stays in the tool's gitignored home folder and is never committed, published or copied into this repository.
- Browser: titles and domains only. SMS: counts and direction only. Email and chat: at most a six-word gist in a signal file; bodies are read only where the effort estimate needs them.
- Other people's speech in transcripts is used for topic segmentation only. It never appears in the owner-facing report beyond short quotes.
- This skill names no person, client or private path beyond the tool's location.

## Evaluation

A pilot day, corrected by the owner's answers, is the first answer key. It is kept in the private home folder, not here. A change passes when a re-run on that day matches the answer key slot for slot on domain, and the tier counts are no worse. Each later week the owner corrects becomes another key.

## Open decisions

1. Whether the assembler is one worker per day or one per window with day-level packs. Today it is one per day.
2. Where the report file lives for a person who is not the Portal owner (a colleague running it on themselves): today, their own time-study home folder.
3. Whether owner answers also flow back to the Portal as activities, or stay in the study.
