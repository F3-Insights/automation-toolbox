---
name: obsidian-video-note
description: "Turn a YouTube video into a note in the owner's Obsidian vault, shaped by why the video mattered to them. Fetches the transcript and details with youtube_transcript.py (or takes a pasted transcript), asks the owner for their takeaway, then writes a themed summary with verbatim quotes as a new note in the vault's inbox folder. Use when the owner says \"summarize this video into my vault\", \"make a note of this YouTube talk\" or pastes a transcript. Not for indexing a creator's channel; content-scout does that."
argument-hint: "[YouTube URL, or a pasted transcript with its title and URL]"
---

# YouTube video to a vault note

Load `obsidian-workstream` first (at `~/.claude/skills/obsidian-workstream/SKILL.md` if it is not loaded) and follow its rules: run `vault_config.py`, stop on exit 2, and write only through `vault_inbox_write.py`.

**The owner provided:** $ARGUMENTS

## What makes this note different

A summary of the video (orientation, executive summary, themed sections, quotes) is table stakes; always write it. What makes a note worth keeping is why the video mattered to the person who saved it. So when a person is in the session, ask the owner for their takeaway before you write, and use the answer as the lens for the whole note. Skip the interview only when another skill or an unattended run calls this one; if you cannot tell whether a person is present, assume one is and ask.

## Steps

### 1. Get the transcript and details

- Given a URL or video id, run `python3 ~/.claude/skills/obsidian-video-note/scripts/youtube_transcript.py <url> --out <scratch>/transcript.txt`. It writes the title, channel, publish date, URL and caption kind, then timestamped paragraphs under the video's chapters. Exit 1 means the video has no captions in that language (try `--language` if the owner names one); exit 2 means yt-dlp is missing. In either case ask the owner to paste the transcript.
- Given a pasted transcript, ask for the video's title and URL if they are not there.
- Do not start drafting without a transcript.

### 2. Interview the owner

Ask the core question, and a follow-up only when it would sharpen the note. One round is enough; short or messy answers are fine. An open question in chat works better than canned options, because the owner's own words are the point.

- Core, always: "Why is this video important to you? What was your main takeaway?"
- Follow-ups: "What did it make you think about in your own work or life?" "Does it reinforce or challenge a decision, project or belief?" "What do you want to remember about it in six months?"

The answer is the lens. It changes what you pull from the transcript: lead with and expand what the owner said mattered, even when the video spends more time elsewhere.

### 3. Read the transcript through that lens

- Find the real themes, not a chronological play-by-play.
- Keep verbatim the quotes, numbers, code, repository names and figures that carry weight; never paraphrase a load-bearing specific.
- Rework the title so it states the insight, not "Summary of X".
- Automatic captions mishear names and terms. Where a name matters and the captions look wrong, say so in the note rather than guess.

### 4. Write the note

Use the owner's `video` note kind from `VAULT-RULES.md` when it has one (title prefix, frontmatter keys, tags, sections). Without one, use this shape:

```markdown
---
video_title: "<the original title, verbatim>"
source: <url>
channel: <channel>
published: <YYYY-MM-DD>
---

# <Reworked title that states the insight>

<One paragraph of orientation: who, what, and the through-line. Link people, repositories and resources inline where known.>

---

## My Takeaway

<Two to five sentences in the owner's first person, built only from the interview answers. Name the project, goal or belief they tied it to. Never invent a motive they did not state.>

---

## Executive Summary

<One dense paragraph, or four to six key-takeaway bullets, led by what the owner flagged.>

---

## <Theme 1>

<A lead paragraph stating the section's point.>

- <One idea per bullet, about 12 to 20 words.>
- <A verbatim quote or figure where it carries weight.>

## <Theme 2>

...
```

Style:

- Each section is a lead paragraph, then bullets; never bullets alone.
- Sections are named for their idea, never "Part 1" or a timestamp.
- Keep code blocks and links verbatim when the video is technical.
- No filler such as "In this video the speaker discusses".
- When the interview was skipped, leave out "My Takeaway" rather than write it for the owner.

### 5. Save and confirm

1. Write the note to a scratch file, then run `python3 ~/.claude/skills/obsidian-workstream/scripts/vault_inbox_write.py --title "<prefix><reworked title>" --from <scratch file>`. If a note of that name exists, the script stops; ask the owner whether to use `--next-free` or another title. Never write over a note.
2. Tell the owner the path it printed, the reworked title, and one line on how their takeaway shaped the emphasis.
3. Offer the next useful change (title, emphasis, a section to add or cut). Moving the note out of the inbox is the owner's step.

## Scripts

- `scripts/youtube_transcript.py VIDEO [--language en] [--format text|json] [--paragraph-seconds 30] [--out FILE]`: the transcript and details through yt-dlp, which the owner installs; the environment variable `YT_DLP` names another command to run it. It refuses an `--out` inside the setting `vault_dir` and any redirected caption download. Standard library only.
