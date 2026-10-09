#!/usr/bin/env python3
"""Is the month's close done? Computed from the Month-End folder alone.

    python3 month_end_check.py FOLDER [--period yyyy-mm] [--format text|json] [--precheck]

FOLDER is a Month-End folder: MONTH-END-PROCEDURES.md (with a '## Balance-sheet accounts' table
| Account | Name | Workstream | ... |) and STATUS.md ('Current period: yyyy-mm') at the root, and
one folder per month, {yyyy}/{yyyy-mm}/, holding STATUS.md (its '## Waiting on' table), LOG.md,
MONTH-END-PROCEDURES-{yyyy-mm}.md, journal-entries/, the evidence file
MONTH-END-EVIDENCE-{yyyy-mm}.csv (written by month_end_record.py),
reporting/MONTH-END-FINDINGS-{yyyy-mm}.md and the read-only ledger pull in work/source/
(pulled.md, headers-, lines- and trial-balance-{yyyy-mm}.json). Without --period the root
STATUS.md's current period is checked.

The four tests of done:
1. entries: every 'entries' evidence row is booked or not-needed with review PASS, and every
   import file in journal-entries/ is found posted in the pull on the period's last day with
   the same total debits (posted-matching), posted with other debits (posted-different: a
   person changed the file), or not posted. Entries posted on the prior month's last day with
   no counterpart this month are listed as recurring candidates, a warning only.
2. reconciliations: every balance-sheet account with a balance in the trial balance is in the
   procedures table and has a reconciled, reviewed row whose file exists and whose amount
   equals the ledger balance.
3. flux: the findings file has content and a 'flux' row is explained with review PASS.
4. questions: every Waiting on row is answered or closed.

--precheck prints one line for a scheduler instead, 'WORK: <reason>' or 'NOTHING: <reason>':
work when the close is not done and something moved (an answered question, a file changed
since the last LOG.md entry, an agent-owned checklist row due).

Exit 0 whenever the check ran, whatever it found; 2 on a bad argument or a missing folder.

    python3 month_end_check.py ~/close/acme --period 2026-03 --format json
"""

import argparse
import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from _common import (TESTS, Bad, column, evidence_path, first_date, money, month_folder, open_month,
                     period_end, read_evidence, read_text, section, shift, tables)

