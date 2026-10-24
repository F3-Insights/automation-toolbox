#!/usr/bin/env python3
"""drafts-deliver: put a Run's checked drafts into the owner's Outlook Drafts folder.

The one path every unattended job takes into Outlook Drafts, run as a finish step after the
session. It never sends. For each draft in RUN/deliveries.json that the reviewer passed, it
writes the check record email-deliver reads (RUN/checks/<draft id>.json) and runs
email_deliver.py beside it, so every guard of that command applies: the draft unchanged since
the check (its content hash), still pending, threaded under the pinned email and addressed only
to the pinned contact, and passed by outbound-check. A draft that is refused stays in the Portal
under its id with its reason in the result; refusals are results, not failures.

What each kind may pass:
- `reply`: the owner's answer to mail he was sent. Not a cold nudge, so a cooldown hold does not
  stop it (--allow-recent-contact); a message the owner sent on the thread since still does.
- `delivery`, `holding`: the owner's own promise coming due (the thing, or an honest new date).
  It follows his own earlier message (--follow-up) and a cooldown hold does not stop it.
- `nudge`: a chase of what someone owes the owner. It follows his own message (--follow-up) and
  keeps every hold.

RUN/deliveries.json, written by the session:

  {"tool": "drafts-deliveries", "version": 1, "dry_run": false,
   "drafts": [{"draft_id": "<uuid>", "kind": "reply" | "nudge" | "delivery" | "holding",
               "contact_id": "<uuid>", "email_ref": "portal://email/<uuid>",
               "verdict": "PASS", "content_hash": "sha256:...", "task": "portal://task/<uuid>" | null,
               "needs_your_word": false, "question": null, "why": "one line"}]}

  python3 drafts_deliver.py --run RUN [--dry-run | --dry-run-if=true|false] [--max-drafts 25]

With no deliveries.json there is nothing to deliver (status `nothing`). A set written by a
dry-run session is never delivered live (refused DRY_RUN). --max-drafts is a runaway backstop:
past it the rest are left in the Portal and listed. Writes RUN/deliver.json on a dry run and
a live one alike, with `dry_run` in it (a dry run's results are `would_deliver`), so whatever
reads the Run (a cursor that moves only once delivery ran, the ledger) finds one file; each
result carries the entry's task, needs_your_word and question so a ledger can name the drafts
that need the owner's word. Exit 0 when it ran, 3 when the set is
refused whole, 2 when it could not run.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import _common as c

TOOL, VERSION = "drafts-deliveries", 1
KINDS = ("reply", "delivery", "holding", "nudge")
FOLLOWS_OWNER = ("delivery", "holding", "nudge")      # --follow-up: it follows the owner's own message
OWNERS_OWN = ("reply", "delivery", "holding")          # --allow-recent-contact: not a cold chase
MAX_DRAFTS = 25
UUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
EMAIL_REF = re.compile(r"^(?:portal://email/)?([0-9a-fA-F-]{36})$")
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
EMAIL_DELIVER = Path(__file__).resolve().parent / "email_deliver.py"


class Refused(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


def truthy_flag(value):
    """--dry-run-if from a scheduler placeholder: only an unmistakable value is accepted."""
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise c.Failure(f"--dry-run-if wants true or false, got {value!r}; nothing was delivered")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def problems(d):
    out = []
    if not isinstance(d, dict):
        return ["the entry is not an object"]
    if not UUID.match(str(d.get("draft_id") or "")):
        out.append("draft_id is a uuid")
    if d.get("kind") not in KINDS:
        out.append(f"kind is one of {', '.join(KINDS)}")
    if not UUID.match(str(d.get("contact_id") or "")):
        out.append("contact_id is a uuid")
    if not EMAIL_REF.match(str(d.get("email_ref") or "")):
        out.append("email_ref is portal://email/<uuid>")
    if not HASH.match(str(d.get("content_hash") or "")):
        out.append("content_hash is the reviewer's sha256 hash of the draft")
    return out


def run_deliver(argv):
    """email_deliver.py's JSON answer and exit code."""
    done = subprocess.run([sys.executable, str(EMAIL_DELIVER), *argv], capture_output=True, text=True,
                          timeout=600, stdin=subprocess.DEVNULL)
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        return done.returncode, {"status": "error", "reason": c.safe((done.stderr or done.stdout).strip()[-300:])}


