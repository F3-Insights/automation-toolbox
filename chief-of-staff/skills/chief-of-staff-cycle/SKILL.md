---
name: chief-of-staff-cycle
description: One unattended chief-of-staff cycle. A decider reads the owner's own documents, the Insights Portal, the orchestrator fleet and the task stack's score, and picks the day's priorities, at most two off-schedule orchestrator launches (behind the owner's switch) and at most two doers from the owner's registry; one small improvement may be proposed or committed on a branch; one verified receipt note and any genuine decision tasks go to the Portal and the owner gets the link. Never asks the owner and never sends to anyone else. Use when a person or a runtime starts a chief-of-staff cycle. Not for an interactive request (chief-of-staff agent).
argument-hint: "[date YYYY-MM-DD] [dry run] [trigger_items JSON]"
---

# The chief-of-staff cycle

One cycle is decide, execute, receipt. The chief of staff decides what runs, launches or dispatches it, evaluates and improves the machinery, and reports; it never does a doer's or an orchestrator's work itself. Its unit of work is more and more an orchestrator: a registered one, launched as its own Run when something its schedule cannot see calls for it (a stall, an event, a priority shift). The in-cycle doers remain for what no orchestrator does yet. This skill is the orchestrator: run it in the main session or as the `chief-of-staff-cycle-orchestrator` agent, because it dispatches the workers. It never stops to ask the owner: what only they can decide becomes a `[<display name>]` task in the Portal and a line in the receipt. The routing front door for interactive work is the separate `chief-of-staff` agent; this is the scheduled cycle.

The commands are scripts in this skill's `scripts/` folder, each printing one JSON object (`rules.md` has the exit codes and folders). `S` below stands for `python3 ~/.claude/skills/chief-of-staff-cycle/scripts`:

```bash
S/chief_of_staff_cycle.py start [--date D] [--dry-run] [--trigger-items -]
S/chief_of_staff_fleet.py snapshot CYCLE          # fleet status, the task stack, what may be launched
S/chief_of_staff_decide_check.py CYCLE            # the registry check; writes decision.json
S/chief_of_staff_fleet.py launch CYCLE NAME       # one accepted launch, through orchestrator-fleet's fleet_launch.py
S/chief_of_staff_produce_work.py pack TARGET --cycle CYCLE
S/chief_of_staff_produce_work.py save TARGET --cycle CYCLE --fingerprint F --result FILE
S/chief_of_staff_cycle.py record CYCLE --doer D --args A --status S --outcome "..."
S/chief_of_staff_improve.py check CYCLE           # may the one improvement be committed, or proposed
S/chief_of_staff_improve.py apply CYCLE --result FILE
S/chief_of_staff_receipt.py read CYCLE            # today's receipt note so far
S/chief_of_staff_receipt.py publish CYCLE         # the note and the decision tasks, by marker
S/chief_of_staff_records.py apply CYCLE           # roster health, one ledger line, one draft principle
S/chief_of_staff_receipt.py verify CYCLE          # the note in the Portal, the decisions raised
S/chief_of_staff_notify.py CYCLE --kind decision|receipt
S/chief_of_staff_cycle.py finish CYCLE --status ok|failed
```

`cos_watch.py --since=CURSOR` is not a step of the cycle: it is the check a runtime's Monitor runs to decide whether a cycle is worth starting (`rules.md`, "Starting a cycle").

`CYCLE` is the folder `start` prints as `folder`. `rules.md` beside this file holds the owner's settings (the documents the decider reads, the doer registry, the switches, the caps, the receipt's shape) and the mechanics. The briefs are `briefs/decider.md`, `briefs/producer.md`, `briefs/doer.md` (for every skill or agent doer), `briefs/improver.md` and `briefs/receipt-writer.md`. The owner's documents are private: workers read them and reason from them, and nothing from them is copied into the Portal, a task, a commit message or this run's report.

## Steps

