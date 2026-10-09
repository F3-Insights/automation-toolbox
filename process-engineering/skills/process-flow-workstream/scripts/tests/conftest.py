"""A made-up engagement, Northwind Traders' order-to-delivery process, shared by the process-flow
script tests: a Context, a working folder with its rules file, transcripts (one recorded twice,
as text and as subtitles), a background document and a delivery folder."""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import _common as C  # noqa: E402
import claim_ledger as cl  # noqa: E402
import process_flow_prepare as prep  # noqa: E402
import process_flow_render as rnd  # noqa: E402

RULES = """# Process flow rules: Northwind Traders

- Default process: order-to-delivery
- Scope: as-is-and-to-be
- Audience: the Northwind operations committee
- Client: Northwind Traders
- Transcript files: *interview*, *.srt
- Reference model: order-to-cash
- Red team bar: B
- Screenshot: no
"""

DESK = """[0:01] Interviewer: How does an order come in?
[0:02] Order desk lead: Orders arrive by fax and I key each one into the ledger by hand.
[0:04] Order desk lead: Keying a large order takes most of an afternoon.
[0:07] Order desk lead: The delivery schedule is a whiteboard in the warehouse, nobody upstairs can see it.
[0:10] Order desk lead: I wish orders came straight from the customer portal.
"""

BILLING = """[0:01] Interviewer: When do you bill?
[0:02] Billing clerk: We bill from the ledger after the driver returns the signed delivery note.
[0:05] Billing clerk: Bills go out a week late because the delivery notes sit in the truck.
"""

BILLING_SRT = """1
00:00:01,000 --> 00:00:02,000
Interviewer: When do you bill?

2
00:00:02,000 --> 00:00:05,000
Billing clerk: We bill from the ledger after the driver returns the signed delivery note.

3
00:00:05,000 --> 00:00:08,000
Billing clerk: Bills go out a week late because the delivery notes sit in the truck.
"""

MEMO = "# Northwind company memo\n\nNorthwind sells kitchen supplies to restaurants on net 15 terms.\n"


def inventory(sid, claims, pains=()):
    block = {"source": sid,
             "claims": [{"n": i, "topic": "orders", "claim": c, "speaker": "lead", "quote": q, "location": loc, "leading": "no"}
                        for i, (c, q, loc) in enumerate(claims, 1)],
             "pains": [{"n": i, "pain": c, "speaker": "lead", "quote": q, "location": loc}
                       for i, (c, q, loc) in enumerate(pains, 1)],
             "wishes": [], "numbers": [], "contradictions": []}
    return f"Source {sid}\n\n```json\n{json.dumps(block)}\n```\n"


def write_toml(path, text):
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def nw(tmp_path, monkeypatch):
    names = ("ctx", "working", "transcripts", "background", "delivery", "models")
    ctx, working, trans, back, deliv, models = (tmp_path / n for n in names)
    for d in (ctx, working, trans, back, deliv, models):
        d.mkdir()
    (working / C.RULES_FILE).write_text(RULES, encoding="utf-8")
    (working / C.BACKGROUND_FILE).write_text("# Northwind\n\nRoles: order desk lead, billing clerk.\n")
    (trans / "order desk interview.txt").write_text(DESK, encoding="utf-8")
    (trans / "billing interview.txt").write_text(BILLING, encoding="utf-8")
    (trans / "billing.srt").write_text(BILLING_SRT, encoding="utf-8")
    (trans / "~$lock interview.txt").write_text("lock", encoding="utf-8")
    (back / "company memo.md").write_text(MEMO, encoding="utf-8")
    (models / "order-to-cash.md").write_text("# Order to cash\n\n- Credit check\n- Returns\n")
    context = {"name": "northwind-o2d", "sources": [
        {"name": "engagement", "kind": "folder", "path": str(working)},
        {"name": "transcripts", "kind": "folder", "path": str(trans)},
        {"name": "background", "kind": "folder", "path": str(back)},
        {"name": "delivery", "kind": "folder", "path": str(deliv)}]}
    (ctx / "northwind-o2d.yaml").write_text(json.dumps(context), encoding="utf-8")  # JSON is valid YAML
    settings = tmp_path / "settings.toml"
    write_toml(settings, f'contexts_dir = "{ctx}"\n\n[process-flow-workstream]\nreference_models_dir = "{models}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    return {"root": tmp_path, "ctx": ctx, "working": working, "transcripts": trans, "background": back,
            "delivery": deliv, "models": models, "settings": settings}


