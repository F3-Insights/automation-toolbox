---
name: board-package-workstream
description: Reference loaded by board-package-writer and board-package-orchestrator, not for a user request; adds to orchestration-workstream. Covers the company's BOARD-RULES.md first, the period's sources from sources.json, the deck spec board-package-render builds, and the figure ledger in which every figure names its source (the results file, the closed trial balance, a calculation over other figures, or a person) so board-package-tieout can tie it. For a board package, start board-package-orchestrator.
---

# Board package workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill if it is not loaded. What follows is only what a board package adds.

A board package reports a closed month to the people who invest in the company and govern it. Its one non-negotiable is that every number in it is the closed books' number. The tools make that provable: you name where each figure comes from, and `board-package-tieout` recomputes it.

## Conduct here

- **The rules first.** The company's `BOARD-RULES.md` (its path is in your brief and in `sources.json` as `rules_file`) names the files, the folders, what you may write and what the package contains. It overrides this skill.
- **Already done?** `sources.json` says whether a person already made this period's package (`people_package`) and which package files exist. A person's package is theirs: report it and stop.
- **The results file is the narrative's source; the trial balance is the books.** Figures come from the month's results file (its table figures are in `work/results-figures.csv`, by metric) or the closed trial balance pull. When the two disagree, the package does not choose: it is a finding and a question for the owner.
- **Never make a figure tie.** A figure that does not tie is reported, never re-printed to match and never given a looser source.
- **Earlier drafts are kept.** Revise the deck with `python3 ~/.claude/skills/board-package-workstream/scripts/board_package_render.py ... --supersede
  <work folder>`; before rewriting the script or the cover email, save its current text under
  `work/superseded-<stamp>/` with the same name.
- **No bookkeeping.** The evidence file, `LOG.md` and `CONFIRMATIONS.md` are the orchestrator's.

## The sources

`work/sources.json` (and `work/sources.md` for reading) holds the close's state, the trial balance pulls (this period and the one before), the results file and its figures, the supporting files (variance files, the executive commentary draft), the newest earlier packages for the format, the deck template, and the path of every package file.

## The deck spec

Write the deck as JSON at `work/deck-spec.json` and build it with `python3 ~/.claude/skills/board-package-workstream/scripts/board_package_render.py work/deck-spec.json --out "<deck path>" --template "<template>"` (add `--supersede <work folder>` for a revision). The spec is a `slides` list; each slide has a `title` and any of `bullets` (a nested list is the level below), `table` (`columns` and `rows` of strings, printed exactly as given) and `notes`. `layout: title` makes a title slide with a `subtitle`. The renderer formats nothing, so write each figure exactly as it should read (`951`, `(74)`, `$1.2M`, `40.2%`), and give each table its unit in its first header cell (`$k`).

## The figure ledger

`work/package-figures.csv`, columns `id,file,location,printed,unit,metric,source,note`. Start it with `python3 ~/.claude/skills/board-package-workstream/scripts/board_package_figures.py <deck> <script> <cover email> --ledger --out work/package-figures.csv`, which lists every figure printed in those files with its place, then fill in `source` for each row (and `unit` where a bare number's unit is not its table's). Every figure printed anywhere in the package needs a row; `board-package-check` counts them slide by slide, so a figure added to the deck after the ledger was started needs its row too.

| Source | The figure is |
|---|---|
| `results:<metric>` or `results:R12` | the results file's figure, by its metric in `results-figures.csv` (`Revenue \| ACT`) |
| `tb:<accounts>` | the closed trial balance's ending balance, summed (`10400-10999`, `10400, 10600`) |
| `tb-month:<accounts>` | the month's activity (this period's year-to-date less the prior period's) |
| `tb-ytd:<accounts>` | the year-to-date activity |
| `calc:<expression>` | arithmetic over other figures by id (`calc:(F6-F9)/F6*100`, a margin in percent) |
| `text:` | an amount the results file prints in its prose |
| `person:<who and where>` | stated by a person, not in the books (a case count); the orchestrator names it in the review note |

A leading `-` negates (`-tb-month:40000-49999`: revenue is a credit in the ledger). Source the actual column of the headline table, cash and the balance sheet from the trial balance, and budget, forecast and variances from the results file, so the package proves the results file against the books as it goes. A helper row (a value a `calc:` needs that the package does not print) leaves `file` blank.

`python3 ~/.claude/skills/board-package-workstream/scripts/board_package_tieout.py COMPANY --period P --period-dir DIR` shows what ties; it writes the tie-out ledger beside the package and exits 1 on any figure that does not.

## The return here

The shared block. `files` lists every file written. `findings` carries each figure that does not tie because the results file and the books disagree (the figure id, both amounts, the accounts), and anything material the board should not be surprised by. `questions` carries what only the owner can decide: which number the board sees when the results file and the books disagree, a figure only a person can state, a page the rules leave open. `extra` carries `{"deck_spec": "...", "ledger": "...", "tieout": "ALL TIE" or the failing ids}`.
