#!/usr/bin/env python3
"""report-weekly-gates: the weekly report's Gates 1 and 2 as one numbered list, and the answers.

    report_weekly_gates.py build WEEK_DIR [--due YYYY-MM-DD] [--rebuild] [--format text|json]
    report_weekly_gates.py apply WEEK_DIR (--answers FILE | --assumed) [--format text|json]

Run unattended, the gates cannot be asked live, so every question becomes one numbered line the
owner answers in one line per number, each with a default stated beside it. Gate 3 (approving
the draft) is not here.

build  reads the week folder's pack.json, verdicts.json and questions.json and writes gates.json
       (the list as data) and gates.md (as the owner reads it): the standing categories, the
       proposed additions, drops and folds, the catch-all candidates, the misfiled and left-out
       items, the carry-overs, the workers' questions, then the wins, the silences, the missing
       figures, the direct reports with no update, the table and the sequence question. It will
       not replace a list already built without --rebuild, and never once it has been asked (a
       "Weekly report gates" request in CONFIRMATIONS.md): exit 3.
apply  turns the answers into gate1.json (what report_organize.py --gate1 reads), the answered
       questions in questions.json, and owner-input.md (every answer verbatim, every default
       taken). The answers file:
           {"reply": "<verbatim>", "answered_on": "YYYY-MM-DD",
            "answers": {"1": "ok", "3": "yes", "9": "<the owner's words>"},
            "gate1_extra": {"categories": {"rename": [{"from": "A", "to": "B"}]}}}
       A proposal takes yes or no; a text question takes the owner's words. --assumed takes
       every default.

Exit 0 ok, 2 error, 3 refused.

Example:
  python3 report_weekly_gates.py build ~/reports/finance/work/2027-11-12 --due 2027-11-11
"""

import argparse
import json
from datetime import date
from pathlib import Path

from _common import (FAILED, GATES_QUESTION, OK, Fail, PERIOD, json_or_none, now_utc, request_for, run_main,
                     run_script, week_file, write_json, write_text)

YES = ("yes", "y", "add", "drop", "fold", "move", "strike", "pull", "include", "agree", "approve")


def one(text, limit=160):
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit - 3].rstrip() + "..."


