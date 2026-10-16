# /// script
# dependencies = ["pyyaml"]
# ///
"""The mail and meetings one task-asks Run decides, gathered in code before the session.

Reads from the Insights Portal (read only), since the domain's cursor less a two-day overlap for
mail that syncs late (first run: 30 days back; --since overrides): the owner's sent and received
mail and their Fellow meetings, keeps what is in the domain's scope, and marks who is a VIP there.
The scope is the first ```yaml block of --domain-file (see _common.py): `mail.inboxes` (mail in
these inboxes), `mail.correspondent_domains` (mail or meetings with people at these domains, from
any inbox), `ignore.senders` (glob patterns on a received message's sender) and `vip` (roles and
titles at companies, resolved from each company's relationships in the CRM, and contacts the
file names by id).

Each item: `key` (asks:email:<id> or asks:meeting:<id>, the source a create carries), `ref`,
`date` (UTC) and `local_date`, `direction` (sent, received or meeting), `subject`, `snippet`,
`counterparties` (addresses and contact ids, the owner left out; a meeting's also `people`, each
attendee's address with the contact it resolves to), `vip` and `vips` (the VIPs on it),
`default_due` (the follow-up when the ask names no date: 3 business days for a VIP and 5 for
others on sent mail, 2 for a VIP otherwise, else null) and `already` (tasks already carrying the
key). A meeting item adds `owner_attended` and `delegated_due`, the follow-up of an action on
someone else (3 business days for a VIP, else 5). Items an earlier Run decided are left out. VIP
items come first, then the newest; at most --max (40), cut into batches of --batch-size (10); the
rest are deferred and come back next Run, since the cursor only moves past what was decided
(task_asks_record.py).

First line: `QUEUE: 12 item(s) queued (3 VIP; 6 sent, 5 received, 1 meeting); 2 deferred; ...`
or `NOTHING: ...`. --out writes a new file and never overwrites one. Exit 0 when it ran, 2 for
a bad argument, an unusable domain file or a Portal that cannot be read.

Example:
    python3 task_asks_queue.py --domain "Northwind" --domain-file ~/ref/northwind.md --out RUN/asks-queue.json
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import _common as c

TOOL, VERSION = "task-asks-queue", 1
MAX_DEFAULT, BATCH_DEFAULT, FIRST_RUN_DAYS = 40, 10, 30
DUE_DAYS = {("sent", True): 3, ("sent", False): 5, ("received", True): 2, ("meeting", True): 2}
ALL_STATUSES = ["TODO", "IN_PROGRESS", "WAITING", "DONE", "CANCELLED"]


def add_business_days(day, n):
    while n > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def due_after(local_date, days):
    """The date `days` business days after an item's local date, or None."""
    try:
        return add_business_days(date.fromisoformat(local_date), days).isoformat() if days else None
    except ValueError:
        return None


def domain_of(address):
    return str(address or "").lower().rpartition("@")[2]


# --------------------------------------------------------------------------- reads

def owner_of(client):
    who = client.call("whoami")
    who = who if isinstance(who, dict) else {}
    principal = who.get("principal") or {}
    contact = str(principal.get("contact_id") or "").lower()
    if not contact:
        raise c.PortalError("whoami named no contact for the owner")
    addresses = {str(principal.get("primary_email") or "").lower()}
    addresses |= {str(i.get("address") or "").lower() for i in who.get("inboxes") or []}
    return contact, sorted(a for a in addresses if a), principal.get("timezone") or "UTC"


def find_domain(client, wanted):
    rows = client.list_all("domain", {"include_inactive": True})
    want = wanted.strip().lower()
    exact = [d for d in rows if want in (str(d.get("id")).lower(), str(d.get("name") or "").lower())]
    loose = [d for d in rows if want in str(d.get("name") or "").lower()]
    picked = exact or loose
    if len(picked) != 1:
        raise c.Bad(f"--domain {wanted!r} matches {len(picked)} domains; give its id or exact name")
    d = picked[0]
    general = [p for p in client.list_all("project", {"domain_id": d["id"]})
               if p.get("is_general") and not p.get("is_archived")]
    return {"id": str(d["id"]).lower(), "name": d.get("name"),
            "catch_all_project": str(general[0]["id"]).lower() if general else None}


