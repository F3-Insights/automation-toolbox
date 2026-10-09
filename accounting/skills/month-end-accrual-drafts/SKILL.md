---
name: month-end-accrual-drafts
description: Draft a month's credit-card accrual and post-cutoff vendor accrual from a Month-End folder, each first checked against the ledger pull and the folder ("is it already done?"), into an import file a person uploads (STATE Posted); agents never upload or post. The folder's maps and settings drive it, so it is the same for any company. Use for "is the card accrual done", "draft the vendor accrual", or rebuilding a past month's accruals for comparison. For any other entry, use month-end-journal-entry.
argument-hint: "[Month-End folder] [period yyyy-mm] [optional: cc | vendor]"
allowed-tools: Read, Glob, Bash(python3:*), Bash(python3 ~/.claude/skills/month-end-accrual-drafts/scripts/card_export.py:*), Bash(python3 ~/.claude/skills/month-end-accrual-drafts/scripts/cc_accrual.py:*), Bash(python3 ~/.claude/skills/month-end-accrual-drafts/scripts/service_period_accrual.py:*), Bash(python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import.py:*), Bash(python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import_check.py:*), Skill
---

# Month-end accrual drafts

An agent prepares the entry; a person uploads it. Every entry leaves as an import file a person uploads (STATE Posted, since that upload is the human review; agents never upload or post) in the month's `journal-entries/` folder (or the month folder, when it has no such subfolder). Before building, each accrual asks whether it is already done, from the data (an entry in the month's read-only ledger pull) or from the folder (an import file already there), and reports the evidence.

Everything specific to the company lives in the folder: accounts, maps, vendor lists, where the card report is, the file name. The contract is in `rules.md` beside this file:
- the folder sections read;
- the done check;
- the outcomes and their exit codes;
- how a caller records each outcome.

Read it before the first run in a session. One standard-library script does the mechanical part and calls the toolbox commands (paths relative to this skill's folder):

```bash
python3 scripts/accruals.py config FOLDER
python3 scripts/accruals.py done FOLDER --period yyyy-mm --accrual cc|vendor
python3 scripts/accruals.py inputs FOLDER --period yyyy-mm --accrual cc|vendor
python3 scripts/accruals.py scan FOLDER --period yyyy-mm
python3 scripts/accruals.py build FOLDER --period yyyy-mm --accrual cc|vendor [--out DIR] [--ignore-done] [--decisions FILE]
```

## Inputs

- **Month-End folder** (required): the folder holding METADATA_FIELDS.md (with its `## Accruals` section), SYSTEMS.md (with `## Close inputs`) and the month folders.
- **Period** (optional): yyyy-mm, the month the entries are dated in. Default: the current period the root STATUS.md names.
- **Accruals** (optional): `cc`, `vendor`, or both. Default both.
- **Trial folder** (optional): a folder outside the Month-End folder to build into instead, for checking a past month against what was uploaded.

If the folder is not given, ask. If no one can be asked, stop and name it.

## Steps

1. [judgment] Settle the folder, the period, the accruals and whether this is a trial run. Read `rules.md` if this session has not. → no folder and no one can be asked: stop
2. [script] Read the accrual settings: `python3 scripts/accruals.py config FOLDER`. → refused (a section or a line is missing): stop
3. [script] Ask "already done?" for each accrual: `python3 scripts/accruals.py done FOLDER --period P --accrual cc` and `--accrual vendor`. Keep each answer's state and evidence. → every accrual asked for is posted, entered or already has a file, and this is not a trial: step 7
4. [script] Build each accrual not done: `python3 scripts/accruals.py build FOLDER --period P --accrual A`, adding `--out TRIAL --ignore-done` on a trial run. It finds the inputs SYSTEMS.md names, runs `card-export` and `cc-accrual`, or `service-period-accrual`, writes the import file with `python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import.py --state Posted`, and lints it with `je-import-check`. For the card accrual it also writes the backup beside the import file, the row trace `card-coding-<yyyy-mm>.csv` and the department reconciliation (`rules.md`, What the build does). The vendor accrual always runs the missing-accrual scan (`rules.md`, The missing-accrual scan) and writes its backup beside the import file. → vendor, exit 4, `missing_accrual.undecided` not empty: step 5 → exit 4 on a trial run: stop → exit 4, an input is missing: step 6 → exit 1, 2 or 3: stop
5. [judgment] Decide each flagged vendor of `missing_accrual.flagged`: accrue or not, with a reason, from its months seen, typical amount, last month seen and the evidence searched (a contract that ended, a vendor billed through the card or another vendor name, an annual or quarterly bill, a cost that is real but unbilled). Write the decisions file (`rules.md`) in the work folder (or the trial folder) and run the build again with `--decisions FILE`. Accepted vendors are drafted into the vendor accrual import file as estimates. → decided: step 4
6. [judgment] Check the result against its source before it counts. The script's output is a claim, not the evidence:
   - the draft's total ties to the source rows: `tie_out.ties`, and the card report's own total for the period, opened and summed, equals `tie_out.card_total`;
   - the department and account per row trace to the source columns and the maps: open the card report and `card-coding-<yyyy-mm>.csv` and check a sample of rows (every row of the largest cardholders, each department source, each override) against the export's department column, the label map, the people map and the card account map;
   - every gap the build reports is carried into the result, not just the first: each disagreement, unknown label, blank, unmapped merchant and cardholder, estimate and overlap, and `ready`;
   - for the vendor accrual, every vendor of `missing_accrual.flagged` is in the result with its months seen, typical amount, evidence and decision, and every `excluded` vendor with its reason, whether or not the build wrote a file. A failed check is reported with both figures, and the draft is not ready. Never edit an import file. A coding gap is a proposed change to METADATA_FIELDS.md (a label, a people-map row, an MCC row or a merchant override); an overlap that would book a cost twice, an estimate, a card draft that is not ready, or a missing input is a question for a person before anyone uploads. → a check fails: step 7 → a trial run: done → a question, and an orchestrator called this skill: step 7 → a question, run on its own: step 8 → nothing to ask: step 7
7. [judgment] Report each accrual's outcome with its evidence (`rules.md` maps outcomes to states), the files written, the proposed changes and the questions. A caller records them; this skill writes no status or log of its own. → reported: done
8. [hand-off: comms-confirm] Ask each question through comms-confirm, one per missing input, overlap or estimate, recorded in the month's CONFIRMATIONS.md. Then report as in step 7. → asked: done

On a stop, say why in one line and what would unblock it: the missing section or the command's message.
