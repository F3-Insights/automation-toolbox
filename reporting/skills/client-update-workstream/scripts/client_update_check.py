# /// script
# dependencies = ["pyyaml"]
# ///
"""Say whether one engagement's weekly client update is drafted and checked, test by test.

Computed from the week folder, the pack (work/sources.json) and the evidence file
(work/UPDATE-EVIDENCE.csv, written only by client_update_record.py). Nine tests, each pass,
fail or na with detail lines:

  sources     the pack parses, has a source, and halves a and b are disjoint and both non-empty
  files       deck: the draft .html and review note exist, every slide section has a notes block
              with an m:ss timing (in total within Slot minutes when set), and no {{ placeholder or
              [TBD]-style blank is left. memo: the draft .md, its .docx, the cover email and the
              review note exist, with no placeholder left in the draft
  claims      every live claim is cited by a <!-- Source: C3 S004 --> comment in the draft, every
              cited claim has a row, every source id is in the pack, every claim names a source
  factcheck   both fact-check halves ran; every live claim is verified or flagged; every flagged
              claim is named in the review note
  redteam     the red-team review passed
  prose       the visible text holds no banned character or phrase (the house list plus the rules')
  continuity  every carried item has its carry row in done, moved or dropped (na with none)
  context     with an engagement context in the pack, work/context-proposed.md says "No changes
              proposed" or holds numbered changes and the whole file under "## Proposed file"
  review      work/CONFIRMATIONS.md holds a comms-confirm request (a "## CR-<10 hex>" section)

--precheck prints one line for a scheduler: NOTHING when a person already wrote this week's
update or it is done, else WORK. Exit 0 whenever it ran; 2 on a bad argument or a missing Context.

    python3 client_update_check.py acme-weekly-update 2026-W40 --week-dir "Weekly Update/2026-10-02" --format json
"""

import argparse
import html
import json
import re
from datetime import timedelta

import _common as cu

TESTS = ("sources", "files", "claims", "factcheck", "redteam", "prose", "continuity", "context", "review")
HOUSE_PHRASES = ("on track", "ahead of schedule", "great progress", "successfully completed",
                 "key milestone", "critical finding", "alarming", "major concern", "game-changer",
                 "revolutionary", "seamless", "robust", "leverage", "going forward",
                 "it should be noted", "as previously discussed", "circle back", "cutting-edge")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
SOURCE_COMMENT_RE = re.compile(r"<!--\s*source\s*:(.*?)-->", re.S | re.I)
CLAIM_ID_RE = re.compile(r"(?<![A-Za-z0-9])C\d+(?![A-Za-z0-9])")
SOURCE_ID_RE = re.compile(r"(?<![A-Za-z0-9])S\d{3}(?![A-Za-z0-9])")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
SLIDE_RE = re.compile(r"<section\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bslide\b[^\"']*[\"'][^>]*>", re.I)
NOTES_RE = re.compile(r"<[a-z][a-z0-9]*\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bnotes\b[^\"']*[\"'][^>]*>", re.I)
TIMING_RE = re.compile(r"(?<![\d:])(\d{1,2}):([0-5]\d)(?![\d:])")
BLANK_RE = re.compile(r"\[\s*(?:tbd|tbc|todo|tk|x{2,}|owner|name|date|client|amount|number|figure|"
                      r"\.{3}|…|insert[^\]\n]{0,40}|fill[^\]\n]{0,40}|placeholder[^\]\n]{0,40})\s*\]", re.I)
CONFIRM_HEAD_RE = re.compile(r"^## (CR-[0-9a-f]{10})\s*$", re.M)
ALREADY_DAYS = 2


def outcome(state, detail, why=None) -> dict:
    """A test's result; why is its first problem, the reason a precheck line gives."""
    return {"state": state, "detail": detail, "why": why or (detail[0] if detail and state == "fail" else None)}


def keep_lines(text: str) -> str:
    """As many newlines as the text spans, so line numbers survive removing it."""
    return text.count("\n") * "\n"


