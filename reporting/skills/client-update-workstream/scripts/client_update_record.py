# /// script
# dependencies = ["pyyaml"]
# ///
"""Record one week of a client update: claims, fact-check verdicts, reviews and carried items,
and carry the week into the engagement's ledger of open items. The only writer of the week's
evidence file, work/UPDATE-EVIDENCE.csv (columns id,kind,item,state,sources,location,evidence,
review,review_file,note,updated_at,by).

  claims --from claims.json            record the writer's claim inventory: new or changed claims
                                       become pending, claims absent from the file are cut, and
                                       each carry item gets its carry:<id> row
  factcheck --checker a|b --from F     record one fact-checker's verdicts (VERIFIED, NOT IN MY
                                       SOURCES, CONTRADICTED). A claim is contradicted when either
                                       says CONTRADICTED, else verified when either says VERIFIED
                                       (a flagged claim stays flagged), else unsupported once both
                                       have spoken, else pending
  flag | cut --claim C3 --note TEXT    flag a claim only the owner can stand behind, or cut one
  review --kind redteam|unslop --state passed|failed --file PATH [--note TEXT]
  ledger [--ledger PATH]               carry the week into <updates>/UPDATES-LEDGER.csv: carried
                                       items close (done, dropped) or stay open (moved, with the
                                       new due date; open), and each next step opens a row with id
                                       L- + 8 hex of the sha1 of its normalised text. Refused
                                       while any claim is contradicted
  render                               (memo) the memo's Word file, the draft's stem with .docx,
                                       made by pandoc from the draft without its source comments;
                                       an unchanged draft is ALREADY, and an earlier Word file
                                       moves to work/superseded-<stamp>/ first. The owner setting
                                       reference_docx in [client-update-workstream] names an
                                       optional Word reference document for pandoc's styles
  show [--format text|json]            print the evidence rows

WEEK is yyyy-Www, a date in the week, or "" for this week. --week-dir, --by, --as-of and
--contexts-dir go before ENGAGEMENT or after the subcommand. Exit 0 recorded, 1 refused (a
claims or verdicts file that breaks the contract, an unknown claim, a contradicted claim at
ledger), 2 on a bad argument or an unreadable file.

    python3 client_update_record.py acme-weekly-update 2026-W40 claims --from work/claims.json --week-dir "Weekly Update/2026-10-02"
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import _common as cu

CLAIM_ID = re.compile(r"^C\d+$")
VERDICTS = ("VERIFIED", "NOT IN MY SOURCES", "CONTRADICTED")
CHECKERS = ("a", "b")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


class Ctx:
    """The week being recorded and who records it."""

    def __init__(self, args):
        self.week = cu.resolve(args.engagement, cu.blank(args.week), args.as_of, args.week_dir, args.contexts_dir)
        self.by = cu.blank(args.by) or "client-update-record"
        self.work = self.week.work

    def upsert(self, key, values) -> str:
        return cu.record_evidence(self.work, key, {**values, "updated_at": cu.now_utc(), "by": self.by})

    def rows(self) -> dict:
        return cu.read_rows(self.work / cu.EVIDENCE_CSV)


def refuse(problems, what):
    raise cu.Refused(f"{what} refused, nothing recorded:\n" + "\n".join(f"  - {p}" for p in problems))


def parse_review(cell: str) -> dict:
    """'a:VERIFIED | b:NOT IN MY SOURCES' as {checker: verdict}."""
    out = {}
    for part in (cell or "").split("|"):
        who, _, verdict = part.partition(":")
        if verdict and who.strip() in CHECKERS:
            out[who.strip()] = verdict.strip()
    return out


def claim_state(verdicts: dict, current: str) -> str:
    said = list(verdicts.values())
    if "CONTRADICTED" in said:
        return "contradicted"
    if current == "flagged":
        return "flagged"
    if "VERIFIED" in said:
        return "verified"
    return "unsupported" if all(k in verdicts for k in CHECKERS) else "pending"


def ledger_id(text: str) -> str:
    normalised = " ".join(re.sub(r"[^\w\s]", " ", str(text).lower()).split())
    return "L-" + hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:8]


# --------------------------------------------------------------------------- claims

def validate_claims(data, known, carry_ids) -> list:
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        return ["the file is not an object with a claims list"]
    problems, seen = [], set()
    for n, claim in enumerate(data["claims"], start=1):
        if not isinstance(claim, dict):
            problems.append(f"claim {n} is not an object")
            continue
        cid = str(claim.get("id") or "")
        if not CLAIM_ID.match(cid):
            problems.append(f"claim {n}: id {cid!r} is not C followed by digits")
        elif cid in seen:
            problems.append(f"claim id {cid} is used twice")
        seen.add(cid)
        if not str(claim.get("text") or "").strip():
            problems.append(f"claim {cid or n} has no text")
        sources = claim.get("sources")
        if not isinstance(sources, list) or not sources:
            problems.append(f"claim {cid or n} names no source")
            continue
        problems += [f"claim {cid or n}: source {s} is not in {cu.SOURCES_JSON}" for s in sources if str(s) not in known]
    for n, item in enumerate(data.get("carry") or [], start=1):
        if not isinstance(item, dict):
            problems.append(f"carry item {n} is not an object")
            continue
        name, state = item.get("id") or n, str(item.get("state") or "")
        if state not in cu.CARRY_STATES:
            problems.append(f"carry item {name}: state {state!r} is not one of {', '.join(cu.CARRY_STATES)}")
        if str(item.get("id") or "") not in carry_ids:
            problems.append(f"carry item {name} is not an open ledger item in the pack")
        if state == "moved" and not cu.DATE_RE.fullmatch(str(item.get("new_due") or "")):
            problems.append(f"carry item {name} is moved without a yyyy-mm-dd new_due")
    for n, step in enumerate(data.get("next_steps") or [], start=1):
        if not isinstance(step, dict) or not str(step.get("text") or "").strip():
            problems.append(f"next step {n} has no text")
    return problems


def keep_claims_file(source: Path, work: Path) -> Path:
    """work/claims.json holds this file; a different one already there is kept aside."""
    target = work / cu.CLAIMS_JSON
    if source.resolve() == target.resolve():
        return target
    if target.exists():
        if target.read_bytes() == source.read_bytes():
            return target
        target.rename(cu.free_path(work / f"claims-{cu.stamp()}.json"))
    work.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def record_claims(ctx, path) -> list:
    source = Path(path).expanduser()
    data = cu.load_json(source, "claims file")
    pack = cu.load_sources(ctx.work)
    problems = validate_claims(data, cu.source_ids(pack), [c["id"] for c in pack.get("carry") or []])
    if problems:
        refuse(problems, source.name)
    kept = keep_claims_file(source, ctx.work)
    rows = ctx.rows()
    counts = {"new": 0, "changed": 0, "same": 0, "cut": 0, "carry": 0}
    given = set()
    for claim in data["claims"]:
        cid = claim["id"]
        given.add(cid)
        values = {"kind": "claim", "item": " ".join(str(claim["text"]).split()),
                  "sources": " ".join(str(s) for s in claim["sources"]),
                  "location": str(claim.get("location") or ""), "evidence": kept.name}
        old = rows.get(f"claim:{cid}")
        if old is None:
            counts["new"] += 1
            values["state"] = "pending"
        elif old.get("state") == "cut" or any(old.get(k, "") != values[k] for k in ("item", "sources", "location")):
            counts["changed"] += 1
            values.update(state="pending", review="", review_file="")
        else:
            counts["same"] += 1
        ctx.upsert(f"claim:{cid}", values)
    for key, row in rows.items():
        if row.get("kind") == "claim" and key.split(":", 1)[1] not in given and row.get("state") != "cut":
            ctx.upsert(key, {"state": "cut", "note": f"absent from {kept.name} at {cu.now_utc()}"})
            counts["cut"] += 1
    for item in data.get("carry") or []:
        note = str(item.get("note") or "")
        if item.get("new_due"):
            note = (note + f" (new due {item['new_due']})").strip()
        ctx.upsert(f"carry:{item['id']}", {"kind": "carry", "item": str(item.get("text") or ""),
                                           "state": item["state"], "evidence": kept.name, "note": note})
        counts["carry"] += 1
    return [f"RECORDED: {len(given)} claims ({counts['new']} new, {counts['changed']} changed, "
            f"{counts['same']} unchanged), {counts['cut']} cut, {counts['carry']} carry item(s) "
            f"in {ctx.work / cu.EVIDENCE_CSV}"]


# --------------------------------------------------------------------------- fact-check, flag, cut, review

def record_factcheck(ctx, checker, path) -> list:
    source = Path(path).expanduser()
    data = cu.load_json(source, "verdicts file")
    if not isinstance(data, list):
        refuse(["the file is not a list of verdicts"], source.name)
    rows, problems, seen = ctx.rows(), [], set()
    for n, verdict in enumerate(data, start=1):
        if not isinstance(verdict, dict):
            problems.append(f"verdict {n} is not an object")
            continue
        cid = str(verdict.get("claim") or "").strip()
        said = " ".join(str(verdict.get("verdict") or "").upper().split())
        if f"claim:{cid}" not in rows:
            problems.append(f"verdict {n}: no claim {cid or '(blank)'} is recorded")
        if said not in VERDICTS:
            problems.append(f"verdict {n}: {verdict.get('verdict')!r} is not one of {', '.join(VERDICTS)}")
        if cid in seen:
            problems.append(f"claim {cid} has two verdicts")
        seen.add(cid)
    if problems:
        refuse(problems, source.name)
    tally = {}
    for verdict in data:
        cid = str(verdict["claim"]).strip()
        said = " ".join(str(verdict["verdict"]).upper().split())
        tally[said] = tally.get(said, 0) + 1
        row = rows[f"claim:{cid}"]
        verdicts = {**parse_review(row.get("review", "")), checker: said}
        state = "cut" if row.get("state") == "cut" else claim_state(verdicts, row.get("state", ""))
        ctx.upsert(f"claim:{cid}", {"review": " | ".join(f"{k}:{verdicts[k]}" for k in CHECKERS if k in verdicts),
                                    "review_file": str(source), "state": state})
    try:
        half = [s["id"] for s in cu.load_sources(ctx.work).get("sources") or [] if s.get("half") == checker]
    except cu.Bad:
        half = []
    ctx.upsert(f"review:factcheck-{checker}", {"kind": "review", "item": f"fact-check half {checker}", "state": "ran",
                                               "evidence": str(source), "note": " ".join(half)})
    return [f"RECORDED: fact-check {checker}, {len(data)} verdict(s) "
            + ", ".join(f"{k} {v}" for k, v in sorted(tally.items()))]


def record_mark(ctx, claim, state, note) -> list:
    key = f"claim:{claim.strip()}"
    if key not in ctx.rows():
        raise cu.Refused(f"no claim {claim.strip()} is recorded for {ctx.week.label}")
    ctx.upsert(key, {"state": state, "note": note})
    return [f"RECORDED: {key} {state}"]


def record_review(ctx, kind, state, path, note) -> list:
    target = Path(path).expanduser()
    if not target.is_file():
        raise cu.Bad(f"no review file at {target}")
    ctx.upsert(f"review:{kind}", {"kind": "review", "item": f"{kind} review", "state": state,
                                  "evidence": str(target), "note": note})
    return [f"RECORDED: review:{kind} {state}"]


# --------------------------------------------------------------------------- ledger

def record_ledger(ctx, path) -> list:
    rows = ctx.rows()
    contradicted = [k for k, r in rows.items() if r.get("kind") == "claim" and r.get("state") == "contradicted"]
    if contradicted:
        raise cu.Refused("the week has contradicted claims, so nothing is carried: " + ", ".join(contradicted))
    target = Path(cu.blank(path)).expanduser() if cu.blank(path) else ctx.week.ledger_file
    existing = cu.read_rows(target)
    claims_file = ctx.work / cu.CLAIMS_JSON
    data = cu.load_json(claims_file, cu.CLAIMS_JSON) if claims_file.is_file() else {}
    dues = {str(c.get("id")): str(c.get("new_due") or "") for c in data.get("carry") or [] if isinstance(c, dict)}
    week, now = ctx.week.label, cu.now_utc()
    closed = moved = kept_open = opened = 0
    for key, row in rows.items():
        if row.get("kind") != "carry":
            continue
        lid, state = key.split(":", 1)[1], row.get("state")
        values = {"last_week": week, "updated_at": now, "by": ctx.by}
        if lid not in existing:
            values.update(item=row.get("item", ""), opened_week=week)
        if row.get("note"):
            values["note"] = row["note"]
        if state in ("done", "dropped"):
            values["state"] = state
            closed += 1
        elif state == "moved":
            values["state"] = "open"
            if dues.get(lid):
                values["due"] = dues[lid]
            moved += 1
        else:
            values["state"] = "open"
            kept_open += 1
        cu.upsert_row(target, cu.LEDGER_COLUMNS, lid, values)
    for step in data.get("next_steps") or []:
        if not isinstance(step, dict) or not str(step.get("text") or "").strip():
            continue
        lid = ledger_id(step["text"])
        if lid in existing or lid in cu.read_rows(target):
            continue
        cu.upsert_row(target, cu.LEDGER_COLUMNS, lid, {
            "item": " ".join(str(step["text"]).split()), "owner": str(step.get("owner") or ""),
            "due": str(step.get("due") or ""), "state": "open", "opened_week": week, "last_week": week,
            "updated_at": now, "by": ctx.by})
        opened += 1
    return [f"RECORDED: ledger {target}: {closed} closed, {moved} moved, {kept_open} kept open, {opened} opened"]


# --------------------------------------------------------------------------- render and show

def record_render(ctx) -> list:
    """The memo's Word file from its Markdown draft, without the source comments."""
    week = ctx.week
    if week.engagement.rules.variant != "memo":
        raise cu.Bad("a deck has no Word file; render is for a memo")
    draft, docx = week.draft, week.docx
    if not draft.is_file():
        raise cu.Bad(f"no memo draft at {draft}")
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise cu.Bad("pandoc is needed to make the Word file and is not installed")
    text = re.sub(r"\n{3,}", "\n\n", COMMENT_RE.sub("", draft.read_text(encoding="utf-8"))).strip() + "\n"
    folder = ctx.work / "render"
    plain = folder / f"{draft.stem}.md"
    if docx.is_file() and plain.is_file() and plain.read_text(encoding="utf-8") == text:
        return [f"ALREADY: {docx.name} is rendered from this draft"]
    moved = []
    for old in (docx, plain):
        if old.is_file():
            keep = ctx.work / f"superseded-{cu.stamp()}"
            keep.mkdir(parents=True, exist_ok=True)
            target = cu.free_path(keep / old.name)
            shutil.move(str(old), str(target))
            moved.append(str(target))
    folder.mkdir(parents=True, exist_ok=True)
    plain.write_text(text, encoding="utf-8")
    built = cu.free_path(folder / f"{draft.stem}.docx")
    command = [pandoc, str(plain), "--from", "markdown+pipe_tables", "--to", "docx", "--output", str(built)]
    reference = cu.blank(cu.settings("client-update-workstream").get("reference_docx"))
    if reference:
        if not Path(reference).expanduser().is_file():
            raise cu.Bad(f"the reference_docx setting names no file: {reference}")
        command.append(f"--reference-doc={Path(reference).expanduser()}")
    done = subprocess.run(command, capture_output=True, check=False)
    if done.returncode != 0 or not built.is_file():
        raise cu.Bad(f"pandoc could not write the Word file: {done.stderr.decode('utf-8', 'replace')[:300]}")
    with zipfile.ZipFile(built) as archive:
        body = archive.read("word/document.xml").decode("utf-8", "replace")
    if re.search(r"Source:\s*C\d+", body):
        raise cu.Refused(f"{built.name} still carries a source comment; not moved into the week folder")
    shutil.move(str(built), str(docx))
    return [f"RENDERED: {docx}"] + [f"  kept the earlier file as {path}" for path in moved]


