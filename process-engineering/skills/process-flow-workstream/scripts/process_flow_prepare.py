# /// script
# dependencies = ["pyyaml", "openpyxl"]
# ///
"""Stage one engagement process into a Run folder, reading the engagement and writing nothing
outside the Run folder.

    process_flow_prepare.py ENGAGEMENT [--process P] [--scope as-is|as-is-and-to-be]
                            [--audience TEXT] --out DIR [--format text|json]

ENGAGEMENT is a Context name (looked up in the owner setting `contexts_dir`) or the path to a
Context file; _common.py says which folder Sources it reads. The process is --process, else the
rules file's `Default process`; scope and audience fall back to the rules file's `Scope` and
`Audience`. A blank option (--process=) means not given.

--out must not exist or be empty. Into it go: the process folder's state as the last session
left it (`process-flows/<process>/`); PROCESS-FLOW-RULES.md and BACKGROUND.md; REFERENCE-MODEL.md,
the model the rules file's `Reference model` names (a file beside the rules file, else
`<name>.md` in the reference-process-models skill, or the folder the setting
`[process-flow-workstream] reference_models_dir` names); sources.json, the source register (a
stable id per file, its hash, its fact-check half A or B, and `duplicate_of` where two files
record the same meeting); sources/<id>.<ext>, each source as readable text; and engagement.json,
what was resolved (the delivery folder among it) and the hash of every staged state file, so
process_flow_publish.py writes back only what the session changed.

Prints `FRESH <summary>` first. Exit 0 when staged, 2 on a bad argument, a Context that does not
resolve or an --out that is not empty.

Example:
    python3 process_flow_prepare.py acme-q2o --out runs/2026-10-06/work
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import _common as C


def reference_model(name, eng):
    """The reference model file the rules file names, or None."""
    if not name:
        return None
    for base in (eng["standing"], eng["working"]):
        if (base / name).expanduser().is_file():
            return (base / name).expanduser()
    slug = name.strip().lower().replace(" ", "-").removesuffix(".md")
    library = C.settings(C.SKILL).get("reference_models_dir") or "~/.claude/skills/reference-process-models"
    cand = Path(library).expanduser() / f"{slug}.md"
    return cand if cand.is_file() else None


def copy_state(src, out):
    """Copy the process folder into out; returns {relpath: sha256} of what was copied."""
    hashes = {}
    if not src.is_dir():
        return hashes
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src).as_posix()
        if not p.is_file() or any(part.startswith(".") for part in Path(rel).parts) or p.name.startswith("~$"):
            continue
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out / rel)
        hashes[rel] = C.sha256_file(p)
    return hashes


def stage_sources(eng, rules, out):
    """Register and convert every source; an unchanged source keeps its earlier conversion."""
    registry = C.read_json(out / C.SOURCES_FILE, {}) or {}
    found = C.scan_sources(eng, rules)
    entries = C.assign_ids(found, registry)
    by_key = {f["key"]: f for f in found}
    old = {e.get("key"): e for e in registry.get("sources") or []}
    sdir = out / "sources"
    sdir.mkdir(parents=True, exist_ok=True)
    texts, exts = {}, {}
    for e in entries:
        e.pop("changed", None)
        if not e.get("present"):
            continue
        path = by_key[e["key"]]["path"]
        prior = old.get(e["key"]) or {}
        if prior.get("sha256") == e["sha256"] and prior.get("staged") and (out / prior["staged"]).is_file():
            e["staged"], e["note"] = prior["staged"], prior.get("note", "")
        else:
            text, ext, note = C.convert(path)
            e["note"], e["staged"] = note, None
            if text is not None:
                (sdir / f"{e['id']}{ext}").write_text(text, encoding="utf-8")
                e["staged"] = f"sources/{e['id']}{ext}"
            elif ext in C.IMAGE_EXT:
                shutil.copy2(path, sdir / f"{e['id']}{ext}")
                e["staged"] = f"sources/{e['id']}{ext}"
            e["changed"] = "changed" if prior else "new"
        e["evidence"] = bool(e.get("staged"))
        if e["evidence"]:
            staged = out / e["staged"]
            e["weight"] = C.IMAGE_WEIGHT if staged.suffix.lower() in C.IMAGE_EXT else staged.stat().st_size
        exts[e["id"]] = Path(e["file"]).suffix.lower()
        if e["kind"] == "transcript" and e.get("staged") and Path(e["staged"]).suffix in (".txt", ".md"):
            texts[e["id"]] = (out / e["staged"]).read_text(encoding="utf-8", errors="replace")
    dups = C.find_duplicates(texts, exts)
    for e in entries:
        if e["id"] in dups:
            e["duplicate_of"] = dups[e["id"]]
        else:
            e.pop("duplicate_of", None)
    C.balance_halves(entries)
    return entries


def prepare(ref, out, process=None, scope=None, audience=None):
    eng = C.load_engagement(ref)
    _, parsed, _ = C.load_rules(eng["standing"])
    process = (process or C.default_process(parsed) or "").strip().lower()
    if not process:
        raise C.EngagementError("no process given and the rules file names no Default process")
    if not C.SLUG_RE.match(process):
        raise C.EngagementError(f"process '{process}' is not a slug (lowercase letters, digits and -)")
    rules, _, rules_path = C.load_rules(eng["standing"], process)
    scope = scope or rules.get("scope") or "as-is-and-to-be"
    if scope not in C.SCOPES:
        raise C.EngagementError(f"scope '{scope}' is not one of {', '.join(C.SCOPES)}")
    audience = audience or rules.get("audience") or ""
    delivery = C.resolve_delivery(eng, process, rules.get("client"))
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise C.EngagementError(f"{out} is not empty; prepare never writes over a staged folder")
    out.mkdir(parents=True, exist_ok=True)

    pdir = C.process_dir(eng, process)
    state = copy_state(pdir, out)
    for name in (C.RULES_FILE, C.BACKGROUND_FILE):
        src = eng["standing"] / name if (eng["standing"] / name).is_file() else eng["working"] / name
        if src.is_file():
            shutil.copy2(src, out / name)
    ref_model = reference_model(rules.get("reference model"), eng)
    if ref_model:
        shutil.copy2(ref_model, out / "REFERENCE-MODEL.md")

    entries = stage_sources(eng, rules, out)
    C.write_json(out / C.SOURCES_FILE, {"engagement": eng["name"], "process": process, "sources": entries})
    map_v, _ = C.latest(out / "maps", "map v{v}.json")
    C.write_json(out / C.STAGED_MARKER, {
        "engagement": C.describe(eng), "process": process, "scope": scope, "audience": audience,
        "process_dir": str(pdir), **delivery, "rules_present": rules_path is not None, "rules": rules,
        "reference_model": str(ref_model) if ref_model else None,
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state": state, "map_version": map_v})
    usable = [e for e in entries if e.get("present") and e.get("evidence") and not e.get("duplicate_of")]
    return {
        "out": str(out), "engagement": eng["name"], "process": process, "scope": scope, "audience": audience,
        "first_session": not state, "map_version": map_v, "rules_present": rules_path is not None,
        "reference_model": str(ref_model) if ref_model else None, **delivery,
        "transcripts": sum(1 for e in usable if e["kind"] == "transcript"),
        "background": sum(1 for e in usable if e["kind"] == "background"),
        "duplicates": [{"id": e["id"], "of": e["duplicate_of"]} for e in entries if e.get("duplicate_of")],
        "unreadable": [{"id": e["id"], "file": e["file"], "note": e.get("note")}
                       for e in entries if e.get("present") and not e.get("evidence")],
        "new_or_changed": [e["id"] for e in entries if e.get("changed")],
        "gone": [e["id"] for e in entries if not e.get("present")],
        "halves": {h: [e["id"] for e in usable if e.get("half") == h] for h in ("A", "B")},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Stage an engagement process's sources, rules and prior state into a Run folder.")
    p.add_argument("engagement", nargs="?", default="", help="A Context name, or the path to a Context file")
    p.add_argument("--process", default="", help="The process slug; blank: the rules file's Default process")
    p.add_argument("--scope", default="", help="as-is or as-is-and-to-be; blank: the rules file's, else both")
    p.add_argument("--audience", default="", help="Who reads the map; blank: the rules file's")
    p.add_argument("--out", required=True, help="The staged folder to write (must be empty)")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        if not a.engagement.strip():
            raise C.EngagementError("ENGAGEMENT is required: a Context name or the path to a Context file")
        r = prepare(a.engagement.strip(), Path(a.out).expanduser(), C.blank(a.process), C.blank(a.scope),
                    C.blank(a.audience))
    except C.EngagementError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(f"FRESH {r['engagement']}/{r['process']}: {r['transcripts']} transcript(s), {r['background']} "
          f"background source(s), {len(r['new_or_changed'])} new or changed since the last session, "
          + (f"map v{r['map_version']}" if r["map_version"] else "no map yet")
          + ("" if r["rules_present"] else "; NO RULES FILE"))
    if a.fmt == "json":
        print(json.dumps(r, indent=1))
        return 0
    print(f"staged into {r['out']}; scope {r['scope']}; audience {r['audience'] or 'not set'}")
    print(f"drafts deliver to {r['delivery'] or 'nowhere'} ({r['delivery_basis']})")
    print(f"fact-check halves: A {', '.join(r['halves']['A']) or '-'}; B {', '.join(r['halves']['B']) or '-'}")
    for d in r["duplicates"]:
        print(f"duplicate: {d['id']} records the same meeting as {d['of']}; not read")
    for u in r["unreadable"]:
        print(f"unreadable: {u['id']} {u['file']} ({u['note']})")
    if not r["reference_model"]:
        print("no reference model: the rules file names none, or it was not found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