def resolve_vips(client, rules, owner):
    """{contact id: {name, why, addresses}} from each rule's company relationships or named
    contacts, and warnings."""
    vips, warnings = {}, []
    for rule in rules:
        if "contacts" in rule:
            for cid in rule["contacts"]:
                if cid != owner:
                    vips.setdefault(cid, {"contact_id": cid, "name": None, "why": "named in the domain file",
                                          "addresses": []})
            continue
        found = client.call("list_entities", {"entity_type": "company", "limit": 25,
                                              "filters": {"search": rule["company"]}})
        rows = [r for r in (found.get("items") or []) if isinstance(r, dict)] if isinstance(found, dict) else []
        company = next((r for r in rows if str(r.get("name") or "").lower() == rule["company"].lower()), None)
        if company is None:
            warnings.append(f"vip: no company named {rule['company']!r}")
            continue
        rels = client.call("list_relationships", {"entity_type": "company", "entity_id": company["id"]})
        hits = 0
        for rel in (rels.get("relationships") or []) if isinstance(rels, dict) else []:
            cid = str(rel.get("contact_id") or "").lower()
            if not cid or cid == owner or not c.vip_match(rel, rule):
                continue
            hits += 1
            why = f"{rel.get('relationship_type')}{', ' + rel['title'] if rel.get('title') else ''} at {company['name']}"
            vips.setdefault(cid, {"contact_id": cid, "name": None, "why": why, "addresses": []})
        if not hits:
            warnings.append(f"vip: nobody at {company['name']} holds {rule['roles'] + rule['titles']}")
    for cid, v in vips.items():
        try:
            got = client.call("get", {"entity_type": "contact", "id_or_query": cid, "detail": "summary"})
        except c.PortalError:
            warnings.append(f"vip: no contact {cid}")
            continue
        rec = got.get("contact") if isinstance(got, dict) and isinstance(got.get("contact"), dict) else got
        if isinstance(rec, dict):
            v["name"] = rec.get("full_name") or rec.get("name")
            mails = [e.get("address") for e in (rec.get("emails") or got.get("emails") or []) if isinstance(e, dict)]
            v["addresses"] = sorted({str(a).lower() for a in mails + [rec.get("primary_email")] if a})
    return vips, warnings


def read_meetings(client, since_iso):
    out, offset = [], 0
    for _ in range(50):
        page = client.call("list_fellow_meetings", {"since": since_iso, "limit": 50, "offset": offset})
        rows = page.get("meetings") or [] if isinstance(page, dict) else []
        out += [r for r in rows if isinstance(r, dict)]
        nxt = page.get("next_offset") if isinstance(page, dict) else None
        if not rows or not isinstance(nxt, int) or nxt <= offset:
            break
        offset = nxt
    return out


# --------------------------------------------------------------------------- items