def visible_html(text: str) -> str:
    out = COMMENT_RE.sub(lambda m: keep_lines(m.group(0)), text)
    out = SCRIPT_STYLE_RE.sub(lambda m: keep_lines(m.group(0)), out)
    return html.unescape(TAG_RE.sub(lambda m: " " + keep_lines(m.group(0)), out))


def visible_md(text: str) -> str:
    return COMMENT_RE.sub(lambda m: keep_lines(m.group(0)), text)


def claim_key(cid: str):
    digits = re.sub(r"\D", "", cid)
    return (int(digits) if digits else 0, cid)


def claim_rows(rows: dict) -> dict:
    return {key.split(":", 1)[1]: row for key, row in rows.items()
            if row.get("kind") == "claim" and key.startswith("claim:")}


# --------------------------------------------------------------------------- the tests

def test_sources(pack, problem) -> dict:
    if pack is None:
        return outcome("fail", [problem or "no pack: run client-update-pack"])
    sources = pack.get("sources") or []
    if not sources:
        return outcome("fail", ["the pack holds no source"])
    detail = []
    ids = [str(s.get("id")) for s in sources]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        detail.append(f"source ids listed twice: {', '.join(dupes)}")
    half_a = [s["id"] for s in sources if s.get("half") == "a"]
    half_b = [s["id"] for s in sources if s.get("half") == "b"]
    loose = [str(s.get("id")) for s in sources if s.get("half") not in ("a", "b")]
    if loose:
        detail.append(f"sources in neither half: {', '.join(loose)}")
    if set(half_a) & set(half_b):
        detail.append("halves a and b share sources")
    if len(sources) >= 2 and not (half_a and half_b):
        detail.append("one half is empty")
    head = f"{len(sources)} sources, half a {len(half_a)}, half b {len(half_b)}"
    return outcome("fail" if detail else "pass", [head] + detail, detail[0] if detail else None)


def deck_form(text: str, slot) -> list:
    """The deck's shape: its first line a summary, the rest problems."""
    starts = [m.start() for m in SLIDE_RE.finditer(text)]
    if not starts:
        return ["the deck has no <section class=\"slide\"> element"]
    problems = []
    segments = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    missing = [n for n, seg in enumerate(segments, start=1) if not NOTES_RE.search(seg)]
    if missing and len(NOTES_RE.findall(text)) != len(starts):
        problems.append(f"slide(s) without a notes block: {', '.join(map(str, missing))}")
    seconds, untimed = 0, []
    for n, seg in enumerate(segments, start=1):
        found = NOTES_RE.search(seg)
        if found:
            timing = TIMING_RE.search(visible_html(seg[found.start():]))
            if timing:
                seconds += int(timing.group(1)) * 60 + int(timing.group(2))
            else:
                untimed.append(str(n))
    if untimed:
        problems.append(f"notes without an m:ss timing on slide(s): {', '.join(untimed)}")
    minutes = seconds / 60
    if slot is not None and minutes > slot:
        problems.append(f"the notes' timings total {minutes:.1f} minutes, over the {slot}-minute slot")
    return [f"{len(starts)} slides, notes timed at {minutes:.1f} minutes"
            + (f" of a {slot}-minute slot" if slot is not None else "")] + problems


def placeholders(visible: str, raw: str, where: str) -> list:
    out = [f"{where}: a {{{{ placeholder is left"] if "{{" in raw else []
    return out + [f"{where}: the blank {m.group(0)} is left" for m in BLANK_RE.finditer(visible)]


