"""Shared by the forecast scripts: the Forecast folder and its vintages, a workbook read as an
account x month grid, the bridge from the prior forecast to the new one, and the evidence ledger.

A Forecast folder holds FORECAST-SETTINGS.yaml (how this company's workbooks are read, its
thresholds), modules.yaml (the bridge lines, each with the account prefixes it claims, an owner
and a materiality) and FORECAST-RULES.md. Each vintage sits in vintages/<vintage>/ with its
VINTAGE.yaml. Everything specific to one company lives in those files; the values below are
generic defaults a settings file overrides.

Money is kept to the cent and compared with a tolerance, never with ==. Workbooks are opened
read-only here; nothing in this file can save one.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

SETTINGS_FILE = "FORECAST-SETTINGS.yaml"
VINTAGE_FILE = "VINTAGE.yaml"
CALIBRATION = "calibration.jsonl"

DEFAULTS = {
    "basis": "pre_bonus",                 # pre_bonus or post_bonus EBITDA, held throughout
    "tolerance": 0.005,                   # dollars: every foot, tie and bridge closes to half a cent
    "materiality_abs": 25000.0,           # a bridge line or flag without its own materiality
    "hypothesis_tolerance_abs": 50000.0,  # a miss inside this needs no deep dive
    "hypothesis_tolerance_pct": 0.25,     # or inside this share of the expected change
    "run_rate_months": 3,                 # trailing actual months a forecast month is judged against
    "run_rate_floor": 0.5,                # below this share of the run rate a month is flagged
    "run_rate_ceiling": 2.0,              # above this multiple of the run rate a month is flagged
    "run_rate_min_amount": 1000.0,        # amounts smaller than this are not screened
    "swing_pct": 0.5,                     # a month-on-month move beyond this share is a swing
    "question_materiality_floor": 25000.0,
    "summary_k_tolerance": 0.5,           # $k: how far a quoted figure may sit from the bridge
    "min_anticipated_questions": 3,
    "min_top_drivers": 3,
    "min_what_would_change_it": 2,
    "max_messages_per_week": 1,           # batched messages to the model's owner, per ISO week
    "process_words": ["workflow", "phase", "gate", "envelope", "snapshot", "agent", "prompt",
                      "pipeline", "orchestrator", "sub-agent", "subagent"],
}
SECTIONS = ("revenue", "cogs", "sga", "other", "below_ebitda")
DEFAULT_SECTION_PREFIXES = {"4": "revenue", "5": "cogs", "6": "sga", "7": "sga",
                            "8": "below_ebitda", "9": "below_ebitda"}
TIE_KEYS = ("revenue", "cogs", "sga", "bonus", "ebitda", "ebitda_pre_bonus")
VINTAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MONTH_RE = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")


class ForecastError(Exception):
    """A missing or malformed setting, file or argument. The scripts exit 2 on it."""


# --- the Forecast folder ------------------------------------------------------------------------


def load_yaml(path, what):
    import yaml  # imported on use so --help works without it
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8").lstrip("\ufeff")) or {}
    except FileNotFoundError:
        raise ForecastError(f"{what}: {path} does not exist") from None
    except yaml.YAMLError as exc:
        raise ForecastError(f"{what}: {path} is not valid YAML: {exc}") from None


def forecast_folder(folder):
    path = Path(folder).expanduser()
    if not path.is_dir():
        raise ForecastError(f"the Forecast folder {path} does not exist")
    if not (path / SETTINGS_FILE).is_file():
        raise ForecastError(f"{path} has no {SETTINGS_FILE}; it is not a Forecast folder")
    return path


def load_settings(folder):
    """The folder's settings over the defaults; `thresholds:` entries are lifted to the top."""
    root = forecast_folder(folder)
    data = load_yaml(root / SETTINGS_FILE, "settings")
    if not isinstance(data, dict):
        raise ForecastError(f"{root / SETTINGS_FILE} must hold a mapping")
    merged = dict(DEFAULTS)
    merged.update(data.get("thresholds") or {})
    merged.update({k: v for k, v in data.items() if k != "thresholds"})
    merged["_root"] = str(root)
    if merged["basis"] not in ("pre_bonus", "post_bonus"):
        raise ForecastError("setting `basis` must be pre_bonus or post_bonus")
    return merged


