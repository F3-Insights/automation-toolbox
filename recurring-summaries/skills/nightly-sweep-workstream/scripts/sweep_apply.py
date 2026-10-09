"""sweep-apply: make the Portal writes one nightly-sweep phase proposed, each once.

The phase workers only read the Portal. Each returns its proposed writes as a fixed JSON change
set, saved as RUN/<date>/phaseN.json, and this script makes them in the Automation's finish step
(or checks them, with --dry-run, during the session). It is the only place the phases write, so
a dry run writes nothing and a re-run of a date writes nothing twice. With --run and no PLAN it
applies phase1.json, phase2.json and phase4.json of every date in RUN/dates.json, in that order.

Each phase may make only its own kinds of write, and a plan holding any other is refused whole:
phase 1 `create_task`, `set_status` WAITING and `create_note`; phase 2 `set_status` DONE; phase
4 `create_note`. The plan's `phase` must match its file name. A worker reads mail anyone can
write, so this is what stops an email that talks a worker into "mark every task done".

- create_task: one task per item of one email (`email_id`, `item`), which must be one of the
  date's emails in RUN/<date>/emails.json. Its marker, `nightly-sweep:email:<email id>:<item>`,
  goes in `source_reference` and as the description's last line beside
  `Source: portal://email/<id>`. A task in any status carrying the marker is reused. The owner
  is always the token's own contact (whoami).
- set_status: WAITING needs `evidence_ref` to an email the date received; DONE needs an email
  the date sent or a meeting note of the date, and a `handle`. A note counts only when it records
  a meeting of the date: attached to a calendar event that started that day, or, attached to no
  event, of a meeting note_type; a note the sweep wrote, a prep note, a Daily Note or a Brief
  never counts. The evidence must share a handle with the task, and the owner's own contact is
  never one. A task with a contact or a company needs that contact, or that company or a contact
  of it, among the sent email's recipients or the note's associations; words cannot stand in.
  A task with neither needs two distinctive words of its title (4 or more letters or digits, not
  all digits, not a stopword, not a word of the owner's or the firm's names) in the note's title,
  or in the sent email's own subject (not a Re: or Fwd:) and its body above the quoted thread and
  the signature, with addresses, links and domain names removed. Only an open task the owner
  owns moves; nothing is ever cancelled.
- create_note: at least one association. Its `key` puts a marker comment at the end of the
  content. A note already titled exactly the same, or carrying the marker, is reused. A rejected
  note_type is retried once without one.

Without --dry-run the run's dates.json must exist, say `dry_run` as a boolean and list the date
(else `NO_RUN`); when it says the run is a dry run, or F3I_TOOLBOX_DRY_RUN is set, a write
without --dry-run is refused (`DRY_RUN`). Every create and update is read back. Results go to
applied-phaseN.json beside the plan (applied-phaseN-dry-run.json in a dry run).

Prints one JSON object. Exit 0 (`applied`, `nothing`, `would_apply`), 3 when some writes failed
(`partial`) or the plan was refused (`refused` with `code` INVALID_PLAN, WRONG_DATE, WRONG_PHASE,
DRY_RUN or NO_RUN: nothing written), 2 when it could not run.

Examples:
    python3 sweep_apply.py RUN/2030-03-06/phase1.json --date 2030-03-06 --dry-run
    python3 sweep_apply.py --run RUN
"""

import argparse
import re
from pathlib import Path

import _common as c

KINDS = ("create_task", "set_status", "create_note")
STATUSES = ("WAITING", "DONE")
PHASE_WRITES = {1: {"create_task", "set_status:WAITING", "create_note"},
                2: {"set_status:DONE"},
                4: {"create_note"}}
