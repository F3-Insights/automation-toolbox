---
name: forecast-method
description: "How a forecast is revised, bridged and defended, and the finance-forecast job's Steps: hypotheses before looking, the driver tree, the citation rule, questions with fallbacks, a bridge that foots, corrections apart from business changes, the executive summary, versions as submissions, and the Forecast folder's file shapes. Sections Write the hypotheses and Propose the rolling forecast (finance-worker), Answer the flags and Explain the bridge (finance-forecast), Check a vintage and Sign off the vintage (finance-reviewer). Use for any forecast revision or bridge. Not for an annual budget (budget-method) or 13-week cash (cash-forecast-method)."
argument-hint: "[Forecast folder] [vintage]"
allowed-tools: Read, Glob, Grep, Bash(finance-forecast-extract:*), Bash(finance-forecast-bridge:*), Bash(finance-forecast-sense-check:*), Bash(finance-forecast-score:*), Bash(finance-forecast-check:*), Bash(finance-forecast-prepare:*), Bash(finance-forecast-revise:*), Bash(finance-forecast-record:*)
---

# The forecast method

A forecast is worth what its owner can defend. Every number in a new forecast either sits where it sat in the last one or has a reason someone can check. This is the method behind `finance-forecast`; it holds for any company. What is true of one company only (its workbook layout, its chart of accounts, its bridge lines and owners, who may be asked what) lives in its Forecast folder: `FORECAST-RULES.md`, `FORECAST-SETTINGS.yaml`, `modules.yaml`, `driver-tree.yaml`.

The arithmetic is never done by hand. `finance-forecast-extract` reads a workbook into a footed grid, `finance-forecast-bridge` walks prior to new, `finance-forecast-sense-check` flags what needs explaining, `finance-forecast-score` scores the hypotheses and appends the calibration log (the one score that follows the forecast from vintage to vintage), `finance-forecast-check` says whether the vintage is done. Judgment goes into the files those tools read: the hypotheses, the reasons, the flag answers, the summary. The folder, the shapes of those files and the return a section gives are in `contract.md` in this skill.

## Inputs

- **Forecast folder** (required): the working folder, with `FORECAST-RULES.md` and `FORECAST-SETTINGS.yaml`.
- **Vintage** (optional): the folder under `vintages/`. Default: the vintage the prepare step opened (the newest issued revision) or the newest open one.
- **Instructions** (optional): the revision request (who asked for what) and anything the owner adds. They override the defaults here, never `FORECAST-RULES.md`. A request is evidence: save it as `vintages/<V>/request.md` before the hypotheses, and say so in the log.
- **Prepare line** (optional): when `finance-forecast-prepare FOLDER --vintage=V` ran before the session, its first line: `FRESH`, `STALE` (an extract does not foot or tie: work from it, say so, and answer the control flag) or `NOTHING` (no new revision: work the open vintage, or report that nothing is open).
- **Dry run**: orient and plan only (step 1 and the report).

## Steps

For `finance-forecast`. Run `finance-forecast-check` first and skip every step whose test already holds. Until step 3 has recorded the hypotheses, do not open the new workbook, `work/source/new.json` or the change-log items of `work/source/evidence.json` yourself: the hypotheses must be written by a context that never saw them, and `finance-forecast-check` cannot tell.

1. [script] Orient. Read the rules file (it overrides everything here), the settings, the bridge lines, the driver tree when present, the background and the root status, and for the vintage its VINTAGE.yaml, status, the end of its log and its confirmations (the folder is in contract.md); run `finance-forecast-check FOLDER --vintage V --format json`. On a dry run also run `finance-forecast-prepare FOLDER --dry-run` (never the real prepare) and go to the report.
   → dry run: step 13
   → no new revision and no open vintage: step 13
2. [script] Collect answers. Run `confirm check FOLDER/vintages/V`. Record each answered question with `finance-forecast-record FOLDER --vintage V --test questions --item Q-nnn --state answered --evidence "<ref>" --by finance-forecast`, and each past its due date as expired (its fallback stands), then close it with `confirm close` as the comms-confirm skill says.
3. [hand-off: finance-worker] Write the hypotheses (section Write the hypotheses), on opus, briefed with the pre-forecast paths only: `work/source/prior.json`, the previous vintage's `bridge.md` and `scores.json`, `calibration.jsonl`, `request.md`, and the evidence files that are requests rather than the new forecast. Never `new.json`, the new workbook or the change-log items. On its return run `finance-forecast-record FOLDER --vintage V --test hypotheses --item set --state written --by finance-worker` before anything else; the record refuses once a bridge exists, which is the point.
4. [hand-off: finance-worker] Rolling vintage only (`VINTAGE.yaml` says `kind: rolling`) and the new workbook not yet built: Propose the rolling forecast (section Propose the rolling forecast), on opus, briefed with the folder, the vintage, the closed actuals, the hypotheses and the answers.
   → not a rolling vintage, or already built: step 6