def layout(settings, name=""):
    """How one kind of workbook is read (`layouts.<name>`, or `layouts.default`), with the
    folder's `accounts` block folded in."""
    layouts = settings.get("layouts") or {}
    if not isinstance(layouts, dict) or not layouts:
        raise ForecastError("settings need a `layouts:` block naming how a forecast workbook is read")
    key = name or "default"
    if key not in layouts:
        raise ForecastError(f"settings have no layout `{key}` (have: {', '.join(sorted(layouts))})")
    out = dict(layouts[key] or {})
    accounts = settings.get("accounts") or {}
    for field in ("section_prefixes", "bonus_accounts", "contra_revenue_accounts", "expense_sign"):
        if field not in out and field in accounts:
            out[field] = accounts[field]
    out.setdefault("section_prefixes", DEFAULT_SECTION_PREFIXES)
    out.setdefault("bonus_accounts", [])
    out.setdefault("contra_revenue_accounts", [])
    out.setdefault("expense_sign", "positive")
    for required in ("sheet", "header_row", "columns"):
        if required not in out:
            raise ForecastError(f"layout `{key}` needs `{required}`")
    if "account" not in (out.get("columns") or {}):
        raise ForecastError(f"layout `{key}`: `columns` must name the `account` column")
    return out


def modules_path(settings):
    return resolve_path(settings["_root"], settings.get("modules_file") or "modules.yaml")


def load_modules(settings):
    """The bridge lines from modules.yaml: key, label, account prefixes, owner, materiality, active."""
    path = modules_path(settings)
    data = load_yaml(path, "modules")
    raw = data.get("modules") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise ForecastError(f"{path} must hold a non-empty `modules:` list")
    modules, seen = [], set()
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("key"):
            raise ForecastError(f"{path}: every module needs a `key`, got {entry!r}")
        key = str(entry["key"])
        if key in seen:
            raise ForecastError(f"{path}: duplicate module key {key!r}")
        seen.add(key)
        modules.append(dict(entry, key=key, label=str(entry.get("label") or key),
                            accounts=[str(a).strip() for a in entry.get("accounts") or [] if str(a).strip()],
                            active=bool(entry.get("active", True)),
                            materiality_abs=float(entry.get("materiality_abs", settings["materiality_abs"]))))
    return modules


def resolve_path(root, value):
    """A path from a settings or vintage file: absolute, `~`, or relative to the folder."""
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else Path(root) / path


def vintage_dir(root, vintage):
    if not VINTAGE_RE.match(str(vintage or "")):
        raise ForecastError(f"vintage {vintage!r} must be a short slug (letters, digits, . _ -)")
    return Path(root) / "vintages" / vintage


def vintages(root):
    """Every vintage folder with a VINTAGE.yaml, oldest first by its `created` stamp."""
    base = Path(root) / "vintages"
    found = []
    for child in sorted(base.iterdir()) if base.is_dir() else []:
        if (child / VINTAGE_FILE).is_file():
            found.append((str(load_yaml(child / VINTAGE_FILE, "vintage").get("created") or ""), child.name))
    return [name for _, name in sorted(found)]


def current_vintage(root):
    names = vintages(root)
    return names[-1] if names else None


def load_vintage(root, vintage):
    folder = vintage_dir(root, vintage)
    meta = folder / VINTAGE_FILE
    if not meta.is_file():
        raise ForecastError(f"vintage {vintage} has no {VINTAGE_FILE} (run forecast-prepare first)")
    data = load_yaml(meta, "vintage")
    if not isinstance(data, dict):
        raise ForecastError(f"{meta} must hold a mapping")
    data = dict(data, vintage=vintage, _dir=str(folder))
    years = data.get("years") or []
    data["years"] = [int(y) for y in ([years] if isinstance(years, (int, str)) else years)]
    for key in ("last_actual_month", "prior_last_actual_month"):
        value = str(data.get(key) or "")
        if value and not MONTH_RE.match(value):
            raise ForecastError(f"{meta}: `{key}` must be YYYY-MM, got {value!r}")
        data[key] = value
    return data


def revisions(settings):
    """Issued revisions in the settings' `revisions.folder`, oldest first: by the number the
    `revisions.number` pattern captures, then by modification time."""
    spec = settings.get("revisions") or {}
    if not spec.get("folder"):
        return []
    folder = resolve_path(settings["_root"], spec["folder"])
    if not folder.is_dir():
        raise ForecastError(f"revisions.folder {folder} does not exist")
    number = re.compile(spec.get("number") or r"rev(\d+)", re.I)

    def key(path):
        match = number.search(path.name)
        return (int(match.group(1)) if match else -1, path.stat().st_mtime)

    files = [p for p in folder.glob(spec.get("pattern") or "*.xlsx")
             if p.is_file() and not p.name.startswith(("~$", "."))]
    return sorted(files, key=key)


