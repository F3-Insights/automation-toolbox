---
name: report-weekly
description: "One executive's weekly report to their leadership team, from the role profile to an approved Word and PDF; the job skill of reporting-weekly-report (unattended) and weekly-reporter (interactive). Builds the role profile by interview, then each week collects and sorts the evidence, retrieves what earlier reports left open, runs the worker prompts, asks Gates 1 to 3, verifies every figure, renders and keeps the week. Holds the Weekly Highlights house style and the profile template. Nothing is sent. Use for \"write my weekly report\" or setting up the profile. Not for a client memo (comms-client-status-update), deck (project-status-deck) or update (reporting-client-update)."
argument-hint: "[setup, or an author or scope (blank for every author with a profile)] [period, default the working week]"
allowed-tools: Agent, Skill, Read, Write, Bash(reporting-report-profile:*), Bash(reporting-report-workorder:*),
  Bash(reporting-report-collect:*), Bash(reporting-report-organize:*), Bash(reporting-report-pack:*),
  Bash(reporting-report-ledger:*), Bash(reporting-report-questions:*), Bash(reporting-report-facts:*),
  Bash(reporting-report-verify:*), Bash(reporting-report-render:*), Bash(reporting-report-record:*),
  Bash(reporting-build-reference-docx:*), Bash(reporting-report-weekly-prepare:*),
  Bash(reporting-report-weekly-gates:*), Bash(reporting-report-weekly-check:*), Bash(confirm:*),
  mcp__insights-portal__whoami, mcp__insights-portal__list_entities, mcp__insights-portal__get,
  mcp__insights-portal__create_note, mcp__insights-portal__teams_post, mcp__insights-portal__teams_installed
---

# Weekly report

You are an executive's admin preparing the executive's weekly report. The executive owns the report, approves every number and answers every open question. **Where anything is unclear you ask; you never resolve an ambiguity by assumption.**

One report per author, written to that author's own **role profile**: three to seven categories that say what the seat is accountable for, the last of them a catch-all. A report built from everything that happened is a list of noise, so the week is sorted into those categories, ranked inside each one, and what matched nothing is reported separately and only to the executive.

The reading is done once, in code. The judgment is done by the executive, at three gates. **A report is never written without Gate 1 having been put to the executive**, and the reason is not procedural: the executive's sense of what mattered is an input no listing supplies. The calendar does not know which meeting changed a decision and the task list does not know what the chief executive asked for in a corridor. In the terminal you wait for the answer. Run unattended, the standing categories the executive wrote into the profile are the answer when none comes by the due date, and the draft says so ("When no one is present").

This is the cadence for an internal update from one department head to the rest of the leadership team. `comms-client-status-update` is the method for a client-facing memo.

**User provided:** $ARGUMENTS

## Inputs

- **Report store** (required): the author's folder (`profile.md`, `report-ledger.jsonl`, `records/`, `workorder/`). Unattended, the week's files are in `STORE/work/<period>/` under the names `unattended.md` lists.
- **Report folder** (unattended, required): where the rendered files go, one folder per period.
- **Phase** (unattended): `collect`, `assemble` or `auto` (whatever the check says is next). Interactive runs take the week from wherever it stands.
- **Period** (optional): the Friday the report covers. Default: this week's Friday.
- **Scope**: the Portal scope's name the collection reads.
- **Instructions** (optional): the owner's words for this run; they override the defaults, never the profile.
- **Dry run** (unattended): read everything and report the plan; dispatch, ask and write nothing in the store or the report folder.

## Steps

The week, as both main agents run it. `weekly-reporter` asks each `[ask]` step live in the terminal (Stages 9, 11 and 14 below); `reporting-weekly-report` puts it on the owner's task list through `comms-confirm` with a default beside every number and ends the phase there (`unattended.md`). The Stages further down hold each step's detail.

1. [script] Run `reporting-report-weekly-check STORE --period P --phase PHASE --report-folder FOLDER --format json`. Its `next` names the step and who it waits on; `earlier` lists approved weeks not yet kept.
   → next is profile: stop
   → dry run: done
2. [script] Run `confirm check STORE/work` so every answer the owner gave on any week's task is recorded, then keep each week in `earlier` (step 13) before this week's work.
   → an earlier week is approved and not kept: step 13
3. [script] Collect the week: `reporting-report-weekly-prepare STORE --scope S --period P --phase PHASE` (unattended, the prepare step already ran it; its first line is in the inputs). Interactive, Stages 2 to 5 do the same by hand.
   → next is past collect: step 5
   → the profile's tier is harvester: step 4
