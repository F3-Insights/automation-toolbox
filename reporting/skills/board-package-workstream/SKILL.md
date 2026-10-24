---
name: board-package-workstream
description: "The job skill of reporting-board-package, not for a user request: one company's monthly board package from its finished close. Covers BOARD-RULES.md first, the period's sources, drafting the deck, script and cover email, the figure ledger that sources every figure for reporting-board-package-tieout, the close-gate and results-file contracts with accounting, the reviewer's checklists Check the numbers and Read the deck cold, and the owner's review request. Done is reporting-board-package-check. Never sends. For a board package, start reporting-board-package."
---

# Board package workstream

This skill extends `orchestration-workstream`: keep its conduct. Load that skill if it is not loaded. What follows is what a board package adds.

A board package reports a closed month to the people who invest in the company and govern it. Its one non-negotiable is that every number in it is the closed books' number. The tools make that provable: you name where each figure comes from, and `reporting-board-package-tieout` recomputes it.

## Inputs

- **Company** (required): the company's Context name. Its rules folder holds `BOARD-RULES.md`; its close folder is the Month-End folder (read only); its package folder is the Reporting folder.
- **Period** (optional): `yyyy-mm`. Default: the month before today.
- **Instructions** (optional): the owner's notes for this package (a combined two-month catch-up, a page to add). They override the defaults here, never the rules file.
- **The pack's first line**: `reporting-board-package-pack` ran before the session. `READY:` means work; `ALREADY:` means a person made this period's package; `NOT READY:` means the close or the results file is not there yet. `work/sources.json` names the period folder (`period_dir`): pass `--period P --period-dir DIR` to every board-package command so a dry run and a live run work the same way.
- **Dry run** (optional): the pack put the period folder inside the Run folder; draft and review there, and make no `comms-confirm` request and record no exception.

## Steps

1. [script] Run `reporting-board-package-check COMPANY --period P --period-dir DIR --format json` and read the rules, `work/sources.md`, the last entries of `work/LOG.md` and `work/CONFIRMATIONS.md`. An answered question is input to this session.
   → the pack said ALREADY or NOT READY: stop
   → every test met: done
2. [judgment] Draft the package (section Draft the package): the deck through `reporting-board-package-render`, the commentary script, the cover email, and the lender pack where the rules keep one, with any review findings answered.
3. [script] Start the figure ledger with `reporting-board-package-figures ... --ledger --out work/package-figures.csv`, source every row, and run `reporting-board-package-tieout COMPANY --period P --period-dir DIR`.
   A figure that does not tie because the results file and the books disagree stays failing and becomes a question at step 6.
   → a figure printed or sourced wrong: step 2 (max 1)
4. [hand-off: reporting-reviewer] Check the numbers (section Check the numbers) with the package files and their sources only. Write its return to `work/finance-review.md` and record it with `reporting-board-package-record COMPANY review --kind finance --state passed|failed --file work/finance-review.md`.
   → FAIL: step 2 (max 2)
5. [hand-off: reporting-reviewer] Read the deck cold (section Read the deck cold) with the deck alone and the one-line purpose. Write its return to `work/redteam.md` and record it with `reporting-board-package-record COMPANY review --kind redteam ...`.
   → FAIL: step 2 (max 2)
6. [ask] Write the review note (section The review note) and make one review request through `comms-confirm` (section Ask the owner). A figure that does not tie because the results file and the books disagree is one numbered question there, and the figure stays failing until the owner answers.
   → dry run: step 7
7. [script] Write the session's `LOG.md` entry, run `reporting-board-package-check` last and report its result test by test.
   → written: done

After two review rounds, what is still failing is a question for the owner, never a third round. After a fix, both reviews run again.

## Done is computed

`reporting-board-package-check COMPANY --period P --period-dir DIR --format json` decides, test by test:

1. **close**: the close is done by the rules' Close gate, and the trial balance pull is there.
2. **results**: the results file is found and its figures are read.
3. **files**: the package files the rules name exist, with no placeholder left.
4. **figures**: every figure printed in the package has a ledger row with a source.
5. **tieout**: every figure ties (or carries an exception the owner approved), every figure a person stated is named in the review note, and the tie-out ledger is current.
6. **review**: the numbers review passed after the last change.
7. **redteam**: the cold read passed the deck after its last change.
8. **prose**: no banned character or phrase.
9. **owner**: the owner's review request is in `work/CONFIRMATIONS.md`.

Run it at the start and last. Report its result, never your own view of it.