def read_json(path):
    """A JSON file, None when missing, {"_unreadable": True} when it does not parse."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_unreadable": True}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- money and months ---------------------------------------------------------------------------


def money(value):
    """A cell as dollars to the cent. Blank, text and error values are 0.00; (1,234) is negative."""
    if value in (None, "") or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2) + 0.0
    text = str(value).strip().replace(",", "").replace("$", "")
    negative = text.startswith("(") and text.endswith(")")
    try:
        amount = float(text[1:-1] if negative else text)
    except ValueError:
        return 0.0
    return round(-amount if negative else amount, 2) + 0.0


def cents(value):
    return round(float(value), 2) + 0.0


def close(a, b, tolerance):
    return abs(cents(a) - cents(b)) <= float(tolerance) + 1e-9


def file_sha(path):
    """SHA-256 of a file, or "" when it does not exist."""
    path = Path(path)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august",
               "september", "october", "november", "december")
_ISO_MONTH = re.compile(r"(20\d{2})[-/](0[1-9]|1[0-2])(?!\d)")
_WORD_MONTH = re.compile(r"([A-Za-z]{3,9})\.?\s+(20\d{2})")
_SHORT_MONTH = re.compile(r"\b([A-Za-z]{3,9})\.?\s*['’-]\s*(\d{2})(?!\d)")


def month_of_header(cell):
    """"YYYY-MM" for a month column's header (a date, "Sep 2026", "Month Ended September 2026",
    "2026-09", "Sep'26"), or "" when the cell is not a month."""
    if isinstance(cell, (datetime, date)):
        return f"{cell.year:04d}-{cell.month:02d}"
    if cell in (None, ""):
        return ""
    text = str(cell).strip()
    match = _ISO_MONTH.search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    for pattern, century in ((_WORD_MONTH, ""), (_SHORT_MONTH, "20")):
        words = pattern.search(text)
        if words:
            name = words.group(1).lower()
            for number, month in enumerate(MONTH_NAMES, start=1):
                if name == month or (len(name) >= 3 and month.startswith(name)):
                    return f"{century}{words.group(2)}-{number:02d}"
    return ""


def year_months(year):
    return [f"{int(year):04d}-{m:02d}" for m in range(1, 13)]


def months_between(first, last):
    year, month = int(first[:4]), int(first[5:7])
    out = []
    while f"{year:04d}-{month:02d}" <= last:
        out.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def quarter_label(month):
    """"2026-09" -> "Q3'26"."""
    year, _, number = month.partition("-")
    return f"Q{(int(number) - 1) // 3 + 1}'{int(year) % 100:02d}"


def section_of(account, prefixes=None):
    """The income-statement section from the account prefix; the longest prefix wins."""
    best, found = "", "other"
    for prefix, section in (prefixes or DEFAULT_SECTION_PREFIXES).items():
        if str(account).strip().startswith(str(prefix)) and len(str(prefix)) > len(best):
            best, found = str(prefix), str(section)
    if found not in SECTIONS:
        raise ForecastError(f"section_prefixes maps {best!r} to {found!r}, not one of {', '.join(SECTIONS)}")
    return found


def ebitda_sign(section, expense_sign="positive"):
    """What a one-dollar increase in an account of this section does to EBITDA."""
    if section == "revenue":
        return 1.0
    if section in ("cogs", "sga"):
        return -1.0 if expense_sign == "positive" else 1.0
    return 0.0


def ident(value, blank_token="blank"):
    """An identity cell as text: blanks, the sheet's blank token and 11.0 all normalise."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        text = text[:-2]
    return "" if blank_token and text.lower() == str(blank_token).lower() else text


def row_key(row):
    return "|".join(str(row.get(k, "")) for k in ("account", "department", "location", "cls"))


# --- reading a workbook -------------------------------------------------------------------------


def column_index(text, header, where):
    """Where a column is: by its header text, or `col:A` for a column with no header."""
    raw = str(text).strip()
    if raw.lower().startswith("col:"):
        letters = raw[4:].strip().upper()
        if not letters.isalpha():
            raise ForecastError(f"{where}: column reference '{raw}' must be `col:` plus column letters")
        at = 0
        for letter in letters:
            at = at * 26 + ord(letter) - 64
        return at - 1
    labels = ["" if cell is None else str(cell).strip() for cell in header]
    index = {label.lower(): position for position, label in enumerate(labels) if label}
    if raw.lower() not in index:
        raise ForecastError(f"{where}: no column headed '{text}' on the header row (found: "
                            f"{', '.join(l for l in labels if l) or 'none'}); a headerless column "
                            "can be addressed as `col:A`")
    return index[raw.lower()]


def cell_at(row, at):
    return row[at] if 0 <= at < len(row) else None


def read_grid(workbook, sheet):
    """Every row of one sheet as cached values, the workbook opened read-only."""
    from openpyxl import load_workbook
    path = Path(workbook)
    if not path.is_file():
        raise ForecastError(f"workbook does not exist: {path}")
    book = load_workbook(str(path), read_only=True, data_only=True)
    try:
        if sheet not in book.sheetnames:
            raise ForecastError(f"{path.name}: no sheet named '{sheet}' (has: {', '.join(book.sheetnames)})")
        return list(book[sheet].iter_rows(values_only=True))
    finally:
        book.close()