EVIDENCE = re.compile(r"^portal://(email|note)/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$")
NOTE_ENTITIES = ("contact", "company", "calendar_event", "project", "task", "domain", "goal")
TITLE_MAX = 100
MEETING_NOTE_TYPES = ("meeting", "meeting-notes", "meeting_notes", "meeting-recap", "meeting_recap", "recap")
NOT_RECAP_TITLES = ("Meeting Prep:", "Daily Note - ", "Brief ")
# Common words and the generic verbs and nouns of task titles, which any email can hold.
STOPWORDS = frozenset("""
about above after again against also among another anyone around back been before being below between
both call calls could does doing done down during each email emails even every first from have having
here into just know last least less like make many more most much must need next once only other over
same should since some such than that their them then there these they this those through today
tomorrow under until upon very want week weekly were what when where which while will with within
would your yours
follow following followup reply respond response send sent schedule scheduling review check confirm
update updates meeting meetings discuss discussion prepare draft finalize share sign provide get
give take ask asked request requested approve approval set setup call note notes task tasks item items
re fw fwd regarding thread question questions plan plans work working time date dates
thanks thank please regards attached attaching attachment best cheers hello hi dear kind warm sincerely
january february march april june july august september sept october november december
monday tuesday tues wednesday weds thursday thur thurs friday saturday sunday
""".split())
WORD = re.compile(r"[a-z0-9][a-z0-9&]*")
EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
DOMAIN = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|io|co|us|ai|biz|info|edu|gov|uk|ca)\b", re.I)
JOINER = re.compile(r"(?<=[a-z0-9])['’‐‑-](?=[a-z0-9])")
REPLY_PREFIX = re.compile(r"^\s*(?:(?:re|fw|fwd)\s*:\s*)+", re.I)
# Where the quoted thread starts in a sent message: everything after was written by someone else.
QUOTE_START = re.compile(r"^\s*(?:>|from:\s|sent:\s|-+\s*original message\s*-+|-{5,}\s*forwarded message|"
                         r"_{10,}\s*$|begin forwarded message|on\b.*\bwrote:\s*$)", re.I)
SIGNOFFS = frozenset({"best", "best regards", "regards", "kind regards", "warm regards", "thanks", "thank you",
                      "many thanks", "cheers", "sincerely"})
APPLY_ORDER = (1, 2, 4)


