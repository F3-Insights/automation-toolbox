#!/usr/bin/env python3
"""The month-end accruals of month-end-accrual-drafts, read from a Month-End folder.

    python3 scripts/accruals.py config FOLDER
    python3 scripts/accruals.py done FOLDER --period yyyy-mm --accrual cc|vendor
    python3 scripts/accruals.py inputs FOLDER --period yyyy-mm --accrual cc|vendor
    python3 scripts/accruals.py scan FOLDER --period yyyy-mm [--out DIR]
    python3 scripts/accruals.py build FOLDER --period yyyy-mm --accrual cc|vendor [--out DIR]
                                [--ignore-done] [--card-report FILE] [--decisions FILE]

FOLDER is the Month-End folder. Everything specific to
the entity is read from it: the accounts, maps and lists from METADATA_FIELDS.md's
"## Accruals" section, where the inputs are from SYSTEMS.md's "## Close inputs" section, and
the ledger data from each period's read-only pull. The contract is rules.md beside this skill.

- config prints what the two sections say, as JSON, or stops naming what is missing.
- done answers "is this accrual already done for the period?" from the data: an entry in the
  ledger pull (posted, or entered as a draft) or an import file already in the period folder.
- inputs lists the inputs the build needs and which are missing.
- scan runs the vendor accrual's missing-accrual scan on its own and writes nothing: vendors whose
  expense recurs in the ledger history and have nothing booked or billed for the period.
- build runs the done check, finds the inputs, and makes the import file with the toolbox
  commands (card-export, cc-accrual, service-period-accrual, je-import, je-import-check). It
  writes `<period folder>/<import file name>`, or into --out for a trial run, and never
  overwrites a file. STATE is Posted: a person uploads the file, and that upload is the
  human review. Agents never upload or post.

Every command prints one JSON object. Exit 0 when the work is done or was built, 4 when an
input is missing (the caller records a Waiting on row), 3 when the build refuses (a file is
already there, the folder is not set up), 1 when a command or the lint failed, 2 on bad
arguments. Standard library only. The commands it runs are plain scripts run with the same
python3: card_export.py, cc_accrual.py and service_period_accrual.py beside this file, and
je_import.py and je_import_check.py in the month-end-journal-entry skill, at
~/.claude/skills/month-end-journal-entry/scripts/ (or under the skills folder
ACCRUALS_SKILLS_DIR names, for tests and unlinked checkouts).
"""

from __future__ import annotations

import argparse
import calendar
import csv
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

ACCRUALS = ("cc", "vendor")
SECTION_FIELDS = "Accruals"
SECTION_INPUTS = "Close inputs"
DEFAULT_FILE_NAME = "SAGE upload - {month} {year} {name} (reversing) DRAFT.csv"
JE_FOLDER = "journal-entries"  # where a month-end folder keeps its draft entries, when it has one


class Refused(Exception):
    """The folder or the request is not in a state the build can act on (exit 3)."""


class Bad(Exception):
    """An argument or a file is wrong (exit 2)."""


# ---------------------------------------------------------------------------------------------
# Periods


def check_period(period: str) -> str:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period or ""):
        raise Bad(f"--period {period!r} is not yyyy-mm")
    return period


def shift(period: str, months: int) -> str:
    year, month = (int(x) for x in period.split("-"))
    index = year * 12 + (month - 1) + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def period_end(period: str) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{period}-{calendar.monthrange(year, month)[1]:02d}"


def period_folder(folder: Path, period: str) -> Path:
    return folder / period[:4] / period


def month_words(period: str) -> Tuple[str, str]:
    year, month = (int(x) for x in period.split("-"))
    return calendar.month_name[month], str(year)


# ---------------------------------------------------------------------------------------------
# Reading the engagement folder


def section(text: str, title: str, level: int = 2) -> Optional[str]:
    """The body of a `## title` (or `### title`) section, or None."""
    marks = "#" * level
    m = re.search(rf"^{marks}\s+{re.escape(title)}\s*$(.*?)(?=^#{{1,{level}}}\s|\Z)", text,
                  re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else None


def fields(body: str) -> Dict[str, str]:
    """`- Name: value` lines, keyed by the lower-cased name."""
    out: Dict[str, str] = {}
    for line in body.splitlines():
        m = re.match(r"^\s*[-*]\s+([^:]+?):\s*(.*?)\s*$", line)
        if m:
            out[m.group(1).strip().lower()] = m.group(2).strip().strip("`")
    return out


def listed(value: str) -> List[str]:
    return [part.strip() for part in re.split(r";", value or "") if part.strip()]


def table(body: str) -> List[Dict[str, str]]:
    """The first markdown table in a section body, as {header: cell} rows."""
    rows = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("|")]
    if len(rows) < 2:
        return []
    split = lambda ln: [c.strip() for c in ln.strip().strip("|").split("|")]  # noqa: E731
    head = split(rows[0])
    out = []
    for ln in rows[2:]:
        cells = split(ln)
        out.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(head)})
    return out


def need(values: Dict[str, str], name: str, where: str) -> str:
    value = values.get(name.lower(), "")
    if not value:
        raise Refused(f"{where} has no '- {name}:' line; the accrual cannot guess it")
    return value


def account_cell(text: str) -> Tuple[str, str]:
    """'5400 Travel - COGS' -> ('5400', 'Travel - COGS')."""
    parts = text.strip().split(None, 1)
    return (parts[0], parts[1] if len(parts) > 1 else "") if parts else ("", "")


def label_key(label: str) -> str:
    """The form a department label is matched in: upper case, spaces trimmed and single."""
    return " ".join(str(label or "").split()).upper()


def by_department(text: str) -> Dict[str, Dict[str, str]]:
    """'COGS=5400 Travel - COGS; G&A=6400 Travel' -> {'COGS': {'account': ..., 'account_name': ...}}."""
    out = {}
    for part in listed(text):
        key, _, cell = part.partition("=")
        o_account, o_name = account_cell(cell)
        if key.strip() and o_account:
            out[key.strip().upper()] = {"account": o_account, "account_name": o_name}
    return out


def department_labels(body: Optional[str]) -> Optional[Dict[str, str]]:
    """The '### Department labels' table (Label | Department), or None when the folder has none.
    A label given two different departments is refused rather than settled by row order."""
    if body is None:
        return None
    out: Dict[str, str] = {}
    for row in table(body):
        label, dept = label_key(row.get("Label", "")), row.get("Department", "").strip().upper()
        if not label or not dept:
            continue
        if out.get(label, dept) != dept:
            raise Refused(f"METADATA_FIELDS.md ### Department labels gives {label!r} two departments "
                          f"({out[label]} and {dept})")
        out[label] = dept
    return out


def merchant_override_rows(body: Optional[str]) -> List[Dict[str, Any]]:
    """The '### Merchant overrides' table (Merchant pattern | Category | Account | By department),
    in order: the first pattern that matches a merchant wins, before the card account map."""
    out: List[Dict[str, Any]] = []
    for row in table(body or ""):
        pattern = row.get("Merchant pattern", "").strip().strip("`")
        if not pattern:
            continue
        account, name = account_cell(row.get("Account", ""))
        overrides = by_department(row.get("By department", ""))
        if not account and not overrides:
            raise Refused(f"METADATA_FIELDS.md ### Merchant overrides: {pattern!r} has no account")
        entry: Dict[str, Any] = {"pattern": pattern, "category": row.get("Category", "").strip().upper(),
                                 "account": account, "account_name": name}
        if overrides:
            if account:
                overrides["default"] = {"account": account, "account_name": name}
            entry["account_by_department"] = overrides
        out.append(entry)
    return out


def setting_number(values: Dict[str, str], name: str, default: float, where: str, whole: bool = False):
    """An optional number setting: its default when the line is absent or blank, refused when it
    is not a number (or not a whole number of at least 1, for a count of months)."""
    raw = values.get(name.lower(), "").replace(",", "").strip()
    if not raw:
        return int(default) if whole else float(default)
    try:
        value = float(raw)
    except ValueError:
        raise Refused(f"{where}: '- {name}: {raw}' is not a number")
    if whole and (value != int(value) or value < 1):
        raise Refused(f"{where}: '- {name}: {raw}' is not a whole number of at least 1")
    if value < 0:
        raise Refused(f"{where}: '- {name}: {raw}' is negative")
    return int(value) if whole else value


