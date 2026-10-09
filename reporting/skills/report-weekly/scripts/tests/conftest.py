"""Shared invented data for the weekly report's script tests.

Northwind Traders is an invented distributor, and its head of finance also holds the technology
seat. Every person, address and figure here is invented.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

PERIOD = "2027-11-12"

PROFILE = """# Weekly report profile

## Author and organisation

- Role: the head of finance and technology
- Organisation: Northwind Traders, a distributor of shop fittings, about 300 people

## Seats

1. Finance: answers for the month-end close, the forecast, the cash position and collections.
2. Technology: answers for the systems the business runs on, security and the support queue.

## Leadership team

1. Chief executive: the whole business, and the board's view of it.
2. Head of operations: the depots, the fleet and service levels.
3. Head of sales: revenue, the pipeline and the major accounts.

## Standing categories

### Month-end close
- Seat: Finance
- Kind: operational
- Covers: the close, its sign-off and the results that follow it.
- Signals:
  - Titles: `close|month[- ]end`
  - Keywords: `sign-off`
- Standing metrics:
  - Days to close from `facts:close_days`
- Owner: the financial controller

### Cash and collections
- Seat: Finance
- Kind: operational
- Covers: the cash position, receivables and anything on credit.
- Signals:
  - Titles: `cash|receivab|collection`
  - Keywords: `receivables`, `overdue`, `AR`
- Standing metrics:
  - Cash on hand from `facts:cash_on_hand`

### Systems and support
- Seat: Technology
- Kind: operational
- Covers: the systems the business runs on, security and the support queue.
- Signals:
  - Titles: `system|support|outage|security`
  - Keywords: `patch`
  - Counterparties: `fabrikam-it.test`

### Other topics
- Seat: Finance
- Kind: other
- Covers: important smaller call-outs that belong to none of the categories above.

## Standing metrics

1. Days to close from `facts:close_days`, monthly
2. Cash on hand from `facts:cash_on_hand`, weekly

## Direct reports

1. The financial controller, reports on the close and collections; file `controller-*.md`

## Collection tier and scope signals

- Tier: manual
- Attendee domains: `northwind.test`
- Title patterns: `/finance|technology/i`
- Mail terms: `close`

## Form rules

- Length: one page, 450 to 600 words
- Hard cap: two pages, 1,100 words
- Deadline: Friday by 3 pm
- Holiday rule: Thursday when Friday is a public holiday
- Materiality: $10,000

1. Every top-level bullet opens with a bold topic label and a colon.

## Names to roles

1. Dana: the financial controller

## Delivery

- Recipients: the leadership team
- Folder: the finance folder in the document store

## Never published

1. the Lakeview settlement

## Never recorded

1. Fabrikam Logistics

## Review date