def read_workbook(workbook, spec, label=""):
    """One workbook read as a layout says. A layout names `sheet`, `header_row`, `columns`
    (`account` required; `account_name`, `department`, `location`, `cls` optional), and
    optionally `row_filter` ({header: value}), `blank_token`, `label_column`, `band` ({row,
    include}: keep only month columns whose band cell starts with one of `include`), `tie_rows`,
    `zero_rows`, `section_prefixes`, `bonus_accounts`, `contra_revenue_accounts`, `expense_sign`.

    Rows with the same account x department x location x class are summed. Rows with no account
    but a label are kept aside for the tie and zero controls."""
    path = Path(workbook)
    sheet = str(spec["sheet"])
    where = f"{path.name}!{sheet}"
    grid = read_grid(path, sheet)
    header_row = int(spec["header_row"])
    if len(grid) < header_row:
        raise ForecastError(f"{where}: header row {header_row} is past the end of the sheet")
    header, body = list(grid[header_row - 1]), grid[header_row:]
    band = spec.get("band") or {}
    band_cells = []
    if band:
        band_row = int(band.get("row", 0))
        if not 1 <= band_row <= len(grid):
            raise ForecastError(f"{where}: band row {band_row} is not on the sheet")
        band_cells = list(grid[band_row - 1])
    band_keep = [str(v).strip().lower() for v in band.get("include") or []]
    blank = str(spec.get("blank_token", "blank") or "")
    columns = {n: t for n, t in (spec.get("columns") or {}).items() if str(t or "").strip()}
    at = {n: column_index(t, header, f"{where} (`{n}`)") for n, t in columns.items()}
    filters = [(column_index(t, header, f"{where} (row_filter)"), str(v))
               for t, v in (spec.get("row_filter") or {}).items()]
    labels_spec = spec.get("label_column")
    if labels_spec:
        label_ats = [column_index(t, header, f"{where} (label_column)")
                     for t in (labels_spec if isinstance(labels_spec, list) else [labels_spec])]
    else:
        label_ats = [at["account_name"]] if "account_name" in at else []

    # Months are located by their header, never counted; a month headed twice is a failed control.
    month_at, repeated = {}, []
    for position, cell in enumerate(header):
        month = month_of_header(cell)
        if not month:
            continue
        if band_keep:
            mark = str(cell_at(band_cells, position) or "").strip().lower()
            if not any(mark.startswith(keep) for keep in band_keep):
                continue
        if month in month_at:
            repeated.append(f"{month} (columns {month_at[month] + 1} and {position + 1})")
        else:
            month_at[month] = position
    if not month_at:
        raise ForecastError(f"{where}: no month columns found on header row {header_row}")
    months = sorted(month_at)
    gaps = [m for m in months_between(months[0], months[-1]) if m not in month_at]

    prefixes = {str(k): str(v) for k, v in (spec.get("section_prefixes") or DEFAULT_SECTION_PREFIXES).items()}
    contra = {str(a).strip() for a in spec.get("contra_revenue_accounts") or []}
    merged, label_rows = {}, []
    for raw in body:
        passes = all(ident(cell_at(raw, a), blank) == v for a, v in filters)
        account = ident(cell_at(raw, at["account"]), blank)
        if not account:
            text = next((ident(cell_at(raw, a), "") for a in label_ats if ident(cell_at(raw, a), "")), "")
            if text:
                label_rows.append((text, {m: money(cell_at(raw, a)) for m, a in month_at.items()}, passes))
            continue
        if not passes:
            continue
        row = {"account": account,
               "account_name": ident(cell_at(raw, at["account_name"]), "") if "account_name" in at else ""}
        for name in ("department", "location", "cls"):
            row[name] = ident(cell_at(raw, at[name]), blank) if name in at else ""
        flip = -1.0 if account in contra else 1.0   # contra revenue back to the income-statement sign
        amounts = {m: cents(flip * money(cell_at(raw, a))) for m, a in month_at.items()}
        key = row_key(row)
        if key in merged:
            for m, v in amounts.items():
                merged[key]["amounts"][m] = cents(merged[key]["amounts"].get(m, 0.0) + v)
        else:
            merged[key] = dict(row, section=section_of(account, prefixes), amounts=amounts)
    rows = [merged[k] for k in sorted(merged)]
    if not rows:
        raise ForecastError(f"{where}: no account rows (check `columns.account` and `row_filter`)")

    out = {"schema": 1, "label": label or path.stem, "workbook": str(path), "sha256": file_sha(path),
           "size": path.stat().st_size, "sheet": sheet, "months": months, "section_prefixes": prefixes,
           "bonus_accounts": [str(a) for a in spec.get("bonus_accounts") or []],
           "expense_sign": str(spec.get("expense_sign", "positive")), "rows": rows}
    out["controls"] = [
        {"name": "every month column is headed once", "ok": not repeated,
         "detail": ("headed twice: " + "; ".join(repeated)) if repeated else f"{len(months)} month(s)"},
        {"name": "no month is missing between the first and the last", "ok": not gaps,
         "detail": ("no column for " + ", ".join(gaps)) if gaps else f"{months[0]} to {months[-1]}"},
    ] + controls(out, label_rows, spec)
    return out


