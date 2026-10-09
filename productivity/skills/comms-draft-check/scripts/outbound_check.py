#!/usr/bin/env python3
"""outbound-check: may a new draft to this person about this thread be created now?

Several jobs can each decide, the same night, that one person should be chased. This answers
the question from Portal state, in code, and a caller that does not get ALLOW does not draft.
The Portal's own drafts and the thread being answered are the ledger, so nothing is stored.
Read only.

Three rules, in order:

1. OPEN_DRAFT_SAME_THREAD: an unsent draft already covers this thread (its thread id, or the
   email it answers, is this thread or one of its messages), or, with no --thread, this
   recipient and this subject. An open draft on the thread that answers an earlier message
   and was created before the --thread email arrived holds as STALE_DRAFT instead: out of
   date, not a duplicate, so the caller can ask whether to set it aside.
2. RECENT_CONTACT: inside --per-person-days business days (Monday to Friday) a draft was
   created for this recipient, or the owner sent a message on this thread. Sent mail carries
   no recipient in the Portal, so mail the owner wrote by hand on another thread is not seen;
   the warnings say so.
3. DAILY_CAP: --daily-cap drafts already exist since midnight in the owner's timezone.

Field names on draft items are read through key lists that try several plausible names;
--explain prints the keys the Portal returned (never values) so the lists can be checked.

Inputs: --to (required), --thread, --subject, --per-person-days (5), --daily-cap (10),
--exclude-draft (the draft being delivered, not a duplicate of itself), --json, --explain.
Prints the verdict (text, or JSON with --json); warnings go to stderr. Exit 0 ALLOW, 3 HOLD,
2 ERROR. Treat any non-zero exit as "do not draft".

Example:
    python3 outbound_check.py --to jordan@example.com --thread portal://email/<id> --json
"""

import argparse
import json
import re
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import _common as c

ALLOW, HOLD, ERROR = 0, 3, 2

# Order is preference order: the first key that yields anything wins.
RECIPIENT_KEYS = ("to", "to_email", "to_emails", "recipient", "recipients", "to_addresses",
                  "recipient_to", "recipient_emails", "recipient_email")
NESTED_EMAIL_KEYS = ("email", "address", "email_address", "value")
THREAD_KEYS = ("thread_id", "conversation_id", "in_reply_to", "reply_to_email_id", "email_id", "_ref")
SUBJECT_KEYS = ("subject", "title")
TIME_KEYS = ("created_at", "sent_at", "received_at", "updated_at")
# A draft in one of these states no longer waits to be sent. Any other status counts as open.
CLOSED_DRAFT_STATUSES = frozenset({"sent", "pushed", "delivered", "discarded", "deleted", "cancelled",
                                   "canceled", "rejected", "archived", "expired"})
DRAFT_LOOKBACK_DAYS = 30
# A draft listing row carries no `email_id`, so with a --thread each open draft is read once
# to learn the email it answers. This caps how many; past it the result warns.
MAX_DRAFT_HYDRATIONS = 100

_SUBJECT_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|antw|rv|vs)\s*(\[\d+\])?\s*:\s*", re.IGNORECASE)
_ADDRESS = re.compile(r"[^\s<>,;\"']+@[^\s<>,;\"']+")


# --------------------------------------------------------------------------- reading items

def bare_address(text):
    found = _ADDRESS.search(str(text or ""))
    return found.group(0).strip(".<>").lower() if found else ""


def emails_in(value):
    """Every address in a string (comma or semicolon separated), a list, or a dict."""
    out = []
    if isinstance(value, str):
        out = [a for a in (bare_address(p) for p in re.split(r"[,;]", value)) if a]
    elif isinstance(value, dict):
        for key in NESTED_EMAIL_KEYS:
            if value.get(key):
                return emails_in(value[key])
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            out.extend(emails_in(item))
    return out


def thread_key(value):
    """`portal://email/abc` and `abc` are the same thread: the last segment, lowercased."""
    text = str(value or "").strip().rstrip("/")
    return text.rsplit("/", 1)[-1].lower() if text else ""


def normalise_subject(subject):
    """Case folded, spaces collapsed, every leading Re: or Fwd: stripped."""
    text = str(subject or "")
    while True:
        stripped = _SUBJECT_PREFIX.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return " ".join(text.split()).casefold()