def run(main, *args, capsys):
    code = main([str(a) for a in args])
    out = capsys.readouterr()
    return code, out.out + out.err


def stage(nw, capsys, name="run1"):
    out = nw["root"] / name / "work"
    code, text = run(prep.main, "northwind-o2d", "--process=", "--scope=", "--audience=", "--out", out, capsys=capsys)
    assert code == 0, text
    assert text.startswith("FRESH northwind-o2d/order-to-delivery:")
    return out


def ids(work):
    return {e["name"]: e for e in json.loads((work / C.SOURCES_FILE).read_text())["sources"]}


def write_inventories(work):
    s = ids(work)
    desk, bill = s["order desk interview.txt"]["id"], s["billing interview.txt"]["id"]
    (work / "inventories").mkdir(exist_ok=True)
    (work / "inventories" / f"{desk}.md").write_text(inventory(desk, [
        ("Orders arrive by fax and are keyed by hand", "Orders arrive by fax and I key each one into the ledger by hand", "0:02"),
        ("The delivery schedule is a whiteboard", "The delivery schedule is a whiteboard in the warehouse", "0:07")],
        pains=[("Keying a large order takes an afternoon", "Keying a large order takes most of an afternoon", "0:04"),
               ("Nobody upstairs sees the schedule", "nobody upstairs can see it", "0:07")]))
    (work / "inventories" / f"{bill}.md").write_text(inventory(bill, [
        ("Billing waits for the signed delivery note", "We bill from the ledger after the driver returns the signed delivery note", "0:02")],
        pains=[("Bills go out a week late", "Bills go out a week late because the delivery notes sit in the truck", "0:05")]))
    return desk, bill


def a_map(desk, bill, version=1):
    return {"schema": C.SCHEMA, "version": version, "process": "order-to-delivery", "title": "Order to delivery",
            "client": "Northwind Traders", "date": "October 2026", "audience": "the operations committee",
            "scope": "as-is-and-to-be", "proposed_system": "PORTAL",
            "lanes": [{"id": "CUST", "label": "Customer", "external": True}, {"id": "DESK", "label": "Order desk"},
                      {"id": "BILL", "label": "Billing"}],
            "abbreviations": {"POD": "proof of delivery"},
            "changes": [] if version == 1 else ["v2: shorter titles (red team)"],
            "sections": [{
                "num": "01", "title": "Order to delivery", "headline": "Orders are keyed by hand today.",
                "narrative": "The order desk keys faxed orders; billing waits for paper delivery notes.",
                "delta": {"today": "orders keyed from fax", "proposed": "orders arrive from the portal",
                          "claims": [f"{desk}-P1"]},
                "asis": {"caption": "From fax to bill.",
                         "nodes": [
                             {"id": "a1", "lane": "DESK", "col": 0, "kind": "step", "title": "Key faxed order",
                              "systems": ["LEDGER"], "badge": "PAIN", "note": 1, "claims": [f"{desk}-C1"]},
                             {"id": "a2", "lane": "DESK", "col": 1, "kind": "store", "title": "Delivery whiteboard",
                              "badge": "PAIN", "note": 2, "claims": [f"{desk}-C2"]},
                             {"id": "a3", "lane": "CUST", "col": 2, "kind": "doc", "title": "Signed delivery note",
                              "claims": [f"{bill}-C1"]},
                             {"id": "a4", "lane": "BILL", "col": 3, "kind": "step", "title": "Bill customer",
                              "badge": "DELAY", "claims": [f"{bill}-C1"]}],
                         "edges": [{"from": "a1", "to": "a2"}, {"from": "a2", "to": "a3"}, {"from": "a3", "to": "a4"}],
                         "callouts": [{"n": 1, "type": "pain", "text": "A large order takes an afternoon (estimate).",
                                       "claims": [f"{desk}-P1"]},
                                      {"n": 2, "type": "pain", "text": "Nobody upstairs sees the schedule.",
                                       "claims": [f"{desk}-P2"]}]},
                "tobe": {"caption": "Orders from the portal; delivery confirmed on the spot.",
                         "nodes": [
                             {"id": "t1", "lane": "DESK", "col": 0, "kind": "step", "title": "Review portal order",
                              "systems": ["PORTAL"], "badge": "NEW", "note": 1, "replaces": ["a1"],
                              "answers": [f"{desk}-P1"], "why": "Removes the hand keying the desk lead named."},
                             {"id": "t2", "lane": "CUST", "col": 1, "kind": "doc", "title": "Signed delivery note",
                              "same_as": "a3"},
                             {"id": "t3", "lane": "BILL", "col": 2, "kind": "step", "title": "Bill on delivery",
                              "badge": "TBD", "answers": [f"{bill}-P1"], "why": "Billing hears of delivery at once."}],
                         "edges": [{"from": "t1", "to": "t2"}, {"from": "t2", "to": "t3"}],
                         "callouts": [{"n": 1, "type": "new", "text": "Orders taken in the customer portal."}]},
                "removed": [{"node": "a2", "answers": [f"{desk}-P2"], "why": "The schedule lives in the portal."}]}]}


