# Brief: attribute one day's 144 ten-minute slots

## The question

What was the owner doing in each 10-minute slot of this one day, for which domain, and how do we know? Turn the day's signals, the meeting topic blocks, the owner's own statements and rules and the domain map into 144 slot attributions, each with its evidence and an evidence tier. Then list what got done, what the owner said they would do and nothing shows they did, the conflicts between sources, and the questions only the owner can answer.

You never invent. A slot with no evidence is `unaccounted`, and a long unaccounted run in waking hours becomes a question, not a guess.

## The inputs

The paths given after this brief, and only those:

- `signals/<date>/`: every signal file for the day. Among them `teams.tsv` (calls and the owner's messages), `zoom_meet.tsv`, `calendar.tsv`, `sent_email.tsv`, `cc_messages.tsv` (Claude Code prompts), `signal_grid.tsv` (per-slot counts), `pc_power.tsv` (sleep, wake, restart, webcam), browser visits, file saves and commits. A file may be missing; say so.
- The segment files for recordings dated this day (`meetings/<recording_id>.md`).
- The window's `owner_stated.md` and `calls_confirmed.csv`, when present.
- The owner's `mapping.md` and `domains.csv`.
- On a re-run: the checker's flags and the owner's answers for this day, together, and this day's previous `slots.csv` and `day.md`. See "On a re-run" below.

Read the previous day's last slots only if the orchestrator passes that path too.

## The rules

**Tiers.** One per slot:

| Tier | When |
|---|---|
| verified | A system recorded the owner doing it in that slot: speaking in a transcript, a prompt typed, a message or email sent, a call joined |
| corroborated | Two indirect signals agree (the PC asleep and a block on the owner's own calendar; a shared-in calendar only where `mapping.md` allows it) |
| owner-stated | The owner said so, in `owner_stated.md`, an answer or a standing rule in `mapping.md` |
| inferred | One indirect signal (a page open, a save in a synced folder, sleep overnight with the PC off) |
| unaccounted | Nothing |

**Presence and domain are two tiers.** Settle them separately, and the slot takes the weaker of the two. Presence says the owner was there doing it; domain says for whom. A domain is verified only by content: the transcript block that says what was discussed, the words of a message or email, the repository of the owner's own commit, a recipient the map places. A domain that rests only on the Teams tenant, the organizer or a calendar event overlapping the slot is inferred, or corroborated when a second independent signal agrees; it is never verified, even when presence is verified.

**Priority inside a slot.** A live call the owner is on, then owner-stated off-PC activity, then typing (prompts, sent mail, chat messages), then page opens, then saves. Everything else active in the slot goes in `concurrent`, not dropped: working during calls is normal.

**Calls.** The owner's own span, not the call's: the transcript's attendance section, the Teams join evidence, and the webcam event that follows within 5 seconds of the owner leaving any call. A Zoom post-meeting page is an upper bound on the leave. A join page alone is not attendance. Inside a recording where the segmenter found the owner absent, the slots are not that call. Across a call slot, take the domain of the topic block that holds most of the slot, and where the slot's minutes split across domains, write the split in `allocation`.

A call slot is verified only for the minutes the owner was present in it. Where presence covers under half of the slot, the rest of the slot is inferred or unaccounted, from whatever other evidence it has, and the shares reflect that: the present minutes go to the call's domain and the remaining minutes to what the other evidence supports, or to `unaccounted`. The slot's tier is then not verified. Never normalise the shares over only the evidenced minutes and credit the whole slot to them.

A standing split for a person in `mapping.md` (for example, their calls split 70/30 between two projects) applies only to calls and chats with that person that have no recording and no clear content. A recorded session keeps the segmenter's topic blocks, whoever it was with.

When the owner says in a recording that they are leaving (for breakfast, a workout, a pickup), the slots that follow are the personal domain, or `unaccounted`, until other evidence shows the owner back. They do not carry the call's domain forward.

**Domains.** Map every signal through `mapping.md`: recipient or attendee to contact to company to domain; repository or folder to domain; site to domain; Teams tenant and identity to person to domain. Apply its standing rules and splits exactly as written (a person's calls split `Domain A:0.9;Domain B:0.1`, evening gaps personal). A signal the map cannot place is `unmapped` in the evidence and the slot takes the domain the rest of its evidence supports, or becomes a question; never a default domain. Write domain names exactly as in `domains.csv`.

Content decides over the account. A chat about a home matter on a work account or a work tenant is personal; the account says only where it was typed.

**Shares.** `primary_domain` is the domain with the largest share in `allocation`; on a tie, the one with the stronger evidence. Every typed owner action in the slot (a prompt, a chat message, a sent email) gets a share in `allocation` or is named in `concurrent` with the reason it has no share. A typed action for another domain than the primary must not vanish from the slot.

**What the signals do not prove.**
- Chrome `visit_duration` is how long a tab stayed open, not attention. Page opens are the activity. A share that rests on browser tabs alone is inferred, however long the tab was open.
- A merge or commit under the owner's identity that the signal file marks `owner=no` (made by automation or someone else through the owner's account), together with a page visit, is corroborated at best, never verified.
- Outlook activity logs (`olk` files) are on a UTC clock. Convert to local time with the owner's timezone before citing a time, and cite the local time.
- A save in a synced folder may be another person's; with `lastModifiedBy` naming someone else it is not the owner's, and without it a save alone is inferred at most.
- A calendar entry is booked time, not attendance. A recurring optional event (a group the owner sometimes skips) is never taken from the calendar; without other evidence it is a question.
- Phone Link may have stopped syncing; an empty day there proves nothing if its newest row is old.
- The PC asleep or locked for most of a slot means off-PC unless another device shows activity. The last input is roughly the PC's idle-to-sleep delay before each sleep entry.
- After a restart, crash-recovery prompts are overhead, not new work.
- Commits and file saves by other people are not the owner's.

**Owner-stated against verified.** Where an owner-stated time conflicts with a verified one, the verified time holds in `slots.csv` and the conflict is listed in `day.md` with both times. Never overwrite a verified slot with a stated one.

**On a re-run.** You are given the checker's flags, the owner's answers and this day's previous files. Revise the previous `slots.csv` and `day.md` rather than starting over. Apply every flag you are given, since the owner has accepted them: change each slot the flag names, and every slot the same reasoning reaches. Where a flag seems wrong against the evidence, apply it and name the disagreement in `## Conflicts` for the owner. Fold every accepted answer in as owner-stated, or as a rule where the answer is a standing one. Keep in `## Questions` only what is still genuinely open after the flags and the answers; an answered question does not come back.

**Tags.** A tag such as `volunteering` marks hours already counted in the slot's domain; it never adds hours.

## Your own folder, and a refused tool call

Scratch files go only in your own folder, `<window>/work/day-assembler-<date>/`, never in a shared scratch folder, a temporary directory or another worker's folder. You run no script: the one command you run is `time-study-day-lint`, which checks your files and does the counting. A script found in `work/` or anywhere else belongs to another worker and another day, and running it can rewrite that day's files.

If a tool call is blocked by a hook or a permission rule, stop and return `STATUS: BLOCKED` with the exact denial text. Never reroute the same action through another tool or a script (a refused shell write redone from Python is the same write).

## What you write

`<window>/days/<date>/slots.csv`, exactly 144 rows from 00:00 to 24:00, header:

```
slot_start,slot_end,primary_activity,primary_domain,tier,concurrent,evidence,allocation,tags
```

Times `HH:MM`, the last slot ending `24:00`. `allocation` is empty or `Domain A:0.8;Domain B:0.2` with weights summing to 1. `evidence` names the file and the row or time it rests on. Before you return, run `python3 ~/.claude/skills/report-time-study/scripts/time_study_day_lint.py <window>/days/<date> --domains <domains.csv>`. It checks that there are 144 contiguous rows, every tier is one of the five, every domain is in `domains.csv`, every allocation sums to 1 and the primary domain is the largest share, and it prints the day's hours by domain. Fix what it names and run it again; its first line, `OK` or `FAIL`, is your `self_check`.

`<window>/days/<date>/day.md`, with these sections in this order, each present even when empty:

```
# <Www YYYY-MM-DD>
## Done              verified outputs: sent, shipped, decided, presented, each with its evidence
## Said but not seen the owner's commitments from the segment files with no later evidence,
                     one numbered line each in the fixed shape below
## Conflicts         sources that disagree, both sides with times
## Unmapped          signals the map could not place, with a proposed domain
## Questions         gaps over 30 minutes in waking hours, conflicts, low-confidence domains,
                     unconfirmed recurring events; each with a proposed answer
## Proposed confirmed calls   date,start,end,title,note rows for calls_confirmed.csv, with evidence
```

Each said-but-not-seen item is one numbered line, its fields separated by ` | `, because `time-study-said-not-seen` turns these lines into the JSON other orchestrators read:

```
1. HH:MM:SS | meetings/<recording_id>.md | "<the owner's words, 20 at most>" | <what, verb first> | to: <whom, or none> | by: <YYYY-MM-DD, or as said, or none> | domain: <domain> | <why it is not seen, a few words>
```

The time is when it was said; the source is the segment file (or the signal file) that holds it. Write `- none` when there are none. A field never contains ` | `.

## The return format

Answer with exactly this block and nothing else:

```
STATUS: OK | BLOCKED
date: YYYY-MM-DD
files: <slots.csv path>, <day.md path>
self_check: passed | failed: <what>
done: <count>
said_but_not_seen: <count>
conflicts: <count>
unmapped: <count>
questions: <count>
revised: no | <flags applied> flags applied, <answers> answers folded in, <questions still open> still open
blocked_on: <what is missing, the exact denial when a tool call was refused, or none>
model: <your model>
```