def excluded_vendors(value: str, body: str) -> List[Tuple[str, str]]:
    """'BANK CARDS (accrued by the card accrual); OLD VENDOR' -> [(key, reason)]. The reason is
    the parenthesis after the name, else the first paragraph of the section that names the
    vendor, else a plain statement that the settings give none."""
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body or "")]
    paragraphs = [p for p in paragraphs if p and not p.lstrip().startswith(("-", "*", "|", "#"))]
    out = []
    for part in listed(value):
        m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", part)
        key, reason = ((m.group(1), m.group(2).strip()) if m else (part, ""))
        key = " ".join(key.split()).upper()
        if not key:
            continue
        if not reason:
            reason = next((p for p in paragraphs if key in p.upper()), "")
        out.append((key, reason or "listed under Excluded vendors; the settings give no reason"))
    return out


def load_config(folder: Path) -> Dict[str, Any]:
    folder = Path(folder)
    meta_path, systems_path = folder / "METADATA_FIELDS.md", folder / "SYSTEMS.md"
    for path in (meta_path, systems_path):
        if not path.is_file():
            raise Refused(f"{path.name} not found in {folder}; set the engagement folder up first")
    meta = meta_path.read_text(encoding="utf-8")
    systems = systems_path.read_text(encoding="utf-8")
    acc = section(meta, SECTION_FIELDS)
    if acc is None:
        raise Refused(f"METADATA_FIELDS.md has no '## {SECTION_FIELDS}' section")
    inputs = section(systems, SECTION_INPUTS)
    if inputs is None:
        raise Refused(f"SYSTEMS.md has no '## {SECTION_INPUTS}' section")

    def sub(title: str) -> str:
        body = section(acc, title, level=3)
        if body is None:
            raise Refused(f"METADATA_FIELDS.md '## {SECTION_FIELDS}' has no '### {title}'")
        return body

    where = f"METADATA_FIELDS.md ### Accrual settings"
    settings = fields(sub("Accrual settings"))
    cc = fields(sub("Credit-card accrual"))
    vendor = fields(sub("Post-cutoff vendor accrual"))
    families = {r.get("Department", "").upper(): r.get("Family", "").upper()
                for r in table(sub("Department families")) if r.get("Department")}

    mcc_map: Dict[str, dict] = {}
    for row in table(sub("Card account map")):
        mcc = row.get("MCC", "").strip()
        if not mcc:
            continue
        account, name = account_cell(row.get("Account", ""))
        entry: Dict[str, Any] = {"category": row.get("Category", "").upper(), "account": account,
                                 "account_name": name, "mcc_description": row.get("MCC description", "")}
        overrides = by_department(row.get("By department", ""))
        if overrides:
            overrides["default"] = {"account": account, "account_name": name}
            entry["account_by_department"] = overrides
        mcc_map[mcc] = entry
    people = {r.get("Cardholder", "").upper(): {"department": r.get("Department", "").upper()}
              for r in table(sub("People map")) if r.get("Cardholder")}
    labels = department_labels(section(acc, "Department labels", level=3))
    merchant_overrides = merchant_override_rows(section(acc, "Merchant overrides", level=3))

    vendor_body = sub("Post-cutoff vendor accrual")
    excluded = excluded_vendors(vendor.get("excluded vendors", ""), vendor_body)
    where_v = "METADATA_FIELDS.md ### Post-cutoff vendor accrual"
    missing_months = setting_number(vendor, "Missing-accrual months", 6, where_v, whole=True)
    missing_min = setting_number(vendor, "Missing-accrual min months", 3, where_v, whole=True)
    missing_floor = setting_number(vendor, "Missing-accrual floor", 1000, where_v)
    if missing_min > missing_months:
        raise Refused(f"{where_v}: Missing-accrual min months ({missing_min}) is more than "
                      f"Missing-accrual months ({missing_months})")

    inp = fields(inputs)
    columns = {}
    for part in listed(inp.get("card report columns", "")):
        key, sep, header = part.partition("=")
        if sep:
            columns[key.strip()] = header.strip()
    config = {
        "folder": str(folder),
        "file_name": settings.get("import file name") or DEFAULT_FILE_NAME,
        "journal": settings.get("journal") or "GJ",
        "liability_account": need(settings, "Liability account", where),
        "liability_name": settings.get("liability account name") or "Accrued Expenses",
        "location": need(settings, "Entity location", where),
        "default_department": need(settings, "Default department", where).upper(),
        "unmapped_account": need(settings, "Unmapped account", where),
        "cc": {
            "name": cc.get("file name") or "CC accrual",
            "posted_contains": listed(cc.get("posted entry contains", "")),
            "vendor_name_floor": float(cc.get("vendor name floor") or 1000),
            "always_vendor_named": [c.upper() for c in listed(cc.get("always vendor-named categories", ""))],
            "post_date_cutoff": cc.get("post-date cutoff", ""),
        },
        "vendor": {
            "name": vendor.get("file name") or "post-cutoff vendor accrual",
            "description": vendor.get("description", ""),
            "posted_contains": listed(vendor.get("posted entry contains", "")),
            "arrears_vendors": [v.upper() for v in listed(vendor.get("arrears vendors", ""))],
            "exclude_vendors": [key for key, _ in excluded],
            "exclude_reasons": {key: reason for key, reason in excluded},
            "expense_prefixes": listed(vendor.get("expense account prefixes", "")) or ["5", "6", "7", "8", "9"],
            "trailing_months": int(vendor.get("trailing months") or 3),
            "missing_months": missing_months,
            "missing_min_months": missing_min,
            "missing_floor": missing_floor,
        },
        "department_families": families,
        "mcc_map": mcc_map,
        "people_map": people,
        "department_labels": labels,
        "merchant_overrides": merchant_overrides,
        "ledger_pull": inp.get("ledger pull") or "work/source",
        "card_report": listed(inp.get("card report", "")),
        "card_sheet": inp.get("card report sheet", ""),
        "card_columns": columns,
        "work": inp.get("work folder") or "work/accruals",
    }
    problems = []
    if not mcc_map:
        problems.append("the Card account map table is empty")
    if not people:
        problems.append("the People map table is empty")
    if not config["cc"]["posted_contains"] or not config["vendor"]["posted_contains"]:
        problems.append("each accrual needs a '- Posted entry contains:' line for the done check")
    if not config["card_report"]:
        problems.append("SYSTEMS.md ## Close inputs has no '- Card report:' line")
    if problems:
        raise Refused("; ".join(problems))
    return config


def import_name(config: Dict[str, Any], accrual: str, period: str) -> str:
    month, year = month_words(period)
    return config["file_name"].format(month=month, year=year, name=config[accrual]["name"])


def import_stem(config: Dict[str, Any], accrual: str, period: str) -> str:
    """The name up to and including the accrual's name: earlier files and second passes match it."""
    month, year = month_words(period)
    head = config["file_name"].split("{name}")[0]
    return head.format(month=month, year=year) + config[accrual]["name"]


# ---------------------------------------------------------------------------------------------
# Is it already done?


def load_json_rows(path: Path) -> Tuple[List[dict], Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("rows") or []), dict(data.get("meta") or {})
    return list(data), {}


