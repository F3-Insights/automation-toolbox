# Standard entries: the contract

What the accruals read from the engagement folder, how "already done?" is answered, what the build writes, and how a caller records each outcome. The examples describe a made-up company, Acme Components.

## What is read from the engagement folder

Nothing entity-specific lives in this skill. `scripts/accruals.py config FOLDER` prints what the folder says, or refuses naming the missing section or line.

METADATA_FIELDS.md, section `## Accruals`, five subsections and three optional ones. Field lines are `- Name: value`; a list is separated by semicolons.

```markdown
## Accruals

### Accrual settings
- Import file name: (ACME) GL upload - {month} {year} {name} (reversing) DRAFT.csv
- Journal: GJ
- Liability account: 2100
- Liability account name: Accrued Liabilities
- Entity location: 1
- Default department: G&A
- Unmapped account: 6999

### Credit-card accrual
- File name: card accrual
- Posted entry contains: credit card accrual
- Vendor name floor: 1000
- Always vendor-named categories: CONSULTING FEES; SOFTWARE
- Post-date cutoff:

### Post-cutoff vendor accrual
- File name: vendor accrual
- Description: To accrue {month} {year} bills received after the AP cutoff
- Posted entry contains: bills received after
- Arrears vendors: PRECISION FREIGHT; NORTHSIDE CONSULTING
- Excluded vendors: FIRST BANK CARD SERVICES (accrued by the credit-card accrual)
- Expense account prefixes: 5; 6; 7
- Trailing months: 3
- Missing-accrual months: 6
- Missing-accrual min months: 3
- Missing-accrual floor: 1000

### Department families
| Department | Family |
|---|---|
| PRODUCTION | COGS |
| G&A | SGA |

### Card account map
| MCC | MCC description | Category | Account | By department |
|---|---|---|---|---|
| 3000 | Airline | AIR TRAVEL | 6110 Travel | COGS=5110 Travel - COGS |
| 5734 | Software stores | SOFTWARE | 6120 Software | |

### Department labels
| Label | Department |
|---|---|
| Production | PRODUCTION |
| Admin | G&A |

### Merchant overrides
| Merchant pattern | Category | Account | By department |
|---|---|---|---|
| FASTENER DEPOT* | SUPPLIES | 6130 Supplies | COGS=5130 Supplies - COGS |

### People map
| Cardholder | Department |
|---|---|
| SAM RIVERA | G&A |
```

- `{month}`, `{year}` and `{name}` in the file name are filled in (`August`, `2026`, the accrual's file name). Earlier files for the month match on the name up to and including `{name}`, so a hand-made `... card accrual (reversing).csv` or a second pass `... vendor accrual 2 (reversing) DRAFT.csv` counts as already there.
- The card account map's Account applies to every department; By department overrides it for a department family or a department, `KEY=account name`, most specific first.
- **Department labels** (optional) maps the card export's department column, filled in per transaction by whoever codes the card, to the ledger's department ids. Labels match without regard to case or surrounding spaces. When the export has that column, it drives each row's department; the people map is a fallback only, for a row whose label is blank or not in this table. A label the table lacks is reported, never guessed. A label given two departments is refused. With no department column, the people map is the source, as before.
- **Merchant overrides** (optional) codes a merchant whose MCC misleads. Rows are checked in order before the card account map; the first match wins. A pattern with `*` or `?` is a glob over the whole merchant name; a pattern without one matches when the name contains it; both ignore case. Category may be left blank to keep the MCC's. By department works as in the card account map.
- Arrears and excluded vendors match when the setting is contained in the ledger's vendor name, without regard to case, so `CLEAN CO` covers `Clean Co Group LLC`. An excluded vendor may carry its reason in parentheses; without one, the reason is the first paragraph of the subsection that names the vendor.
- `Missing-accrual months` (default 6), `Missing-accrual min months` (default 3) and `Missing-accrual floor` (default 1000) set the missing-accrual scan (below). Each is optional; a value that is not a number, a month count below 1, or a min months above the months is refused.
- "Posted entry contains" is matched without regard to case against the description of entries dated the last day of the period. Give every wording the entry has been posted under.

SYSTEMS.md, section `## Close inputs`, field lines; paths are relative to the period folder:

- `Ledger pull`: the folder holding the period's read-only pull: `headers-<yyyy-mm>.json`, `lines-<yyyy-mm>.json`, `ap-bill-lines-<yyyy-mm>.json` and `pulled.md` (each JSON is `{"meta": ..., "rows": [...]}` in the ledger's own field names). Default `work/source`.
- `Work folder`: where the build keeps its working files (the card CSV, the maps as JSON, the kit outputs). Default `work/accruals`.
- `Card report`: file name patterns for the card download in the period folder. Exactly one must match; several stop the build, which then needs `--card-report FILE`.
- `Card report sheet` and `Card report columns`: passed to `card-export` as `--sheet` and `--column key=Header` when the export is not the default layout.

