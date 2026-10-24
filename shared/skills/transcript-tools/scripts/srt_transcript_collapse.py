#!/usr/bin/env python3
"""Collapse an SRT or WebVTT transcript into speaker-attributed text.

Subtitle exports split one speaker's sentence across many timed cues and spend about half
their bytes on cue numbers and timestamps. This turns

    1
    00:03:12,400 --> 00:03:15,900
    <v Dana>So the question is whether

    2
    00:03:15,900 --> 00:03:18,200
    <v Dana>we move the close earlier

into one line per speaker turn, stamped with the turn's first cue:

    03:12 Dana: So the question is whether we move the close earlier

Speakers are read from the WebVTT voice tag <v Name> or a "Name: text" prefix; a cue with
neither belongs to the previous speaker. Consecutive cues from one speaker merge.

Input: one .srt or .vtt file. Prints the collapsed text (or --format json with counts and
the text). With --out DIR it writes <name>.txt into DIR (or, with --chunk-bytes N, files
<name>.partNN.txt each under N bytes, split only between turns) and prints a summary.
Exit 0 ok, 2 when the file is missing or is not SRT or WebVTT.

Example:
  python3 srt_transcript_collapse.py interview.vtt --out sources/
"""

import argparse
import json
import re
import sys
from pathlib import Path

TS = r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})"  # 00:03:12,400 or 03:12.400
TIMING_RE = re.compile(rf"^\s*{TS}\s*-->\s*{TS}")
VOICE_TAG_RE = re.compile(r"^<v\s+([^>]+)>\s*(.*)$", re.S)
PREFIX_RE = re.compile(r"^([A-Z][\w.'\- ]{0,60}?)\s*:\s+(.*)$", re.S)
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


class NotATranscript(Exception):
    pass


def parse_cues(text):
    """(start seconds, cue text) per cue; multi-line cue text is joined with spaces."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues, i = [], 0
    timed = False
    while i < len(lines):
        m = TIMING_RE.match(lines[i])
        i += 1
        if not m:
            continue
        timed = True
        h, mi, s, ms = m.group(1, 2, 3, 4)
        start = int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(lines[i].strip())
            i += 1
        if body:
            cues.append((start, " ".join(body)))
    if not timed:
        raise NotATranscript("No cue timings found; input is not SRT or WebVTT.")
    return cues


def split_speaker(raw, previous):
    m = VOICE_TAG_RE.match(raw)
    if m:
        return m.group(1).strip(), HTML_TAG_RE.sub("", m.group(2)).strip()
    m = PREFIX_RE.match(raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return previous, HTML_TAG_RE.sub("", raw).strip()


def collapse(text):
    """Turns as [start seconds, speaker or None, text], same-speaker cues merged."""
    turns, prev = [], None
    for start, raw in parse_cues(text):
        speaker, body = split_speaker(raw, prev)
        if not body:
            continue
        if turns and turns[-1][1] == speaker:
            turns[-1][2] += " " + body
        else:
            turns.append([start, speaker, body])
        prev = speaker
    return turns


def render(turn):
    start, speaker, text = turn
    s = int(start)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    stamp = f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
    return f"{stamp} {speaker + ': ' if speaker else ''}{text}"


def chunk(turns, max_bytes):
    """Turns grouped under max_bytes of rendered text, never splitting a turn."""
    chunks, cur, size = [], [], 0
    for t in turns:
        n = len(render(t).encode("utf-8")) + 1
        if cur and size + n > max_bytes:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(t)
        size += n
    if cur:
        chunks.append(cur)
    return chunks


def summarise(path, chunk_bytes=0):
    raw = path.read_text(encoding="utf-8", errors="replace")
    turns = collapse(raw)
    text = "\n".join(render(t) for t in turns)
    result = {"source": str(path), "cues": len(parse_cues(raw)), "turns": len(turns),
              "speakers": sorted({t[1] for t in turns if t[1]}),
              "bytes_in": len(raw.encode("utf-8")), "bytes_out": len(text.encode("utf-8")), "text": text}
    result["reduction_pct"] = round(100 * (1 - result["bytes_out"] / max(result["bytes_in"], 1)), 1)
    if chunk_bytes:
        result["chunks"] = ["\n".join(render(t) for t in c) for c in chunk(turns, chunk_bytes)]
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Collapse an SRT or WebVTT transcript into speaker-attributed text.")
    ap.add_argument("path")
    ap.add_argument("--chunk-bytes", type=int, default=0, help="split into files under this many bytes (0: one file)")
    ap.add_argument("--out", default=None, help="write .txt files into this folder instead of printing")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="stdout format without --out")
    args = ap.parse_args(argv)
    src = Path(args.path).expanduser()
    if not src.is_file():
        print(f"Not a file: {src}", file=sys.stderr)
        return 2
    try:
        result = summarise(src, args.chunk_bytes)
    except NotATranscript as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.out is not None:
        dest = Path(args.out) if args.out else src.parent
        dest.mkdir(parents=True, exist_ok=True)
        if "chunks" in result:
            parts = [(dest / f"{src.stem}.part{i:02d}.txt", c) for i, c in enumerate(result["chunks"], 1)]
        else:
            parts = [(dest / f"{src.stem}.txt", result["text"])]
        for f, body in parts:
            f.write_text(body + "\n", encoding="utf-8")
        print(f"{result['cues']} cues -> {result['turns']} turns, {len(result['speakers'])} speakers, "
              f"{result['reduction_pct']}% smaller. Wrote {len(parts)} file(s):")
        for f, _ in parts:
            print(f"  {f}")
    elif args.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False))
    else:
        print(result["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
