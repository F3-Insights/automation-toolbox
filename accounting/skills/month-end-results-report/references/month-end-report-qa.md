# Report QA: assume it is wrong until each check passes

Output a short pass/fail log; fix defects in place; re-run until clean. Only then report to the owner with the QA log, the data vintage, and the version's change list.

## A. Numbers
1. Freshness: pull the trial balance again and recompute the headline rollups. If actuals moved since the report was built, the report is stale: rebuild and record the delta in "adjustments since prior version".
2. Headline re-derivation: recompute REV/COGS/SGA/EBITDA for ACT (lines snapshot), FCST and BGT (budget-detail with contra signs) and tie to the table exactly.
3. Internal sums: every "Composition:" list sums to its headline; entity table sums to total revenue; bucket variances sum to the section variance; caveat box total matches its items; any EBITDA bridge foots.
4. Cross-table consistency: a number appearing twice is identical everywhere.
5. Version diff: every change vs the prior version is explained by the adjustments bullet.

## B. Content rules (from month-end-report-format.md and the client's own rules file; each is a hard check)
- No close-process language (grep accrual / reclass / booked / recode / upload / JE) unless it is business-mechanics phrasing.
- No employee names. No scenario labels the version is not supposed to carry.
- Bullets not paragraphs; compositions labeled; standing offsets netted; every revenue type explained.
- Rounding consistent ($k); parentheses for unfavorable; colors match the sign.
- Meta block present: snapshot time, budget ids, checks run, thresholds, open items.

## C. Mechanics
- HTML integrity (balanced tags, full skeleton, no external resources, both themes render, wide tables in overflow wrappers). Right folder, right version number, prior versions untouched.

## D. Judgment sweep
- Would any bullet mislead a board member who reads only the bold text?
- Is every "favorable" item honestly labeled if it is an artifact?
- Are open questions visible in the caveat boxes rather than silently omitted?
- Does the bottom line follow from the sections above it?