# --- totals -------------------------------------------------------------------------------------


def is_bonus(account, bonus_accounts):
    return any(str(account).startswith(str(b)) for b in bonus_accounts if str(b))


def totals(extract, months):
    """revenue, cogs and sga (bonus excluded), bonus, ebitda_pre_bonus and ebitda over months."""
    bonus_accounts = extract.get("bonus_accounts") or []
    out = {"revenue": 0.0, "cogs": 0.0, "sga": 0.0, "bonus": 0.0}
    for row in extract["rows"]:
        amount = sum(float(row["amounts"].get(m, 0.0)) for m in months)
        if row["section"] in ("cogs", "sga") and is_bonus(row["account"], bonus_accounts):
            out["bonus"] += amount
        elif row["section"] in out:
            out[row["section"]] += amount
    out = {k: cents(v) for k, v in out.items()}
    factor = 1.0 if extract.get("expense_sign", "positive") == "positive" else -1.0
    out["ebitda_pre_bonus"] = cents(out["revenue"] - factor * (out["cogs"] + out["sga"]))
    out["ebitda"] = cents(out["ebitda_pre_bonus"] - factor * out["bonus"])
    return out


def basis_key(basis):
    return "ebitda" if basis == "post_bonus" else "ebitda_pre_bonus"


def ebitda_amount(row, extract, months, basis):
    """The row's contribution to EBITDA on the basis over months (pre-bonus leaves bonus out)."""
    if row["section"] not in ("revenue", "cogs", "sga"):
        return 0.0
    if basis == "pre_bonus" and row["section"] != "revenue" \
            and is_bonus(row["account"], extract.get("bonus_accounts") or []):
        return 0.0
    amount = sum(float(row["amounts"].get(m, 0.0)) for m in months)
    return cents(amount * ebitda_sign(row["section"], extract.get("expense_sign", "positive")))


def year_summary(extract, year, basis):
    """FY totals and quarter EBITDA on the basis, over the months of the year the workbook has."""
    months = [m for m in year_months(year) if m in set(extract["months"])]
    key = basis_key(basis)
    quarters = {}
    for label in dict.fromkeys(quarter_label(m) for m in months):
        quarters[label] = totals(extract, [m for m in months if quarter_label(m) == label])[key]
    return {"months": months, "totals": totals(extract, months), "quarters": quarters}


def gross_sections(extract, month):
    """Section totals for one month with the bonus left inside its section, as a report shows them."""
    out = {s: 0.0 for s in ("revenue", "cogs", "sga")}
    bonus = 0.0
    for row in extract["rows"]:
        amount = float(row["amounts"].get(month, 0.0))
        if row["section"] in out:
            out[row["section"]] += amount
        if row["section"] in ("cogs", "sga") and is_bonus(row["account"], extract.get("bonus_accounts") or []):
            bonus += amount
    factor = 1.0 if extract.get("expense_sign", "positive") == "positive" else -1.0
    ebitda = out["revenue"] - factor * (out["cogs"] + out["sga"])
    return {"revenue": cents(out["revenue"]), "cogs": cents(out["cogs"]), "sga": cents(out["sga"]),
            "bonus": cents(bonus), "ebitda": cents(ebitda), "ebitda_pre_bonus": cents(ebitda + factor * bonus)}


def controls(extract, label_rows, spec):
    """The workbook's own tie rows and "must be zero" rows, checked month by month to fifty cents
    (a report row is rounded by the workbook). A tie row's label matches exactly, preferring a row
    that passes the row filter; a zero row's label matches as a prefix."""
    tolerance = float(spec.get("control_tolerance", 0.5))
    out = []
    for key, text in (spec.get("tie_rows") or {}).items():
        if key not in TIE_KEYS:
            raise ForecastError(f"tie_rows: {key!r} is not one of {', '.join(TIE_KEYS)}")
        found = sorted((r for r in label_rows if r[0].strip().lower() == str(text).strip().lower()),
                       key=lambda r: not r[2])
        if not found:
            out.append({"name": f"tie {key}", "ok": False, "detail": f"no row labelled '{text}'"})
            continue
        values = found[0][1]
        misses = [f"{m} rows {gross_sections(extract, m)[key]:,.2f} vs '{text}' {values.get(m, 0.0):,.2f}"
                  for m in extract["months"] if not close(gross_sections(extract, m)[key], values.get(m, 0.0), tolerance)]
        out.append({"name": f"tie {key}", "ok": not misses,
                    "detail": "; ".join(misses[:4]) or f"every month ties to '{text}'"})
    for prefix in spec.get("zero_rows") or []:
        found = [r for r in label_rows if r[0].strip().lower().startswith(str(prefix).strip().lower())]
        bad = [f"{r[0][:40]} {m} {v:,.2f}" for r in found for m, v in r[1].items() if abs(v) > tolerance]
        detail = ("; ".join(bad[:4]) if bad else f"{len(found)} row(s), all zero") if found \
            else f"no row labelled '{prefix}...'"
        out.append({"name": f"zero rows '{prefix}'", "ok": bool(found) and not bad, "detail": detail})
    return out


