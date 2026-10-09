"""Helpers the erp-ledger-pull scripts share: settings, snapshot files, the standard ledger
fields, a read-only Sage Intacct session, and the snapshot pull with its gates.

Nothing here writes to an ERP. The Intacct session can only ask for a token and run
queries; there is no create, update or delete call anywhere in this folder.

Credentials come from the environment only, never from a file:

    SAGE_INTACCT_CLIENT_ID, SAGE_INTACCT_CLIENT_SECRET    the web-services app
    SAGE_INTACCT_COMPANY_ID                               or setting intacct_company_id
    SAGE_INTACCT_API_USER                                 or setting intacct_api_user

For the SANDBOX environment each name is tried with a `_SANDBOX` suffix first
(SAGE_INTACCT_CLIENT_ID_SANDBOX), then without it. The two settings sit in the
`[erp-ledger-pull]` table of the owner settings file.
"""

from __future__ import annotations

import calendar
import json
import os
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_BASE = "https://api.intacct.com/ia/api/v1"
PAGE_SIZE = 1000
SKILL = "erp-ledger-pull"


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


# --- snapshot files ---------------------------------------------------------------------------
# A snapshot is {"meta": {...}, "rows": [...]} or a bare list of rows.


def load_snapshot(path):
    """(rows, meta) from either snapshot shape."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"snapshot not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("rows") or []), dict(data.get("meta") or {})
    if isinstance(data, list):
        return data, {}
    raise ValueError(f"{path}: a snapshot is a list of rows or a {{meta, rows}} object")


def write_snapshot(path, rows, meta):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "rows": rows}, indent=1), encoding="utf-8")
    return path


def server_total(meta):
    """The server's row count a snapshot recorded, under any of the names in use, or None."""
    for key in ("server_total", "server-total-count", "server_total_count", "totalCount"):
        if meta.get(key) is not None:
            return int(meta[key])
    return None


def shift_period(period, months):
    year, month = (int(p) for p in period.split("-")[:2])
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def period_end(period):
    year, month = (int(p) for p in period.split("-")[:2])
    return f"{period[:7]}-{calendar.monthrange(year, month)[1]:02d}"


# --- the standard ledger fields ---------------------------------------------------------------
# A GL line is read in the standard shape gl-normalize writes (account, date, debit, credit)
# or in Intacct's dotted shape as a pull lands it (glAccount.id, entryDate, txnType with an
# unsigned baseAmount). The standard name wins when the row carries it.

INTACCT_LINE = {
    "je_id": "journalEntry.key", "line_no": "id", "journal": "journalEntry.glJournal.id",
    "date": "entryDate", "posting_date": "entryDate", "account": "glAccount.id",
    "account_name": "glAccount.name", "department": "dimensions.department.id",
    "location": "dimensions.location.id", "class": "dimensions.class.id", "memo": "description",
    "state": "journalEntry.state", "created_at": "audit.createdDateTime",
    "created_by": "audit.createdBy", "vendor": "dimensions.vendor.id",
    "customer": "dimensions.customer.id",
}


def money(value):
    """Amounts arrive as strings or numbers; blank means zero."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", ""))


def ln(row, name):
    """The text of standard field `name` on a GL line of either shape ('' when absent)."""
    value = row[name] if name in row else row.get(INTACCT_LINE.get(name, name))
    return "" if value is None else str(value)


def signed(row):
    """A GL line's amount, debits positive."""
    if "debit" in row or "credit" in row:
        return money(row.get("debit")) - money(row.get("credit"))
    amount = money(row.get("baseAmount") or row.get("txnAmount"))
    return amount if str(row.get("txnType", "")).lower().startswith("d") else -amount


# --- Sage Intacct, read only ------------------------------------------------------------------


class IntacctError(Exception):
    """An authentication or API failure, with the response body Intacct sent."""

    def __init__(self, message, status=None, body=None):
        detail = f" (HTTP {status})" if status else ""
        super().__init__(f"{message}{detail}\n{body or ''}".rstrip())


