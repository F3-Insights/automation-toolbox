#!/usr/bin/env python3
"""report-record: keep the week's record, and propose what the next weeks should change.

save   writes <store>/records/<period>/: the approved report, the draft, the facts set, the
       evidence map, the pack, the gate answers, the questions and the verify result, each
       hashed (sha256) in record.json, plus the rendered files (--rendered, repeatable):
       copied into rendered/ when the profile's never-recorded list is empty, and otherwise
       kept by reference only (path and sha256 in the manifest, `rendered_storage` saying
       why), because a Word or PDF file cannot be redacted. --rendered-by-reference forces
       the reference form.
       The role profile's two lists behave differently. Never recorded is redacted from every
       stored file, JSON strings included, as case-insensitive substrings (a rule barring
       "Bluejay" takes it out of "Projectbluejay"), and the manifest names which rule (by its number in
       the profile, never by quoting it) matched in which file. Never published refuses the
       record outright when the approved text trips it: exit 3 and nothing is written.
       The Gate 3 edit size (bullets added, removed, changed, unchanged; words; the share of
       the text changed) is measured from --draft and the approved text and appended to
       <store>/edit-size.jsonl; with no draft the row is nulls and a reason, never zeros.
       Then the stored report goes to report_ledger.py add; if that fails the record still
       stands, with ledger_pending true and the reason.
learn  reads the last --last records (default 8) and proposes, for the executive to approve or
       reject and changing nothing: a topic written in by hand three weeks or more, a category
       with no bullet three weeks running, a three-word phrase taken out three weeks or more.

The store is --store, else $REPORT_STORE_DIR; there is no default path. Prints text, or JSON
with --json. Exit 0 ok, 2 error, 3 refused.

Example:
  python3 report_record.py save --store ~/reports/finance --period 2027-11-12 \\
      --report approved.md --draft draft.md --pack pack.json --profile ~/reports/finance/profile.md --json
"""

import argparse
import difflib
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

import _profile as pf
from _common import (BOLD_LABEL, FAILED, OK, TOP_BULLET, Fail, check_period, header_of,
                     now_utc, redact, run_main, run_script, safe, store_dir, term_pattern, write_json)

INPUTS = (("report", "report.md", True), ("draft", "draft.md", True), ("facts", "facts.json", False),
          ("evidence_map", "evidence-map.json", False), ("pack", "pack.json", False),
          ("gate_answers", "gate-answers.json", False), ("questions", "questions.json", False),
          ("verify", "verify.json", False))
EDIT_FIELDS = ("bullets_added", "bullets_removed", "bullets_changed", "bullets_unchanged",
               "words_draft", "words_final", "word_change_ratio")
REPEATS = 3


def redact_payload(payload, rules):
    """One stored file redacted: as JSON where it is JSON (keys and values), else as text."""
    text = payload.decode("utf-8", "replace")
    try:
        found = json.loads(text)
    except ValueError:
        cleaned, hits = redact(text, rules)
        return cleaned.encode("utf-8"), hits
    tally = {}

    def walk(node):
        if isinstance(node, str):
            cleaned, hits = redact(node, rules)
            for hit in hits:
                tally[hit["rule"]] = tally.get(hit["rule"], 0) + hit["times"]
            return cleaned
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, dict):
            return {walk(k): walk(v) for k, v in node.items()}
        return node

    walked = walk(found)
    if not tally:
        return payload, []
    return json.dumps(walked, separators=(",", ":")).encode("utf-8"), [{"rule": r, "times": n} for r, n in tally.items()]


def bullets(text):
    out = []
    for line in str(text or "").splitlines():
        hit = TOP_BULLET.match(line)
        if hit and len(hit.group("indent")) <= 1:
            rest = " ".join(hit.group("rest").split())
            label = BOLD_LABEL.match(rest)
            out.append({"text": rest, "label": label.group(1).strip().casefold() if label else ""})
    return out


