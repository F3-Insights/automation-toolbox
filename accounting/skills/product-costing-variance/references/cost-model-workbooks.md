# Cost model workbooks: what each must contain

The method needs three inputs. Their tab names and layouts vary by client; what matters is that each holds the content below, mapped by header rather than by position. `fg-pl-extract` reads the per-finished-good P&L; `product-costing-revision` is how a shared copy is re-issued.

## 1. Cost model (the standards)

- Standard cost per finished good, split by component: direct material, direct labour, variable overhead, fixed overhead.
- Routing minutes per finished good by operation and work centre, with the work centre's factory, and the rate per minute or hour each operation is costed at.
- The rates themselves and how each was built (pool over base, from the budget), so a standard can be re-derived rather than trusted.
- Where the ERP holds a placeholder, the alternative standard used and a flag saying so.
- Every mapping the model relies on: products to customer groups, work centres to factories, cost categories to drivers.

## 2. Standard-versus-actual P&L per finished good

- One row per finished good per factory, and per period: sales quantity, sales amount, produced quantity, standard and variance for each cost component, contribution and gross margin in dollars and percent.
- A year-to-date view that is the sum of the months, and a roll-up by customer group.
- The variance allocation shown by tier (direct to product, to customer group, residual by driver), so each product's variance can be traced.
- From the first revision onward, a revision log and the list of client requests.

## 3. Trial balance by site

- Account-level balances per factory (or site) for every month in the period, with the mapping of accounts to cost categories.
- Enough to show, per category and factory, that standard plus variance equals the ledger.

## Quote versus standard

When a product's margin is disputed, compare its quoted cost (materials, routing, rates and currency as quoted) with its standard. **Standard cost is not quoted cost**: quotes carry markups and assumptions, standards carry the ERP's routing and rates. When they disagree the question is which one is wrong, and it is often the standard.