- Last reviewed: 2027-11-01
- Next review: 2028-02-01
"""


def item(ref, kind, title, text="", when="2027-11-10", **extra):
    source = {"task": "work_tracker", "project": "work_tracker", "note": "note", "mail": "mail",
              "meeting": "calendar", "direct_report": "direct_report"}[kind]
    row = {"source": source, "kind": kind, "ref": ref, "title": title, "detail": "", "text": text,
           "occurred_at": when, "hours": None, "counterparties": [], "projects": [],
           "weight": 1.0, "extra": {}}
    row.update(extra)
    return row


ITEMS = [
    item("portal://task/t1", "task", "Close the October books",
         "The October close signed off on 2027-11-06, two days later than planned."),
    item("portal://task/t2", "task", "Chase the overdue receivables",
         "The Fabrikam Logistics account is 62 days overdue and the credit hold is disputed.",
         extra={"lists": ["overdue"], "priority": "P1"}),
    item("portal://email/e1", "mail", "Support queue after the patch window",
         "The support queue rose to 41 tickets after the patch window.",
         counterparties=["Sam Jordan", "fabrikam-it.test"],
         extra={"awaiting_owner": True, "message_count": 3}),
    item("portal://task/t7", "task", "Renew the goods-in scanner contract",
         "The scanner contract renews in January and nobody has priced it."),
    item("portal://email/e9", "mail", "Staff social", "The winter lunch is booked for the 18th."),
    item("portal://task/t8", "task", "Close out the disputed credit hold",
         "The account on credit hold goes to a call on Monday with the customer."),
    item("calendar://m1", "meeting", "Finance weekly", hours=1.5,
         counterparties=["northwind.test"]),
]


def ledger(period=PERIOD, items=None, prior=None, goals=None):
    return {
        "schema": "evidence-ledger/1", "tier": "manual", "model_driven": False,
        "generated_at": f"{period}T17:00:00Z", "generator": "the test fixture",
        "author": {"scope_kind": "domain", "scope_id": "d1", "scope_name": "Northwind Traders",
                   "short_name": "Northwind", "seats": ["Finance", "Technology"]},
        "period": {"since": "2027-11-08", "until": period, "timezone": "UTC", "as_of": period,
                   "lookahead_until": None, "lookahead_days": 0},
        "outline": {"source": "profile-file", "found": True, "note_ref": None, "text": ""},
        "items": list(ITEMS if items is None else items),
        "direct_reports": [], "prior_reports": list(prior or []), "goals": list(goals or []),
        "provenance": {"caps_applied": [], "warnings": [], "could_not_determine": []},
    }


def run(script, *args, stdin=None, env=None):
    """Run one script of this skill with the system interpreter, as the skill runs it."""
    merged = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py"), *map(str, args)],
                          capture_output=True, text=True, input=stdin, env=merged)


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    (root / "profile.md").write_text(PROFILE, encoding="utf-8")
    return root


@pytest.fixture
def ledger_file(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger()), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- a fake Portal

PORTAL_PROFILE = PROFILE.replace("- Tier: manual", "- Tier: portal")
PRIOR_REPORT = """# Weekly Highlights - Finance and Technology - 2027-11-05

## Cash and collections

