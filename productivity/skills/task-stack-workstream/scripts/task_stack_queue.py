#!/usr/bin/env python3
"""task-stack-queue: the work queue of one task-stack Run, from a task_stack_check.py json.

Takes the tasks flagged in the chosen components (default filing, next_action, no_due_date,
waiting), keeps the owner's own and unowned tasks (other people's are counted, not queued),
orders them worst domain first (most flagged, then lowest score), then highest priority, then
oldest, caps the list and cuts it into batches b1, b2, ... for the workers.

Inputs: CHECK_JSON (the check's json output); --owner defaults to its owner_contact_id.
Offline: reads one file and writes at most one new file (--out, never overwritten).

Output: text (first line QUEUE: or NOTHING:), or --format json. Exit 0 when it ran, 2 on a
bad argument. A missing CHECK_JSON (the check before it could not read the Portal) prints
STALE: and exits 0.

Example:
  python3 task_stack_queue.py RUN/before.json --max 50 --batch-size 25 --format json --out RUN/queue.json
"""

import argparse
import json
import sys
from pathlib import Path

TOOL, VERSION = "task-stack-queue", 1
CLARIFY = ("filing", "next_action", "no_due_date", "waiting")
COMPONENTS = ("filing", "next_action", "overdue", "stale", "no_due_date", "waiting", "duplicates",
              "projects", "goals")
MAX_DEFAULT, BATCH_DEFAULT = 50, 25
NO_DOMAIN = "(no domain)"


class Stop(Exception):
    pass


def priority_rank(value):
    """P1 -> 1 ... P4 -> 4; anything else sorts last."""
    text = str(value or "").strip().upper().lstrip("P")
    return int(text) if text.isdigit() and 0 < int(text) < 10 else 99