def items(pack, verdicts, questions):
    """Every gate question, in the order the owner reads them, each with its default."""
    rows = []
    add = lambda gate, kind, ask, default, **data: rows.append(  # noqa: E731
        {"gate": gate, "kind": kind, "ask": ask, "default": default, "data": data})
    cats = pack.get("categories") or []
    catch_all = next((c for c in reversed(cats) if c.get("kind") == "other"), {}).get("name") or "the catch-all"
    add("gate1", "categories", "This week's report is about the standing categories, with the items each found: "
        + ", ".join(f"{c['name']} ({c['counts']['evidence']})" for c in cats) + ". Ok, or what changes?",
        "ok: the standing categories as the profile has them", names=[c["name"] for c in cats])
    block = pack.get("proposals") or {}
    for row in (block.get("add_category") or [])[:4]:
        add("gate1", "add", f"Add a category for the {row['kind']} '{row['key']}'? {one(row.get('reason'))}.",
            "no: not added", cluster=row)
    for row in block.get("drop_this_week") or []:
        add("gate1", "drop", f"Drop '{row['name']}' this week? {one(row.get('reason'))}.",
            "no: it stays, and the report says it was quiet", name=row["name"])
    for row in block.get("fold_into_other") or []:
        add("gate1", "fold", f"Fold '{row['name']}' into '{catch_all}' this week? {one(row.get('reason'))}.",
            "no: it keeps its own section", name=row["name"])
    for row in (block.get("other_topics_candidates") or [])[:6]:
        add("gate1", "other", f"Include '{one(row.get('title'), 90)}' ({row.get('kind')}, {one(row.get('detail'), 60)}) "
            f"in '{catch_all}'?", "no: left out of the report", ref=row.get("ref"))
    for row in verdicts.get("gate1_proposals") or []:
        add("gate1", "misfiled", one(row.get("ask"), 200), "no: it stays where the signals filed it",
            ref=row.get("ref"), action=row.get("action"), category=row.get("category"))
    for row in [r for r in verdicts.get("leave_out") or [] if r.get("ref")][:8]:
        add("gate1", "leave-out", f"Pull back '{one(row.get('item'), 90)}', which the leadership test left out "
            f"({one(row.get('why'), 90)})?", "no: left out", ref=row.get("ref"), category=row.get("category"))
    for c in cats:
        for carry in c.get("carry_overs") or []:
            add("gate1", "carry-over", f"Carried over from {carry.get('report_date') or 'an earlier report'} under "
                f"{c['name']}: '{one(carry.get('label'), 90)}'. Strike it, or say what happened?",
                "the report says what happened to it from this week's evidence", label=carry.get("label"),
                ledger_id=carry.get("ledger_id"))
    for row in questions.get("questions") or []:
        if not row.get("answered"):
            add("gate1", "question", one(row.get("question"), 240),
                "unanswered: the item it holds up stays out of the report as pending", question_id=str(row.get("id")))
    add("gate2", "wins", "What big wins from this week are missing from the list? For each one, the size or the effect.",
        "none added")
    silent = pack.get("silent") or {}
    fed = {c["name"] for c in cats if c.get("direct_report_input")}
    for name in silent.get("categories") or []:
        if name != catch_all and name not in fed:
            add("gate2", "silent", f"'{name}' produced no evidence this week. Any update?",
                "nothing to report this week", category=name)
    for name in silent.get("outline_projects") or []:
        add("gate2", "silent", f"The project '{name}' that the profile names had no activity. Any update?",
            "nothing to report this week", project=name)
    for goal in silent.get("goals") or []:
        add("gate2", "silent", f"The {goal.get('priority')} goal '{one(goal.get('title'), 90)}' was touched by nothing "
            f"this week. Any update?", "nothing to report this week", goal=goal.get("ref"))
    for c in cats:
        for metric in c.get("standing_metrics") or []:
            if metric.get("status") == "MISSING":
                add("gate2", "metric", f"The standing metric '{metric['name']}' ({c['name']}) has no figure. The "
                    f"figure, with its as-of date?", "not available this week", metric=metric["name"],
                    source=metric.get("source"))
    for who in (pack.get("direct_reports") or {}).get("missing") or []:
        add("gate2", "direct-report", f"No weekly update arrived from {who}. Anything from them to include?",
            "the report goes ahead without it", who=who)
    add("gate2", "table", "Any table to add this week? Paste it in the reply.", "no table")
    add("gate2", "sequence", "Does anything on the list reach another department before they have heard it directly?",
        "no")
    for number, row in enumerate(rows, 1):
        row["n"] = number
    return rows


def build(folder, due, rebuild):
    pack = json_or_none(week_file(folder, "pack"))
    if not isinstance(pack, dict):
        raise Fail(f"no pack at {week_file(folder, 'pack')}: run report_weekly_prepare.py first")
    target = week_file(folder, "gates")
    asked = request_for(week_file(folder, "confirmations"), GATES_QUESTION)
    if target.is_file() and asked:
        raise Fail(f"the gate questions are already out ({asked.get('Id')}); the owner's answers are numbered "
                   f"against them", FAILED)
    if target.is_file() and not rebuild:
        raise Fail(f"{target} exists; --rebuild replaces it while nothing has been asked", FAILED)
    rows = items(pack, json_or_none(week_file(folder, "verdicts")) or {}, json_or_none(week_file(folder, "questions")) or {})
    period = folder.name if PERIOD.match(folder.name) else str((pack.get("period") or {}).get("until"))[:10]
    weight = (pack.get("proposals") or {}).get("gate_weight") or "one line"
    by_gate = {g: len([r for r in rows if r["gate"] == g]) for g in ("gate1", "gate2")}
    write_json(target, {"schema": "report-weekly-gates/1", "period": period, "due": due or None, "built_at": now_utc(),
                        "gate_weight": weight, "count": len(rows), "by_gate": by_gate, "items": rows})
    text = [f"# Weekly report gates: the week ending {period}", "",
            f"Answer by {due or 'the assembly run'}, one line per number, for example \"1 ok, 3 yes, 9 closed the "
            f"credit line renewal two weeks early\". A number you do not answer takes the default beside it, and the "
            f"draft says which defaults were taken. Nothing is sent: the draft comes back to you to approve.", "",
            f"Gate weight this week: {weight}.", ""]
    for gate, title in (("gate1", "## This week's categories"), ("gate2", "## The silences, the figures, the table and the wins")):
        text += [title, ""] + [f"{r['n']}. {r['ask']} (No answer: {r['default']}.)" for r in rows if r["gate"] == gate] + [""]
    write_text(week_file(folder, "gates_md"), "\n".join(text))
    return {"action": "build", "gates": str(target), "gates_md": str(week_file(folder, "gates_md")), "count": len(rows),
            "by_gate": by_gate, "gate_weight": weight}