## Already done?

`scripts/accruals.py done` answers from the data first, then the folder, and always says why:

| State | Meaning | Evidence it prints |
|---|---|---|
| `posted` | An entry dated the period's last day, not a reversal, whose description matches, is posted in the ledger pull | the JE key, description, debits and the date it was entered |
| `entered` | The same, but the ledger holds it as a draft or submitted | the JE key and its state |
| `file` | No such entry, and an import file for the accrual is already in the period folder | the file names and the pull's date |
| `not-done` | Neither | what was searched and the pull's date |

The ledger pull is a snapshot: `not-done` means "not in the ledger as of the pull's date". The pull's date is always part of the evidence.

## What the build does

`scripts/accruals.py build` runs the done check first and stops at `already-done` unless `--ignore-done`. Then it looks for the inputs:

- credit-card accrual: one card report in the period folder;
- post-cutoff vendor accrual: the AP bill lines of the next month's pull, and the period's and the prior months' AP bill lines for the estimates (Trailing months, default 3).

A missing input ends the build with exit 4 and the question to ask. With the inputs found it runs the toolbox commands `card-export`, `cc-accrual` or `service-period-accrual`, then `je-import --state Posted` and `python3 ~/.claude/skills/month-end-journal-entry/scripts/je_import_check.py --state Posted` (a person uploads the file, and that upload is the human review; agents never upload or post), and writes the import file into the period folder (or into `--out` on a trial run). It never overwrites a file: one already there is a refusal (exit 3), and the done check normally finds it first.

It also lists `possible_overlaps`: each account in the draft that another entry dated month end, crediting the liability account, already touches, with that entry's lines and any line naming a draft vendor. The other accrual of this skill is not counted (the card statement vendor is excluded from the vendor accrual). An overlap is a question, not a correction.

Every vendor build also runs the missing-accrual scan (next section) and writes its backup, `<import file name without .csv> backup.md`, beside the import file: the draft's source and the scan's tables with each decision.

For the credit-card accrual the build also writes, and returns:

- `department_reconciliation`: where each row's department came from (`by_source`), every cardholder whose column department differs from the people map's with rows, amount and the one used (`disagreements`; a cardholder missing from the map counts), every unknown label (`unknown_labels`) and every blank (`blanks`), with the fallback each took;
- `card-coding-<yyyy-mm>.csv` in the work folder (`coding`): one line per card row with its source columns, its department and account, and where each came from (`column`, `people map`, `mcc NNNN`, `merchant override PATTERN`, `unmapped`);
- `tie_out`: the card rows' total against the coded rows, the entry's net expense lines and the offset credit, with `ties`;
- the backup, `<import file name without .csv> backup.md` beside the import file: source, tie-out, the department reconciliation, unmapped merchants and the overrides applied. The workstream adds its judgment below; the build never rewrites it;
- `ready`: false when any row's department came from a fallback or an unknown label, a queue is not empty, the tie-out fails or the lint fails. A draft that is not ready is not uploaded.

## The missing-accrual scan

The post-cutoff accrual finds bills that arrive after the cutoff. The scan finds the vendors that send nothing at all: every vendor whose expense recurs in the ledger history and has nothing booked or billed for the period.