5. [script] Build it: `finance-forecast-revise FOLDER --vintage V`, then `finance-forecast-prepare FOLDER --vintage V` to extract what was built. A refusal (dynamic arrays, a closed month) is a question for the owner, not a workaround.
   → refused: step 9
6. [script] The numbers: `finance-forecast-bridge FOLDER --vintage V`, `finance-forecast-sense-check FOLDER --vintage V`, `finance-forecast-score FOLDER --vintage V`. A bridge that does not foot is a defect in the extracts or the settings; never adjust a number.
   → the bridge does not foot: stop
7. [judgment] Explain. Answer the flags (section Answer the flags) and Explain the bridge and write the summary (section of that name), yourself, from the evidence. A flag answered `revised` on a rolling vintage goes back to step 4 with the fix.
8. [script] Re-run `finance-forecast-bridge`, `finance-forecast-sense-check` and `finance-forecast-score` so the reasons attach and the scores are current, then `finance-forecast-check FOLDER --vintage V --format json`.
   → a test from extracts to summary still unmet: step 7 (max 1)
9. [script] Questions. Collect every question of steps 3 to 8; drop any below the rules' materiality floor (its fallback is the answer). Record each with `finance-forecast-record ... --test questions --item Q-nnn --state asked --note "<fallback>"`, ask each through `confirm new` and `confirm task` as the comms-confirm skill says, then send them as one batched message with `confirm relay`, recorded once with `finance-forecast-record ... --test messages --item <yyyy-mm-dd> --state asked`. Never more batched messages a week than the rules allow: if the week's message is spent, hold the questions and work on the fallbacks. Skip on a dry run.
10. [hand-off: finance-reviewer] Check a vintage (section Check a vintage), on opus, with the file paths only: the extracts, `hypotheses.json`, `scores.json`, `bridge.md`, `bridge.json`, `reasons.json`, `flags.json`, `flags-resolved.json`, `summary.md`, `evidence.json`, `proposals.json` when present, `FORECAST-RULES.md`. Write its return as `vintages/<V>/reviews/review <V> v<N>.md` (N one more than the last) and record it with `finance-forecast-record ... --test review --item vintage --state reviewed --review PASS|FAIL --review-file "reviews/<file>" --by finance-reviewer`.
   → FAIL on proposals.json: step 4 (max 2)
   → FAIL: step 7 (max 2)
11. [hand-off: finance-reviewer] Sign off the vintage (section Sign off the vintage), on fable, once every other test holds; the same paths, written and recorded as in step 10. Two FAILs running become a question for the owner.
   → FAIL: step 7 (max 1)
12. [judgment] File. After a PASS: write the reviewed `bridge.md` and `summary.md` as one new file in the delivery folder the settings name (`deliver_to`), named `<revision file stem> bridge.md`, never replacing anything; record it with `finance-forecast-record ... --test delivered --item vintage --state delivered --evidence "<path>"`.
13. [script] Close. Update the vintage's and the root STATUS.md (where it stands against the eleven tests, what waits on whom, the next action and its date), append the session to LOG.md (a heading "yyyy-mm-dd HH:MM by finance-forecast" with Done, Files, Decisions, Open), run `finance-forecast-check FOLDER --vintage V` last and report its result.
   → reported: done

With no one present the steps run the same: questions go on the owner's list through `comms-confirm` and the session carries on with the fallbacks. End with `needs_owner` only when `FORECAST-RULES.md` or `FORECAST-SETTINGS.yaml` is missing, or the extracts cannot be read at all.

## Working on a vintage

Whoever does a section (`finance-forecast` itself, `finance-worker` or `finance-reviewer`) keeps `orchestration-workstream`'s conduct, reads `contract.md` for the folder and its file's shape, and adds:

- **Read the rules first.** `FORECAST-RULES.md` in the Forecast folder says what you may do, who may be asked what, and the limits. It overrides your own instructions.
- **Workbooks are read, never saved.** Read a workbook through `finance-forecast-extract` or the vintage's extracts; never open one for writing. A rolling vintage's workbook is written only by `finance-forecast-revise`, from `proposals.json`. A person's workbook and any file in the delivery folder are never edited, moved or deleted.
- **One writer of state.** `finance-forecast` alone writes `STATUS.md`, `LOG.md`, `CONFIRMATIONS.md`, `request.md`, the review notes, the evidence ledger (`FORECAST-EVIDENCE-<vintage>.csv`, through `finance-forecast-record`) and the delivered file. The tools write the extracts, `bridge.json`, `flags.json` and `scores.json`. A worker writes only the file its section names.
- **Already done?** Each file may already exist from an earlier session. Read it and the latest `finance-forecast-check FOLDER --vintage V --format json` first; change only what the check or the reviewer says is wrong.
- **Employees are never named** in anything a reader sees: roles, departments, counts. Nothing reaches the CEO or the board, or the accounting system, from here: a person approves, sends and uploads.
- **One command per call**, no pipes, redirects, `&&` or variables.

## Hypotheses before evidence

Before anyone opens the new forecast, write what you expect each bridge line to do in this vintage and by how much, in EBITDA terms, with a confidence and one sentence of why, plus each year's expected EBITDA. Work from what is known before looking: the last bridge, the change requests, the closed month, the calibration log of earlier misses.

- **Never edit a hypothesis after looking.** A miss is the vintage's most valuable output. Moving the expectation to match what you found destroys the only record of whether this forecast can be trusted; `finance-forecast-check` refuses hypotheses that changed after they were recorded.
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

- **Positive is favourable to EBITDA.** Prior, then closed months restated (should be zero), then the months that became actual since the prior, then one line per bridge line over the forecast months, then the accounts no line claims, then new. `finance-forecast-bridge` builds it so every line's accounts sum to the line, the lines sum to the change, and the quarters' changes sum to the year's. The extract ties to the workbook's own revenue and EBITDA rows month by month and checks the sheet's own "must be zero" rows.
- **Corrections apart from business changes.** Each line's reason has a kind: `business` (the outlook changed), `correction` (the model was wrong), `timing` (the same thing in another month), `new-data` (an actual or a new source replaced an estimate), or `mixed` with a detail for each part. A reader must never take a bug fix for a profit swing, or the reverse.
- **About six details explain almost any line.** List offsetting increases separately so the net is honest; detail amounts sum to the line.
- **Split the walk by quarter and by revenue category,** and explain revenue on the dimensions the company plans on (entity, account, class).
- **Say what is not in the revision.** When costs are still at the prior plan, the cost lines show no change by construction, and the losses that follow are revenue reductions on an unrevised cost base, not a view of profitability. Write that sentence.
- **Unclaimed is a finding.** An amount on accounts no line claims, beyond materiality, means the bridge lines need a change: propose it for `modules.yaml`.

## What the sense checks mean

`finance-forecast-sense-check` flags, it never judges: a forecast month far off its run rate, a revenue account below zero or a cost against the sign, a month-on-month swing, a closed month that moved, a workbook that does not foot or tie, an unclaimed amount, a hypothesis missed. Each material flag gets one answer: **explained** (the cause, with evidence), **revised** (the model was wrong; what changes and who changes it), or **open** (who owns it and the question that will settle it).

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

Every figure comes from the bridge: `finance-forecast-check` ties each `$` figure to a value the bridge carries. Money in $k to one decimal, negatives in parentheses, number first and cause after, one idea per bullet. Never name an employee: roles, departments, counts. Customers and vendors may be named. Nothing about how the forecast was produced (tools, agents, steps) reaches a reader.

## Versions are submissions

- A **version** exists only when the forecast is submitted or presented. Most months end at v1; a v2 exists only when management pushes back.
- An issued workbook is never edited. A revision is a new, dated file; the change log beside it is the audit trail.
- The prior for a vintage is the prior vintage's final, issued file.
- **Corrections apart from business changes, in every version.** A fix to a wrong formula or a wrong-month reference is a correction; a new expectation is a business change. Label every change as one or the other (or new data), so no reader takes a bug fix for a profit swing or a profit swing for a bug fix.
- A rolling vintage the agents build is a values-only copy of the prior (`finance-forecast-revise`): only forecast months change, closed months never, a formula cell is never overwritten, and the copy is the agents' working file until a person submits it.
- A workbook that uses features a library cannot round-trip (dynamic arrays, for example) is never saved by a library. A person builds that revision; the agents bridge it.
- After any programmatic write: keep cached values, confirm every content type and relationship target resolves, and reopen the file. Excel's repair dialog is the failure no one sees from here, so the integrity check stands in for it.
- Keep sheet names and the bridge's sheet layout stable between revisions; a renamed sheet or driver breaks the extract and the log. The extract refuses rather than guesses.

