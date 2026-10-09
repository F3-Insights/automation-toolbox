# /// script
# dependencies = ["pyyaml", "python-pptx", "openpyxl"]
# ///
"""Say whether one company's board package for a period is done, test by test.

Computed from the close folder, the period folder and its evidence file (written only by
board_package_record.py), never from an agent's word. Nine tests, each pass or fail with detail:

  close     the close is done by the rules' Close gate, and the period's trial balance pull is there
  results   the results file is found and work/results-figures.csv was read from it
  files     every package file the rules name exists, with no {{, [TBD], TODO or XX left in it
  figures   every figure printed in the package files has a row in work/package-figures.csv at
            the same place with the same printed value, and every row names a valid source
  tieout    the tie-out, computed again here, ties every figure (or the owner approved an
            exception); every figure a person stated is named in the review note; the tie-out
            ledger beside the package is current
  review    review:finance passed after the last change to a package file or the ledger
  redteam   review:redteam passed after the last change to the deck
  prose     the package files carry no banned character or phrase (the house list plus the rules')
  owner     work/CONFIRMATIONS.md holds a comms-confirm request (the owner's review)

--precheck prints one line for a scheduler: NOTHING when the close is not done, the results
file is missing, a person already made the package, or the package is done; else WORK. Exit 0
whenever it ran; 2 on a bad argument or a missing Context.

    python3 board_package_check.py acme-board --period 2026-09 --period-dir "Reporting/2026-09" --format json
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import _common as bc

TESTS = ("close", "results", "files", "figures", "tieout", "review", "redteam", "prose", "owner")
PLACEHOLDER_RE = re.compile(r"\{\{|\[(?:TBD|TODO|XX+)\]|\bTODO\b|\bXX+\b|\?\?\?")


def outcome(state, detail, why=None) -> dict:
    return {"state": state, "detail": detail, "why": why if why is not None else (detail[0] if detail else "")}


def test_close(per) -> dict:
    state, tb = bc.close_state(per), per.tb_file()
    detail = [state["why"], f"trial balance pull {per.period}: {'present' if tb.is_file() else 'missing'} ({tb})"]
    if not state["done"]:
        return outcome("fail", detail, f"the close is not done: {state['why']}")
    if not tb.is_file():
        return outcome("fail", detail, f"no trial balance pull for {per.period}")
    return outcome("pass", detail)


def test_results(per) -> dict:
    found = per.results_file()
    if found is None:
        return outcome("fail", [f"no file matches {bc.fill(per.rules.results_file, per.period)!r} in {per.close_month}"])
    rows = bc.read_csv(per.work / bc.RESULTS_FIGURES_CSV)
    if not rows:
        return outcome("fail", [f"{found.name} found; no {bc.RESULTS_FIGURES_CSV} yet: run board_package_pack.py"])
    named = {r.get("file") for r in rows}
    if found.name not in named:
        return outcome("fail", [f"{bc.RESULTS_FIGURES_CSV} was read from {', '.join(sorted(named))}, "
                                f"not the newest results file {found.name}: run board_package_pack.py"])
    return outcome("pass", [f"{found.name}: {len(rows)} table figures"])


def test_files(per) -> dict:
    detail, missing = [], []
    for role, path in per.package_files().items():
        if path is None:
            detail.append(f"{role}: none (the rules keep none)")
        elif not path.is_file():
            missing.append(f"{role} ({path.name})")
        else:
            try:
                hit = PLACEHOLDER_RE.search(bc.file_text(path))
            except bc.Bad as exc:
                missing.append(f"{role} ({exc})")
                continue
            if hit:
                missing.append(f"{role} ({path.name}) still holds the placeholder {hit.group(0)!r}")
            else:
                detail.append(f"{role}: {path.name}")
    if missing:
        return outcome("fail", [f"missing or unfinished: {', '.join(missing)}"] + detail)
    return outcome("pass", detail)


def key_of(printed):
    """What makes two printings of a figure the same: value at its decimals, suffix, percent."""
    p = bc.parse_printed(printed)
    return None if p is None else (round(p.value, p.decimals), p.suffix, p.percent)


def show_key(key) -> str:
    value, suffix, percent = key
    return f"{value:g}{suffix}{'%' if percent else ''}"


def test_figures(per) -> dict:
    ledger = bc.read_csv(per.work / bc.PACKAGE_FIGURES_CSV)
    files = [p for p in per.figure_files() if p.is_file()]
    if not files:
        return outcome("fail", ["no package file to read yet"])
    if not ledger:
        return outcome("fail", [f"no figure ledger ({bc.PACKAGE_FIGURES_CSV}): start it with "
                                f"board_package_figures.py --ledger"])
    detail, problems, total = [], [], 0
    unknown = sorted({r.get("file", "") for r in ledger} - {p.name for p in files} - {""})
    if unknown:
        problems.append(f"ledger rows name files that are not package files: {', '.join(unknown)}")
    for path in files:
        try:
            found = bc.extract(path, None, per.rules.figure_ignore)
        except bc.Bad as exc:
            problems.append(str(exc))
            continue
        # Count each (place, figure) printed in the file against the ledger rows for the file.
        printed = Counter((bc.match_location(path.name, f["location"]), key_of(f["printed"]))
                          for f in found if key_of(f["printed"]) is not None)
        total += sum(printed.values())
        listed = Counter()
        for r in ledger:
            if r.get("file") != path.name:
                continue
            key = key_of(r.get("printed", ""))
            if key is None:
                problems.append(f"{r.get('id')}: printed {r.get('printed')!r} is not a number")
            else:
                listed[(bc.match_location(path.name, r.get("location", "")), key)] += 1
        where = lambda loc: f"{path.name}{' ' + loc if loc else ''}"  # noqa: E731
        for (loc, key), n in sorted((printed - listed).items(), key=str):
            problems.append(f"{where(loc)}: {show_key(key)} printed {n} time(s) more than the ledger lists")
        for (loc, key), n in sorted((listed - printed).items(), key=str):
            problems.append(f"{where(loc)}: the ledger lists {show_key(key)} {n} time(s) more than the file prints")
        detail.append(f"{path.name}: {sum(printed.values())} figure(s) printed, {sum(listed.values())} listed")
    unsourced = [r.get("id", "?") for r in ledger if not bc.blank(r.get("source"))]
    if unsourced:
        problems.append(f"rows with no source: {', '.join(unsourced[:20])}" + (" ..." if len(unsourced) > 20 else ""))
    bad = []
    for r in ledger:
        if bc.blank(r.get("source")):
            try:
                bc.parse_source(r["source"])
            except bc.SourceError:
                bad.append(r.get("id", "?"))
    if bad:
        problems.append(f"rows whose source is not results:, tb:, tb-month:, tb-ytd:, calc:, text: or person:: "
                        f"{', '.join(bad)}")
    if problems:
        return outcome("fail", problems + detail, problems[0])
    return outcome("pass", [f"{total} figure(s) across {len(files)} file(s), every one in the ledger with a source"]
                   + detail)


def test_tieout(per):
    try:
        result = bc.tieout(per)
    except bc.Bad as exc:
        return outcome("fail", [str(exc)]), None
    detail = [", ".join(f"{n} {s}" for s, n in sorted(result["counts"].items()))]
    problems = []
    for f in result["figures"]:
        if f["state"] in ("differs", "error") and f.get("exception") is None:
            problems.append(f"{f['id']} {f['file']} {f['location']} {f['printed']} [{f['source']}]: {f.get('detail', '')}")
        elif f.get("exception") is not None:
            detail.append(f"{f['id']}: exception approved by the owner ({f['exception']})")
    if not result["report_tieout"]["passed"]:
        problems.append("report-tieout finds disagreements in the ledger")
    stated = [f["id"] for f in result["figures"] if f["state"] == "stated"]
    if stated:
        note = per.review_note
        text = note.read_text(encoding="utf-8", errors="replace") if note.is_file() else ""
        unnamed = [fid for fid in stated if not re.search(rf"(?<![A-Za-z0-9]){re.escape(fid)}(?![0-9])", text)]
        if unnamed:
            problems.append(f"figures stated by a person and not named in the review note ({note.name}): "
                            f"{', '.join(unnamed)}")
    ledger = per.tieout_ledger
    if not ledger.is_file():
        problems.append(f"no tie-out ledger beside the package ({ledger.name}): run board_package_tieout.py")
    elif ledger.read_text(encoding="utf-8") != bc.tieout_ledger_text(result):
        problems.append(f"{ledger.name} is not current: run board_package_tieout.py again")
    if problems:
        return outcome("fail", problems + detail, problems[0]), result
    return outcome("pass", detail), result


def test_review(per, rows, kind, watched, what) -> dict:
    row = rows.get(f"review:{kind}")
    if not row:
        return outcome("fail", [f"no {what} recorded (board_package_record.py review --kind {kind})"])
    if row.get("state") != "passed":
        return outcome("fail", [f"the {what} {row.get('state') or 'has no state'}: {row.get('note', '')}".strip()])
    try:
        when = datetime.fromisoformat(row.get("updated_at", "").strip())
    except ValueError:
        return outcome("fail", [f"the {what} has no time recorded"])
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    times = [datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) for p in watched if p.is_file()]
    latest = max(times).replace(microsecond=0) if times else None
    if latest is not None and latest > when:
        return outcome("fail", [f"the {what} passed at {when.isoformat()}, before the last change "
                                f"({latest.isoformat()}): review again"])
    return outcome("pass", [f"passed {when.isoformat()} ({Path(row.get('review_file', '')).name})"])


def test_prose(per) -> dict:
    rules, checked, problems = per.rules, [], []
    phrases = list(bc.HOUSE_PHRASES) + [p.lower() for p in rules.banned_phrases]
    for role in ("deck", "script", "cover email", "lender pack"):
        path = per.package_files().get(role)
        if path is None or not path.is_file():
            continue
        try:
            text = bc.file_text(path)
        except bc.Bad as exc:
            problems.append(str(exc))
            continue
        checked.append(path.name)
        hits = [f"character U+{ord(c):04X}" for c in rules.banned_characters if c and c in text]
        hits += [f"phrase {p!r}" for p in phrases
                 if p and re.search(rf"(?<![a-z]){re.escape(p.lower())}(?![a-z])", text.lower())]
        if hits:
            problems.append(f"{path.name}: {', '.join(hits)}")
    if not checked and not problems:
        return outcome("fail", ["no package file to read yet"])
    return outcome("fail", problems) if problems else outcome("pass", [f"clean: {', '.join(checked)}"])


def test_owner(per) -> dict:
    store = per.work / bc.CONFIRMATIONS_MD
    if not store.is_file():
        return outcome("fail", [f"no {bc.CONFIRMATIONS_MD}: ask the owner to review through comms-confirm"])
    requests = bc.CONFIRM_HEAD_RE.findall(store.read_text(encoding="utf-8", errors="replace"))
    if not requests:
        return outcome("fail", [f"{bc.CONFIRMATIONS_MD} holds no request"])
    return outcome("pass", [f"{len(requests)} request(s): {', '.join(requests)}"])


def check(per) -> dict:
    rows = bc.evidence_rows(per.evidence_file)
    tieout_test, tieout_result = test_tieout(per)
    tests = {
        "close": test_close(per),
        "results": test_results(per),
        "files": test_files(per),
        "figures": test_figures(per),
        "tieout": tieout_test,
        "review": test_review(per, rows, "finance", per.figure_files() + [per.work / bc.PACKAGE_FIGURES_CSV],
                              "finance review"),
        "redteam": test_review(per, rows, "redteam", [per.deck], "red-team review"),
        "prose": test_prose(per),
        "owner": test_owner(per),
    }
    failing = [name for name, t in tests.items() if t["state"] == "fail"]
    people = per.people_package()
    return {"company": per.company.name, "period": per.period, "period_dir": str(per.period_dir),
            "period_dir_exists": per.period_dir.is_dir(), "deck": str(per.deck),
            "people_package": str(people) if people else None,
            "tests": tests, "done": not failing, "next": failing[0] if failing else None,
            "tieout": {k: v for k, v in (tieout_result or {}).items()
                       if k in ("counts", "failing", "exceptions", "passed")}}


def precheck_line(result) -> str:
    who = f"{result['company']} {result['period']}"
    if result["people_package"] and not Path(result["deck"]).is_file():
        return f"NOTHING: {who}: a person already made the package ({Path(result['people_package']).name})"
    if result["done"]:
        return f"NOTHING: {who}: the package is drafted, tied and reviewed"
    for gate in ("close", "results"):
        if result["tests"][gate]["state"] == "fail":
            return f"NOTHING: {who}: waiting on the {gate} ({result['tests'][gate]['why']})"
    if not Path(result["deck"]).is_file():
        return f"WORK: {who}: the close is done and no package is drafted yet"
    return f"WORK: {who}: {result['next']} ({result['tests'][result['next']]['why'] or 'not done'})"


def render(result) -> str:
    passed = sum(1 for t in result["tests"].values() if t["state"] != "fail")
    out = [f"board-package-check {result['company']} {result['period']} ({result['period_dir']})",
           f"{'DONE' if result['done'] else 'NOT DONE'}: {passed} of {len(TESTS)} tests pass"
           + (f"; next: {result['next']}" if result["next"] else "")]
    if result["people_package"]:
        out.append(f"a person's package for the period is in the folder: {result['people_package']}")
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {test['state'].upper()}")
        out += [f"  - {line}" for line in test["detail"]]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Whether COMPANY's board package for PERIOD is done, test by test.")
    parser.add_argument("company", nargs="?", default="", metavar="COMPANY")
    bc.add_period_options(parser)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    args = parser.parse_args()

    result = check(bc.resolve(args))
    if args.precheck:
        line = precheck_line(result)
        print(line)
        if line.startswith("WORK"):
            print(f"  failing: {', '.join(n for n, t in result['tests'].items() if t['state'] == 'fail')}")
    elif args.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    bc.run_main(main)