1. [script] Run `chief_of_staff_cycle.py start` with `--date` when the request names one, `--dry-run` in a dry run, and, when the request carries `trigger_items` (the JSON list of `{key, summary}` a runtime's Monitor passes when a change woke this cycle), the list written exactly as given to `trigger-items.json` in the run's own folder and passed as `--trigger-items @<that file's path>` (a runtime session may not pipe or redirect, so never `-` there; in a terminal `-` reads stdin). It makes the cycle folder, copies the owner's doer registry and the paths of their documents into `cycle.json`, keeps the trigger items in `cycle.json` for the decider, and says whether Monday's week in review is still due. Keep `folder` as CYCLE.
   → `ok`: step 2
   → the command could not run: stop
2. [script] Run `chief_of_staff_fleet.py snapshot CYCLE`. It reads orchestrator-fleet's `fleet_status.py --format json` (each registered orchestrator's status, last Run, what is live or queued, Runs waiting on the owner, its check's headline) and task-stack-workstream's `task_stack_check.py --precheck`, and writes `CYCLE/fleet.json`: those, the owner's launch switch, today's launches and what is left of the backstop, and which orchestrators this cycle may launch, live or as a dry run. It only reads, so it runs in a dry run too.
   → `ok`: step 3
   → the command could not run: step 3
3. [hand-off: chief-of-staff-decider] Dispatch the decider with `briefs/decider.md` and the path of `CYCLE/cycle.json`. It reads the owner's documents, the health probe and the Portal, and returns one JSON decision object. Save its reply verbatim as `CYCLE/decide-raw.txt`.
   → a reply: step 4
   → BLOCKED or no reply: step 4
4. [script] Run `chief_of_staff_decide_check.py CYCLE`. Only doers in the owner's registry with arguments that match their pattern are accepted, at most two, and at most one improvement to a registry doer skill's SKILL.md. Launches are checked against `CYCLE/fleet.json`: the switch on, an orchestrator the snapshot lists as launchable, an off-schedule trigger, params that match the registry, nothing live or queued, nothing that succeeded today without new evidence. The runner decides concurrency; the owner's daily backstop (default 12) is the only total. Every rejection is named.
   → `ok`: step 5
   → `parse_failed` or `empty`: step 16
   → the command could not run: step 16
5. [judgment] Take the next accepted launch in `CYCLE/decision.json` (`launches`) whose `launch:<orchestrator>` row is not yet in `CYCLE/execution.json`.
   → none left: step 7
   → one: step 6
6. [script] Run `chief_of_staff_fleet.py launch CYCLE <orchestrator>`. It launches through `fleet_launch.py <orchestrator> --authority propose --cap <backstop>`, as a dry run where the registry says so, with the params the check accepted, and records the launch and why in `execution.json`. In a dry-run cycle it records `would launch` and runs nothing. A launch only enqueues a Run; the orchestrator runs as its own session, and its result reaches a later cycle through the fleet status.
   → `launched`: step 5
   → `would_launch`: step 5
   → `refused` or `failed`: step 5
   → the command could not run: step 5
7. [judgment] Take the next accepted dispatch in `CYCLE/decision.json` that is not yet in `CYCLE/execution.json`. In a dry run, record each one with `chief_of_staff_cycle.py record ... --status dry-run --outcome "would dispatch"` and dispatch nothing.
   → none left: step 13
   → route `produce`: step 8
   → route `skill`: step 11
   → route `agent`: step 12
8. [script] Run `chief_of_staff_produce_work.py pack TARGET --cycle CYCLE` (TARGET is the dispatch's args). When it does not answer `ok`, record its `outcome` with `chief_of_staff_cycle.py record` (status `already_prepared`, `held` or `failed`; `dry-run` for `would_pack`) and go back.
   → `ok`: step 9
   → `already_prepared`: step 7
   → `held`: step 7
   → `would_pack`: step 7
   → the command could not run: step 7
9. [hand-off: chief-of-staff-producer] Dispatch the producer with `briefs/producer.md` and the `packet` path from step 8. It has no Portal tools and returns one JSON object; save its reply verbatim as `CYCLE/produce-N.txt` (N is the dispatch's number).
   → a reply: step 10
   → no reply: step 7
10. [script] Run `chief_of_staff_produce_work.py save TARGET --cycle CYCLE --fingerprint F --result CYCLE/produce-N.txt`, then `chief_of_staff_cycle.py record` with its status and `outcome`, and its `local_path` as `--local-path` (that path stays out of the receipt). On no reply at step 9, record `failed` instead.
   → `prepared`, `blocked` or `already_prepared`: step 7
   → `invalid`: step 7
   → `would_save`: step 7
   → the command could not run: step 7
11. [hand-off: the dispatch's worker] Dispatch the agent the dispatch names as `worker` (a doer agent such as `chief-of-staff-readonly-doer` or `chief-of-staff-meeting-prep-doer`) with `briefs/doer.md`, the dispatch's `skill`, `args` and `reason`. It runs that skill headless and returns at most twelve lines, findings first. Record the result with `chief_of_staff_cycle.py record` (status `dispatched` with its first line as the outcome, or `failed` with why).
   → a result: step 7
   → BLOCKED or no result: step 7
12. [hand-off: the dispatch's worker] Dispatch the agent the dispatch names as `worker` directly (a worker agent the owner's registry lists, such as `person-researcher`) with `briefs/doer.md`, the dispatch's `args` and `reason`. Record the result as in step 11.
   → a result: step 7
   → BLOCKED or no result: step 7
13. [script] Run `chief_of_staff_improve.py check CYCLE`. In a dry run it answers `would_apply` and nothing is edited; under `improvements = "propose"` (the default), or with no `improve_repo` set, it answers `proposed` and the receipt files the change as a decision.
   → `ok`: step 14
   → `would_apply`: step 16
   → `proposed`: step 16
   → `none`: step 16
   → `refused`: step 16
   → the command could not run: step 16
14. [hand-off: chief-of-staff-improver] Dispatch the improver with `briefs/improver.md` and the `target`, `path`, `change` and `rationale` from the check. It reads that one file and returns one JSON object: the exact old text and its replacement with an `APPLIED: ...` line, or a `SKIPPED: ...` line. Save its reply verbatim as `CYCLE/improve-reply.txt`.
   → a reply: step 15
   → no reply: step 16
15. [script] Run `chief_of_staff_improve.py apply CYCLE --result CYCLE/improve-reply.txt`. It makes the one edit in code, in the improvement worktree on the owner's improvement branch, only when the reply says APPLIED, the old text is in the file exactly once, the file has not changed since the check and the edit is at most 30 lines; then it commits that one file on the branch. The owner's own checkout is never touched and nothing is pushed.
   → `committed`, `not_applied`, `unchanged` or `refused`: step 16
   → `would_commit`: step 16
   → the command could not run: step 16
16. [script] Run `chief_of_staff_receipt.py read CYCLE`: whether today's receipt note exists, and its text.
   → `found` or `absent`: step 17
   → the command could not run: step 17
17. [hand-off: chief-of-staff-receipt-writer] Dispatch the receipt writer with `briefs/receipt-writer.md` and the cycle folder's path; it reads `cycle.json`, `decision.json`, `execution.json`, `fleet.json`, `improve.json` and `receipt-read.json` there. On a second round, add the refusals from step 18. Save its reply verbatim as `CYCLE/receipt.json`.
   → a reply: step 18
   → no reply: step 20
18. [script] Run `chief_of_staff_receipt.py publish CYCLE` (with `--dry-run` in a dry run). It writes this cycle's text into the one daily note, creates the decision tasks within the day's ceiling (a proposed improvement among them), reuses any already open, and reads the note back.
   → `published` or `dry_run`: step 19
   → `unverified`: step 19
   → `refused` because `F3I_TOOLBOX_DRY_RUN` is set (a dry runner, nothing written; treat as `dry_run`): step 19
   → `refused`: step 17 (max 1)
   → `refused` after the last round: step 20
   → the command could not run: step 20
19. [script] Run `chief_of_staff_records.py apply CYCLE` (with `--dry-run` in a dry run): the Health cells of the doers dispatched this cycle in the owner's doer roster, one event-ledger line, one draft principle in the principles inbox, each only when the writer proposed it and its setting names the file.
   → `applied` or `dry_run`: step 20
   → `refused` because `F3I_TOOLBOX_DRY_RUN` is set (treat as `dry_run`): step 20
   → the command could not run: step 20
20. [script] Run `chief_of_staff_receipt.py verify CYCLE`. The Portal holding the note is the evidence; the writer saying so is a claim.
   → `found`: step 21
   → `missing` or `unverified`: step 22
   → the command could not run: step 22
21. [script] Run `chief_of_staff_notify.py CYCLE --kind decision`, then `chief_of_staff_notify.py CYCLE --kind receipt`. Neither ever fails the cycle.
   → `sent`, `held`, `skipped`, `not_sent` or `dry_run`: step 22
   → the command could not run: step 22
22. [script] Run `chief_of_staff_cycle.py finish CYCLE --status ok`, or `--status failed --reason "..."` when the cycle could not do its work (no decision could be read and no receipt could be written). Its `receipt` answer is `verified` only when this cycle's own block is in the receipt note (`verify.json` `this_cycle_written` true; the day's note alone is not enough, since a later cycle whose append was refused still finds the morning's note); anything less is answered as RECEIPT-FAILED with why. A cycle already finished answers `already_finished`.
   → `finished`: step 23
   → `already_finished`: step 23
   → the command could not run: step 23
23. [judgment] Write `CYCLE/report.md`: the priorities, each launch and its answer, each dispatch and its outcome (private artifact paths are fine here, never in the receipt), the skipped dispatches with their reasons, the improvement result, the receipt note and the decision tasks with their ids, what was sent to the owner, and anything that failed. Then finish with the block under "Finishing".
   → the report written: done

**One dispatch is one unit of work.** A doer that fails, times out or returns nothing is recorded for that dispatch and the cycle moves to the next; a failed improvement goes to the receipt. A launch is one unit too: refused or failed, it is recorded and the cycle moves on. Only a cycle that cannot start ends early. Before you act on a branch, read the evidence the command gave; a result no branch names is recorded with its evidence and the cycle carries on, never guessed at.

**Nothing waits on the owner.** A decision only they can make is a `decisions_needed` entry, which the writer turns into an `[<display name>]` task (at most three a day across all cycles) and a line in the receipt. Never end with a question to the session.

**Dry run.** When the request asks for a dry run (a runner says `Dry run: True`), pass `--dry-run` to `start`; every later command reads it from `cycle.json`, and the commands that take `--dry-run` get it too. The decider and the receipt writer run, so the judgment is exercised; no orchestrator is launched (`launch` records `would launch`), no doer, producer or improver is dispatched, nothing is written to the Portal or the owner's records, nothing is committed and nothing is sent. The commands enforce this from `cycle.json`, not from the flag.

## Finishing

The last message of a run is one fenced JSON block:

```json
{"status": "done", "cycle_id": "2030-03-04/061502", "date": "2030-03-04",
 "dry_run": false,
 "launches": [{"orchestrator": "task-reconcile-orchestrator", "mode": "dry-run", "status": "launched",
               "why": "stall: no Run in three days while the stack scores WORK"}],
 "dispatches": [{"doer": "produce-work", "args": "task:...", "status": "prepared",
                 "outcome": "prepared: private review-ready draft"}],
 "skipped": [{"name": "relationship-check", "reason": "retired: ..."}],
 "improvement": "none: no improvement proposed inside the improvement surface",
 "receipt": {"note_id": "...", "verified": true, "action": "created"},
 "decisions": [{"task_id": "...", "title": "[<display name>] Choose the Fabrikam renewal terms", "action": "created"}],
 "open_decisions": [{"task_id": "...", "title": "[<display name>] Choose the Fabrikam renewal terms"}],
 "notified": {"decision": "sent", "receipt": "sent"},
 "report": "CYCLE/report.md"}
```

`launches` is every `launch:` row of `execution.json`; a launch queues a Run and nothing more, so its result is a later cycle's fleet status, never this one's claim.

or, when the cycle could not start or could not finish:

```json
{"status": "stopped", "reason": "start could not run: the state folder is not writable.",
 "cycle_id": "", "launches": [], "dispatches": [], "skipped": [], "decisions": [], "open_decisions": [], "report": ""}
```

`decisions` lists every `[<display name>]` task this cycle created or reused, from `publish.json`; `open_decisions` is every `[<display name>]` task still open, from `verify.json`, which is what waits on the owner; `receipt.verified` is `verify.json`'s answer, never the writer's claim.

## When no one is present

The steps are the same, and nothing waits on a person: decisions go to the Portal as tasks and to the receipt, never to the session. Nothing that is the owner's decision is guessed.