def pulled_on(source: Path) -> str:
    """The pull's date from pulled.md ('Pulled 2026-10-03'), or ''."""
    note = source / "pulled.md"
    if note.is_file():
        m = re.search(r"Pulled (\d{4}-\d{2}-\d{2})", note.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return ""


def ledger_entries(config: Dict[str, Any], folder: Path, period: str, accrual: str) -> Dict[str, Any]:
    source = period_folder(folder, period) / config["ledger_pull"]
    headers_path = source / f"headers-{period}.json"
    if not headers_path.is_file():
        return {"pull": None, "entries": [], "note": f"no ledger pull for {period} ({headers_path.name} absent)"}
    headers, meta = load_json_rows(headers_path)
    tokens = [t.casefold() for t in config[accrual]["posted_contains"]]
    end = period_end(period)
    found, others = [], []
    for h in headers:
        text = str(h.get("description") or "")
        if text.casefold().startswith("reversed - ") or h.get("reversedFromDate"):
            continue
        if str(h.get("postingDate") or "")[:10] != end:
            continue
        entry = {"je": str(h.get("key") or h.get("id") or ""), "description": text,
                 "state": str(h.get("state") or ""), "posting_date": end}
        if any(t in text.casefold() for t in tokens):
            found.append(entry)
        elif not any(t.casefold() in text.casefold() for a in ACCRUALS for t in config[a]["posted_contains"]):
            others.append(entry)   # the other accrual of this skill is complementary, not an overlap
    lines_path = source / f"lines-{period}.json"
    lines = load_json_rows(lines_path)[0] if lines_path.is_file() else []
    by_je: Dict[str, List[dict]] = {}
    for ln in lines:
        by_je.setdefault(str(ln.get("journalEntry.key") or ""), []).append(ln)
    for entry in found:
        mine = by_je.get(entry["je"], [])
        entry["lines"] = len(mine)
        entry["debits"] = round(sum(float(ln.get("baseAmount") or 0) for ln in mine
                                    if str(ln.get("txnType")) == "debit"), 2)
        stamps = sorted(str(ln.get("audit.createdDateTime") or "") for ln in mine if ln.get("audit.createdDateTime"))
        entry["entered_at"] = stamps[0] if stamps else ""
    # Other entries dated month end that credit the liability account: accruals booked another
    # way, which a draft must not book a second time.
    accruals = []
    for entry in others:
        mine = by_je.get(entry["je"], [])
        if not any(str(ln.get("glAccount.id")) == config["liability_account"] and str(ln.get("txnType")) == "credit"
                   for ln in mine):
            continue
        entry["debit_lines"] = [
            {"account": str(ln.get("glAccount.id") or ""), "department": str(ln.get("dimensions.department.id") or ""),
             "location": str(ln.get("dimensions.location.id") or ""), "amount": round(float(ln.get("baseAmount") or 0), 2),
             "memo": str(ln.get("description") or "")}
            for ln in mine if str(ln.get("txnType")) == "debit"]
        accruals.append(entry)
    return {"pull": str(headers_path.relative_to(folder)), "pulled_on": pulled_on(source),
            "pulled_at": str(meta.get("pulled-at") or ""), "entries": found, "other_accruals": accruals}


def overlaps(draft_lines: List[dict], other_accruals: List[dict]) -> List[Dict[str, Any]]:
    """Accounts in the draft that another month-end accrual already touches, one row per
    account: the draft's lines on it, the other entries' lines on it, and any of those lines
    that names a draft vendor. A person decides whether it is the same cost."""
    by_account: Dict[str, List[dict]] = {}
    for line in draft_lines:
        if line.get("naming") != "offset":
            by_account.setdefault(str(line.get("account")), []).append(line)
    out = []
    for account, mine in sorted(by_account.items()):
        theirs = [(entry["je"], other) for entry in other_accruals for other in entry.get("debit_lines", [])
                  if other["account"] == account]
        if not theirs:
            continue
        named = []
        for line in mine:
            word = next((w for w in re.split(r"[^A-Z0-9]+", str(line.get("vendor") or "").upper()) if len(w) > 2), "")
            for je, other in theirs:
                if word and re.search(rf"(?<![A-Z0-9]){re.escape(word)}(?![A-Z0-9])", other["memo"].upper()):
                    named.append(f"{line.get('vendor')} in JE {je}")
        out.append({
            "account": account,
            "draft": f"{len(mine)} line(s), {sum(float(ln.get('debit') or 0) for ln in mine):,.2f}",
            "existing": [f"JE {je} {o['department']} {o['amount']:,.2f} {o['memo']}" for je, o in theirs],
            "vendor_named": named,
        })
    return out


def files_in_folder(config: Dict[str, Any], folder: Path, period: str, accrual: str) -> List[str]:
    where = period_folder(folder, period)
    stem = import_stem(config, accrual, period).casefold()
    found = []
    for place in (where, where / JE_FOLDER):
        if place.is_dir():
            found += [str(p.relative_to(where)) for p in place.iterdir()
                      if p.is_file() and p.suffix.lower() == ".csv" and p.name.casefold().startswith(stem)]
    return sorted(found)


def done(config: Dict[str, Any], folder: Path, period: str, accrual: str) -> Dict[str, Any]:
    ledger = ledger_entries(config, folder, period, accrual)
    files = files_in_folder(config, folder, period, accrual)
    posted = [e for e in ledger["entries"] if e["state"].lower() == "posted"]
    entered = [e for e in ledger["entries"] if e["state"].lower() != "posted"]
    vintage = ledger.get("pulled_on") or ledger.get("pulled_at") or "unknown"
    if posted:
        state, evidence = "posted", "; ".join(
            f"JE {e['je']} '{e['description']}' posted {e['posting_date']}, debits {e.get('debits', 0):,.2f}"
            f"{', entered ' + e['entered_at'][:10] if e.get('entered_at') else ''}" for e in posted)
    elif entered:
        state, evidence = "entered", "; ".join(
            f"JE {e['je']} '{e['description']}' is in the ledger as {e['state']}, not posted" for e in entered)
    elif files:
        state, evidence = "file", (f"import file already in the period folder: {', '.join(files)}; "
                                   f"no matching entry in the ledger pull of {vintage}")
    else:
        state = "not-done"
        evidence = (f"no entry dated {period_end(period)} whose description contains "
                    f"{' or '.join(repr(t) for t in config[accrual]['posted_contains'])} in "
                    f"{ledger['pull'] or 'the ledger pull (none for the period)'}"
                    f"{' of ' + vintage if ledger['pull'] else ''}, and no import file in the period folder")
    return {"accrual": accrual, "period": period, "done": state != "not-done", "state": state,
            "evidence": evidence, "ledger": ledger, "files": files}


# ---------------------------------------------------------------------------------------------
# Inputs


def card_reports(config: Dict[str, Any], folder: Path, period: str) -> List[Path]:
    where = period_folder(folder, period)
    if not where.is_dir():
        return []
    out = []
    for p in sorted(where.iterdir()):
        if p.is_file() and not p.name.startswith("~$") and any(
                fnmatch.fnmatch(p.name.casefold(), pat.casefold()) for pat in config["card_report"]):
            out.append(p)
    return out


def inputs(config: Dict[str, Any], folder: Path, period: str, accrual: str,
           card_report: Optional[str] = None) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    missing: List[Dict[str, str]] = []
    month, year = month_words(period)
    if accrual == "cc":
        if card_report:
            path = Path(card_report).expanduser()
            if not path.is_file():
                raise Bad(f"--card-report {card_report}: no such file")
            found["card_report"] = str(path)
        else:
            reports = card_reports(config, folder, period)
            if len(reports) == 1:
                found["card_report"] = str(reports[0])
            elif not reports:
                missing.append({
                    "input": "card report",
                    "looked_for": f"{', '.join(config['card_report'])} in {period_folder(folder, period).relative_to(folder)}",
                    "question": (f"Can the {month} {year} card transaction detail download, with employee and "
                                 f"department filled in, be saved to the {period} folder?"),
                })
            else:
                raise Refused(f"{len(reports)} card reports match in the period folder "
                              f"({', '.join(p.name for p in reports)}); name one with --card-report")
    else:
        nxt = shift(period, 1)
        source = period_folder(folder, nxt) / config["ledger_pull"]
        next_bills = source / f"ap-bill-lines-{nxt}.json"
        if next_bills.is_file():
            found["next_bills"] = str(next_bills)
            found["next_pulled_on"] = pulled_on(source)
        else:
            next_month, next_year = month_words(nxt)
            missing.append({
                "input": "next-month AP bills",
                "looked_for": str(next_bills.relative_to(folder)),
                "question": (f"Can the {next_month} {next_year} AP bill lines be pulled read-only into "
                             f"{next_bills.parent.relative_to(folder)} once the AP cutoff for {month} has passed?"),
            })
        trailing = []
        for back in range(config["vendor"]["trailing_months"] - 1, -1, -1):
            p = shift(period, -back)
            path = period_folder(folder, p) / config["ledger_pull"] / f"ap-bill-lines-{p}.json"
            if path.is_file():
                trailing.append(str(path))
        found["bills"] = trailing
    return {"accrual": accrual, "period": period, "found": found, "missing": missing, "ready": not missing}


# ---------------------------------------------------------------------------------------------
# The missing-accrual scan: recurring vendors with nothing booked or billed for the period


LEGAL_WORDS = {"LLC", "INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LP", "LLP", "PC", "PLLC",
               "THE", "AND", "OF", "GROUP"}


def name_key(name: str) -> str:
    return " ".join(str(name or "").split()).upper()


def name_words(name: str) -> List[str]:
    return [w for w in re.split(r"[^A-Z0-9]+", name_key(name)) if len(w) >= 2 and w not in LEGAL_WORDS]


def has_word(text: str, word: str) -> bool:
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(word)}(?![A-Z0-9])", text))


