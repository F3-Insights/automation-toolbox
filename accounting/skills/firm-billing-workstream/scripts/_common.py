"""What the five firm-billing scripts share: BILLING.yaml, the period and its folder, the issued
invoices, the time records, the evidence file and the re-derivation of a draft invoice.

The contract is BILLING.md beside this skill. In short:

- The billing folder holds BILLING.yaml and one folder per period, {yyyy}/{yyyy-mm}/.
  --period-dir DIR names another period folder (a dry run's <run-dir>/billing/{yyyy}/{yyyy-mm}/).
- The period is the month billed, yyyy-mm. Blank means the month before --as-of (else today).
- Money is Decimal rounded to cents. JSON written here carries money and hours as numbers; JSON
  read here is compared through Decimal(str(value)).
- An option left blank on a launch form arrives as --x= and means "not given".
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import yaml

BILLING_YAML = "BILLING.yaml"
PULL_JSON = "billing-pull.json"
PULLED_MD = "pulled.md"
DEFAULT_PATTERN = (r"\((?P<firm>[^)]+)\) Invoice (?P<number>\d{3,6}) to \((?P<client>[^)]+)\) "
                   r"(?P<date>\d{4}-\d{2}-\d{2})")
CADENCES = ("monthly", "quarterly", "milestone")
TIMINGS = ("arrears", "advance", "month-end")
DELIVERIES = ("file", "outlook-drafts")
RATE_KINDS = ("retainer", "hourly", "milestone", "pass-through")
EVIDENCE_COLUMNS = ("id", "client", "state", "draft", "amount", "rate_basis", "months", "evidence",
                    "question", "note", "content_sha256", "review", "review_file", "review_sha256",
                    "updated_at", "by")
STATES = ("drafted", "already-billed", "not-billable", "question", "open")
FINAL_STATES = ("drafted", "already-billed", "not-billable", "question")
WORK_FIELDS = ("state", "draft", "content_sha256", "amount")      # a change here clears the review
REVIEW_FIELDS = ("review", "review_file", "review_sha256")
CLIENT_PREFIX = "client:"
CENT = Decimal("0.01")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


class Bad(Exception):
    """A bad argument or an unreadable input: exit 2."""


class Refused(Exception):
    """A refusal the script exists to make: exit 1."""


class Stale(Exception):
    """BILLING.yaml cannot be read or is not a billing file."""


def blank(value) -> str | None:
    """None for a value that is missing, empty or only whitespace; else the stripped text."""
    text = "" if value is None else str(value).strip()
    return text or None


def truthy(value) -> bool:
    return (blank(value) or "").lower() in ("true", "1", "yes", "on")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_json(data) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False, default=str) + "\n"


def load_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Bad(f"no {what} at {path}") from None
    except (OSError, ValueError) as exc:
        raise Bad(f"{path} could not be read as JSON: {type(exc).__name__}") from None


# ---------------------------------------------------------------- money and months

def dec(value, what: str = "value") -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{what} is not a number")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{what} {value!r} is not a number") from None


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def money(value):
    return None if value is None else float(cents(value))


def fmt_money(value) -> str:
    return f"{cents(dec(value)):,.2f}"


def plain_money(value) -> str:
    return f"{cents(dec(value)):.2f}"


def parse_month(text, what: str = "--period") -> str:
    found = MONTH_RE.match(text or "")
    if not found or not 1 <= int(found.group(2)) <= 12:
        raise Bad(f"{what} {text!r} is not a yyyy-mm month")
    return text


def month_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def first_day(month: str) -> date:
    return date(int(month[:4]), int(month[5:7]), 1)


def last_day(month: str) -> date:
    y, m = int(month[:4]), int(month[5:7])
    return date(y, m, calendar.monthrange(y, m)[1])


def add_months(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7]) - 1 + n
    return f"{y + m // 12:04d}-{m % 12 + 1:02d}"


def months_between(start: str, end: str) -> list[str]:
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def month_name(month: str) -> str:
    return f"{calendar.month_name[int(month[5:7])]} {month[:4]}"


def resolve_period(period, as_of=None) -> tuple[str, date]:
    """(period, as_of): the period given, else the month before as_of (else today)."""
    try:
        today = date.fromisoformat(blank(as_of)) if blank(as_of) else date.today()
    except ValueError:
        raise Bad(f"--as-of {as_of!r} is not a yyyy-mm-dd date") from None
    if blank(period):
        return parse_month(blank(period)), today
    return month_of(today.replace(day=1) - timedelta(days=1)), today


# ---------------------------------------------------------------- folders

def billing_folder(folder) -> Path:
    if not blank(folder):
        raise Bad("FOLDER is required: the firm's billing folder, with BILLING.yaml")
    root = Path(blank(folder)).expanduser()
    if not root.is_dir():
        raise Bad(f"no folder {root}")
    return root


def period_dir(root: Path, period: str, given=None) -> Path:
    return Path(blank(given)).expanduser() if blank(given) else root / period[:4] / period


def pull_path(pdir: Path) -> Path:
    return pdir / "work" / "source" / PULL_JSON


def evidence_path(pdir: Path, period: str) -> Path:
    return pdir / f"BILLING-EVIDENCE-{period}.csv"


def resolve_file(name, *bases: Path) -> Path | None:
    """The file a name points at: absolute, or relative to the first base that has it."""
    if not blank(name):
        return None
    path = Path(name.strip()).expanduser()
    if path.is_absolute():
        return path if path.is_file() else None
    return next((base / path for base in bases if (base / path).is_file()), None)


def load_pull(pdir: Path) -> dict | None:
    path = pull_path(pdir)
    if not path.is_file():
        return None
    data = load_json(path, PULL_JSON)
    if not isinstance(data, dict):
        raise Bad(f"{path} is not a billing pull")
    return data


# ---------------------------------------------------------------- BILLING.yaml

class Billing:
    """BILLING.yaml as read and checked, with the sha256 of its bytes."""

    def __init__(self, path: Path, sha256: str, data: dict):
        self.path, self.sha256, self.data = path, sha256, data
        self.settings = data.get("settings") or {}
        self.firm = data.get("firm") or {}
        self.contracts = data["contracts"]
        self.pattern = re.compile(self.settings.get("invoice_pattern") or DEFAULT_PATTERN)
        terms = self.settings.get("payment_terms_days")
        self.terms_days = 30 if terms in (None, "") else int(terms)
        self.currency = str(self.settings.get("currency") or "USD")

    def contract(self, cid: str) -> dict | None:
        return next((c for c in self.contracts if c["id"] == cid), None)


def _date(value, what: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise Stale(f"{what} {value!r} is not a yyyy-mm-dd date") from None


def _month(value, what: str) -> str:
    if isinstance(value, date):
        return month_of(value)
    text = str(value or "").strip()
    if MONTH_RE.match(text) and 1 <= int(text[5:7]) <= 12:
        return text
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text[:7]
    raise Stale(f"{what} {value!r} is not a yyyy-mm month")


def _number(value, what: str) -> Decimal:
    try:
        return dec(value, what)
    except ValueError as exc:
        raise Stale(str(exc)) from None


def validate_billing(data) -> dict:
    """The checked BILLING.yaml, dates and months normalised; every problem is a Stale."""
    if not isinstance(data, dict):
        raise Stale("the top level is not a mapping")
    if data.get("version") != 1:
        raise Stale(f"version must be 1, not {data.get('version')!r}")
    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        raise Stale("settings is not a mapping")
    if not isinstance(settings.get("invoice_folders") or [], list):
        raise Stale("settings.invoice_folders is not a list")
    if settings.get("invoice_pattern"):
        try:
            groups = set(re.compile(str(settings["invoice_pattern"])).groupindex)
        except re.error as exc:
            raise Stale(f"settings.invoice_pattern is not a regex: {exc}") from None
        if {"number", "client", "date"} - groups:
            raise Stale("settings.invoice_pattern lacks the named groups "
                        + ", ".join(sorted({"number", "client", "date"} - groups)))
    if not isinstance(data.get("firm") or {}, dict):
        raise Stale("firm is not a mapping")
    contracts = data.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        raise Stale("contracts is not a non-empty list")
    seen = set()
    for n, c in enumerate(contracts, start=1):
        if not isinstance(c, dict):
            raise Stale(f"contract {n} is not a mapping")
        cid = str(c.get("id") or "")
        if not KEBAB.match(cid):
            raise Stale(f"contract {n}: id {cid!r} is not kebab-case")
        if cid in seen:
            raise Stale(f"contract {cid} appears twice")
        seen.add(cid)
        for key in ("client", "invoice_tag"):
            if not str(c.get(key) or "").strip():
                raise Stale(f"contract {cid}: {key} is required")
        c["start"] = _date(c.get("start"), f"contract {cid}: start")
        if c["start"] is None:
            raise Stale(f"contract {cid}: start is required")
        c["end"] = _date(c.get("end"), f"contract {cid}: end")
        c["cadence"] = str(c.get("cadence") or "monthly")
        c["timing"] = str(c.get("timing") or "arrears")
        c["email_delivery"] = str(c.get("email_delivery") or "file")
        for key, allowed in (("cadence", CADENCES), ("timing", TIMINGS), ("email_delivery", DELIVERIES)):
            if c[key] not in allowed:
                raise Stale(f"contract {cid}: {key} must be one of {', '.join(allowed)}, not {c[key]!r}")
        po = c.get("po") or {}
        if not isinstance(po, dict):
            raise Stale(f"contract {cid}: po is not a mapping")
        c["po"] = {"required": bool(po.get("required")), "number": blank(po.get("number"))}
        c["confirmed"] = bool(c.get("confirmed"))
        rates = c.get("rates")
        if not isinstance(rates, list) or not rates:
            raise Stale(f"contract {cid}: rates is not a non-empty list")
        rate_ids = set()
        for r in rates:
            if not isinstance(r, dict):
                raise Stale(f"contract {cid}: a rate is not a mapping")
            rid, kind = str(r.get("id") or ""), str(r.get("kind") or "")
            if not rid or rid in rate_ids:
                raise Stale(f"contract {cid}: a rate id is missing or repeated ({rid!r})")
            rate_ids.add(rid)
            if kind not in RATE_KINDS:
                raise Stale(f"contract {cid}: rate {rid} kind must be one of {', '.join(RATE_KINDS)}")
            where = f"contract {cid}: rate {rid}"
            if kind in ("retainer", "milestone"):
                r["amount"] = _number(r.get("amount"), f"{where} amount")
            if kind == "hourly":
                r["rate"] = _number(r.get("rate"), f"{where} rate")
                r["cap_hours"] = None if r.get("cap_hours") is None else _number(r["cap_hours"], f"{where} cap_hours")
            if kind == "milestone":
                r["due"] = _month(r.get("due"), f"{where} due")
            if kind == "pass-through":
                r["markup_pct"] = _number(r.get("markup_pct") or 0, f"{where} markup_pct")
            r["description"] = str(r.get("description") or rid)
    return data


def load_billing(root: Path) -> Billing:
    path = root / BILLING_YAML
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Stale(f"{path} cannot be read ({type(exc).__name__})") from None
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise Stale(f"{path} is not valid YAML ({type(exc).__name__})") from None
    try:
        return Billing(path, sha256_bytes(raw), validate_billing(data))
    except Stale as exc:
        raise Stale(f"{path}: {exc}") from None


def billing_or_bad(root: Path) -> Billing:
    try:
        return load_billing(root)
    except Stale as exc:
        raise Bad(str(exc)) from None


def rates_by_id(contract: dict) -> dict:
    return {r["id"]: r for r in contract["rates"]}


def active_in(contract: dict, month: str) -> bool:
    return contract["start"] <= last_day(month) and (contract["end"] is None or contract["end"] >= first_day(month))


# ---------------------------------------------------------------- the draft check

def content_sha256(draft: dict) -> str:
    body = {k: v for k, v in draft.items() if k != "content_sha256"}
    return sha256_bytes(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                   default=str).encode("utf-8"))


def lines_reasons(contract: dict, pull: dict, doc, period: str, bases) -> tuple[list, Decimal | None, list]:
    """Check a lines document (the lines file, or a draft) against BILLING.yaml and the pull.
    Returns (normalised lines, total, reasons); no reasons means it may be drafted."""
    if not isinstance(doc, dict) or not isinstance(doc.get("lines"), list):
        return [], None, ["the lines file is not an object with a lines list"]
    reasons: list[str] = []
    cid = contract["id"]
    if str(doc.get("contract") or "") != cid:
        reasons.append(f"the lines are for contract {doc.get('contract')!r}, not {cid}")
    if str(doc.get("period") or "") != period:
        reasons.append(f"the lines are for period {doc.get('period')!r}, not {period}")
    if contract["po"]["required"] and not contract["po"]["number"]:
        reasons.append(f"contract {cid} requires a PO and BILLING.yaml has none")
    entry = next((e for e in pull.get("contracts") or [] if e.get("id") == cid), None)
    if entry is None:
        reasons.append(f"the pull has no contract {cid}")
        entry = {}
    unbilled = list(entry.get("unbilled_months") or [])
    months = doc.get("months")
    if not isinstance(months, list) or not months:
        reasons.append("months is not a non-empty list")
        months = []
    months = [str(m) for m in months]
    for m in months:
        if m not in unbilled:
            reasons.append(f"month {m} is not one of the pull's unbilled months for {cid} "
                           f"({', '.join(unbilled) or 'none'})")
    rates = rates_by_id(contract)
    expected = entry.get("expected") or {}
    out, total, retainers = [], Decimal(0), set()
    if not doc["lines"]:
        reasons.append("there are no lines")
    for n, line in enumerate(doc["lines"], start=1):
        where = f"line {n}"
        if not isinstance(line, dict):
            reasons.append(f"{where} is not an object")
            continue
        rid, month = str(line.get("rate_id") or ""), str(line.get("month") or "")
        rate = rates.get(rid)
        if rate is None:
            reasons.append(f"{where}: rate_id {rid!r} is not a rate of {cid} in BILLING.yaml")
            continue
        if month not in months:
            reasons.append(f"{where}: month {month!r} is not in months")
        try:
            qty = dec(line.get("quantity"), f"{where} quantity")
            unit = dec(line.get("unit_price"), f"{where} unit_price")
            amount = dec(line.get("amount"), f"{where} amount")
        except ValueError as exc:
            reasons.append(str(exc))
            continue
        if cents(qty * unit) != cents(amount) or amount != cents(amount):
            reasons.append(f"{where}: amount {amount} is not quantity {qty} times unit_price {unit} "
                           f"({cents(qty * unit)}) to the cent")
        override = blank(line.get("override_reason"))
        evidence = line.get("evidence") or []
        evidence = [evidence] if isinstance(evidence, str) else evidence
        kind = rate["kind"]
        pulled = next((e for e in expected.get(month) or [] if e.get("rate_id") == rid), None)
        basis = (pulled or {}).get("basis") or ""
        if kind == "retainer":
            if unit != rate["amount"]:
                reasons.append(f"{where}: a retainer's unit_price {unit} is not its amount {rate['amount']}")
            if qty != 1:
                reasons.append(f"{where}: a retainer's quantity is {qty}, not 1 for the month")
            if (rid, month) in retainers:
                reasons.append(f"{where}: retainer {rid} is billed twice for {month}")
            retainers.add((rid, month))
            basis = basis or f"retainer {rid}, one month at {plain_money(rate['amount'])}"
        elif kind == "hourly":
            if unit != rate["rate"]:
                reasons.append(f"{where}: an hourly line's unit_price {unit} is not its rate {rate['rate']}")
            want = None if pulled is None or pulled.get("quantity") is None else dec(pulled["quantity"])
            if not override and (want is None or qty != want):
                reasons.append(f"{where}: quantity {qty} is not the pull's hours for {month} "
                               f"({'none in the pull' if want is None else want}) and there is no override_reason")
            basis = basis or f"hourly {rid} at {plain_money(rate['rate'])}"
        elif kind == "milestone":
            if cents(amount) != cents(rate["amount"]):
                reasons.append(f"{where}: milestone {rid} amount {amount} is not its rate amount {rate['amount']}")
            if rate["due"] > period:
                reasons.append(f"{where}: milestone {rid} is due {rate['due']}, after the period")
            basis = basis or f"milestone {rid}, {plain_money(rate['amount'])}"
        else:  # pass-through: the unit price is the cost plus the markup
            markup = rate["markup_pct"]
            if blank(line.get("cost")) is not None:
                try:
                    cost = dec(line.get("cost"), f"{where} cost")
                    if cents(cost * (1 + markup / 100)) != cents(unit):
                        reasons.append(f"{where}: unit_price {unit} is not the cost {cost} plus {markup}%")
                except ValueError as exc:
                    reasons.append(str(exc))
            elif markup != 0:
                reasons.append(f"{where}: a pass-through with a {markup}% markup needs its cost")
            basis = basis or f"pass-through {rid} at cost plus {markup}%"
        if kind in ("milestone", "pass-through"):
            names = [str(e) for e in evidence if blank(e)]
            if not names:
                reasons.append(f"{where}: a {kind} line needs evidence naming a file")
            for name in names:
                if resolve_file(name, *bases) is None:
                    reasons.append(f"{where}: evidence {name!r} is not a file that exists")
        if override:
            basis = f"{basis}; override: {override}" if basis else f"override: {override}"
        description = blank(line.get("description")) or \
            f"{rate['description']}, {month_name(month) if MONTH_RE.match(month) else month}"
        norm = {"rate_id": rid, "kind": kind, "month": month, "description": description,
                "quantity": float(qty), "unit_price": money(unit), "amount": money(amount), "basis": basis}
        if override:
            norm["override_reason"] = override
        if evidence:
            norm["evidence"] = [str(e) for e in evidence]
        if line.get("cost") is not None:
            norm["cost"] = line.get("cost")
        out.append(norm)
        total += cents(amount)
    if doc.get("total") is not None:
        try:
            if cents(dec(doc["total"], "total")) != cents(total):
                reasons.append(f"the total {doc['total']} does not add up to the lines ({cents(total)})")
        except ValueError as exc:
            reasons.append(str(exc))
    return out, cents(total), reasons


def verify_draft(root: Path, billing: Billing, pdir: Path, period: str, draft_path: Path) -> tuple[list, dict | None]:
    """Re-derive a draft against BILLING.yaml and the pull: (reasons, the draft). No reasons is OK."""
    if not draft_path.is_file():
        return [f"no draft at {draft_path}"], None
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{draft_path} could not be read as JSON: {type(exc).__name__}"], None
    if not isinstance(draft, dict):
        return [f"{draft_path} is not a draft invoice"], None
    reasons = []
    if draft.get("content_sha256") != content_sha256(draft):
        reasons.append("content_sha256 does not match the draft's content (edited after drafting)")
    contract = billing.contract(str(draft.get("contract") or ""))
    if contract is None:
        return reasons + [f"contract {draft.get('contract')!r} is not in BILLING.yaml"], draft
    pull = load_pull(pdir)
    if pull is None:
        return reasons + [f"no billing pull at {pull_path(pdir)}"], draft
    if pull.get("billing_sha256") != billing.sha256:
        reasons.append("the pull is stale: BILLING.yaml changed since it was pulled")
    _, total, line_reasons = lines_reasons(contract, pull, draft, period, (pdir, root))
    reasons += line_reasons
    if total is not None and (draft.get("total") is None or cents(dec(draft["total"])) != total):
        reasons.append(f"the total {draft.get('total')} is not the sum of the lines ({total})")
    if draft.get("bill_to") != contract.get("bill_to"):
        reasons.append("bill_to is not the contract's bill_to in BILLING.yaml")
    if draft.get("firm") != billing.firm:
        reasons.append("the firm header is not BILLING.yaml's firm")
    return reasons, draft


# ---------------------------------------------------------------- the evidence file

def read_csv(path: Path) -> list[dict]:
    """A CSV file's rows as dicts, a leading byte-order mark ignored."""
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def evidence_rows(path: Path) -> list[dict]:
    """The evidence file's rows in file order, values stripped; the first row of an id wins."""
    out, seen = [], set()
    for raw in read_csv(path) if path.is_file() else []:
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if row.get("id") and row["id"] not in seen:
            seen.add(row["id"])
            out.append(row)
    return out


