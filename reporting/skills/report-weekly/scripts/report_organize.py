#!/usr/bin/env python3
"""report-organize: sort one week's evidence ledger into the profile's categories, in code alone.

Inputs: the evidence ledger (--ledger, whichever tier wrote it), optionally the role profile or
outline (--outline-file; otherwise the one the ledger captured), the figures (--facts: a
report-facts set, or a flat JSON map of key to {value, as_of, source}), the report ledger's
candidates for the week (--ledger-candidates) and the executive's Gate 1 answers for this week
only (--gate1).

What it does: each item goes into at most one category, first match in category order, with
the matched signal recorded; an item nothing matches is unassigned and never folded into the
catch-all. Each category gets its standing metrics (a figure with no value is MISSING, never
zero), its carry-overs (earlier report bullets that named a problem, a delay, a wait, an open
decision or a date now passed, plus the ledger candidates), its ranked evidence and its direct
reports' input. Then the unassigned bucket and the noise report (for the executive, never the
report), the silent list (Gate 2's question), and the Gate 1 proposals: clusters worth a
category, categories to drop or fold this week, catch-all candidates.

Writes the pack (--out, compact JSON that report_verify.py checks a draft against; stdout without
it) and the digest (--digest, the Markdown the workers read once, inlined in their prompts).
`outline.errors` in the pack names anything that stops a report being written from the profile.
Exit 0 ok, 2 error.

Example:
  python3 report_organize.py --ledger ledger.json --outline-file profile.md \\
      --facts facts.json --gate1 gate1.json --out pack.json --digest digest.md
"""

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

import _digest
import _profile as pf
from _common import (OK, STOPWORDS, WORD, Fail, as_date, carry_reasons, expectation_dates,
                     json_or_none, ledger_errors, now_utc, read_json, read_text, run_main, safe, write_json,
                     write_text)

KINDS = ("task", "project", "note", "mail", "meeting")
WEIGHTS = {"meeting_hours": 2.0, "threads_awaiting_owner": 3.0, "p1_tasks": 4.0, "overdue_tasks": 3.0,
           "deadlines_in_lookahead": 2.0, "carry_overs": 5.0, "standing_metrics_present": 1.0,
           "standing_metrics_missing": 2.0}
TIER_NOTES = {"portal": "the work tracker, calendar and mail were read by code",
              "harvester": "a worker read the mail and calendar, so the sweep can have missed things "
                           "and the gates carry more weight",
              "manual": "nothing was connected: the evidence is the supplied files and what the "
                        "executive says at the gates"}
DOMAIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+)+")


# --------------------------------------------------------------------------- reading in

def read_facts(path):
    """(figures by key, warnings, which shape was read). A facts set is flattened here."""
    if not str(path or "").strip():
        return {}, [], None
    target = Path(path).expanduser()
    if not target.is_file():
        return {}, [f"no facts file at {target}; every standing metric from it is MISSING"], None
    if target.suffix.casefold() in (".csv", ".tsv"):
        rows = csv.DictReader(io.StringIO(read_text(target)),
                              delimiter="\t" if target.suffix.casefold() == ".tsv" else ",")
        flat = {r["key"]: {"value": r.get("value") or None, "as_of": r.get("as_of"), "source": r.get("source")}
                for r in ({str(k).strip().casefold(): v for k, v in row.items()} for row in rows) if r.get("key")}
        return flat, [], "csv"
    found = json_or_none(target)
    if isinstance(found, dict) and str(found.get("schema") or "").startswith("report-facts/"):
        figures = found.get("figures") or {}
        return ({k: {"value": r.get("value"), "as_of": r.get("as_of"), "source": r.get("source"),
                     "unit": r.get("unit"), "reason": r.get("reason")} for k, r in figures.items()},
                [], "facts-set")
    if isinstance(found, dict):
        return ({k: (r if isinstance(r, dict) else {"value": r}) for k, r in found.items()}, [], "flat-export")
    return {}, [f"{target} holds neither a facts set nor a map of figures"], None


def read_candidates(path):
    if not str(path or "").strip():
        return [], []
    found = json_or_none(Path(path).expanduser())
    rows = found.get("candidates") if isinstance(found, dict) else found
    if not isinstance(rows, list):
        return [], [f"no candidates list in {path}, so the carry-overs came from earlier reports alone"]
    return [r for r in rows if isinstance(r, dict)], []