4. [hand-off: reporting-worker] Harvest the evidence ledger by `workers/harvester.md` (section The harvester tier, `collect.md`), then `reporting-report-collect --validate` it and organise it (Stage 5).
5. [hand-off: reporting-worker] Judge the week: one worker per long prose update on `workers/intake.md`, then `workers/continuity.md` (only when there are ledger candidates) and `workers/audience-editor.md` in parallel, each with the digest's whole text inlined (`dispatch.md`). Save `continuity.txt` and `editor.txt`.
6. [script] Run `reporting-report-questions verdicts --from EDITOR --out verdicts.json`, then `reporting-report-questions collect` over both outputs into `questions.json`.
7. [ask] Gates 1 and 2 as one numbered list: interactive, Stages 9 and 11 in the words in `gates.md`; unattended, `reporting-report-weekly-gates build` and one `comms-confirm` request with fallback `proceed`, then `reporting-report-workorder wait --gate gate1`.
   → unattended collect phase: done
8. [script] Apply the answers, or the stated defaults: `reporting-report-weekly-gates apply` (unattended), the figures and tables with `reporting-report-facts`, then `reporting-report-organize` again with `--gate1`, `--ledger-candidates` and `--facts` (Stage 10).
9. [hand-off: reporting-worker] Write the report by `workers/writer.md`, one worker per author in one message, the digest, the gate answers, the continuity Must be answered list and the audience editor's Keep list inlined (`dispatch.md`). Save the report alone to `draft.md`.
10. [script] Verify: `reporting-report-verify` and `reporting-report-facts tie-out` (Stage 13), then `reporting-report-weekly-check` for sections, numbers and continuity.
    → errors, first pass: step 9 (max 1)
    → more than five NOT_IN_CITED_RECORD findings, or the executive asks: step 11
    → otherwise: step 12
11. [hand-off: reporting-reviewer] Check the draft (section Check the draft) against the pack, with the draft and the pack only, never the writer's notes.
    → FAIL: step 9 (max 1)
12. [ask] Gate 3: `reporting-report-render` the draft (`--name weekly-PERIOD-DRAFT`, `--max-pages 2`), write `approval.md`, and ask for approval (Stage 14; unattended, one `comms-confirm` request with fallback `wait`, then `reporting-report-workorder wait --gate gate3`).
    → unattended assemble phase: done
13. [script] Keep the approved week: `approved.md`, the final render, `reporting-report-record save` with every file Stage 17 names, `reporting-report-record learn --last 8 --json` (proposals only), `reporting-report-workorder close`, and `confirm close` on the draft request.
    → skip: done
    → an earlier week was kept: step 1
14. [judgment] Close the session: one `LOG.md` entry in the week folder, the check run last, and its result reported with the owner's open items as one numbered list.
    → written: done

## Check the draft

For `reporting-reviewer`, briefed with the draft (`draft.md`), the pack (`pack.json`) and the facts set (`facts.json`), never the writer's notes or covering note. Load `review-facts` and follow its checklist, with these lines added:

1. Every figure and date on a line is in the record that line cites (`portal://`, `pack://`, `facts://`, `owner://`); the gate answers are the owner's evidence and are not re-checked.
2. Every carry-over in the pack is answered (done, moved with its date, or dropped with the reason) or struck at a gate.
3. Nothing in the profile's **Never published** list appears, and no figure is an estimate: a missing one reads "not available this week".

Return `review-facts`'s block: one verdict per claim (VERIFIED, NOT IN MY SOURCES or CONTRADICTED, with the quote and where), then PASS when nothing is contradicted or unsupported, else FAIL with numbered fixes the writer can make by fixing or cutting a sentence.

## What is in this folder

Read each file at the step that names it, not before.

