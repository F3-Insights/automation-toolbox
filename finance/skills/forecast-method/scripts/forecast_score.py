# /// script
# dependencies = ["pyyaml"]
# ///
"""Score a vintage's hypotheses against its bridge, and keep the calibration log across vintages.

Hypotheses are written with numbers before anyone looks at the new forecast (hypotheses.json);
this is the after. Each line's expectation is scored against the bridge line of the same key,
and each year's ebitda_expected against the bridge's FY change, both in EBITDA terms (a cost that
rises is negative), so the error is a number, not a direction puzzle.

Writes scores.json in the vintage folder and appends one line per score to the folder's
calibration.jsonl, which is never rewritten: a vintage already in the log is not appended again.
Prints the misses (or the result with --format json). Exit 0 whenever it ran, 1 when there is no
hypotheses.json or bridge.json to score, 2 on a bad argument.

Example:
    python3 forecast_score.py ~/Forecast --vintage rev3
"""

import argparse
import json
import sys
from pathlib import Path

from _common import (CALIBRATION, ForecastError, cents, file_sha, forecast_folder, load_settings, load_vintage,
                     now, write_json)


def one_score(line, year, expected, actual, absolute, percent):
    expected, actual = cents(expected), cents(actual)
    error = cents(actual - expected)
    return {"line": line, "year": year, "expected": expected, "actual": actual, "error": error,
            "abs_error_pct": round(abs(error) / abs(expected), 4) if expected else None,
            "within_tolerance": bool(abs(error) <= absolute or (expected and abs(error) <= abs(expected) * percent))}


def score(root, vintage_id):
    settings = load_settings(root)
    vdir = Path(load_vintage(root, vintage_id)["_dir"])
    hyp_path, bridge_path = vdir / "hypotheses.json", vdir / "bridge.json"
    if not hyp_path.is_file() or not bridge_path.is_file():
        return None
    hypotheses = json.loads(hyp_path.read_text(encoding="utf-8"))
    years = json.loads(bridge_path.read_text(encoding="utf-8")).get("years") or {}
    absolute, percent = float(settings["hypothesis_tolerance_abs"]), float(settings["hypothesis_tolerance_pct"])
    scores = []
    for key, expectation in sorted((hypotheses.get("lines") or {}).items()):
        year, _, line = key.partition(":")
        if year in years:
            found = next((l for l in years[year]["walk"] if l["key"] == line), None)
            scores.append(one_score(line, year, float(expectation.get("expected", 0.0)),
                                    found["amount"] if found else 0.0, absolute, percent))
    for year, expectation in sorted((hypotheses.get("fy") or {}).items()):
        walk = years.get(str(year))
        if walk and "ebitda_expected" in expectation:
            scores.append(one_score("fy_ebitda", str(year), float(expectation["ebitda_expected"]) - walk["fy_prior"],
                                    walk["fy_change"], absolute, percent))
    return {"ok": True, "vintage": vintage_id, "scored_at": now(),
            "inputs": {"hypotheses.json": file_sha(hyp_path), "bridge.json": file_sha(bridge_path)}, "scores": scores}


def append_calibration(root, result):
    """Append the vintage's scores to calibration.jsonl unless the vintage is already there."""
    path = Path(root) / CALIBRATION
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(raw).get("vintage") == result["vintage"]:
                    return False
            except json.JSONDecodeError:
                continue
    with path.open("a", encoding="utf-8") as handle:
        for item in result["scores"]:
            handle.write(json.dumps(dict(item, vintage=result["vintage"], at=result["scored_at"])) + "\n")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score the vintage's hypotheses and keep the calibration log.")
    parser.add_argument("folder", help="the Forecast folder")
    parser.add_argument("--vintage", required=True, help="the vintage folder under vintages/")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        root = forecast_folder(args.folder)
        result = score(root, args.vintage)
    except ForecastError as exc:
        print(f"forecast-score: {exc}", file=sys.stderr)
        return 2
    if result is None:
        print("forecast-score: needs hypotheses.json and bridge.json in the vintage folder")
        return 1
    write_json(Path(load_vintage(root, args.vintage)["_dir"]) / "scores.json", result)
    appended = append_calibration(root, result)
    if args.format == "json":
        print(json.dumps(dict(result, appended=appended), indent=1))
        return 0
    misses = [s for s in result["scores"] if not s["within_tolerance"]]
    print(f"{len(result['scores'])} score(s), {len(misses)} outside tolerance; calibration "
          f"{'appended' if appended else 'already holds this vintage'}")
    for s in misses:
        print(f"  FY{s['year']} {s['line']}: expected {s['expected']:,.0f}, actual {s['actual']:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
