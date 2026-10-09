#!/usr/bin/env python3
"""The decision store: a small SQLite database of the owner's decision cases and playbooks.

It holds four things. A source is one harvested artifact (a sent email, a recording, a
document). A case is one real decision the owner made, cited to at least one source. A
playbook is the draft or ratified rule set for one category of decision. A bullet is one
rule in a playbook, cited to at least one case or source. The store refuses a case or a
bullet with no citation, which is the point of it: no rule without evidence.

Inputs: a subcommand, and for the writes a JSON object or list given with --json or read
from a file with --file. The database is --db, else the setting `database` under
[decision-case-mining] in the owner settings file.

Output: JSON on stdout (the ids written, the counts, the audit) or, for export-playbook,
the playbook as Markdown. Exit 0 on success, 1 when the audit finds violations or a write
is refused, 2 when the database is not configured.

Subcommands:
  init               create the database
  add-source         upsert sources by (type, external_ref)
  add-case           add cases; each source is a source_id or an inline source to upsert
  add-playbook       add a draft playbook for one category
  add-bullet         add cited bullets to a playbook
  stats              counts, sources by type, cases by category
  cases              one category's cases with their sources (--category)
  sources            sources, optionally of one --type and one meta --category
  audit              the provenance check: uncited cases and bullets, missing raw files
  export-playbook    one category's playbook as reviewable Markdown with its citations

Example:
  python3 decision_store.py add-case --file RUN/cases/batch-1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tomllib
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

-- One row per harvested artifact; everything derived points back here.
CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY,
    type         TEXT NOT NULL CHECK (type IN ('email', 'recording', 'recording_frame', 'manual')),
    external_ref TEXT NOT NULL,      -- Portal email id, recording id or file path
    url          TEXT,               -- a pointer a person can open
    title        TEXT,
    content_hash TEXT,               -- sha256 of the raw artifact when harvested
    raw_path     TEXT,               -- the archived copy, absolute or relative to the database
    harvested_at TEXT NOT NULL DEFAULT (datetime('now')),
    meta         TEXT,               -- JSON: duration, classification, category and the like
    UNIQUE (type, external_ref)
);

-- One real decision. Cases are never edited after they are added.
CREATE TABLE IF NOT EXISTS cases (
    id                INTEGER PRIMARY KEY,
    category          TEXT,
    situation_summary TEXT NOT NULL,
    context_snapshot  TEXT,          -- JSON: what was known when the decision was made
    action_taken      TEXT NOT NULL,
    reasoning         TEXT,          -- the owner's own words, or NULL when none were given
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS case_sources (
    case_id   INTEGER NOT NULL REFERENCES cases(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    locator   TEXT NOT NULL DEFAULT '',   -- a message id in the thread, or t=seconds in a recording
    PRIMARY KEY (case_id, source_id, locator)
);

CREATE TABLE IF NOT EXISTS playbooks (
    id               INTEGER PRIMARY KEY,
    category         TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    -- emulate: the owner's behaviour is the standard; uphold: the owner's stated standard
    -- governs where behaviour falls short of it.
    stance           TEXT NOT NULL DEFAULT 'emulate' CHECK (stance IN ('emulate', 'uphold')),
    risk_tier        TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high', 'financial')),
    human_final_pass INTEGER NOT NULL DEFAULT 0,   -- 1: a person always makes the final move
    status           TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'retired')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A bullet's text is never edited; a new bullet supersedes it.
CREATE TABLE IF NOT EXISTS playbook_bullets (
    id            INTEGER PRIMARY KEY,
    playbook_id   INTEGER NOT NULL REFERENCES playbooks(id),
    kind          TEXT NOT NULL DEFAULT 'principle'
                  CHECK (kind IN ('policy-ref', 'principle', 'procedure', 'pitfall', 'escalation')),
    text          TEXT NOT NULL,
    valid_from    TEXT NOT NULL DEFAULT (datetime('now')),
    superseded_by INTEGER REFERENCES playbook_bullets(id)
);

CREATE TABLE IF NOT EXISTS bullet_sources (
    bullet_id INTEGER NOT NULL REFERENCES playbook_bullets(id),
    source_id INTEGER REFERENCES sources(id),
    case_id   INTEGER REFERENCES cases(id),
    locator   TEXT NOT NULL DEFAULT '',
    CHECK (source_id IS NOT NULL OR case_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_cases_category ON cases(category);
CREATE INDEX IF NOT EXISTS idx_bullets_playbook ON playbook_bullets(playbook_id);
"""