def email_item(row, direction, owner, owner_addrs, scope, vips, vip_addrs):
    """The item for one email, or (None, why) when it is out of scope or ignored."""
    sender = str(row.get("from_address") or "").lower()
    to = [str(a).lower() for a in (row.get("to_addresses") or []) + (row.get("cc_addresses") or [])]
    if direction == "received" and c.ignored(sender, scope["ignore_senders"]):
        return None, "ignored"
    others = [a for a in ([sender] if direction == "received" else []) + to if a not in owner_addrs]
    inbox_hit = (sender in scope["inboxes"]) if direction == "sent" else any(a in scope["inboxes"] for a in to)
    if not (inbox_hit or any(domain_of(a) in scope["correspondent_domains"] for a in others)):
        return None, "out_of_scope"
    ids = [str(x).lower() for x in row.get("recipient_contact_ids") or []]
    if direction == "received" and row.get("contact_id"):
        ids.insert(0, str(row["contact_id"]).lower())
    ids = list(dict.fromkeys(i for i in ids if i != owner))
    on = [v for v in vips if v in ids] + [v for v, a in vip_addrs.items() if v not in ids and set(a) & set(others)]
    rid = str(row["id"]).lower()
    return {"key": f"asks:email:{rid}", "ref": f"portal://email/{rid}", "date": row.get("received_at"),
            "local_date": str(row.get("received_local") or row.get("received_at") or "")[:10],
            "direction": direction, "subject": row.get("subject"), "from": sender or None,
            "snippet": row.get("snippet") or row.get("summary"),
            "counterparties": {"addresses": others, "contact_ids": ids}, "vips": on}, None


def contact_lookup(client):
    """address -> {contact_id, name}: the contact holding that address as its natural key and
    among its own addresses, else nulls. Each address is read once."""
    cache = {}

    def find(address):
        if address not in cache:
            try:
                got = client.call("get", {"entity_type": "contact", "id_or_query": address, "detail": "summary"})
            except c.PortalError:  # one failed lookup leaves that attendee unresolved
                got = {}
            got = got if isinstance(got, dict) else {}
            rec = got.get("contact") if isinstance(got.get("contact"), dict) else {}
            mails = {str(e.get("address") or "").lower() for e in got.get("emails") or [] if isinstance(e, dict)}
            mails.add(str(rec.get("primary_email") or "").lower())
            hit = rec.get("id") and address in mails
            cache[address] = {"contact_id": str(rec["id"]).lower() if hit else None,
                              "name": rec.get("full_name") if hit else None}
        return cache[address]
    return find


def meeting_item(row, event, owner_addrs, scope, vip_addrs, contact_for):
    ev = event.get("event") if isinstance(event.get("event"), dict) else event
    organizer = str(ev.get("organizer_email") or "").lower()
    emails = [str(a).lower() for a in event.get("attendee_emails") or
              [x.get("email") for x in ev.get("attendees") or [] if isinstance(x, dict)] if a]
    everyone = list(dict.fromkeys([organizer] + emails if organizer else emails))
    others = [a for a in everyone if a not in owner_addrs]
    if not (any(a in scope["inboxes"] for a in everyone)
            or any(domain_of(a) in scope["correspondent_domains"] for a in others)):
        return None, "out_of_scope"
    people = [{"address": a, **contact_for(a)} for a in others]
    rid = str(row["id"]).lower()
    note = f"portal://note/{str(row['note_id']).lower()}" if row.get("note_id") else None
    return {"key": f"asks:meeting:{rid}", "ref": note or f"portal://calendar_event/{row['calendar_event_id']}",
            "event": f"portal://calendar_event/{str(row['calendar_event_id']).lower()}",
            "date": row.get("started_at"),
            "local_date": str(ev.get("start_local") or row.get("started_at") or "")[:10],
            "direction": "meeting", "subject": ev.get("title"), "from": organizer or None, "snippet": None,
            "counterparties": {"addresses": others, "people": people,
                               "contact_ids": [p["contact_id"] for p in people if p["contact_id"]]},
            "owner_attended": any(a in owner_addrs for a in everyone),
            "vips": [v for v, a in vip_addrs.items() if set(a) & set(others)]}, None


def already(client, key):
    """The tasks (any status) already carrying this item's key, the first ask's or a later one's."""
    out = client.call("list_entities", {"entity_type": "task", "limit": 50,
                                        "filters": {"search": key, "status": ALL_STATUSES}})
    rows = out.get("items") or [] if isinstance(out, dict) else []
    hits = []
    for t in rows:
        desc = str(t.get("description") or "")
        if f"Captured from: {key}\n" in desc + "\n" or f"Captured from: {key}:" in desc:
            hits.append({"task": f"portal://task/{str(t.get('id')).lower()}", "title": t.get("title"),
                         "status": t.get("status"), "owner_contact_id": t.get("owner_contact_id")})
    return hits


