# /// script
# dependencies = ["pyyaml"]
# ///
"""Flag what in a new forecast needs explaining. It flags; it never judges.

Reads the vintage's extracts, and its bridge.json and hypotheses.json when they exist. Each flag
states a number, the reference it failed against and the bridge line that owns the account. The
thresholds are in FORECAST-SETTINGS.yaml:

- run_rate: a forecast month outside run_rate_floor..run_rate_ceiling times the trailing
  run_rate_months actual average (needs last_actual_month on the vintage).
- sign: a revenue account below zero, or a cost against the workbook's sign, in a forecast month
  (sign_exempt_accounts lists prefixes negative by nature, such as discounts).
- swing: a month-on-month move beyond swing_pct (the last actual month is the base).
- restated: a month already actual in the prior forecast that changed in the new one.
- control: an extract that does not foot or tie to the workbook's own rows.
- unclaimed: the bridge's unclaimed line beyond materiality.
- hypothesis_miss: a bridge line, or the FY change, that missed its hypothesis beyond
  hypothesis_tolerance_abs or hypothesis_tolerance_pct.

Month-by-month flags are grouped to one per kind and account. A flag's id is a hash of what it is
about, so it keeps its id when the flags are rebuilt. A flag is material beyond the owning line's
materiality_abs; restated, control and an FY miss are always material.

Writes flags.json in the vintage folder and prints the material flags (or the whole result with
--format json). Exit 0 whenever it ran, 2 on a bad argument or a missing extract.

Example:
    python3 forecast_sense_check.py ~/Forecast --vintage rev3
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from _common import (ForecastError, cents, close, file_sha, forecast_folder, load_extract, load_modules,
                     load_settings, load_vintage, now, owner_of, read_json, write_json)

MONTHLY = ("run_rate", "sign", "swing", "restated")


def flag_id(*parts):
    return "F-" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:6]


def flag(kind, text, value, reference, materiality, line="", account="", month="", year="", material=False):
    material = material or (bool(line) and abs(cents(value - reference)) > materiality)
    return {"id": flag_id(kind, year, line, account, month), "kind": kind, "line": line, "account": account,
            "month": month, "year": year, "value": cents(value), "reference": cents(reference),
            "severity": "material" if material else "minor", "text": text}


def by_account(extract):
    """{account: {section, name, amounts}} summed across dimensions."""
    out = {}
    for row in extract["rows"]:
        entry = out.setdefault(row["account"], {"section": row["section"], "name": row.get("account_name", ""),
                                                "amounts": {}})
        for month, amount in row["amounts"].items():
            entry["amounts"][month] = cents(entry["amounts"].get(month, 0.0) + float(amount))
    return out


def owned(account, modules):
    """(materiality, line key) of the module that owns the account, or (0, "")."""
    module = owner_of(account, modules)
    return (module["materiality_abs"], module["key"]) if module else (0.0, "")


def pl_accounts(extract):
    return [(a, e) for a, e in sorted(by_account(extract).items()) if e["section"] in ("revenue", "cogs", "sga")]


def run_rate(new, modules, s, actual, forecast):
    window = int(s["run_rate_months"])
    trailing = actual[-window:] if window > 0 else actual
    if not trailing:
        return []
    floor, ceiling, minimum = float(s["run_rate_floor"]), float(s["run_rate_ceiling"]), float(s["run_rate_min_amount"])
    flags = []
    for account, e in pl_accounts(new):
        average = cents(sum(e["amounts"].get(m, 0.0) for m in trailing) / len(trailing))
        if abs(average) < minimum:
            continue
        for month in forecast:
            amount = e["amounts"].get(month, 0.0)
            if abs(amount - average) < minimum or floor <= amount / average <= ceiling:
                continue
            materiality, line = owned(account, modules)
            flags.append(flag("run_rate", f"{account} {e['name']} {month} {amount:,.0f} is {amount / average:.2f}x the "
                              f"{len(trailing)}-month actual average of {average:,.0f} (outside {floor:g}x to {ceiling:g}x)",
                              amount, average, materiality, line, account, month))
    return flags


def sign(new, modules, s, forecast):
    exempt = [str(p) for p in s.get("sign_exempt_accounts") or []]
    minimum = float(s["run_rate_min_amount"])
    wanted = 1.0 if new.get("expense_sign", "positive") == "positive" else -1.0
    flags = []
    for account, e in pl_accounts(new):
        if any(account.startswith(p) for p in exempt):
            continue
        for month in forecast:
            amount = e["amounts"].get(month, 0.0)
            if abs(amount) < minimum:
                continue
            if (amount < 0) if e["section"] == "revenue" else (amount * wanted < 0):
                materiality, line = owned(account, modules)
                flags.append(flag("sign", f"{e['section']} account {account} {e['name']} is {amount:,.0f} in {month}",
                                  amount, 0.0, materiality, line, account, month))
    return flags


def swing(new, modules, s, actual, forecast):
    limit, minimum = float(s["swing_pct"]), float(s["run_rate_min_amount"])
    series = actual[-1:] + list(forecast)
    flags = []
    for account, e in pl_accounts(new):
        for before_m, after_m in zip(series, series[1:]):
            before, after = e["amounts"].get(before_m, 0.0), e["amounts"].get(after_m, 0.0)
            if abs(before) < minimum or abs((after - before) / abs(before)) <= limit:
                continue
            materiality, line = owned(account, modules)
            flags.append(flag("swing", f"{account} {e['name']} moves {(after - before) / abs(before):+.0%} from "
                              f"{before_m} {before:,.0f} to {after_m} {after:,.0f} (limit {limit:.0%})",
                              after, before, materiality, line, account, after_m))
    return flags


def restated(prior, new, modules, s, closed):
    old, now_ = by_account(prior), by_account(new)
    flags = []
    for account in sorted(set(old) | set(now_)):
        for month in closed:
            a = (old.get(account) or {}).get("amounts", {}).get(month, 0.0)
            b = (now_.get(account) or {}).get("amounts", {}).get(month, 0.0)
            if not close(a, b, float(s["tolerance"])):
                flags.append(flag("restated", f"{account} {month} was actual at {a:,.2f} in the prior forecast "
                                  f"and is {b:,.2f} now", b, a, 0.0, owned(account, modules)[1], account, month,
                                  material=True))
    return flags


def control(prior, new):
    return [flag("control", f"{side} forecast {x.get('label')}: {c['name']}: {c['detail']}", 0.0, 0.0, 0.0,
                 account=c["name"], year=side, material=True)
            for side, x in (("prior", prior), ("new", new)) for c in x.get("checks") or [] if not c["ok"]]


def missed(miss, expected, s):
    return not (abs(miss) <= float(s["hypothesis_tolerance_abs"])
                or (expected and abs(miss) <= abs(expected) * float(s["hypothesis_tolerance_pct"])))


def bridge_flags(bridge, hypotheses, s):
    if not bridge:
        return []
    flags = []
    lines = (hypotheses or {}).get("lines") or {}
    fy = (hypotheses or {}).get("fy") or {}
    absolute, percent = float(s["hypothesis_tolerance_abs"]), float(s["hypothesis_tolerance_pct"])
    for year, walk in bridge.get("years", {}).items():
        for line in walk["walk"]:
            if line["kind"] == "unclaimed" and abs(line["amount"]) > line["materiality"]:
                flags.append(flag("unclaimed", f"FY{year}: {line['amount']:,.0f} sits on accounts no module claims "
                                  f"({', '.join(a['account'] for a in line['accounts'][:5])})", line["amount"], 0.0,
                                  line["materiality"], "unclaimed", year=year))
            key = f"{year}:{line['key']}"
            if hypotheses is not None and key in lines:
                expected = float(lines[key].get("expected", 0.0))
                if missed(line["amount"] - expected, expected, s):
                    flags.append(flag("hypothesis_miss", f"FY{year} {line['label']}: expected {expected:,.0f}, came to "
                                      f"{line['amount']:,.0f}, a miss of {line['amount'] - expected:,.0f} beyond "
                                      f"{absolute:,.0f} or {percent:.0%}", line["amount"], expected,
                                      line["materiality"], line["key"], year=year))
        target = fy.get(str(year)) or {}
        if hypotheses is not None and "ebitda_expected" in target:
            expected = float(target["ebitda_expected"]) - walk["fy_prior"]
            if missed(walk["fy_change"] - expected, expected, s):
                flags.append(flag("hypothesis_miss", f"FY{year} EBITDA: expected a change of {expected:,.0f}, came to "
                                  f"{walk['fy_change']:,.0f}", walk["fy_change"], expected, 0.0, "fy", year=year,
                                  material=True))
    return flags


def group(flags):
    """One flag per kind and account for the month-by-month checks, so twelve months of one
    pattern are one thing to explain: the months listed, the worst month's numbers kept,
    material when any month was."""
    out, grouped = [], {}
    for f in flags:
        if f["kind"] not in MONTHLY:
            if all(o["id"] != f["id"] for o in out):
                out.append(f)
            continue
        key = (f["kind"], f["line"], f["account"])
        entry = grouped.get(key)
        if entry is None:
            entry = grouped[key] = dict(f, months=[f["month"]], id=flag_id(f["kind"], "", f["line"], f["account"]))
            out.append(entry)
            continue
        entry["months"].append(f["month"])
        if abs(f["value"] - f["reference"]) > abs(entry["value"] - entry["reference"]):
            entry.update({k: f[k] for k in ("value", "reference", "text", "month")})
        if f["severity"] == "material":
            entry["severity"] = "material"
    for entry in grouped.values():
        if len(entry["months"]) > 1:
            entry["text"] = (f"{len(entry['months'])} months ({entry['months'][0]} to {entry['months'][-1]}); "
                             f"worst: {entry['text']}")
    return out


def build(folder, vintage_id):
    root = forecast_folder(folder)
    s = load_settings(root)
    modules = load_modules(s)
    meta = load_vintage(root, vintage_id)
    vdir = Path(meta["_dir"])
    prior, new = load_extract(vdir / "work/source/prior.json"), load_extract(vdir / "work/source/new.json")
    last, prior_last = meta["last_actual_month"], meta["prior_last_actual_month"]
    years = {str(y) for y in meta["years"]} or {m[:4] for m in new["months"]}
    in_years = [m for m in new["months"] if m[:4] in years]
    actual = [m for m in new["months"] if last and m <= last]
    forecast = [m for m in in_years if not last or m > last]
    closed = [m for m in in_years if prior_last and m <= prior_last and m in prior["months"]]
    bridge, hypotheses = read_json(vdir / "bridge.json"), read_json(vdir / "hypotheses.json")
    flags = group(control(prior, new) + restated(prior, new, modules, s, closed)
                  + run_rate(new, modules, s, actual, forecast) + sign(new, modules, s, forecast)
                  + swing(new, modules, s, actual, forecast) + bridge_flags(bridge, hypotheses, s))
    return {"schema": 1, "vintage": vintage_id, "built_at": now(),
            "inputs": {name: file_sha(vdir / rel) for name, rel in
                       (("prior.json", "work/source/prior.json"), ("new.json", "work/source/new.json"),
                        ("bridge.json", "bridge.json"), ("hypotheses.json", "hypotheses.json"))},
            "flags": flags, "material": sum(1 for f in flags if f["severity"] == "material")}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Flag what in the new forecast needs explaining.")
    parser.add_argument("folder", help="the Forecast folder")
    parser.add_argument("--vintage", required=True, help="the vintage folder under vintages/")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        result = build(args.folder, args.vintage)
        vdir = Path(load_vintage(forecast_folder(args.folder), args.vintage)["_dir"])
    except ForecastError as exc:
        print(f"forecast-sense-check: {exc}", file=sys.stderr)
        return 2
    write_json(vdir / "flags.json", result)
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(f"{len(result['flags'])} flag(s), {result['material']} material, vintage {result['vintage']}")
        for f in result["flags"]:
            if f["severity"] == "material":
                print(f"  {f['id']} {f['kind']}: {f['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