def write_map(work, m):
    (work / "maps").mkdir(exist_ok=True)
    (work / "maps" / f"map v{m['version']}.json").write_text(json.dumps(m), encoding="utf-8")


def fact_return(work, half, verdict="VERIFIED"):
    items = json.loads(next((work / "reviews").glob("assertions v*.json")).read_text())["assertions"]
    half_ids = [s["id"] for s in cl.halves(work)[half]]
    verdicts = []
    for a in items:
        src = a["claims"][0]["source"] if a["claims"] else None
        if src in half_ids:
            verdicts.append({"key": a["key"], "verdict": verdict, "source": src,
                             "quote": a["claims"][0]["quote"], "location": a["claims"][0]["location"]})
        else:
            verdicts.append({"key": a["key"], "verdict": "NOT IN MY SOURCES"})
    p = work / "returns" / f"factcheck-{half}.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text("Summary.\n\n```json\n" + json.dumps({"half": half, "verdicts": verdicts, "omissions": [
        {"fact": "Terms are net 15", "source": half_ids[0], "location": "line 3", "quote": "net 15 terms"}]}) + "\n```\n")
    return p


def run_reviews(work, capsys, grade="A-"):
    assert run(cl.main, "brief", work, capsys=capsys)[0] == 0
    for half in ("A", "B"):
        code, text = run(cl.main, "record", work, "--kind", f"factcheck-{half}", "--from", fact_return(work, half),
                         capsys=capsys)
        assert code == 0, text
    desk = ids(work)["order desk interview.txt"]["id"]
    comp = work / "returns" / "completeness.md"
    comp.write_text("```json\n" + json.dumps({"model": "order-to-cash", "questions": [
        {"n": 1, "priority": "high", "question": "How are credit limits checked?", "why": "No credit step",
         "who": "the order desk lead", "answered_by": None},
        {"n": 2, "priority": "low", "question": "How do orders arrive?", "why": "Intake channel",
         "answered_by": {"source": desk, "location": "0:02", "quote": "Orders arrive by fax"}}]}) + "\n```")
    assert run(cl.main, "record", work, "--kind", "completeness", "--from", comp, capsys=capsys)[0] == 0
    red = work / "returns" / "redteam.md"
    red.write_text("```json\n" + json.dumps({"overall": grade, "one_change": "Fewer words",
                                             "sections": [{"num": "01", "grade": grade,
                                                           "criticisms": [{"text": "Long caption", "fix": "Trim it"}]}]}) + "\n```")
    assert run(cl.main, "record", work, "--kind", "redteam", "--from", red, capsys=capsys)[0] == 0
    code, text = run(cl.main, "memo", work, "--format", "json", capsys=capsys)
    assert code == 0, text
    return json.loads(text)


def drafted(nw, capsys, name="run1"):
    """A staged folder carried through ledger, map v1, render and reviews."""
    work = stage(nw, capsys, name)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    assert run(rnd.main, work, "--no-shot", capsys=capsys)[0] == 0
    run_reviews(work, capsys)
    return work
