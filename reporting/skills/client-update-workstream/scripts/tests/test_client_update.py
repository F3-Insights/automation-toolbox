"""client_update_check.py and client_update_record.py against an invented engagement with
Acme Components: a Context, deck or memo rules, an updates folder with last week's update, a
week packed by hand, and a week recorded through to done."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
# Loaded under its own name, so this skill's tests can run beside another skill's _common.
_spec = importlib.util.spec_from_file_location("client_update_common", SCRIPTS / "_common.py")
cu = sys.modules["client_update_common"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cu)

NAME = "acme-weekly-update"
WEEK = "2026-W40"
DATE = "2026-10-02"

DECK_RULES = {
    "Variant": "deck", "Update day": "Friday", "Week folder": "decks/{date}",
    "Draft file": "{date} Acme Weekly Update - draft.html", "Review note": "{date} review-notes.md",
    "Previous updates": "decks/*/*.html, Acme Update *.html", "Banned phrases": "bad data; padding",
    "Slot minutes": "30",
}
MEMO_RULES = {
    "Variant": "memo", "Update day": "Friday", "Week folder": "Drafts/{date}",
    "Draft file": "Acme Status Update {date} DRAFT.md", "Review note": "{date} review-notes.md",
    "Cover email": "Acme Email {date} DRAFT.md", "Previous updates": "Acme Status Update *.md",
}

DECK_HTML = """<!doctype html><html><head><style>.slide{{}}</style>
<script>var x = [1, 2]; // {{not visible}}</script></head><body>
<section class="slide title">
<h1>Acme Components weekly update</h1>
<p>The pricing model was rebuilt this week.</p>
<!-- Source: C1 S001 S003 -->
<aside class="notes">1:30 Open with the pricing model.</aside>
</section>
<section class="slide">
<p>Two of three plants now report daily.</p>
<!-- source: C2 S004 -->
<div class="notes">2:00 Walk the plant list.{extra}</div>
</section>
</body></html>
"""

MEMO_MD = """# Acme Components status update

The pricing model was rebuilt this week. <!-- Source: C1 S001 -->