def test_files(week) -> dict:
    rules = week.engagement.rules
    wanted = [("draft", week.draft), ("review note", week.review_note)]
    if rules.variant == "memo":
        wanted[1:1] = [("Word file", week.docx), ("cover email", week.cover_email)]
    missing = [f"no {what}: {path.name if path else '(not set)'}" for what, path in wanted
               if path is None or not path.is_file()]
    detail, form = [], []
    if week.draft.is_file():
        text = cu.read_text(week.draft)
        if rules.variant == "deck":
            shape = deck_form(text, rules.slot_minutes)
            detail.append(shape[0])
            form += shape[1:]
            form += placeholders(visible_html(text), SCRIPT_STYLE_RE.sub("", COMMENT_RE.sub("", text)), week.draft.name)
        else:
            form += placeholders(visible_md(text), visible_md(text), week.draft.name)
    problems = missing + form
    return outcome("fail" if problems else "pass", missing + detail + form, problems[0] if problems else None)


def test_claims(week, pack, rows) -> dict:
    if not week.draft.is_file():
        return outcome("fail", [f"no draft: {week.draft.name}"])
    claims = claim_rows(rows)
    live = {cid: row for cid, row in claims.items() if row.get("state") != "cut"}
    if not live:
        return outcome("fail", ["no claims recorded: client_update_record.py ... claims --from claims.json"])
    known = set(cu.source_ids(pack)) if pack else set()
    comments = SOURCE_COMMENT_RE.findall(cu.read_text(week.draft))
    cited_claims = {c for body in comments for c in CLAIM_ID_RE.findall(body)}
    cited_sources = {s for body in comments for s in SOURCE_ID_RE.findall(body)}
    detail = [f"{len(live)} live claims, {len(comments)} Source comments"]
    uncited = sorted(set(live) - cited_claims, key=claim_key)
    if uncited:
        detail.append(f"claims in no Source comment: {', '.join(uncited)}")
    no_row = sorted(cited_claims - set(claims), key=claim_key)
    if no_row:
        detail.append(f"Source comments name claims with no row: {', '.join(no_row)}")
    recorded = {s for row in live.values() for s in SOURCE_ID_RE.findall(row.get("sources", ""))}
    unknown = sorted((cited_sources | recorded) - known)
    if unknown:
        detail.append(f"source ids not in the pack: {', '.join(unknown)}")
    sourceless = sorted((c for c, r in live.items() if not SOURCE_ID_RE.search(r.get("sources", ""))), key=claim_key)
    if sourceless:
        detail.append(f"claims with no source: {', '.join(sourceless)}")
    return outcome("fail" if len(detail) > 1 else "pass", detail, detail[1] if len(detail) > 1 else None)


def test_factcheck(week, rows) -> dict:
    detail = [f"fact-check half {half} not recorded" for half in ("a", "b")
              if (rows.get(f"review:factcheck-{half}") or {}).get("state") not in ("ran", "passed")]
    live = {cid: r for cid, r in claim_rows(rows).items() if r.get("state") != "cut"}
    if not live:
        detail.append("no claims recorded")
    for state in ("contradicted", "unsupported", "pending"):
        ids = sorted((cid for cid, r in live.items() if r.get("state") == state), key=claim_key)
        if ids:
            detail.append(f"{state}: {', '.join(ids)}")
    flagged = sorted((cid for cid, r in live.items() if r.get("state") == "flagged"), key=claim_key)
    note = cu.read_text(week.review_note)
    absent = [cid for cid in flagged if not re.search(rf"(?<![A-Za-z0-9]){re.escape(cid)}(?![0-9])", note)]
    if absent:
        detail.append(f"flagged claims not named in the review note: {', '.join(absent)}")
    verified = sum(1 for r in live.values() if r.get("state") == "verified")
    head = f"{verified} verified, {len(flagged)} flagged of {len(live)} live claims"
    return outcome("fail" if detail else "pass", [head] + detail, detail[0] if detail else None)


def test_redteam(rows) -> dict:
    row = rows.get("review:redteam")
    if row is None:
        return outcome("fail", ["no red-team review recorded"])
    if row.get("state") != "passed":
        return outcome("fail", [f"the red-team review is {row.get('state') or 'blank'}"
                                + (f": {row['note']}" if row.get("note") else "")])
    return outcome("pass", [f"passed ({row.get('evidence') or 'no file named'})"])