class NoCredentials(Exception):
    """The environment does not name a complete set of Intacct credentials."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # a redirect is an error, never followed


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_json(url, method="GET", body=None, headers=None, timeout=60):
    """One HTTPS request, JSON in and out. Intacct's error bodies name the bad field, so they
    are kept in the error."""
    # Intacct's edge refuses Python's default User-Agent, so the request names itself.
    hdrs = {"User-Agent": os.environ.get("INTACCT_USER_AGENT", "f3i-toolbox-intacct/1.0 (read-only)"),
            **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise IntacctError(f"Request to {url} failed", exc.code,
                           exc.read().decode("utf-8", errors="replace")) from None
    except urllib.error.URLError as exc:
        raise IntacctError(f"Could not reach {url}: {exc.reason}") from None


class IntacctSession:
    """An OAuth client-credentials session that can only GET and query."""

    def __init__(self, client_id, client_secret, company_id, api_user):
        self._login = {"grant_type": "client_credentials", "client_id": client_id,
                       "client_secret": client_secret, "username": f"{api_user}@{company_id}"}
        self._token = None

    def _headers(self):
        if not self._token:
            self._token = http_json(f"{API_BASE}/oauth2/token", "POST", self._login)["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def get(self, endpoint):
        return http_json(f"{API_BASE}{endpoint}", headers=self._headers())

    def query(self, object_name, fields, filters=None, order_by=None, max_records=None):
        """Every row matching the filters (ANDed), page by page: (rows, server total)."""
        rows, start, total = [], 1, None
        while True:
            size = PAGE_SIZE if max_records is None else min(PAGE_SIZE, max_records - len(rows))
            if size <= 0:
                break
            body = {"object": object_name, "fields": fields, "start": start, "size": size}
            if filters:
                body["filters"] = filters
                if len(filters) > 1:
                    body["filterExpression"] = " and ".join(str(i + 1) for i in range(len(filters)))
            if order_by:
                body["orderBy"] = order_by
            response = http_json(f"{API_BASE}/services/core/query", "POST", body, self._headers())
            page = response.get("ia::result") or []
            total = (response.get("ia::meta") or {}).get("totalCount", total)
            rows.extend(page)
            if not page or len(page) < size or (total is not None and len(rows) >= total):
                break
            start += len(page)
        return rows, total


def credentials(environment="PROD", api_user=""):
    """(client_id, client_secret, company_id, api_user) from the environment and settings.
    Raises NoCredentials naming what is missing, never a value."""
    mine = settings(SKILL)

    def env(name):
        if environment.upper() != "PROD" and os.environ.get(f"{name}_{environment.upper()}"):
            return os.environ[f"{name}_{environment.upper()}"]
        return os.environ.get(name, "")

    values = {
        "SAGE_INTACCT_CLIENT_ID": env("SAGE_INTACCT_CLIENT_ID"),
        "SAGE_INTACCT_CLIENT_SECRET": env("SAGE_INTACCT_CLIENT_SECRET"),
        "SAGE_INTACCT_COMPANY_ID": env("SAGE_INTACCT_COMPANY_ID") or str(mine.get("intacct_company_id", "")),
        "SAGE_INTACCT_API_USER": env("SAGE_INTACCT_API_USER") or str(mine.get("intacct_api_user", "")) or api_user,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise NoCredentials("no Sage Intacct credentials: set " + ", ".join(missing) + " in the environment"
                            " (the company id and API user may instead be the settings intacct_company_id"
                            f" and intacct_api_user under [{SKILL}])")
    return tuple(values.values())


# --- the snapshot pull ------------------------------------------------------------------------
# What intacct-snapshot and month-end-pull read from Intacct. Field lists are overridable per
# object through a config file's "objects" key.

AP_FIELDS = ["id", "bill.id", "bill.postingDate", "vendor.name", "glAccount.id", "glAccount.name",
             "baseAmount", "memo", "dimensions.department.id", "dimensions.location.id"]
OBJECTS = {
    "headers": {"prefixes": ("headers",), "object": "general-ledger/journal-entry", "date_field": "postingDate",
                "fields": ["id", "key", "postingDate", "state", "description", "referenceNumber", "txnSource",
                           "moduleName", "scheduledOperationKey", "reversedFromDate", "balance", "glJournal.id",
                           "entity.id", "entity.name"]},
    "lines": {"prefixes": ("lines",), "object": "general-ledger/journal-entry-line", "date_field": "entryDate",
              "fields": ["id", "journalEntry.key", "glAccount.id", "glAccount.name", "entryDate",
                         "accountingPeriod", "txnType", "txnAmount", "baseAmount", "description",
                         "dimensions.location.id", "dimensions.location.name", "dimensions.department.id",
                         "dimensions.customer.id", "dimensions.vendor.id", "dimensions.class.id",
                         "journalEntry.glJournal.id", "journalEntry.state", "audit.createdDateTime",
                         "audit.createdBy"]},
    "ap_bill_lines": {"prefixes": ("ap-bill-lines", "ap_bill_lines"), "object": "accounts-payable/bill-line",
                      "date_field": "bill.postingDate", "fields": AP_FIELDS},
    # Bills posted after the period, from the 1st of the next month to today: the service-period
    # accrual reads their memos.
    "ap_bill_lines_next": {"prefixes": ("ap-bill-lines-next",), "object": "accounts-payable/bill-line",
                           "date_field": "bill.postingDate", "range": "next", "fields": AP_FIELDS},
    "ar_invoice_lines": {"prefixes": ("ar-invoice-lines", "ar_invoice_lines"),
                         "object": "accounts-receivable/invoice-line", "date_field": "invoice.invoiceDate",
                         "fields": ["id", "invoice.id", "invoice.invoiceDate", "invoice.customer.name",
                                    "glAccount.id", "glAccount.name", "baseAmount", "memo",
                                    "dimensions.location.id"]},
    # Budget rows carry no transaction date, so the whole object is pulled.
    "budget_detail": {"prefixes": ("budget-detail", "budget_detail"), "object": "general-ledger/budget-detail",
                      "date_field": "", "range": "all",
                      "fields": ["id", "key", "amount", "budget.id", "glAccount.id", "reportingPeriod.id",
                                 "entity.id", "dimensions.department.id", "dimensions.location.id", "notes"]},
}


def resolve_sources(directory, name, named=None):
    """The snapshot file(s) for one object: named[name] (a path or list), else the first file
    in `directory` whose name starts with one of the object's prefixes."""
    named = named or {}
    if name in named:
        value = named[name]
        paths = [Path(str(p)) for p in ([value] if isinstance(value, (str, Path)) else value)]
        return [p if p.is_absolute() else Path(directory) / p for p in paths]
    for file in sorted(Path(directory).glob("*.json")):
        if file.name.startswith(OBJECTS[name]["prefixes"]):
            return [file]
    return []