Two of three plants now report daily. <!-- Source: C2 S002 -->
"""

CONFIRMATIONS = "# Confirmations\n\n## CR-0123456789\n\n- Question: Is the update ready?\n- Asked of: the owner\n"


def put(path: Path, text="acme", day=None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if day:
        when = datetime.fromisoformat(f"{day}T12:00:00").timestamp()
        os.utime(path, (when, when))
    return path


def acme(tmp: Path, variant="deck", previous=True) -> dict:
    """An Acme engagement: a Context, its rules, an updates folder, and owner settings naming the Contexts."""
    fields = dict(DECK_RULES if variant == "deck" else MEMO_RULES)
    rules = tmp / "rules"
    put(rules / cu.RULES_MD, "\n".join(["# Acme Components update rules", "", "## Update inputs", ""]
                                       + [f"- {k}: {v}" for k, v in fields.items()]
                                       + ["", "## Something else", "", "- Variant: ignored", ""]))
    updates = tmp / "client" / "Weekly Update"
    updates.mkdir(parents=True)
    if previous:
        if variant == "deck":
            put(updates / "Acme Update 2026-09-25.html", "<section class='slide'>last week</section>", "2026-09-25")
        else:
            put(updates / "Acme Status Update 2026-09-25.md", "last week's memo", "2026-09-25")
    contexts = tmp / "contexts"
    contexts.mkdir()
    (contexts / f"{NAME}.yaml").write_text(json.dumps({"name": NAME, "sources": [
        {"name": "rules", "kind": "folder", "path": str(rules)},
        {"name": "updates", "kind": "folder", "path": str(updates)}]}), encoding="utf-8")
    settings = tmp / "settings.toml"
    settings.write_text(f'[client-update-workstream]\ncontexts_dir = "{contexts}"\n', encoding="utf-8")
    os.environ["F3I_TOOLBOX_SETTINGS"] = str(settings)
    return {"rules": rules, "updates": updates, "contexts": contexts, "week_dir": tmp / "week"}


@pytest.fixture(autouse=True)
def keep_env(monkeypatch, tmp_path):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "unset.toml"))


def week_of(paths) -> cu.Week:
    return cu.resolve(NAME, WEEK, None, str(paths["week_dir"]))


def pack_week(paths, n=4, carry=()):
    """A pack as client-update-pack writes it: sources with ids and halves, and the carry list."""
    sources = [{"id": f"S{i:03d}", "role": "transcript", "title": f"source {i}", "half": "ab"[i % 2],
                "path": f"source-{i}.txt"} for i in range(1, n + 1)]
    put(paths["week_dir"] / "work" / cu.SOURCES_JSON, json.dumps({"sources": sources, "carry": list(carry)}))
    return sources


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py"), *[str(a) for a in args]],
                          capture_output=True, text=True, env=os.environ.copy())


def record(paths, *args):
    return run("client_update_record", NAME, WEEK, *args, "--week-dir", paths["week_dir"], "--by", "acme-test")


def check_json(paths):
    res = run("client_update_check", NAME, WEEK, "--week-dir", paths["week_dir"], "--format", "json")
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def precheck(paths, *extra):
    res = run("client_update_check", NAME, WEEK, "--precheck", *extra)
    assert res.returncode == 0, res.stderr
    return res.stdout.splitlines()[0]


def done_week(tmp: Path, variant="deck") -> dict:
    """An Acme week that passes every test of done."""
    paths = acme(tmp, variant)
    cu.upsert_row(paths["updates"] / cu.UPDATES_LEDGER_CSV, cu.LEDGER_COLUMNS, "L-0000aaaa",
                  {"item": "Send the plant list", "owner": "the client's controller", "due": "2026-09-30",
                   "state": "open", "opened_week": "2026-W39"})
    pack_week(paths, carry=[{"id": "L-0000aaaa", "item": "Send the plant list"}])
    wk = week_of(paths)
    if variant == "deck":
        put(wk.draft, DECK_HTML.format(extra=""))
        c1, c2 = ["S001", "S003"], ["S004"]
    else:
        put(wk.draft, MEMO_MD)
        put(wk.docx, "docx bytes")
        put(wk.cover_email, "Dear client, the memo is attached.")
        c1, c2 = ["S001"], ["S002"]
    put(wk.review_note, "C2 needs the owner's word before it goes.")
    claims = {"claims": [{"id": "C1", "text": "The pricing model was rebuilt.", "sources": c1, "location": "slide 1"},
                         {"id": "C2", "text": "Two of three plants report daily.", "sources": c2, "location": "slide 2"}],
              "carry": [{"id": "L-0000aaaa", "state": "done", "text": "Send the plant list", "note": "sent"}],
              "next_steps": [{"text": "Agree the pricing review date", "owner": "the owner", "due": "2026-10-09"}]}
    put(tmp / "claims.json", json.dumps(claims))
    assert record(paths, "claims", "--from", tmp / "claims.json").returncode == 0
    put(tmp / "fa.json", json.dumps([{"claim": "C1", "verdict": "VERIFIED"}, {"claim": "C2", "verdict": "NOT IN MY SOURCES"}]))
    put(tmp / "fb.json", json.dumps([{"claim": "C1", "verdict": "NOT IN MY SOURCES"},
                                     {"claim": "C2", "verdict": "NOT IN MY SOURCES"}]))
    assert record(paths, "flag", "--claim", "C2", "--note", "the owner confirms").returncode == 0
    assert record(paths, "factcheck", "--checker", "a", "--from", tmp / "fa.json").returncode == 0
    assert record(paths, "factcheck", "--checker", "b", "--from", tmp / "fb.json").returncode == 0
    put(wk.work / "redteam.md", "Reads well.")
    assert record(paths, "review", "--kind", "redteam", "--state", "passed", "--file", wk.work / "redteam.md").returncode == 0
    put(wk.work / cu.CONFIRMATIONS_MD, CONFIRMATIONS)
    return paths


def rows(paths):
    return cu.read_rows(paths["week_dir"] / "work" / cu.EVIDENCE_CSV)


# --------------------------------------------------------------------------- check

def test_a_finished_deck_passes_every_test(tmp_path):
    paths = done_week(tmp_path)
    result = check_json(paths)
    want = {n: "pass" for n in result["tests"]}
    want["context"] = "na"
    assert {n: t["state"] for n, t in result["tests"].items()} == want, result["tests"]
    assert len(result["tests"]) == 9 and result["done"] is True and result["date"] == DATE
    assert "3.5 minutes" in result["tests"]["files"]["detail"][0]
    res = run("client_update_check", NAME, WEEK, "--week-dir", paths["week_dir"], "--precheck")
    assert res.stdout.splitlines()[0] == f"NOTHING: {NAME} {WEEK} is drafted and checked"
    text = run("client_update_check", NAME, "--week", WEEK, "--week-dir", paths["week_dir"]).stdout
    assert text.splitlines()[1].startswith("DONE") and "8 context: NA" in text


def test_deck_form_failures(tmp_path):
    paths = done_week(tmp_path)
    wk = week_of(paths)
    broken = DECK_HTML.format(extra=" [TBD] {{figure}}").replace("2:00 ", "")
    put(wk.draft, broken + '<section class="slide"><p>No notes here.</p></section>')
    text = "\n".join(check_json(paths)["tests"]["files"]["detail"])
    assert "without a notes block: 3" in text and "without an m:ss timing on slide(s): 2" in text
    assert "placeholder" in text and "[TBD]" in text
    put(wk.draft, DECK_HTML.format(extra="").replace("1:30", "29:30"))
    assert "over the 30-minute slot" in "\n".join(check_json(paths)["tests"]["files"]["detail"])


def test_claims_failures(tmp_path):
    paths = done_week(tmp_path)
    put(week_of(paths).draft, DECK_HTML.format(extra="").replace("C2 S004", "C9 S099"))
    detail = "\n".join(check_json(paths)["tests"]["claims"]["detail"])
    assert "claims in no Source comment: C2" in detail
    assert "claims with no row: C9" in detail and "not in the pack: S099" in detail


def test_factcheck_and_redteam_failures(tmp_path):
    paths = done_week(tmp_path)
    put(tmp_path / "fb2.json", json.dumps([{"claim": "C1", "verdict": "CONTRADICTED"}]))
    assert record(paths, "factcheck", "--checker", "b", "--from", tmp_path / "fb2.json").returncode == 0
    note = week_of(paths).work / "redteam.md"
    assert record(paths, "review", "--kind", "redteam", "--state", "failed", "--file", note,
                  "--note", "slide 2 overclaims").returncode == 0
    result = check_json(paths)
    assert "contradicted: C1" in result["tests"]["factcheck"]["detail"]
    assert "slide 2 overclaims" in result["tests"]["redteam"]["detail"][0]
    assert result["next"] == "factcheck"


def test_prose_hits_name_the_phrase_and_where(tmp_path):
    paths = done_week(tmp_path)
    wk = week_of(paths)
    put(wk.draft, DECK_HTML.format(extra=" We are on track\u2014the bad data is gone.").replace(
        "<!-- Source: C1", "<!-- leverage is fine inside a comment. Source: C1"))
    prose = check_json(paths)["tests"]["prose"]
    joined = "\n".join(prose["detail"])
    assert prose["state"] == "fail" and 'banned phrase "on track"' in joined and 'banned phrase "bad data"' in joined
    assert "U+2014" in joined and "leverage" not in joined and "not visible" not in joined
    assert all(line.startswith(wk.draft.name + ":") for line in prose["detail"])


def test_continuity_and_review(tmp_path):
    paths = done_week(tmp_path)
    claims = json.loads((tmp_path / "claims.json").read_text())
    claims["carry"][0]["state"] = "open"
    put(tmp_path / "claims2.json", json.dumps(claims))
    assert record(paths, "claims", "--from", tmp_path / "claims2.json").returncode == 0
    work = week_of(paths).work
    (work / cu.CONFIRMATIONS_MD).unlink()
    result = check_json(paths)
    assert result["tests"]["continuity"]["state"] == "fail" and "L-0000aaaa" in result["tests"]["continuity"]["detail"][1]
    assert result["tests"]["review"]["state"] == "fail" and "comms-confirm" in result["tests"]["review"]["detail"][0]


def test_a_finished_memo_passes_and_needs_its_word_file(tmp_path):
    paths = done_week(tmp_path, "memo")
    assert check_json(paths)["done"] is True
    wk = week_of(paths)
    put(wk.cover_email, "Dear client, we will circle back going forward.")
    prose = check_json(paths)["tests"]["prose"]
    assert any(wk.cover_email.name in line and "circle back" in line for line in prose["detail"])
    wk.docx.unlink()
    files = check_json(paths)["tests"]["files"]
    assert files["state"] == "fail" and any("Word file" in d for d in files["detail"])


def test_context_needs_a_proposed_revision(tmp_path):
    paths = done_week(tmp_path)
    wk = week_of(paths)
    pack = json.loads((wk.work / cu.SOURCES_JSON).read_text())
    pack["sources"].append({"id": "S099", "role": "context", "half": "a", "path": "ENGAGEMENT-CONTEXT.md"})
    put(wk.work / cu.SOURCES_JSON, json.dumps(pack))
    result = check_json(paths)
    assert result["tests"]["context"]["state"] == "fail" and result["next"] == "context"
    put(wk.work / cu.CONTEXT_PROPOSED_MD, "## Proposed file\n\n# Acme: engagement context\n")
    assert "numbered" in check_json(paths)["tests"]["context"]["why"]
    put(wk.work / cu.CONTEXT_PROPOSED_MD, "1. Deliverables: the pricing model is delivered.\n\n## Proposed file\n\n# Acme\n")
    assert check_json(paths)["done"] is True
    put(wk.work / cu.CONTEXT_PROPOSED_MD, "No changes proposed: nothing moves the context.")
    assert check_json(paths)["tests"]["context"]["state"] == "pass"


def test_precheck_lines(tmp_path):
    paths = acme(tmp_path)
    assert precheck(paths) == f"WORK: {NAME} {WEEK}: no draft yet for {DATE}"
    put(paths["updates"] / "Acme Update 2026-09-28.html", "<p>Monday steering deck</p>", "2026-09-28")
    assert precheck(paths) == f"WORK: {NAME} {WEEK}: no draft yet for {DATE}"
    put(paths["updates"] / "Acme Update 2026-10-01.html", "<p>done by hand</p>", "2026-10-01")
    assert precheck(paths) == (f"NOTHING: {NAME} {WEEK}: an update dated 2026-10-01 "
                               f"(Acme Update 2026-10-01.html) is already in the folder")


def test_precheck_names_the_first_failing_test(tmp_path):
    paths = done_week(tmp_path)
    (week_of(paths).work / cu.CONFIRMATIONS_MD).unlink()
    res = run("client_update_check", NAME, WEEK, "--week-dir", paths["week_dir"], "--precheck")
    assert res.stdout.splitlines()[0].startswith(f"WORK: {NAME} {WEEK}: review (no CONFIRMATIONS.md")
    assert res.stdout.splitlines()[1].startswith("  failing: review")


def test_blank_week_and_bad_arguments(tmp_path):
    acme(tmp_path)
    res = run("client_update_check", NAME, "--week=", "--as-of", "2026-09-29", "--format", "json")
    assert res.returncode == 0 and json.loads(res.stdout)["week"] == WEEK
    assert run("client_update_check").returncode == 2
    assert run("client_update_check", "nobody").returncode == 2
    assert run("client_update_check", NAME, "2026-W99").returncode == 2
    assert run("client_update_check", NAME, "--as-of", "someday").returncode == 2
    os.environ["F3I_TOOLBOX_SETTINGS"] = str(tmp_path / "none.toml")
    res = run("client_update_check", NAME)
    assert res.returncode == 2 and "contexts_dir" in res.stderr


# --------------------------------------------------------------------------- record

def setup(tmp_path):
    paths = acme(tmp_path)
    book = paths["updates"] / cu.UPDATES_LEDGER_CSV
    for lid, item in (("L-0000aaaa", "Send the plant list"), ("L-0000bbbb", "Book the plant visit"),
                      ("L-0000cccc", "Share the cost model")):
        cu.upsert_row(book, cu.LEDGER_COLUMNS, lid, {"item": item, "state": "open", "opened_week": "2026-W38"})
    pack_week(paths, n=3, carry=[{"id": i} for i in ("L-0000aaaa", "L-0000bbbb", "L-0000cccc")])
    return paths


def claims_file(tmp_path, name="claims.json", **override):
    data = {"claims": [{"id": "C1", "text": "The pricing model was rebuilt.", "sources": ["S001"], "location": "slide 1"},
                       {"id": "C2", "text": "Two plants report daily.", "sources": ["S003"], "location": "slide 2"},
                       {"id": "C3", "text": "The cost model is shared.", "sources": ["S001", "S003"]}],
            "carry": [{"id": "L-0000aaaa", "state": "done", "text": "Send the plant list", "note": "sent Tuesday"},
                      {"id": "L-0000bbbb", "state": "moved", "text": "Book the plant visit", "new_due": "2026-10-16"},
                      {"id": "L-0000cccc", "state": "open", "text": "Share the cost model"}],
            "next_steps": [{"text": "Agree the pricing review date.", "owner": "the owner", "due": "2026-10-09"}]}
    data.update(override)
    return put(tmp_path / name, json.dumps(data))


def test_claims_are_recorded_pending_with_carry(tmp_path):
    paths = setup(tmp_path)
    res = record(paths, "claims", "--from", claims_file(tmp_path))
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("RECORDED: 3 claims (3 new, 0 changed, 0 unchanged), 0 cut, 3 carry")
    got = rows(paths)
    assert got["claim:C1"]["state"] == "pending" and got["claim:C3"]["sources"] == "S001 S003"
    assert got["claim:C1"]["by"] == "acme-test" and got["carry:L-0000bbbb"]["state"] == "moved"
    header = (paths["week_dir"] / "work" / cu.EVIDENCE_CSV).read_text().splitlines()[0]
    assert header == ",".join(cu.EVIDENCE_COLUMNS)


def test_a_bad_claims_file_is_refused_whole(tmp_path):
    paths = setup(tmp_path)
    bad = claims_file(tmp_path, claims=[{"id": "C1", "text": "ok", "sources": ["S001"]},
                                        {"id": "C1", "text": "twice", "sources": ["S001"]},
                                        {"id": "claim 4", "text": "bad id", "sources": ["S001"]},
                                        {"id": "C5", "text": "unknown source", "sources": ["S999"]},
                                        {"id": "C6", "text": "no source", "sources": []}],
                      carry=[{"id": "L-ffffffff", "state": "finished"}])
    res = record(paths, "claims", "--from", bad)
    assert res.returncode == 1
    for words in ("C1 is used twice", "'claim 4' is not C", "source S999 is not in", "C6 names no source",
                  "'finished' is not one of", "L-ffffffff is not an open ledger item"):
        assert words in res.stderr, words
    assert not (paths["week_dir"] / "work" / cu.EVIDENCE_CSV).exists()


def test_a_changed_claim_is_pending_again_and_an_absent_one_is_cut(tmp_path):
    paths = setup(tmp_path)
    record(paths, "claims", "--from", claims_file(tmp_path))
    put(tmp_path / "fa.json", json.dumps([{"claim": "C1", "verdict": "VERIFIED"}, {"claim": "C2", "verdict": "verified"}]))
    assert record(paths, "factcheck", "--checker", "a", "--from", tmp_path / "fa.json").returncode == 0
    second = claims_file(tmp_path, "claims2.json", claims=[
        {"id": "C1", "text": "The pricing model was rebuilt.", "sources": ["S001"], "location": "slide 1"},
        {"id": "C2", "text": "Three plants report daily.", "sources": ["S003"], "location": "slide 2"}])
    res = record(paths, "claims", "--from", second)
    assert "(0 new, 1 changed, 1 unchanged), 1 cut" in res.stdout, res.stderr
    got = rows(paths)
    assert got["claim:C1"]["state"] == "verified" and got["claim:C1"]["review"] == "a:VERIFIED"
    assert got["claim:C2"]["state"] == "pending" and got["claim:C2"]["review"] == ""
    assert got["claim:C3"]["state"] == "cut"
    assert len(list((paths["week_dir"] / "work").glob("claims-*.json"))) == 1


def test_factcheck_states_follow_both_checkers(tmp_path):
    paths = setup(tmp_path)
    record(paths, "claims", "--from", claims_file(tmp_path))
    assert record(paths, "flag", "--claim", "C3", "--note", "the owner's figure").returncode == 0
    put(tmp_path / "fa.json", json.dumps([{"claim": "C1", "verdict": "NOT IN MY SOURCES"},
                                          {"claim": "C2", "verdict": "VERIFIED"},
                                          {"claim": "C3", "verdict": "NOT IN MY SOURCES"}]))
    assert record(paths, "factcheck", "--checker", "a", "--from", tmp_path / "fa.json").returncode == 0
    got = rows(paths)
    assert (got["claim:C1"]["state"], got["claim:C2"]["state"], got["claim:C3"]["state"]) == \
        ("pending", "verified", "flagged")
    assert got["review:factcheck-a"]["note"] == "S002"
    put(tmp_path / "fb.json", json.dumps([{"claim": "C1", "verdict": "NOT IN MY SOURCES"},
                                          {"claim": "C2", "verdict": "CONTRADICTED"},
                                          {"claim": "C3", "verdict": "NOT IN MY SOURCES"}]))
    assert record(paths, "factcheck", "--checker", "b", "--from", tmp_path / "fb.json").returncode == 0
    got = rows(paths)
    assert got["claim:C1"]["state"] == "unsupported"
    assert got["claim:C1"]["review"] == "a:NOT IN MY SOURCES | b:NOT IN MY SOURCES"
    assert got["claim:C2"]["state"] == "contradicted" and got["claim:C3"]["state"] == "flagged"


def test_factcheck_refuses_an_unknown_claim_or_verdict(tmp_path):
    paths = setup(tmp_path)
    record(paths, "claims", "--from", claims_file(tmp_path))
    put(tmp_path / "fa.json", json.dumps([{"claim": "C1", "verdict": "VERIFIED"}, {"claim": "C9", "verdict": "VERIFIED"},
                                          {"claim": "C2", "verdict": "PROBABLY"}]))
    res = record(paths, "factcheck", "--checker", "a", "--from", tmp_path / "fa.json")
    assert res.returncode == 1 and "no claim C9" in res.stderr and "'PROBABLY'" in res.stderr
    assert rows(paths)["claim:C1"]["state"] == "pending"
    assert record(paths, "factcheck", "--checker", "c", "--from", tmp_path / "fa.json").returncode == 2
    assert record(paths, "factcheck", "--checker", "a", "--from", tmp_path / "none.json").returncode == 2


def test_flag_cut_and_review(tmp_path):
    paths = setup(tmp_path)
    record(paths, "claims", "--from", claims_file(tmp_path))
    assert record(paths, "cut", "--claim", "C2", "--note", "not this week").returncode == 0
    assert record(paths, "flag", "--claim", "C7", "--note", "x").returncode == 1
    note = put(tmp_path / "redteam.md", "Fine.")
    assert record(paths, "review", "--kind", "redteam", "--state", "passed", "--file", note).returncode == 0
    assert record(paths, "review", "--kind", "unslop", "--state", "failed", "--file", note,
                  "--note", "two hedges").returncode == 0
    assert record(paths, "review", "--kind", "redteam", "--state", "passed", "--file",
                  tmp_path / "missing.md").returncode == 2
    got = rows(paths)
    assert got["claim:C2"]["state"] == "cut" and got["claim:C2"]["note"] == "not this week"
    assert got["review:redteam"]["state"] == "passed" and got["review:unslop"]["note"] == "two hedges"


def test_ledger_carries_the_week_and_refuses_when_contradicted(tmp_path):
    paths = setup(tmp_path)
    record(paths, "claims", "--from", claims_file(tmp_path))
    res = record(paths, "ledger")
    assert "1 closed, 1 moved, 1 kept open, 1 opened" in res.stdout, res.stderr
    book = cu.read_rows(paths["updates"] / cu.UPDATES_LEDGER_CSV)
    assert book["L-0000aaaa"]["state"] == "done" and book["L-0000aaaa"]["last_week"] == WEEK
    assert book["L-0000bbbb"]["state"] == "open" and book["L-0000bbbb"]["due"] == "2026-10-16"
    new = [r for k, r in book.items() if k not in ("L-0000aaaa", "L-0000bbbb", "L-0000cccc")]
    assert len(new) == 1 and new[0]["owner"] == "the owner" and new[0]["id"].startswith("L-")
    assert "0 opened" in record(paths, "ledger").stdout
    elsewhere = tmp_path / "run" / "UPDATES-LEDGER.csv"
    assert record(paths, "ledger", "--ledger", elsewhere).returncode == 0 and elsewhere.is_file()
    put(tmp_path / "fb.json", json.dumps([{"claim": "C1", "verdict": "CONTRADICTED"}]))
    record(paths, "factcheck", "--checker", "b", "--from", tmp_path / "fb.json")
    res = record(paths, "ledger")
    assert res.returncode == 1 and "claim:C1" in res.stderr


def test_show_and_options_before_the_engagement(tmp_path):
    paths = setup(tmp_path)
    record(paths, "claims", "--from", claims_file(tmp_path))
    res = run("client_update_record", NAME, WEEK, "show", "--format", "json", "--week-dir", paths["week_dir"])
    assert {r["id"] for r in json.loads(res.stdout)["rows"]} >= {"claim:C1", "claim:C3", "carry:L-0000aaaa"}
    text = run("client_update_record", "--week-dir", paths["week_dir"], "--as-of", "2026-09-30", NAME, "", "show")
    assert text.returncode == 0 and "claim:C1  pending" in text.stdout


def test_a_missing_pack_is_exit_2(tmp_path):
    paths = acme(tmp_path)
    res = record(paths, "claims", "--from", claims_file(tmp_path))
    assert res.returncode == 2 and cu.SOURCES_JSON in res.stderr


def test_render_makes_the_memos_word_file_without_source_comments(tmp_path):
    if not shutil.which("pandoc"):
        pytest.skip("pandoc is not installed")
    paths = acme(tmp_path, "memo")
    wk = week_of(paths)
    put(wk.draft, "# Acme status\n\nThe pricing model was rebuilt.\n<!-- Source: C1 S001 -->\n")
    res = record(paths, "render")
    assert res.stdout.startswith("RENDERED:"), res.stderr
    body = zipfile.ZipFile(wk.docx).read("word/document.xml").decode()
    assert "pricing model was rebuilt" in body and "Source:" not in body
    assert record(paths, "render").stdout.startswith("ALREADY:")
    put(wk.draft, "# Acme status\n\nThe pricing model was rebuilt twice.\n")
    third = record(paths, "render")
    assert third.stdout.startswith("RENDERED:") and "kept the earlier file" in third.stdout
    assert len(list(wk.work.glob("superseded-*/*.docx"))) == 1


def test_render_refuses_a_deck(tmp_path):
    paths = setup(tmp_path)
    assert record(paths, "render").returncode == 2