def apply(folder, answers_file, assumed):
    gates = json_or_none(week_file(folder, "gates"))
    if not isinstance(gates, dict):
        raise Fail(f"no gates at {week_file(folder, 'gates')}: build them first")
    if bool(answers_file) == bool(assumed):
        raise Fail("give exactly one of --answers FILE and --assumed")
    given = json_or_none(Path(answers_file).expanduser()) if answers_file else {}
    if answers_file and not (isinstance(given, dict) and isinstance(given.get("answers"), dict)):
        raise Fail(f"{answers_file}: not an answers file (an object with 'answers')")
    answers = {str(k).strip(): str(v or "").strip() for k, v in (given.get("answers") or {}).items()}
    stray = sorted(set(answers) - {str(r["n"]) for r in gates["items"]}, key=lambda s: (len(s), s))
    if stray:
        raise Fail(f"answers for numbers the gates do not have: {', '.join(stray)}")
    pack = json_or_none(week_file(folder, "pack")) or {}
    catch = next((c for c in reversed(pack.get("categories") or []) if c.get("kind") == "other"), {})
    gate1 = {"schema": "gate1-answers/1", "answered_on": str(given.get("answered_on") or date.today().isoformat())[:10],
             "permanent": False, "categories": {"add": [], "drop": [], "rename": [], "fold": []},
             "items": {"pull_back": [], "strike": [], "move": []}, "carry_overs": {"answer": [], "strike": []}, "notes": ""}
    lines, taken, answered, question_answers = {"gate1": [], "gate2": []}, [], [], []
    for row in gates["items"]:
        n, kind, data, answer = row["n"], row["kind"], row.get("data") or {}, answers.get(str(row["n"]), "")
        if not answer:
            taken.append(n)
            lines[row["gate"]].append(f"{n}. {row['ask']}\n   Default taken: {row['default']}.")
            continue
        answered.append(n)
        lines[row["gate"]].append(f"{n}. {row['ask']}\n   Answer: {answer}")
        words = answer.casefold().replace(",", " ").split()
        yes = bool(words) and words[0].rstrip(".:;!") in YES
        if kind == "add" and yes:
            cluster = data.get("cluster") or {}
            name = answer.split(None, 1)[1].strip() if words[0] == "add" and len(words) > 1 else cluster.get("key")
            signal = {"project": "projects", "counterparty": "counterparties"}.get(cluster.get("kind"), "keywords")
            gate1["categories"]["add"].append({"name": name, "seat": catch.get("seat"), "kind": "project",
                                               "covers": one(cluster.get("reason"), 200), "signals": {signal: [cluster.get("key")]}})
        elif kind == "drop" and yes:
            gate1["categories"]["drop"].append(data.get("name"))
        elif kind == "fold" and yes:
            gate1["categories"]["fold"].append({"from": data.get("name"), "into": catch.get("name") or "Other topics"})
        elif kind in ("other", "leave-out") and yes:
            gate1["items"]["pull_back"].append({"ref": data.get("ref")})
        elif kind == "misfiled" and yes:
            if data.get("action") == "strike":
                gate1["items"]["strike"].append(data.get("ref"))
            else:
                gate1["items"]["move"].append({"ref": data.get("ref"), "category": data.get("category")})
        elif kind == "carry-over" and answer.casefold().startswith(("strike", "drop", "closed")):
            gate1["carry_overs"]["strike"].append(data.get("label"))
        elif kind == "question":
            question_answers.append((data.get("question_id"), answer))
    extra = given.get("gate1_extra") or {}
    for block in ("categories", "items", "carry_overs"):
        for key, values in (extra.get(block) or {}).items():
            if isinstance(values, list) and key in gate1[block]:
                gate1[block][key] += values
    gate1["permanent"] = extra.get("permanent") is True
    due = gates.get("due") or "the assembly run"
    gate1["notes"] = (str(given.get("reply") or "").strip() if answers else
                      f"No answer to the gate questions by {due}: every default stated in gates.md was taken.")
    write_json(week_file(folder, "gate1"), gate1)
    for ident, text in question_answers:
        code, _, err = run_script("report_questions", ["answer", "--questions", week_file(folder, "questions"),
                                                       "--id", ident, "--answer", text])
        if code:
            raise Fail(f"report_questions.py answer --id {ident} failed: {err.strip()[:200]}")
    head = (f"The owner answered on {gate1['answered_on']}." if answered else
            f"The owner did not answer by {due}; every default below was taken, and the draft's covering note says so.")
    body = [f"# The owner's gate answers: the week ending {gates.get('period')}", "", head, ""]
    if given.get("reply"):
        body += ["The reply, verbatim:", "", "> " + str(given["reply"]).replace("\n", "\n> "), ""]
    body += ["## Gate 1", ""] + lines["gate1"] + ["", "## Gate 2", ""] + lines["gate2"] + [""]
    write_text(week_file(folder, "owner_input"), "\n".join(body))
    return {"action": "apply", "gate1": str(week_file(folder, "gate1")), "owner_input": str(week_file(folder, "owner_input")),
            "answered": answered, "defaults_taken": taken, "assumed": not answered,
            "questions_answered": [q for q, _ in question_answers],
            "effects": {b: {k: len(v) for k, v in gate1[b].items()} for b in ("categories", "items", "carry_overs")}}