def pull_live(session, period, baseline_months, out_dir, specs, wanted=None, environment="PROD", today=""):
    """Query each object over the period plus `baseline_months` before it and write one
    snapshot per object. Returns one manifest entry per object."""
    start = f"{shift_period(period, -baseline_months)}-01"
    end = period_end(period)
    today = today or datetime.now(timezone.utc).date().isoformat()
    pulled = []
    for name in wanted or list(specs):
        spec = specs[name]
        field, scope = spec.get("date_field") or "", spec.get("range", "period")
        if scope == "all" or not field:
            filters = None
        elif scope == "next":
            filters = [{"$gte": {field: f"{shift_period(period, 1)}-01"}}, {"$lte": {field: today}}]
        else:
            filters = [{"$gte": {field: start}}, {"$lte": {field: end}}]
        rows, total = session.query(spec["object"], spec["fields"], filters=filters,
                                    order_by=[{field: "asc"}] if field else None)
        meta = {"pulled-at": datetime.now(timezone.utc).isoformat(), "object": spec["object"],
                "fields": spec["fields"], "filters": filters, "row-count": len(rows),
                "server-total-count": total, "environment": environment}
        path = write_snapshot(Path(out_dir) / f"{name.replace('_', '-')}-{period}.json", rows, meta)
        pulled.append({"name": name, "object": spec["object"], "source": str(path), "sources": [str(path)],
                       "rows": len(rows), "server_total": total, "pulled_at": meta["pulled-at"]})
    return pulled