def edit_size(draft, final):
    """How much the author changed at Gate 3. A reworded bullet (same label, or 60 percent
    alike) counts as changed, not as one added and one removed."""
    before, after = bullets(draft), bullets(final)
    pairs, used_a, used_b = [], set(), set()
    for i, b in enumerate(before):
        j = next((j for j, a in enumerate(after) if b["label"] and a["label"] == b["label"] and j not in used_b), None)
        if j is not None:
            pairs.append((i, j)); used_a.add(i); used_b.add(j)
    scored = sorted(((difflib.SequenceMatcher(None, before[i]["text"], after[j]["text"], autojunk=False).ratio(), i, j)
                     for i in range(len(before)) if i not in used_a for j in range(len(after)) if j not in used_b),
                    key=lambda r: (-r[0], r[1], r[2]))
    for ratio, i, j in scored:
        if ratio >= 0.6 and i not in used_a and j not in used_b:
            pairs.append((i, j)); used_a.add(i); used_b.add(j)
    unchanged = sum(1 for i, j in pairs if before[i]["text"] == after[j]["text"])
    words_a, words_b = str(draft).split(), str(final).split()
    matching = sum(b.size for b in difflib.SequenceMatcher(None, words_a, words_b, autojunk=False).get_matching_blocks())
    longest = max(len(words_a), len(words_b))
    return {"bullets_added": len(after) - len(pairs), "bullets_removed": len(before) - len(pairs),
            "bullets_changed": len(pairs) - unchanged, "bullets_unchanged": unchanged,
            "words_draft": len(words_a), "words_final": len(words_b),
            "word_change_ratio": round(1 - matching / longest, 2) if longest else 0.0}


