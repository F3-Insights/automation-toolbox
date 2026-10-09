#!/usr/bin/env python3
"""report-workorder: each week's report as a work order that can be resumed.

The state file <store>/workorder/<period>.json is the source of truth and is always written: the
period, the author and agent, the stage reached, the gate it is waiting at, the files produced so
far and a trail of what happened. Where the Insights Portal is in use the work order is also
mirrored as a task assigned to the agent, found or created by its source reference
`weekly-report:<author>:<period>`. The mirror is best effort: a Portal that cannot be reached,
or an agent slug that is not an active profile on the roster, is a finding in the output, never
a failure. --no-portal skips the mirror entirely.

Subcommands (all take --period YYYY-MM-DD and --store; the store is $REPORT_STORE_DIR without it):
  open    open the period's work order (--author and --agent slugs; --title, --domain, --due)
  stage   record the stage reached (--stage, --note, --file repeatable); clears a pending gate
  wait    put the run at a gate (--gate gate1|gate2|gate3|questions, --questions N, --note)
  resume  where the run stopped and what comes next, from the file alone
  close   close it as done on the files it produced (--file repeatable); refused (exit 3) with no file
  show    the work order as it stands

The stages, in order: collect, organize, continuity, leadership-test, gate1, gate2, questions,
write, verify, gate3, deliver, record. Prints JSON; findings also go to standard error.
Exit 0 ok, 2 error, 3 refused.

Example:
  python3 report_workorder.py open --period 2027-11-12 --author finance --agent weekly-reporter --store ~/reports/finance
"""

import argparse
import re
import sys

from _common import FAILED, OK, Fail, check_period, emit, json_or_none, now_utc, run_main, safe, store_dir, write_json

STAGES = ("collect", "organize", "continuity", "leadership-test", "gate1", "gate2", "questions", "write",
          "verify", "gate3", "deliver", "record")
GATES = ("gate1", "gate2", "gate3", "questions")
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def state_path(store, period):
    return store_dir(store) / "workorder" / f"{check_period(period)}.json"


def load(store, period, must=True):
    path = state_path(store, period)
    if not path.is_file():
        if must:
            raise Fail(f"no work order for {period} in {path.parent}; run `open` first")
        return None
    found = json_or_none(path)
    if not isinstance(found, dict):
        raise Fail(f"{path} could not be read; it is the source of truth, so move it aside and open the period again")
    return found


def save(state, store):
    state["updated_at"] = now_utc()
    return write_json(state_path(store, state["period"]), state)


def trail(state, action, detail):
    state.setdefault("trail", []).append({"at": now_utc(), "action": action, "detail": detail})


def next_step(state):
    """What comes next, derived from the file so it cannot go stale."""
    if state.get("closed_at"):
        return "the work order is closed; nothing comes next for this period"
    gate = state.get("gate") or {}
    if gate.get("name"):
        count = gate.get("questions")
        return (f"the run is waiting at {gate['name']} with "
                f"{count if count is not None else 'an unrecorded number of'} question(s) outstanding; put them "
                f"to the author, then record the next stage")
    stage = state.get("stage")
    if not stage:
        return f"no stage has been recorded; begin at {STAGES[0]!r}"
    at = STAGES.index(stage)
    return (f"{stage!r} is the last stage, so the work order is ready to close" if at + 1 == len(STAGES)
            else f"{stage!r} is done; the next stage is {STAGES[at + 1]!r}")


def mirror(state, portal, status, headline, body):
    """Put the status on the task and a note on the trail, best effort. The assignees are never
    resent after open, because an update replaces them."""
    if portal is None or not state.get("task_id"):
        why = state["portal"].get("reason") or "the work order carries no task id"
        return [f"the Portal was not used: {why}. The work order was still written"]
    try:
        portal.call("update_task", {"id": state["task_id"], "status": status})
    except Fail as exc:
        state["portal"] = {"in_use": False, "reason": f"update_task failed: {exc}", "checked_at": now_utc()}
        return [f"the task was not updated ({exc}); the work order was still written"]
    state["task_status"] = status
    try:
        portal.call("create_activity", {"activity_type": "note", "title": headline, "description": body})
    except Fail as exc:
        return [f"the task reads {status} but the trail note was not written ({exc})"]
    return []