# --------------------------------------------------------------------------- the queue

def gather(client, domain, scope, since, cursor, now, max_items=MAX_DEFAULT, batch_size=BATCH_DEFAULT):
    owner, owner_addrs, tz = owner_of(client)
    dom = find_domain(client, domain)
    vips, warnings = resolve_vips(client, scope["vip"], owner)
    vip_addrs = {cid: v["addresses"] for cid, v in vips.items()}
    decided = set(cursor["decided"])
    contact_for = contact_lookup(client)
    since_iso = c.iso(since)
    counts = {"emails_read": 0, "meetings_read": 0, "out_of_scope": 0, "ignored": 0, "decided_before": 0,
              "unmatched_meetings": 0}
    items = []

    def keep(item, why):
        if item is None:
            counts[why] += 1
        elif item["key"] in decided:
            counts["decided_before"] += 1
        else:
            items.append(item)

    for direction in ("sent", "received"):
        for row in client.list_all("email", {"direction": direction, "since": since_iso}):
            when = c.parse_time(row.get("received_at"))
            if when is None or when < since:
                continue
            counts["emails_read"] += 1
            keep(*email_item(row, direction, owner, owner_addrs, scope, vips, vip_addrs))
    for row in read_meetings(client, since_iso):
        when = c.parse_time(row.get("started_at"))
        if row.get("via_delegation") or when is None or when < since:
            continue
        counts["meetings_read"] += 1
        if not row.get("calendar_event_id"):
            counts["unmatched_meetings"] += 1
            continue
        if f"asks:meeting:{str(row['id']).lower()}" in decided:
            counts["decided_before"] += 1
            continue
        event = client.call("get", {"entity_type": "calendar_event", "id_or_query": row["calendar_event_id"],
                                    "detail": "summary"})
        keep(*meeting_item(row, event if isinstance(event, dict) else {}, owner_addrs, scope, vip_addrs,
                           contact_for))

    for it in items:
        it["vip"] = bool(it["vips"])
        it["vips"] = [{"contact_id": v, "name": vips[v]["name"], "why": vips[v]["why"]} for v in it["vips"]]
        it["default_due"] = due_after(it["local_date"], DUE_DAYS.get((it["direction"], it["vip"])))
        if it["direction"] == "meeting":  # an action the meeting put on someone else is followed up as sent mail is
            it["delegated_due"] = due_after(it["local_date"], DUE_DAYS[("sent", it["vip"])])
    items.sort(key=lambda i: (i["vip"], str(i["date"] or ""), i["key"]), reverse=True)
    queued, deferred = items[:max_items], items[max_items:]
    for n, it in enumerate(queued):
        it["batch"] = f"b{n // batch_size + 1}"
        it["already"] = already(client, it["key"])
    per = {}
    for it in queued:
        per[it["direction"]] = per.get(it["direction"], 0) + 1
    counts.update(queued=len(queued), deferred=len(deferred), vip=sum(1 for i in queued if i["vip"]),
                  per_direction=per)
    return {"tool": TOOL, "version": VERSION, "generated_at": c.iso(now),
            "domain": dom, "owner_contact_id": owner, "owner_addresses": owner_addrs, "timezone": tz,
            "window": {"since": since_iso, "until": c.iso(now), "first_run": cursor["since"] is None},
            "scope": {k: scope[k] for k in ("inboxes", "correspondent_domains", "ignore_senders")},
            "vips": list(vips.values()), "warnings": warnings, "counts": counts,
            "batches": sorted({i["batch"] for i in queued}, key=lambda b: int(b[1:])),
            "items": queued,
            "deferred": [{"key": i["key"], "date": i["date"], "vip": i["vip"]} for i in deferred],
            "teams": "not read by this command; the session reads it when it has a Microsoft 365 connector"}