def names_vendor(text: str, words: List[str], distinctive: bool) -> bool:
    """Whether free text (a GL line, an import file's memo) names the vendor: its first word when
    no other vendor in the history shares that word, else every word of its name."""
    text = name_key(text)
    if not words or not text:
        return False
    if distinctive:
        return has_word(text, words[0])
    return all(has_word(text, w) for w in words)


def period_tokens(period: str) -> List[str]:
    """Upper-case fragments that name the period in a memo (as service-period-accrual reads them)."""
    year, month = (int(x) for x in period.split("-"))
    name, abbr = calendar.month_name[month].upper(), calendar.month_abbr[month].upper()
    yy = f"{year % 100:02d}"
    return [f"{name} {year}", f"{abbr} {year}", f"{name} {yy}", f"{abbr} {yy}", f"{abbr}-{yy}", f"{abbr}{yy}",
            period, f"{month:02d}/{year}", f"{month}/{year}", f"{month:02d}-{year}", name, f"{abbr}."]


def money_of(value: Any) -> float:
    try:
        return float(str(value if value is not None else 0).replace(",", "") or 0)
    except ValueError:
        return 0.0


def import_rows(where: Path) -> List[Tuple[str, str, str]]:
    """(file name, the row's text, its memo) for each row of each CSV in a folder: the period's
    import files. The memo is the MEMO column when the file has one, else the row's text."""
    out: List[Tuple[str, str, str]] = []
    if not where.is_dir():
        return out
    for path in sorted(where.iterdir()):
        if not (path.is_file() and path.suffix.lower() == ".csv"):
            continue
        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                rows = list(csv.reader(handle))
            if rows and rows[0] and rows[0][0].startswith("\ufeff"):  # a byte-order mark
                rows[0][0] = rows[0][0][1:]
        except OSError:
            continue
        head = [c.strip().upper() for c in rows[0]] if rows else []
        memo_at = head.index("MEMO") if "MEMO" in head else None
        for row in rows[1:] if memo_at is not None else rows:
            text = " ".join(cell for cell in row if cell)
            memo = row[memo_at] if memo_at is not None and memo_at < len(row) else text
            out.append((path.name, text, memo))
    return out