class Refused(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


# --------------------------------------------------------------------------- words

def owner_stopwords():
    """Every word of the owner's and the firm's names: on half the mail, so never distinctive."""
    return frozenset(w for name in c.name_list("owner_names") + c.name_list("firm_names") for w in name.split())


def owner_signoffs():
    """The owner's names, alone or after a sign-off word, as a signature line."""
    names = c.name_list("owner_names")
    return frozenset(names + [f"{s} {n}" for s in ("thanks", "best", "cheers", "regards") for n in names])


def words(text):
    """The text's words, lower case: addresses, links and domain names removed first, a possessive
    "'s" cut, and a hyphen or apostrophe inside a word joined ("follow-up" is "followup")."""
    text = str(text or "").lower().replace("‘", "'").replace("’", "'")
    text = DOMAIN.sub(" ", URL.sub(" ", EMAIL_ADDRESS.sub(" ", text)))
    text = JOINER.sub("", re.sub(r"(?<=[a-z0-9])'s\b", "", text))
    return WORD.findall(text)


def distinctive(title):
    out, owner = [], owner_stopwords()
    for w in words(title):
        if len(w) >= 4 and not w.isdigit() and w not in STOPWORDS and w not in owner and w not in out:
            out.append(w)
    return out


def shared_words(title, text):
    held = set(words(text))
    return [w for w in distinctive(title) if w in held]


def own_words(body):
    """The part of a sent message the owner wrote: cut at the quoted thread and at the signature."""
    lines = str(body or "").replace("\r\n", "\n").split("\n")
    out, signoffs = [], owner_signoffs()
    for i, ln in enumerate(lines):
        bare = ln.strip()
        nxt = lines[i + 1].strip().lower() if i + 1 < len(lines) else ""
        if QUOTE_START.match(ln) or (bare.lower().startswith("on ") and nxt.endswith("wrote:")):
            break
        if bare in ("--", "-- "):
            break
        line = re.sub(r"[\s,.!-]+", " ", bare.lower()).strip()
        if any(o.strip() for o in out) and (line in SIGNOFFS or line in signoffs):
            break
        out.append(ln)
    return "\n".join(out)


def own_subject(subject):
    """A reply's or a forward's subject was written by the sender it answers: it counts for nothing."""
    return "" if REPLY_PREFIX.match(str(subject or "")) else str(subject or "")


# --------------------------------------------------------------------------- validation

def priority(value):
    if value in (None, ""):
        return None
    m = re.fullmatch(r"[Pp]?([1-4])", str(value).strip())
    if not m:
        raise ValueError(f"priority {value!r} is not P1 to P4")
    return int(m.group(1))


def evidence(ref):
    m = EVIDENCE.match(str(ref or "").strip())
    return (m.group(1), m.group(2).lower()) if m else None


def day_emails(emails):
    out = {"inbound": set(), "sent": set()}
    for part in out:
        for row in (emails or {}).get(part) or []:
            if isinstance(row, dict) and row.get("id"):
                out[part].add(str(row["id"]).lower())
    return out


def plan_phase(plan, source):
    phase = plan.get("phase")
    if isinstance(phase, bool) or not isinstance(phase, int) or phase not in PHASE_WRITES:
        raise Refused("WRONG_PHASE", f"the plan's phase is {phase!r}; only phases 1, 2 and 4 write")
    m = re.fullmatch(r"phase(\d+)", source.stem) if source else None
    if m and int(m.group(1)) != phase:
        raise Refused("WRONG_PHASE", f"{source.name} holds a plan that says it is phase {phase}")
    return phase


def validate(plan, day, emails=None, source=None):
    """The writes, checked; a plan with any bad write is refused whole, before any write."""
    if not isinstance(plan, dict):
        raise Refused("INVALID_PLAN", "the phase return is not a JSON object")
    if str(plan.get("date") or "") != day:
        raise Refused("WRONG_DATE", f"the plan is for {plan.get('date')!r}, this run is sweeping {day}")
    phase = plan_phase(plan, source)
    allowed = PHASE_WRITES[phase]
    writes = plan.get("writes") or []
    if not isinstance(writes, list):
        raise Refused("INVALID_PLAN", "`writes` is not a list")
    mail = day_emails(emails)
    problems, seen = [], set()
    for i, w in enumerate(writes):
        where = f"writes[{i}]"
        if not isinstance(w, dict) or w.get("kind") not in KINDS:
            problems.append(f"{where}: kind must be one of {', '.join(KINDS)}")
            continue
        kind = w["kind"]
        bound = f"set_status:{w.get('status')}" if kind == "set_status" else kind
        if bound not in allowed:
            problems.append(f"{where}: phase {phase} may not write {bound.replace(':', ' ')} "
                            f"(it may write {', '.join(sorted(a.replace(':', ' ') for a in allowed))})")
            continue
        if kind == "create_task":
            if not c.is_uuid(w.get("email_id")):
                problems.append(f"{where}: create_task needs the email_id it came from")
            elif emails is None:
                problems.append(f"{where}: emails.json was not found, so the email cannot be checked")
            elif str(w["email_id"]).lower() not in mail["inbound"] | mail["sent"]:
                problems.append(f"{where}: email {w['email_id']} is not one of {day}'s emails")
            if not isinstance(w.get("item"), int) or isinstance(w.get("item"), bool) or w["item"] < 1:
                problems.append(f"{where}: item is the item's number in its email, 1 for a single ask")
            title = str(w.get("title") or "").strip()
            if not title or len(title) > TITLE_MAX:
                problems.append(f"{where}: title is required and at most {TITLE_MAX} characters")
            if not str(w.get("domain") or "").strip():
                problems.append(f"{where}: domain is required (route with the routing tests)")
            try:
                priority(w.get("priority"))
            except ValueError as exc:
                problems.append(f"{where}: {exc}")
            due = w.get("due_date")
            if due not in (None, "") and not c.DATE_RE.match(str(due)):
                problems.append(f"{where}: due_date is YYYY-MM-DD or null")
            key = ("task", str(w.get("email_id")), w.get("item"))
        elif kind == "set_status":
            if not c.is_uuid(w.get("task_id")):
                problems.append(f"{where}: set_status needs a task_id")
            if not str(w.get("evidence") or "").strip():
                problems.append(f"{where}: set_status needs the evidence")
            ref = evidence(w.get("evidence_ref"))
            if not ref:
                problems.append(f"{where}: set_status needs evidence_ref, portal://email/<id> or portal://note/<id>")
            elif w.get("status") == "WAITING":
                if ref[0] != "email":
                    problems.append(f"{where}: WAITING needs the email that confirmed it, not a note")
                elif emails is None:
                    problems.append(f"{where}: emails.json was not found, so the evidence cannot be checked")
                elif ref[1] not in mail["inbound"]:
                    problems.append(f"{where}: {w['evidence_ref']} is not an email {day} received")
            if w.get("status") == "DONE" and not str(w.get("handle") or "").strip():
                problems.append(f"{where}: DONE needs the handle the evidence shares with the task (its contact or "
                                "its company, or for a task with neither, two distinctive words of its title)")
            if ref and w.get("status") == "DONE" and ref[0] == "email":
                if emails is None:
                    problems.append(f"{where}: emails.json was not found, so the evidence cannot be checked")
                elif ref[1] not in mail["sent"]:
                    problems.append(f"{where}: {w['evidence_ref']} is not an email sent on {day}")
            key = ("status", str(w.get("task_id")))
        else:
            if not str(w.get("title") or "").strip() or not str(w.get("content") or "").strip():
                problems.append(f"{where}: create_note needs a title and content")
            if not re.fullmatch(r"[A-Za-z0-9:._-]{3,200}", str(w.get("key") or "")):
                problems.append(f"{where}: create_note needs a key (letters, digits, : . _ -)")
            assoc = w.get("associations") or []
            if not assoc or not all(isinstance(a, dict) and a.get("entity_type") in NOTE_ENTITIES
                                    and c.is_uuid(a.get("entity_id")) for a in assoc):
                problems.append(f"{where}: a note needs at least one association, each "
                                f"{{entity_type, entity_id}} with entity_type one of {', '.join(NOTE_ENTITIES)}")
            key = ("note", str(w.get("key")))
        if key in seen:
            problems.append(f"{where}: the same write appears twice ({key[0]} {key[1]})")
        seen.add(key)
    if problems:
        raise Refused("INVALID_PLAN", "; ".join(problems))
    return writes


# --------------------------------------------------------------------------- the writer

def new_id(created, kind):
    nid = created.get("id") if isinstance(created, dict) else None
    if not c.is_uuid(nid) and isinstance(created, dict):
        nid = (created.get(kind) or {}).get("id")
    return str(nid) if c.is_uuid(nid) else None


class Applier:
    def __init__(self, client, day, dry_run, tz_name, emails=None):
        self.client, self.day, self.dry_run = client, day, dry_run
        self.window = c.local_day(c.parse_date(day), c.zone(tz_name))
        self._owner = None
        self.rows = {str(r["id"]).lower(): r for part in ("inbound", "sent")
                     for r in (emails or {}).get(part) or [] if isinstance(r, dict) and r.get("id")}

    def owner(self):
        if self._owner is None:
            self._owner = c.owner_contact(self.client)
        return self._owner

    # ---------------------------------------------------------------- tasks

    def create_task(self, w):
        marker = c.task_marker(str(w["email_id"]), int(w["item"]))
        out = {"kind": "create_task", "marker": marker, "title": w["title"]}
        found = c.with_marker(c.tasks_mentioning(self.client, str(w["email_id"])), marker)
        if found:
            return dict(out, outcome="reused", id=found[0]["id"], status=found[0].get("status"),
                        reason="a task carrying this marker already exists")
        body = str(w.get("description") or "").rstrip()
        description = "\n".join(p for p in (body, f"Source: {c.email_ref(w['email_id'])}", marker) if p)
        args = {"title": str(w["title"]).strip(), "domain_id_or_name": str(w["domain"]).strip(),
                "priority": priority(w.get("priority")), "due_date": w.get("due_date") or None,
                "owner_contact_id": self.owner(), "description": description,
                "source_reference": marker, "source_email_id": str(w["email_id"])}
        for extra in ("project_id", "task_contact_id"):
            if c.is_uuid(w.get(extra)):
                args[extra] = w[extra]
        args = {k: v for k, v in args.items() if v is not None}
        if self.dry_run:
            return dict(out, outcome="would_create", args=args)
        try:
            tid = new_id(self.client.call("create_task", args), "task")
            problem = "" if tid else "create_task answered without an id"
        except Exception as exc:  # noqa: BLE001 - reconciled below by looking the marker up
            tid, problem = None, f"create_task failed: {type(exc).__name__}: {exc}"
        if not tid:
            again = c.with_marker(c.tasks_mentioning(self.client, str(w["email_id"])), marker)
            if not again:
                return dict(out, outcome="failed", reason=f"{problem}; no task carries the marker, so a "
                                                          "re-run of this date creates it")
            tid = again[0]["id"]
            out["recovered"] = True
        task = c.get_record(self.client, "task", str(tid))
        verified = marker in str(task.get("description") or "") or task.get("source_reference") == marker
        return dict(out, outcome="created", id=tid, verified=verified,
                    **({} if verified else {"reason": "read back without its marker"}))

    def set_status(self, w):
        tid, target = str(w["task_id"]), w["status"]
        out = {"kind": "set_status", "id": tid, "status": target, "evidence": w.get("evidence"),
               "evidence_ref": w.get("evidence_ref")}
        try:
            task = c.get_record(self.client, "task", tid)
        except Exception as exc:  # noqa: BLE001
            return dict(out, outcome="failed", reason=c.safe(exc))
        out["title"] = task.get("title")
        if str(task.get("owner_contact_id") or "") != self.owner():
            return dict(out, outcome="skipped", reason=f"the task is {task.get('owner_name') or 'someone else'}'s, "
                                                       "not the owner's; the sweep moves only their own tasks")
        ref = evidence(w.get("evidence_ref"))
        if target == "DONE" and ref:
            problem, handle = self.done_evidence(task, ref)
            if problem:
                return dict(out, outcome="skipped", reason=problem)
            out["handle"] = handle
        current = str(task.get("status") or "")
        if current == target:
            return dict(out, outcome="unchanged", reason=f"already {target}")
        movable = ("TODO", "IN_PROGRESS") if target == "WAITING" else c.OPEN
        if current not in movable:
            return dict(out, outcome="skipped", reason=f"the task is {current}, not open")
        if self.dry_run:
            return dict(out, outcome="would_update", was=current)
        try:
            self.client.call("update_task", {"id": tid, "status": target})
            after = c.get_record(self.client, "task", tid)
        except Exception as exc:  # noqa: BLE001
            return dict(out, outcome="failed", reason=c.safe(f"update_task failed: {type(exc).__name__}: {exc}"))
        ok = str(after.get("status") or "") == target
        return dict(out, outcome="updated" if ok else "failed", was=current, verified=ok,
                    **({} if ok else {"reason": f"read back as {after.get('status')}"}))

    # ---------------------------------------------------------------- DONE evidence

    def done_evidence(self, task, ref):
        """(problem, handle): why the evidence does not show this task done, or what it shares."""
        owner = self.owner().lower()
        if ref[0] == "note":
            try:
                note = c.get_record(self.client, "note", ref[1])
            except Exception as exc:  # noqa: BLE001
                return f"the evidence note could not be read: {c.safe(exc)}", ""
            if not c.in_window(note.get("created_at"), self.window):
                return f"the evidence note was not written on {self.day}", ""
            problem = self.not_a_meeting_note(note)
            if problem:
                return problem, ""
            ids = {str(a.get("entity_id") or "").lower() for a in note.get("associations") or []
                   if isinstance(a, dict) and a.get("entity_type") in ("contact", "company")}
            text = str(note.get("title") or "")
            people, where = "the note's associations", "the note's title"
        else:
            row = self.rows.get(ref[1]) or {}
            ids = {str(x).lower() for x in row.get("recipient_contact_ids") or []}
            text = own_subject(str(row.get("subject") or "")) + "\n" + own_words(self.email_body(ref[1]))
            people, where = "the email's recipients", "the email's own subject and unquoted text"
        ids.discard(owner)
        ids.discard("")
        contact = str(task.get("task_contact_id") or "").lower()
        contact = "" if contact == owner else contact
        company = str(task.get("company_id") or "").lower()
        if contact or company:
            if contact and contact in ids:
                return "", f"contact {task.get('task_contact_name') or contact}"
            if company and (company in ids or company in self.companies_of(ids)):
                return "", f"company {task.get('company_name') or company}"
            named = " or ".join(x for x in (
                f"contact {task.get('task_contact_name') or contact}" if contact else "",
                f"company {task.get('company_name') or company}" if company else "") if x)
            return (f"the evidence shares nothing with the task: the task names {named}, which is not among "
                    f"{people}; title words do not stand in for a contact or a company", "")
        shared = shared_words(str(task.get("title") or ""), text)
        if len(shared) >= 2:
            return "", "title words " + ", ".join(shared)
        held = f" ({', '.join(shared)})" if shared else ""
        return (f"the evidence shares nothing with the task: it has no contact or company, and {where} holds "
                f"{len(shared)} distinctive word(s) of its title{held}; two are needed", "")

    def not_a_meeting_note(self, note):
        """Empty when the note records a meeting of the date; otherwise why not."""
        tags = {str(t.get("name") if isinstance(t, dict) else t).lower()
                for t in (note.get("tags") or []) + (note.get("tag_names") or [])}
        content, title = str(note.get("content") or ""), str(note.get("title") or "")
        if c.SWEEP_TAG in tags or f"{c.SWEEP_TAG}:" in content:
            return "the evidence note was written by the nightly sweep itself, not a meeting record"
        if title.startswith(NOT_RECAP_TITLES):
            return f"the evidence note is a {title.split(':')[0].split(' - ')[0]}, not a meeting record"
        events = {str(a.get("entity_id")) for a in note.get("associations") or []
                  if isinstance(a, dict) and a.get("entity_type") == "calendar_event" and a.get("entity_id")}
        if note.get("calendar_event_id"):
            events.add(str(note["calendar_event_id"]))
        if events:
            for eid in sorted(events):
                try:
                    event = self.client.call("get", {"entity_type": "calendar_event", "id_or_query": eid})
                except Exception:  # noqa: BLE001 - an unreadable event is not evidence
                    continue
                if isinstance(event, dict) and isinstance(event.get("event"), dict):
                    event = event["event"]
                if isinstance(event, dict) and c.in_window(event.get("start_time"), self.window):
                    return ""
            return (f"the evidence note is not a meeting record of {self.day}: no calendar event it is attached "
                    "to started that day")
        if str(note.get("note_type") or "").strip().lower() in MEETING_NOTE_TYPES:
            return ""
        return (f"the evidence note is not a meeting record of {self.day}: its note_type is "
                f"{note.get('note_type')!r} and it is attached to no calendar event")

    def email_body(self, eid):
        try:
            out = self.client.call("email_bodies", {"ids": [eid]})
        except Exception:  # noqa: BLE001 - the subject still counts
            return ""
        rows = out.get("items") if isinstance(out, dict) else None
        return " ".join(str(r.get("body") or "") for r in rows or [] if isinstance(r, dict) and r.get("found"))

    def companies_of(self, contact_ids):
        out = set()
        for cid in sorted(contact_ids)[:10]:
            try:
                got = self.client.call("get", {"entity_type": "contact", "id_or_query": cid, "detail": "summary"})
            except Exception:  # noqa: BLE001
                continue
            inner = got.get("contact") if isinstance(got, dict) and isinstance(got.get("contact"), dict) else got
            if not isinstance(inner, dict):
                continue
            nested = inner.get("company") if isinstance(inner.get("company"), dict) else {}
            company = inner.get("company_id") or nested.get("id")
            if company:
                out.add(str(company).lower())
        return out

    # ---------------------------------------------------------------- notes

    def create_note(self, w):
        title = str(w["title"]).strip()
        marker = c.note_marker(str(w["key"]))
        out = {"kind": "create_note", "key": w["key"], "title": title}
        existing = c.notes_titled(self.client, title, marker)
        if existing:
            return dict(out, outcome="reused", id=existing[0]["id"],
                        reason="a note with this marker already exists" if existing[0].get("found_by") == "marker"
                        else "a note with this exact title already exists")
        args = {"title": title, "content": str(w["content"]).rstrip() + "\n\n" + marker + "\n",
                "associations": [{"entity_type": a["entity_type"], "entity_id": a["entity_id"]}
                                 for a in w["associations"]],
                "is_pinned": False}
        if w.get("note_type"):
            args["note_type"] = str(w["note_type"])
        if w.get("tag_names"):
            args["tag_names"] = [str(t) for t in w["tag_names"]]
        if self.dry_run:
            return dict(out, outcome="would_create", note_type=args.get("note_type"),
                        associations=args["associations"])
        nid, problem, flags = self._create_note(args)
        if not nid:
            again = c.notes_titled(self.client, title, marker)
            if not again:
                return dict(out, outcome="failed", reason=f"{problem}; no note has this title, so a re-run "
                                                          "of this date creates it")
            nid = again[0]["id"]
            out["recovered"] = True
        note = c.get_record(self.client, "note", str(nid))
        verified = marker in str(note.get("content") or "") and str(note.get("title") or "").strip() == title
        return dict(out, outcome="created", id=nid, verified=verified, flags=flags,
                    **({} if verified else {"reason": "read back without its title or marker"}))

    def _create_note(self, args):
        """create_note; a rejected note_type is retried once without one, and flagged."""
        flags, problem = [], ""
        attempts = [args] + ([{k: v for k, v in args.items() if k != "note_type"}] if "note_type" in args else [])
        for n, attempt in enumerate(attempts):
            try:
                created = self.client.call("create_note", attempt)
            except Exception as exc:  # noqa: BLE001
                problem = f"create_note failed: {type(exc).__name__}: {exc}"
                if n == 0 and len(attempts) > 1 and "note_type" in str(exc).lower():
                    flags.append(f"note_type {args['note_type']!r} was rejected; created with the org's default")
                    continue
                return None, problem, flags
            nid = new_id(created, "note")
            if nid:
                return nid, "", flags
            return None, "create_note answered without an id", flags
        return None, problem, flags

    def one(self, w):
        try:
            return getattr(self, w["kind"])(w)
        except Exception as exc:  # noqa: BLE001 - one write failing is that write's result
            return {"kind": w["kind"], "outcome": "failed", "reason": c.safe(f"{type(exc).__name__}: {exc}"),
                    **{k: w.get(k) for k in ("email_id", "item", "task_id", "key", "title") if w.get(k)}}


def apply(client, plan, day, dry_run=False, emails=None, source=None, tz_name="UTC"):
    writes = validate(plan, day, emails, source)
    phase = plan.get("phase")
    if not writes:
        return {"status": "nothing", "date": day, "phase": phase, "dry_run": dry_run, "results": [], "counts": {}}
    applier = Applier(client, day, dry_run, tz_name, emails)
    results = [applier.one(w) for w in writes]
    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    unverified = [r for r in results if r.get("verified") is False]
    if dry_run:
        status = "would_apply"
    elif counts.get("failed") or unverified:
        status = "partial"
    else:
        status = "applied"
    return {"status": status, "date": day, "phase": phase, "dry_run": dry_run, "results": results, "counts": counts}


def apply_file(get_client, source, day, dry_run, run, tz_name, emails_path=None, out=None):
    """One plan file, exactly as the single-file form runs it; returns the result object."""
    refusal = c.run_refusal(run, dry_run, day)
    if refusal:
        return {"status": "refused", "code": refusal[0], "reason": refusal[1], "date": day, "written": 0}
    plan = c.read_json(source)
    mail_file = c.guard_run_path(emails_path) if emails_path else Path(source).with_name("emails.json")
    emails = c.read_json(mail_file) if Path(mail_file).is_file() else None
    try:
        result = apply(get_client(), plan, day, dry_run, emails, Path(source), tz_name)
    except Refused as exc:
        return {"status": "refused", "code": exc.code, "reason": exc.reason, "date": day, "written": 0}
    target = c.out_path(out) if out else Path(source).with_name(
        f"applied-{Path(source).stem}{'-dry-run' if dry_run else ''}.json")
    c.atomic_json(target, result)
    result["out"] = str(target)
    return result


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Make the writes one nightly-sweep phase proposed, each found by marker "
                                             "first and read back. Exit 0 applied, 3 partial or refused, 2 error.")
    ap.add_argument("plan", nargs="?", help="RUN/<date>/phaseN.json (or use --run alone)")
    ap.add_argument("--date", dest="day", help="the date this run is sweeping, with PLAN")
    ap.add_argument("--dry-run", action="store_true", help="read and check everything, write nothing")
    ap.add_argument("--out", help="where to write the results (default: beside the plan)")
    ap.add_argument("--run", help="the run folder (default: two levels above the plan); alone, every date")
    ap.add_argument("--emails", help="the date's emails.json (default: beside the plan)")
    ap.add_argument("--tz", help="the owner's IANA timezone (default: the settings)")
    args = ap.parse_args(argv)
    result = {}

    def body():
        tz_name = c.timezone_name(args.tz)
        if not args.plan:
            if not args.run or args.day or args.out or args.emails:
                raise c.Stop("give PLAN --date D, or --run RUN alone")
            run = c.guard_run_path(args.run)
            portal = []

            def get_client():
                if not portal:
                    portal.append(client or c.Portal())
                return portal[0]
            dates = []
            for row in c.run_date_rows(run):
                day, phases = row["date"], {}
                for n in APPLY_ORDER:
                    source = Path(run) / day / f"phase{n}.json"
                    if not source.is_file():
                        phases[str(n)] = {"status": "absent"}
                        continue
                    try:
                        phases[str(n)] = apply_file(get_client, source, day, args.dry_run, run, tz_name)
                    except Exception as exc:  # noqa: BLE001 - one phase failing is that phase's result
                        phases[str(n)] = {"status": "error", "reason": c.safe(f"{type(exc).__name__}: {exc}")}
                dates.append({"date": day, "phases": {k: {x: v.get(x) for x in ("status", "code", "reason", "counts",
                                                                                  "out") if v.get(x) is not None}
                                                      for k, v in phases.items()}})
            bad = any(p["status"] not in ("applied", "nothing", "would_apply", "absent")
                      for d in dates for p in d["phases"].values())
            result.update({"status": "partial" if bad else ("would_apply" if args.dry_run else "applied"),
                           "run": str(run), "dry_run": args.dry_run, "dates": dates})
            return
        if not args.day:
            raise c.Stop("--date is required with PLAN")
        c.parse_date(args.day)
        source = c.guard_run_path(args.plan)
        run = c.guard_run_path(args.run) if args.run else Path(source).parent.parent
        result.update(apply_file(lambda: client or c.Portal(), source, args.day, args.dry_run, run, tz_name,
                                 args.emails, args.out))

    c.run_main(body, "sweep_apply")
    c.emit(result, c.STOP if result.get("status") in ("partial", "refused") else c.OK)


if __name__ == "__main__":
    main()