- **Credit hold:** the disputed credit hold is pending a decision by 2027-11-09.
"""


def portal_answer(tool, args):
    """What the invented Portal returns for one call. Every record here is invented."""
    entity, filters = args.get("entity_type"), args.get("filters") or {}
    page = lambda rows: {"items": rows, "total": len(rows), "has_more": False}  # noqa: E731
    if tool == "whoami":
        return {"principal": {"timezone": "UTC", "primary_email": "owner@northwind.test"},
                "inboxes": [{"address": "owner@northwind.test"}]}
    if tool == "list_entities":
        if entity == "domain":
            return page([{"id": "d1", "name": "Northwind Traders", "_ref": "portal://domain/d1"}])
        if entity == "note":
            search = filters.get("search") or ""
            if search == "Weekly report profile":
                return page([{"id": "nprofile", "title": "Weekly report profile", "updated_at": "2027-11-01"}])
            if search.startswith("Weekly Highlights"):
                return page([{"id": "nprior", "title": "Weekly Highlights - Finance - 2027-11-05",
                              "created_at": "2027-11-05T16:00:00Z"}])
            if search:
                return page([])
            return page([{"id": "n1", "title": "Close review notes", "updated_at": "2027-11-10T10:00:00Z",
                          "created_at": "2027-11-10T09:00:00Z"}])
        if entity == "goal":
            return page([{"id": "g1", "title": "Cut debtor days", "priority": "P1", "_ref": "portal://goal/g1"}])
        if entity == "project":
            return page([{"id": "p1", "name": "Month-end close", "status": "active", "_ref": "portal://project/p1",
                          "updated_at": "2027-11-10T00:00:00Z"}])
        if entity == "task":
            return page([
                {"id": "t1", "title": "Close the October books", "status": "open", "priority": "P1",
                 "created_at": "2027-11-09T08:00:00Z", "due_date": "2027-11-15", "project_id": "p1",
                 "description": "Sign-off is due on the 15th.", "_ref": "portal://task/t1"},
                {"id": "t2", "title": "Chase the overdue receivables", "status": "waiting",
                 "created_at": "2027-10-01T08:00:00Z", "due_date": "2027-11-01", "_ref": "portal://task/t2",
                 "description": "The account is 62 days overdue."}])
        if entity == "calendar_event":
            if filters.get("since", "").startswith("2027-11-08"):
                return page([{"id": "c1", "_ref": "portal://calendar_event/c1", "title": "Finance weekly",
                              "event_kind": "meeting", "start_time": "2027-11-09T09:00:00Z",
                              "end_time": "2027-11-09T10:30:00Z",
                              "attendees": [{"email": "owner@northwind.test"},
                                            {"email": "dana@northwind.test"}]},
                             {"id": "c2", "title": "Lunch", "event_kind": "availability_block",
                              "start_time": "2027-11-09T12:00:00Z", "end_time": "2027-11-09T13:00:00Z"}])
            return page([])
        if entity == "email":
            return page([{"id": "e1", "_ref": "portal://email/e1", "subject": "Re: Support queue after the patch",
                          "from_address": "sam@fabrikam-it.test", "from_name": "Sam Jordan",
                          "received_at": "2027-11-10T15:00:00Z"}])
        if entity == "task" or args.get("filters", {}).get("assigned_agent"):
            return page([])
    if tool == "get":
        if args.get("entity_type") == "note" and args.get("id_or_query") == "nprofile":
            return {"id": "nprofile", "_ref": "portal://note/nprofile", "content": PORTAL_PROFILE}
        if args.get("entity_type") == "note" and args.get("id_or_query") == "nprior":
            return {"id": "nprior", "_ref": "portal://note/nprior", "content": PRIOR_REPORT,
                    "created_at": "2027-11-05T16:00:00Z"}
        if args.get("entity_type") == "note":
            return {"id": "n1", "_ref": "portal://note/n1", "title": "Close review notes",
                    "content": "Decided to move the close review to Tuesday.", "created_at": "2027-11-10T09:00:00Z",
                    "associations": [{"entity_type": "project", "entity_id": "p1"}]}
        if args.get("entity_type") == "email":
            return {"thread": [{"direction": "received", "received_at": "2027-11-10T15:00:00Z",
                                "from_address": "sam@fabrikam-it.test"}]}
    if tool == "email_bodies":
        return [{"id": "e1", "body": "The queue rose to 41 tickets.\n\n> earlier message"}]
    if tool == "search":
        return {"notes": []}
    if tool == "list_agent_profiles":
        return {"profiles": [{"slug": "weekly-reporter", "is_active": True}]}
    if tool == "create_task":
        return {"id": "task-wo"}
    return {}


@pytest.fixture
def portal(tmp_path, monkeypatch):
    """A local JSON-RPC server answering as the Portal, wired in through the owner settings."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            params = body["params"]
            calls.append((params["name"], params["arguments"], self.headers.get("Authorization")))
            result = portal_answer(params["name"], params["arguments"])
            payload = json.dumps({"jsonrpc": "2.0", "id": body["id"],
                                  "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": f"http://127.0.0.1:{server.server_port}/mcp",
        "headers": {"Authorization": "Bearer ${NORTHWIND_TEST_TOKEN}"}}}}), encoding="utf-8")
    settings = tmp_path / "settings.toml"
    settings.write_text(f'portal_mcp_config = "{config}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    monkeypatch.setenv("NORTHWIND_TEST_TOKEN", "test-token")
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)
    yield calls
    server.shutdown()


@pytest.fixture(autouse=True)
def no_owner_settings(tmp_path, monkeypatch):
    """No test reads the real owner's settings file; the portal fixture points at its own."""
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "no-settings.toml"))


@pytest.fixture
def week(tmp_path, store):
    """The manual-tier week, collected and organised by report_weekly_prepare.py."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "controller-week-46.md").write_text(
        "---\nkind: direct_report\nfrom: the financial controller\ndate: 2027-11-11\n---\n\n"
        "The October close signed off on 2027-11-06.\n")
    (incoming / "my-week.md").write_text("# Support queue\n\nThe queue rose to 41 tickets.\n")
    done = run("report_weekly_prepare", store, "--period", PERIOD, "--from-dir", incoming, "--format", "json")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)
