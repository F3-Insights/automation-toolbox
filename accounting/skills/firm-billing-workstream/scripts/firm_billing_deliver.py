#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Place each reviewed invoice's cover email in the owner's mail Drafts folder, where BILLING.yaml
allows it and a reply thread is staged. Never sends anything.

    python3 firm_billing_deliver.py FOLDER --period P [--period-dir DIR] [--dry-run] [--config F] [--format text|json]

The Automation's finish step. One line per drafted contract whose review is PASS, in evidence-file
order:

- FILE: its email_delivery is "file", or there is no work/delivery-<contract>.json (no staged
  Portal draft); the invoice and cover email stay files.
- ALREADY: work/delivery-result-<contract>.json exists.
- HELD: firm_billing_check.py for the period is not done (the open tests are named).
- Otherwise the comms-reply-to-email skill's email_deliver.py runs with the staged draft_id, check,
  contact_id and email_ref. It only places a reply to the pinned email in the Drafts folder and
  refuses on any failed guard: DELIVERED <link>, WOULD DELIVER (--dry-run) or REFUSED <code> <reason>.

A delivery is recorded in work/delivery-result-<contract>.json, never over an existing one. Before
each push it writes work/delivery-intent-<contract>.json; a re-run that finds the draft already
delivered after such a record writes the missing result ("ALREADY ... reconciled"). With nothing
drafted and reviewed it prints "NONE: ...". --config names the MCP config holding the Portal
server; without it email_deliver.py uses its own setting.

Exit 0 for every outcome above; 3 when a push failed; 2 on a bad argument, an unreadable file or
a Portal that cannot be reached.

Example:
    python3 firm_billing_deliver.py ~/Billing --period 2026-09 --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import _common as c

EMAIL_DELIVER = Path("~/.claude/skills/comms-reply-to-email/scripts/email_deliver.py").expanduser()
CHECK = Path(__file__).resolve().parent / "firm_billing_check.py"
DELIVERY_FIELDS = ("draft_id", "check", "contact_id", "email_ref")
SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text: str) -> str:
    """Redact anything token-shaped on its way to the screen."""
    return SECRETS.sub("[redacted]", text)


