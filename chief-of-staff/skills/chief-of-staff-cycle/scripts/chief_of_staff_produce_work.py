#!/usr/bin/env python3
"""chief-of-staff-produce-work: the produce-work doer's two halves in code, around the draft the
cycle's main agent writes (chief-of-staff-cycle-runner, by chief-of-staff-cycle's section Produce one draft).

    pack TARGET --cycle CYCLE_DIR [--add REF ...] [--dry-run]
    save TARGET --cycle CYCLE_DIR --fingerprint F --result FILE [--dry-run]

TARGET is task:UUID, project:UUID, meeting:UUID, email:UUID or goal:UUID, never free text.

`pack` reads the selected record with one Portal `get`, refuses a response that does not hold
the record's own id (a not-found message echoes the id back), adds each related record named
with --add (TYPE:UUID or portal://TYPE/UUID, at most six: the thread, meeting or project the
draft needs, read the same way and cited as portal://TYPE/UUID), adds the fixed guidance (the
owner's principles file and voice guide, the settings principles and voice_guide, each cut to
16,000 characters) and refuses a packet over 120,000 characters. The fingerprint covers the
production instructions (task-stack-produce's SKILL.md) and the packet, so unchanged
evidence maps to the same folder:
- already_prepared: a prepared artifact for this evidence exists unedited; no duplicate (exit 0).
- held: a result for this evidence exists but is blocked or was edited; kept (exit 3).
- ok: the packet is written as source.json in the artifact folder (exit 0).

`save` validates the draft's JSON (prepared: a title, an artifact of at least 200
characters, source references all from the packet including a portal:// one, assumptions and
review items as lists of strings; blocked: a reason), then writes review.json, artifact.md
and manifest.json. The structural check is all it proves; a person still reviews the draft.

Artifacts live in <state>/artifacts/<target>/<fingerprint>/, mode 0700. In a cycle started
with --dry-run, or with --dry-run, nothing is written: pack answers would_pack and save
answers would_save. Exit 0 to go on, 3 for a hold or an invalid result, 2 when it could not run.

Example:
    chief-of-staff-produce-work pack task:00000000-1111-4111-8111-111111111111 --cycle CYCLE
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import _common as c

TARGET = re.compile(r"^(task|project|meeting|email|goal):(" + c.UUID + r")$")
RELATED = re.compile(r"^(?:portal://)?(task|project|meeting|calendar_event|email|goal|note|contact|company)[:/]("
                     + c.UUID + r")$")
MAX_RELATED = 6
GUIDANCE_CHARS = 16000
PACKET_MAX = 120000
MIN_ARTIFACT = 200


def parse_target(target):
    m = TARGET.match(target or "")
    if not m:
        raise c.Bad("the target is an entity type and a UUID, e.g. task:<uuid>, never free text")
    return m.group(1), m.group(2)


def _contains_id(value, uid):
    if isinstance(value, dict):
        return str(value.get("id", "")).lower() == uid.lower() or any(_contains_id(v, uid) for v in value.values())
    if isinstance(value, list):
        return any(_contains_id(v, uid) for v in value)
    return False


def guidance_files():
    """The owner's principles and voice guide, when the settings name them."""
    out = []
    for key in ("principles", "voice_guide"):
        value = c.setting(key)
        if value and Path(value).expanduser().is_file():
            out.append((f"setting:{key}", Path(value).expanduser()))
    return out


def _read(client, kind, uid, what):
    data = client.call("get", {"entity_type": kind, "id_or_query": uid})
    if not isinstance(data, dict) or data.get("error") or set(data) <= {"text"}:
        raise c.Bad(f"the {what} could not be resolved")
    if not _contains_id(data, uid):
        raise c.Bad(f"the {what} was not present in the response")
    return data


def parse_related(refs):
    """[(kind, uuid)] for --add, in order, without repeats; at most MAX_RELATED."""
    out = []
    for ref in refs or []:
        m = RELATED.match(str(ref).strip())
        if not m:
            raise c.Bad(f"--add takes TYPE:UUID or portal://TYPE/UUID, got {c.flat(ref, 80)!r}")
        pair = (m.group(1), m.group(2).lower())
        if pair not in out:
            out.append(pair)
    if len(out) > MAX_RELATED:
        raise c.Bad(f"--add takes at most {MAX_RELATED} related records")
    return out