def outline_for(ledger, outline_file):
    if str(outline_file or "").strip():
        found = pf.outline_from_file(outline_file)
    else:
        block = ledger.get("outline") or {}
        found = dict(block.get("parsed") or {}) or pf.parse_outline(block.get("text") or "",
                                                                     str(block.get("source") or "unknown"))
        found.setdefault("found", bool(block.get("found")))
    found["errors"], found["warnings"] = pf.validate_outline(found)
    return found


# --------------------------------------------------------------------------- Gate 1 answers

def load_gate1(path):
    """The executive's Gate 1 answers (schema gate1-answers/1), or an unapplied blank."""
    blank = {"applied": False, "categories": {"add": [], "drop": [], "rename": [], "fold": []},
             "items": {"pull_back": [], "strike": [], "move": []},
             "carry_overs": {"answer": [], "strike": []}, "notes": "", "effects": [], "unmatched": []}
    if not str(path or "").strip():
        return blank, []
    found = json_or_none(Path(path).expanduser())
    if not isinstance(found, dict):
        return blank, [f"no readable Gate 1 answers at {path}, so the week was organised as the profile stands"]
    for block in ("categories", "items", "carry_overs"):
        for key in blank[block]:
            value = (found.get(block) or {}).get(key)
            blank[block][key] = list(value) if isinstance(value, list) else []
    blank.update(applied=True, path=str(path), answered_on=found.get("answered_on"),
                 permanent=bool(found.get("permanent")), notes=str(found.get("notes") or ""))
    return blank, []


def apply_gate1_to_outline(outline, answers):
    """This week's categories: renamed, folded, dropped and added in a copy. The catch-all stays last."""
    found = json.loads(json.dumps(outline, default=str))
    cats, effects, unmatched = found["categories"], answers["effects"], answers["unmatched"]
    index = lambda name: next((i for i, c in enumerate(cats) if c["name"].casefold() == str(name).casefold()), -1)  # noqa: E731
    catch_all = lambda: next((c for c in reversed(cats) if c["kind"] == "other"), None)  # noqa: E731
    for entry in answers["categories"]["rename"]:
        at = index(entry.get("from", "")) if isinstance(entry, dict) else -1
        if at < 0 or not str(entry.get("to") or "").strip():
            unmatched.append(f"rename: no category called {entry!r}")
            continue
        cats[at]["name"] = entry["to"].strip()
        effects.append(f"renamed {entry['from']!r} to {entry['to']!r} for this week")
    for entry in answers["categories"]["fold"]:
        old = entry.get("from", "") if isinstance(entry, dict) else str(entry)
        if index(old) < 0:
            unmatched.append(f"fold: no category called {old!r}")
            continue
        into = entry.get("into", "") if isinstance(entry, dict) else ""
        dropped = cats.pop(index(old))
        target = cats[index(into)] if into and index(into) >= 0 else catch_all()
        if target is not None:
            for key, values in (dropped.get("signals") or {}).items():
                target.setdefault("signals", pf.empty_signals()).setdefault(key, [])
                target["signals"][key] += [v for v in values if v not in target["signals"][key]]
        effects.append(f"folded {old!r} into {(target or {}).get('name', 'nothing')!r} for this week")
    for entry in answers["categories"]["drop"]:
        name = entry.get("name", "") if isinstance(entry, dict) else str(entry or "")
        if index(name) < 0:
            unmatched.append(f"drop: no category called {name!r}")
            continue
        cats.pop(index(name))
        effects.append(f"dropped {name!r} for this week")
    for entry in answers["categories"]["add"]:
        if not isinstance(entry, dict) or not str(entry.get("name") or "").strip():
            unmatched.append("add: a category was named with no name")
            continue
        signals = {k: list(v) for k, v in (entry.get("signals") or {}).items() if k in pf.SIGNAL_FIELDS}
        row = {"name": entry["name"].strip(),
               "seat": entry.get("seat") or (found.get("seats") or [{}])[0].get("name", ""),
               "kind": str(entry.get("kind") or "project").casefold(), "covers": entry.get("covers") or "",
               "signals": {**pf.empty_signals(), **signals}, "standing_metrics": [], "owner": ""}
        cats.insert(len(cats) - 1 if cats and cats[-1]["kind"] == "other" else len(cats), row)
        effects.append(f"added {row['name']!r} for this week")
    found["errors"], found["warnings"] = pf.validate_outline(found)
    return found


