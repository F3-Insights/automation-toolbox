# Settings and mechanics for meeting-scheduled-worker

The first half is the owner's current settings for this job: theirs to change, in this file. The values below are examples to replace. The second half is how the steps run. The owner's data-privacy policy, where they have one, governs client data and is read, never copied.

## The owner's settings

**Recordings per run: 5.** `python3 ~/.claude/skills/meeting-scheduled-worker/scripts/meeting_pending.py --limit 5`. Oldest first, so the scheduled runs drain any backlog before they reach this week's meetings. A request may name another limit.

**Cut-off: meetings that started on or after the date this job went live.** The `since` setting under `[meeting-scheduled-worker]` holds it (`<YYYY-MM-DD>T00:00:00Z`), and `meeting-pending --since` overrides it for one run. Earlier recordings are a deliberate backfill: run with an earlier `--since` when the owner asks for one.

**Length cap: 3 hours.** A recording longer than that is not analysed. `meeting-fetch` reports `over_cap`, the ledger marks that revision permanent, and the report flags it so the owner can decide what to do with it.

**Retries: 3 attempts, 6 hours apart.** A recording skipped for any reason is tried again on a run at least 6 hours later, and after 3 attempts without being acknowledged it is parked and listed in every report until the owner clears it (`python3 ~/.claude/skills/meeting-scheduled-worker/scripts/meeting_skip.py RID --clear`). A recording skipped for a reason no retry can cure (the cap, an empty transcript, a cancelled admin task) is marked permanent for that revision. The Portal being unreachable is not the recording's fault: it defers the recording for the same 6 hours and counts no attempt, at whichever step it happens.

**Revision rounds: 2.** An invalid plan or a checker FAIL goes back to the analyst with the errors or the numbered fixes, at most twice. A third failure skips the recording for this run.

**What is written without asking.** The owner authorises ordinary, sourced internal writes for this job: the recording's own meeting note, rewritten in place from the transcript and linked to the meeting, the people and the tasks; action tasks for commitments the room accepted, with their owner, domain and stated due date; links to tasks that already track an action; enrichment hand-offs for the people and companies this meeting taught something durable about; and the admin task and the acknowledgment. Never written: a new Project, an email or any message to anyone, a change to who has authority over what, a completed business task, or a deletion. Silence is not approval.

**What is the owner's decision, so asked.** Asked in the Portal, never in the session: the questions go at the end of the recording's admin task, which is set WAITING, and the run moves on. The owner answers by commenting on that task, by moving it to TODO (an answer typed into its description is read too; a question nothing answers then goes ahead unanswered and is flagged in the note), or both. Only what blocks correct cataloguing after the Portal has been checked is asked:

- who owns an accepted action when the transcript and the Portal leave two or more plausible owners;
- which client, domain or project a material action belongs to when the evidence points two ways (a missing Project alone is not a question: the action goes to its domain with no project);
- background only the owner has that changes what an action means (a name nobody in the Portal holds, a commitment that may already be settled).

Not the owner's decisions, so never asked, and flagged in the note instead: an unaccepted proposal whose speaker is uncertain (it stays an unattributed proposal), questions the meeting left open for the participants to pursue, poor audio, unreliable speaker labels, and anything the Portal context answers.