## Explaining a variance

How any line is explained, in a flag answer, a reason or a deep dive. A variance is explained when a reader could repeat the explanation to a board member, with what caused it named: "timing" and "higher activity" are not explanations unless they name which timing and which activity.

- One line each: the driver, the amount, the evidence (an `E-nnn`, or the account, month and cell that shows it).
- Look for the largest entries, a new customer or vendor, a one-time item, an entry in the wrong period, an accrual that reversed without replacement. An entry that looks wrong is a finding for its owner, not something to fix here.
- Favourable surprises get the same suspicion as unfavourable ones: missing expense masquerades as savings.

## Write the hypotheses

For `finance-worker`, on opus, isolated: the brief carries only what predates the new forecast.

Goal: `vintages/<V>/hypotheses.json` that a reader can later hold the bridge against. One entry per active line in `modules.yaml` for every year in `VINTAGE.yaml`, plus each year's `ebitda_expected`, each with a direction, an expected change in EBITDA terms, a confidence and one sentence of why (Hypotheses before evidence, above; the shape in `contract.md`).

1. Work only from the brief's paths: the prior extract, the last vintage's bridge and scores, the calibration log (where the forecast has missed before and by how much), the request, and the evidence that predates the new forecast. **Do not open the new workbook, `new.json` or the change-log items of `evidence.json`**, even if you can find them: a hypothesis written after looking is worth nothing.
2. A line you have no view on gets `expected: 0` and a rationale saying why you expect no change. Name the key events that would decide the year.
3. A fact only a person knows is a question with its fallback, never a guess.

Return the `orchestration-workstream` block: `items` `[{"test": "hypotheses", "item": "set", "state": "written"}]`, `files`, `questions` (with `extra.fallback` and `extra.due`), `findings`.

## Propose the rolling forecast

For `finance-worker`, on opus, rolling vintages only, so the context that explains the numbers did not choose them.

Roll the forecast forward the way a careful analyst would: last month's final forecast is the baseline, the closed month replaces its forecast, and every forecast month that moves has a reason. Goal: `vintages/<V>/proposals.json` for a vintage whose `VINTAGE.yaml` says `kind: rolling`: one row per account, department, location and class that changes, with the amount for each forecast month (after `last_actual_month`), in the workbook's sign, and the node or evidence that put it there. A row left out keeps the prior forecast's number, which is right for anything nothing has moved.

1. Start from `work/source/prior.json` (the prior final forecast) and the closed actuals the brief names. The closed months are not yours: `finance-forecast-revise` refuses them.
2. Walk `driver-tree.yaml` line by line (The driver tree, above): zoom where the change trips a node's threshold, stop where the next level would not change the number, name the driver in a phrase. Every row above a line's materiality carries an evidence or question id in `note`.
3. Use `hypotheses.json` and the answered questions; where a question is still open, forecast on its fallback and say so in `note`.
4. Keep the layout stable: rows keep the sheet's own identity values (`finance-forecast-extract` shows them), a new row only where nothing existing fits.
5. Corrections and business changes stay apart (Versions are submissions, above): say which in `note`.

If the prior workbook cannot be written by the tool (it carries dynamic-array formulas), stop: that revision is built by a person. Return it as a question for the owner.

Return the `orchestration-workstream` block: `items` `[{"test": "proposals", "item": "proposals.json", "state": "drafted"}]`, `files`, `findings` (what moved the most and why), `questions` with `extra.fallback` and `extra.due`.

## Answer the flags

Done by `finance-forecast` itself, after the bridge. Goal: `vintages/<V>/flags-resolved.json` answering every material flag in `flags.json` exactly once, by its id, so the bridge can be signed.

- **explained**: the cause in one sentence, with evidence ids (`E-nnn`) or the cell and month that shows it (Explaining a variance, above). Eliminations negative by design, a planned step change, a reversal in a closed month found in the extract: each is explained, with its evidence.
- **revised**: the model is wrong. Say what is wrong, where, and what the right number is; the model's owner changes it (a person for an issued revision; for a rolling vintage, step 4 again). Never change a workbook yourself.
- **open**: only a person can settle it. Name the owner (a role from `BACKGROUND.md`) and draft the question, with its fallback.

A `hypothesis_miss` flag is answered with the deep dive the method asks for: why the expectation was wrong. Never suggest editing the hypothesis. Read the minor flags too; one that matters goes in the report.

