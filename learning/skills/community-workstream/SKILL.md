---
name: community-workstream
description: Reference loaded by learning-community-orchestrator and community-writer, not for a user request; what running a learning community's sessions (a peer group that meets on a cadence) adds to orchestration-workstream. Covers COMMUNITY-RULES.md first, the agenda from members' requested topics, the invitation in the owner's voice staged and never sent, the recap from the recording traced to the transcript with no member named without consent, the session record, the prepare and recap DONE checklists, and the shapes.
---

# Community workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill if it is not loaded. It covers one community session at a time, in two passes: **prepare** (agenda and invitation, before the session) and **recap** (recap post and session record, after it).

## Conduct here

- **The rules file first.** `COMMUNITY-RULES.md` in the group's folder (the caller gives its path) says: the cadence and the session slots with their timezone, the meeting link, the roster's source (a Portal tag or a roster file), where members' topic requests are kept, the invitation lead time, the invitation channel (`email` staged as a Portal draft, or `file`), where the recap is posted, the voice guide (default: the owner's voice guide, setting `voice_guide`), the sessions folder and its record template, and the members who agreed to be named. It overrides this skill.
- **Members choose the topics.** An agenda item is a member's request (cite where it was made) or the owner's own pick (say so). Never invent a member's interest.
- **Stage, never send.** The invitation is a file and, when the rules say `email`, one Portal draft. The recap is a file. Nothing is posted, sent, scheduled or put on a calendar.
- **The recording is the source.** The recap says only what the transcript shows. A member is named or quoted only if the rules list them as agreeing; everyone else is "a member".
- **No prices.** Sessions are free; a recap never pitches a paid service.

## Files of one session

In the session folder (`<sessions folder>/<yyyy-mm-dd>/` when the rules name one and the fence allows writing there; otherwise `RUN/session/`):

- `agenda.md`: date, time and timezone, duration, then each item with its minutes, its owner (the owner or a member who agreed to lead) and its source.
- `invitation.md`: subject line, then the body: what, when (with timezone), the link or "link to follow", the agenda in three lines at most, any pre-work. Under 150 words.
- `recap.md`: what was covered, the demos or artifacts shown, what members said they would try, the next session's date and topics. Each sentence carries a hidden source comment `<!-- t=MM:SS -->` or `<!-- line N -->` pointing into the transcript.
- `record.md`: the session record in the rules' template (outline, not transcript).
- `topics-proposal.md`: topics raised in the session for the backlog, each with its timestamp, as a proposal to the topics file; never written into it.

## The return here

The shared block with item test `session-file` (item: the file name; state `written`, `skipped`, `blocked`), `files` the files written, `questions` for the owner (a topic choice, a member who may not be named, a missing link), and `proposals` the topics-backlog additions.

## DONE: prepare (the orchestrator checks each item and cites its evidence)

1. The session date and time match the rules' cadence or the owner's input, with timezone.
2. Every agenda item cites a member's request or is marked as the owner's pick; the minutes fit the duration.
3. `invitation.md` exists, under 150 words, with date, time, timezone and link (or "link to follow"), no prices, and no member's name beyond those the rules allow.
4. The invitation is ready at least the rules' lead time before the session, or the lateness is a question for the owner.
5. Channel `email` and not a dry run: one Portal draft staged by `email-drafter`, its id recorded; nothing sent.

## DONE: recap (the orchestrator checks each item and cites its evidence)

1. The recording or transcript read is the session's own (date and attendees match).
2. Every sentence of `recap.md` has a source comment, and `fact-check` returned no CONTRADICTED and no unresolved NOT IN MY SOURCES.
3. No member is named or quoted unless the rules list them as agreeing.
4. `record.md` follows the rules' template; `topics-proposal.md` lists the new topics.
5. Nothing was posted or sent.

## Later tools

- `community-pack`: before the session, compute the next session date from the cadence, read the roster tag and the topic requests into `RUN/pack.json`, so the precheck says NOTHING when no session is due inside the lead time.
- `community-check`: compute both DONE checklists from the session folder (source comments, word count, names against the consent list).