def foots(extract, years, basis, tolerance):
    """Per year, the rows re-add to the stated totals and the quarters to the year."""
    checks = []
    stated = extract.get("years") or {}
    for year in years:
        mine, theirs = year_summary(extract, int(year), basis), stated.get(str(year))
        if theirs is None:
            checks.append({"name": f"{year}: summary present", "ok": False, "detail": "no summary for the year"})
            continue
        for line in ("revenue", "cogs", "sga", "bonus", "ebitda_pre_bonus", "ebitda"):
            a, b = mine["totals"][line], float(theirs["totals"].get(line, 0.0))
            checks.append({"name": f"{year} {line}: rows sum to the stated total", "ok": close(a, b, tolerance),
                           "detail": f"rows {a:,.2f} vs stated {b:,.2f}"})
        quarter_sum = cents(sum(float(v) for v in theirs.get("quarters", {}).values()))
        fy = float(theirs["totals"].get(basis_key(basis), 0.0))
        checks.append({"name": f"{year}: the quarters sum to the year", "ok": close(quarter_sum, fy, tolerance),
                       "detail": f"quarters {quarter_sum:,.2f} vs FY {fy:,.2f}"})
    return checks


def extract(workbook, folder, layout_name="", years=None, label=""):
    """One workbook as a footed, tied extract: rows, per-year summaries, controls and foots."""
    settings = load_settings(folder)
    out = read_workbook(workbook, layout(settings, layout_name), label)
    out["layout"] = layout_name or "default"
    out["basis"] = settings["basis"]
    years = years or sorted({int(m[:4]) for m in out["months"]})
    out["years"] = {str(y): year_summary(out, int(y), settings["basis"]) for y in years}
    out["checks"] = foots(out, years, settings["basis"], float(settings["tolerance"])) + out["controls"]
    out["ok"] = all(c["ok"] for c in out["checks"])
    return out


# --- the bridge ---------------------------------------------------------------------------------


def load_extract(path):
    path = Path(path)
    if not path.is_file():
        raise ForecastError(f"{path} does not exist (run forecast-prepare for the vintage)")
    return json.loads(path.read_text(encoding="utf-8"))


def owner_of(account, modules):
    """The active module whose prefix claims the account; longest prefix wins, then first listed."""
    best = None
    for module in modules:
        if module.get("active", True):
            for prefix in module["accounts"]:
                if str(account).startswith(prefix) and (best is None or len(prefix) > best[0]):
                    best = (len(prefix), module)
    return best[1] if best else None


def overlaps(modules):
    """Prefixes two active modules both claim (the first listed takes them)."""
    seen, out = {}, []
    for module in modules:
        if module.get("active", True):
            for prefix in module["accounts"]:
                if prefix in seen and seen[prefix] != module["key"]:
                    out.append(f"{prefix} ({seen[prefix]} and {module['key']})")
                seen.setdefault(prefix, module["key"])
    return out


def account_changes(prior, new, months, basis):
    """{account: {account, name, section, prior, new, change}} in EBITDA terms over months."""
    out = {}
    for side, data in (("prior", prior), ("new", new)):
        for row in data["rows"]:
            entry = out.setdefault(row["account"], {"account": row["account"], "name": "",
                                                    "section": row["section"], "prior": 0.0, "new": 0.0})
            entry["name"] = entry["name"] or row.get("account_name", "")
            entry[side] = cents(entry[side] + ebitda_amount(row, data, months, basis))
    for entry in out.values():
        entry["change"] = cents(entry["new"] - entry["prior"])
    return out


def walk_line(key, label, kind, months, changes, materiality, owner=""):
    detail = sorted((c for c in changes if abs(c["change"]) >= 0.005), key=lambda c: -abs(c["change"]))
    return {"key": key, "label": label, "kind": kind, "owner": owner, "months": list(months),
            "amount": cents(sum(c["change"] for c in changes)), "materiality": materiality, "accounts": detail}