def gate_counts(objects, required=True):
    """counts_tie: an object's rows must equal the server's total. No total is unverifiable."""
    findings = []
    for obj in objects:
        total = obj.get("server_total")
        if total is None:
            findings.append({"gate": "counts_tie", "severity": "error" if required else "info",
                             "object": obj["name"],
                             "detail": f"{obj['rows']:,} row(s) with no server total in meta: unverifiable"})
        elif int(total) != int(obj["rows"]):
            findings.append({"gate": "counts_tie", "severity": "error", "object": obj["name"],
                             "detail": f"{obj['rows']:,} row(s) but the server reported {int(total):,}"})
    return findings


def gate_vintage(objects, max_skew_hours=1.0):
    """one_vintage: every object pulled within `max_skew_hours` of the others."""
    stamps = {}
    for obj in objects:
        if obj.get("pulled_at"):
            try:
                stamps[obj["name"]] = datetime.fromisoformat(str(obj["pulled_at"]).replace("Z", "+00:00"))
            except ValueError:
                return [{"gate": "one_vintage", "severity": "error", "object": obj["name"],
                         "detail": f"unparseable pulled-at {obj['pulled_at']!r}"}]
    if len(stamps) < 2:
        return []
    old, new = min(stamps, key=stamps.get), max(stamps, key=stamps.get)
    if stamps[new] - stamps[old] <= timedelta(hours=max_skew_hours):
        return []
    hours = (stamps[new] - stamps[old]).total_seconds() / 3600
    return [{"gate": "one_vintage", "severity": "error", "object": new,
             "detail": (f"{hours:.1f}h between {old} ({stamps[old].isoformat()}) and {new} "
                        f"({stamps[new].isoformat()}); limit is {max_skew_hours}h")}]


def gate_lines_have_headers(lines, headers, known_creators=(), known_journals=()):
    """lines_have_headers: every line's entry key resolves to a header. Lines from a known
    integration creator or journal (whose headers the API does not return) are info only."""
    have = {str(h.get("key") or "") for h in headers} | {str(h.get("id") or "") for h in headers}
    orphans = {}
    for line in lines:
        key = str(line.get("journalEntry.key") or "")
        if key and key not in have:
            entry = orphans.setdefault(key, {"lines": 0, "creator": str(line.get("audit.createdBy") or ""),
                                             "journal": str(line.get("journalEntry.glJournal.id") or "")})
            entry["lines"] += 1
    creators, journals = {str(c) for c in known_creators or ()}, {str(j) for j in known_journals or ()}
    findings = []
    for key, e in sorted(orphans.items()):
        known = e["creator"] in creators or e["journal"] in journals
        findings.append({"gate": "lines_have_headers", "severity": "info" if known else "error", "object": "lines",
                         "detail": (f"JE{key} has {e['lines']} line(s) and no header (journal "
                                    f"{e['journal'] or '?'}, created by {e['creator'] or '?'})"
                                    + (" - known integration creator" if known else ""))})
    return findings


def gate_snapshot(objects, max_skew_hours=1.0, counts_required=True, known_creators=(), known_journals=()):
    """The three gates over a list of manifest entries."""
    findings = gate_counts(objects, counts_required) + gate_vintage(objects, max_skew_hours)
    by_name = {o["name"]: o for o in objects}
    if "lines" in by_name and "headers" in by_name:
        lines, _ = load_snapshot(by_name["lines"]["source"])
        headers, _ = load_snapshot(by_name["headers"]["source"])
        findings += gate_lines_have_headers(lines, headers, known_creators, known_journals)
    return findings