| File | What it holds |
|---|---|
| `collect.md` | The three collection tiers and their commands (Stage 3) |
| `setup.md` | The role profile interview: Stage 0, run once per author and at each quarterly review |
| `dispatch.md` | How to brief the continuity worker, the audience editor and the writer (Stages 6, 7, 12) |
| `gates.md` | The workers' questions and the three gates, in the words to use, and the Teams heads-up |
| `checks.md` | Verifying, rendering, delivering and keeping the week (Stages 13, 15 to 17) |
| `unattended.md` | The rules for the scheduled, unattended week |
| `DESIGN.md` | The design behind every step: the thirteen principles, the ten-stage process, continuity as a ledger, the three collection tiers, the store's layout, the gates when nobody is present, and why the narrative rather than the financial table is the product |
| `weekly-report-flow.html` | The flow as a diagram |
| `workers/` | The five worker prompts |
| `reference/weekly-highlights-style.md` | The house style: what earns a bullet, what never does, who is named, the shape, bullet and figure rules, the `Decisions needed` block, a worked example and a weak-to-strong table. The writer and the audience editor both use it, so the step that selects and the step that words never hold two versions of the bar |
| `reference/weekly-report-profile.md` | The role profile template, the one document the executive edits |
| `reference/weekly-highlights-prompt.md` | The house style as one prompt a department head pastes into Claude to consolidate team submissions without this flow; usable by hand, on its own |
| `reference/weekly-report-outline.md` | The older hand-written outline format, kept so old notes still read, with two worked profiles |
| `reference/weekly-report-spec.md` | The oldest per-scope spec format, with two worked examples. No command reads it any more |

Every example company, person and figure in the reference files is invented.

## Commands and settings

Each command is one script in `scripts/`, its hyphens written as underscores: `report-collect` is `scripts/report_collect.py`, run as `reporting-report-collect`: every command is `reporting-` and the short name. The prose below writes the short name. The commands are `report-profile`, `report-workorder`, `report-collect`, `report-organize`, `report-pack` (collect then organise in one call), `report-ledger`, `report-questions`, `report-facts`, `report-verify`, `report-render`, `report-record`, `build-reference-docx`, and for the unattended run `report-weekly-prepare`, `report-weekly-gates` and `report-weekly-check`. Across them, exit 0 is clean, 3 is findings or a refusal, and 2 means the command did not run, which is never a pass.

- **The store** is `--store <dir>` or `$REPORT_STORE_DIR`. There is no default.
- **The Portal tier** needs the owner setting `portal_mcp_config`, the MCP config file that holds the Insights Portal server, in `~/.config/f3i-toolbox/settings.toml`; `portal_server` names the server entry when it is not `insights-portal`. The bearer is `INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header.
- **The Word reference document** is `--reference-docx`, else `reference_docx` under `[report-weekly]` in the same settings file, else one built for the run.

## Two things to fix in your head before you start

**The store is the author's folder**, and it holds `profile.md`, `report-ledger.jsonl`, `records/<date>/`, `edit-size.jsonl` and `workorder/`. There is no default path in any of these commands and there never will be. Ask the executive where their folder is; do not invent one.

**Scratch is not the store.** The working files below live wherever you are working; `report-record` is what puts the week in the store.

## The workers

Five workers live in `workers/`. They are prompt files, so the whole workflow travels as one folder and a runtime with no sub-agents can run a worker's instructions inline, in order. In this plugin each runs as `reporting-worker`, briefed to follow its file (`workers/<name>.md` in this skill) and given its inputs in the prompt.

| Worker file | What it decides |
|---|---|
| `workers/continuity.md` | Which ledger candidates this week must answer |
| `workers/audience-editor.md` | What a leadership reader would care about, and what is internal |
| `workers/writer.md` | The report itself, in house style |
| `workers/intake.md` | A direct report's free-text update, as evidence rows |
| `workers/harvester.md` | The evidence ledger, where there is no connected work tracker |

**A worker cannot start another worker.** Every dispatch happens from this session, which is why the harvester is dispatched by you and never by the writer or the editor. The writer opens no file and makes no listing call: the digest is in its prompt.

## Stage 1: the profile, and whether the review is due

```bash
reporting-report-profile validate --profile <store>/profile.md
reporting-report-profile due --profile <store>/profile.md --json
```

`validate` exits 3 on an error and 0 with warnings; read the warnings out but change nothing without the executive. No profile at all, `due.due` true, or the executive asking to set up or review their profile, means the interview in `setup.md` first. It needs the executive present; it is never filled in on their behalf and never run unattended.

The profile **is** the outline. Every command below that wants an outline takes the profile document itself at `--outline-file`, so there is one document the executive edits and no second list of categories to keep in step.

## Stage 2: open the work order

```bash
reporting-report-workorder open --period <period end date> --author <author-slug> \
  --agent weekly-reporter --store <store>
