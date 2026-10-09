# /// script
# dependencies = ["pyyaml"]
# ///
"""Put the week's checked cover email into the owner's Outlook Drafts. It never sends.

The Automation's finish step (skipped on a dry run). The first line printed is one of:

  FILE: the cover email stays a file in the week folder (<reason>)
        the variant is a deck, the rules' Email delivery is file, the rules name more than one
        Recipient (a pushed reply reaches only the sender of the email it answers), or there is
        no work/delivery.json (no staged Portal draft).
  ALREADY: delivered at <when>     work/delivery-result.json exists.
  HELD: <reason>                   client_update_check.py for the week is not done.
  DELIVERED: <link>, WOULD DELIVER: ... (--dry-run) or REFUSED: <code> <reason>
        from comms-reply-to-email's email_deliver.py, run with delivery.json's draft_id, check
        (the email-checker's record), contact_id and email_ref. Every guard lives there: the
        check record must be a PASS for this exact draft content, addressed only to the pinned
        contact, answering the pinned email, past outbound-check. A delivery is written to
        work/delivery-result.json, never over an existing one; a dry run or a refusal writes
        nothing.

A re-run after a push that landed but whose result was lost (email_deliver.py left
delivery-intent.json beside the check record, and the draft now reads as already delivered)
is reported ALREADY, reconciled.

Exit 0 for every outcome above; 3 when the push failed; 2 on a bad argument, an unreadable
file, or a check or delivery that could not run.

    python3 client_update_deliver.py acme-weekly-update --week 2026-W40
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import _common as cu

CHECK = Path(__file__).resolve().parent / "client_update_check.py"
EMAIL_DELIVER = Path("~/.claude/skills/comms-reply-to-email/scripts/email_deliver.py").expanduser()
DELIVERY_FIELDS = ("draft_id", "check", "contact_id", "email_ref")


def delivery_spec(work):
    """delivery.json's four fields, or None when no draft was staged."""
    path = work / cu.DELIVERY_JSON
    if not path.is_file():
        return None
    data = cu.load_json(path, cu.DELIVERY_JSON)
    if not isinstance(data, dict):
        raise cu.Bad(f"{path} is not an object")
    missing = [k for k in DELIVERY_FIELDS if not str(data.get(k) or "").strip()]
    if missing:
        raise cu.Bad(f"{path} lacks {', '.join(missing)}")
    return {k: str(data[k]).strip() for k in DELIVERY_FIELDS}