def _csv_line(values, terminator: str) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator=terminator).writerow(list(values))
    return buf.getvalue()


def evidence_upsert(path: Path, key: str, values: dict) -> dict:
    """Create the row with id key, or update the first one. Fields not given keep their value;
    every other row keeps its exact text; no row is ever removed; the file is replaced atomically.
    When a work field changes and no new review is given, the old review is cleared."""
    raw = path.read_bytes().decode("utf-8") if path.is_file() else ""
    bom = "﻿" if raw.startswith("﻿") else ""
    text = raw[len(bom):]
    lines = text.splitlines(keepends=True)
    reader = csv.reader(iter(lines))
    records, used = [], 0
    for cells in reader:   # each record with its exact text (a cell may span lines)
        records.append((cells, "".join(lines[used:reader.line_num])))
        used = reader.line_num
    terminator = "\r\n" if records and records[0][1].endswith("\r\n") else "\n"
    if records and [c.strip() for c in records[0][0]] != list(EVIDENCE_COLUMNS):
        raise Refused(f"{path.name} does not start with the header {','.join(EVIDENCE_COLUMNS)}")
    if not records:
        records = [(list(EVIDENCE_COLUMNS), _csv_line(EVIDENCE_COLUMNS, terminator))]
    index = next((i for i, (cells, _) in enumerate(records) if i and cells and cells[0].strip() == key), None)
    old = dict(zip(EVIDENCE_COLUMNS, [c.strip() for c in records[index][0]] + [""] * 16)) if index else {}
    row = {c: old.get(c, "") for c in EVIDENCE_COLUMNS}
    row.update({k: "" if v is None else str(v) for k, v in values.items()})
    row["id"] = key
    work_changed = any(f in values and row[f] != old.get(f, "") for f in WORK_FIELDS)
    cleared = bool(old) and work_changed and "review" not in values and bool(old.get("review"))
    if cleared:
        for f in REVIEW_FIELDS:
            if f not in values:
                row[f] = ""
    if row["state"] not in STATES:
        raise Refused(f"--state {row['state']!r} is not one of {', '.join(STATES)}")
    line = _csv_line([row[c] for c in EVIDENCE_COLUMNS], terminator)
    if index:
        records[index] = (records[index][0], line)
    else:
        if not records[-1][1].endswith(("\n", "\r")):
            records[-1] = (records[-1][0], records[-1][1] + terminator)
        records.append(([], line))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(bom + "".join(r for _, r in records))
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():   # the replacement keeps the old file's permissions
            os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return {"action": "updated" if index else "created", "row": row, "review_cleared": cleared}
