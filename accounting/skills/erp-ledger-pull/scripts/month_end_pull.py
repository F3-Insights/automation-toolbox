#!/usr/bin/env python3
# /// script
# dependencies = ["openpyxl"]
# ///
"""Refresh one month's read-only ledger pull in a Month-End folder.

    python3 month_end_pull.py FOLDER [--period yyyy-mm] [--live | --offline-from DIR]
                              [--label PRELIMINARY|FINAL] [--preliminary-days N]

Built to run before an agent session, so every session works from today's books. It never
fails its caller for a soft problem: the first line printed is always

    FRESH: pulled <date> <counts>; <label>; <trial balance>
    STALE: <reason>; using the pull of <date>

and the exit code is 0 for both. Exit 2 is kept for a bad argument or a folder that is not a
Month-End folder (no SYSTEMS.md with a "## Close inputs" section).

What it reads from SYSTEMS.md's "## Close inputs" lines ("- Name: value"; lists separated by
semicolons):

- ERP: the ledger system. Only Sage Intacct has a puller; anything else is STALE. Required.
- ERP environment: PROD (default) or SANDBOX; SANDBOX reads the _SANDBOX credential variables.
- ERP API user: the API user when neither the environment nor the settings name one.
- Ledger pull: where the pull lives, relative to the period folder (default work/source).
- Headerless line creators, Headerless line journals: integrations whose lines the API returns
  without a header. Their lines are a known gap, reported as a note; any other line without a
  header fails the pull.
- Trial balance history, Trial balance bridge, Chart of accounts: the inputs of
  trial_balance.py other than the current window, relative to the Month-End folder or
  absolute. When all three are set the trial balance is rebuilt with each pull.
- Trial balance pull from: yyyy-mm-dd, the earliest date the trial balance's own lines pull may
  start. Default: the first day of the month twelve months before the period.

The pull. The period's JE headers, JE lines, AP bill lines and AR invoice lines go into a
staging folder beside the pull, from Intacct (--live, the default) or from files a person
exported (--offline-from DIR). Gates run on the staging copy: rows tie to the server's
total, one vintage, every line has a header or is a known gap, and the month has JE lines.
Only when all pass are the current pull files moved to <pull>/superseded-<date-time>/
(never deleted) and the new ones put in place with a new pulled.md. On any failure the
existing pull is untouched.

The trial balance. Its current window is one JE lines pull from the day after the history
(or from "Trial balance pull from" when later) through the period end, gated like the other
objects; the period's lines file is sliced from it. The bridge fills only the dates between
the history and the window start, and when it does not cover them the trial balance is not
rebuilt and the first line says why. Offline, a lines-window-<yyyy-mm>.json in the export is
the window. When a trial balance of the same period was in place, the first line and
pulled.md say how many accounts changed and how far YTD net income moved.

Credentials come from the environment only (SAGE_INTACCT_CLIENT_ID, SAGE_INTACCT_CLIENT_SECRET,
SAGE_INTACCT_COMPANY_ID, SAGE_INTACCT_API_USER; see _common.py) and are scrubbed from every
message. The live path makes only the token request and queries.

Example:
    python3 month_end_pull.py "Month-End" --period 2026-09 --live
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from _common import (OBJECTS, IntacctSession, NoCredentials, credentials, gate_snapshot, ln, load_snapshot,
                     period_end, pull_live, resolve_sources, server_total, shift_period, write_snapshot)

HERE = Path(__file__).resolve().parent
SECTION = "Close inputs"
DEFAULT_PULL = "work/source"
PULLED_OBJECTS = ("headers", "lines", "ap_bill_lines", "ar_invoice_lines")
WINDOW = "tb_lines"
DESCRIBE = {"headers": "JE headers", "lines": "JE lines", "ap_bill_lines": "AP bill lines",
            "ar_invoice_lines": "AR invoice lines", WINDOW: "JE lines of the TB window"}
WINDOW_MONTHS = 12
TB_FIELDS = {"history": "Trial balance history", "bridge": "Trial balance bridge", "accounts": "Chart of accounts"}


class BadArgument(Exception):
    """A bad argument or a folder that is not a Month-End folder (exit 2)."""


class Stale(Exception):
    """A soft problem: the existing pull stays and the caller is told why (exit 0)."""


def file_name(name, period):
    return f"lines-window-{period}.json" if name == WINDOW else f"{name.replace('_', '-')}-{period}.json"


def day_after(iso):
    return (date.fromisoformat(iso) + timedelta(days=1)).isoformat()


def day_before(iso):
    return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()


def line_date(row):
    return ln(row, "date")[:10]


def money(value):
    return f"{value:,.2f}"


def specs():
    return {name: OBJECTS[name] for name in PULLED_OBJECTS}


# --- the folder's settings --------------------------------------------------------------------


def read_settings(folder):
    """The "- Name: value" lines of SYSTEMS.md's ## Close inputs, keyed by lower-cased name."""
    if not folder.is_dir():
        raise BadArgument(f"{folder} is not a folder")
    systems = folder / "SYSTEMS.md"
    if not systems.is_file():
        raise BadArgument(f"{folder} is not a Month-End folder: no SYSTEMS.md")
    m = re.search(rf"^##\s+{SECTION}\s*$(.*?)(?=^#{{1,2}}\s|\Z)", systems.read_text(encoding="utf-8"),
                  re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not m:
        raise BadArgument(f"{folder} is not a Month-End folder: SYSTEMS.md has no '## {SECTION}' section")
    out = {}
    for line in m.group(1).splitlines():
        field = re.match(r"^\s*[-*]\s+([^:]+?):\s*(.*?)\s*$", line)
        if field:
            out[field.group(1).strip().lower()] = field.group(2).strip().strip("`")
    return out


def listed(value):
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def folder_path(folder, value):
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else folder / path


def existing_pull_date(pull_dir, period):
    """The date of the pull in place: pulled.md's "Pulled yyyy-mm-dd", else the lines file's
    modification date, else ''."""
    pulled = pull_dir / "pulled.md"
    if pulled.is_file():
        m = re.search(r"\bPulled (\d{4}-\d{2}-\d{2})", pulled.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1)
    lines = pull_dir / file_name("lines", period)
    return datetime.fromtimestamp(lines.stat().st_mtime).date().isoformat() if lines.is_file() else ""


# --- the ERP side -----------------------------------------------------------------------------


class ReadOnlySession:
    """Exposes query and nothing else, so the pull cannot reach any other endpoint."""

    def __init__(self, session):
        self._session = session

    def query(self, object_name, fields, filters=None, order_by=None, **kwargs):
        return self._session.query(object_name, fields, filters=filters, order_by=order_by, **kwargs)


def intacct_session(environment, api_user):
    """A read-only session and the values to scrub from any message."""
    try:
        cid, secret, company, user = credentials(environment, api_user)
    except NoCredentials as exc:
        raise Stale(str(exc)) from None
    return ReadOnlySession(IntacctSession(cid, secret, company, user)), [cid, secret, company]


def scrub(message, secrets):
    text = str(message or "")
    for value in secrets:
        if value and len(value) >= 4:
            text = text.replace(value, "***")
    return (text.strip().splitlines() or ["unknown error"])[0][:300]


def entry(name, obj, path, rows, total, pulled_at, sources=None, **more):
    return {"name": name, "object": obj, "source": str(path), "sources": [str(s) for s in sources or [path]],
            "rows": rows, "server_total": None if total is None else int(total), "pulled_at": pulled_at, **more}


def offline_objects(source, staging, period):
    """Each object's export copied into staging under its pull name: <object>-<period>.json,
    else the first file with the object's prefix."""
    found = []
    for name, spec in specs().items():
        exact = source / file_name(name, period)
        paths = [exact] if exact.is_file() else resolve_sources(source, name)
        if not paths:
            raise Stale(f"gate missing_object failed: no {DESCRIBE[name]} snapshot in {source}")
        rows, meta = load_snapshot(paths[0])
        target = write_snapshot(staging / file_name(name, period), rows, meta)
        found.append(entry(name, str(meta.get("object") or spec["object"]), target, len(rows), server_total(meta),
                           str(meta.get("pulled-at") or meta.get("pulled_at") or ""), [paths[0]]))
    return found


def pull_window(session, start, end, staging, period, environment):
    """One query of JE lines from `start` through `end`: the trial balance's window."""
    spec = OBJECTS["lines"]
    field = spec["date_field"]
    filters = [{"$gte": {field: start}}, {"$lte": {field: end}}]
    rows, total = session.query(spec["object"], spec["fields"], filters=filters, order_by=[{field: "asc"}])
    meta = {"pulled-at": datetime.now(timezone.utc).isoformat(), "object": spec["object"], "fields": spec["fields"],
            "filters": filters, "row-count": len(rows), "server-total-count": total, "environment": environment}
    path = write_snapshot(staging / file_name(WINDOW, period), rows, meta)
    return entry(WINDOW, spec["object"], path, len(rows), total, meta["pulled-at"])


def slice_period(window, staging, period):
    """The period's lines file cut from the window pull. Its server total is the slice's count
    only when the window's count tied to the server."""
    rows, meta = load_snapshot(window["source"])
    lo, hi = f"{period}-01", period_end(period)
    mine = [r for r in rows if lo <= line_date(r) <= hi]
    tied = window["server_total"] is not None and window["server_total"] == len(rows)
    field = OBJECTS["lines"]["date_field"]
    out = dict(meta, filters=[{"$gte": {field: lo}}, {"$lte": {field: hi}}], **{
        "row-count": len(mine), "server-total-count": len(mine) if tied else None,
        "sliced-from": {"filters": meta.get("filters"), "row-count": len(rows),
                        "server-total-count": window["server_total"]}})
    path = write_snapshot(staging / file_name("lines", period), mine, out)
    return entry("lines", window["object"], path, len(mine), out["server-total-count"], window["pulled_at"],
                 sliced=True)


def filter_range(meta):
    """The ($gte, $lte) dates of a snapshot's query filters, or ('', '')."""
    lo = hi = ""
    for item in meta.get("filters") or []:
        for op, value in (item.items() if isinstance(item, dict) else []):
            if isinstance(value, dict) and value:
                when = str(next(iter(value.values())))[:10]
                lo, hi = (when if op == "$gte" else lo), (when if op == "$lte" else hi)
    return lo, hi


def offline_window(source, staging, period, history_through):
    """A person's export of the trial balance window, from the day after the history. None when
    the export has none."""
    path = source / file_name(WINDOW, period)
    if not path.is_file():
        return None
    rows, meta = load_snapshot(path)
    lo, _ = filter_range(meta)
    dates = [d for d in (line_date(r) for r in rows) if d]
    start = max(lo or (min(dates) if dates else f"{period}-01"), day_after(history_through))
    kept = [r for r in rows if start <= line_date(r) <= period_end(period)]
    target = write_snapshot(staging / file_name(WINDOW, period), kept, meta)
    total = server_total(meta)
    return entry(WINDOW, str(meta.get("object") or OBJECTS["lines"]["object"]), target, len(kept),
                 None if total is None or len(kept) != len(rows) else total,
                 str(meta.get("pulled-at") or meta.get("pulled_at") or ""), [path], start=start)


def run_gates(objects, counts_required, creators, journals):
    findings = gate_snapshot(objects, 1.0, counts_required, creators, journals)
    lines = next((o for o in objects if o["name"] == "lines"), None)
    if lines is not None and lines["rows"] == 0:
        findings.append({"gate": "lines_present", "severity": "error", "object": "lines",
                         "detail": "the pull returned no journal-entry lines for the month"})
    return findings


# --- the trial balance ------------------------------------------------------------------------


def plan_trial_balance(settings, folder, period):
    """Decide the trial balance window before anything is pulled."""
    named = {k: folder_path(folder, settings.get(v.lower(), "")) for k, v in TB_FIELDS.items()}
    unset = [k for k, v in named.items() if v is None]
    if unset:
        return {"ok": False, "inputs": named,
                "note": "not rebuilt: SYSTEMS.md sets no " + ", ".join(f"'{TB_FIELDS[k]}'" for k in unset)}
    missing = [f"{k} {v}" for k, v in named.items() if not v.is_file()]
    if missing:
        return {"ok": False, "inputs": named, "note": "not rebuilt: file not found: " + "; ".join(missing)}
    configured = settings.get("trial balance pull from", "")
    if configured and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", configured):
        return {"ok": False, "inputs": named,
                "note": f"not rebuilt: 'Trial balance pull from' {configured!r} is not yyyy-mm-dd"}
    try:
        dates = [d for d in (line_date(r) for r in load_snapshot(named["history"])[0]) if d]
    except Exception as exc:  # a trial balance problem is reported, never raised
        return {"ok": False, "inputs": named, "note": f"not rebuilt: history unreadable: {type(exc).__name__}"}
    if not dates:
        return {"ok": False, "inputs": named, "note": "not rebuilt: the history file has no dated lines"}
    floor = configured or f"{shift_period(period, -WINDOW_MONTHS)}-01"
    start = max(day_after(max(dates)), floor)
    if start > period_end(period):
        return {"ok": False, "inputs": named, "note": f"not rebuilt: the history runs to {max(dates)}, past the period"}
    return {"ok": True, "inputs": named, "history_through": max(dates), "start": start, "note": ""}


def bridge_gap(plan, start):
    """'' when the bridge covers every date between the history and the window start, else why
    the trial balance cannot be rebuilt. The bridge's range is its query filters when it
    records them, else the months of its first and last lines."""
    gap_lo, gap_hi = day_after(plan["history_through"]), day_before(start)
    if gap_lo > gap_hi:
        return ""
    rows, meta = load_snapshot(plan["inputs"]["bridge"])
    lo, hi = filter_range(meta)
    if lo and hi:
        covered, how = lo <= gap_lo and hi >= gap_hi, "its query filters"
    else:
        dates = sorted(d for d in (line_date(r) for r in rows) if d)
        lo, hi = (dates[0], dates[-1]) if dates else ("none", "none")
        covered, how = bool(dates) and lo[:7] <= gap_lo[:7] and hi[:7] >= gap_hi[:7], "the months of its lines"
    if covered:
        return ""
    return (f"not rebuilt: {gap_lo}..{gap_hi} lies between the history (through {plan['history_through']}) and "
            f"the pull window (from {start}) and the bridge does not cover it (bridge {lo}..{hi}, by {how}); "
            f"set '- Trial balance pull from: {gap_lo}' or refresh the bridge")


def build_trial_balance(plan, window, staging, period, label):
    """Rebuild the trial balance into staging by running trial_balance.py beside this script."""
    named = plan["inputs"]
    if not plan["ok"] or window.get("note"):
        return {"built": False, "inputs": named, "note": plan["note"] or window["note"]}
    as_of = period_end(period)
    try:
        done = subprocess.run(
            [sys.executable, str(HERE / "trial_balance.py"), "--as-of", as_of, "--history", str(named["history"]),
             "--bridge", str(named["bridge"]), "--current", str(window["path"]), "--current-from", window["start"],
             "--accounts", str(named["accounts"]), "--out", str(staging / f"trial-balance-{period}.xlsx"),
             "--label", f"{as_of} {label}", "--format", "json"], capture_output=True, text=True, timeout=900)
        result = json.loads(done.stdout) if done.returncode in (0, 1) else None
        reason = "" if result else (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
        if result:
            result.pop("written", None)
            (staging / f"trial-balance-{period}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
            accounts = sum(1 for r in result["rows"] if r["Account"] != "RE-PRIOR")
    except Exception as exc:  # a trial balance problem is reported, never raised
        result, reason = None, f"{type(exc).__name__}: {exc}"
    if not result:
        return {"built": False, "inputs": named, "note": f"not rebuilt: {reason[:200]}"}
    return {"built": True, "inputs": named, "as_of": as_of, "accounts": accounts, "balanced": result["balanced"],
            "debits": result["debits"], "credits": result["credits"], "ytd_net_income": result["ytd_net_income"],
            "lines": result["lines"], "windows": result.get("windows", {}), "rows": result["rows"],
            "window": window,
            "note": f"rebuilt ({accounts} accounts, " + ("balanced" if result["balanced"] else "DOES NOT BALANCE") + ")"}


def compare_previous(previous, tbs):
    """How far the rebuilt trial balance moved from the one it replaces, or None."""
    if not tbs.get("built") or not previous.is_file():
        return None
    try:
        old = json.loads(previous.read_text(encoding="utf-8"))
        before = {str(r["Account"]): float(r["Ending balance"]) for r in old["rows"]}
        old_ni = float(old["ytd_net_income"])
    except Exception:  # an unreadable old trial balance is reported, never raised
        return {"unreadable": True}
    after = {str(r["Account"]): float(r["Ending balance"]) for r in tbs["rows"]}
    changed = sorted(a for a in set(before) | set(after) if abs(after.get(a, 0.0) - before.get(a, 0.0)) >= 0.005)
    return {"changed": len(changed), "accounts": changed, "old_ni": round(old_ni, 2),
            "new_ni": tbs["ytd_net_income"], "ni_change": round(tbs["ytd_net_income"] - old_ni, 2)}


def change_text(change):
    if change is None:
        return ""
    if change.get("unreadable"):
        return "the previous TB could not be read for comparison"
    if not change["changed"] and abs(change["ni_change"]) < 0.005:
        return "vs the previous TB: no account changed"
    return (f"vs the previous TB: {change['changed']} account(s) changed, YTD net income "
            f"{money(change['old_ni'])} -> {money(change['new_ni'])} ({change['ni_change']:+,.2f})")


# --- pulled.md --------------------------------------------------------------------------------


def write_pulled_md(path, *, folder, period, label, mode, environment, source_dir, objects, findings, tbs,
                    pulled_on, superseded, counts_required, extra):
    by = {o["name"]: o for o in objects}
    stamps = sorted(o["pulled_at"][11:16] for o in objects + extra if len(o.get("pulled_at") or "") >= 16)
    window = f"objects between {stamps[0]} and {stamps[-1]} UTC" if stamps else "no pull time in the snapshots"
    end = period_end(period)
    out = [f"# Pulled data, {period} ({'PRELIMINARY, period may still be open' if label == 'PRELIMINARY' else 'FINAL'})",
           ""]
    if mode == "live":
        out.append(f"Read-only pull from Sage Intacct {environment} by `month_end_pull.py`. No write, import, post "
                   f"or delete call was made. Pulled {pulled_on} ({window}). LABEL: {label}.")
    else:
        out.append(f"Offline pull from snapshot files in `{source_dir}` by `month_end_pull.py`; the ERP was not "
                   f"called. Pulled {pulled_on} ({window}). LABEL: {label}.")
    if label == "PRELIMINARY":
        out.append(f"The period ended {end}; entries may still change.")
    out += ["", "## Files in this folder", "| File | Rows | Source object |", "|---|---|---|"]
    for name in PULLED_OBJECTS:
        o = by[name]
        sliced = ", sliced from the trial balance window pull" if o.get("sliced") else ""
        out.append(f"| {file_name(name, period)} | {o['rows']} | {o['object']}, by {OBJECTS[name]['date_field']}{sliced} |")
    if tbs["built"]:
        out.append(f"| trial-balance-{period}.xlsx / .json | {tbs['accounts']} accounts | computed, see below |")
    parts = [f"{DESCRIBE[n]} {by[n]['rows']:,} of {by[n]['server_total']:,}" if by[n]["server_total"] is not None
             else f"{DESCRIBE[n]} {by[n]['rows']:,} (no server total)" for n in PULLED_OBJECTS]
    if all(o["server_total"] is not None and o["server_total"] == o["rows"] for o in objects + extra):
        tie = "Row count equals server totalCount for every object"
    else:
        tie = "Row counts and server totals differ" if counts_required else \
            "Server totals were not required for this offline pull"
    out += ["", "## Server totals", f"One range per object, {period}-01 to {end}. {tie}: " + "; ".join(parts) + "."]
    tb_window = tbs.get("window") or {}
    for o in extra:
        counted = f"{o['rows']:,} of {o['server_total']:,}" if o["server_total"] is not None \
            else f"{o['rows']:,} (no server total)"
        out.append(f"The trial balance window, one range {tb_window.get('start') or o.get('start') or '?'} to {end}: "
                   f"{DESCRIBE[o['name']]} {counted}. It is the trial balance's input only and was not kept in "
                   "this folder." + (" The period's JE lines file is that pull's slice of the month."
                                     if by["lines"].get("sliced") else ""))
    how = "--live" if mode == "live" else f"--offline-from {source_dir}"
    out += ["", "## Commands",
            f"- Pull: `month_end_pull.py {folder} --period {period} {how}` (the erp-ledger-pull skill's scripts)."]
    inputs = tbs.get("inputs") or {}
    if tbs["built"]:
        w = tbs["windows"]
        out.append(
            f"- Trial balance: `trial_balance.py --as-of {tbs['as_of']} --history {inputs['history']} "
            f"--bridge {inputs['bridge']} --current <the window pull, {file_name(WINDOW, period)}, staging only> "
            f"--current-from {tb_window.get('start', '')} --accounts {inputs['accounts']} --format xlsx`. Windows: "
            f"history through {w.get('history_through', '?')}; bridge {w.get('bridge_window', '?')} "
            f"({w.get('bridge_used', 0):,} lines used); current {w.get('current_window', '?')}. Built from posted "
            f"lines: {tbs['lines']:,} lines, debits {money(tbs['debits'])} = credits {money(tbs['credits'])}, "
            f"balanced {tbs['balanced']}, YTD net income {money(tbs['ytd_net_income'])}.")
    elif tbs["note"].startswith("not rebuilt: SYSTEMS.md sets no"):
        out.append(f"- Trial balance: {tbs['note']}. Set '- Trial balance history:', '- Trial balance bridge:' and "
                   "'- Chart of accounts:' under ## Close inputs in SYSTEMS.md to rebuild it with each pull.")
    else:
        out.append(f"- Trial balance: {tbs['note']}.")
    notes = [f"- {f['gate']}: {f['detail']}" for f in findings
             if f["severity"] != "error" and f["gate"] != "lines_have_headers"]
    orphans = [f for f in findings if f["gate"] == "lines_have_headers"]
    if orphans:
        count = sum(int(m.group(1)) for f in orphans if (m := re.search(r"has (\d+) line", f["detail"])))
        notes.insert(0, f"- {count} line(s) in {len(orphans)} entr{'y' if len(orphans) == 1 else 'ies'} have no "
                        "header: a known integration creator or journal (SYSTEMS.md 'Headerless line ...'). "
                        "Lines are present; headers are not.")
    if tbs["built"] and not tbs["balanced"]:
        notes.append("- The trial balance does NOT balance; treat it as a stop and report it.")
    if not tbs["built"]:
        notes.append(f"- Trial balance {tbs['note']}.")
    change = tbs.get("change")
    if change_text(change):
        accounts = (change or {}).get("accounts") or []
        detail = (f" Accounts: {', '.join(accounts[:20])}" + (" and more." if len(accounts) > 20 else ".")
                  if accounts else "")
        notes.append(f"- Trial balance {change_text(change)}.{detail}")
    if superseded:
        notes.append(f"- The previous pull's files were moved to `{superseded}/`.")
    out += ["", "## Gaps and notes"] + (notes or ["- None."])
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --- the refresh ------------------------------------------------------------------------------


def unique_dir(parent, name):
    path, n = parent / name, 2
    while path.exists():
        path, n = parent / f"{name}-{n}", n + 1
    return path


def refresh(folder, period, live, offline_from, label, preliminary_days, now, session_factory=None):
    """One refresh. Returns {'status': 'FRESH'|'STALE', 'line': first line, 'details': [...]}.
    `session_factory(environment, api_user)` returns (session, secrets); tests pass a fake."""
    settings = read_settings(folder)
    pull_dir = folder / period[:4] / period / settings.get("ledger pull", DEFAULT_PULL)
    previous = existing_pull_date(pull_dir, period)

    def stale(reason, details=None):
        using = f"using the pull of {previous}" if previous else "using the pull of none (no earlier pull exists)"
        return {"status": "STALE", "line": f"STALE: {reason}; {using}", "details": details or []}

    erp = settings.get("erp", "")
    if not erp:
        return stale("SYSTEMS.md names no ERP (add '- ERP: Sage Intacct' under ## Close inputs)")
    if re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", erp)).strip().lower() != "sage intacct":
        return stale(f"no puller for {erp}")
    environment = (settings.get("erp environment") or "PROD").strip().upper()
    if not label:
        days_since = (now.date() - date.fromisoformat(period_end(period))).days
        label = "PRELIMINARY" if days_since < preliminary_days else "FINAL"

    secrets, session = [], None
    if live:
        try:
            session, secrets = (session_factory or intacct_session)(environment, settings.get("erp api user", ""))
        except Stale as exc:
            return stale(str(exc))
        except Exception as exc:  # trouble reaching the ERP is a soft problem
            return stale(f"no Sage Intacct session: {type(exc).__name__}: {scrub(exc, secrets)}")

    plan = plan_trial_balance(settings, folder, period)
    gap = ""
    if plan["ok"] and live:
        try:
            gap = bridge_gap(plan, plan["start"])
        except Exception as exc:  # a trial balance problem is reported, never raised
            gap = f"not rebuilt: the bridge is unreadable: {type(exc).__name__}"

    created = [p for p in (pull_dir.parent, *pull_dir.parent.parents) if not p.exists() and folder in p.parents]
    stamp = now.strftime("%Y-%m-%d-%H%M")
    pull_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = unique_dir(pull_dir.parent, f".pull-staging-{stamp}")
    staging.mkdir(parents=True)
    try:
        try:
            window, extra = ({"note": gap} if gap else {}), []
            if live and plan["ok"] and not gap:
                objects = pull_live(session, period, 0, staging, specs(),
                                    [n for n in PULLED_OBJECTS if n != "lines"], environment, now.date().isoformat())
                wide = pull_window(session, plan["start"], period_end(period), staging, period, environment)
                objects.insert(PULLED_OBJECTS.index("lines"), slice_period(wide, staging, period))
                extra, window = [wide], {"path": wide["source"], "start": plan["start"]}
            elif live:
                objects = pull_live(session, period, 0, staging, specs(), list(PULLED_OBJECTS), environment,
                                    now.date().isoformat())
            else:
                objects = offline_objects(offline_from, staging, period)
                if plan["ok"]:
                    try:
                        wide = offline_window(offline_from, staging, period, plan["history_through"])
                        if wide is None or wide["start"] > plan["start"]:
                            gap = (f"not rebuilt: the export has no {file_name(WINDOW, period)} covering "
                                   f"{plan['start']}..{period_end(period)}; the bridge alone can miss entries "
                                   "booked late into earlier months")
                        else:
                            extra, window = [wide], {"path": wide["source"], "start": wide["start"]}
                            gap = bridge_gap(plan, window["start"])
                    except Exception as exc:  # a trial balance problem is reported, never raised
                        gap = f"not rebuilt: the TB window or bridge is unreadable: {type(exc).__name__}"
                    window = {"note": gap} if gap else window
        except Stale:
            raise
        except Exception as exc:  # network, auth or API trouble is a soft problem
            raise Stale(f"the pull failed: {type(exc).__name__}: {scrub(exc, secrets)}") from None

        findings = run_gates(extra + objects, live, listed(settings.get("headerless line creators", "")),
                             listed(settings.get("headerless line journals", "")))
        details = [f"  {f['severity'].upper():7} {f['gate']:20} {f['object']:16} {scrub(f['detail'], secrets)}"
                   for f in findings]
        errors = [f for f in findings if f["severity"] == "error"]
        if errors:
            more = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
            raise Stale(f"gate {errors[0]['gate']} failed on {errors[0]['object']}: "
                        f"{scrub(errors[0]['detail'], secrets)}{more}", details)

        tbs = build_trial_balance(plan, window, staging, period, label)
        tbs["change"] = compare_previous(pull_dir / f"trial-balance-{period}.json", tbs)

        superseded = ""
        pull_dir.mkdir(parents=True, exist_ok=True)
        owned = [file_name(n, period) for n in PULLED_OBJECTS] + [
            f"trial-balance-{period}.json", f"trial-balance-{period}.xlsx", "pulled.md"]
        current = [pull_dir / name for name in owned if (pull_dir / name).is_file()]
        if current:
            target = unique_dir(pull_dir, f"superseded-{stamp}")
            target.mkdir()
            for path in current:
                shutil.move(str(path), str(target / path.name))
            superseded = target.name
        for path in sorted(staging.iterdir()):
            if path.name != file_name(WINDOW, period):  # the window is the trial balance's input only
                shutil.move(str(path), str(pull_dir / path.name))
        pulled_on = now.date().isoformat()
        write_pulled_md(pull_dir / "pulled.md", folder=folder, period=period, label=label,
                        mode="live" if live else "offline", environment=environment,
                        source_dir=str(offline_from or ""), objects=objects, findings=findings, tbs=tbs,
                        pulled_on=pulled_on, superseded=superseded, counts_required=live, extra=extra)
    except Stale as exc:
        shutil.rmtree(staging, ignore_errors=True)
        for path in created:  # deepest first: folders this run made, only when still empty
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        return stale(str(exc.args[0]), exc.args[1] if len(exc.args) > 1 else [])
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    counts = ", ".join(f"{DESCRIBE[o['name']]} {o['rows']:,}" for o in objects)
    tb_text = f"TB {tbs['note']}" + (f"; {change_text(tbs['change'])}" if change_text(tbs.get("change")) else "")
    if superseded:
        details.append(f"  previous pull moved to {superseded}/")
    details.append(f"  wrote {pull_dir / 'pulled.md'}")
    return {"status": "FRESH", "line": f"FRESH: pulled {pulled_on} {counts}; {label}; {tb_text}", "details": details}


def main(argv=None):
    p = argparse.ArgumentParser(description="Refresh one month's read-only ledger pull in a Month-End folder.")
    p.add_argument("folder", help="the Month-End folder")
    p.add_argument("--period", default="", help="yyyy-mm; default the month before today")
    p.add_argument("--live", action="store_true", help="pull from the ERP, read only (the default)")
    p.add_argument("--offline-from", default=None, help="take the snapshot files from this folder instead")
    p.add_argument("--label", type=str.upper, choices=["PRELIMINARY", "FINAL"], default=None,
                   help="force the label; default PRELIMINARY within --preliminary-days of the period end")
    p.add_argument("--preliminary-days", type=int, default=15)
    p.add_argument("--today", default="", help=argparse.SUPPRESS)  # yyyy-mm-dd, for tests
    args = p.parse_args(argv)
    try:
        offline = Path(args.offline_from).expanduser() if args.offline_from else None
        if args.live and offline is not None:
            raise BadArgument("pass --live or --offline-from, not both")
        if offline is not None and not offline.is_dir():
            raise BadArgument(f"--offline-from {offline} is not a folder")
        try:
            today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
        except ValueError:
            raise BadArgument(f"--today {args.today!r} is not yyyy-mm-dd") from None
        now = datetime.combine(today, datetime.now(timezone.utc).time(), timezone.utc)
        if args.period and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args.period):
            raise BadArgument(f"--period {args.period!r} is not yyyy-mm")
        period = args.period or shift_period(f"{today:%Y-%m}", -1)
        result = refresh(Path(args.folder).expanduser(), period, offline is None, offline, args.label or "",
                         args.preliminary_days, now)
    except BadArgument as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result["line"])
    for line in result["details"]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