def apply_gate1_to_pack(pack, answers):
    """Strike, pull back and move items, and strike answered carry-overs, in place."""
    effects, unmatched = answers["effects"], answers["unmatched"]
    cats, loose = pack["categories"], pack["unassigned"]["items"]
    by_name = {c["name"].casefold(): c for c in cats}
    catch_all = next((c for c in reversed(cats) if c["kind"] == "other"), cats[-1] if cats else None)
    struck = {str(r).strip() for r in answers["items"]["strike"] if str(r).strip()}
    if struck:
        before = sum(len(c["evidence"]) for c in cats) + len(loose)
        for c in cats:
            c["evidence"] = [r for r in c["evidence"] if r["ref"] not in struck]
        loose[:] = [r for r in loose if r["ref"] not in struck]
        gone = before - sum(len(c["evidence"]) for c in cats) - len(loose)
        effects.append(f"struck {gone} evidence row(s) the executive said do not belong")
        unmatched += [f"strike: nothing in the pack cites {r}" for r in sorted(struck)
                      if not any(x["ref"] == r for x in pack["items"])]

    def find(ref):
        for c in cats:
            row = next((r for r in c["evidence"] if r["ref"] == ref), None)
            if row:
                return c, row
        return None, next((r for r in loose if r["ref"] == ref), None)

    for entry in answers["items"]["pull_back"]:
        ref = str(entry.get("ref") if isinstance(entry, dict) else entry).strip()
        wanted = str(entry.get("category") or "") if isinstance(entry, dict) else ""
        source, row = find(ref)
        if row is None:
            unmatched.append(f"pull_back: nothing in the pack cites {ref}")
            continue
        row["pulled_back"] = True
        if source is not None:
            effects.append(f"marked {ref} as pulled back by the executive")
            continue
        target = by_name.get(wanted.casefold()) or catch_all
        if target is None:
            unmatched.append(f"pull_back: {ref} has no category to go to")
            continue
        loose.remove(row)
        target["evidence"].append(row)
        effects.append(f"pulled {ref} back into {target['name']!r}"
                       + ("" if wanted else ", the catch-all, because no category was named"))
    for entry in answers["items"]["move"]:
        ref = str(entry.get("ref") if isinstance(entry, dict) else entry).strip()
        wanted = str(entry.get("category") or "") if isinstance(entry, dict) else ""
        target = by_name.get(wanted.casefold())
        if not wanted or target is None:
            unmatched.append(f"move: {ref} names no category this week has ({wanted!r}); it stayed put")
            continue
        source, row = find(ref)
        if row is None:
            unmatched.append(f"move: nothing in the pack cites {ref}")
            continue
        if source is target:
            continue
        origin = source["name"] if source else "the unassigned bucket"
        (source["evidence"] if source else loose).remove(row)
        row["moved_from"] = origin
        target["evidence"].append(row)
        effects.append(f"moved {ref} out of {origin!r} into {target['name']!r}")
    for c in cats:
        c["evidence"].sort(key=lambda r: (-float(r.get("weight") or 0), str(r.get("title") or "").casefold()))
        c["counts"]["evidence"] = len(c["evidence"]) + int(c.get("evidence_left_out") or 0)
    pack["unassigned"]["total"] = len(loose)
    struck_carries = {str(r).strip().casefold() for r in answers["carry_overs"]["strike"] if str(r).strip()}
    if struck_carries:
        for c in cats:
            keep = [x for x in c["carry_overs"] if str(x.get("label") or "").casefold() not in struck_carries
                    and str(x.get("ledger_id") or "").casefold() not in struck_carries]
            if len(keep) < len(c["carry_overs"]):
                effects.append(f"struck {len(c['carry_overs']) - len(keep)} carry-over(s) under {c['name']!r}")
            c["carry_overs"], c["counts"]["carry_overs"] = keep, len(keep)


