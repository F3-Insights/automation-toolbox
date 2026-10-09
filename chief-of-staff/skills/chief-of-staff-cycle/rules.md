# Settings and mechanics for chief-of-staff-cycle

The first half is what the owner sets, in the owner settings file (`~/.config/f3i-toolbox/settings.toml`, table `[chief-of-staff-cycle]`; a key not there is read from the top level). The second half is how the steps run. Where a script enforces a setting, the number here is the script's default.

## The owner's settings

**Starting a cycle.** What starts a cycle, and when, is outside this toolbox: a person, or a runtime's scheduler. The cycle works the same either way, and more than one cycle may run in a day. A runtime that starts a cycle when something changes runs `scripts/cos_watch.py` as its check (a runtime's file or schedule monitor, for example): it reports, in code, a task newly overdue or due today, new VIP mail, and a meeting new to the calendar inside the next 24 hours, and keeps no state, its cursor carrying what it saw. The runtime passes the items to the cycle as `trigger_items`, and `start --trigger-items` keeps them in `cycle.json` for the decider. How often the check runs, its hours, the gap between cycles and the daily cap are the runtime's.

**What the decider reads.** Each is a file or folder the owner keeps outside this repository, named by a setting. None has a default; a missing one is named in `cycle.json`'s `notes`, and the decider carries on without it.

| What | Setting | Flag on `start` |
|---|---|---|
| The chief of staff's charter: its role, authority and limits | `charter` | |
| The owner's profile: facts about them, not preferences | `owner_profile` | |
| Strategic goals | `goals_doc` | `--goals` |
| Decision principles and hard rules | `principles` | |
| The doer roster: trust rung, cost and health per doer (see "The roster's shape") | `doer_roster` | |
| The event ledger: dated lines of what happened | `event_ledger` | |
| Strategy notes the decider may follow links into, a folder | `vault_dir` | `--vault` |
| An estate health probe's latest output (optional) | `health_probe` | `--health` |
| The standing autonomy policy (optional) | `autonomy_policy` | `--autonomy` |

**The doer registry** (`doer_registry`, a TOML file the owner keeps). It lists the only doers the cycle may dispatch; with no registry, no doer runs and only launches remain. `references/doer-registry.example.toml` beside this file is a starting point. Each `[[doer]]` has:

- `name`: what the decider writes, lowercase words joined by hyphens.
- `route`: `produce` (the produce-work doer: `chief_of_staff_produce_work.py` and the `chief-of-staff-producer` worker, by the `task-stack-produce` standard; args a target such as `task:<uuid>`), `skill` (a toolbox skill run headless by a doer agent: `skill` names the skill, `worker` the doer agent, default `chief-of-staff-readonly-doer`), or `agent` (a worker agent dispatched directly: `agent` names it). The orchestrator's `Agent(...)` grant lists every agent it may dispatch; a new `agent`-route or `worker` name runs only once it is added there.
- `args`: the pattern the whole argument string must match. `UUID`, `FOCUS` (words and `. , ' @ : / -`, at most 200 characters) and `PRODUCE_TARGET` stand for the shared patterns. Left out, the doer takes no arguments (for `produce`, `PRODUCE_TARGET`).
- `default_args`, `purpose`, `when` (when the decider should pick it): optional.

An orchestrator is never a doer (it must be the main session of its own Run): name it in the fleet registry and let the cycle launch it. A `[retired]` table maps an old doer name to the reason it went, which a decider naming it gets back.

Each worker's tool grant is its boundary: the read-only doer holds no write tool; a writing doer holds only the writes its one skill makes. Give a skill that writes its own doer agent rather than widening the read-only one.

**Dispatches: at most 2 a cycle.** `--max` on the decide check can lower the cap, never raise it. Zero is a valid answer.

**Improvements: at most 1 a cycle.** The setting `improvements`: `"off"`, `"propose"` (the default) or `"commit"`.

