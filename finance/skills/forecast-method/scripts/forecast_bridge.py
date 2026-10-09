# /// script
# dependencies = ["pyyaml"]
# ///
"""Build a vintage's bridge from the prior forecast to the new one, so that it foots.

Reads the vintage's two extracts (work/source/prior.json and new.json, written by
forecast-prepare), the folder's modules.yaml (the bridge lines and the account prefixes each
claims) and, when present, the vintage's reasons.json (why each line moved). For each fiscal
year in VINTAGE.yaml it walks, positive being favourable to EBITDA on the folder's basis:

    prior FY EBITDA
      + closed months restated     (months already actual in the prior that changed; should be 0)
      + actuals replaced forecast  (months closed since the prior: actual less what was forecast)
      + one line per module        (the forecast months, account by account, longest prefix wins)
      + other / unclaimed          (accounts no active module claims)
    = new FY EBITDA

Every line carries its accounts, so a line's detail sums to the line, the lines sum to the
change and the quarters' changes sum to the year's. Nothing is plugged.

Writes bridge.json and bridge.md in the vintage folder; prints a short walk (or the bridge with
--format json). Exit 0 when the walk foots, 1 when a foot fails (the files are still written),
2 on a bad argument or a missing extract.

Example:
    python3 forecast_bridge.py ~/Forecast --vintage rev3
"""

import argparse
import json
import sys
from pathlib import Path

from _common import ForecastError, build_bridge, cents, forecast_folder, load_vintage, write_json


def k(value):
    """$ to $k at one decimal, negatives in parentheses."""
    amount = value / 1000.0
    return f"({abs(amount):,.1f})" if amount < 0 else f"{amount:,.1f}"


def render_markdown(bridge):
    out = [f"# Bridge: {bridge['prior']['label']} to {bridge['new']['label']}", "",
           f"EBITDA {bridge['basis'].replace('_', '-')}, $'000. Positive is favourable. Prior workbook "
           f"`{Path(str(bridge['prior']['workbook'])).name}`, new workbook `{Path(str(bridge['new']['workbook'])).name}`.", ""]
    for year, walk in bridge["years"].items():
        out += [f"## FY{year}", "", "| Line | Owner | $'000 | Why |", "|---|---|---:|---|"]
        for line in walk["walk"]:
            reason = line.get("reason") or {}
            cites = ", ".join(list(reason.get("evidence", [])) + list(reason.get("questions", [])))
            why = f"{reason.get('driver', '')} [{cites}]" if cites else reason.get("driver", "")
            out.append(f"| {line['label']} | {line.get('owner', '')} | {k(line['amount'])} | {why} |")
        out += ["", f"Prior {k(walk['fy_prior'])} to new {k(walk['fy_new'])}, a change of {k(walk['fy_change'])}.",
                "", "| Quarter | Prior | New | Change |", "|---|---:|---:|---:|"]
        out += [f"| {q['quarter']} | {k(q['prior'])} | {k(q['new'])} | {k(q['change'])} |" for q in walk["quarters"]]
        out += ["", "| Section | Prior | New | Change |", "|---|---:|---:|---:|"]
        out += [f"| {name} | {k(s['prior'])} | {k(s['new'])} | {k(s['change'])} |" for name, s in walk["sections"].items()]
        if walk.get("vs_budget"):
            out += ["", "Against budget: " + ", ".join(f"{n} {k(v)}" for n, v in walk["vs_budget"].items()) + "."]
        out += ["", "### Accounts behind each line", ""]
        for line in walk["walk"]:
            if line["kind"] in ("start", "end") or not line.get("accounts"):
                continue
            top = line["accounts"][:6]   # about six details explain a line; the rest are summed
            parts = [f"{a['account']} {a['name']} {k(a['change'])}" for a in top]
            if len(line["accounts"]) > 6:
                rest = cents(line["amount"] - sum(a["change"] for a in top))
                parts.append(f"{len(line['accounts']) - 6} more {k(rest)}")
            out.append(f"- {line['label']}: " + "; ".join(parts))
        out.append("")
    failed = [c for c in bridge["foots"] if not c["ok"]]
    out.append("Foots: " + ("all hold." if not failed else "; ".join(f"FAIL {c['name']} ({c['detail']})" for c in failed)))
    if bridge.get("overlapping_prefixes"):
        out.append("Prefixes claimed twice (the first module listed takes them): " + ", ".join(bridge["overlapping_prefixes"]))
    return "\n".join(out) + "\n"


def render_text(bridge):
    lines = [f"{'OK' if bridge['ok'] else 'FAIL'}: bridge {bridge['prior']['label']} to {bridge['new']['label']} "
             f"({bridge['basis']})"]
    for year, walk in bridge["years"].items():
        lines.append(f"  FY{year}: {walk['fy_prior']:,.0f} to {walk['fy_new']:,.0f} ({walk['fy_change']:+,.0f})")
        lines += [f"    {l['label']:<40} {l['amount']:>14,.0f}" for l in walk["walk"]
                  if l["kind"] not in ("start", "end") and abs(l["amount"]) >= 0.005]
    lines += [f"  FAIL {c['name']}: {c['detail']}" for c in bridge["foots"] if not c["ok"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the vintage's bridge from the prior forecast to the new one.")
    parser.add_argument("folder", help="the Forecast folder")
    parser.add_argument("--vintage", required=True, help="the vintage folder under vintages/")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        bridge = build_bridge(args.folder, args.vintage)
        vdir = Path(load_vintage(forecast_folder(args.folder), args.vintage)["_dir"])
    except ForecastError as exc:
        print(f"forecast-bridge: {exc}", file=sys.stderr)
        return 2
    write_json(vdir / "bridge.json", bridge)
    (vdir / "bridge.md").write_text(render_markdown(bridge), encoding="utf-8")
    print(json.dumps(bridge, indent=1) if args.format == "json" else render_text(bridge))
    return 0 if bridge["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