# --------------------------------------------------------------------------- the sorting

def evidence_row(item):
    """One ledger item in the shape the signals read: counterparties split into domains and names."""
    extra = item.get("extra") or {}
    domains, names = [], []
    for party in item.get("counterparties") or []:
        text = str(party or "").strip()
        if "@" in text:
            domains.append(text.rsplit("@", 1)[1].casefold())
        elif DOMAIN.fullmatch(text) and " " not in text:
            domains.append(text.casefold().lstrip("@"))
        elif text:
            names.append(text)
    row = {"kind": item.get("kind"), "ref": item.get("ref"), "title": " ".join(str(item.get("title") or "").split()),
           "detail": item.get("detail") or "", "text": item.get("text") or "",
           "subject": extra.get("subject") or (item.get("title") if item.get("kind") == "mail" else ""),
           "domains": domains, "names": names, "projects": [str(p) for p in item.get("projects") or [] if p],
           "goals": [str(g) for g in extra.get("goals") or [] if g], "weight": float(item.get("weight") or 0),
           "hours": item.get("hours"), "occurred_at": item.get("occurred_at")}
    for key in ("lists", "priority", "due_date", "flags", "awaiting_owner", "excerpt", "authored_in_period"):
        if extra.get(key) not in (None, [], ""):
            row[key] = extra[key]
    return row


def trimmed(row):
    out = {k: row[k] for k in ("kind", "ref", "title", "detail", "matched_signal", "weight")}
    out.update({k: row[k] for k in ("priority", "due_date", "lists", "flags", "awaiting_owner", "hours",
                                    "occurred_at", "authored_in_period", "pulled_back", "moved_from")
                if row.get(k) not in (None, [], "")})
    return out


def counts_of(rows, carries, metrics):
    tasks = [r for r in rows if r["kind"] == "task"]
    counts = {"evidence": len(rows), "by_kind": {k: len([r for r in rows if r["kind"] == k]) for k in KINDS},
              "meeting_hours": round(sum(float(r.get("hours") or 0) for r in rows if r["kind"] == "meeting"), 2),
              "threads_awaiting_owner": len([r for r in rows if r["kind"] == "mail" and r.get("awaiting_owner")]),
              "p1_tasks": len([t for t in tasks if str(t.get("priority") or "").upper() == "P1"]),
              "overdue_tasks": len([t for t in tasks if "overdue" in (t.get("lists") or [])]),
              "deadlines_in_lookahead": len([t for t in tasks if "due_in_lookahead" in (t.get("lists") or [])]),
              "carry_overs": carries,
              "standing_metrics_present": len([m for m in metrics if m["status"] == "present"]),
              "standing_metrics_missing": len([m for m in metrics if m["status"] == "MISSING"])}
    return counts, round(sum(WEIGHTS[k] * float(counts[k]) for k in WEIGHTS), 2)


def metrics_of(category, facts):
    """Each standing metric with its figure, or MISSING. A metric from the owner is MISSING until
    the owner gives it at Gate 2; nothing is ever estimated."""
    out = []
    for m in category["standing_metrics"]:
        found = facts.get(m.get("facts_key") or "") or {}
        present = found.get("value") is not None
        out.append({"name": m["name"], "source": m["source"], "facts_key": m.get("facts_key") or None,
                    "value": found.get("value") if present else None, "as_of": found.get("as_of") if present else None,
                    "status": "present" if present else "MISSING",
                    "source_label": (found.get("source") or f"facts:{m['facts_key']}") if present
                    else "the owner, at Gate 2" if m["source"] == "owner" else f"facts:{m.get('facts_key')}"})
    return out


def carry_overs(prior, as_of):
    """Every earlier bullet this week has to say what happened to, one per topic label."""
    out = {}
    for report in prior:
        when = as_date(report.get("date"))
        for bullet in report.get("bullets") or []:
            reasons = carry_reasons(bullet["label"], bullet.get("text", ""))
            if when and as_of:
                passed = [d for d in expectation_dates(f"{bullet['label']}: {bullet.get('text')}", when) if d < as_of]
                reasons += [f"the date it named, {passed[0].isoformat()}, has passed"] if passed else []
            if not reasons:
                continue
            key = bullet["label"].casefold()
            if key in out:
                out[key]["weeks_running"] += 1
                continue
            out[key] = {"label": bullet["label"], "text": bullet.get("text", ""), "reason": "; ".join(reasons),
                        "category": bullet.get("category"), "report_title": report.get("title"),
                        "report_date": report.get("date"), "ref": report.get("ref"), "weeks_running": 1}
    return list(out.values())