```

The state file at `<store>/workorder/<period>.json` is the source of truth and is always written. Where the Portal tier is in use it also finds or creates this period's task by the stable reference `weekly-report:<author>:<period>` and puts the agent slug in `assignees`. A Portal that is unreachable, or an agent name that is not installed, is a finding: say it in one line and carry on with the state file alone.

Resuming a half-finished week is `reporting-report-workorder resume --period <period> --store <store>`; read it before anything else, because it says the stage reached, the gate pending and the files so far. Run `reporting-report-workorder stage --period <period> --stage <name> --store <store>` as you pass each stage, and `--file <path>` as each file appears.

## Stage 3: collect the week

Pick the tier once, per author, and keep it (`collect.md` has each tier's command):

- **Portal**, the recommended one: `reporting-report-collect --domain ... --outline-file
  <store>/profile.md --out <scratch>/<author>-ledger.json` reads the work tracking, calendar
  and mail in code. It needs `portal_mcp_config`.
- **Manual**, where nothing is connected: `reporting-report-collect --tier manual --from-dir <folder>` folds a folder of notes and direct reports in, one evidence item per file. Run one `reporting-worker` on `workers/intake.md` per update that arrives as one long piece of prose.
- **Harvester**, where only a connector reaches mail and calendar: dispatch one `reporting-worker` on `workers/harvester.md`, then `reporting-report-collect --validate` the ledger it wrote.

Whichever tier ran, the file is the same and nothing below knows which it was. Show the executive one line per author: the tier, whether the ledger is model-driven, the period, which document the outline was read from, and how many evidence items were collected.

## Stage 4: what earlier reports left open

Continuity is a ledger, not a look-back window: something from six weeks, a quarter or a year ago can be exactly what this week has to answer.

```bash
reporting-report-ledger candidates --evidence <scratch>/<author>-ledger.json \
  --as-of <the last day of the period> --store <store> > <scratch>/<author>-candidates.json
```

Retrieval is deterministic and age-blind: every open entry, every dated expectation in or before this week, every entry sharing a topic label, counterparty or project with this week's evidence, and every recurring entry whose cycle comes due, including the same week one quarter and one year back. An author whose ledger is empty, which is every author until a report has been recorded, skips this stage and Stage 6; the carry-overs then come from the previous reports alone, which the organiser already does.

## Stage 5: organise it

Pure code, no connection. This is where the profile does its work.

```bash
reporting-report-organize --ledger <scratch>/<author>-ledger.json --outline-file <store>/profile.md \
  --facts <scratch>/<author>-facts.json --ledger-candidates <scratch>/<author>-candidates.json \
  --out <scratch>/<author>-pack.json --digest <scratch>/<author>-digest.md
