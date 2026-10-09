#!/usr/bin/env python3
"""report-questions: the workers' questions as one numbered list, and the audience editor's lists.

A worker never resolves an ambiguity by assumption; it ends its output with

    <!-- QUESTIONS_START -->
    Q1 | <the question> | <why it matters> | <the references it holds up, comma separated>
    <!-- QUESTIONS_END -->

Subcommands:
  collect   pull every questions block out of the saved worker outputs (--from, repeatable),
            fold duplicates together and number what is left (--out writes the list)
  answer    record the executive's answer to one numbered question (--questions, --id,
            --answer); an answered question is citable as owner://questions/<id>
  list      the list as it stands (--open for the unanswered) and the citable references
  verdicts  the audience editor's Keep, Leave out and Misfiled lists as data (--from, --out):
            `gate1_proposals` is the numbered "move <ref> to <category>?" list Gate 1 shows,
            `moves` is ready for the Gate 1 answers file's items.move, and
            `strike_candidates` is every misfiled line that reads as belonging to no category.

Prints JSON. Exit 0 ok, 2 error.

Example:
  python3 report_questions.py collect --from continuity.txt --from editor.txt --out questions.json
"""

import argparse
import re
import sys
from pathlib import Path

from _common import OK, Fail, emit, now_utc, read_json, run_main, today_utc, write_json

BLOCK = re.compile(r"<!-- QUESTIONS_START -->(.*?)<!-- QUESTIONS_END -->", re.DOTALL)
SEPARATOR = re.compile(r"\s*\|\s*")
REFERENCE = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+")


def normal(text):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(text or "").casefold()).split())


def read_outputs(paths):
    found, missing = [], []
    for given in paths:
        path = Path(given).expanduser()
        if path.is_file():
            found.append((path.stem, path.read_text(encoding="utf-8")))
        else:
            missing.append(str(path))
    if missing and not found:
        raise Fail(f"none of the worker outputs could be read: {', '.join(missing)}")
    return found, missing


def collect(outputs):
    """One numbered list; a question asked twice (case and punctuation aside) is asked once."""
    numbered, seen, raw = [], {}, 0
    for worker, text in outputs:
        for body in BLOCK.findall(text):
            for line in (ln.strip() for ln in body.splitlines()):
                if not line or line.startswith(("#", "```")):
                    continue
                raw += 1
                parts = SEPARATOR.split(line)
                malformed = len(parts) != 4
                parts = (parts + [""] * 4)[:4]
                question = line if malformed else parts[1]
                if normal(question) in seen:
                    entry = seen[normal(question)]
                    entry["asked_by"] = list(dict.fromkeys(entry["asked_by"] + [worker]))
                    entry["affects"] = list(dict.fromkeys(entry["affects"] + [a.strip() for a in parts[3].split(",") if a.strip()]))
                    entry["duplicates"] += 1
                    continue
                ident = str(len(numbered) + 1)
                entry = {"id": ident, "question": question, "why": parts[2] or None,
                         "affects": [a.strip() for a in parts[3].split(",") if a.strip()],
                         "asked_by": [worker], "worker_ids": [parts[0]] if parts[0] and not malformed else [],
                         "duplicates": 0, "malformed": malformed, "answered": False, "answer": None,
                         "answered_on": None, "ref": f"owner://questions/{ident}"}
                seen[normal(question)] = entry
                numbered.append(entry)
    return {"schema": "report-questions/1", "collected_at": now_utc(), "sources": [w for w, _ in outputs],
            "raw": raw, "count": len(numbered), "questions": numbered,
            "rule": "put these to the executive batched, at the next gate, never one at a time; an item a "
                    "question holds up stays pending until it is answered"}