def build_packet(client, target, related=None):
    kind, uid = parse_target(target)
    data = _read(client, kind, uid, "source")
    sources = [{"ref": f"portal://{kind}/{uid}", "content": data}]
    for rkind, ruid in parse_related(related):
        if (rkind, ruid) == (kind, uid.lower()):
            continue
        sources.append({"ref": f"portal://{rkind}/{ruid}", "content": _read(client, rkind, ruid, f"related {rkind}")})
    related_count = len(sources) - 1
    for ref, path in guidance_files():
        sources.append({"ref": ref, "content": path.read_text(encoding="utf-8")[:GUIDANCE_CHARS]})
    packet = {"target": target, "sources": sources,
              "limitations": ("Hydrated selected entity" + (" and the related records added" if related_count else "")
                              + " only. Do not assume complete inbox, attachment or current-draft coverage.")}
    if len(json.dumps(packet)) > PACKET_MAX:
        raise c.Bad("the source packet is too large; select a narrower task")
    return packet


def fingerprint(packet):
    path = c.PRODUCE_INSTRUCTIONS
    instructions = path.read_text(encoding="utf-8") if path.exists() else ""
    return hashlib.sha256((instructions + json.dumps(packet, sort_keys=True)).encode()).hexdigest()[:20]


def artifact_dir(root, target, fp):
    parse_target(target)
    if not re.fullmatch(r"[0-9a-f]{20}", fp or ""):
        raise c.Bad("--fingerprint is the 20-hex value pack printed")
    return Path(root) / "artifacts" / target.replace(":", "-") / fp


def existing_prepared(folder):
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
        digest = hashlib.sha256((folder / "artifact.md").read_bytes()).hexdigest()
        return manifest.get("status") == "prepared" and manifest.get("sha256") == digest
    except (OSError, ValueError):
        return False