def show(ctx, fmt) -> list:
    rows = list(ctx.rows().values())
    if fmt == "json":
        return [json.dumps({"evidence": str(ctx.work / cu.EVIDENCE_CSV), "rows": rows}, indent=1, ensure_ascii=False)]
    return [f"{ctx.work / cu.EVIDENCE_CSV} ({len(rows)} rows)"] + [
        f"{r['id']}  {r.get('state', '')}" + (f"  [{r['sources']}]" if r.get("sources") else "")
        + (f"  {r['review']}" if r.get("review") else "") + (f"  {r['item'][:80]}" if r.get("item") else "")
        for r in rows]


def shared_options(parser, default) -> None:
    parser.add_argument("--week-dir", default=default, help="Use this folder as the week folder")
    parser.add_argument("--by", default=default, help="Who records (an agent or a person's role)")
    parser.add_argument("--as-of", default=default, help="The current week as of this date, for a blank WEEK")
    parser.add_argument("--contexts-dir", default=default, help="Where Context YAML files are found by name")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record one week's claims, verdicts, reviews and carried items.")
    parser.add_argument("engagement", metavar="ENGAGEMENT")
    parser.add_argument("week", metavar="WEEK", help='yyyy-Www, a date, or "" for this week')
    shared_options(parser, None)
    shared = argparse.ArgumentParser(add_help=False)
    shared_options(shared, argparse.SUPPRESS)   # given after the subcommand, these win
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("claims", parents=[shared])
    p.add_argument("--from", dest="path", required=True, help="The claims.json the writer returned")
    p = sub.add_parser("factcheck", parents=[shared])
    p.add_argument("--checker", choices=CHECKERS, required=True)
    p.add_argument("--from", dest="path", required=True, help="The checker's verdicts JSON")
    for name in ("flag", "cut"):
        p = sub.add_parser(name, parents=[shared])
        p.add_argument("--claim", required=True)
        p.add_argument("--note", required=True)
    p = sub.add_parser("review", parents=[shared])
    p.add_argument("--kind", choices=("redteam", "unslop"), required=True)
    p.add_argument("--state", choices=("passed", "failed"), required=True)
    p.add_argument("--file", dest="path", required=True, help="The review's file")
    p.add_argument("--note", default="")
    p = sub.add_parser("ledger", parents=[shared])
    p.add_argument("--ledger", dest="path", default="", help="The ledger file; blank: <updates>/UPDATES-LEDGER.csv")
    sub.add_parser("render", parents=[shared])
    p = sub.add_parser("show", parents=[shared])
    p.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    ctx = Ctx(args)
    actions = {
        "claims": lambda: record_claims(ctx, args.path),
        "factcheck": lambda: record_factcheck(ctx, args.checker, args.path),
        "flag": lambda: record_mark(ctx, args.claim, "flagged", args.note),
        "cut": lambda: record_mark(ctx, args.claim, "cut", args.note),
        "review": lambda: record_review(ctx, args.kind, args.state, args.path, args.note),
        "ledger": lambda: record_ledger(ctx, args.path),
        "render": lambda: record_render(ctx),
        "show": lambda: show(ctx, args.format),
    }
    for line in actions[args.action]():
        print(line)
    return 0


if __name__ == "__main__":
    cu.run_main(main)