def delivery_spec(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = c.load_json(path, path.name)
    if not isinstance(data, dict):
        raise c.Bad(f"{path} is not an object")
    missing = [k for k in DELIVERY_FIELDS if not str(data.get(k) or "").strip()]
    if missing:
        raise c.Bad(f"{path} lacks {', '.join(missing)}")
    return {k: str(data[k]).strip() for k in DELIVERY_FIELDS}


def run_json(cmd: list[str], what: str) -> dict:
    """Run a sibling or another skill's script and parse the one JSON object it prints."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise c.Bad(f"{what} failed: {safe((proc.stderr or proc.stdout).strip()[:300])}") from None
    if not isinstance(out, dict) or out.get("status") == "error":
        raise c.Bad(f"{what} failed: {safe(str(out.get('reason') if isinstance(out, dict) else out))}")
    return out


def outcome_line(cid: str, result: dict) -> str:
    status = result.get("status")
    if status in ("delivered", "handoff_link"):
        link = result.get("web_link") or result.get("compose_url") or result.get("delivered_to") or "no link returned"
        extra = "" if status == "delivered" else f" (a compose link: {result.get('reason') or 'the draft stays in the Portal'})"
        return f"DELIVERED: {cid} {link}{extra}"
    if status in ("would_deliver", "would_handoff_link"):
        return (f"WOULD DELIVER: {cid} draft {result.get('draft_id')} to "
                f"{result.get('delivered_to') or 'the inbox that received the email'}"
                + (" as a compose link" if status == "would_handoff_link" else ""))
    refusals = result.get("refusals") or []
    if refusals:
        return f"REFUSED: {cid} {refusals[0].get('code')} {refusals[0].get('reason')}"
    return f"REFUSED: {cid} {str(status or 'unknown').upper()} {result.get('reason') or ''}".rstrip()


def deliver(folder, period=None, given_dir=None, dry_run=False, config=None, email_deliver=EMAIL_DELIVER) -> dict:
    root = c.billing_folder(folder)
    per, _ = c.resolve_period(period)
    pdir = c.period_dir(root, per, given_dir)
    billing = c.billing_or_bad(root)
    rows = [r for r in c.evidence_rows(c.evidence_path(pdir, per))
            if r.get("state") == "drafted" and r.get("review") == "PASS"]
    out = {"period": per, "period_dir": str(pdir), "dry_run": dry_run, "contracts": []}
    if not rows:
        out["lines"] = [f"NONE: no drafted, reviewed contract for {per}"]
        return out
    state = None
    for row in rows:
        cid = row["id"]
        item = {"id": cid}
        out["contracts"].append(item)
        contract = billing.contract(cid)
        if contract is None:
            item.update(outcome="HELD", line=f"HELD: {cid} is not a contract in BILLING.yaml")
            continue
        if contract["email_delivery"] == "file":
            item.update(outcome="FILE", line=f"FILE: {cid} the invoice and cover email stay files (BILLING.yaml says file)")
            continue
        spec = delivery_spec(pdir / "work" / f"delivery-{cid}.json")
        if spec is None:
            item.update(outcome="FILE", line=f"FILE: {cid} the invoice and cover email stay files (no staged Portal draft)")
            continue
        result_path = pdir / "work" / f"delivery-result-{cid}.json"
        intent_path = pdir / "work" / f"delivery-intent-{cid}.json"
        if result_path.exists():
            done = c.load_json(result_path, result_path.name)
            when = done.get("delivered_at") if isinstance(done, dict) else None
            item.update(outcome="ALREADY", line=f"ALREADY: {cid} delivered at {when or 'an unrecorded time'}")
            continue
        if state is None:   # the check runs once, and only when something could be delivered
            cmd = [sys.executable, str(CHECK), str(root), "--period", per, "--format", "json"]
            state = run_json(cmd + (["--period-dir", str(pdir)] if c.blank(given_dir) else []), "firm-billing-check")
            state["status"] = "ok"
        if not state.get("done"):
            failing = [n for n, t in state["tests"].items() if not t["met"]]
            item.update(outcome="HELD", line=f"HELD: {cid} firm-billing-check is not done (open: {', '.join(failing)})")
            continue
        if not Path(email_deliver).is_file():
            raise c.Bad(f"email_deliver.py is not installed at {email_deliver} (the comms-reply-to-email skill)")
        had_intent = intent_path.exists()
        if not dry_run:   # the intent record, before the external write
            intent_path.parent.mkdir(parents=True, exist_ok=True)
            intent_path.write_text(c.dump_json({"draft_id": spec["draft_id"], "started_at": c.now_utc(),
                                                "contract": cid, "period": per}), encoding="utf-8")
        cmd = [sys.executable, str(email_deliver), "--draft", spec["draft_id"], "--check", spec["check"],
               "--contact", spec["contact_id"], "--email", spec["email_ref"]]
        cmd += (["--dry-run"] if dry_run else []) + (["--config", c.blank(config)] if c.blank(config) else [])
        result = run_json(cmd, "email_deliver.py (the Portal could not be reached?)")
        line = outcome_line(cid, result)
        item.update(result=result, line=line, outcome=line.split(":", 1)[0])
        already = any(isinstance(r, dict) and r.get("code") == "ALREADY_DELIVERED" for r in result.get("refusals") or [])
        if not dry_run and had_intent and result.get("status") == "refused" and already:
            result = {**result, "status": "delivered", "reconciled": True}
            item.update(result=result, outcome="ALREADY",
                        line=f"ALREADY: {cid} delivered by an earlier run (reconciled from its intent record)")
        if result.get("status") == "push_failed":
            item["failed"] = True
        if not dry_run and result.get("status") in ("delivered", "handoff_link"):
            with result_path.open("x", encoding="utf-8") as fh:   # "x": never over an existing result
                fh.write(c.dump_json({**result, "delivered_at": c.now_utc(), "contract": cid, "period": per}))
            item["written"] = str(result_path)
    out["lines"] = [i["line"] for i in out["contracts"]]
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="firm-billing-deliver", description="Place reviewed invoices' cover emails in Drafts; never sends.")
    p.add_argument("folder", nargs="?", default="", help="the firm's billing folder, with BILLING.yaml")
    p.add_argument("--period", default="", help="the month billed (yyyy-mm); blank: the month before today")
    p.add_argument("--period-dir", default="", help="use this folder as the period folder")
    p.add_argument("--dry-run", action="store_true", help="run every check, place nothing")
    p.add_argument("--config", default="", help="the MCP config holding the Portal server")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        out = deliver(a.folder, a.period, a.period_dir, a.dry_run, a.config)
    except c.Bad as exc:
        print(safe(f"ERROR {exc}"), file=sys.stderr)
        return 2
    print(safe(json.dumps(out, indent=1, default=str) if a.format == "json" else "\n".join(out["lines"])))
    return 3 if any(i.get("failed") for i in out["contracts"]) else 0


if __name__ == "__main__":
    sys.exit(main())