BULLET_KINDS = ("policy-ref", "principle", "procedure", "pitfall", "escalation")

SECTIONS = [
    ("policy-ref", "Policies: consult and link; no judgment needed where these apply"),
    ("principle", "Principles: the why, for when policy is silent or in tension"),
    ("procedure", "Procedures: the mechanics"),
    ("pitfall", "Pitfalls: where the principles above do not apply"),
    ("escalation", "Escalation triggers: stop and ask the owner, whatever the autonomy level"),
]


class Refused(Exception):
    """A write the store will not make; the message says why."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def db_path(flag: str | None) -> Path:
    value = flag or settings("decision-case-mining").get("database")
    if not value:
        print("decision_store: no database; set `database` under [decision-case-mining] "
              "in the owner settings, or pass --db", file=sys.stderr)
        sys.exit(2)
    return Path(value).expanduser()


def connect(path: Path, create: bool = False) -> sqlite3.Connection:
    if not create and not path.exists():
        raise Refused(f"no database at {path}; run `init` first")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def items(payload) -> list[dict]:
    return payload if isinstance(payload, list) else [payload]


def as_json(value):
    return json.dumps(value) if value else None


def upsert_source(conn, it: dict) -> int:
    # meta is merged key by key, so re-registering a source (a re-harvest) keeps the
    # classification and category set on it earlier.
    meta = it.get("meta")
    old = conn.execute("SELECT meta FROM sources WHERE type = ? AND external_ref = ?",
                       (it["type"], str(it["external_ref"]))).fetchone()
    if meta and old and old["meta"]:
        meta = {**json.loads(old["meta"]), **{k: v for k, v in meta.items() if v is not None}}
    row = conn.execute(
        """INSERT INTO sources (type, external_ref, url, title, content_hash, raw_path, meta)
           VALUES (:type, :external_ref, :url, :title, :content_hash, :raw_path, :meta)
           ON CONFLICT(type, external_ref) DO UPDATE SET
             url = COALESCE(excluded.url, url), title = COALESCE(excluded.title, title),
             content_hash = COALESCE(excluded.content_hash, content_hash),
             raw_path = COALESCE(excluded.raw_path, raw_path), meta = COALESCE(excluded.meta, meta)
           RETURNING id""",
        {"type": it["type"], "external_ref": str(it["external_ref"]), "url": it.get("url"),
         "title": it.get("title"), "content_hash": it.get("content_hash"),
         "raw_path": it.get("raw_path"), "meta": as_json(meta)},
    ).fetchone()
    return row["id"]


def add_sources(conn, payload) -> dict:
    return {"source_ids": [upsert_source(conn, it) for it in items(payload)]}


def add_cases(conn, payload) -> dict:
    """Every case needs a source. A source entry is either {"source_id": n} or an inline
    source ({"type", "external_ref", ...}) that is upserted first, so a miner's case file
    loads in one call."""
    ids = []
    for it in items(payload):
        cited = it.get("sources") or []
        if not cited:
            raise Refused(f"case has no source: {str(it.get('situation_summary', ''))[:80]}")
        for key in ("situation_summary", "action_taken"):
            if not it.get(key):
                raise Refused(f"case has no {key}")
        case_id = conn.execute(
            """INSERT INTO cases (category, situation_summary, context_snapshot, action_taken, reasoning)
               VALUES (?, ?, ?, ?, ?) RETURNING id""",
            (it.get("category"), it["situation_summary"], as_json(it.get("context_snapshot")),
             it["action_taken"], it.get("reasoning")),
        ).fetchone()["id"]
        for s in cited:
            source_id = s.get("source_id") or upsert_source(conn, s)
            conn.execute("INSERT OR IGNORE INTO case_sources (case_id, source_id, locator) VALUES (?, ?, ?)",
                         (case_id, source_id, s.get("locator", "")))
        ids.append(case_id)
    return {"case_ids": ids}


def add_playbook(conn, payload) -> dict:
    it = payload[0] if isinstance(payload, list) else payload
    row = conn.execute(
        """INSERT INTO playbooks (category, title, stance, risk_tier, human_final_pass, status)
           VALUES (?, ?, ?, ?, ?, ?) RETURNING id""",
        (it["category"], it["title"], it.get("stance", "emulate"), it["risk_tier"],
         int(bool(it.get("human_final_pass"))), it.get("status", "draft")),
    ).fetchone()
    return {"playbook_id": row["id"]}


def add_bullets(conn, payload) -> dict:
    ids = []
    for it in items(payload):
        refs = it.get("sources") or []
        if not refs:
            raise Refused(f"bullet has no source: {str(it.get('text', ''))[:80]}")
        kind = it.get("kind", "principle")
        if kind not in BULLET_KINDS:
            raise Refused(f"unknown bullet kind {kind!r}; use one of {', '.join(BULLET_KINDS)}")
        bullet_id = conn.execute(
            "INSERT INTO playbook_bullets (playbook_id, kind, text) VALUES (?, ?, ?) RETURNING id",
            (it["playbook_id"], kind, it["text"]),
        ).fetchone()["id"]
        for r in refs:
            if not (r.get("case_id") or r.get("source_id")):
                raise Refused("a bullet citation needs a case_id or a source_id")
            conn.execute(
                "INSERT INTO bullet_sources (bullet_id, source_id, case_id, locator) VALUES (?, ?, ?, ?)",
                (bullet_id, r.get("source_id"), r.get("case_id"), r.get("locator", "")))
        ids.append(bullet_id)
    return {"bullet_ids": ids}


def stats(conn) -> dict:
    out = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
           for t in ("sources", "cases", "playbooks", "playbook_bullets")}
    out["sources_by_type"] = {r["type"]: r["c"] for r in
                              conn.execute("SELECT type, COUNT(*) c FROM sources GROUP BY type")}
    out["cases_by_category"] = {r["category"] or "(unclassified)": r["c"] for r in
                                conn.execute("SELECT category, COUNT(*) c FROM cases GROUP BY category")}
    return out


def list_cases(conn, category: str) -> list[dict]:
    out = []
    for c in conn.execute("SELECT * FROM cases WHERE category = ? ORDER BY id", (category,)):
        case = dict(c)
        case["context_snapshot"] = json.loads(c["context_snapshot"]) if c["context_snapshot"] else None
        case["sources"] = [dict(r) for r in conn.execute(
            "SELECT s.id AS source_id, s.type, s.external_ref, s.title, s.url, cs.locator "
            "FROM case_sources cs JOIN sources s ON s.id = cs.source_id WHERE cs.case_id = ?", (c["id"],))]
        out.append(case)
    return out


def list_sources(conn, kind: str | None, category: str | None) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM sources WHERE ? IS NULL OR type = ? ORDER BY id", (kind, kind)):
        src = dict(r)
        src["meta"] = json.loads(r["meta"]) if r["meta"] else {}
        if category is None or src["meta"].get("category") == category:
            out.append(src)
    return out


def audit(conn, base: Path) -> dict:
    """Every case and bullet cited, every source findable, every archived copy present and hashed."""
    def ids(sql):
        return [r[0] for r in conn.execute(sql)]

    problems = {
        "uncited_cases": ids("SELECT c.id FROM cases c LEFT JOIN case_sources cs ON cs.case_id = c.id "
                             "WHERE cs.case_id IS NULL"),
        "uncited_bullets": ids("SELECT b.id FROM playbook_bullets b LEFT JOIN bullet_sources bs "
                               "ON bs.bullet_id = b.id WHERE bs.bullet_id IS NULL"),
        "sources_without_url_or_copy": ids("SELECT id FROM sources WHERE url IS NULL AND raw_path IS NULL"),
        "sources_copy_missing": [r["id"] for r in conn.execute(
            "SELECT id, raw_path FROM sources WHERE raw_path IS NOT NULL")
            if not (base / Path(r["raw_path"]).expanduser()).exists()],
        "sources_copy_unhashed": ids("SELECT id FROM sources WHERE raw_path IS NOT NULL AND content_hash IS NULL"),
    }
    return {"violations": sum(len(v) for v in problems.values()), **problems}


def export_playbook(conn, category: str) -> str:
    pb = conn.execute("SELECT * FROM playbooks WHERE category = ?", (category,)).fetchone()
    if not pb:
        raise Refused(f"no playbook for category {category!r}")
    head = (f"- Category: `{pb['category']}` | Risk tier: {pb['risk_tier']} | Stance: {pb['stance']}"
            f" | Status: {pb['status']}" + (" | A person makes the final move" if pb["human_final_pass"] else ""))
    lines = [f"# Playbook: {pb['title']}", "", head, ""]
    bullets = conn.execute("SELECT * FROM playbook_bullets WHERE playbook_id = ? AND superseded_by IS NULL "
                           "ORDER BY id", (pb["id"],)).fetchall()
    for kind, heading in SECTIONS:
        group = [b for b in bullets if b["kind"] == kind]
        if not group:
            continue
        lines += ["", f"## {heading}", ""]
        for b in group:
            cites = []
            for r in conn.execute("SELECT * FROM bullet_sources WHERE bullet_id = ?", (b["id"],)):
                if r["case_id"]:
                    cites.append(f"case:{r['case_id']}")
                    continue
                src = conn.execute("SELECT * FROM sources WHERE id = ?", (r["source_id"],)).fetchone()
                where = (src["url"] or src["raw_path"] or "") + (f"?{r['locator']}" if r["locator"] else "")
                cites.append(f"[{src['title'] or src['external_ref']}]({where})")
            lines.append(f"- {b['text']}  \n  Sources: {', '.join(cites)}")
    return "\n".join(lines) + "\n"


def read_payload(args):
    if args.json is not None:
        return json.loads(args.json)
    return json.loads(Path(args.file).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="the database file (default: [decision-case-mining] database)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "stats", "audit"):
        sub.add_parser(name)
    for name in ("add-source", "add-case", "add-playbook", "add-bullet"):
        sp = sub.add_parser(name)
        given = sp.add_mutually_exclusive_group(required=True)
        given.add_argument("--json", help="a JSON object or a list of them")
        given.add_argument("--file", help="a file holding that JSON")
    sp = sub.add_parser("export-playbook")
    sp.add_argument("--category", required=True)
    sp = sub.add_parser("cases")
    sp.add_argument("--category", required=True)
    sp = sub.add_parser("sources")
    sp.add_argument("--type", dest="kind", choices=["email", "recording", "recording_frame", "manual"])
    sp.add_argument("--category", help="only sources whose meta names this category")
    args = ap.parse_args(argv)

    path = db_path(args.db)
    try:
        if args.cmd == "init":
            conn = connect(path, create=True)
            conn.executescript(SCHEMA)
            conn.commit()
            print(json.dumps({"ok": True, "db": str(path)}))
            return 0
        conn = connect(path)
        if args.cmd == "export-playbook":
            print(export_playbook(conn, args.category), end="")
            return 0
        if args.cmd == "cases":
            print(json.dumps(list_cases(conn, args.category), indent=2))
            return 0
        if args.cmd == "sources":
            print(json.dumps(list_sources(conn, args.kind, args.category), indent=2))
            return 0
        if args.cmd == "stats":
            print(json.dumps(stats(conn), indent=2))
            return 0
        if args.cmd == "audit":
            result = audit(conn, path.parent)
            print(json.dumps(result, indent=2))
            return 1 if result["violations"] else 0
        writer = {"add-source": add_sources, "add-case": add_cases,
                  "add-playbook": add_playbook, "add-bullet": add_bullets}[args.cmd]
        try:
            result = writer(conn, read_payload(args))
        except Exception:
            conn.rollback()
            raise
        conn.commit()
        print(json.dumps(result))
        return 0
    except Refused as why:
        print(f"decision_store: refused: {why}", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError, OSError, json.JSONDecodeError, sqlite3.Error) as why:
        print(f"decision_store: {type(why).__name__}: {why}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