def merge_candidates(pack, candidates):
    """The report ledger's candidates as carry-overs, merged with the earlier reports' on the
    topic label. One whose category is not this week's goes to the catch-all."""
    cats = pack["categories"]
    catch_all = next((c for c in reversed(cats) if c["kind"] == "other"), None)
    merged = 0
    for row in candidates:
        label = str(row.get("topic") or row.get("label") or "").strip()
        target = next((c for c in cats if c["name"].casefold() == str(row.get("category") or "").casefold()),
                      catch_all)
        if not label or target is None:
            continue
        entry = {"label": label, "text": str(row.get("text") or ""),
                 "reason": str(row.get("reason") or "the report ledger holds it open"),
                 "category": target["name"], "report_title": row.get("report_title"),
                 "report_date": row.get("report_date"), "ref": row.get("_ref") or f"ledger://{row.get('id')}",
                 "weeks_running": int(row.get("weeks_running") or 1), "source": "report-ledger",
                 "ledger_id": row.get("id"), "entry_kind": row.get("kind"), "due_date": row.get("due_date")}
        same = next((c for c in target["carry_overs"] if c["label"].casefold() == label.casefold()), None)
        if same:
            same.update({k: entry[k] for k in ("source", "ledger_id", "entry_kind", "due_date")})
            same["reason"] = f"{same['reason']}; {entry['reason']}"
        else:
            target["carry_overs"].append(entry)
        merged += 1
        target["counts"]["carry_overs"] = len(target["carry_overs"])
        target["importance"] = round(sum(WEIGHTS[k] * float(target["counts"][k]) for k in WEIGHTS), 2)
    pack["ledger_candidates"] = {"count": len(candidates), "merged": merged}


def proposals(pack, outline, unassigned):
    """What Gate 1 asks, counted rather than judged: clusters worth a category, categories to
    drop or fold this week, and the heaviest loose items as catch-all candidates."""
    own = set()
    author = pack.get("author") or {}
    for text in [str(v) for k, v in author.items() if isinstance(v, str) and k not in ("scope_id", "scope_ref")] \
            + [str(outline.get("meeting_signals") or "")]:
        own |= {d.casefold() for d in DOMAIN.findall(text)} | {w.casefold() for w in WORD.findall(text)}
    groups = {"project": {}, "counterparty": {}, "term": {}}
    for row in unassigned:
        for name in row["projects"]:
            groups["project"].setdefault(name, []).append(row)
        for party in row["domains"] + row["names"]:
            if party.casefold() not in own:
                groups["counterparty"].setdefault(party, []).append(row)
        for word in {w.casefold() for w in WORD.findall(row["title"])}:
            if word not in STOPWORDS and len(word) >= 4 and word not in own:
                groups["term"].setdefault(word, []).append(row)
    clusters = sorted(({"kind": kind, "key": key, "items": len(rows),
                        "hours": round(sum(float(r.get("hours") or 0) for r in rows), 2),
                        "refs": [r["ref"] for r in rows][:5], "titles": [r["title"] for r in rows][:5]}
                       for kind, grouped in groups.items() for key, rows in grouped.items() if len(rows) >= 2),
                      key=lambda c: (-c["items"], -c["hours"], c["kind"], c["key"]))[:8]
    adds = [dict(c, reason=f"{c['items']} unassigned items share the {c['kind']} {c['key']!r}"
                 + (f" and {c['hours']} hours of meetings" if c["hours"] else ""))
            for c in clusters if c["items"] >= 3 or c["hours"] >= 2.0]
    cats = pack["categories"]
    drops = [{"name": c["name"], "reason": "nothing matched it, it carries nothing forward and no standing "
                                           "metric has a figure this week"}
             for c in cats if c["kind"] != "other" and not c["counts"]["evidence"] and not c["carry_overs"]
             and not c["counts"]["standing_metrics_present"]]
    folds = [{"name": c["name"], "reason": f"{c['counts']['evidence']} item(s) matched it and nothing carries "
                                           f"forward, so it is a bullet rather than a header this week"}
             for c in cats if c["kind"] != "other" and 0 < c["counts"]["evidence"] <= 2 and not c["carry_overs"]]
    claimed = {ref for c in adds for ref in c["refs"]}
    others = sorted((r for r in unassigned if r["ref"] not in claimed and r["kind"] != "project"),
                    key=lambda r: -r["weight"])[:6]
    others = [{"ref": r["ref"], "kind": r["kind"], "title": r["title"], "detail": r["detail"],
               "weight": round(r["weight"], 2)} for r in others]
    any_one = bool(adds or drops or folds or others)
    return {"clusters": clusters, "add_category": adds, "drop_this_week": drops, "fold_into_other": folds,
            "other_topics_candidates": others,
            "carry_overs_to_answer": sum(len(c["carry_overs"]) for c in cats),
            "any": any_one, "gate_weight": "full" if any_one else "one line"}


