# Results report: format rules (violations are defects)

These are the rules every client's results report follows. The client's own additions (the report folder and file name pattern, its entity table, its standing offset pairs, its comparator budget ids, its revenue buckets) are in the month folder's `MONTH-END-RULES.md`. Read both.

Deliverable: a self-contained HTML file (inline CSS, no external resources) in the client's report folder, named by its file name pattern. Local file, never a hosted artifact. Increment the version; never overwrite a version the owner has reviewed; each version lists what changed since the prior one.

1. **Results only, zero close-process commentary.** No "accruals are booked", no reclass mechanics. Where mechanics explain a number, say it in business terms ("includes two months of a consultant's fees from their arrears billing cycle").
2. **Bullets, not paragraphs.** Bold claim with numbers first; one fact per sub-bullet.
3. **Lead with the three-way table**: ACT | BGT | delta BGT | FCST | delta FCST, rows Revenue, COGS, Gross profit, SG&A, EBITDA. Name the exact budget ids of the comparators in the meta block.
4. **Revenue leads with the entity table** when the client has more than one entity, then its revenue buckets. **Every revenue type is explained every month.**
5. **Composition lists say "Composition:" and visibly sum** to the headline figure.
6. **Net the client's standing offset pairs** (listed in its rules file) before presenting.
7. **Names**: vendors and customers yes; employees never. Round to $k (small items one decimal); `( )` = unfavorable.
8. **Materiality**: if the forecast was meant to be exact, any variance matters; if it was a range, allow more. A couple thousand dollars is worth a look; the report picks what matters.
9. **Caveat boxes** (amber): (a) "Caveats: favorable variances that are not savings" with a total; (b) "Accounting changes not yet made", including adjustments booked since the prior version and their net EBITDA impact.
10. **Bottom line**: three or four bullets: EBITDA vs both references, the one-sentence causal story, what is real vs artifact.
11. **Meta block**: prepared date, source ("Sage Intacct general ledger, all entities"), snapshot time, comparators (budget ids), checks run and thresholds, open items. A memo without run metadata is invalid.

Design: memo aesthetic (serif body, sans figures with `tabular-nums`, slate-teal accent, red/green variance colors with parentheses, light and dark via CSS tokens, tables in `overflow-x:auto`, about a 60rem column). Reuse the `<style>` block from the client's latest version.
