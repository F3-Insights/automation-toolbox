"""A fake Insights Portal served over HTTP on 127.0.0.1, so the scripts run through their real
client. All data is invented: the owner works with Dana Whitfield of Acme Components. Dates
are relative to the real clock, because outbound-check runs at the current time."""

import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import _common as c

NOW = datetime.now(timezone.utc)
SKILLS = Path(__file__).resolve().parents[3]
FORBIDDEN = {"send_agent_message", "teams_post", "draft_create", "draft_update", "draft_delete",
             "draft_transition"}


def ago(days=0, hours=0):
    return (NOW - timedelta(days=days, hours=hours)).isoformat()


class FakePortal:
    def __init__(self):
        self.calls = []
        self.inboxes = [
            {"id": "ib-o", "address": "owner@owner.test", "provider": "outlook_oauth", "kind": "owned", "is_active": True},
            {"id": "ib-g", "address": "owner@gmail.test", "provider": "gmail_oauth", "kind": "owned", "is_active": True},
        ]
        self.contacts = {
            "c-dana": {"name": "Dana Whitfield", "emails": ["dana@acme.test"], "company": "Acme Components"},
            "c-near": {"name": "Dana Whitfieldson", "emails": ["dw@northwind.test"], "company": None},
            "c-sam1": {"name": "Sam Ortiz", "emails": ["sam@one.test"], "company": None},
            "c-sam2": {"name": "Sam Ortiz", "emails": ["sam@two.test"], "company": None},
            "c-quiet": {"name": "Priya Quiet", "emails": ["priya@lakeview.test"], "company": None},
        }
        self.emails = {
            "m1": {"thread": "T1", "direction": "sent", "from_address": "owner@owner.test",
                   "to_addresses": ["dana@acme.test"], "received_at": ago(20), "subject": "Kickoff",
                   "contact_id": None, "body": "Hi Dana, good to meet. Cheers"},
            "m2": {"thread": "T1", "direction": "received", "from_address": "dana@acme.test",
                   "to_addresses": ["owner@owner.test"], "received_at": ago(10), "subject": "Re: Kickoff",
                   "contact_id": "c-dana", "body": "Thanks, the numbers look right."},
            "m3": {"thread": "T1", "direction": "received", "from_address": "Dana <dana@acme.test>",
                   "to_addresses": ["owner@owner.test"], "received_at": ago(1), "subject": "Re: Kickoff",
                   "contact_id": "c-dana",
                   "body": "Can we meet next week to go over the proposal?\n\nOn Tue the owner wrote:\n> old"},
            "m4": {"thread": "T2", "direction": "received", "from_address": "jordan@fabrikam.test",
                   "to_addresses": ["owner@owner.test"], "cc_addresses": ["dana@acme.test"],
                   "received_at": ago(0, 2), "subject": "FYI", "contact_id": None, "body": "cc only"},
        }
        self.drafts = {}
        self.tasks = [{"id": "t1", "title": "Send the proposal", "status": "WAITING", "priority": "P2",
                       "project_id": "p1", "project_name": "Acme rollout", "related": "c-dana"}]
        start = (NOW + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
        self.events = [{"id": "ev1", "_ref": "portal://calendar_event/ev1", "title": "Board", "is_all_day": False,
                        "event_kind": "meeting", "start_time": start.isoformat(),
                        "end_time": (start + timedelta(hours=1)).isoformat()}]

    def who_has(self, address):
        return next((cid for cid, x in self.contacts.items() if address.lower() in x["emails"]), "")

    def contact_payload(self, cid):
        x = self.contacts[cid]
        return {"contact": {"id": cid, "full_name": x["name"], "title": "CFO", "is_active": True},
                "emails": [{"address": a} for a in x["emails"]], "primary_email": x["emails"][0],
                "company": {"id": "co1", "name": x["company"]} if x["company"] else None,
                "notes": [{"id": "n1", "title": "Met at a conference", "created_at": ago(30)}], "relationships": []}

    def email_row(self, eid):
        e = self.emails[eid]
        return {"id": eid, "_ref": f"portal://email/{eid}", "subject": e["subject"], "from_address": e["from_address"],
                "received_at": e["received_at"], "direction": e["direction"], "to_addresses": e.get("to_addresses"),
                "cc_addresses": e.get("cc_addresses"), "contact_id": e.get("contact_id"), "snippet": e["body"][:40]}

    def whoami(self, a):
        return {"principal": {"org_member_id": "mem-1", "contact_id": "c-owner", "primary_email": "owner@owner.test",
                              "timezone": "America/New_York"}, "inboxes": self.inboxes}

    def search(self, a):
        q = a["query"].lower()
        return {"contacts": [{"id": cid, "name": x["name"], "company_name": x["company"]}
                             for cid, x in self.contacts.items() if all(w in x["name"].lower() for w in q.split())]}

    def get(self, a):
        kind, key = a["entity_type"], a["id_or_query"]
        if kind == "contact":
            cid = key if key in self.contacts else self.who_has(key)
            return self.contact_payload(cid) if cid else {"error": f"no contact {key}"}
        if kind == "email":
            if key not in self.emails:
                return {"error": "Not found"}
            rows = sorted((self.email_row(i) for i, e in self.emails.items() if e["thread"] == self.emails[key]["thread"]),
                          key=lambda r: r["received_at"])
            sender = self.who_has(c.bare_address(self.emails[key]["from_address"]))
            return {"thread": rows, "thread_total": len(rows), "thread_truncated": False,
                    "sender": {"id": sender} if sender else None, "related_tasks": []}
        if kind == "draft":
            d = self.drafts.get(key)
            return dict(d, id=key) if d else {"error": "Not found"}
        if kind == "project":
            return {"project": {"id": key, "name": "Acme rollout", "status": "IN_PROGRESS"}}
        return {"error": "unsupported"}

    def list_entities(self, a):
        kind, f = a["entity_type"], a.get("filters") or {}
        if kind == "email":
            rows = []
            for eid, e in self.emails.items():
                if f.get("direction") and e["direction"] != f["direction"]:
                    continue
                if "contact_id" in f and e.get("contact_id") != f["contact_id"]:
                    continue
                if "participant_contact_id" in f:
                    people = [e["from_address"]] + (e.get("to_addresses") or []) + (e.get("cc_addresses") or [])
                    if f["participant_contact_id"] not in {self.who_has(c.bare_address(p)) for p in people}:
                        continue
                rows.append(self.email_row(eid))
            return {"items": sorted(rows, key=lambda r: r["received_at"], reverse=True), "has_more": False}
        if kind == "draft":
            return {"items": [{"id": k, "status": d["status"], "recipient_to": d["recipient_to"],
                               "thread_id": d.get("thread_id"), "subject": d["subject"], "created_at": d["created_at"]}
                              for k, d in self.drafts.items()], "has_more": False}
        if kind == "task":
            hits = [dict(t, _ref=f"portal://task/{t['id']}") for t in self.tasks
                    if "related_contact" in f and t["related"] == f["related_contact"]]
            return {"items": hits, "has_more": False}
        if kind == "calendar_event":
            return {"items": self.events, "total": len(self.events), "has_more": False}
        return {"items": [], "has_more": False}

    def email_bodies(self, a):
        return {"items": [{"id": i, "found": True, "body": self.emails[i]["body"]} if i in self.emails
                          else {"id": i, "found": False} for i in a["ids"]]}

    def draft_push(self, a):
        self.drafts[a["id"]].update(delivered_at=NOW.isoformat(), provider_draft_id="prov-1")
        return {"success": True, "id": a["id"], "web_link": "https://outlook.example.com/draft/1"}

    def draft_compose_url(self, a):
        return {"draft_id": a["id"], "url": "https://mail.example.com/compose?x=1"}

    def dispatch(self, name, args):
        self.calls.append((name, args))
        return getattr(self, name)(args)


def serve(fake, redirect=False):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            if redirect:
                self.send_response(307)
                self.send_header("Location", "http://127.0.0.1:9/elsewhere")
                self.end_headers()
                return
            assert self.headers.get("Authorization") == "Bearer test-token"
            params = req["params"]
            try:
                result = fake.dispatch(params["name"], params.get("arguments") or {})
                body = {"jsonrpc": "2.0", "id": req["id"], "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}
            except Exception as exc:
                body = {"jsonrpc": "2.0", "id": req["id"],
                        "result": {"isError": True, "content": [{"type": "text", "text": repr(exc)}]}}
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def point_settings_at(monkeypatch, tmp_path, port, token_env=True):
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": f"http://127.0.0.1:{port}/mcp", "headers": {"Authorization": "Bearer ${TEST_PORTAL_SECRET}"}}}}))
    settings = tmp_path / "settings.toml"
    settings.write_text(f'portal_mcp_config = "{config}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    if token_env:
        monkeypatch.setenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "test-token")
    return config


@pytest.fixture
def portal(monkeypatch, tmp_path):
    fake = FakePortal()
    httpd = serve(fake)
    point_settings_at(monkeypatch, tmp_path, httpd.server_address[1])
    # email_deliver.py runs outbound-check from the comms-draft-check skill beside this one.
    monkeypatch.setattr(c, "skill_script", lambda skill, name: SKILLS / skill / "scripts" / name)
    yield fake
    httpd.shutdown()
    httpd.server_close()
    names = {name for name, _ in fake.calls}
    assert not names & FORBIDDEN, f"a reply script called {names & FORBIDDEN}"


def run(module, capsys, *args):
    """Run a script's main() as the command line would; (exit code, parsed JSON)."""
    old = sys.argv
    sys.argv = [module.__name__, *[str(a) for a in args]]
    try:
        module.main()
        code = 0
    except SystemExit as exc:
        code = exc.code or 0
    finally:
        sys.argv = old
    out = capsys.readouterr().out
    try:
        return code, json.loads(out)
    except ValueError:
        raise AssertionError(f"not JSON (exit {code}): {out!r}")