def organize(ledger, outline, facts, facts_note, candidates, answers, max_evidence):
    warnings = list((ledger.get("provenance") or {}).get("warnings") or [])
    caps = list((ledger.get("provenance") or {}).get("caps_applied") or [])
    if answers["applied"]:
        outline = apply_gate1_to_outline(outline, answers)
    warnings += [f"outline is not valid: {e}" for e in outline["errors"]] + [f"outline: {w}" for w in outline["warnings"]]
    categories = pf.compile_outline(outline)
    rows = [evidence_row(i) for i in ledger.get("items") or [] if i.get("kind") != "direct_report"]
    grouped = {c["name"]: [] for c in categories}
    unassigned = []
    for row in rows:
        pf.assign(categories, row)
        (grouped[row["category"]] if row["category"] else unassigned).append(row)
    rank = lambda r: (-r["weight"], r["title"].casefold())  # noqa: E731
    prior = list(ledger.get("prior_reports") or [])
    for report in prior:
        for bullet in report.get("bullets") or []:
            probe = {"kind": "prior", "title": bullet["label"], "text": bullet.get("text", ""), "subject": "",
                     "domains": [], "names": [], "projects": [], "goals": []}
            bullet["category"] = pf.assign(categories, probe)["category"]
    direct = list(ledger.get("direct_reports") or [])
    # A direct report's update written as an evidence item (by a worker, say) and not listed
    # under direct_reports still reaches its category.
    listed = {d.get("ref") for d in direct}
    direct += [{"name": (i.get("counterparties") or ["a direct report"])[0], "source": "ledger", "found": True,
                "reports_on": (i.get("extra") or {}).get("reports_on"), "ref": i.get("ref"), "title": i.get("title"),
                "received": i.get("occurred_at"), "text": i.get("text")}
               for i in ledger.get("items") or [] if i.get("kind") == "direct_report" and i.get("ref") not in listed]
    for entry in direct:
        entry["category"] = None
        if entry.get("found"):
            probe = {"kind": "direct_report", "title": str(entry.get("title") or ""), "text": str(entry.get("text") or ""),
                     "subject": "", "domains": [], "names": [str(entry.get("name") or "")], "projects": [], "goals": []}
            entry["category"] = pf.assign(categories, probe)["category"] or next(
                (c["name"] for c in categories if entry.get("name") and c["owner"].casefold() == str(entry["name"]).casefold()), None)
    as_of = as_date((ledger.get("period") or {}).get("as_of"))
    carries = carry_overs(prior, as_of)
    out_categories = []
    for c in categories:
        mine = sorted(grouped[c["name"]], key=rank)
        if len(mine) > max_evidence:
            caps.append(f"the roster under {c['name']!r} was cut to its top {max_evidence} items")
        metrics = metrics_of(c, facts)
        own_carries = [x for x in carries if x.get("category") == c["name"]]
        counts, importance = counts_of(mine, len(own_carries), metrics)
        out_categories.append({
            "name": c["name"], "seat": c["seat"], "kind": c["kind"], "covers": c["covers"], "owner": c["owner"] or None,
            "importance": importance, "counts": counts, "standing_metrics": metrics, "carry_overs": own_carries,
            "evidence": [trimmed(r) for r in mine[:max_evidence]], "evidence_left_out": max(0, len(mine) - max_evidence),
            "direct_report_input": [d for d in direct if d.get("category") == c["name"]],
            "prior_labels": sorted({b["label"] for r in prior for b in r.get("bullets") or []
                                    if b.get("category") == c["name"]})})
    unassigned.sort(key=rank)
    hours_total = round(sum(float(r.get("hours") or 0) for r in rows if r["kind"] == "meeting"), 2)
    loose_hours = round(sum(float(r.get("hours") or 0) for r in unassigned if r["kind"] == "meeting"), 2)
    share = lambda part, whole: round(100.0 * part / whole, 1) if whole else None  # noqa: E731
    total = {k: len([r for r in rows if r["kind"] == k]) for k in ("mail", "task")}
    loose = {k: len([r for r in unassigned if r["kind"] == k]) for k in ("mail", "task")}
    domains, words = {}, {}
    for r in unassigned:
        for d in r["domains"] if r["kind"] in ("mail", "meeting") else []:
            domains[d] = domains.get(d, 0) + 1
        for w in {w.casefold() for w in WORD.findall(r["title"])} - STOPWORDS:
            words[w] = words.get(w, 0) + 1
    calendar = ledger.get("calendar") or {"period": {
        "meetings_in_scope": len([r for r in rows if r["kind"] == "meeting"]), "hours_sum": hours_total}}
    goals = list(ledger.get("goals") or [])
    blob = "\n".join(f"{r['title']}\n{r['text']}" for r in rows).casefold()
    touched = {g.casefold() for r in rows for g in r["goals"]}
    seen_projects = {p.casefold() for r in rows for p in r["projects"]}
    named_projects = list(dict.fromkeys(p for c in categories for p in c["matchers"]["projects"]))
    pack = {
        "schema": "report-pack/1",
        "author": ledger.get("author") or {},
        "period": ledger.get("period") or {},
        "tier": {"name": ledger.get("tier"), "model_driven": bool(ledger.get("model_driven")),
                 "why": TIER_NOTES.get(str(ledger.get("tier")))},
        "outline": outline,
        "categories": out_categories,
        "unassigned": {"counts": {k: len([r for r in unassigned if r["kind"] == k]) for k in KINDS},
                       "total": len(unassigned), "items": [trimmed(r) for r in unassigned]},
        "noise": {"meeting_hours_total": hours_total, "meeting_hours_unassigned": loose_hours,
                  "meeting_hours_unassigned_pct": share(loose_hours, hours_total),
                  "mail_threads_total": total["mail"], "mail_threads_unassigned": loose["mail"],
                  "mail_threads_unassigned_pct": share(loose["mail"], total["mail"]),
                  "open_tasks_total": total["task"], "open_tasks_unassigned": loose["task"],
                  "open_tasks_unassigned_pct": share(loose["task"], total["task"]),
                  "largest_clusters_by_counterparty_domain": [{"domain": d, "items": n} for d, n in
                                                              sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))[:5]],
                  "largest_clusters_by_title_word": [{"word": w, "items": n} for w, n in
                                                     sorted(words.items(), key=lambda kv: (-kv[1], kv[0]))[:5] if n > 1]},
        "continuity": {"reports_read": len(prior),
                       "reports": [{"title": r.get("title"), "date": r.get("date"), "ref": r.get("ref"),
                                    "bullets": len(r.get("bullets") or [])} for r in prior],
                       "carry_overs_total": len(carries),
                       "carry_overs_unassigned": [x for x in carries if not x.get("category")]},
        "direct_reports": {"items": direct, "found": len([d for d in direct if d.get("found")]),
                           "missing": [d.get("name") for d in direct if not d.get("found")]},
        "silent": {"categories": [c["name"] for c in out_categories if not c["evidence"]],
                   "outline_projects": [p for p in named_projects if not any(p in s for s in seen_projects)],
                   "goals": [{"title": g.get("title"), "priority": g.get("priority"), "ref": g.get("_ref")}
                             for g in goals if str(g.get("priority") or "").upper() in ("P1", "P2")
                             and str(g.get("id") or "").casefold() not in touched
                             and str(g.get("title") or "").casefold() not in touched
                             and (not g.get("title") or str(g["title"]).casefold() not in blob)]},
        "assignment": {"assigned": len(rows) - len(unassigned), "unassigned": len(unassigned),
                       "rule": "at most one category per item, first match in category order; an item "
                               "nothing matched is unassigned and never folded into the catch-all"},
        "facts": facts_note,
        "goals": goals,
        "calendar": calendar,
        "items": [{k: v for k, v in r.items() if k != "subject"} for r in rows]
        + [{"kind": "direct_report", "ref": d.get("ref"), "title": d.get("title"), "text": d.get("text"),
            "names": [d.get("name")]} for d in direct if d.get("found")],
    }
    pack["silent"]["count"] = sum(len(pack["silent"][k]) for k in ("categories", "outline_projects", "goals"))
    merge_candidates(pack, candidates)
    pack["proposals"] = proposals(pack, outline, unassigned)
    if answers["applied"]:
        apply_gate1_to_pack(pack, answers)
    pack["gate1"] = answers if answers["applied"] else {
        "applied": False, "note": "no Gate 1 answers were supplied, so the week was organised as the profile stands"}
    if unassigned:
        warnings.append(f"{len(unassigned)} of {len(rows)} evidence items matched no category")
    if ledger.get("model_driven"):
        warnings.append("the evidence was collected by a worker rather than by code, so it can be "
                        "incomplete and the gates carry more weight")
    pack["provenance"] = {"command": "report-organize", "organised_at": now_utc(),
                          "collected_by": ledger.get("generator"), "collected_at": ledger.get("generated_at"),
                          "tier": ledger.get("tier"),
                          "caps_applied": caps, "warnings": warnings,
                          "could_not_determine": list((ledger.get("provenance") or {}).get("could_not_determine") or [])}
    return pack