def first_line(result):
    n = result["counts"]
    tail = f"; since {result['window']['since']}" + (f"; {len(result['warnings'])} warning(s)" if result["warnings"] else "")
    if not n["queued"]:
        return (f"NOTHING: no new ask to decide ({n['emails_read']} emails, {n['meetings_read']} meetings read; "
                f"{n['out_of_scope']} out of scope, {n['ignored']} ignored, {n['decided_before']} decided before){tail}")
    where = ", ".join(f"{v} {k}" for k, v in n["per_direction"].items())
    return f"QUEUE: {n['queued']} item(s) queued ({n['vip']} VIP; {where}); {n['deferred']} deferred{tail}"


def as_text(result):
    lines = [first_line(result)] + [f"  warning: {w}" for w in result["warnings"]]
    for it in result["items"]:
        mark = " VIP" if it["vip"] else ""
        held = f" already {it['already'][0]['task']}" if it["already"] else ""
        lines.append(f"  {it['batch']} {it['key']} {it['local_date']} {it['direction']}{mark}: "
                     f"{str(it['subject'] or '')[:80]}{held}")
    return "\n".join(lines)


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="task_asks_queue.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--domain", required=True, help="The Portal domain, by name or id")
    p.add_argument("--domain-file", required=True, help="The domain's reference file (its first ```yaml block)")
    p.add_argument("--since", default="", help="Read from this date or instant instead of the cursor")
    p.add_argument("--max", default=str(MAX_DEFAULT), help="At most this many items (default 40)")
    p.add_argument("--batch-size", default=str(BATCH_DEFAULT), help="Items per worker batch (default 10)")
    p.add_argument("--state", default="", help="The state folder (default: setting state_dir)")
    p.add_argument("--as-of", default="", help="Judge as of this instant (ISO) instead of now")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--out", default="", help="Also write the JSON to this new file (never overwritten)")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="The Portal's server name (default: setting portal_server)")
    a = p.parse_args(argv)
    try:
        cap = whole(a.max, "max", MAX_DEFAULT, 1, 1000)
        size = whole(a.batch_size, "batch-size", BATCH_DEFAULT, 1, 200)
        now = c.parse_time(a.as_of) if a.as_of.strip() else datetime.now(timezone.utc)
        if now is None:
            raise c.Bad(f"--as-of wants an ISO date or instant, got {a.as_of!r}")
        out_path = Path(a.out).expanduser() if a.out.strip() else None
        if out_path is not None and out_path.exists():
            raise c.Bad(f"--out {a.out!r} exists; this command never overwrites a file")
        scope = c.load_scope(a.domain_file)
        path = c.cursor_path(a.domain, a.state)
        cursor = c.read_cursor(path)
        last = c.parse_time(cursor["since"])
        since = c.parse_time(a.since) if a.since.strip() else (
            last - c.OVERLAP if last else now - timedelta(days=FIRST_RUN_DAYS))
        if since is None:
            raise c.Bad(f"--since wants an ISO date or instant, got {a.since!r}")
        client = client or c.Portal(a.config or None, a.server or None)
        result = gather(client, a.domain, scope, since, cursor, now, cap, size)
    except (c.Bad, c.PortalError) as exc:
        c.fail(exc)
    result["cursor"] = str(path)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("x", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False, default=str)
            fh.write("\n")
    if a.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(c.safe(as_text(result) if out_path is None else first_line(result)))
    return 0


def whole(value, name, default, low, high):
    """A whole-number option; blank (from a launch form) means the default."""
    text = str(value or "").strip()
    if not text:
        return default
    if not text.isdigit() or not (low <= int(text) <= high):
        raise c.Bad(f"--{name} wants a whole number from {low} to {high}, got {value!r}")
    return int(text)


if __name__ == "__main__":
    sys.exit(main())