DEBIT_TOLERANCE = 0.005
BALANCE_TOLERANCE = 0.01
LOG_GRACE = timedelta(minutes=1)        # LOG.md headings carry minutes only
BOOKKEEPING = ("LOG.md", "STATUS.md")   # written by the orchestrator around its LOG entry
MONTH_WORDS = "|".join(sorted({"january", "february", "march", "april", "may", "june", "july", "august",
                               "september", "october", "november", "december", "jan", "feb", "mar", "apr",
                               "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}, key=len, reverse=True))

# Standard ledger field -> the Sage Intacct name a raw pull carries instead.
LINE_ALIAS = {"je_id": "journalEntry.key"}
HEADER_ALIAS = {"je_id": ("key", "id"), "date": ("postingDate",), "reversed_from": ("reversedFromDate",)}


def header_field(row, name):
    for key in (name, *HEADER_ALIAS.get(name, ())):
        if key in row:
            return "" if row[key] is None else str(row[key])
    return ""


def line_debit(row):
    """A GL line's debit, from the standard shape or a raw Intacct line (amount plus txnType)."""
    if "debit" in row or "credit" in row:
        return money(row.get("debit")) or 0.0
    if str(row.get("txnType", "")).lower().startswith("d"):
        return money(row.get("baseAmount") or row.get("txnAmount")) or 0.0
    return 0.0


# The ledger pull

def load_rows(path):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("rows") or []) if isinstance(data, dict) else list(data)


def pull_info(month):
    note = month / "work" / "source" / "pulled.md"
    if not note.is_file():
        return {"date": None, "preliminary": False, "note": "no pulled.md in work/source"}
    text = note.read_text(encoding="utf-8")
    m = re.search(r"Pulled (\d{4}-\d{2}-\d{2})", text)
    found = m.group(1) if m else (str(first_date(text)) if first_date(text) else None)
    return {"date": found, "preliminary": "PRELIMINARY" in text, "note": ""}


def describe(text):
    """A description folded for matching: lower case, no reversal prefix, months, digits or punctuation."""
    body = re.sub(r"^\s*reversed?\s*-\s*", "", str(text or "").lower())
    body = re.sub(r"\d+", " ", body)
    body = re.sub(rf"\b({MONTH_WORDS})\b", " ", body)
    body = re.sub(r"[^a-z]+", " ", body)
    return re.sub(r"\s+", " ", body).strip()


def ledger_entries(source, period):
    """The pull's journal entries with their total debits, or None when there is no headers file."""
    headers = load_rows(source / f"headers-{period}.json")
    if headers is None:
        return None
    debits = {}
    for ln in load_rows(source / f"lines-{period}.json") or []:
        key = str(ln.get("je_id", ln.get(LINE_ALIAS["je_id"], "")) or "")
        debits[key] = debits.get(key, 0.0) + line_debit(ln)
    out = []
    for h in headers:
        key, text = header_field(h, "je_id"), header_field(h, "description")
        out.append({"je": key, "description": text, "state": header_field(h, "state"),
                    "date": header_field(h, "date")[:10],
                    "reversal": bool(re.match(r"^\s*reversed?\s*-", text, re.I) or header_field(h, "reversed_from")),
                    "debits": round(debits.get(key, 0.0), 2), "has_lines": key in debits})
    return out


# Test 1: entries

def draft_entries(je_folder):
    """Each entry of each import CSV under journal-entries/ (files with DEBIT and CREDIT columns).
    A new entry starts at LINE_NO 1 or at a row with a DATE."""
    out = []
    if not je_folder.is_dir():
        return out
    for path in sorted(p for p in je_folder.rglob("*") if p.is_file() and p.suffix.lower() == ".csv"):
        reader = csv.DictReader(io.StringIO(read_text(path), newline=""))
        if not {"DEBIT", "CREDIT"} <= set(reader.fieldnames or []):
            continue
        entries = []
        for row in reader:
            if not entries or str(row.get("LINE_NO") or "").strip() == "1" or str(row.get("DATE") or "").strip():
                entries.append([])
            entries[-1].append(row)
        for entry in entries:
            first = entry[0]
            out.append({"file": str(path.relative_to(je_folder.parent)),
                        "description": str(first.get("DESCRIPTION") or "").strip(),
                        "date": str(first.get("DATE") or "").strip(),
                        "state": str(first.get("STATE") or "").strip(),
                        "debits": round(sum(money(r.get("DEBIT")) or 0.0 for r in entry), 2)})
    return out


def same_description(a, b):
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def match_drafts(drafts, ledger, end):
    """Find each draft in the pull: same debits first (preferring the same description), then
    the same description with other debits. Each posted entry matches one draft at most."""
    candidates = [e for e in ledger or [] if e["date"] == end and not e["reversal"]]
    used, out = set(), []
    for draft in drafts:
        mine = describe(draft["description"])
        result = dict(draft, status="not-posted", je="", posted_debits=None, note="")
        if ledger is None:
            result["note"] = "no ledger pull for the period"
            out.append(result)
            continue
        posted = [e for e in candidates if e["state"].lower() == "posted" and e["je"] not in used]
        same = sorted((e for e in posted if abs(e["debits"] - draft["debits"]) <= DEBIT_TOLERANCE),
                      key=lambda e: not same_description(describe(e["description"]), mine))
        named = [e for e in posted if same_description(describe(e["description"]), mine)]
        entered = [e for e in candidates if e["state"].lower() != "posted"
                   and (same_description(describe(e["description"]), mine)
                        or abs(e["debits"] - draft["debits"]) <= DEBIT_TOLERANCE)]
        hit = None
        if same:
            hit = same[0]
            result.update(status="posted-matching", je=hit["je"], posted_debits=hit["debits"])
        elif named:
            hit = named[0]
            result.update(status="posted-different", je=hit["je"], posted_debits=hit["debits"],
                          note=f"draft {draft['debits']:,.2f}, posted {hit['debits']:,.2f}")
        elif entered:
            result["note"] = f"JE {entered[0]['je']} is in the ledger as {entered[0]['state'] or 'unposted'}"
        if hit:
            used.add(hit["je"])
        out.append(result)
    return out


def recurring_candidates(root, period, ledger, drafts):
    """Posted entries on the prior month's last day with nothing like them this month."""
    prior = shift(period, -1)
    prior_ledger = ledger_entries(month_folder(root, prior) / "work" / "source", prior)
    if prior_ledger is None:
        return [], f"no {prior} pull (headers-{prior}.json) to compare with"
    end, prior_end = period_end(period), period_end(prior)
    present = {describe(e["description"]) for e in ledger or [] if e["date"] == end and not e["reversal"]}
    present |= {describe(d["description"]) for d in drafts}
    present.discard("")
    out, seen = [], set()
    for e in prior_ledger:
        key = describe(e["description"])
        if (e["date"] != prior_end or e["reversal"] or e["state"].lower() != "posted" or not key
                or key in seen or any(same_description(key, p) for p in present)):
            continue
        seen.add(key)
        out.append({"je": e["je"], "description": e["description"], "date": e["date"], "debits": e["debits"]})
    return out, ""


def test_entries(root, period, month, evidence):
    gaps, ok = [], 0
    rows = [r for r in evidence.values() if r.get("test") == "entries"]
    for r in rows:
        if r.get("state") in ("booked", "not-needed") and r.get("review") == "PASS":
            ok += 1
        elif r.get("state") not in ("booked", "not-needed"):
            gaps.append(f"{r['id']}: state {r.get('state') or 'blank'}, not booked")
        else:
            gaps.append(f"{r['id']}: {r.get('state')} but review is {r.get('review') or 'not done'}, not PASS")
    if not rows:
        gaps.append("no entries rows in the evidence file")
    ledger = ledger_entries(month / "work" / "source", period)
    drafts = match_drafts(draft_entries(month / "journal-entries"), ledger, period_end(period))
    for d in drafts:
        if d["status"] == "not-posted":
            gaps.append(f"draft not posted: {d['file']} '{d['description']}' {d['debits']:,.2f}"
                        + (f" ({d['note']})" if d["note"] else ""))
    candidates, note = recurring_candidates(root, period, ledger, drafts)
    counts = {"rows": len(rows), "rows_ok": ok, "drafts": len(drafts),
              **{s: sum(1 for d in drafts if d["status"] == s)
                 for s in ("posted-matching", "posted-different", "not-posted")},
              "recurring_candidates": len(candidates)}
    return {"met": not gaps, "counts": counts, "gaps": gaps, "drafts": drafts, "recurring_candidates": candidates,
            "recurring_note": note, "ledger": "no headers file in the pull" if ledger is None else f"{len(ledger)} entries"}


# Test 2: reconciliations

def account_spec(cell):
    """'10400', '15000-15999' or '19300, 19350' as (low, high) pairs."""
    out = []
    for part in re.split(r"[,;]", cell.replace("`", "")):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if m and int(m.group(1)) <= int(m.group(2)):
            out.append((m.group(1), m.group(2)))
        elif part:
            out.append((part, part))
    return out


def in_spec(account, spec):
    return any(account == low if low == high else account.isdigit() and int(low) <= int(account) <= int(high)
               for low, high in spec)


def test_reconciliations(root, period, month, evidence):
    tb = load_rows(month / "work" / "source" / f"trial-balance-{period}.json")
    if tb is None:
        return {"met": False, "counts": {"accounts": 0, "reconciled": 0}, "by_workstream": {},
                "gaps": [f"no trial balance in the pull (work/source/trial-balance-{period}.json)"], "items": []}
    balances = {}
    for row in tb:
        if str(row.get("Type") or "") != "balanceSheet":
            continue  # only balance-sheet accounts are reconciled; other rows are never parsed
        amount = money(row.get("Ending balance")) or 0.0
        if abs(amount) >= 0.005:
            balances[str(row.get("Account") or "").strip()] = (str(row.get("Name") or ""), amount)

    gaps = []
    procedures = root / "MONTH-END-PROCEDURES.md"
    body = section(procedures.read_text(encoding="utf-8"), "Balance-sheet accounts") if procedures.is_file() else None
    table = tables(body)[0] if body and tables(body) else []
    if not table:
        gaps.append("MONTH-END-PROCEDURES.md has no '## Balance-sheet accounts' table")
    groups = []
    for row in table:
        cell = " ".join(column(row, "Account").replace("`", "").split())
        if cell:
            groups.append({"cell": cell, "spec": account_spec(cell),
                           "workstream": column(row, "Workstream") or "unassigned", "accounts": []})
    unassigned = []
    for account in sorted(balances):
        group = next((g for g in groups if in_spec(account, g["spec"])), None)
        (group["accounts"] if group else unassigned).append(account)

    items = []

    def judge(item, accounts, workstream, row):
        ledger = round(sum(balances[a][1] for a in accounts), 2)
        problems = []
        if row is None:
            problems.append("no evidence row")
        else:
            if row.get("state") != "reconciled":
                problems.append(f"state {row.get('state') or 'blank'}, not reconciled")
            if row.get("review") != "PASS":
                problems.append(f"review {row.get('review') or 'not done'}, not PASS")
            named = row.get("evidence", "")
            if not named:
                problems.append("no reconciliation file named")
            elif not (month / named).is_file():
                problems.append(f"file missing: {named}")
            try:
                recorded = money(row.get("amount"))
            except ValueError:
                recorded = None
            if recorded is None:
                problems.append("no amount recorded")
            elif abs(recorded - ledger) > BALANCE_TOLERANCE:
                problems.append(f"stale: reconciled at {recorded:,.2f}, ledger now {ledger:,.2f}")
        items.append({"item": item, "accounts": accounts, "workstream": workstream, "ledger": ledger,
                      "ok": not problems, "problems": problems})
        if problems:
            gaps.append(f"reconciliations:{item} ({workstream}, ledger {ledger:,.2f}): {'; '.join(problems)}")

    # An account reconciles on its own row, or as part of a row for the whole table cell (a range).
    for group in groups:
        loose = []
        for account in group["accounts"]:
            row = evidence.get(f"reconciliations:{account}")
            if row:
                judge(account, [account], group["workstream"], row)
            else:
                loose.append(account)
        if not loose:
            continue
        row = evidence.get(f"reconciliations:{group['cell']}")
        if row:
            judge(group["cell"], loose, group["workstream"], row)
        else:
            for account in loose:
                judge(account, [account], group["workstream"], None)
    for account in unassigned:
        items.append({"item": account, "accounts": [account], "workstream": "unassigned",
                      "ledger": balances[account][1], "ok": False, "problems": ["not in the procedures table"]})
        gaps.append(f"unassigned: {account} {balances[account][0]} ({balances[account][1]:,.2f}) "
                    "is not in the procedures table")

    by_ws = {}
    for it in items:
        ws = by_ws.setdefault(it["workstream"], {"accounts": 0, "reconciled": 0})
        ws["accounts"] += len(it["accounts"])
        ws["reconciled"] += len(it["accounts"]) if it["ok"] else 0
    counts = {"accounts": len(balances), "reconciled": sum(w["reconciled"] for w in by_ws.values()),
              "unassigned": len(unassigned)}
    return {"met": not gaps, "counts": counts, "by_workstream": by_ws, "gaps": gaps, "items": items}


# Tests 3 and 4: flux and questions

def test_flux(period, month, evidence):
    gaps, content = [], 0
    findings = month / "reporting" / f"MONTH-END-FINDINGS-{period}.md"
    if not findings.is_file():
        gaps.append(f"no findings file (reporting/{findings.name})")
    else:
        content = sum(1 for ln in findings.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.lstrip().startswith("#"))
        if not content:
            gaps.append(f"reporting/{findings.name} has nothing beyond its heading")
    rows = [r for r in evidence.values() if r.get("test") == "flux"]
    good = [r for r in rows if r.get("state") == "explained" and r.get("review") == "PASS"]
    if not good:
        seen = ", ".join(f"{r['id']} {r.get('state') or ''}/{r.get('review') or 'no review'}" for r in rows)
        gaps.append("no flux row explained with review PASS" + (f" ({seen})" if rows else ""))
    return {"met": not gaps, "counts": {"finding_lines": content, "rows": len(rows), "rows_ok": len(good)},
            "gaps": gaps}


def waiting_on(month):
    status = month / "STATUS.md"
    body = section(status.read_text(encoding="utf-8"), "Waiting on") if status.is_file() else None
    found = tables(body) if body else []
    return found[0] if found else []


def test_questions(month, today):
    rows = waiting_on(month)
    gaps, still_open, answered = [], [], []
    for row in rows:
        state = column(row, "State").strip("*_ ").lower()
        ident = column(row, "Id") or "?"
        if state == "answered":
            answered.append(ident)
        if state in ("answered", "closed"):
            continue
        asked = first_date(column(row, "Asked at"))
        age = (today - asked).days if asked else None
        still_open.append({"id": ident, "question": column(row, "Question"), "asked_of": column(row, "Asked of"),
                           "state": state or "blank", "age_days": age})
        gaps.append(f"{ident} {state or 'blank'}{f', {age} day(s)' if age is not None else ''}: "
                    f"{column(row, 'Question')} (asked of {column(row, 'Asked of') or '?'})")
    return {"met": not gaps, "counts": {"rows": len(rows), "open": len(still_open), "answered": len(answered)},
            "gaps": gaps, "open": still_open, "answered": answered}


# The check and the precheck

def check(folder, period=None, today=None):
    root, period, month = open_month(folder, period)
    today = today or date.today()
    evidence = read_evidence(evidence_path(root, period))
    tests = {"entries": test_entries(root, period, month, evidence),
             "reconciliations": test_reconciliations(root, period, month, evidence),
             "flux": test_flux(period, month, evidence),
             "questions": test_questions(month, today)}
    met = sum(1 for t in tests.values() if t["met"])
    return {"folder": str(root), "period": period, "today": today.isoformat(), "pull": pull_info(month),
            "evidence_rows": len(evidence), "tests": tests, "met": met, "done": met == len(tests)}


def last_log_time(month):
    log = month / "LOG.md"
    if not log.is_file():
        return None
    times = []
    for day, clock in re.findall(r"^##\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", log.read_text(encoding="utf-8"), re.M):
        try:
            times.append(datetime.fromisoformat(f"{day}T{clock}"))
        except ValueError:
            continue
    return max(times) if times else None


def changed_since(month, period, since):
    """Files changed after the last LOG entry, leaving out the orchestrator's own bookkeeping and
    the work folder (except the pull note)."""
    skip = set(BOOKKEEPING) | {f"MONTH-END-PROCEDURES-{period}.md"}
    out = []
    for path in sorted(month.rglob("*")):
        rel = path.relative_to(month)
        if not path.is_file() or path.name.startswith((".", "~$")):
            continue
        if rel.parts[0] == "work" and rel.as_posix() != "work/source/pulled.md":
            continue
        if len(rel.parts) == 1 and rel.name in skip:
            continue
        if datetime.fromtimestamp(path.stat().st_mtime) > since + LOG_GRACE:
            out.append(rel.as_posix())
    return out


def agent_rows_due(month, period, today):
    """Open checklist rows owned by an agent whose 'ME+n = yyyy-mm-dd' due date has come."""
    copy = month / f"MONTH-END-PROCEDURES-{period}.md"
    if not copy.is_file():
        return []
    out = []
    for table in tables(copy.read_text(encoding="utf-8")):
        for row in table:
            if "agent" not in column(row, "Owner").lower():
                continue
            if column(row, "Status").strip("*_ ").lower() not in ("open", ""):
                continue
            due = None
            for cell in row.values():
                m = re.search(r"ME\s*[+-]?\s*\d*\s*=\s*(\d{4}-\d{2}-\d{2})", cell)
                if m:
                    due = first_date(m.group(1))
                    break
            if due and due <= today:
                label = " ".join([v for v in row.values() if v][:2]) or "?"
                out.append(f"{label} (due {due.isoformat()})")
    return out


def precheck(folder, period=None, today=None):
    result = check(folder, period, today)
    month = month_folder(Path(result["folder"]), result["period"])
    today = date.fromisoformat(result["today"])
    if result["done"]:
        return {"work": False, "line": f"NOTHING: close done for {result['period']} (all four tests met)", "details": []}
    reasons, details = [], []
    answered = result["tests"]["questions"]["answered"]
    if answered:
        reasons.append(f"{len(answered)} Waiting on row(s) answered ({', '.join(answered)})")
    logged = last_log_time(month)
    if logged is None:
        reasons.append("no LOG.md entry for the month yet")
    else:
        changed = changed_since(month, result["period"], logged)
        if changed:
            reasons.append(f"{len(changed)} file(s) changed since the last LOG entry ({logged:%Y-%m-%d %H:%M})")
            details += [f"changed: {c}" for c in changed]
    due = agent_rows_due(month, result["period"], today)
    if due:
        reasons.append(f"{len(due)} agent-owned checklist row(s) open and due")
        details += [f"due: {d}" for d in due]
    if reasons:
        return {"work": True, "line": f"WORK: {'; '.join(reasons)}", "details": details}
    return {"work": False, "details": [],
            "line": (f"NOTHING: {result['period']} close open ({result['met']} of 4 tests met) but no answer, "
                     "no change since the last LOG entry and no agent row due")}


def render(result):
    pull, t = result["pull"], result["tests"]
    out = [f"Month-end check {result['period']} ({result['folder']})",
           f"Pull: {pull['date']}{' PRELIMINARY' if pull['preliminary'] else ''}" if pull["date"]
           else f"Pull: none found ({pull['note']})",
           f"Close: {'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of 4 tests met)"]
    e, r = t["entries"]["counts"], t["reconciliations"]
    summaries = {
        "entries": (f"{e['rows_ok']}/{e['rows']} evidence rows booked and reviewed; {e['drafts']} draft(s): "
                    f"{e['posted-matching']} posted-matching, {e['posted-different']} posted-different, "
                    f"{e['not-posted']} not posted"),
        "reconciliations": (f"{r['counts']['reconciled']}/{r['counts']['accounts']} balance-sheet accounts reconciled"
                            + ("; " + ", ".join(f"{ws} {c['reconciled']}/{c['accounts']}"
                                                for ws, c in sorted(r["by_workstream"].items()))
                               if r["by_workstream"] else "")),
        "flux": (f"{t['flux']['counts']['finding_lines']} finding line(s), "
                 f"{t['flux']['counts']['rows_ok']}/{t['flux']['counts']['rows']} flux row(s) explained and reviewed"),
        "questions": f"{t['questions']['counts']['open']} open of {t['questions']['counts']['rows']} Waiting on row(s)",
    }
    for number, name in enumerate(TESTS, start=1):
        test = t[name]
        out += ["", f"{number} {name}: {'MET' if test['met'] else 'NOT MET'}. {summaries[name]}"]
        out += [f"  - {g}" for g in test["gaps"]]
        if name == "entries":
            for d in test["drafts"]:
                if d["status"] == "posted-different":
                    out.append(f"  ~ posted-different: {d['file']} '{d['description']}' draft {d['debits']:,.2f}, "
                               f"posted JE {d['je']} {d['posted_debits']:,.2f}")
            for c in test["recurring_candidates"]:
                out.append(f"  ? recurring candidate: '{c['description']}' (JE {c['je']}, {c['date']}, "
                           f"{c['debits']:,.2f}) has no counterpart this month")
            if test["recurring_note"]:
                out.append(f"  ? recurring candidates not checked: {test['recurring_note']}")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Report the four tests of done for a month's close. Exit 0 when it ran, 2 on a bad argument.")
    p.add_argument("folder", help="the Month-End folder")
    p.add_argument("--period", help="yyyy-mm (default: the root STATUS.md's Current period)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="one line for a scheduler: WORK: <reason> or NOTHING: <reason>")
    p.add_argument("--today", help=argparse.SUPPRESS)  # pretend today is yyyy-mm-dd, for tests
    a = p.parse_args(argv)
    try:
        today = date.fromisoformat(a.today) if a.today else None
        if a.precheck:
            result = precheck(a.folder, a.period, today)
            print(result["line"])
            for line in result["details"]:
                print(f"  {line}")
            return 0
        result = check(a.folder, a.period, today)
    except (Bad, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1) if a.format == "json" else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