def year_walk(prior, new, year, modules, settings, last_actual, prior_last_actual):
    """One fiscal year's walk from the prior forecast's EBITDA to the new one's."""
    basis = settings["basis"]
    present = set(prior["months"]) & set(new["months"])
    months = [m for m in year_months(year) if m in present]
    if not months:
        raise ForecastError(f"FY{year}: neither extract carries a month of the year in common")
    p_sum, n_sum = year_summary(prior, year, basis), year_summary(new, year, basis)
    fy_prior = cents(sum(ebitda_amount(r, prior, months, basis) for r in prior["rows"]))
    fy_new = cents(sum(ebitda_amount(r, new, months, basis) for r in new["rows"]))
    default_mat = float(settings["materiality_abs"])
    # Three kinds of month: already actual in the prior (restated), closed since (actuals
    # replaced forecast), and still forecast (explained line by line).
    restated = [m for m in months if prior_last_actual and m <= prior_last_actual]
    newly_actual = [m for m in months if last_actual and m <= last_actual and m not in restated]
    forecast = [m for m in months if m not in restated and m not in newly_actual]

    walk = [{"key": "start", "label": f"{prior.get('label', 'prior')} forecast", "kind": "start", "amount": fy_prior}]
    if restated:
        walk.append(walk_line("restated", "Closed months restated", "restated", restated,
                              list(account_changes(prior, new, restated, basis).values()), 0.0))
    if newly_actual:
        walk.append(walk_line("actuals", "Actuals replaced forecast", "actuals", newly_actual,
                              list(account_changes(prior, new, newly_actual, basis).values()), default_mat))
    active = [m for m in modules if m.get("active", True)]
    claimed = {m["key"]: [] for m in active}
    unclaimed = []
    for account, change in (account_changes(prior, new, forecast, basis) if forecast else {}).items():
        module = owner_of(account, modules) if change["section"] in ("revenue", "cogs", "sga") else None
        (claimed[module["key"]] if module else unclaimed).append(change)
    for module in active:
        walk.append(walk_line(module["key"], module["label"], "driver", forecast, claimed[module["key"]],
                              float(module["materiality_abs"]), str(module.get("owner") or "")))
    walk.append(walk_line("unclaimed", "Other / unclaimed", "unclaimed", forecast, unclaimed, default_mat))
    walk.append({"key": "end", "label": f"{new.get('label', 'new')} forecast", "kind": "end", "amount": fy_new})

    quarters = []
    for label in sorted({quarter_label(m) for m in months}):
        p, n = cents(p_sum["quarters"].get(label, 0.0)), cents(n_sum["quarters"].get(label, 0.0))
        quarters.append({"quarter": label, "prior": p, "new": n, "change": cents(n - p)})
    sections = {line: {"prior": p_sum["totals"][line], "new": n_sum["totals"][line],
                       "change": cents(n_sum["totals"][line] - p_sum["totals"][line])}
                for line in ("revenue", "cogs", "sga", "bonus", basis_key(basis))}
    return {"year": year, "basis": basis, "months": months, "fy_prior": fy_prior, "fy_new": fy_new,
            "fy_change": cents(fy_new - fy_prior), "walk": walk, "quarters": quarters, "sections": sections,
            "split": {"restated": restated, "actuals": newly_actual, "forecast": forecast}}


def foot_year(year, prior, new, tolerance):
    """The walk lands: start plus lines is end, start and end are the extracts' FY EBITDA, each
    line's accounts sum to it, and the quarters' changes sum to the year's."""
    y, basis = year["year"], year["basis"]
    lines = [l for l in year["walk"] if l["kind"] not in ("start", "end")]
    start = next(l["amount"] for l in year["walk"] if l["kind"] == "start")
    end = next(l["amount"] for l in year["walk"] if l["kind"] == "end")
    walked = cents(start + sum(l["amount"] for l in lines))
    stated_prior = year_summary(prior, y, basis)["totals"][basis_key(basis)]
    stated_new = year_summary(new, y, basis)["totals"][basis_key(basis)]
    checks = [
        {"name": f"FY{y}: start plus the lines lands on end", "ok": close(walked, end, tolerance),
         "detail": f"{start:,.2f} + {walked - start:,.2f} = {walked:,.2f} vs end {end:,.2f}"},
        {"name": f"FY{y}: the start is the prior forecast's FY EBITDA", "ok": close(start, stated_prior, tolerance),
         "detail": f"{start:,.2f} vs {stated_prior:,.2f}"},
        {"name": f"FY{y}: the end is the new forecast's FY EBITDA", "ok": close(end, stated_new, tolerance),
         "detail": f"{end:,.2f} vs {stated_new:,.2f}"},
        {"name": f"FY{y}: the change is new less prior", "ok": close(year["fy_change"], end - start, tolerance),
         "detail": f"{year['fy_change']:,.2f} vs {end - start:,.2f}"},
    ]
    for line in lines:
        detail = cents(sum(a["change"] for a in line["accounts"]))
        checks.append({"name": f"FY{y} {line['key']}: its accounts sum to the line",
                       "ok": close(detail, line["amount"], tolerance),
                       "detail": f"accounts {detail:,.2f} vs line {line['amount']:,.2f}"})
    quarter_change = cents(sum(q["change"] for q in year["quarters"]))
    checks.append({"name": f"FY{y}: the quarters' changes sum to the year's",
                   "ok": close(quarter_change, year["fy_change"], tolerance),
                   "detail": f"{quarter_change:,.2f} vs {year['fy_change']:,.2f}"})
    return checks