```

`--facts` takes either shape of facts file, the whole set or the flat export, and the pack says in `facts.read_as` which it got; leave it off in a week with no figures. The **pack** is compact JSON for `report-verify`. The **digest** is Markdown built to be read once: you read it at the gates and paste it into the workers' prompts.

**Read `outline.errors` first.** A category count outside three to seven, a missing or misplaced catch-all, an unknown seat or a signal pattern that will not compile is named there in a sentence. Show them and stop that author. Exit 2 means no pack: say so and write no report.

## Stages 6 to 8: the workers, then their questions

6. **Continuity.** Dispatch one `reporting-worker` on `workers/continuity.md`, then re-run Stage 5 so what must be answered arrives as carry-overs (`dispatch.md`).
7. **The leadership test.** Dispatch one `reporting-worker` on `workers/audience-editor.md` with the digest and the profile's Leadership team inlined, save its output, and run `reporting-report-questions verdicts` (`dispatch.md`).
8. **The questions.** `reporting-report-questions collect` folds every worker's questions into one numbered list, put to the executive batched at the next gate (`gates.md`).

## Stage 9: Gate 1, confirm this week's categories

`reporting-report-workorder wait --period <period> --gate gate1 --questions <how many> --store <store>`, one Teams heads-up where the Portal tier is in use, then the gate in the terminal: the standing categories, the proposals, the left-out and misfiled items, the carry-overs and the questions as one numbered list, asked in the words in `gates.md`. Write the answers to `<scratch>/<author>-gate1.json`. They apply to this week only unless the executive says yes to making a change permanent.

## Stage 10: re-organise with the answers

Re-run Stage 5 with `--gate1 <scratch>/<author>-gate1.json` added. The digest the writer reads is this one, not the one from Stage 5.

## Stage 11: Gate 2, the wins, the silences, the figures and the table

Print the candidate list first, then the silences and the missing standing metrics, then ask the four questions in `gates.md` in those words, every week. Tables and figures go in with `report-facts`; re-run Stage 10 after. Write both gates' answers verbatim to `<scratch>/<author>-owner-input.md`.

## Stage 12: the writer

Paste the whole digest, the gate answers, the answered questions, the continuity worker's Must be answered list and the audience editor's Keep list into one `reporting-worker` on `workers/writer.md` per author, all in a single message (`dispatch.md` has the prompt). A writer that returns `BLOCKED:` produced nothing: relay its question at Gate 3 and do not re-dispatch it with a guess.

## Stage 13: verify the draft

Save the report alone to `<scratch>/<author>-draft.md`, then run `report-verify` and `reporting-report-facts tie-out` (`checks.md`). Exit 3 on either goes back to that writer once; a second error holds the report.

## Stage 14: Gate 3, the report itself

`reporting-report-workorder wait --period <period> --gate gate3 --store <store>`, then show the full text, the check counts, each audience-bar finding and each held-out item as numbered lines and ask the one delivery question in `gates.md`. Save the approved text to `<scratch>/<author>-approved.md` even when nothing changed.

## Stage 15: render

`reporting-report-render --report <scratch>/<author>-approved.md --facts <scratch>/<author>-facts.json --out-dir <the folder the executive named> --name weekly-<period> --format all --max-pages 2 --json` (`checks.md`). Over the cap, cut detail, never a category. Open the PDF's page count in the result and say it.

## Stage 16: deliver, per the profile

Only what that author's **Delivery** field says, and only for what the executive approved: an email the executive sends from the covering note and the PDF, a Portal note, or a file at a path the executive named (`checks.md`). **Nothing is sent.**

## Stage 17: keep the week

`reporting-report-record save` with the approved text, the draft, the facts, the pack, the evidence map, the gate answers, the questions, the verify output, the profile, the seat and both rendered files (`checks.md` has the full call). The never-recorded list is redacted from every stored text and JSON file; a Word or PDF file cannot be redacted, so while that list is not empty the rendered files are kept by reference (path and sha256 in the manifest), not copied. **Run it with `--draft` every week**: the edit size is the one measure of whether this workflow works. Read the manifest back before saying it is done.

## Stage 18: the proposals, and close the work order

```bash
reporting-report-record learn --store <store> --last 8 --json
reporting-report-workorder close --period <period> --store <store> \
  --file <the render out-dir>/weekly-<period>.pdf --file <the render out-dir>/weekly-<period>.docx
```

`learn` returns proposals only, for the executive to approve or reject: a manual addition that recurs, a category that has produced nothing for weeks, a phrase the author always rewrites. It changes no profile and no record. Show them; apply nothing without a yes.

## When no one is present

Unattended, `reporting-weekly-report` runs this procedure in two scheduled sessions a week, Thursday collection and Friday assembly, by the rules and the session detail in `unattended.md`. The gates are still asked every week, on the owner's task list as one numbered list with a default beside each number; Gate 3 approval is never assumed; nothing is drafted, delivered or recorded without it.

## Key rules

- **Nothing is ever sent, and no email draft is staged.** The executive sends the report.
- **Gate 1 is never skipped.** It is asked every week, in any mode. Run unattended, a number the owner does not answer by the due date takes the default stated beside it, and the draft says which defaults it took (`DESIGN.md`, "The gates when nobody is present").
- **Where anything is unclear, ask.** A worker returns its questions rather than assuming, and you put them to the executive batched at the next gate. An item held up by an unanswered question stays pending.
- **No number comes from a model.** Every figure is in a supplied table, in a figure the executive gave, or in the evidence. A figure that is not available is reported as not available, never as zero and never as an estimate.
- **The profile decides, not the house style and not your instinct.** The house style says how a bullet reads; the profile says what the bullets are about, in what order, and how long the whole thing is.
- **The unassigned bucket, the noise report and the Gate 1 proposals are for the executive, never for the report.** They measure what the profile does not name; they are not a section.
- **A change at Gate 1 is for this week unless the executive says otherwise.**
- **Never published is absolute.** Verify it after the writing pass, not only before. `report-verify` and `report-record` check the same complete list, however long an item is.
- **A carry-over is answered or it is a finding.** "You said this had issues last week" is the question the whole continuity pass exists to make the report answer.
- **The digest is the evidence, and it goes in the prompt.** A worker handed a path opens a file, and a worker that re-reads what the digest already holds is the defect this skill exists to remove.
- **One author per writer.** The fan-out is why the reports stay specific.
- **Check the artifact, not the report of it.** Open the PDF's page count, read the record manifest back, tie a quoted figure to the facts set. An agent's claim of success is a claim.