def parse_time(value):
    """An ISO timestamp as aware UTC; one with no zone is read as UTC."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_open_draft(row):
    return str(row.get("status") or row.get("state") or "").strip().lower() not in CLOSED_DRAFT_STATUSES


class Item:
    """One draft or email, read through the key lists. Never raises on a bad shape."""

    def __init__(self, raw):
        data = raw if isinstance(raw, dict) else {}
        self.id = str(data.get("id") or data.get("_ref") or "")
        recipients = []
        for key in RECIPIENT_KEYS:
            if key in data:
                recipients += [a for a in emails_in(data[key]) if a not in recipients]
        self.recipients = list(dict.fromkeys(recipients))
        self.thread = next((thread_key(data.get(k)) for k in THREAD_KEYS if thread_key(data.get(k))), "")
        self.email = thread_key(data.get("email_id"))
        self.subject = normalise_subject(next((data[k] for k in SUBJECT_KEYS if str(data.get(k) or "").strip()), ""))
        self.when = next((parse_time(data.get(k)) for k in TIME_KEYS if parse_time(data.get(k))), None)
        self.open = is_open_draft(data)

    @property
    def usable(self):
        """An item with neither a recipient nor a thread can match no rule (it still counts
        toward the daily cap, the fail-closed direction)."""
        return bool(self.recipients or self.thread)

    def on_thread(self, want, thread_ids):
        return bool({k for k in (self.thread, self.email) if k} & ({want} | set(thread_ids)))

    def day(self):
        return self.when.date().isoformat() if self.when else "unknown"


# --------------------------------------------------------------------------- time

def business_days_back(now, days):
    """The instant `days` weekdays before `now`; a weekend never uses up the cooldown."""
    cursor, counted = now, 0
    while counted < max(0, days):
        cursor -= timedelta(days=1)
        if cursor.weekday() < 5:
            counted += 1
    return cursor


def local_midnight(now, tz):
    local = now.astimezone(tz)
    return datetime.combine(local.date(), time(0, 0), tzinfo=tz).astimezone(timezone.utc)


def owner_timezone(portal):
    """The owner's zone from whoami, or UTC with a warning: it only moves the cap's midnight."""
    name, warnings = "", []
    try:
        who = portal.call("whoami")
        principal = who.get("principal") if isinstance(who, dict) else None
        if isinstance(principal, dict):
            name = str(principal.get("timezone") or "")
    except Exception:
        warnings.append("whoami failed: using UTC for the daily cap's midnight")
    if not name:
        if not warnings:
            warnings.append("whoami returned no principal.timezone: using UTC for the daily cap's midnight")
        return timezone.utc, "UTC", warnings
    try:
        return ZoneInfo(name), name, warnings
    except Exception:
        warnings.append(f"unknown timezone {name!r}: using UTC for the daily cap's midnight")
        return timezone.utc, "UTC", warnings


# --------------------------------------------------------------------------- the rules

def hold(rule, reason, evidence, drafts, sent):
    return {"verdict": "HOLD", "rule": rule, "reason": reason, "evidence": evidence,
            "checked": {"drafts": len(drafts), "sent": len(sent)}}


def evaluate(drafts, sent, to, thread, subject, now, per_person_days, daily_cap, tz, tz_name="UTC",
             thread_ids=frozenset(), email_at=None):
    """The three rules over listings already read. No I/O and no clock reads."""
    address, want_thread, want_subject = bare_address(to), thread_key(thread), normalise_subject(subject)
    cutoff = business_days_back(now, per_person_days)
    midnight = local_midnight(now, tz)

    if want_thread:
        matched, basis = [d for d in drafts if d.open and d.on_thread(want_thread, thread_ids)], "thread"
    elif want_subject:
        matched = [d for d in drafts if d.open and address in d.recipients and d.subject == want_subject]
        basis = "recipient and subject"
    else:
        matched, basis = [], "skipped: no --thread and no --subject to match on"
    stale = []
    if matched and want_thread and email_at is not None:
        # A draft with no time, or one answering this very email, stays a duplicate.
        stale = [d for d in matched if d.email != want_thread and d.when is not None and d.when < email_at]
        matched = [d for d in matched if d not in stale]
    if matched:
        return hold("OPEN_DRAFT_SAME_THREAD",
                    f"an unsent draft already covers this thread, matched on {basis} "
                    f"(draft {matched[0].id or 'with no id'}, created {matched[0].day()})",
                    {"matched_on": basis, "open_drafts": len(matched), "draft_ids": [d.id for d in matched[:5] if d.id],
                     "created": sorted({d.day() for d in matched})}, drafts, sent)
    if stale:
        return hold("STALE_DRAFT",
                    f"an unsent draft on this thread predates the email being answered "
                    f"(draft {stale[0].id or 'with no id'}, created {stale[0].day()}; the email arrived "
                    f"{email_at.date().isoformat()})",
                    {"matched_on": basis, "stale_drafts": len(stale), "draft_ids": [d.id for d in stale[:5] if d.id],
                     "created": sorted({d.day() for d in stale}), "answers": sorted({d.email for d in stale if d.email}),
                     "email_arrived": email_at.isoformat()}, drafts, sent)

    recent_drafts = [d for d in drafts if address in d.recipients and d.when and d.when >= cutoff]
    recent_sent = [s for s in sent if address in s.recipients and s.when and s.when >= cutoff]
    if recent_drafts or recent_sent:
        days = sorted({i.day() for i in recent_drafts + recent_sent})
        return hold("RECENT_CONTACT",
                    f"this recipient was contacted inside the last {per_person_days} business days "
                    f"(on {', '.join(days)}); the cooldown runs to {cutoff.date().isoformat()}",
                    {"per_person_days": per_person_days, "cutoff": cutoff.isoformat(),
                     "drafts_to_recipient": len(recent_drafts), "sent_to_recipient": len(recent_sent),
                     "dates": days}, drafts, sent)

    today = [d for d in drafts if d.when and d.when >= midnight]
    if len(today) >= daily_cap:
        return hold("DAILY_CAP", f"{len(today)} drafts have been created since midnight {tz_name} and the cap is "
                                 f"{daily_cap}",
                    {"drafts_today": len(today), "daily_cap": daily_cap, "timezone": tz_name,
                     "since": midnight.isoformat()}, drafts, sent)

    return {"verdict": "ALLOW", "rule": None,
            "reason": (f"no unsent draft on this thread, no contact with this recipient in the last "
                       f"{per_person_days} business days, {len(today)} of {daily_cap} drafts used today"),
            "evidence": {"open_drafts_on_thread": 0, "per_person_days": per_person_days, "cutoff": cutoff.isoformat(),
                         "drafts_today": len(today), "daily_cap": daily_cap, "timezone": tz_name},
            "checked": {"drafts": len(drafts), "sent": len(sent)}}


# --------------------------------------------------------------------------- the reads

def thread_messages(portal, thread):
    """Every message on the thread; a failed read returns [] and the draft ledger still runs."""
    try:
        found = portal.call("get", {"entity_type": "email", "id_or_query": thread_key(thread)})
    except Exception:
        return []
    if not isinstance(found, dict) or found.get("error"):
        return []
    return [m for m in found.get("thread") or [] if isinstance(m, dict)]


def with_email_ids(portal, rows):
    """Each open draft with the email it answers, read with `get` (a listing row has none)."""
    out, read, skipped = [], 0, 0
    for row in rows:
        if not isinstance(row, dict) or "email_id" in row or not is_open_draft(row) or not row.get("id"):
            out.append(row)
            continue
        if read >= MAX_DRAFT_HYDRATIONS:
            skipped += 1
            out.append(row)
            continue
        read += 1
        try:
            full = portal.call("get", {"entity_type": "draft", "id_or_query": str(row["id"])})
        except Exception:
            full = None
        if isinstance(full, dict) and not full.get("error"):
            row = dict(row, email_id=full.get("email_id"), contact_id=full.get("contact_id"))
        out.append(row)
    note = (f"{skipped} open drafts past the first {MAX_DRAFT_HYDRATIONS} were not read for the email they answer"
            if skipped else "")
    return out, note


def key_report(rows):
    """Which keys the Portal put on these items. Keys only, never values."""
    keys = {}
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                keys[str(key)] = keys.get(str(key), 0) + 1
    return {"items": len(rows), "keys": dict(sorted(keys.items()))}


def run(portal, to, thread="", subject="", per_person_days=5, daily_cap=10, now=None, exclude_draft=""):
    address = bare_address(to)
    if not address:
        raise c.Failure("--to needs an email address")
    if per_person_days < 0:
        raise c.Failure("--per-person-days cannot be negative")
    if daily_cap < 1:
        raise c.Failure("--daily-cap has to be at least 1")
    now = now or datetime.now(timezone.utc)
    tz, tz_name, warnings = owner_timezone(portal)

    # The drafts read reaches back far enough to cover the longest of the three windows.
    cutoff = business_days_back(now, per_person_days)
    horizon = min(cutoff, local_midnight(now, tz), now - timedelta(days=DRAFT_LOOKBACK_DAYS))
    raw_drafts = c.list_entities(portal, "draft", {"since": horizon.strftime("%Y-%m-%dT%H:%M:%SZ")})
    skip = thread_key(exclude_draft)
    if skip:
        raw_drafts = [r for r in raw_drafts if not (isinstance(r, dict) and thread_key(r.get("id") or r.get("_ref")) == skip)]

    # Sent mail carries no recipient in the Portal, so it is checked on this thread only.
    raw_sent, thread_ids, email_at = [], frozenset(), None
    if thread:
        messages = thread_messages(portal, thread)
        thread_ids = frozenset(thread_key(m.get("id")) for m in messages if m.get("id"))
        email_at = next((Item(m).when for m in messages if thread_key(m.get("id")) == thread_key(thread)), None)
        raw_sent = [m for m in messages if str(m.get("direction", "")).lower() == "sent"
                    and Item(m).when is not None and Item(m).when >= cutoff]
        raw_drafts, note = with_email_ids(portal, raw_drafts)
        if note:
            warnings.append(note)
    drafts = [Item(r) for r in raw_drafts]
    sent = [Item(dict(r, to=address)) for r in raw_sent]
    result = evaluate(drafts, sent, address, thread, subject, now, per_person_days, daily_cap, tz, tz_name,
                      thread_ids=thread_ids, email_at=email_at)
    if skip:
        result["excluded_draft"] = skip
    unparsed = sum(1 for i in drafts + sent if not i.usable)
    if unparsed:
        warnings.append(f"{unparsed} items carried neither a recipient nor a thread in any key this command knows, "
                        "and were ignored for matching; run --explain and extend the key lists")
    warnings.append("mail the owner sent by hand outside this thread is not visible through the Portal, so only "
                    "the draft ledger" + (" and this thread were checked" if thread else " was checked"))
    result["warnings"] = warnings
    result["explain"] = {"draft": key_report(raw_drafts), "email": key_report(raw_sent)}
    return result


def report(result, as_json, explain):
    for warning in result.get("warnings") or []:
        print(c.safe(f"warning: {warning}"), file=sys.stderr)
    if as_json:
        payload = {k: result[k] for k in ("verdict", "rule", "reason", "evidence", "checked")}
        if explain:
            payload["explain"] = result["explain"]
        print(c.safe(json.dumps(payload, indent=1, default=str)))
        return
    print(result["verdict"] + (f" {result['rule']}" if result["rule"] else ""))
    print(c.safe(result["reason"]))
    for key, value in (result["evidence"] or {}).items():
        print(c.safe(f"  {key}: {value}"))
    print(f"  checked: {result['checked']['drafts']} drafts, {result['checked']['sent']} sent")
    if explain:
        for entity, seen in result["explain"].items():
            print(f"keys seen on {entity} items ({seen['items']} read):", file=sys.stderr)
            for key, count in seen["keys"].items():
                print(f"  {key} ({count})", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="May a new draft to this person about this thread be created "
                                                 "now? Exit 0 ALLOW, 3 HOLD, 2 ERROR.")
    parser.add_argument("--to", required=True, help="recipient email address")
    parser.add_argument("--thread", default="", help="thread reference or id, e.g. portal://email/<id>")
    parser.add_argument("--subject", default="", help="subject, used only when no --thread is given")
    parser.add_argument("--per-person-days", type=int, default=5, help="cooldown per recipient, in business days")
    parser.add_argument("--daily-cap", type=int, default=10, help="most drafts that may exist since local midnight")
    parser.add_argument("--exclude-draft", default="", help="a draft id left out of the ledger (the one being delivered)")
    parser.add_argument("--json", dest="as_json", action="store_true", help="print the verdict as JSON")
    parser.add_argument("--explain", action="store_true", help="also print the item keys the Portal returned")
    args = parser.parse_args()   # a usage error exits 2, the same as ERROR
    try:
        result = run(c.client(), args.to, args.thread, args.subject, args.per_person_days, args.daily_cap,
                     exclude_draft=args.exclude_draft)
    except c.Failure as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(ERROR)
    except Exception as exc:  # a check that could not run is not a check that passed
        print(c.safe(f"ERROR outbound-check could not complete: {type(exc).__name__}: {exc}"), file=sys.stderr)
        sys.exit(ERROR)
    report(result, args.as_json, args.explain)
    sys.exit(ALLOW if result["verdict"] == "ALLOW" else HOLD)


if __name__ == "__main__":
    main()