def main():
    parser = argparse.ArgumentParser(description="Sort one week's evidence into the profile's categories.")
    parser.add_argument("--ledger", required=True, help="the evidence ledger")
    parser.add_argument("--outline-file", default="", help="the role profile, overriding the ledger's")
    parser.add_argument("--facts", default="", help="a report-facts set or a flat map of figures")
    parser.add_argument("--ledger-candidates", default="", help="report_ledger.py candidates output")
    parser.add_argument("--gate1", default="", help="the executive's Gate 1 answers, this week only")
    parser.add_argument("--max-evidence", type=int, default=40, help="evidence rows listed per category")
    parser.add_argument("--out", default="", help="write the pack here, compact; stdout without it")
    parser.add_argument("--digest", default="", help="also write the Markdown digest here")
    args = parser.parse_args()

    ledger = read_json(args.ledger, "evidence ledger")
    errors = ledger_errors(ledger)
    if errors:
        raise Fail(f"{args.ledger} is not a valid evidence ledger: {errors[0]}")
    outline = outline_for(ledger, args.outline_file)
    facts, facts_warnings, shape = read_facts(args.facts)
    candidates, candidate_warnings = read_candidates(args.ledger_candidates)
    answers, answer_warnings = load_gate1(args.gate1)
    note = {"path": str(Path(args.facts).expanduser()) if args.facts else None, "read_as": shape,
            "keys": len(facts), "items": facts, "warnings": facts_warnings}
    pack = organize(ledger, outline, facts, note, candidates, answers, args.max_evidence)
    pack["provenance"]["warnings"] += candidate_warnings + answer_warnings + [f"facts: {w}" for w in facts_warnings]

    for problem in pack["outline"]["errors"]:
        print(safe(f"outline error: {problem}"), file=sys.stderr)
    if args.out.strip():
        path = write_json(args.out, pack, compact=True)
        print(f"{path} ({len(json.dumps(pack, default=str))} characters)")
    else:
        print(safe(json.dumps(pack, indent=1, default=str)))
    if args.digest.strip():
        text, stats = _digest.build(pack)
        write_text(args.digest, text)
        print(f"{args.digest} ({stats['characters']} characters, {len(stats['caps_applied'])} digest caps)")
    return OK


if __name__ == "__main__":
    run_main(main)