## Explain the bridge and write the summary

Done by `finance-forecast` itself. The numbers are already right: `finance-forecast-bridge` built them from the two workbooks and they foot. This section is the why. Goal: `vintages/<V>/reasons.json` and `vintages/<V>/summary.md` such that `finance-forecast-check` counts the `reasons` and `summary` tests met, and a reader of `bridge.md` plus the summary knows, for every line that matters, what changed, why, who asked, and whether it was a correction or a business change.

The reasons:
- Work from `bridge.md` (each line with its accounts) and `bridge.json`, the evidence index `work/source/evidence.json`, the request, the answered questions, and the extracts when you need a month or an account.
- Every line at or above its materiality gets a `driver` in one phrase, a `kind`, and at least one evidence or question id that exists. `restated` is never immaterial: a closed month that moved is explained or it is a question.
- Use `detail` to split a line into its causes (about six at most), with amounts that sum to the line; list offsetting moves separately so the net is honest.
- A line you cannot explain from the evidence is not guessed: draft the question, cite its id once recorded, and say in `driver` what is unknown.
- An amount on `unclaimed` beyond materiality is a proposal for `modules.yaml`: which accounts, which line should own them, and why. It goes in the report for the owner.

The summary: the eight parts of The executive summary, above, in order, with the headings `## Top drivers`, `## What would change it` and `## Anticipated questions`. Every `$` figure is one the bridge carries; say what the revision does not change (costs left at plan) when that is true; name no employee; say nothing about how the forecast was produced. Apply `unslop-deliverable`.

## Check a vintage

For `finance-reviewer`, on opus, given the file paths only, never the makers' reasoning. Load `review-numbers` too; this section wins where they differ. The one question: would the owner be comfortable handing this bridge and summary to the CEO and the board as they stand? "Mostly fine" is FAIL.

1. **The hypotheses.** Every line that missed its hypothesis beyond tolerance (`scores.json`, `flags.json`) owes an answer that explains the miss, not a restatement of the new number. A hypothesis that looks written after the fact (it matches the result to the dollar with no reason to) is a finding.
2. **The bridge and its reasons.** Run `finance-forecast-check FOLDER --vintage V --format json` and read its gaps; then go beyond it. For each material line, open the evidence each reason cites and confirm it says what the reason claims. A correction presented as a business change, or the reverse, is a finding. An unclaimed amount beyond materiality without a proposal is a finding.
3. **The rolling model** (when `proposals.json` exists). Every row above materiality cites a node, evidence or question; no closed month moves; corrections are labelled apart from business changes.
4. **The flags.** Every material flag's answer is true to the extract and the evidence; an `explained` that explains nothing is a finding.
5. **The summary.** The eight parts in order; every figure in the bridge; the walk not restated; no employee named; nothing about the machinery; what the revision does not change said when it applies; the fallbacks in use named under what we do not trust.
6. **The rules.** Nothing done that `FORECAST-RULES.md` does not allow; questions batched within the weekly limit; nothing written over a person's file.

You review; you never rewrite. A finding names what is wrong and where, and the fix, not a replacement paragraph. Three real findings beat fifteen observations. Return the verdict note (verdict, then each finding with the file, the line or flag, what is wrong and the fix), then one fenced `json` block, which `finance-forecast` writes as the review note:

```json
{"verdict": "PASS",
 "findings": [{"where": "reasons.json 2027:distributor_sales", "what": "cites E-004, which is a legal note", "fix": "cite the change-log row E-002"}],
 "expectations": [{"line": "2027:distributor_sales", "status": "addressed"}]}
```

`verdict` is PASS or FAIL. `expectations` holds one row per line that stated a hypothesis: `addressed` (scored and any miss explained), `partial` (scored, explanation does not carry the miss) or `missing`.

## Sign off the vintage

For `finance-reviewer`, on fable, once `finance-forecast-check` shows every test but `review` and `delivered` met. Walk Check a vintage in full again, from the files, as if no earlier review existed; then read `summary.md` once more as the CEO would, cold. PASS only if the owner could hand it on without editing a line. Same return.

## Done

`finance-forecast-check FOLDER --vintage V` computes it: extracts that tie, hypotheses recorded first and never edited, a bridge that re-derives and foots, a cited reason for every material line, every material flag answered, the hypotheses scored and the calibration log kept, a summary that ties, every question closed, a reviewer's PASS on the current bridge and summary, the weekly message limit kept, and the reviewed bridge filed beside the revision as a new file.