def open_on_portal(state, portal, args):
    """Check the agent is on the roster, then find this period's task or create it."""
    try:
        roster = portal.call("list_agent_profiles", {})
        rows = roster.get("profiles") if isinstance(roster, dict) else roster
        active = {str(r.get("slug")).casefold() for r in rows or [] if isinstance(r, dict) and r.get("is_active", True)}
        if state["agent"] not in active:
            raise Fail(f"{state['agent']!r} is not an active agent profile on the roster, and an assignee the "
                       f"Portal cannot resolve fails the whole call")
        tasks, _ = portal.page("task", {"assigned_agent": state["agent"], "include_completed": True})
        found = next((t for t in tasks if t.get("source_reference") == state["source_reference"]), None)
        if found:
            state["task_id"] = str(found.get("id"))
        else:
            payload = {"title": state["title"], "source_reference": state["source_reference"],
                       "assignees": [state["agent"]],
                       "description": f"Weekly report for {state['period']}, author {state['author']}. The work "
                                      f"order file is the source of truth for resuming; this task mirrors it."}
            payload.update({k: v for k, v in (("domain_id_or_name", args.domain), ("due_date", args.due)) if v})
            made = portal.call("create_task", payload)
            ident = (made or {}).get("id") or ((made or {}).get("task") or {}).get("id")
            if not ident:
                raise Fail("create_task returned no task id")
            state["task_id"] = str(ident)
    except Fail as exc:
        state["portal"] = {"in_use": False, "reason": str(exc), "checked_at": now_utc()}
        return [f"the task was not created or found ({exc}); the work order was still written"]
    state["portal"] = {"in_use": True, "reason": None, "checked_at": now_utc()}
    return mirror(state, portal, "IN_PROGRESS", f"Weekly report {state['period']}: work order open",
                  f"The work order for {state['period']} is open and assigned to {state['agent']}.") \
        + ([] if not found else ["this period already had a task; it was reused rather than duplicated"])