def save(args):
    store, period = store_dir(args.store), check_period(args.period)
    sources = {}
    for option, _, _ in INPUTS:
        given = str(getattr(args, option) or "").strip()
        if given:
            path = Path(given).expanduser().resolve()
            if not path.is_file():
                raise Fail(f"no file at {path} for --{option.replace('_', '-')}")
            sources[option] = path
    if "report" not in sources:
        raise Fail("--report is required: the record is of the approved text")
    published, recorded = pf.exclusions(args.profile)
    if args.profile and not Path(args.profile).expanduser().is_file():
        raise Fail(f"no role profile at {args.profile}")
    approved = sources["report"].read_text(encoding="utf-8")
    for rule in published:
        hit = term_pattern(rule).search(approved)
        if hit:
            line = approved[:hit.start()].count("\n") + 1
            raise Fail(f"the approved report trips the profile's never-published rule {rule!r} at line {line}; "
                       f"nothing was written", FAILED)
    root = store / "records" / period
    root.mkdir(parents=True, exist_ok=True)
    files, missing, redactions, stored_text = {}, {}, [], {}
    for option, filename, prose in INPUTS:
        if option not in sources:
            missing[option] = f"--{option.replace('_', '-')} was not given, so no {filename} was stored"
            continue
        payload = sources[option].read_bytes()
        if prose:
            text, hits = redact(payload.decode("utf-8", "replace"), recorded)
            stored_text[option], payload = text, text.encode("utf-8")
        else:
            payload, hits = redact_payload(payload, recorded) if recorded else (payload, [])
        redactions += [{"file": filename, "rule": f"never-recorded rule {recorded.index(h['rule']) + 1}"
                        if h["rule"] in recorded else "a never-recorded rule", "occurrences": h["times"]} for h in hits]
        (root / filename).write_bytes(payload)
        files[filename] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "source": str(sources[option])}
    # A Word or PDF file cannot be redacted, so with a never-recorded list in force the
    # rendered files are kept by reference (path and hash) and never copied into the store.
    by_reference = bool(args.rendered_by_reference or recorded)
    rendered = []
    for given in args.rendered:
        path = Path(given).expanduser().resolve()
        if not path.is_file():
            missing[f"rendered:{path.name}"] = f"no rendered file at {path}"
            continue
        payload = path.read_bytes()
        if not by_reference:
            (root / "rendered").mkdir(exist_ok=True)
            (root / "rendered" / path.name).write_bytes(payload)
        rendered.append({"name": path.name, "sha256": hashlib.sha256(payload).hexdigest(), "path": str(path),
                         "stored": "by reference" if by_reference else f"rendered/{path.name}"})
    if not args.rendered:
        rendered_storage = None
    elif recorded:
        rendered_storage = ("by reference: the profile's never-recorded list is not empty and a rendered Word or "
                            "PDF file cannot be redacted, so its path and sha256 are kept and the file is not copied")
    elif args.rendered_by_reference:
        rendered_storage = "by reference, as --rendered-by-reference asked"
    else:
        rendered_storage = "copied into rendered/: the profile has no never-recorded list"
    if not args.rendered:
        missing["rendered"] = "no --rendered file was given"
    measured = edit_size(stored_text["draft"], stored_text["report"]) if "draft" in stored_text else None
    if measured is None:
        missing["edit_size"] = "no --draft was given, so the Gate 3 edit could not be measured (and is not zero)"
    ledger, pending = None, True
    if args.skip_ledger:
        missing["ledger"] = "the ledger call was skipped with --skip-ledger"
    else:
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch) / "report.md"
            copy.write_text(stored_text["report"], encoding="utf-8")
            command = ["add", "--report", copy, "--date", period, "--store", store, "--source-ref", f"record://{period}"]
            for option, value in (("--seat", args.seat), ("--profile", args.profile), ("--pack", sources.get("pack"))):
                command += [option, value] if value else []
            code, out, err = run_script("report_ledger", command)
        if code == OK:
            ledger, pending = json.loads(out), False
        else:
            missing["ledger"] = f"the report ledger refused the report: {err.strip()[:300]}"
    if not args.profile:
        missing["profile"] = "no --profile was given, so neither exclusion list was applied"
    manifest = {"schema": "report-record/1", "period": period, "saved": now_utc(), "files": files,
                "missing": missing, "redactions": redactions, "redacted": bool(redactions), "rendered": rendered,
                "rendered_storage": rendered_storage,
                "edit_size": measured, "ledger_pending": pending, "ledger": ledger,
                "profile": str(Path(args.profile).expanduser()) if args.profile else None}
    payload, _ = redact_payload(json.dumps(manifest).encode("utf-8"), recorded) if recorded else (None, None)
    write_json(root / "record.json", json.loads(payload) if payload else manifest)
    row = {"period": period, "saved": manifest["saved"], "measured": bool(measured),
           "reason": None if measured else missing["edit_size"], **(measured or {f: None for f in EDIT_FIELDS})}
    with (store / "edit-size.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return manifest


def phrases(text):
    """Every three-word phrase of a text, ignoring ones made of very short words."""
    out = set()
    for run in (m.split() for m in re.findall(r"[a-z']+(?:\s+[a-z']+)*", str(text or "").casefold())):
        out |= {" ".join(run[i:i + 3]) for i in range(len(run) - 2)
                if sum(1 for w in run[i:i + 3] if len(w) >= 3) >= 2}
    return out


def merge_phrases(items):
    """Overlapping phrases joined back into the run of words they came from, so one struck
    sentence is one proposal and not one per starting word. The caller groups by the weeks a
    phrase was taken out, so only phrases struck in exactly the same weeks are merged."""
    parts = {phrase: phrase.split() for phrase in items}
    follows, claimed = {}, set()
    for left in items:
        for right in items:
            if left != right and right not in claimed and parts[left][1:] == parts[right][:-1]:
                follows[left] = right
                claimed.add(right)
                break
    out, seen = [], set()
    for phrase in items:
        if phrase in claimed:
            continue
        chain, current = [phrase], phrase
        seen.add(phrase)
        while current in follows and follows[current] not in seen:
            current = follows[current]
            seen.add(current)
            chain.append(current)
        out.append(" ".join(parts[chain[0]] + [parts[p][-1] for p in chain[1:]]))
    # A phrase that only ever follows another, in a loop, starts no chain; keep it anyway.
    out.extend(phrase for phrase in items if phrase not in seen)
    return out


def learn(store, last):
    root = store / "records"
    if not root.is_dir():
        raise Fail(f"no records under {root}: nothing has been saved to this store yet")
    folders = sorted(p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))[-max(1, last):]
    read = lambda path: path.read_text(encoding="utf-8") if path.is_file() else ""  # noqa: E731
    records = []
    for folder in folders:
        pack = {}
        try:
            pack = json.loads(read(folder / "pack.json") or "{}")
        except ValueError:
            pass
        records.append({"period": folder.name, "report": read(folder / "report.md"), "draft": read(folder / "draft.md"),
                        "categories": [c.get("name") for c in pack.get("categories") or [] if c.get("name")]})
    found, drafted = [], [r for r in records if r["draft"].strip()]
    added = {}
    for r in drafted:
        for label in sorted({b["label"] for b in bullets(r["report"]) if b["label"]}
                            - {b["label"] for b in bullets(r["draft"]) if b["label"]}):
            added.setdefault(label, []).append(r["period"])
    found += [{"kind": "recurring_manual_addition", "weeks": len(p), "evidence": p,
               "detail": f"the topic {label!r} was written in by hand in {len(p)} of the last {len(records)} weeks and "
                         f"was in no draft; propose it as a standing category or a signal"}
              for label, p in added.items() if len(p) >= REPEATS]
    for name in dict.fromkeys(n for r in records for n in r["categories"]):
        streak = []
        for r in reversed(records):
            if name not in r["categories"]:
                break
            under, count = False, 0
            for line in r["report"].splitlines():
                header = header_of(line)
                if header is not None:
                    under = header.casefold() in name.casefold() or name.casefold() in header.casefold()
                elif under and (hit := TOP_BULLET.match(line)) and len(hit.group("indent")) <= 1:
                    count += 1
            if count:
                break
            streak.append(r["period"])
        if len(streak) >= REPEATS:
            found.append({"kind": "category_without_a_bullet", "weeks": len(streak), "evidence": streak[::-1],
                          "detail": f"the category {name!r} produced no bullet for {len(streak)} weeks running; propose "
                                    f"it for review"})
    removed = {}
    for r in drafted:
        for phrase in phrases(r["draft"]) - phrases(r["report"]):
            removed.setdefault(phrase, []).append(r["period"])
    grouped = {}
    for phrase, p in sorted(removed.items()):
        if len(p) >= REPEATS:
            grouped.setdefault(tuple(p), []).append(phrase)
    found += [{"kind": "phrase_always_rewritten", "weeks": len(p), "evidence": list(p),
               "detail": f"the phrase {phrase!r} was in the draft and out of the approved text in {len(p)} of the "
                         f"last {len(records)} weeks; propose it for the house style's barred list"}
              for p, items in grouped.items() for phrase in merge_phrases(items)]
    kept = []
    for kind in ("recurring_manual_addition", "category_without_a_bullet", "phrase_always_rewritten"):
        kept += sorted((f for f in found if f["kind"] == kind), key=lambda f: (-f["weeks"], f["detail"]))[:10]
    notes = ["These are proposals for the executive to approve or reject; nothing has been applied.",
             f"a pattern is proposed once it has held for {REPEATS} weeks"]
    if len(records) < REPEATS:
        notes.append(f"only {len(records)} record(s) were read, fewer than the {REPEATS} a pattern needs")
    return {"schema": "report-record/proposals/1", "records_read": len(records),
            "window": [r["period"] for r in records], "proposals": kept, "notes": notes}


