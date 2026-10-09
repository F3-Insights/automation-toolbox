---
name: forecast-method
description: "How a forecast is revised, bridged and defended, and what each forecast worker writes: hypotheses with numbers before looking, the driver tree and when to zoom, the citation rule, questions with owners and fallbacks, a prior-to-new bridge that foots to the dollar, corrections apart from business changes, the executive-summary contract, versions as submissions, workbook hygiene, and the Forecast folder with every worker file's shape and what forecast-check counts. Use for any forecast revision, reforecast or bridge, with or without forecast-orchestrator, and when a forecast or budget agent needs the folder layout and file shapes. Not for an annual budget (budget-method) or 13-week cash (cash-forecast-method)."
argument-hint: "[Forecast folder] [vintage]"
allowed-tools: Read, Glob, Grep, Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_extract.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_bridge.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_sense_check.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_score.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_check.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_prepare.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_revise.py:*), Bash(python3 ~/.claude/skills/forecast-method/scripts/forecast_record.py:*)
---

# The forecast method

A forecast is worth what its owner can defend. Every number in a new forecast either sits where it sat in the last one or has a reason someone can check. This is the method behind `forecast-orchestrator`; it holds for any company. What is true of one company only (its workbook layout, its chart of accounts, its bridge lines and owners, who may be asked what) lives in its Forecast folder: `FORECAST-RULES.md`, `FORECAST-SETTINGS.yaml`, `modules.yaml`, `driver-tree.yaml`.

The arithmetic is never done by hand. `forecast-extract` reads a workbook into a footed grid, `forecast-bridge` walks prior to new, `forecast-sense-check` flags what needs explaining, `forecast-score` scores the hypotheses, `forecast-check` says whether the vintage is done. Judgment goes into the files those tools read: the hypotheses, the reasons, the flag answers, the summary. The folder, the shapes of those files and the return a worker gives are in `contract.md` in this skill.

## Working as a forecast worker

A worker dispatched by `forecast-orchestrator` or `budget-orchestrator` keeps `orchestration-workstream`'s conduct and returns its block (load it by name if it is not loaded), reads `contract.md` for the folder, its file's shape and the return's item tests, and adds:

- **Read the rules first.** `FORECAST-RULES.md` in the Forecast folder says what you may do, who may be asked what, and the limits. It overrides your own instructions.
- **Workbooks are read, never saved.** Read a workbook through `forecast-extract` or the vintage's extracts; never open one for writing. A rolling vintage's workbook is written only by `forecast-revise`, from your `proposals.json`.
- **Your files, not state.** You write the work product your brief names in the vintage folder. You never write `STATUS.md`, `LOG.md`, the evidence ledger (`FORECAST-EVIDENCE-<vintage>.csv`), `bridge.json`, `flags.json` or `scores.json`: the orchestrator and the tools do.
- **Already done?** Each file you are asked for may already exist from an earlier session. Read it and the latest `python3 ~/.claude/skills/forecast-method/scripts/forecast_check.py FOLDER --vintage V --format json` first; change only what the check or the reviewer says is wrong. A file that is already right is returned as it is.
- **Employees are never named** in anything a reader sees: roles, departments, counts.

## Hypotheses before evidence

Before anyone opens the new forecast, write what you expect each bridge line to do in this vintage and by how much, in EBITDA terms, with a confidence and one sentence of why, plus each year's expected EBITDA. Work from what is known before looking: the last bridge, the change requests, the closed month, the calibration log of earlier misses.

- **Never edit a hypothesis after looking.** A miss is the vintage's most valuable output. Moving the expectation to match what you found destroys the only record of whether this forecast can be trusted; `forecast-check` refuses hypotheses that changed after they were recorded.
- **A miss beyond tolerance owes a deep dive**: why the expectation was wrong, not a restatement of the new number. "Expected a two-quarter slip; the signed contracts put both new distributors one quarter out" is a deep dive. "Revenue came in lower than expected" is not.
- **Three drivers, always.** Every change decomposes into revenue, variable cost and overhead. If you cannot say which of the three a change belongs to, you do not understand it yet.
- **Signs, once.** Workbook amounts are revenue positive, costs positive. Every change, hypothesis and bridge line is in EBITDA terms: spend going up is negative.