def run_json(cmd, what, ok_codes):
    """Run a sibling command and return its JSON, or stop with exit 2."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        raise cu.Bad(f"{what} could not run: {type(exc).__name__}") from None
    if done.returncode not in ok_codes:
        lines = (done.stderr or done.stdout or "no output").strip().splitlines()
        raise cu.Bad(f"{what} exited {done.returncode}: {lines[-1] if lines else ''}")
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise cu.Bad(f"{what} did not print JSON") from None


def outcome_line(result) -> str:
    status = result.get("status")
    if status in ("delivered", "handoff_link"):
        link = result.get("web_link") or result.get("compose_url") or result.get("delivered_to") or "no link returned"
        extra = "" if status == "delivered" else f" (a compose link: {result.get('reason') or 'the draft stays in the Portal'})"
        return f"DELIVERED: {link}{extra}"
    if status in ("would_deliver", "would_handoff_link"):
        return (f"WOULD DELIVER: draft {result.get('draft_id')} to "
                f"{result.get('delivered_to') or 'the inbox that received the email'}"
                + (" as a compose link" if status == "would_handoff_link" else ""))
    refusals = result.get("refusals") or []
    if refusals:
        return f"REFUSED: {refusals[0].get('code')} {refusals[0].get('reason')}"
    return f"REFUSED: {str(status or 'unknown').upper()} {result.get('reason') or ''}".rstrip()


def deliver(engagement, week=None, week_dir=None, dry_run=False, config=None, contexts=None) -> dict:
    wk = cu.resolve(engagement, week, None, week_dir, contexts)
    rules = wk.engagement.rules
    out = {"engagement": wk.engagement.name, "week": wk.label, "week_dir": str(wk.week_dir), "dry_run": dry_run,
           "detail": []}
    keep = "FILE: the cover email stays a file in the week folder "
    if rules.variant == "deck":
        return dict(out, outcome="FILE", line=keep + "(a deck has no cover email to deliver)")
    if rules.email_delivery == "file":
        return dict(out, outcome="FILE", line=keep + "(the rules say file)")
    if len(rules.recipients) > 1:
        return dict(out, outcome="FILE", line=keep + f"({len(rules.recipients)} recipients; a pushed reply reaches only one)")
    spec = delivery_spec(wk.work)
    if spec is None:
        return dict(out, outcome="FILE", line=keep + "(no staged Portal draft)")
    result_path = wk.work / cu.DELIVERY_RESULT_JSON
    if result_path.exists():
        done = cu.load_json(result_path, cu.DELIVERY_RESULT_JSON)
        when = done.get("delivered_at") if isinstance(done, dict) else None
        return dict(out, outcome="ALREADY", line=f"ALREADY: delivered at {when or 'an unrecorded time'}")

    cmd = [sys.executable, str(CHECK), engagement, wk.label, "--week-dir", str(wk.week_dir), "--format", "json"]
    state = run_json(cmd + (["--contexts-dir", contexts] if cu.blank(contexts) else []), "client_update_check.py", (0,))
    if not state.get("done"):
        failing = [n for n, t in (state.get("tests") or {}).items() if t.get("state") == "fail"]
        return dict(out, outcome="HELD", line=f"HELD: client_update_check.py is not done (failing: {', '.join(failing)})")

    check_path = Path(spec["check"]).expanduser()
    if not check_path.is_absolute():
        check_path = wk.work / check_path
    had_intent = (check_path.parent / "delivery-intent.json").exists()
    cmd = [sys.executable, str(EMAIL_DELIVER), "--draft", spec["draft_id"], "--check", str(check_path),
           "--contact", spec["contact_id"], "--email", spec["email_ref"]]
    cmd += (["--dry-run"] if dry_run else []) + (["--config", config] if cu.blank(config) else [])
    result = run_json(cmd, "email_deliver.py", (0, 3))
    out.update(result=result, line=outcome_line(result))
    out["outcome"] = out["line"].split(":", 1)[0]
    reconciled = had_intent and result.get("status") == "refused" and any(
        r.get("code") == "ALREADY_DELIVERED" for r in result.get("refusals") or [] if isinstance(r, dict))
    if not dry_run and reconciled:
        result = out["result"] = {**result, "status": "delivered", "reconciled": True}
        out.update(outcome="ALREADY", line="ALREADY: delivered by an earlier run (reconciled from its intent record)")
    out["failed"] = result.get("status") == "push_failed"
    out["detail"] = [f"{r.get('code')} {r.get('reason')}" for r in (result.get("refusals") or [])[1:]]
    if not dry_run and result.get("status") in ("delivered", "handoff_link"):
        if result_path.exists():
            raise cu.Bad(f"refusing to overwrite {result_path}")
        result_path.write_text(json.dumps({**result, "delivered_at": cu.now_utc(), "week": wk.label}, indent=1,
                                          default=str) + "\n", encoding="utf-8")
        out["written"] = str(result_path)
    return out


def main():
    p = argparse.ArgumentParser(description="Put the week's checked cover email into the owner's Outlook Drafts; "
                                            "never sends.")
    p.add_argument("engagement", nargs="?", default="", help="a Context name or the path to a Context YAML file")
    p.add_argument("--week", default="", help="yyyy-Www or a yyyy-mm-dd date; blank: this week")
    p.add_argument("--week-dir", default="", help="use this folder as the week folder")
    p.add_argument("--dry-run", action="store_true", help="run every check, place nothing")
    p.add_argument("--config", default="", help="the MCP config holding the Portal (default: the setting)")
    p.add_argument("--contexts-dir", default="", help="where Context YAML files are found by name")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    args = p.parse_args()
    out = deliver(args.engagement, cu.blank(args.week), cu.blank(args.week_dir), args.dry_run, args.config,
                  args.contexts_dir)
    print(json.dumps(out, indent=1, default=str) if args.fmt == "json"
          else "\n".join([out["line"]] + [f"  {d}" for d in out["detail"]]))
    return 3 if out.get("failed") else 0


if __name__ == "__main__":
    cu.run_main(main)