def main():
    parser = argparse.ArgumentParser(description="Keep the week's record; propose changes from the last few.")
    sub = parser.add_subparsers(dest="action", required=True)
    save_cmd = sub.add_parser("save")
    for option, filename, _ in INPUTS:
        save_cmd.add_argument(f"--{option.replace('_', '-')}", dest=option, default="", help=f"stored as {filename}")
    save_cmd.add_argument("--period", required=True, help="the period end date, YYYY-MM-DD")
    save_cmd.add_argument("--rendered", action="append", default=[], help="a rendered file to keep; repeatable")
    save_cmd.add_argument("--rendered-by-reference", action="store_true")
    save_cmd.add_argument("--profile", default="", help="the role profile the two exclusion lists come from")
    save_cmd.add_argument("--seat", default="", help="passed to the report ledger")
    save_cmd.add_argument("--skip-ledger", action="store_true")
    learn_cmd = sub.add_parser("learn")
    learn_cmd.add_argument("--last", type=int, default=8)
    for one in (save_cmd, learn_cmd):
        one.add_argument("--store", default="", help="the author's folder; $REPORT_STORE_DIR without it")
        one.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.action == "learn":
        result = learn(store_dir(args.store), args.last)
        print(json.dumps(result, indent=1) if args.json else "\n".join(
            [f"# Report record: proposals ({result['records_read']} records)", ""]
            + ([f"- {p['kind']} ({p['weeks']} weeks): {p['detail']}" for p in result["proposals"]]
               or ["No pattern has held long enough to propose anything."])
            + [""] + [f"- {n}" for n in result["notes"]]))
        return OK
    manifest = save(args)
    if args.json:
        print(safe(json.dumps(manifest, indent=1, default=str)))
    else:
        size = manifest["edit_size"]
        print("\n".join(["# Report record", "", f"{manifest['period']} saved under {store_dir(args.store) / 'records'}"]
                        + [f"- {n}: {r['bytes']} bytes, {r['sha256'][:12]}" for n, r in manifest["files"].items()]
                        + [f"- edit size: {size}" if size else "- edit size: not measured"]
                        + [f"- redacted: {r['file']}, {r['rule']} x{r['occurrences']}" for r in manifest["redactions"]]
                        + [f"- not recorded: {k}: {v}" for k, v in manifest["missing"].items()]
                        + [f"- ledger pending: {manifest['ledger_pending']}"]))
    if manifest["ledger_pending"] and not args.skip_ledger:
        print(f"warning: {manifest['missing'].get('ledger')}", file=sys.stderr)
    return OK


if __name__ == "__main__":
    run_main(main)
