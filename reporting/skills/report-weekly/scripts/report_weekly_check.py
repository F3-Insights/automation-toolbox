#!/usr/bin/env python3
"""report-weekly-check: whether the week's leadership report is done, computed from its files.

    report_weekly_check.py STORE [--period YYYY-MM-DD] [--phase collect|assemble|auto]
                           [--report-folder DIR] [--as-of YYYY-MM-DD] [--format text|json] [--precheck]

STORE is the author's report store; the week's working files are in STORE/work/<period>/.
Seven tests, each from files, never from what a session says it did:
  1 evidence    ledger.json with items, pack.json with no outline errors, digest.md, editor.txt
                and verdicts.json, and continuity.txt where the ledger had candidates
  2 gates       gates.json built, a "Weekly report gates" request in CONFIRMATIONS.md, and
                gate1.json and owner-input.md written from the answers or the defaults
  3 sections    the draft (approved.md, else draft.md) has a heading for every category of the
                pack and a Decisions needed block
  4 numbers     report_verify.py finds no error, and no untied figure (NOT_IN_CITED_RECORD,
                UNCITED_FIGURE, FIGURE_NOT_CITED_TO_FACTS) unless the owner approved; and
                report_facts.py tie-out finds nothing. Both are run here
  5 continuity  no CARRY_OVER_NOT_ADDRESSED finding
  6 rendered    weekly-<period>.docx and .pdf (or the -DRAFT pair) in REPORT_FOLDER/<period>/,
                the PDF within two pages
  7 recorded    approved.md, STORE/records/<period>/record.json with ledger_pending false, and
                the work order closed
--phase collect is done once the evidence is in and the gate questions are out; assemble once
the draft is verified, rendered and put to the owner; auto needs all seven. `next` names the next
step and who it waits on; `earlier` lists earlier weeks the owner approved and nobody kept.
--precheck prints one line for a scheduler, WORK: <why> or NOTHING: <why>.

Exit 0 whenever it ran; 2 on a bad argument or a missing store.

Example:
  python3 report_weekly_check.py ~/reports/finance --period 2027-11-12 --phase collect --precheck
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

from _common import (DRAFT_QUESTION, GATES_QUESTION, OK, PERIOD, WORK_DIR, Fail, first_line, header_of,
                     json_or_none, request_for, request_state, resolve_period, run_main, run_script,
                     store_dir, week_dir, week_file)

TESTS = ("evidence", "gates", "sections", "numbers", "continuity", "rendered", "recorded")
PHASES = {"collect": ("evidence", "gates"), "assemble": TESTS[:6], "auto": TESTS}
UNTIED = ("NOT_IN_CITED_RECORD", "UNCITED_FIGURE", "FIGURE_NOT_CITED_TO_FACTS")
AGENT_STEPS = {"collect": ("collect", "judge", "ask-gates"),
               "assemble": ("apply-gates", "write", "fix-draft", "render", "ask-approval", "approve", "record")}


def clean(text):
    return " ".join(re.sub(r"[*_`]", "", text).split()).casefold()


def pdf_pages(path):
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:  # noqa: BLE001 - no pypdf, or a PDF it cannot read: count the page objects
        found = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", path.read_bytes()))
        return found or None


def check(store, period, phase, report_folder, today):
    folder = week_dir(store, period)
    has = lambda role: week_file(folder, role).is_file()  # noqa: E731
    pack = json_or_none(week_file(folder, "pack"))
    gates_request = request_for(week_file(folder, "confirmations"), GATES_QUESTION)
    draft_request = request_for(week_file(folder, "confirmations"), DRAFT_QUESTION)
    tests = {}

    ledger = json_or_none(week_file(folder, "ledger"))
    items = len((ledger or {}).get("items") or []) if isinstance(ledger, dict) else 0
    wanted = len((json_or_none(week_file(folder, "candidates")) or {}).get("candidates") or [])
    gaps = (["not collected: no ledger.json"] if not has("ledger") else
            ["the evidence ledger holds no items"] if not items else [])
    if not isinstance(pack, dict):
        gaps.append("not organised: no pack.json")
    elif (pack.get("outline") or {}).get("errors"):
        gaps.append(f"the profile has {len(pack['outline']['errors'])} error(s); fix the profile")
    gaps += [] if has("digest") else ["no digest.md"]
    gaps += [f"{wanted} ledger candidates and no continuity.txt"] if wanted and not has("continuity") else []
    gaps += [] if has("editor") else ["no editor.txt from report-audience-editor"]
    gaps += [] if has("verdicts") else ["no verdicts.json (report_questions.py verdicts)"]
    tests["evidence"] = {"met": not gaps, "gaps": gaps, "items": items, "ledger_candidates": wanted}

    state, resolved, gaps = request_state(gates_request, today), has("gate1") and has("owner_input"), []
    if not has("gates"):
        gaps.append("the gate questions are not built (report_weekly_gates.py build)")
    elif state == "none":
        gaps.append("the gate questions are not asked (comms-confirm)")
    if not resolved:
        gaps.append(f"waiting on the owner's answers, due {gates_request.get('Due') or 'unknown'}" if state == "open" else
                    f"the request is {state}: apply the answers or the defaults (report_weekly_gates.py apply)"
                    if state in ("past-due", "answered", "closed") else "no gate1.json and owner-input.md yet"
                    if has("gates") else "")
    gaps = [g for g in gaps if g]
    tests["gates"] = {"met": not gaps, "gaps": gaps, "asked": state != "none", "request": state, "resolved": resolved}

    draft = week_file(folder, "approved") if has("approved") else week_file(folder, "draft")
    text = draft.read_text(encoding="utf-8") if draft.is_file() else None
    if text is None:
        tests["sections"] = {"met": False, "gaps": ["no draft.md yet"]}
    else:
        headers = {clean(h) for line in text.splitlines() if (h := header_of(line))}
        missing = [c["name"] for c in (pack or {}).get("categories") or [] if clean(c["name"]) not in headers]
        gaps = [f"no section for '{n}'" for n in missing] + ([] if "decisions needed" in clean(text) else
                                                             ["no Decisions needed block"])
        tests["sections"] = {"met": not gaps, "gaps": gaps}

    findings = []
    if text is None or not isinstance(pack, dict):
        tests["numbers"] = {"met": False, "gaps": ["no draft to verify"]}
    else:
        code, out, err = run_script("report_verify", ["--report", draft, "--pack", week_file(folder, "pack"), "--json"])
        found = json_or_none_text(out)
        gaps = []
        if not found:
            gaps.append(f"report-verify did not run: {first_line(err) or 'no output'}")
        else:
            findings = found.get("findings") or []
            if found.get("errors"):
                first = found["errors"][0]
                gaps.append(f"report-verify: {len(found['errors'])} error(s), first: {first['kind']} {first.get('text')}")
            untied = [f for f in findings if f["kind"] in UNTIED]
            if untied and not has("approved"):
                gaps.append(f"{len(untied)} figure(s) not tied to a record or a fact, first: {untied[0]['kind']} "
                            f"{untied[0].get('text')}")
        if has("facts"):
            tie, out, err = run_script("report_facts", ["tie-out", "--facts", week_file(folder, "facts"), "--report", draft])
            if tie:
                gaps.append(f"report-facts tie-out: {first_line(out) or first_line(err)}")
        tests["numbers"] = {"met": not gaps, "gaps": gaps}

    open_carries = [f.get("text") for f in findings if f["kind"] == "CARRY_OVER_NOT_ADDRESSED"]
    tests["continuity"] = {"met": text is not None and not open_carries,
                           "gaps": ["no draft yet"] if text is None else [f"carry-over not answered: {t}" for t in open_carries]}

    files, pages, gaps = [], None, []
    if report_folder is None:
        gaps.append("no --report-folder given, so the files cannot be found")
    else:
        for base in (f"weekly-{period}", f"weekly-{period}-DRAFT"):
            docx, pdf = report_folder / period / f"{base}.docx", report_folder / period / f"{base}.pdf"
            if docx.is_file() and pdf.is_file():
                files, pages = [str(docx), str(pdf)], pdf_pages(pdf)
                break
        gaps += ([f"no Word and PDF pair in {report_folder / period}"] if not files else
                 ["the PDF's page count cannot be read"] if pages is None else
                 [f"the PDF is {pages} pages, over the 2-page cap"] if pages > 2 else [])
    tests["rendered"] = {"met": not gaps, "gaps": gaps, "files": files, "pages": pages,
                         "final": bool(files) and "-DRAFT" not in files[0]}

    gaps = []
    if not has("approved"):
        gaps.append("the owner has not approved the draft" + ("; the request has an answer to apply"
                    if request_state(draft_request, today) in ("answered", "closed") else ""))
    manifest = json_or_none(store / "records" / period / "record.json")
    gaps += (["not kept: no records/<period>/record.json (report_record.py save)"] if not isinstance(manifest, dict)
             else ["kept, but the report ledger is pending"] if manifest.get("ledger_pending") else [])
    order = json_or_none(store / "workorder" / f"{period}.json")
    gaps += [] if isinstance(order, dict) and order.get("closed_at") else ["the work order is not closed"]
    tests["recorded"] = {"met": not gaps, "gaps": gaps}

    prepared = json_or_none(week_file(folder, "prepare")) or {}
    draft_state = request_state(draft_request, today)
    if prepared.get("blocked") or not (store / "profile.md").is_file():
        nxt = ("profile", "owner", "the role profile is missing, invalid or due for review; the owner runs the report-weekly setup interview")
    elif not has("pack"):
        nxt = ("collect", "agent", "the week is not collected")
    elif not tests["evidence"]["met"]:
        nxt = ("judge", "agent", tests["evidence"]["gaps"][0])
    elif not has("gates") or not tests["gates"]["asked"]:
        nxt = ("ask-gates", "agent", tests["gates"]["gaps"][0])
    elif not tests["gates"]["met"]:
        nxt = ("wait-gates", "owner", tests["gates"]["gaps"][0]) if tests["gates"]["request"] == "open" else \
            ("apply-gates", "agent", tests["gates"]["gaps"][0])
    elif text is None:
        nxt = ("write", "agent", "no draft yet")
    elif not all(tests[n]["met"] for n in ("sections", "numbers", "continuity")):
        nxt = ("fix-draft", "agent", next(tests[n]["gaps"][0] for n in ("sections", "numbers", "continuity")
                                          if not tests[n]["met"]))
    elif not tests["rendered"]["met"]:
        nxt = ("render", "agent", tests["rendered"]["gaps"][0])
    elif not has("approved"):
        nxt = ("ask-approval", "agent", "the draft is not yet put to the owner") if draft_state == "none" else \
            ("wait-approval", "owner", "the draft is with the owner to approve") if draft_state in ("open", "past-due") \
            else ("approve", "agent", "the owner answered the draft request: apply it")
    elif not tests["recorded"]["met"]:
        nxt = ("record", "agent", tests["recorded"]["gaps"][0])
    else:
        nxt = ("done", "nobody", "every test of done is met")
    if phase == "collect":
        phase_done = tests["evidence"]["met"] and tests["gates"]["asked"]
    elif phase == "assemble":
        phase_done = all(tests[n]["met"] for n in PHASES["assemble"]) and (has("approved") or draft_state != "none")
    else:
        phase_done = all(t["met"] for t in tests.values())
    earlier = []
    work = store / WORK_DIR
    for other in sorted(p for p in work.iterdir() if p.is_dir() and PERIOD.match(p.name)) if work.is_dir() else []:
        if other.name < period and not (store / "records" / other.name / "record.json").is_file() and (
                week_file(other, "approved").is_file() or request_state(
                    request_for(week_file(other, "confirmations"), DRAFT_QUESTION), today) in ("answered", "closed")):
            earlier.append(other.name)
    return {"scope": str(store), "period": period, "phase": phase, "folder": str(folder), "as_of": today.isoformat(),
            "tests": tests, "met": sum(1 for t in tests.values() if t["met"]), "of": len(TESTS),
            "phase_tests": list(PHASES[phase]), "phase_done": phase_done,
            "done": all(t["met"] for t in tests.values()),
            "next": {"step": nxt[0], "waits_on": nxt[1], "why": nxt[2]}, "earlier": earlier}


def json_or_none_text(text):
    try:
        found = json.loads(text)
    except (TypeError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def precheck_line(result):
    nxt = result["next"]
    if result["earlier"]:
        return f"WORK: the owner answered the draft for {', '.join(result['earlier'])}; keep it"
    if nxt["step"] == "profile":
        return f"NOTHING: {nxt['why']}"
    if nxt["waits_on"] == "owner":
        return f"NOTHING: waiting on the owner for {result['period']}: {nxt['why']}"
    if nxt["step"] == "done" or result["phase_done"]:
        return f"NOTHING: the {result['phase']} phase for {result['period']} is done"
    allowed = AGENT_STEPS.get(result["phase"])
    if allowed and nxt["step"] not in allowed:
        if result["phase"] == "assemble" and nxt["step"] in AGENT_STEPS["collect"]:
            return f"NOTHING: the week {result['period']} is not collected and asked yet"
        return f"NOTHING: {nxt['step']} is not this phase's work ({nxt['why']})"
    return f"WORK: {nxt['step']} for {result['period']}: {nxt['why']}"


def main():
    parser = argparse.ArgumentParser(description="Whether the week's leadership report is done, test by test.")
    parser.add_argument("store", nargs="?", default="", help="the author's store; $REPORT_STORE_DIR without it")
    parser.add_argument("--period", default="", help="the period end; this week's Friday without it")
    parser.add_argument("--phase", default="", help="collect, assemble or auto (the default)")
    parser.add_argument("--report-folder", default="", help="where the rendered Word and PDF files go")
    parser.add_argument("--as-of", default="", help="judge as of this YYYY-MM-DD; today without it")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    args = parser.parse_args()
    phase = args.phase.strip().casefold() or "auto"
    if phase not in PHASES:
        raise Fail(f"--phase {phase!r} is not collect, assemble or auto")
    try:
        today = date.fromisoformat(args.as_of) if args.as_of.strip() else date.today()
    except ValueError:
        raise Fail(f"--as-of {args.as_of!r} is not YYYY-MM-DD") from None
    folder = Path(args.report_folder).expanduser() if args.report_folder.strip() else None
    result = check(store_dir(args.store, must_exist=True), resolve_period(args.period, today), phase, folder, today)
    if args.precheck:
        print(precheck_line(result))
    elif args.format == "json":
        print(json.dumps(result, indent=1, default=str))
    else:
        print("\n".join([f"report-weekly-check {result['scope']} {result['period']} ({result['phase']})",
                         f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met); "
                         f"this phase {'done' if result['phase_done'] else 'not done'}",
                         f"Next: {result['next']['step']} (waits on {result['next']['waits_on']}): {result['next']['why']}"]
                        + [line for n, (name, t) in enumerate(result["tests"].items(), 1)
                           for line in [f"{n} {name}: {'MET' if t['met'] else 'NOT MET'}"] + [f"  - {g}" for g in t["gaps"]]]
                        + ([f"Earlier weeks to keep: {', '.join(result['earlier'])}"] if result["earlier"] else [])))
    return OK


if __name__ == "__main__":
    run_main(main)