def missing_accrual_scan(config: Dict[str, Any], folder: Path, period: str,
                         draft_bills: Optional[List[dict]] = None,
                         extra_dirs: Tuple[Path, ...] = ()) -> Dict[str, Any]:
    """Every vendor whose expense recurs in the ledger history and has nothing booked or billed for
    the period. History: the AP bill lines of the last `Missing-accrual months` pulls before the
    period. A vendor is in scope when its expense was at or above the floor in at least `min
    months` of them; an arrears vendor is always in scope; an excluded vendor never is. In-scope
    vendors are searched for in the period: an AP bill dated in the period (for an arrears vendor,
    one naming the period), a line of this build's draft, a GL line in the period naming the vendor
    (reversals left out), and the period's import files. A vendor with none of these is flagged,
    with the typical amount (the median of the months seen) as the proposed accrual."""
    v = config["vendor"]
    months_back, min_months, floor = v["missing_months"], v["missing_min_months"], v["missing_floor"]
    prefixes = tuple(v["expense_prefixes"])
    arrears, excluded = v["arrears_vendors"], v["exclude_vendors"]
    history = [shift(period, -k) for k in range(months_back, 0, -1)]
    pulled, missing_pulls = [], []
    lines_by_vendor: Dict[str, List[dict]] = {}
    names: Dict[str, str] = {}
    for month in history:
        path = period_folder(folder, month) / config["ledger_pull"] / f"ap-bill-lines-{month}.json"
        if not path.is_file():
            missing_pulls.append(month)
            continue
        pulled.append(month)
        for row in load_json_rows(path)[0]:
            account = str(row.get("glAccount.id") or "")
            vendor = name_key(row.get("vendor.name"))
            if not vendor or not account.startswith(prefixes):
                continue
            names.setdefault(vendor, " ".join(str(row.get("vendor.name")).split()))
            lines_by_vendor.setdefault(vendor, []).append({
                "month": month, "account": account, "account_name": str(row.get("glAccount.name") or ""),
                "department": str(row.get("dimensions.department.id") or config["default_department"]).upper(),
                "location": str(row.get("dimensions.location.id") or config["location"]),
                "amount": money_of(row.get("baseAmount"))})

    word_count: Dict[str, int] = {}
    for vendor in lines_by_vendor:
        for w in set(name_words(vendor)):
            word_count[w] = word_count.get(w, 0) + 1

    here = period_folder(folder, period)
    source = here / config["ledger_pull"]
    bills_path, lines_path = source / f"ap-bill-lines-{period}.json", source / f"lines-{period}.json"
    headers_path = source / f"headers-{period}.json"
    period_bills = load_json_rows(bills_path)[0] if bills_path.is_file() else []
    gl_lines = load_json_rows(lines_path)[0] if lines_path.is_file() else []
    reversed_keys = set()
    if headers_path.is_file():
        for h in load_json_rows(headers_path)[0]:
            if h.get("reversedFromDate") or str(h.get("description") or "").casefold().startswith("reversed"):
                reversed_keys.add(str(h.get("key") or h.get("id") or ""))
    tokens = period_tokens(period)
    bill_memos: Dict[str, str] = {}
    for row in period_bills:
        bill_memos[str(row.get("bill.id"))] = bill_memos.get(str(row.get("bill.id")), "") + " " + \
            str(row.get("memo") or "").upper()
    dirs = [here, here / JE_FOLDER, *extra_dirs]
    files = [r for d in dict.fromkeys(dirs) for r in import_rows(Path(d))]
    searched = [
        f"AP bills dated {period} ({bills_path.name if bills_path.is_file() else 'no AP bill pull for the period'})",
        "this build's draft lines" if draft_bills is not None else "this build's draft (not built)",
        f"GL lines in {period} naming the vendor, reversals left out "
        f"({lines_path.name if lines_path.is_file() else 'no GL line pull for the period'})",
        f"import files in the period folder ({len({f for f, _, _ in files})} CSV)",
    ]

    flagged, covered, excluded_out = [], [], []
    for vendor, rows in sorted(lines_by_vendor.items()):
        by_month: Dict[str, float] = {}
        for r in rows:
            by_month[r["month"]] = by_month.get(r["month"], 0.0) + r["amount"]
        is_arrears = any(a and a in vendor for a in arrears)
        ex_key = next((x for x in excluded if x and x in vendor), None)
        at_floor = [m for m in history if by_month.get(m, 0) >= floor and by_month.get(m, 0) > 0]
        seen = [m for m in history if by_month.get(m, 0) > 0] if is_arrears else at_floor
        if ex_key is None and not (is_arrears and seen) and len(at_floor) < min_months:
            continue
        typical = round(median([by_month[m] for m in seen]), 2) if seen else 0.0
        mine = [r for r in rows if r["month"] in seen and r["amount"]]
        alloc: Dict[Tuple[str, str, str], float] = {}
        acct_names: Dict[str, str] = {}
        for r in mine:
            alloc[(r["account"], r["department"], r["location"])] = \
                alloc.get((r["account"], r["department"], r["location"]), 0.0) + r["amount"]
            acct_names[r["account"]] = r["account_name"]
        alloc = {k: a for k, a in alloc.items() if a > 0}
        total = sum(alloc.values()) or 1.0
        allocation = [{"account": a, "account_name": acct_names.get(a, ""), "department": d, "location": loc,
                       "share": round(amt / total, 4)} for (a, d, loc), amt in sorted(alloc.items(), key=lambda kv: -kv[1])]
        by_acct: Dict[str, float] = {}
        by_dept: Dict[str, float] = {}
        for (a, d, _), amt in alloc.items():
            by_acct[a] = by_acct.get(a, 0.0) + amt
            by_dept[d] = by_dept.get(d, 0.0) + amt
        entry: Dict[str, Any] = {
            "vendor": names.get(vendor, vendor), "arrears": is_arrears,
            "months_seen": seen, "months_seen_count": len(seen), "of_months": len(pulled),
            "typical": typical, "last_seen": seen[-1] if seen else "",
            "accounts": [f"{a} {acct_names.get(a, '')}".strip() + f" ({amt / total:.0%})"
                         for a, amt in sorted(by_acct.items(), key=lambda kv: -kv[1])],
            "departments": [f"{d} ({amt / total:.0%})" for d, amt in sorted(by_dept.items(), key=lambda kv: -kv[1])],
            "allocation": allocation,
        }
        if ex_key is not None:
            entry["reason"] = v["exclude_reasons"].get(ex_key, "listed under Excluded vendors")
            entry["excluded_by"] = ex_key
            excluded_out.append(entry)
            continue

        found: List[str] = []
        for row in period_bills:
            if name_key(row.get("vendor.name")) != vendor or not str(row.get("glAccount.id") or "").startswith(prefixes):
                continue
            bill_id = str(row.get("bill.id"))
            if is_arrears and not any(t in bill_memos.get(bill_id, "") for t in tokens):
                continue
            found.append(f"AP bill {bill_id} dated {str(row.get('bill.postingDate'))[:10]}, "
                         f"{money_of(row.get('baseAmount')):,.2f} '{str(row.get('memo') or '')[:40]}'")
        for b in draft_bills or []:
            if name_key(b.get("vendor")) == vendor:
                found.append(f"this draft: {b.get('reason')}, {float(b.get('amount') or 0):,.2f} "
                             f"({b.get('bill_id')})")
        words = name_words(vendor)
        distinctive = bool(words) and word_count.get(words[0], 0) <= 1
        for ln in gl_lines:
            key = str(ln.get("journalEntry.key") or "")
            text = str(ln.get("description") or "")
            account = str(ln.get("glAccount.id") or "")
            if key in reversed_keys or text.casefold().startswith("reversed"):
                continue
            if not (account.startswith(prefixes) or account == config["liability_account"]):
                continue
            if names_vendor(text, words, distinctive):
                found.append(f"JE {key} {account} {money_of(ln.get('baseAmount')):,.2f} {ln.get('txnType') or ''} "
                             f"'{text[:50]}'")
        for name, _, memo in files:
            if names_vendor(memo, words, distinctive):
                found.append(f"import file '{name}': {memo[:80]}")
        entry["evidence"] = {"searched": searched, "found": found[:12], "found_count": len(found)}
        if found:
            covered.append(entry)
        else:
            entry["proposed_amount"] = typical
            entry["status"] = "flagged"
            flagged.append(entry)

    seen_arrears = {a for a in arrears for vendor in lines_by_vendor if a and a in vendor}
    return {
        "period": period,
        "settings": {"months": months_back, "min_months": min_months, "floor": floor,
                     "expense_prefixes": list(prefixes)},
        "history": {"months": pulled, "missing": missing_pulls},
        "flagged": flagged, "covered": covered, "excluded": excluded_out,
        "arrears_not_seen": [a for a in arrears if a not in seen_arrears],
        "summary": (f"{period}: {len(flagged)} recurring vendor(s) with nothing booked or billed, "
                    f"{len(covered)} covered, {len(excluded_out)} excluded; history {len(pulled)} of "
                    f"{months_back} month(s), at least {min_months} month(s) at or above {floor:,.0f}"),
    }


