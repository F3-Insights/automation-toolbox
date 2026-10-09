---
name: product-costing-variance
description: "Build or refresh a manufacturing client's standard-versus-actual P&L per finished good: standard cost times sales quantity, actual cost from the trial balance, the difference allocated to products in three tiers, per factory, tied to the TB. Use for a monthly cost review, a margin question about specific products, or disputed product profitability. Not for a GL P&L against budget; use month-end-flux. For the whole monthly review, start product-costing-orchestrator."
argument-hint: "[client workbook] [YYYY-MM] [build | refresh | explain <product>]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/product-costing-workstream/scripts/fg_pl_extract.py:*), Bash(python3 ~/.claude/skills/product-costing-workstream/scripts/costmodel_audit.py:*), Bash(python3:*)
---

# Per-finished-good P&L variance

What the cost model, the per-finished-good P&L and the trial balance must contain is in `references/cost-model-workbooks.md` in this skill's folder; the extractor is `fg-pl-extract` (`python3 ~/.claude/skills/product-costing-workstream/scripts/fg_pl_extract.py`), which reads the workbook through the client's cost-model layout file (`--layout`, or the `cost_model_layout` setting under `[product-costing-workstream]`; `product-costing-workstream` describes it); re-issuing a shared copy follows `product-costing-revision`. This skill is the method between them. For a client on SAP, `references/sap-product-costing-playbook.md` holds the standard transactions and the order of a costing run.

## The pipeline, and which steps are code

1. **Receive extracts** (TB, purchase price variance, scrap, freight-in, production and sales quantities, labour clock data, cost breakdown, routings). Chase and version them. *Judgment.*
2. **Normalise and stack** monthly tabs into long tables; map columns by header, never by position. *Code (`fg-pl-extract`, or `sap-extract-normalize` for SAP extracts, both in `product-costing-workstream`).*
3. **Quantity sanity.** Detect month-over-month carry-forward (the same quantity for most products two months running means the file was not refreshed); reconcile to signed raw movements; list products with production but no labour standard. *Code.*
4. **Standard selection.** Prefer a reasonable frozen standard kept beside the model over an ERP placeholder, through the existing override flag. Flag every placeholder. *Code, with judgment on each override.*
5. **Routing minutes.** Own versus own-plus-linked minutes per product, base-quantity aware, work centre tagged to factory, mixed-factory routes flagged. Validate roll-ups by implied $/minute against the budget rate: within 5% for linked, within 10% for own, else reject. *Code; accept or reject is judgment.*
6. **Absorbed standard** = standard per unit x produced quantity, per product, per factory. *Code.*
7. **Variance** = TB actual minus absorbed standard, per cost category x factory, then allocated in tiers: **Tier 1** direct to product where the source names it; **Tier 2** to a product group where the driver sits at that level; **Tier 3** the residual by a driver pool. Keep factory pools separate. *Code.* For example, a $10,000 unfavourable scrap variance at one factory: $6,000 on scrap tickets that name products goes to those products, $3,000 tied to one product family's material change goes across that family, and the last $1,000 is spread by produced units.
8. **Product P&L.** Apply standard plus per-unit variance to sales quantity; YTD; customer roll-up. *Code.*
9. **Tie-outs.** Standard plus variance equals TB per category; factory pools sum to consolidated; YTD equals the sum of months; margin arithmetic holds when cost is zero. *Code (`costmodel-audit`, with the same layout file; `fg-pl-extract` does the revenue tie).*
10. **Explain the swings** against the prior version. Find products whose variance is larger than their standard; separate model fixes from real results. *Judgment.*
11. **Revision log and client requests.** *Code scaffold, judgment content.*
12. **Client memo** in the `comms-client-status-update` voice. *Judgment.*

## Rules that hold

- **Standard plus variance must tie to the TB per category.** A model that does not tie is not a model; stop and find the gap before any product-level statement.
- **Base variance metrics on production volume, not sales volume.** Variance is incurred when things are made.
- **Allocate 100% by the detailed schedule first, residual by driver.** Never spread everything by one driver when the source data can place most of it directly.
- **Keep factory pools separate.** A consolidated rate blends sites with different costs and hides where a variance arises.
- **Prefer a reasonable frozen standard over an ERP placeholder**, through the override column, and say so on the product.
- **Sanity-check outliers in the real world.** A standard that is many times what the operation plausibly takes (say 10 minutes of labour on a part that takes 1) is a data error, not a finding.
- **A correction is not a profit change.** Label every delta.
- **List exactly what the client still owes.**

## Modes

- **`build`**: first version for a period. Runs steps 1 to 12; expect two passes because step 9 will fail on the first.
- **`refresh`**: new extracts into an existing model, through `product-costing-revision`.
- **`explain <product>`**: one product's standard, actual, variance by tier, and the routing and quantity facts behind them, with the flags (placeholder standard, cost-pending, mixed factory) stated first.

## Output

The workbook, the revision log, the client requests, and a memo whose first sentence says whether this version's movement is mostly correction or mostly business. Margin percentages are recomputed from summed dollars, never averaged. A product with revenue and no standard cost shows a null margin labelled cost-pending, never 0% or 100%.