def load_check(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Stop(f"{path} is not a readable json file ({type(exc).__name__})") from None
    if not isinstance(data, dict) or data.get("tool") != "task-stack-check" or "findings" not in data:
        raise Stop(f"{path} is not a task-stack-check json output")
    return data


def domain_matches(task, want, domains):
    want = want.strip().lower()
    ids = {str(d.get("id") or "").lower() for d in domains
           if str(d.get("id") or "").lower() == want or want in str(d.get("name") or "").lower()}
    return str(task.get("domain_id") or "").lower() in ids or want in str(task.get("domain") or "").lower()


def dom(row):
    return str(row.get("domain") or NO_DOMAIN)


def build(data, components=CLARIFY, owner=None, max_tasks=MAX_DEFAULT, batch_size=BATCH_DEFAULT, domain=""):
    owner = (owner or data.get("owner_contact_id") or "").strip().lower() or None
    tasks = {}
    for comp in components:
        for f in (data.get("findings") or {}).get(comp) or []:
            ref = str(f.get("ref") or "")
            if not ref.startswith("portal://task/"):
                continue
            row = tasks.setdefault(ref, {
                "ref": ref, **{k: f.get(k) for k in ("title", "domain", "domain_id", "project", "project_id",
                                                     "status", "priority", "created_at", "updated_at", "due",
                                                     "owner_contact_id")},
                "lenses": [], "reasons": {}})
            row["lenses"].append(comp)
            row["reasons"][comp] = f.get("reason") or ""
    others, eligible = 0, []
    for row in tasks.values():
        if domain and not domain_matches(row, domain, data.get("domains") or []):
            continue
        holder = str(row.get("owner_contact_id") or "").strip().lower()
        if owner and holder and holder != owner:
            others += 1
            continue
        eligible.append(row)
    scores = {d.get("name"): d.get("score") for d in data.get("domains") or []}
    per_domain = {}
    for row in eligible:
        per_domain[dom(row)] = per_domain.get(dom(row), 0) + 1

    def domain_key(name):
        score = scores.get(name)
        return (-per_domain[name], float(score) if isinstance(score, (int, float)) else 101.0, name.lower())

    order = sorted(per_domain, key=domain_key)
    rank = {name: i for i, name in enumerate(order)}
    eligible.sort(key=lambda r: (rank[dom(r)], priority_rank(r.get("priority")),
                                 str(r.get("created_at") or "9999"), r["ref"]))
    queued = eligible[:max_tasks]
    for i, row in enumerate(queued):
        row["batch"] = f"b{i // batch_size + 1}"
    domains_out = []
    for name in order:
        q = sum(1 for r in queued if dom(r) == name)
        domains_out.append({"name": name, "score": scores.get(name), "eligible": per_domain[name],
                            "queued": q, "deferred": per_domain[name] - q})
    return {"tool": TOOL, "version": VERSION, "as_of": data.get("as_of"), "components": list(components),
            "owner_contact_id": owner, "domain": domain or None, "max": max_tasks, "batch_size": batch_size,
            "flagged": len(tasks), "others": others, "eligible": len(eligible), "queued": len(queued),
            "deferred": len(eligible) - len(queued), "domains": domains_out,
            "batches": sorted({r["batch"] for r in queued}, key=lambda b: int(b[1:])), "tasks": queued}


def first_line(result):
    comps = ", ".join(result["components"])
    if not result["queued"]:
        extra = f"; {result['others']} other people's tasks left alone" if result["others"] else ""
        return f"NOTHING: no task of the owner's flagged in {comps}{extra}"
    where = ", ".join(f"{d['name']} {d['queued']}" for d in result["domains"] if d["queued"])
    return (f"QUEUE: {result['queued']} of {result['eligible']} tasks queued ({where}); "
            f"{result['deferred']} deferred; {result['others']} other people's tasks left alone")


def as_text(result):
    return "\n".join([first_line(result)] + [
        f"  {r['batch']} {r['ref']} [{dom(r)}] {r.get('priority') or '-'} {', '.join(r['lenses'])}: {r.get('title') or ''}"
        for r in result["tasks"]])


def whole(value, name, default, low, high):
    text = str(value or "").strip()
    if not text:
        return default
    if not text.isdigit() or not low <= int(text) <= high:
        raise Stop(f"--{name} wants a whole number from {low} to {high}, got {value!r}")
    return int(text)


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_stack_queue.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("check_json", help="A task_stack_check.py --format json output")
    p.add_argument("--max", dest="max_tasks", default=str(MAX_DEFAULT), help="At most this many tasks")
    p.add_argument("--batch-size", default=str(BATCH_DEFAULT), help="Tasks per worker batch")
    p.add_argument("--domain", default="", help="Only this domain (id, or name contains)")
    p.add_argument("--components", default=",".join(CLARIFY), help="Components whose flagged tasks are queued")
    p.add_argument("--owner", default="", help="The owner's contact id (default: the check's owner_contact_id)")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    p.add_argument("--out", default="", help="Also write the json to this new file (never overwritten)")
    args = p.parse_args(argv)
    try:
        cap = whole(args.max_tasks, "max", MAX_DEFAULT, 1, 5000)
        size = whole(args.batch_size, "batch-size", BATCH_DEFAULT, 1, 500)
        comps = [n.strip() for n in args.components.replace(" ", ",").split(",") if n.strip()] or list(CLARIFY)
        unknown = [n for n in comps if n not in COMPONENTS]
        if unknown:
            raise Stop(f"unknown component {', '.join(unknown)} (known: {', '.join(COMPONENTS)})")
        not_tasks = [n for n in comps if n in ("projects", "goals")]
        if not_tasks:
            raise Stop(f"{', '.join(not_tasks)} flag projects and goals, not tasks")
        comps = list(dict.fromkeys(comps))
        out_path = Path(args.out).expanduser() if args.out.strip() else None
        if out_path is not None and out_path.exists():
            raise Stop(f"--out {args.out!r} exists; this command never overwrites a file")
        source = Path(args.check_json).expanduser()
        if not source.exists():
            print(f"STALE: {args.check_json} does not exist; no queue written")
            sys.exit(0)
        result = build(load_check(source), comps, args.owner or None, cap, size, args.domain.strip())
    except Stop as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        sys.exit(2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(result, indent=1, ensure_ascii=False, default=str) + "\n")
    if args.fmt == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(as_text(result) if out_path is None else first_line(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