- `propose`: nothing is edited; the receipt files the change as a `[<display name>]` decision task (inside the three a day), for the owner to apply or drop.
- `commit`: the change is made by `chief_of_staff_improve.py apply`, in code, and committed in a separate git worktree of the repository the setting `improve_repo` names, on the branch `improve_branch` (default `chief-of-staff/improvements`). The worktree lives in the state folder. The script refuses a folder that is the repository's own checkout rather than a separate linked worktree, never touches that checkout, and never pushes: the owner reviews the branch and merges it, or deletes it. With no `improve_repo`, `commit` acts as `propose`.

The surface is the `SKILL.md` of each skill the doer registry runs (route `skill`, and `task-stack-produce` for route `produce`). Never this skill's files, a script, or any other file. In the worktree the target must be exactly one file tracked by git at `<...>/skills/<skill>/SKILL.md`, not a symlink, and the worktree must hold no other change. The edit is refused when its old text is not in the file exactly once, when the file changed since the check, or when it changes more than 30 lines added plus removed. The commit is `chief-of-staff: <summary>` with a `Chief-of-Staff-Cycle: <cycle id>` trailer, of that one file only.

**The name the owner sees.** The setting `display_name`, default `Chief of Staff`, written below as `<display name>`: the receipt title, the decision-task prefix, the message text and the ledger line all use it, and `start` copies it into `cycle.json` for the writers. `former_names` (a list) lets the scripts recognise a receipt or decision task written under an earlier name, so a rename never duplicates today's receipt or an open decision.

**Decision tasks: at most 3 a day** across all cycles, `[<display name>] ...`, owned by the owner's own contact (whoami), due the cycle's date. Most days need none.

**The receipt.** One note a day, `<display name> Receipt YYYY-MM-DD`: ten lines for the first cycle, four for each later cycle's block, a System section of at most six lines when there are findings, and on Mondays one "Week in review" paragraph, once a day.

**Messages to the owner.** Through comms-reply-to-email's `notify_owner.py` (the Portal's post to the owner's own Teams chat, email when Teams refuses), never to anyone else: the receipt link once a day, only for a verified receipt; the decision count at most three times a day, only when the Portal shows a new `[<display name>]` task. A link and a count, never a briefing. The link needs `portal_web_url`, the Portal's web address. `NOTIFY_OWNER_MODE=off` silences both.

**Fleet launches: off unless the owner turns them on.** The setting `fleet_launches = "on"` lets the cycle launch registered orchestrators; missing or anything else reads off. While it is off the cycle still reads the fleet and the decider may still name launches, but the decide check skips every one with the reason and `launch` refuses, so the receipt shows what would have run. With it on, the snapshot enforces, the decide check enforces again, and the launch enforces a third time:

- **Launch path.** orchestrator-fleet's `fleet_launch.py NAME --authority propose --cap <backstop> --by chief-of-staff-cycle-orchestrator`, the cycle's only launch. The cycle's authority is `propose`: a registry entry at `trusted` is refused and never offered; one at `dry-run-only` runs only as a dry run.
- **Live or dry.** Live only for an entry at `propose` whose registry status is `live`; every other launch is a dry run.
- **Never launched by the cycle**: the cycle itself; any entry whose registry authority is `trusted` (the owner or its own schedule starts those); an orchestrator with a Run live or queued now, or one that succeeded today unless the launch names `new_evidence`; anything not built (registry status `spec`, or no Automation).
- **Off schedule only.** Each launch names its trigger: `stall` (a Run failed, has waited on the owner too long, or has not run when it should), `event` (something its schedule cannot see) or `priority` (the day's priorities moved). An orchestrator that fires on its own schedule (status `scheduled`) takes `stall` or `event` only. Nothing parses the schedule; the decider weighs how soon it fires next.
- **No cap per cycle or per day, except the backstop.** Concurrency is the runner's. The backstop is the setting `launch_backstop`, default 12 a day, counted from the cycle folders; `--cap` counts the same day in the runner's records as the second fence, and each Automation's own limits are the third. Hitting it refuses the launch and sends the owner one message. It is separate from the two dispatches a cycle.
- **Recorded.** Each launch is a `launch:<name>` row in `execution.json` with the queue line and why, which the receipt reports; a refusal is recorded the same way.

**Writes to the owner's records.** Only `chief_of_staff_records.py`, from the receipt writer's proposals: the Health (and Trust) cells of doers dispatched this cycle in `doer_roster`, one line appended to `event_ledger`, one draft principle file in the folder `principles_inbox`. The principles file and the profile are never written.

**Outward writes.** None, beyond the Portal note, the decision tasks, the message to the owner, and what a dispatched doer's own skill writes. A doer whose skill reads the owner's documents never holds a tool that publishes outside (an issue tracker, a web search); keep those apart in separate doer agents.

**Permission rules need a guard.** The agents' `Bash(x:*)` rules are prefix rules, and Claude Code alone does not stop a command chained after an allowed prefix. Run these agents under a runner that enforces the prefix, or in a session with such a guard installed; never start them headless with permissions skipped and no guard.

## The roster's shape

`doer_roster` is Markdown with a section headed `## Active doers` holding one table: the first column names the doer (its registry name), the column before last is its trust rung (OBSERVE, PROPOSE or TRUSTED) and the last its health note. The records script replaces only those two cells of a dispatched doer's one row. OBSERVE: the decider does not dispatch it. PROPOSE: it may, and the receipt flags the doer as not yet proven. TRUSTED: dispatched freely.

The event ledger's lines read `- YYYY-MM-DD | <display name> | event (ref)`.

## Mechanics

**State folder**: `--state`, else `[chief-of-staff-cycle] state`, else `<state_dir>/chief-of-staff`. Never inside this skill's folder.

- `cycles/<date>/<HHMMSS>[-dry-run]/`: the cycle folder (CYCLE). In the order the steps write it: `cycle.json`, `execution.json`, `fleet.json`, `task-stack.json`, `decide-raw.txt`, `decision.json`, `produce-N.txt`, `improve.json`, `improve-reply.txt`, `receipt-read.json`, `receipt.json`, `publish.json`, `records.json`, `verify.json`, `report.md`.
- `artifacts/<target>/<fingerprint>/`: produce-work's private `source.json`, `review.json`, `artifact.md`, `manifest.json`, mode 0700.
- `improve-worktree/`: the improvement worktree, on the improvement branch.
- `notify.json`: the messages sent per kind per day, seven days kept.

**Markers**, found before anything is written:

| Item | Marker |
|---|---|
| The receipt note | the title `<display name> Receipt <date>` |
| One cycle's text in it | `<!-- chief-of-staff:cycle:<date>/<cycle id> -->` at the end of that cycle's text |
| A decision task | `source_reference` `chief-of-staff:decision:<date>:<key>`, the key a hash of the title; an open `[<display name>]` task with the same title is reused too |
| A ledger line | the line itself |
| A draft principle | the file `<principles_inbox>/<date>-chief-of-staff-<slug>.md` |
| A produce-work artifact | the fingerprint of the instructions and the packet |

**Exit codes**: every script prints one JSON object; exit 0 to go on, 3 for a hold, a refusal or a missing note, 2 when it could not run. A script that could not run fails that dispatch or that step, never the cycle. The notify script always exits 0.

**The workers**

| Agent | Model | May touch | Brief |
|---|---|---|---|
| `chief-of-staff-decider` | opus | Portal reads; reads the owner's documents named in `cycle.json` | `briefs/decider.md` |
| `chief-of-staff-producer` | opus | reads the packet and the produce-work instructions only | `briefs/producer.md` |
| `chief-of-staff-readonly-doer` | opus | Portal reads; reads the named skill's files | `briefs/doer.md` |
| `chief-of-staff-meeting-prep-doer` | opus | Portal reads, `meeting_prep` and the one prep note | `briefs/doer.md` |
| a worker agent the registry names | its own | its own tool grant | `briefs/doer.md` |
| `chief-of-staff-improver` | opus | reads the one target file; returns the edit, makes none | `briefs/improver.md` |
| `chief-of-staff-receipt-writer` | opus | reads the cycle folder and the owner's documents | `briefs/receipt-writer.md` |

None of the workers writes the receipt, a decision task, the owner's records or the improvement; the scripts do. The orchestrator writes only in the state folder.