def load_reasons(vdir):
    """reasons.json's `lines`, keyed "<year>:<line key>", or {}."""
    data = read_json(Path(vdir) / "reasons.json")
    return dict((data or {}).get("lines") or {}) if isinstance(data, dict) else {}


def build_bridge(folder, vintage_id):
    """The vintage's bridge, every year, footed, with reasons.json attached to its lines."""
    root = forecast_folder(folder)
    settings = load_settings(root)
    modules = load_modules(settings)
    vintage = load_vintage(root, vintage_id)
    vdir = Path(vintage["_dir"])
    source = vdir / "work" / "source"
    prior, new = load_extract(source / "prior.json"), load_extract(source / "new.json")
    years = vintage["years"] or sorted({int(m[:4]) for m in new["months"]})
    out = {"schema": 1, "vintage": vintage_id, "basis": settings["basis"], "built_at": now(),
           "prior": {k: prior.get(k) for k in ("label", "workbook", "sha256")},
           "new": {k: new.get(k) for k in ("label", "workbook", "sha256")},
           "inputs": {"prior.json": file_sha(source / "prior.json"), "new.json": file_sha(source / "new.json"),
                      "modules": file_sha(modules_path(settings))},
           "overlapping_prefixes": overlaps(modules), "years": {}, "foots": []}
    for year in years:
        walk = year_walk(prior, new, int(year), modules, settings, vintage["last_actual_month"],
                         vintage["prior_last_actual_month"])
        out["years"][str(year)] = walk
        out["foots"] += foot_year(walk, prior, new, float(settings["tolerance"]))
    if (source / "budget.json").is_file():
        budget = load_extract(source / "budget.json")
        keys = ("revenue", "cogs", "sga", basis_key(settings["basis"]))
        for year, walk in out["years"].items():
            b = year_summary(budget, int(year), settings["basis"])["totals"]
            n = year_summary(new, int(year), settings["basis"])["totals"]
            walk["vs_budget"] = {k: cents(n[k] - b[k]) for k in keys}
    reasons = load_reasons(vdir)
    out["reasons_attached"] = bool(reasons)
    for year, walk in out["years"].items():
        for line in walk["walk"]:
            if line["kind"] not in ("start", "end"):
                line["reason"] = reasons.get(f"{year}:{line['key']}") or {}
    out["ok"] = all(c["ok"] for c in out["foots"])
    return out


def values_in_k(bridge):
    """Every figure the bridge carries, in $k to one decimal: what a summary may quote."""
    values = []
    for walk in bridge.get("years", {}).values():
        values += [walk["fy_prior"], walk["fy_new"], walk["fy_change"]]
        for q in walk["quarters"]:
            values += [q["prior"], q["new"], q["change"]]
        for line in walk["walk"]:
            values.append(line["amount"])
            values += [a["change"] for a in line.get("accounts", [])]
            values += [float(d["amount"]) for d in (line.get("reason") or {}).get("detail") or []
                       if isinstance(d.get("amount"), (int, float))]
        for section in walk["sections"].values():
            values += [section["prior"], section["new"], section["change"]]
        values += list((walk.get("vs_budget") or {}).values())
    return sorted({round(float(v) / 1000.0, 1) for v in values})


# --- the evidence ledger (FORECAST-EVIDENCE-<vintage>.csv) ----------------------------------------

LEDGER_COLUMNS = ["id", "test", "item", "state", "evidence", "amount", "review", "review_file", "note",
                  "updated_at", "by"]


def ledger_path(vdir, vintage):
    return Path(vdir) / f"FORECAST-EVIDENCE-{vintage}.csv"


def ledger_rows(vdir, vintage):
    """The ledger's rows keyed by id, values stripped; the first row of an id wins."""
    path = ledger_path(vdir, vintage)
    if not path.is_file():
        return {}
    out = {}
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")   # a spreadsheet may add a byte-order mark
    for raw in csv.DictReader(io.StringIO(text, newline="")):
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if row.get("id") and row["id"] not in out:
            out[row["id"]] = row
    return out


def work_shas(vdir):
    """What a review vouches for: the bridge and the summary as they are now."""
    return f"bridge={file_sha(Path(vdir) / 'bridge.json')[:16]} summary={file_sha(Path(vdir) / 'summary.md')[:16]}"