## Which forecast is the prior

- Name the prior explicitly and reconcile its copies. A board workbook and the accounting-system upload of the same vintage can differ by rounding; a board slide can differ from its own source workbook by a presentational double count. Bridge from the **model**, never from a slide, and explain any deck gap in one paragraph.
- State the basis, pre-bonus or post-bonus EBITDA, and hold it throughout. The same forecast has two headline numbers either side of the bonus accrual and people quote both.
- When the accounting system keeps a live forecast id and dated history ids, compare vintages on the dated id.

## The driver tree: where to look, when to stop

A bridge line (a module) is a set of accounts, an owner, a materiality and a subtree of the driver tree, all at once.

1. Start at the line and compare it with the prior.
2. Where the change trips a node's `zoom_when` (an amount or a share), descend to its `zoom_to` level: account, then customer, employee or department.
3. Stop when the next level down would not change the explanation.
4. Say the driver in one phrase: "new warehouse opening moved a quarter later", "two sales hires brought forward", "renewal booked twice". If it will not fit in a phrase, it is not found yet.
5. Cite it. Above the line's materiality, every reason carries an evidence id (`E-nnn`, from the vintage's evidence index: the revision's change log, the requests, the files) or a question id (`Q-nnn`). With neither, the number has not earned its place: say so and ask.

Favourable and unfavourable get equal suspicion. Revenue that rises with no named cause is as suspect as cost that rises with none. Last vintage's forecast is the baseline, not the enemy: explain what moved and why, not what you would have done differently.

## The bridge

- **Positive is favourable to EBITDA.** Prior, then closed months restated (should be zero), then the months that became actual since the prior, then one line per bridge line over the forecast months, then the accounts no line claims, then new. `forecast-bridge` builds it so every line's accounts sum to the line, the lines sum to the change, and the quarters' changes sum to the year's. The extract ties to the workbook's own revenue and EBITDA rows month by month and checks the sheet's own "must be zero" rows.
- **Corrections apart from business changes.** Each line's reason has a kind: `business` (the outlook changed), `correction` (the model was wrong), `timing` (the same thing in another month), `new-data` (an actual or a new source replaced an estimate), or `mixed` with a detail for each part. A reader must never take a bug fix for a profit swing, or the reverse.
- **About six details explain almost any line.** List offsetting increases separately so the net is honest; detail amounts sum to the line.
- **Split the walk by quarter and by revenue category,** and explain revenue on the dimensions the company plans on (entity, account, class).
- **Say what is not in the revision.** When costs are still at the prior plan, the cost lines show no change by construction, and the losses that follow are revenue reductions on an unrevised cost base, not a view of profitability. Write that sentence.
- **Unclaimed is a finding.** An amount on accounts no line claims, beyond materiality, means the bridge lines need a change: propose it for `modules.yaml`.

## What the sense checks mean

`forecast-sense-check` flags, it never judges: a forecast month far off its run rate, a revenue account below zero or a cost against the sign, a month-on-month swing, a closed month that moved, a workbook that does not foot or tie, an unclaimed amount, a hypothesis missed. Each material flag gets one answer: **explained** (the cause, with evidence), **revised** (the model was wrong; what changes and who changes it), or **open** (who owns it and the question that will settle it).

Patterns worth checking every time:

- **Reach-back ranges.** A formula that adds earlier months' activity (orders, starts, renewals) must reach back exactly as far as the business logic says. Check the range against the stated lag, and look at the first month where the formula grows an extra term.
- **Missing formulas.** One hard-coded or empty cell in a formula row can partly offset an error elsewhere and hide it.
- **Rectangle sums.** A row total whose range covers a block instead of its own row double counts. Display-only cells never feed the upload, but they are what a reader sees.
- **Month headers.** A copied tab can carry a duplicated or shifted month heading; the extract fails rather than silently drop a month.
- **A negative revenue posting in a closed month** is usually a reversal, not a trend. Find the entry before forecasting off it.
- **Favourable SG&A is not savings until named**: unfilled headcount, a posting artefact, a credit, a mis-mapping that carries into the forecast months. Contractors converted to employees, allowances already in the plan and one-off increments are the usual confusions; check an increment is not both its own line and inside the run rate.
- **Personnel**: headcount by department against plan first; benefits follow headcount with a lag; check that any accrual split across functions (bonus, commission) is not counted in more than one place.
- **Actuals**: load closed months from the trial balance by dimension when GL detail lags, and label preliminary months. A tab's name says nothing about how current it is; the freshest source is the one with a date.
- **Upload sheets**: one row per account, department, location and class, fed by values; an empty dimension may carry a placeholder token so lookups never depend on empty cells; the budget id is set on every row.

## Questions

A question exists because a number depends on something only a person knows.

- It names its owner (a role, never a department), its due date and the **fallback assumption** used if nobody answers. A question never stalls the forecast: on expiry the fallback is the forecast, recorded as an expiry, never as an answer, and the summary says so.
- One question per item, the fallback stated in it: "If I do not hear by Thursday I will assume both contracts slip to the first quarter" gets answered; "any update?" does not.
- Ask for the fact, not the number: "Are these two contracts signed for January?", not "is December revenue $100k?" Never put a ledger figure in the message.
- Below the materiality floor the fallback is the answer; do not spend someone's attention on it.
- Questions are batched: the rules file says how many messages a week the model's owner may get (one, by default), and they go through `comms-confirm`, relayed by the owner. Nothing sent may read as coming from a person.
- A question open two vintages running is no longer a question. It is an assumption: write it down as one.

## The executive summary

Eight things, in this order, and nothing else:

1. **The headline**: FY EBITDA on the basis, new against prior, in $k.
2. **The shape of the change**: where in the year it falls, by quarter.
3. **The walk**: point to the bridge; never restate or round it differently.
4. **Top drivers** (`## Top drivers`): the three biggest lines, each with its amount and one sentence of cause.
5. **What would change it** (`## What would change it`): at least two real forks, not hedges.
6. **Anticipated questions** (`## Anticipated questions`): at least three, each with its answer.
7. **What we do not trust**: the data-quality flags and the fallbacks in use.
8. **The bottom line**: two or three sentences a reader could repeat.

Every figure comes from the bridge: `forecast-check` ties each `$` figure to a value the bridge carries. Money in $k to one decimal, negatives in parentheses, number first and cause after, one idea per bullet. Never name an employee: roles, departments, counts. Customers and vendors may be named. Nothing about how the forecast was produced (tools, agents, steps) reaches a reader.

## Versions are submissions

- A **version** exists only when the forecast is submitted or presented. Most months end at v1; a v2 exists only when management pushes back.
- An issued workbook is never edited. A revision is a new, dated file; the change log beside it is the audit trail.
- The prior for a vintage is the prior vintage's final, issued file.
- A rolling vintage the agents build is a values-only copy of the prior (`forecast-revise`): only forecast months change, closed months never, a formula cell is never overwritten, and the copy is the agents' working file until a person submits it.
- A workbook that uses features a library cannot round-trip (dynamic arrays, for example) is never saved by a library. A person builds that revision; the agents bridge it.
- After any programmatic write: keep cached values, confirm every content type and relationship target resolves, and reopen the file. Excel's repair dialog is the failure no one sees from here, so the integrity check stands in for it.
- Keep sheet names and the bridge's sheet layout stable between revisions; a renamed sheet or driver breaks the extract and the log. The extract refuses rather than guesses.

## Done

`python3 ~/.claude/skills/forecast-method/scripts/forecast_check.py FOLDER --vintage V` computes it: extracts that tie, hypotheses recorded first and never edited, a bridge that re-derives and foots, a cited reason for every material line, every material flag answered, the hypotheses scored, a summary that ties, every question closed, a reviewer's PASS on the current bridge and summary, the weekly message limit kept, and the reviewed bridge filed beside the revision as a new file.