def validate_result(value, refs):
    if not isinstance(value, dict):
        raise c.Bad("the draft is not a JSON object")
    if value.get("status") == "blocked":
        if not isinstance(value.get("reason"), str) or not value["reason"].strip():
            raise c.Bad("a blocked result needs a reason")
        return value
    if value.get("status") != "prepared":
        raise c.Bad("the draft is neither prepared nor blocked")
    for field in ("title", "artifact"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise c.Bad("missing deliverable content")
    if len(value["artifact"].strip()) < MIN_ARTIFACT:
        raise c.Bad("deliverable too short for structural acceptance")
    cited = value.get("source_refs")
    if (not isinstance(cited, list) or not cited or any(not isinstance(r, str) or r not in refs for r in cited)
            or not any(r.startswith("portal://") for r in cited)):
        raise c.Bad("unknown or missing source references")
    for field in ("assumptions", "review_needed"):
        if not isinstance(value.get(field), list) or any(not isinstance(i, str) for i in value[field]):
            raise c.Bad("missing review information")
    return value


def cycle_is_dry(cycle):
    data = c.read_json(Path(cycle) / "cycle.json")
    if not isinstance(data, dict):
        raise c.Bad(f"{cycle} is not a cycle folder (no cycle.json)")
    return bool(data.get("dry_run"))


def pack(client, root, target, cycle, dry_run=False, related=None):
    dry_run = dry_run or cycle_is_dry(cycle)
    packet = build_packet(client, target, related)
    fp = fingerprint(packet)
    folder = artifact_dir(root, target, fp)
    if existing_prepared(folder):
        return {"status": "already_prepared", "target": target, "fingerprint": fp, "local_path": str(folder / "artifact.md"),
                "outcome": "already prepared: the private artifact remains available for review; no duplicate"}
    if (folder / "manifest.json").exists():
        return {"status": "held", "target": target, "fingerprint": fp, "local_path": str(folder),
                "outcome": "held: an existing private result is blocked or was edited; kept, not regenerated"}
    out = {"status": "would_pack" if dry_run else "ok", "target": target, "fingerprint": fp, "dry_run": dry_run,
           "instructions": str(c.PRODUCE_INSTRUCTIONS), "sources": [s["ref"] for s in packet["sources"]]}
    if not dry_run:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        c.atomic_json(folder / "source.json", packet)
        out["packet"] = str(folder / "source.json")
    return out


def save(root, target, fp, result_text, cycle, dry_run=False):
    dry_run = dry_run or cycle_is_dry(cycle)
    folder = artifact_dir(root, target, fp)
    if existing_prepared(folder):
        return {"status": "already_prepared", "target": target, "local_path": str(folder / "artifact.md")}
    packet = c.read_json(folder / "source.json")
    if not isinstance(packet, dict):
        if dry_run:
            return {"status": "would_save", "target": target, "dry_run": True,
                    "reason": "a dry run packs nothing, so there is nothing to save"}
        raise c.Bad("no source.json for this target and fingerprint: run pack first")
    try:
        value = validate_result(c.load_object(result_text), {s.get("ref") for s in packet.get("sources") or []})
    except c.Bad as exc:
        return {"status": "invalid", "target": target, "reason": str(exc),
                "outcome": "failed: the draft did not pass the structural check; nothing claimed"}
    if dry_run:
        return {"status": "would_save", "target": target, "result_status": value["status"], "dry_run": True}
    os.umask(0o077)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    (folder / "review.json").write_text(json.dumps(value, indent=2) + "\n")
    manifest = {"status": value["status"], "created_at": c.local_now().isoformat(),
                "verification": "structure-and-source-membership-only", "review_required": True}
    if value["status"] == "prepared":
        (folder / "artifact.md").write_text(value["artifact"].strip() + "\n")
        manifest["sha256"] = hashlib.sha256((folder / "artifact.md").read_bytes()).hexdigest()
    c.atomic_json(folder / "manifest.json", manifest)
    if value["status"] == "blocked":
        return {"status": "blocked", "target": target, "local_path": str(folder / "review.json"),
                "outcome": "blocked: the packet did not hold enough evidence; the private review.json says what is missing"}
    return {"status": "prepared", "target": target, "local_path": str(folder / "artifact.md"),
            "outcome": "prepared: private review-ready draft; source references checked; human review still required"}


def main(argv=None):
    p = argparse.ArgumentParser(description="The produce-work doer's pack and save. One JSON object out.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("pack", "save"):
        s = sub.add_parser(name)
        s.add_argument("target")
        s.add_argument("--cycle", dest="cycle_dir", required=True, help="The cycle folder; a dry-run cycle writes nothing")
        s.add_argument("--state", default=None, help="State folder (default: the settings)")
        s.add_argument("--dry-run", action="store_true")
        if name == "pack":
            s.add_argument("--config", default=None, help="MCP config holding the Portal (default: setting portal_mcp_config)")
            s.add_argument("--server", default=None)
            s.add_argument("--add", dest="related", action="append", default=[],
                           help="A related record the draft needs, TYPE:UUID or portal://TYPE/UUID (repeat, at most 6)")
        else:
            s.add_argument("--fingerprint", dest="fp", required=True)
            s.add_argument("--result", dest="result_path", required=True, help="The draft's JSON, saved verbatim")
    args = p.parse_args(argv)
    try:
        cycle = c.cycle_dir(args.cycle_dir)
        root = c.state_root(args.state)
        if args.cmd == "pack":
            out = pack(c.Portal(args.config, args.server), root, args.target, cycle, args.dry_run, args.related)
            c.emit(out, c.STOP if out["status"] == "held" else c.OK)
        text = Path(args.result_path).expanduser().read_text(encoding="utf-8", errors="replace")
        out = save(root, args.target, args.fp, text, cycle, args.dry_run)
    except (c.Bad, OSError) as exc:
        c.fail(str(exc))
    c.emit(out, c.OK if out["status"] in ("prepared", "already_prepared", "would_save") else c.STOP)


if __name__ == "__main__":
    main()