def verdicts(outputs):
    """The editor's three lists, each line split on ` | ` into its fields, as written."""
    found = {"keep": [], "leave_out": [], "misfiled": []}
    for worker, text in outputs:
        current = ""
        for line in text.splitlines():
            heading = re.match(r"^\s*#{1,6}\s*(.+?)\s*$", line)
            if heading:
                words = normal(heading.group(1))
                current = next((key for name, key in (("keep", "keep"), ("leave out", "leave_out"),
                                                      ("misfiled", "misfiled"))
                                if words == name or words.startswith(name + " ")), "")
                continue
            bullet = re.match(r"^\s*[-*+]\s+(.*\S)\s*$", line)
            if not current or not bullet:
                continue
            parts = [p.strip() for p in SEPARATOR.split(bullet.group(1))]
            ref = next((h.group(0).strip("[]()<>,;") for p in reversed(parts) if (h := REFERENCE.search(p))), "")
            row = {"worker": worker, "line": bullet.group(1), "ref": ref}
            get = lambda i: parts[i] if len(parts) > i else ""  # noqa: E731
            if current == "misfiled":
                row.update(filed_under=re.sub(r"(?i)^\s*filed\s+under\s+", "", get(1)),
                           reads_as=re.sub(r"(?i)^\s*reads\s+as\s+", "", get(2)), why=get(3), malformed=len(parts) != 4)
            elif current == "keep":
                row.update(category=get(0), item=get(1), test=get(2), why=get(3), malformed=len(parts) != 5)
            else:
                row.update(category=get(0), item=get(1), why=get(2), malformed=len(parts) != 4)
            found[current].append(row)
    moves, strikes, proposals = [], [], []
    for row in found["misfiled"]:
        reads, ref = row["reads_as"].strip(), row["ref"]
        if not ref or not reads:
            continue
        if reads.casefold().startswith("not this scope"):
            strikes.append(ref)
            proposals.append({"ref": ref, "action": "strike", "category": None,
                              "ask": f"strike {ref}? It reads as belonging to no category in this scope."})
        else:
            moves.append({"ref": ref, "category": reads})
            proposals.append({"ref": ref, "action": "move", "category": reads, "ask": f"move {ref} to {reads}?"})
    for number, row in enumerate(proposals, 1):
        row["number"] = number
    warnings = [] if any(found.values()) else [
        "no Keep, Leave out or Misfiled list was found; the editor writes each under its own heading"]
    return {"schema": "report-verdicts/1", "collected_at": now_utc(), "sources": [w for w, _ in outputs],
            "counts": {k: len(v) for k, v in found.items()}, **found, "moves": moves,
            "strike_candidates": strikes, "gate1_proposals": proposals, "warnings": warnings,
            "rule": "the editor never re-files anything; an item moves only when the executive answers the "
                    "numbered proposal at Gate 1"}


def main():
    parser = argparse.ArgumentParser(description="The workers' questions as one numbered list.")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("collect", "verdicts"):
        one = sub.add_parser(name)
        one.add_argument("--from", dest="sources", action="append", required=True, help="a saved worker output")
        one.add_argument("--out", default="")
    answer = sub.add_parser("answer")
    answer.add_argument("--questions", required=True)
    answer.add_argument("--id", required=True)
    answer.add_argument("--answer", required=True)
    answer.add_argument("--on", default="", help="YYYY-MM-DD; today in UTC without it")
    answer.add_argument("--out", default="", help="write here instead of back to --questions")
    listing = sub.add_parser("list")
    listing.add_argument("--questions", required=True)
    listing.add_argument("--open", action="store_true")
    args = parser.parse_args()

    if args.action in ("collect", "verdicts"):
        outputs, missing = read_outputs(args.sources)
        result = collect(outputs) if args.action == "collect" else verdicts(outputs)
        if missing:
            result.setdefault("warnings", []).append(f"{len(missing)} worker output(s) could not be read: "
                                                     f"{', '.join(missing)}")
        if args.out.strip():
            result["file"] = str(write_json(args.out, result))
        emit(result)
        for warning in result.get("warnings") or []:
            print(f"warning: {warning}", file=sys.stderr)
        return OK
    found = read_json(args.questions, "questions file")
    if not isinstance(found, dict) or not isinstance(found.get("questions"), list):
        raise Fail(f"{args.questions} is not a questions file: it holds no 'questions' list")
    if args.action == "list":
        rows = [q for q in found["questions"] if not args.open or not q.get("answered")]
        emit({"action": "list", "count": len(rows), "questions": rows,
              "open": len([q for q in found["questions"] if not q.get("answered")]),
              "answered_refs": [q["ref"] for q in found["questions"] if q.get("answered")]})
        return OK
    row = next((q for q in found["questions"] if str(q.get("id")) == args.id.strip()), None)
    if row is None:
        raise Fail(f"no question numbered {args.id!r}; the ids are "
                   f"{', '.join(str(q.get('id')) for q in found['questions']) or 'none'}")
    row.update(answered=True, answer=args.answer.strip(), answered_on=args.on.strip() or today_utc().isoformat())
    path = write_json(args.out.strip() or args.questions, found)
    emit({"action": "answer", "file": str(path), "answered": row["id"], "ref": row["ref"],
          "open": len([q for q in found["questions"] if not q.get("answered")]), "count": len(found["questions"])})
    return OK


if __name__ == "__main__":
    run_main(main)