def deliver(run, dry_run, max_drafts=MAX_DRAFTS, runner=run_deliver):
    source = run / "deliveries.json"
    if not source.is_file():
        return {"tool": "drafts-deliver", "status": "nothing", "dry_run": dry_run, "results": [],
                "reason": "no deliveries.json: the session staged no draft for delivery"}
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused("INVALID_SET", f"deliveries.json could not be read ({type(exc).__name__})") from None
    if not isinstance(data, dict) or data.get("tool") != TOOL or data.get("version") != VERSION:
        raise Refused("INVALID_SET", f"deliveries.json is not a {TOOL} v{VERSION} file")
    if not isinstance(data.get("dry_run"), bool) or not isinstance(data.get("drafts"), list):
        raise Refused("INVALID_SET", "deliveries.json needs dry_run true or false and a drafts list")
    if data["dry_run"] and not dry_run:
        raise Refused("DRY_RUN", "deliveries.json was written by a dry-run session; deliver it with --dry-run")
    checks = run / "checks"
    results, seen, pushed = [], set(), 0
    for d in data["drafts"]:
        bad = problems(d)
        entry = d if isinstance(d, dict) else {}
        draft = str(entry.get("draft_id") or "")
        row = {"draft_id": draft or None, "kind": entry.get("kind"), "task": entry.get("task"),
               "needs_your_word": bool(entry.get("needs_your_word")), "question": entry.get("question")}
        if bad:
            results.append(dict(row, status="refused", code="INVALID_ENTRY", reason="; ".join(bad)))
            continue
        if draft in seen:
            results.append(dict(row, status="refused", code="DUPLICATE_ENTRY", reason="the draft is listed twice"))
            continue
        seen.add(draft)
        if str(entry.get("verdict") or "").upper() != "PASS":
            results.append(dict(row, status="left_in_portal", code="NOT_PASSED",
                                reason=f"the reviewer said {entry.get('verdict')!r}, not PASS"))
            continue
        if pushed >= max_drafts:
            results.append(dict(row, status="left_in_portal", code="DEFERRED",
                                reason=f"--max-drafts {max_drafts} reached; the draft is in the Portal"))
            continue
        pushed += 1
        check = checks / f"{draft}.json"
        atomic_json(check, {"verdict": "PASS", "draft_id": draft, "content_hash": entry["content_hash"],
                            "contact_id": entry["contact_id"], "email_ref": entry["email_ref"],
                            "checker": "productivity-reviewer", "kind": entry["kind"], "task": entry.get("task"),
                            "why": entry.get("why")})
        argv = ["--draft", draft, "--check", str(check), "--contact", entry["contact_id"], "--email",
                entry["email_ref"]]
        if entry["kind"] in FOLLOWS_OWNER:
            argv.append("--follow-up")
        if entry["kind"] in OWNERS_OWN:
            argv.append("--allow-recent-contact")
        if dry_run:
            argv.append("--dry-run")
        code, out = runner(argv)
        status = str(out.get("status") or "error")
        results.append(dict(row, status=status if code in (0, 3) else "error", exit=code,
                            refusals=out.get("refusals") or [], reason=out.get("reason"),
                            delivered_to=out.get("delivered_to"), web_link=out.get("web_link"),
                            compose_url=out.get("compose_url"),
                            recent_contact_overridden=out.get("recent_contact_overridden")))
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"tool": "drafts-deliver", "status": "nothing" if not results else "done", "dry_run": dry_run,
            "counts": counts, "results": results}


def main(argv=None, runner=run_deliver):
    p = argparse.ArgumentParser(prog="drafts_deliver.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, help="the Run folder holding deliveries.json")
    p.add_argument("--dry-run", action="store_true", help="run every guard, push nothing")
    p.add_argument("--dry-run-if", default=None, help="true or false (a scheduler placeholder); true is --dry-run")
    p.add_argument("--max-drafts", type=int, default=MAX_DRAFTS, help=f"runaway backstop (default {MAX_DRAFTS})")
    a = p.parse_args(argv)
    try:
        dry_run = a.dry_run or (a.dry_run_if is not None and truthy_flag(a.dry_run_if))
        if not 0 <= a.max_drafts <= 200:
            raise c.Failure("--max-drafts is 0 to 200")
        run = c.guard_run_path(a.run)
        if not run.is_dir():
            raise c.Failure(f"the Run folder {run} does not exist")
        try:
            result = deliver(run, dry_run, a.max_drafts, runner)
        except Refused as exc:
            c.emit({"tool": "drafts-deliver", "status": "refused", "code": exc.code, "reason": exc.reason}, c.STOP)
        atomic_json(run / "deliver.json", result)
    except c.Failure as exc:
        c.emit({"tool": "drafts-deliver", "status": "error", "reason": str(exc)}, c.ERROR)
    c.emit(result, c.OK)


if __name__ == "__main__":
    main()