- **History.** The AP bill lines of the `Missing-accrual months` pulls before the period (each month's `ap-bill-lines-<yyyy-mm>.json`), expense lines only (the expense account prefixes), totalled by vendor and month. A month without a pull is listed under `history.missing`.
- **In scope.** A vendor whose expense was at or above `Missing-accrual floor` in at least `Missing-accrual min months` of those months. An arrears vendor is always in scope, whatever the thresholds. An excluded vendor never is: it is listed under `excluded` with its reason.
- **Booked or billed.** Searched for each vendor in scope, in the period:
  - an AP bill dated in the period (for an arrears vendor, a bill whose memo names the period, since its other bills are the month before);
  - a line of this build's draft (a next-month bill, or an arrears estimate);
  - a GL line in the period on an expense account or the liability account whose description names the vendor, reversals left out (an accrual already in the ledger);
  - a row of an import file (CSV) in the period folder or its `journal-entries/`, by its MEMO.

  A name counts when its first word (legal suffixes such as LLC and INC left out) appears as a word and no other vendor in the history shares that word, else when every word of it appears.
- **Flagged.** A vendor in scope with none of these. Each is a proposal: the months seen, the typical amount (the median of the months seen), the last month seen, the accounts and departments it usually hits with their shares, the evidence searched, and the proposed amount (the typical amount).

The scan never drafts a flagged vendor on its own. The arrears estimate is the exception, and it comes from the build, not the scan. The worker decides each flagged vendor and passes the decisions with `--decisions FILE`:

```json
{"decisions": [
  {"vendor": "STEADY JANITORIAL", "accrue": true, "reason": "monthly contract; no August bill yet"},
  {"vendor": "MAPLE LEGAL", "accrue": false, "reason": "matter closed in July"}
]}
```

`vendor` is the flagged name (case does not matter), `accrue` true or false, `reason` required, `amount` optional (default the proposed amount). An accepted vendor is drafted into the vendor accrual's import file at that amount, allocated across the accounts, departments and locations its history hit, each line's memo saying `ESTIMATE, missing accrual`. A decision for a vendor the scan did not flag, or one without a reason, is an error (exit 2).

Until every flagged vendor has a decision, the build writes no import file: it ends `waiting` (exit 4) with the question in `inputs.missing` and the findings in `missing_accrual` and `work/missing-accrual-<yyyy-mm>.json`. `accruals.py scan FOLDER --period P` runs the scan on its own and writes nothing, counting the draft as cover when the next month's bills are pulled. The scan's findings are in every vendor result (`missing_accrual`), whatever the outcome; when the next month's bills are not pulled, its `note` says the draft was not counted, so an arrears vendor shows as flagged until it is.

Outcomes and exit codes:

| Outcome | Exit | Meaning |
|---|---|---|
| `already-done` | 0 | the done check found it; nothing written |
| `built` | 0 | the import file is written and passes the lint; `needs_review` is true when a queue, a department gap, an estimate or an overlap needs a person's eye, and `ready` says whether the card draft may be uploaded |
| `nothing-to-accrue` | 0 | the inputs were there and nothing belongs to the period; no file |
| `waiting` | 4 | an input is missing, or a vendor the missing-accrual scan flagged has no decision; `inputs.missing` holds what was looked for and the question |
| `lint-failed` | 1 | the file was written and fails `je-import-check`; nobody uploads it |
| `failed` | 1 | a command failed; its message is in `detail` |
| `refused` | 3 | the folder is not set up, or the file is already there |
| `error` | 2 | a bad argument or a command script not found |

## How a caller records each outcome

This skill writes no status or log. The caller records each outcome. In a month-end close that is the orchestrator: an evidence row with `month-end-record` (test `entries`, item `cc-accrual` or `vendor-accrual`), and the workstream's row in the month's STATUS.md:

| Outcome | Evidence state | Evidence | Note |
|---|---|---|---|
| `posted` | booked | the JE key | "posted as JE n, debits x, entered yyyy-mm-dd" |
| `entered` | waiting | the JE key | "JE n in the ledger as draft; waiting for a person to post" |
| `file` | drafted | the import file | "draft ready to upload; not in the ledger pull of yyyy-mm-dd" |
| `built` | drafted | the import file | lines, total, lint PASS, `ready`, every gap the build reported, and for the vendor accrual each flagged vendor with its decision |
| `nothing-to-accrue` | not-needed | the done-check evidence | the summary |
| `waiting` | waiting | none | the missing input and its question |

An overlap, an estimate or a card draft that is not ready keeps the entry waiting until its question is answered.

## Questions

Run on its own, the skill asks through comms-confirm. The role comes from the folder's BACKGROUND.md (`- Controller: Name <address>`). While questions relay through the owner, the channel is `owner`, which with no one present becomes a task on the owner's list. Called by an orchestrator, it returns the questions instead. Either way, an accrual is never built on an assumption about a missing input.

## External commands

The script ships inside this skill's folder; comms-confirm's script ships with the `comms-confirm` skill. Nothing is on PATH. `accruals.py` runs `card_export.py`, `cc_accrual.py` and `service_period_accrual.py` beside it, and `je_import.py` and `je_import_check.py` from the `month-end-journal-entry` skill as `python3 ~/.claude/skills/month-end-journal-entry/scripts/<name>.py` (`ACCRUALS_SKILLS_DIR` replaces `~/.claude/skills` for tests). Standard-library Python 3.8 or later for the scripts.

- `python3 scripts/accruals.py`
- the `comms-confirm` skill's `scripts/confirm.py`