def main():
    parser = argparse.ArgumentParser(description="Each week's report as a resumable work order.")
    sub = parser.add_subparsers(dest="action", required=True)
    commands = {name: sub.add_parser(name) for name in ("open", "stage", "wait", "resume", "close", "show")}
    for name, one in commands.items():
        one.add_argument("--period", required=True)
        one.add_argument("--store", default="")
        if name in ("open", "stage", "wait", "close"):
            one.add_argument("--no-portal", action="store_true", help="keep the work order on disk only")
    commands["open"].add_argument("--author", required=True, help="the author slug")
    commands["open"].add_argument("--agent", required=True, help="the agent profile slug the task is assigned to")
    commands["open"].add_argument("--title", default="")
    commands["open"].add_argument("--domain", default="", help="the Portal domain to file the task under")
    commands["open"].add_argument("--due", default="", help="the task's due date")
    commands["stage"].add_argument("--stage", required=True, choices=STAGES)
    commands["wait"].add_argument("--gate", required=True, choices=GATES)
    commands["wait"].add_argument("--questions", type=int, default=None)
    for name in ("stage", "wait", "close"):
        commands[name].add_argument("--note", default="")
    for name in ("stage", "close"):
        commands[name].add_argument("--file", action="append", default=[], dest="files")
    args = parser.parse_args()

    period = check_period(args.period)
    if args.action in ("resume", "show"):
        state = load(args.store, period)
        out = dict(state, action=args.action, workorder=str(state_path(args.store, period)), next=next_step(state))
        if args.action == "resume":
            gate = state.get("gate") or {}
            out["stopped_at"] = ("the run is closed" if state.get("closed_at") else f"the gate {gate['name']}"
                                 if gate.get("name") else f"the stage {state.get('stage')!r}" if state.get("stage")
                                 else "nothing has run yet")
        emit(out)
        return OK

    portal, reason = None, "--no-portal was passed, so the work order was kept on disk only"
    if not args.no_portal:
        try:
            from _portal import Portal
            portal, reason = Portal(), None
        except Fail as exc:
            reason = str(exc)

    findings = []
    if args.action == "open":
        author, agent = args.author.strip().casefold(), args.agent.strip().casefold()
        for value, what in ((author, "author"), (agent, "agent")):
            if not SLUG.match(value):
                raise Fail(f"--{what} {value!r} is not a slug: lower-case letters, digits, '.', '_' or '-'")
        reference = f"weekly-report:{author}:{period}"
        state = load(args.store, period, must=False)
        reopened = state is not None
        if state and state.get("source_reference") != reference:
            raise Fail(f"the work order for {period} belongs to {state.get('source_reference')!r}; one period is one "
                       f"work order, so use another store for another author or agent", FAILED)
        title = " ".join((args.title or f"Weekly report {period}, {author}").split())
        if len(title) > 100:
            cut = title[:100]
            title = (cut[:cut.rfind(" ")] if cut.rfind(" ") >= 50 else cut).rstrip(" ,;:-")
            findings.append(f"the title was cut to the Portal's 100 characters: {title!r}")
        state = state or {"schema": "report-workorder/1", "period": period, "source_reference": reference,
                          "author": author, "agent": agent, "stage": None, "gate": None, "files": [], "task_id": None,
                          "task_status": None, "opened_at": now_utc(), "closed_at": None, "trail": []}
        state.update(title=title, closed_at=None, portal={"in_use": False, "reason": reason, "checked_at": now_utc()})
        findings += open_on_portal(state, portal, args) if portal else [
            f"the Portal was not used: {reason}. The work order was still written and resume reads it"]
        trail(state, "open", f"work order {'reopened' if reopened else 'opened'} for {period}")
        result = {"reopened": reopened, "task_id": state.get("task_id"), "portal": state["portal"]}
    else:
        state = load(args.store, period)
        if portal is None:
            state["portal"] = {"in_use": False, "reason": reason, "checked_at": now_utc()}
        files = [f for f in getattr(args, "files", []) if f.strip() and f not in state["files"]]
        state["files"] += files
        if args.action == "stage":
            was_waiting = bool((state.get("gate") or {}).get("name"))
            state.update(stage=args.stage, stage_note=args.note or None, gate=None)
            findings += mirror(state, portal, "IN_PROGRESS", f"Weekly report {period}: {args.stage}",
                               f"The weekly report for {period} reached the stage {args.stage!r}. {args.note}".strip())
            trail(state, "stage", f"reached {args.stage}" + (f"; {args.note}" if args.note else ""))
            result = {"stage": args.stage, "gate_cleared": was_waiting, "files_added": files}
        elif args.action == "wait":
            if args.questions is not None and args.questions < 0:
                raise Fail("--questions cannot be negative")
            state["gate"] = {"name": args.gate, "questions": args.questions, "note": args.note or None,
                             "since": now_utc()}
            findings += mirror(state, portal, "WAITING", f"Weekly report {period}: waiting at {args.gate}",
                               f"The weekly report for {period} is waiting at {args.gate}.")
            trail(state, "wait", f"waiting at {args.gate}")
            result = {"gate": state["gate"]}
        else:
            if not state["files"]:
                raise Fail(f"the work order for {period} names no file to close it on; pass --file with the rendered "
                           f"report", FAILED)
            state.update(gate=None, stage=state.get("stage") or "record", closed_at=now_utc())
            findings += mirror(state, portal, "DONE", f"Weekly report {period}: done",
                               "Files produced:\n" + "\n".join(f"- {f}" for f in state["files"]))
            trail(state, "close", f"closed on {len(state['files'])} file(s)")
            result = {"files_added": files, "closed_at": state["closed_at"]}
    path = save(state, args.store)
    emit({"action": args.action, "workorder": str(path), "period": period, **result, "files": state["files"],
          "task_status": state.get("task_status"), "next": next_step(state), "findings": findings})
    for finding in findings:
        print(safe(f"finding: {finding}"), file=sys.stderr)
    return OK


if __name__ == "__main__":
    run_main(main)