## The close gate and the results file (contracts with accounting)

Two files and one command cross into accounting, and nothing else does.

- **The Close gate.** `BOARD-RULES.md`'s `Close gate` is `month-end-check` (the default) or `attested`. With `month-end-check`, the pack and the check run accounting's command `accounting-month-end-check <close folder> --period P --format json` (found on PATH, else accounting's script in this toolbox checkout) and read `done`, `met` and the names of the tests not met from its JSON. With `attested`, a period is closed when the rules' `Closed by hand` list names it.
- **The results file.** The month's results memo the close produces, found by the rules' `Results file` glob in the close's month folder. Its table figures are read into `work/results-figures.csv` by metric. The board package reads it and never writes it; how it is written is accounting's.

## Conduct here

- **The rules first.** `BOARD-RULES.md` (its path is in `sources.json` as `rules_file`) names the files, the folders, what may be written and what the package contains. It overrides this skill.
- **Already done?** `sources.json` says whether a person already made this period's package (`people_package`) and which package files exist. A person's package is theirs: record that in `LOG.md` and stop.
- **The results file is the narrative's source; the trial balance is the books.** Figures come from the results file (`work/results-figures.csv`) or the closed trial balance pull. When the two disagree, the package does not choose: it is a finding and a question for the owner.
- **Never make a figure tie.** A figure that does not tie is reported, never re-printed to match and never given a looser source.
- **Earlier drafts are kept.** Revise the deck with `reporting-board-package-render ... --supersede <work folder>`; before rewriting the script or the cover email, save its current text under `work/superseded-<stamp>/` with the same name.
- **You alone keep the books of the session**: `LOG.md`, the review note, `finance-review.md`, `redteam.md`, and the evidence file through `reporting-board-package-record`.
- **Authority.** New files only, in the period folder and its `work/`. Never send anything to the board, investors or lenders; never upload; never post to the ledger; never edit, move or delete a person's file; never change a figure to make it tie.
- One command per call, with no pipes, redirects, `&&` or variables.

## The sources

`work/sources.json` (and `work/sources.md` for reading) holds the close's state, the trial balance pulls (this period and the one before), the results file and its figures, the supporting files (variance files, the executive commentary draft), the newest earlier packages for the format, the deck template, and the path of every package file.

| Path | Holds |
|---|---|
| `BOARD-RULES.md` (the company's rules folder) | What the package is, its files, authority, done |
| `<period folder>/` | The package files, the review note and the tie-out ledger |
| `<period folder>/work/` | `sources.json`, `results-figures.csv`, `deck-spec.json`, `package-figures.csv`, `BOARD-EVIDENCE-<p>.csv`, `finance-review.md`, `redteam.md`, `CONFIRMATIONS.md`, `LOG.md` |

## Draft the package

Run by the main agent. Done means a package the owner could send after one read, in the format of the company's earlier packages, in which every figure ties to the closed books, proven by `reporting-board-package-tieout`, not by your care. Use `report-tieout` for the arithmetic of agreement and `unslop-deliverable` for every word.

1. Read the rules file, `work/sources.md`, the results file in full, the supporting files and the newest earlier package (`powerpoint-handler --ppt-file <deck> --output-format markdown` reads a deck; a PDF reads directly). Note the earlier package's pages, their order, how it rounds and what it calls things; the new package follows it unless the rules or the instructions say otherwise.
2. Draft the deck spec and render it on the template. Lead with the results: the headline table (actual against budget and forecast), revenue by entity and bucket, the EBITDA walk, cash, the KPIs the results file carries, the variance story in the results file's words and order, and the forecast page the rules ask for. Full-sentence slide titles that state the finding. Speaker notes on every content slide.
3. Write the commentary script (about three minutes spoken, the same figures as the deck, no new ones) and the cover email (short; what is attached, the headline, what the board is asked to note).
4. Start the figure ledger from the files, source every figure, and run the tie-out. A figure you printed or sourced wrong, fix and run again. A figure that does not tie because the results file and the trial balance disagree is a finding and a question, never a fix.
5. When review findings came back, answer each one: change the package, or say in the review note why not.

## The deck spec

Write the deck as JSON at `work/deck-spec.json` and build it with `reporting-board-package-render work/deck-spec.json --out "<deck path>" --template "<template>"` (add `--supersede <work folder>` for a revision). The spec is a `slides` list; each slide has a `title` and any of `bullets` (a nested list is the level below), `table` (`columns` and `rows` of strings, printed exactly as given) and `notes`. `layout: title` makes a title slide with a `subtitle`. The renderer formats nothing, so write each figure exactly as it should read (`951`, `(74)`, `$1.2M`, `40.2%`), and give each table its unit in its first header cell (`$k`).

## The figure ledger

`work/package-figures.csv`, columns `id,file,location,printed,unit,metric,source,note`. Start it with `reporting-board-package-figures <deck> <script> <cover email> --ledger --out work/package-figures.csv`, which lists every figure printed in those files with its place, then fill in `source` for each row (and `unit` where a bare number's unit is not its table's). Every figure printed anywhere in the package needs a row; `reporting-board-package-check` counts them slide by slide, so a figure added to the deck after the ledger was started needs its row too.

| Source | The figure is |
|---|---|
| `results:<metric>` or `results:R12` | the results file's figure, by its metric in `results-figures.csv` (`Revenue \| ACT`) |
| `tb:<accounts>` | the closed trial balance's ending balance, summed (`10400-10999`, `10400, 10600`) |
| `tb-month:<accounts>` | the month's activity (this period's year-to-date less the prior period's) |
| `tb-ytd:<accounts>` | the year-to-date activity |
| `calc:<expression>` | arithmetic over other figures by id (`calc:(F6-F9)/F6*100`, a margin in percent) |
| `text:` | an amount the results file prints in its prose |
| `person:<who and where>` | stated by a person, not in the books (a case count); the review note names it |

A leading `-` negates (`-tb-month:40000-49999`: revenue is a credit in the ledger). Source the actual column of the headline table, cash and the balance sheet from the trial balance, and budget, forecast and variances from the results file, so the package proves the results file against the books as it goes. A helper row (a value a `calc:` needs that the package does not print) leaves `file` blank.

`reporting-board-package-tieout COMPANY --period P --period-dir DIR` shows what ties; it writes the tie-out ledger beside the package and exits 1 on any figure that does not.

## Check the numbers

For `reporting-reviewer`. Load `review-numbers` and follow its checklist over the package files (deck, script, cover email, lender pack), with these sources only: the results file, the trial balance pulls, `work/results-figures.csv`, the tie-out ledger (`tieout-ledger-<p>.csv`, which `report-tieout` reads) and the newest earlier package. Never the drafting notes or the deck spec's reasoning. Added lines:

1. Every figure in the deck, the script and the cover email that names the same metric and period agrees across the three at the precision printed.
2. Every `person:` row is a figure a person stated; it is listed under Not checked, never treated as tied.
3. Every exception the evidence file records as approved is a figure the review note names.

Return `review-numbers`'s block. The main agent writes it to `work/finance-review.md`.

## Read the deck cold

For `reporting-reviewer`. Load `review-red-team` and read the deck alone, as a member of the board reading it the night before the meeting, with the purpose "the monthly financial package the board reads before it meets". No sources, no notes, no earlier versions. Return `review-red-team`'s block; PASS when every section meets its bar and every blocking fix is made. The main agent writes it to `work/redteam.md`.

## The review note

Its name is in the rules. Write: what the package says in three lines, the tie-out result, every figure stated by a person by its id, every exception and open question, what the reviewers changed, and what the owner must decide before sending.

## Ask the owner

One review request through the `comms-confirm` skill, store `work/CONFIRMATIONS.md`, asked of the owner, as a task: `confirm new work/CONFIRMATIONS.md --question "Review the <period> board package and <review note>; record or waive the video; send it" --of owner --channel task --due <date> --by reporting-board-package`, then (not on a dry run) `confirm task work/CONFIRMATIONS.md <id>`. A figure that does not tie because the results file and the books disagree is one numbered question in that request: which number the board sees. The owner's answer becomes an exception (`reporting-board-package-record COMPANY exception --figure F12 --evidence CR-... --note ...`), or a corrected results file and a new pack. The upload to the investor portal is the owner's to assign after approval.

## The LOG entry

`## yyyy-mm-dd HH:MM by reporting-board-package`, then `- Done:`, `- Files:`, `- Decisions:`, `- Open:`. Write a line before each review dispatch and record each return at once, so a session that stops part-way can be resumed by the next.

## When no one is present

Every step runs the same. Questions go on the owner's task list through `comms-confirm`, never asked live. End with `needs_owner` only for a decision that blocks the whole package and only the owner can make. Report the check's result test by test, the figures by tie-out state, and the figures that need the owner.
