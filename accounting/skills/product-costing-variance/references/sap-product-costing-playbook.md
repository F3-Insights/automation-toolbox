# SAP product costing reference

The standard SAP ECC and S/4 transactions a product-costing review reaches for, and the usual order of a costing run. The codes are SAP's own; configuration specific to any one company belongs in that engagement's notes, not here.

## T-codes by task

| Area | Action | T-code |
|---|---|---|
| Material master | Display / change material (incl. costing views, overhead group) | MM03 / MM02 |
| | Change standard price manually | MR21 |
| Bill of materials | Create / change / display | CS01 / CS02 / CS03 |
| | Multi-level explosion / where-used | CS12 / CS15 |
| Routings | Create / change / display | CA01 / CA02 / CA03 |
| | Routing list report | CA80 |
| Work centres | Create / change / display / list | CR01 / CR02 / CR03 / CR05 |
| Activity types | Create / change / display / list | KL01 / KL02 / KL03 / KL13 |
| Activity rates | Change / display planned rates | KP26 / KP27 |
| | Calculate planned / actual rates | KSPI / KSU5 |
| Cost centre planning | Plan primary costs / display / copy plan | KP06 / KP07 / KP97 |
| Costing variants | Display configuration | OKKN |
| Costing sheets | Display | KZS2 |
| Cost estimates | Single / mass cost estimate | CK11N / CK40N |
| | Mark and release the standard | CK24 |
| Configuration | IMG | SPRO |

## The costing run, in order

1. Plan cost-centre costs and activity quantities for the year (KP06, KP26).
2. Calculate planned activity rates (KSPI) and review them against the budget.
3. Check master data: BOMs, routings, work centres and each material's costing views, including any overhead group.
4. Confirm the costing variant and costing sheet (overhead calculation bases, rates and credits).
5. Run the cost estimate, single (CK11N) to test and mass (CK40N) for the population; review errors and outliers before going further.
6. Mark and release (CK24); the released estimate becomes the standard price.
7. Make any configuration change in a test system first and move it to production by transport.

## A check that catches placeholder standards

Routing minutes times activity rate, plus scrap, should reproduce a material's standard labour cost within a few percent. Where it does not, the standard is probably a placeholder and the product's margin is unreliable until the routing or the standard is fixed.