def read_decisions(path: Optional[Path], scan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The worker's decision on each flagged vendor, keyed by vendor: accrue or not, with a reason."""
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Bad(f"--decisions {path}: {exc}")
    items = data.get("decisions") if isinstance(data, dict) else data
    flagged = {name_key(f["vendor"]): f for f in scan["flagged"]}
    out: Dict[str, Dict[str, Any]] = {}
    for item in items or []:
        vendor = name_key(item.get("vendor") if isinstance(item, dict) else "")
        if vendor not in flagged:
            raise Bad(f"--decisions names {vendor or 'no vendor'!r}, which the scan did not flag "
                      f"(flagged: {', '.join(sorted(flagged)) or 'none'})")
        if not isinstance(item.get("accrue"), bool) or not str(item.get("reason") or "").strip():
            raise Bad(f"--decisions: {vendor} needs 'accrue' (true or false) and a 'reason'")
        amount = item.get("amount", flagged[vendor]["proposed_amount"])
        if item["accrue"] and (not isinstance(amount, (int, float)) or amount <= 0):
            raise Bad(f"--decisions: {vendor} amount {amount!r} is not a positive number")
        out[vendor] = {"accrue": item["accrue"], "reason": str(item["reason"]).strip(),
                       "amount": round(float(amount), 2) if item["accrue"] else 0.0}
    return out


def missing_accrual_lines(scan: Dict[str, Any], decisions: Dict[str, Dict[str, Any]],
                          period: str) -> List[dict]:
    """Debit lines for each flagged vendor the worker decided to accrue, allocated across the
    accounts, departments and locations its history hit."""
    out = []
    for f in scan["flagged"]:
        d = decisions.get(name_key(f["vendor"]))
        if not d or not d["accrue"]:
            continue
        shares = f["allocation"] or []
        amounts = [round(d["amount"] * s["share"], 2) for s in shares]
        if amounts:
            amounts[0] = round(amounts[0] + d["amount"] - sum(amounts), 2)
        for s, amount in zip(shares, amounts):
            if amount <= 0:
                continue
            out.append({"account": s["account"], "account_name": s["account_name"], "department": s["department"],
                        "location": s["location"], "debit": amount, "credit": 0.0,
                        "memo": f"ACCRUED {f['vendor']} - {s['account_name']} {period} (ESTIMATE, missing accrual)".strip(),
                        "vendor": f["vendor"], "category": "", "naming": "vendor", "max_merchant": amount})
    return out


def add_lines(proposal: Dict[str, Any], extra: List[dict], config: Dict[str, Any], period: str) -> Dict[str, Any]:
    """The vendor proposal with the accepted missing-accrual lines added and one offset per location
    recomputed, built fresh when the draft had nothing else."""
    if not extra:
        return proposal
    props = proposal.get("proposals") or []
    if props:
        entry = props[0]
    else:
        month, year = month_words(period)
        template = config["vendor"]["description"] or "To accrue {month} {year} expenses received after the AP cutoff"
        nxt = shift(period, 1)
        entry = {"je_id": f"POST-CUTOFF VENDOR ACCRUAL {period}", "journal": config["journal"],
                 "description": template.format(month=month, year=year), "posting_date": period_end(period),
                 "reversal_date": f"{nxt}-01", "source": "service-period-accrual", "lines": []}
        props = [entry]
    debits = [ln for ln in entry["lines"] if ln.get("naming") != "offset"] + extra
    by_location: Dict[str, float] = {}
    for ln in debits:
        by_location[ln["location"]] = by_location.get(ln["location"], 0.0) + float(ln["debit"])
    offsets = [{"account": config["liability_account"], "account_name": config["liability_name"],
                "department": config["default_department"], "location": loc, "debit": 0.0, "credit": round(amt, 2),
                "memo": f"ACCRUED POST-CUTOFF VENDOR EXPENSES {period}", "vendor": "", "category": "",
                "naming": "offset", "max_merchant": 0.0} for loc, amt in sorted(by_location.items())]
    entry["lines"] = debits + offsets
    proposal["proposals"] = props
    return proposal


def scan_table(scan: Dict[str, Any]) -> List[str]:
    """The scan as markdown: flagged vendors with their decision, then covered, then excluded."""
    s = scan["settings"]
    out = [f"History: {', '.join(scan['history']['months']) or 'none'}"
           + (f"; no pull for {', '.join(scan['history']['missing'])}" if scan["history"]["missing"] else "")
           + f". In scope: expense in at least {s['min_months']} of the last {s['months']} month(s) at or above "
           f"{s['floor']:,.0f}, and every arrears vendor.", "",
           "Flagged (nothing booked or billed for the period):", ""]
    if scan["flagged"]:
        out += ["| Vendor | Months seen | Typical | Last seen | Accounts | Departments | Proposed | Decision |",
                "|---|---|---:|---|---|---|---:|---|"]
        for f in scan["flagged"]:
            d = f.get("decision")
            decision = (f"{'accrue ' + money_cell(d['amount']) if d['accrue'] else 'do not accrue'}: {d['reason']}"
                        if d else "undecided")
            out.append(f"| {f['vendor']}{' (arrears)' if f['arrears'] else ''} | {f['months_seen_count']} of "
                       f"{f['of_months']} ({', '.join(f['months_seen'])}) | {money_cell(f['typical'])} | {f['last_seen']} | "
                       f"{'; '.join(f['accounts'])} | {'; '.join(f['departments'])} | {money_cell(f['proposed_amount'])} | "
                       f"{decision} |")
        out += ["", "Searched for each: " + "; ".join(scan["flagged"][0]["evidence"]["searched"]) + "."]
    else:
        out.append("None.")
    out += ["", "Covered (something booked or billed for the period):", ""]
    if scan["covered"]:
        out += ["| Vendor | Months seen | Typical | Evidence |", "|---|---|---:|---|"]
        out += [f"| {c['vendor']} | {c['months_seen_count']} of {c['of_months']} | {money_cell(c['typical'])} | "
                f"{c['evidence']['found'][0]}{' (+' + str(c['evidence']['found_count'] - 1) + ')' if c['evidence']['found_count'] > 1 else ''} |"
                for c in scan["covered"]]
    else:
        out.append("None.")
    out += ["", "Excluded by the settings (never flagged):", ""]
    if scan["excluded"]:
        out += ["| Vendor | Months seen | Typical | Reason |", "|---|---|---:|---|"]
        out += [f"| {x['vendor']} | {x['months_seen_count']} of {x['of_months']} | {money_cell(x['typical'])} | "
                f"{x['reason']} |" for x in scan["excluded"]]
    else:
        out.append("None in the history.")
    return out


def vendor_backup_text(result: Dict[str, Any], file_name: str) -> str:
    """The vendor accrual's backup beside its import file: the draft's source and the scan."""
    period, scan = result["period"], result["missing_accrual"]
    out = [f"# Backup: {period} post-cutoff vendor accrual (reversing), DRAFT", "",
           f"Import file: `{file_name}`. Written by `accruals.py build`; not uploaded or posted.", "",
           "## Source", "", f"- {result['summary']}.",
           f"- Next-month AP bills pulled {result.get('next_pulled_on') or 'on an unknown date'}.", "",
           "## Missing-accrual scan", "", scan["summary"] + ".", ""]
    out += scan_table(scan)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------
# Build


# Which skill owns each command this script runs. None means this skill, beside this file.
COMMAND_OWNERS = {
    "card-export": None,
    "cc-accrual": None,
    "service-period-accrual": None,
    "je-import": "month-end-journal-entry",
    "je-import-check": "month-end-journal-entry",
}


def command(name: str) -> List[str]:
    """The argv that runs one command: python3 and its owning skill's script."""
    if name not in COMMAND_OWNERS:
        raise Bad(f"{name} is not a command this script runs")
    script = name.replace("-", "_") + ".py"
    owner = COMMAND_OWNERS[name]
    if owner is None:
        path = Path(__file__).resolve().parent / script
    else:
        skills = Path(os.environ.get("ACCRUALS_SKILLS_DIR") or "~/.claude/skills").expanduser()
        path = skills / owner / "scripts" / script
    if not path.is_file():
        raise Bad(f"the command {name} is not at {path} (is the {owner or 'month-end-accrual-drafts'} "
                  f"skill linked into ~/.claude/skills?)")
    return [sys.executable or "python3", str(path)]


def run(name: str, args: List[str], ok: Tuple[int, ...] = (0,)) -> Tuple[int, Dict[str, Any], str]:
    done_ = subprocess.run([*command(name), *args, "--format", "json"], capture_output=True, text=True,
                           timeout=600)
    try:
        out = json.loads(done_.stdout or "{}")
    except ValueError:
        out = {}
    if done_.returncode not in ok or not out:
        raise RuntimeError(f"{name} exited {done_.returncode}: {(done_.stderr or done_.stdout).strip()[-600:]}")
    return done_.returncode, out, done_.stderr


def vendor_args(config: Dict[str, Any], period: str, next_bills: str, bills: Path) -> List[str]:
    """The service-period-accrual arguments the folder's settings give."""
    v = config["vendor"]
    args = ["--period", period, "--next-bills", next_bills, "--bills", str(bills),
            "--liability-account", config["liability_account"], "--liability-name", config["liability_name"],
            "--location", config["location"], "--default-department", config["default_department"],
            "--journal", config["journal"]]
    for vendor in v["arrears_vendors"]:
        args += ["--arrears-vendor", vendor]
    for vendor in v["exclude_vendors"]:
        args += ["--exclude-vendor", vendor]
    for prefix in v["expense_prefixes"]:
        args += ["--expense-prefix", prefix]
    if v["description"]:
        args += ["--description", v["description"]]
    return args


def merge_trailing(paths: List[str], target: Path) -> None:
    rows: List[dict] = []
    for path in paths:
        rows += load_json_rows(Path(path))[0]
    target.write_text(json.dumps({"meta": {"merged_from": paths}, "rows": rows}), encoding="utf-8")


def scan_only(config: Dict[str, Any], folder: Path, period: str, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """The missing-accrual scan on its own, writing nothing: when the next month's AP bills are
    pulled, the draft's lines (bills and arrears estimates) count as cover, as they do in a build."""
    import tempfile
    need_ = inputs(config, folder, period, "vendor")
    draft = None
    if need_["ready"]:
        with tempfile.TemporaryDirectory() as tmp:
            bills = Path(tmp) / "bills.json"
            merge_trailing(need_["found"]["bills"], bills)
            _, built, _ = run("service-period-accrual", vendor_args(config, period, need_["found"]["next_bills"], bills),
                              ok=(0, 1))
            draft = built["bills"]
    scan = missing_accrual_scan(config, folder, period, draft, (out_dir,) if out_dir else ())
    if draft is None:
        scan["note"] = ("the next month's AP bills are not pulled, so the draft (its bills and arrears "
                        "estimates) was not counted as cover")
    return scan


def build(config: Dict[str, Any], folder: Path, period: str, accrual: str, out_dir: Optional[Path] = None,
          ignore_done: bool = False, card_report: Optional[str] = None,
          decisions_path: Optional[Path] = None) -> Tuple[int, Dict[str, Any]]:
    status = done(config, folder, period, accrual)
    result: Dict[str, Any] = {"accrual": accrual, "period": period, "done_check": status}
    extra_dirs = (Path(out_dir),) if out_dir else ()
    if status["done"] and not ignore_done:
        result.update(outcome="already-done", detail=status["evidence"])
        if accrual == "vendor":
            result["missing_accrual"] = missing_accrual_scan(config, folder, period, None, extra_dirs)
        return 0, result
    need_ = inputs(config, folder, period, accrual, card_report)
    result["inputs"] = need_
    if not need_["ready"]:
        result.update(outcome="waiting", detail="; ".join(f"{m['input']} not found ({m['looked_for']})"
                                                          for m in need_["missing"]))
        if accrual == "vendor":
            scan = missing_accrual_scan(config, folder, period, None, extra_dirs)
            scan["note"] = ("the next month's AP bills are not pulled, so the draft (its bills and arrears "
                            "estimates) was not counted as cover")
            result["missing_accrual"] = scan
        return 4, result

    here = period_folder(folder, period)
    target_dir = Path(out_dir) if out_dir else (here / JE_FOLDER if (here / JE_FOLDER).is_dir() else here)
    target = target_dir / import_name(config, accrual, period)
    backup = target.with_name(target.stem + " backup.md")
    for path in (target, backup):
        if path.exists():
            raise Refused(f"{path.name} is already in {target_dir}; it is never overwritten")
    work = (Path(out_dir) / "work") if out_dir else period_folder(folder, period) / config["work"]
    work.mkdir(parents=True, exist_ok=True)
    liability = config["liability_account"]
    if accrual == "cc":
        card_csv = work / f"card-transactions-{period}.csv"
        args = [need_["found"]["card_report"], "--period", period, "--out", str(card_csv)]
        if config["card_sheet"]:
            args += ["--sheet", config["card_sheet"]]
        for key, header in config["card_columns"].items():
            args += ["--column", f"{key}={header}"]
        _, card, _ = run("card-export", args)
        mcc_path, people_path = work / "mcc-map.json", work / "people-map.json"
        mcc_path.write_text(json.dumps({"department_families": config["department_families"],
                                        "merchant_overrides": config["merchant_overrides"],
                                        "map": config["mcc_map"]}, indent=1), encoding="utf-8")
        people_path.write_text(json.dumps(config["people_map"], indent=1), encoding="utf-8")
        labels_path = work / "dept-labels.json"
        if config["department_labels"] is not None:
            labels_path.write_text(json.dumps(config["department_labels"], indent=1), encoding="utf-8")
        proposal = work / f"cc-accrual-{period}.json"
        cc = config["cc"]
        args = [str(card_csv), "--period", period, "--mcc-map", str(mcc_path), "--people-map", str(people_path),
                "--liability-account", liability, "--liability-name", config["liability_name"],
                "--unmapped-account", config["unmapped_account"], "--location", config["location"],
                "--default-department", config["default_department"], "--journal", config["journal"],
                "--vendor-name-floor", str(cc["vendor_name_floor"]), "--out", str(proposal)]
        for cat in cc["always_vendor_named"]:
            args += ["--always-vendor-named", cat]
        if cc["post_date_cutoff"]:
            args += ["--post-date-cutoff", cc["post_date_cutoff"]]
        if config["department_labels"] is not None:
            args += ["--dept-labels", str(labels_path)]
        code, built, _ = run("cc-accrual", args, ok=(0, 1))
        result["card"] = {k: card[k] for k in ("row_count", "total", "dropped")}
        result["queues"] = {"unmapped_merchants": built["unmapped_merchants"],
                            "unmapped_cardholders": built["unmapped_cardholders"]}
        recon = built["department_reconciliation"]
        if recon["source"] == "column" and config["department_labels"] is None:
            recon["note"] = ("the card export has a department column and METADATA_FIELDS.md has no "
                             "'### Department labels' table, so every label is unknown")
        result["department_reconciliation"] = recon
        result["merchant_overrides_used"] = built["merchant_overrides_used"]
        coding_csv = work / f"card-coding-{period}.csv"
        write_coding(coding_csv, built["rows"])
        result["coding"] = str(coding_csv)
        result["tie_out"] = tie_out(card, built)
        result["ready"] = bool(built["ready"]) and result["tie_out"]["ties"]
    else:
        bills = work / f"ap-bill-lines-trailing-{period}.json"
        merge_trailing(need_["found"]["bills"], bills)
        proposal = work / f"vendor-accrual-{period}.json"
        args = vendor_args(config, period, need_["found"]["next_bills"], bills) + ["--out", str(proposal)]
        code, built, _ = run("service-period-accrual", args, ok=(0, 1))
        result["queues"] = {"estimates": built["estimates"], "counts": built["counts"]}
        result["next_pulled_on"] = need_["found"].get("next_pulled_on", "")
        # Every vendor build runs the missing-accrual scan. A flagged vendor is drafted only on the
        # worker's decision; the import file waits until each one has a decision.
        scan = missing_accrual_scan(config, folder, period, built["bills"], extra_dirs)
        decisions = read_decisions(decisions_path, scan)
        for f in scan["flagged"]:
            if name_key(f["vendor"]) in decisions:
                f["decision"] = decisions[name_key(f["vendor"])]
        undecided = [f["vendor"] for f in scan["flagged"] if "decision" not in f]
        scan["undecided"] = undecided
        result["missing_accrual"] = scan
        (work / f"missing-accrual-{period}.json").write_text(json.dumps(scan, indent=1), encoding="utf-8")
        if undecided:
            result["inputs"]["missing"].append({
                "input": "missing-accrual decisions",
                "looked_for": "a decision (accrue or not, with a reason) for each flagged vendor",
                "question": (f"Should {', '.join(undecided)} be accrued for {period}? Each recurs in the history "
                             f"and has nothing booked or billed for the period."),
            })
            result["inputs"]["ready"] = False
            result.update(outcome="waiting", detail=(f"{len(undecided)} flagged vendor(s) need a decision: "
                                                     f"{', '.join(undecided)}; rerun with --decisions FILE"))
            return 4, result
        extra = missing_accrual_lines(scan, decisions, period)
        if extra:
            built = add_lines(built, extra, config, period)
            proposal.write_text(json.dumps(built, indent=1), encoding="utf-8")
            accepted = sorted({ln["vendor"] for ln in extra})
            result["queues"]["missing_accrual_accepted"] = accepted
            built["summary"] += (f"; plus {len(accepted)} missing-accrual estimate(s) accepted by the worker "
                                 f"({', '.join(accepted)}), ${sum(ln['debit'] for ln in extra):,.2f}")
            code = 1
    result["summary"] = built["summary"]
    lines = [ln for prop in built["proposals"] for ln in prop["lines"]]
    result["possible_overlaps"] = overlaps(lines, status["ledger"].get("other_accruals", []))
    if not built["proposals"]:
        result.update(outcome="nothing-to-accrue", detail=built["summary"])
        return 0, result

    _, imported, _ = run("je-import", [str(proposal), "--period", period, "--out", str(target),
                                       "--state", "Posted", "--liability-account", liability])
    lint_code, lint, _ = run("je-import-check", [str(target), "--liability-account", liability,
                                                 "--state", "Posted"], ok=(0, 1))
    result.update(file=str(target), lines=imported["line_count"], entries=imported["je_count"],
                  total_debits=lint["total_debits"], total_credits=lint["total_credits"],
                  lint={"passed": lint["passed"], "findings": lint["findings"]},
                  needs_review=bool(code) or bool(result["possible_overlaps"]) or not result.get("ready", True),
                  outcome="built" if lint["passed"] else "lint-failed")
    if accrual == "cc":
        result["ready"] = result["ready"] and lint["passed"]
        backup.write_text(backup_text(result, built, need_["found"]["card_report"], target.name), encoding="utf-8")
    else:
        backup.write_text(vendor_backup_text(result, target.name), encoding="utf-8")
    result["backup"] = str(backup)
    return (0 if lint["passed"] else 1), result


# ---------------------------------------------------------------------------------------------
# The card accrual's trace, tie-out and backup


CODING_FIELDS = ["date", "merchant", "cardholder", "amount", "mcc", "dept_export", "column_department",
                 "people_department", "department", "department_source", "category", "account",
                 "account_name", "coded_by"]


def write_coding(path: Path, rows: List[dict]) -> None:
    """One line per card row: its source columns, its department and account, and where each came from."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CODING_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def tie_out(card: Dict[str, Any], built: Dict[str, Any]) -> Dict[str, Any]:
    """The card rows' total against the coded rows and the entry's expense lines and offset."""
    lines = [ln for prop in built["proposals"] for ln in prop["lines"]]
    expense = round(sum(float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
                        for ln in lines if ln.get("naming") != "offset"), 2)
    offset = round(sum(float(ln.get("credit") or 0) - float(ln.get("debit") or 0)
                       for ln in lines if ln.get("naming") == "offset"), 2)
    coded = round(sum(float(r["amount"]) for r in built["rows"]), 2)
    card_total = round(float(card["total"]), 2)
    excluded = int(built.get("excluded_by_post_date") or 0)
    ties = abs(coded - expense) < 0.005 and abs(expense - offset) < 0.005 and (
        abs(card_total - coded) < 0.005 or excluded > 0)
    return {"card_rows": card["row_count"], "card_total": card_total, "coded_rows": len(built["rows"]),
            "coded_total": coded, "entry_expense_net": expense, "entry_offset": offset,
            "excluded_by_post_date": excluded, "ties": ties}


def money_cell(value: float) -> str:
    return f"({abs(value):,.2f})" if value < 0 else f"{value:,.2f}"


def backup_text(result: Dict[str, Any], built: Dict[str, Any], card_report: str, file_name: str) -> str:
    """The backup the build writes beside the import file: source, tie-out, departments, coding gaps.
    A person or the workstream adds judgment below it; the build never rewrites it."""
    t, recon, period = result["tie_out"], result["department_reconciliation"], result["period"]
    out = [f"# Backup: {period} credit-card accrual (reversing), DRAFT", "",
           f"Import file: `{file_name}`. Written by `accruals.py build`; not uploaded or posted.", "",
           f"Ready: {'yes' if result.get('ready') else 'no'}. "
           f"{'' if result.get('ready') else 'A department, coding or tie-out gap below needs a person before upload.'}",
           "", "## Source", "",
           f"- Card report: `{Path(card_report).name}`, {t['card_rows']} row(s) in {period}, "
           f"{money_cell(t['card_total'])}; dropped {result['card']['dropped'] or 'none'}.",
           f"- Row trace (department, account and where each came from): `{Path(result['coding']).name}` "
           f"in the work folder.", "", "## Tie-out", "", "| Item | Amount |", "|---|---:|",
           f"| Card rows in the period ({t['card_rows']}) | {money_cell(t['card_total'])} |",
           f"| Coded rows ({t['coded_rows']}) | {money_cell(t['coded_total'])} |",
           f"| Entry expense lines, net | {money_cell(t['entry_expense_net'])} |",
           f"| Entry offset credit | {money_cell(t['entry_offset'])} |", "",
           f"Ties: {'yes' if t['ties'] else 'NO'}"
           + (f"; {t['excluded_by_post_date']} row(s) excluded by the post-date cutoff" if t["excluded_by_post_date"] else "")
           + ".", "", "## Departments", "", recon["summary"] + ".", ""]
    if recon.get("note"):
        out += [recon["note"] + ".", ""]
    out += ["| Department source | Rows | Amount |", "|---|---:|---:|"]
    out += [f"| {k} | {v['rows']} | {money_cell(v['amount'])} |" for k, v in sorted(recon["by_source"].items())]
    if recon["disagreements"]:
        out += ["", "Where the column and the people map disagree:", "",
                "| Cardholder | Column | People map | Used | Rows | Amount |", "|---|---|---|---|---:|---:|"]
        out += [f"| {d['cardholder']} | {d['column']} | {d['people_map']} | {d['used']} | {d['rows']} | "
                f"{money_cell(d['amount'])} |" for d in recon["disagreements"]]
    if recon["unknown_labels"]:
        out += ["", "Labels the label map does not know (department taken from a fallback):", "",
                "| Label | Rows | Amount | Cardholders | Used |", "|---|---:|---:|---|---|"]
        out += [f"| {u['label']} | {u['rows']} | {money_cell(u['amount'])} | {', '.join(u['cardholders'])} | "
                f"{', '.join(u['used'])} |" for u in recon["unknown_labels"]]
    if recon["blanks"]:
        out += ["", "Rows with a blank label (department taken from a fallback):", "",
                "| Cardholder | Used | Rows | Amount |", "|---|---|---:|---:|"]
        out += [f"| {b['cardholder']} | {b['used']} ({b['used_source']}) | {b['rows']} | {money_cell(b['amount'])} |"
                for b in recon["blanks"]]
    unmapped: Dict[Tuple[str, str], List[float]] = {}
    for r in built["rows"]:
        if r["coded_by"] == "unmapped":
            unmapped.setdefault((r["merchant"], r["mcc"]), []).append(float(r["amount"]))
    out += ["", "## Coding", ""]
    if unmapped:
        out += [f"Merchants whose MCC is not in the card account map, coded to the unmapped account:", "",
                "| Merchant | MCC | Rows | Amount |", "|---|---|---:|---:|"]
        out += [f"| {m} | {c} | {len(a)} | {money_cell(round(sum(a), 2))} |" for (m, c), a in sorted(unmapped.items())]
    else:
        out.append("Every merchant mapped.")
    if result.get("merchant_overrides_used"):
        out += ["", "Merchant overrides applied:", "", "| Pattern | Rows | Amount |", "|---|---:|---:|"]
        out += [f"| {k} | {v['rows']} | {money_cell(v['amount'])} |"
                for k, v in sorted(result["merchant_overrides_used"].items())]
    if result["queues"]["unmapped_cardholders"]:
        out += ["", "Cardholders a fallback needed and the people map lacks (accrued at the default "
                "department): " + ", ".join(result["queues"]["unmapped_cardholders"]) + "."]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------
# CLI


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("config")
    p.add_argument("folder", type=Path)
    p = sub.add_parser("scan")
    p.add_argument("folder", type=Path)
    p.add_argument("--period", required=True)
    p.add_argument("--out", type=Path, help="also search this trial folder's import files")
    for name in ("done", "inputs", "build"):
        p = sub.add_parser(name)
        p.add_argument("folder", type=Path)
        p.add_argument("--period", required=True)
        p.add_argument("--accrual", required=True, choices=ACCRUALS)
        if name in ("inputs", "build"):
            p.add_argument("--card-report", help="the card download to use, when the folder holds several")
        if name == "build":
            p.add_argument("--out", type=Path, help="write into this folder instead of the period folder (a trial run)")
            p.add_argument("--ignore-done", action="store_true", help="build even when the done check says done")
            p.add_argument("--decisions", type=Path,
                           help="vendor: the worker's decision on each flagged vendor (JSON; rules.md)")
    args = ap.parse_args(argv)
    try:
        config = load_config(args.folder)
        if args.command == "config":
            print(json.dumps(config, indent=1))
            return 0
        period = check_period(args.period)
        if args.command == "scan":
            print(json.dumps(scan_only(config, args.folder, period, args.out), indent=1))
            return 0
        if args.command == "done":
            print(json.dumps(done(config, args.folder, period, args.accrual), indent=1))
            return 0
        if args.command == "inputs":
            out = inputs(config, args.folder, period, args.accrual, args.card_report)
            print(json.dumps(out, indent=1))
            return 0 if out["ready"] else 4
        code, out = build(config, args.folder, period, args.accrual, args.out, args.ignore_done, args.card_report,
                          args.decisions)
        print(json.dumps(out, indent=1))
        return code
    except Bad as exc:
        print(json.dumps({"outcome": "error", "detail": str(exc)}))
        return 2
    except Refused as exc:
        print(json.dumps({"outcome": "refused", "detail": str(exc)}))
        return 3
    except RuntimeError as exc:
        print(json.dumps({"outcome": "failed", "detail": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