**Enrichment goes to the Portal's research agent.** `python3 ~/.claude/skills/meeting-scheduled-worker/scripts/meeting_publish.py --agent-slug
<slug>` names the Portal agent (for example `deep-researcher`) whose queue takes `Enrich contact:` and `Enrich company:` tasks. The admin task is
assigned to no agent: it is the job's record, not work for another worker.

## The folders

Nothing lives in the toolbox repository; every command refuses a path inside it.

- **State folder**: `--state`, else `$MEETING_PROCESSING_STATE`, else the `state_dir` setting under `[meeting-scheduled-worker]`, else `meeting-processing/` under the top-level `state_dir` setting. With none of these the commands stop; there is no built-in default. It holds `ledger.json` and one folder per recording revision, `recordings/<recording id>-<digest>/`. The recording folder outlives a run, so an interrupted recording resumes from what it has.
- **Run folder**: the folder a runner passes, else `<state>/runs/YYYY-MM-DD-HHMM/`. It holds `pending.json` and `report.md`.

The recording folder, in the order the steps write it:

| File | Written at | By |
|---|---|---|
| `existing.json` | step 3 | `python3 ~/.claude/skills/meeting-scheduled-worker/scripts/meeting_existing.py --out` |
| `source.json`, `transcript.txt` | step 4 | `meeting-fetch` |
| `plan.json` | step 5 | the orchestrator, the analyst's JSON block verbatim (earlier rounds `plan-1.json`, `plan-2.json`) |
| `check.json` | step 7 | the orchestrator, the checker's JSON block verbatim (earlier rounds `check-1.json`, `check-2.json`) |
| `answers.md` | step 3 | `meeting-existing`, the owner's comments on the admin task verbatim (and its description when they moved it to TODO); `meeting-publish` reads it whenever it is there |
| `publish.json` | step 8 | `meeting-publish` (`publish-dry-run.json` and `note-preview.md` in a dry run); `notes_written` holds a fingerprint of every note text it wrote and `questions_written` of every questions section it put on the admin task, carried from run to run |

When the owner answers, `meeting-existing` moves `plan.json` and `check.json` to the next free `plan-N.json` and `check-N.json`, so the analyst starts again with the answers.

The Portal is the ledger of what was written; the folder is a cache. Delete a recording folder and the next run rebuilds it and finds every task it made by marker. One thing goes with the folder: `notes_written` and `questions_written`. A note this job already wrote then reads as edited by someone else (NOTE_EDITED, marked permanent) and is left alone, until the owner removes the marker line from it and clears the recording with `python3 ~/.claude/skills/meeting-scheduled-worker/scripts/meeting_skip.py RID --digest D --clear`; and an earlier questions section on the admin task is kept as it stands, with any new questions added below it, rather than replaced.

## The ledger

`ledger.json` in the state folder, one entry per recording revision: attempts, the last attempt's time and reason, `permanent`, and the admin task a WAITING recording waits on. `meeting-existing` counts an attempt (also when its lookup fails, except when the Portal was unreachable, which defers the recording without counting); `meeting-fetch`, `meeting-publish` and `meeting-acknowledge`, when the Portal is unreachable, defer the recording and take that attempt back; `meeting-fetch` marks the cap and an empty transcript permanent; `meeting-publish` records the admin task a `waiting` result waits on and marks permanent a note edit no retry cures; `meeting-skip` adds the reason the orchestrator saw. `meeting-pending` reads it and never writes it. Every write to it, and every publish, waits at most 10 seconds for its lock and then skips that recording with the reason. Losing it costs nothing but retries.

## Markers

Every write carries a marker, so what an earlier attempt wrote is found and reused.

| Item | `source_reference` |
|---|---|
| Admin task | `meeting-processing:recording:<recording id>:<digest>` (the older `meeting-processing:<event id>:<digest>` is recognised) |
| Action task | `local-meeting:<event id>:<first 16 of the full transcript hash>:<plan index>` |
| Enrichment task | `context-enrichment:<contact or company>:<id>` |
| Meeting note | `<!-- meeting-processing:recording:<id>:<digest> -->` at the end of the content; a note several recordings share keeps each recording's section between `local-recording-section` comments |

The listing has no `source_reference` filter and its search does not match `source_reference` either, so a lookup searches tasks for the recording id and the event id and matches the marker exactly on the rows. Every task this job creates therefore carries the id its lookup searches for in its description.

## Exit codes

Every command prints one JSON object. Exit 0 to go on, 3 to skip this recording (or, for `meeting-pending`, `not_local_owner`), 2 when it could not run. A command that could not run skips that recording, never the run, except `meeting-pending`, which has nothing to skip. `meeting-skip` exits 0 or 2.

`python3 ~/.claude/skills/meeting-scheduled-worker/scripts/meeting_pending.py --precheck` prints `NOTHING` or `WORK: <n> recordings to process` on its first line and exits 0, so a scheduler can skip waking a model.

## The workers

| Agent | Model | May touch | Brief |
|---|---|---|---|
| `meeting-analyst` | opus | Portal reads, Read | `briefs/analyst.md`, returning `briefs/plan.schema.json` |
| `meeting-checker` | opus | Portal reads, Read | `briefs/checker.md`, returning `briefs/checker.schema.json` |

Neither writes anything; every write is `meeting-publish`'s. The analysis and the independent check both read the whole transcript, so both are Opus work. Each brief is the worker's whole instruction for this job: paste its text and the paths it names into the dispatch.

## What the tools enforce, so no prompt has to

- `meeting-fetch` retrieves the exact recording by id and refuses one whose words do not hash to the listed digest, whose event or note do not match, or which runs over the cap.
- `meeting-validate` refuses a quote that is not in the segment it cites, a new task without a verified owner and domain, and a plan that would make a second task for an action an earlier attempt already created.
- `meeting-publish` refuses a plan without a PASS check for its exact hash; re-checks before each write that the Portal still hands processing to this host and the transcript, event and note are unchanged; keeps a human's edit to the note (NOTE_EDITED) rather than writing over it, before it creates anything; refuses a plan made without the owner's answers when there are some (ANSWERS_UNAPPLIED, read from `REC/answers.md` whether or not it is passed); never drops text the owner typed into the admin task's description when it asks again; reads every write back; and completes the admin task, then acknowledges, only after the note, its links and every task verify.
- `meeting-validate`'s `plan_hash` covers the plan and the note it was made against, so a note that changed after the check is a changed check, and `meeting-fetch` reports `earlier_check` false.
- `meeting-existing` reads the owner's answers from the owner's comments on the admin task (author email from whoami, comments carrying an agent's "(posted by ..., an agent)" line excluded) and sets the old plan aside.
- `meeting-acknowledge` acknowledges only a DONE admin task that shows the note, for the transcript revision the Portal still holds. A task carrying only the older marker is given the exact marker first, because the Portal acknowledges against nothing else.
