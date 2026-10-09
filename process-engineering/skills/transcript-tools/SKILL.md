---
name: transcript-tools
description: "Two commands other skills load to clean and collapse meeting and interview transcripts before reading them: srt-transcript-collapse turns an SRT or WebVTT export into one speaker-attributed line per turn, and transcript-hygiene reports duplicate and undated transcripts in a folder. Loaded by other skills, not for a user request."
user-invocable: false
---

# Transcript tools

Run each command by this skill's name, one call at a time. Both use only the standard library.

## srt-transcript-collapse

`python3 ~/.claude/skills/transcript-tools/scripts/srt_transcript_collapse.py <file> [--out DIR] [--chunk-bytes N] [--format text|json]`

Collapses one `.srt` or `.vtt` file into `MM:SS Speaker: text` lines, one per speaker turn, merging consecutive cues from one speaker (about half the bytes, still citable by time). Speakers come from the WebVTT `<v Name>` tag or a `Name: text` prefix. With `--out DIR` it writes `<name>.txt` into DIR, or with `--chunk-bytes N` files `<name>.partNN.txt` each under N bytes split only between turns, and prints a summary; without `--out` it prints the text. Exit 2 when the file is missing or not SRT or WebVTT.

## transcript-hygiene

`python3 ~/.claude/skills/transcript-tools/scripts/transcript_hygiene.py <folder> [--format text|json]`

Reports, never moves or deletes. Scans `.txt`, `.md`, `.srt` and `.vtt` files under the folder. Two files are one meeting when their names differ only by extension, case or punctuation, or their first 400 characters of speech match; the copy to read is the collapsed text form (`.txt`, then `.md`, `.vtt`, `.srt`). A date in the file name wins over the modified time; a file with none is undated and cannot be cited by date. Run it before reading a transcript folder so no meeting is read twice. Exit 2 when the folder does not exist.

Tests: `scripts/tests/`, invented data only.