def snippet(line: str, at: int, length: int, around: int = 30) -> str:
    start, end = max(0, at - around), min(len(line), at + length + around)
    return ("..." if start else "") + " ".join(line[start:end].split()) + ("..." if end < len(line) else "")


def prose_hits(text: str, where: str, rules) -> list:
    hits = []
    phrases = list(HOUSE_PHRASES) + [p for p in rules.banned_phrases if p]
    for number, line in enumerate(text.splitlines(), start=1):
        for char in rules.banned_characters:
            at = line.find(char)
            if at >= 0:
                hits.append(f"{where}:{number}: banned character U+{ord(char[0]):04X} in "
                            f"\"{snippet(line, at, len(char))}\"")
        for phrase in phrases:
            for found in re.finditer(rf"(?<![A-Za-z]){re.escape(phrase)}(?![A-Za-z])", line, re.I):
                hits.append(f"{where}:{number}: banned phrase \"{phrase}\" in "
                            f"\"{snippet(line, found.start(), len(phrase))}\"")
    return hits


def test_prose(week) -> dict:
    rules = week.engagement.rules
    if not week.draft.is_file():
        return outcome("fail", [f"no draft: {week.draft.name}"])
    text = cu.read_text(week.draft)
    hits = prose_hits(visible_html(text) if rules.variant == "deck" else visible_md(text), week.draft.name, rules)
    if rules.variant == "memo" and week.cover_email and week.cover_email.is_file():
        hits += prose_hits(visible_md(cu.read_text(week.cover_email)), week.cover_email.name, rules)
    return outcome("fail" if hits else "pass", hits or ["no banned character or phrase"])


def test_continuity(pack, rows) -> dict:
    carry = (pack or {}).get("carry") or []
    if not carry:
        return outcome("na", ["nothing carried from earlier updates"])
    unanswered = [c["id"] for c in carry
                  if (rows.get(f"carry:{c['id']}") or {}).get("state") not in ("done", "moved", "dropped")]
    detail = [f"{len(carry) - len(unanswered)} of {len(carry)} carried items answered"]
    if unanswered:
        detail.append(f"carried items not answered (done, moved or dropped): {', '.join(unanswered)}")
    return outcome("fail" if unanswered else "pass", detail, detail[1] if unanswered else None)


def test_context(week, pack) -> dict:
    if not any(s.get("role") == "context" for s in (pack or {}).get("sources") or []):
        return outcome("na", [f"no engagement context in the pack ({week.engagement.context_label})"])
    path = week.work / cu.CONTEXT_PROPOSED_MD
    if not path.is_file():
        return outcome("fail", [f"no {cu.CONTEXT_PROPOSED_MD}: the writer proposes the context's revision"])
    text = cu.read_text(path)
    if re.search(r"^## Proposed file\s*$", text, re.M):
        if not re.search(r"^\s*1[.)]\s+\S", text.split("## Proposed file", 1)[0], re.M):
            return outcome("fail", ["a proposed file without a numbered list of changes above it"])
        return outcome("pass", ["a revision is proposed for the owner to accept"])
    if re.search(r"\bno changes proposed\b", text, re.I):
        return outcome("pass", ["no changes proposed"])
    return outcome("fail", [f"{cu.CONTEXT_PROPOSED_MD} neither proposes a file under '## Proposed file' "
                            "nor says 'No changes proposed'"])


def test_review(week) -> dict:
    path = week.work / cu.CONFIRMATIONS_MD
    if not path.is_file():
        return outcome("fail", [f"no {cu.CONFIRMATIONS_MD}: ask the owner to review through comms-confirm"])
    requests = CONFIRM_HEAD_RE.findall(cu.read_text(path))
    if not requests:
        return outcome("fail", [f"{cu.CONFIRMATIONS_MD} holds no request"])
    return outcome("pass", [f"{len(requests)} request(s): {', '.join(requests)}"])