def main():
    parser = argparse.ArgumentParser(description="The weekly report's gates as one numbered list.")
    sub = parser.add_subparsers(dest="action", required=True)
    build_cmd, apply_cmd = sub.add_parser("build"), sub.add_parser("apply")
    for one_cmd in (build_cmd, apply_cmd):
        one_cmd.add_argument("week_dir", help="the week folder, <store>/work/<period>")
        one_cmd.add_argument("--format", choices=("text", "json"), default="text")
    build_cmd.add_argument("--due", default="", help="when the answers are wanted, YYYY-MM-DD")
    build_cmd.add_argument("--rebuild", action="store_true")
    apply_cmd.add_argument("--answers", default="", help="the owner's answers, by number")
    apply_cmd.add_argument("--assumed", action="store_true", help="no answer came: take every default")
    args = parser.parse_args()
    folder = Path(args.week_dir).expanduser()
    if not folder.is_dir():
        raise Fail(f"WEEK_DIR must exist: {args.week_dir!r}")
    if args.action == "build":
        if args.due and not PERIOD.match(args.due):
            raise Fail(f"--due {args.due!r} is not YYYY-MM-DD")
        result = build(folder, args.due, args.rebuild)
        text = (f"BUILT: {result['count']} gate questions ({result['by_gate']['gate1']} at Gate 1, "
                f"{result['by_gate']['gate2']} at Gate 2), weight {result['gate_weight']}: {result['gates_md']}")
    else:
        result = apply(folder, args.answers.strip(), args.assumed)
        text = ("ASSUMED: every default taken" if result["assumed"] else
                f"APPLIED: {len(result['answered'])} answered, {len(result['defaults_taken'])} defaults taken") \
            + f"; {result['gate1']} and {result['owner_input']}"
    print(json.dumps(result, indent=1) if args.format == "json" else text)
    return OK


if __name__ == "__main__":
    run_main(main)