def already_done(week):
    """A file Previous updates matches, dated in this ISO week within ALREADY_DAYS of the update
    date, while no draft of ours exists: a person already wrote this week's update. A deck from
    early in the week (a Monday steering deck before a Friday update) is the previous update."""
    if week.draft.is_file():
        return None
    monday = week.date - timedelta(days=week.date.weekday())
    for when, path in cu.rule_matched_updates(week):
        if monday <= when <= monday + timedelta(days=6) and abs((when - week.date).days) <= ALREADY_DAYS \
                and path != week.draft:
            return f"{when.isoformat()} ({path.name})"
    return None


def check(week) -> dict:
    pack, problem = None, None
    try:
        pack = cu.load_sources(week.work)
    except cu.Bad as exc:
        problem = str(exc)
    rows = cu.read_rows(week.work / cu.EVIDENCE_CSV)
    tests = {
        "sources": test_sources(pack, problem),
        "files": test_files(week),
        "claims": test_claims(week, pack, rows),
        "factcheck": test_factcheck(week, rows),
        "redteam": test_redteam(rows),
        "prose": test_prose(week),
        "continuity": test_continuity(pack, rows),
        "context": test_context(week, pack),
        "review": test_review(week),
    }
    failing = [name for name, t in tests.items() if t["state"] == "fail"]
    return {"engagement": week.engagement.name, "week": week.label, "date": week.date.isoformat(),
            "variant": week.engagement.rules.variant, "week_dir": str(week.week_dir),
            "week_dir_exists": week.week_dir.is_dir(), "draft": str(week.draft),
            "tests": tests, "done": not failing, "next": failing[0] if failing else None,
            "already": already_done(week)}


def precheck_line(result) -> str:
    who = f"{result['engagement']} {result['week']}"
    if result["already"]:
        return f"NOTHING: {who}: an update dated {result['already']} is already in the folder"
    if result["done"]:
        return f"NOTHING: {who} is drafted and checked"
    if not result["week_dir_exists"]:
        return f"WORK: {who}: no draft yet for {result['date']}"
    return f"WORK: {who}: {result['next']} ({result['tests'][result['next']]['why'] or 'not done'})"


def render(result) -> str:
    passed = sum(1 for t in result["tests"].values() if t["state"] != "fail")
    out = [f"client-update-check {result['engagement']} {result['week']} ({result['variant']}, dated {result['date']})",
           f"{'DONE' if result['done'] else 'NOT DONE'}: {passed} of {len(TESTS)} tests pass or n/a"
           + (f"; next: {result['next']}" if result["next"] else "")]
    if result["already"]:
        out.append(f"an update dated {result['already']} is already in the folder")
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {test['state'].upper()}")
        out += [f"  - {line}" for line in test["detail"]]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Whether ENGAGEMENT's weekly update for WEEK is drafted and checked.")
    parser.add_argument("engagement", nargs="?", default="", metavar="ENGAGEMENT")
    parser.add_argument("week_arg", nargs="?", default="", metavar="WEEK")
    parser.add_argument("--week", default="", help="yyyy-Www or a yyyy-mm-dd date; blank: this week")
    parser.add_argument("--week-dir", default="", help="Use this folder as the week folder")
    parser.add_argument("--as-of", default="", help="The current week as of this date (yyyy-mm-dd); blank: today")
    parser.add_argument("--contexts-dir", default="", help="Where Context YAML files are found by name")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    args = parser.parse_args()

    week = cu.resolve(args.engagement, cu.blank(args.week_arg) or cu.blank(args.week), args.as_of,
                      args.week_dir, args.contexts_dir)
    result = check(week)
    if args.precheck:
        line = precheck_line(result)
        print(line)
        if line.startswith("WORK") and result["next"]:
            print(f"  failing: {', '.join(n for n, t in result['tests'].items() if t['state'] == 'fail')}")
    elif args.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    cu.run_main(main)
