# Weekly report outline

**Superseded as a form.** The one document an author fills in is the role profile, `weekly-report-profile.md`, written by `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py init` and filled in by the setup interview in the `report-weekly` skill (`setup.md`). The outline is a projection of that profile, not a second document anybody keeps in step by hand.

- `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py show --profile <profile.md> --outline` writes the outline Markdown.
- `python3 ~/.claude/skills/report-weekly/scripts/report_pack.py --outline-file <profile.md>` and `python3 ~/.claude/skills/report-weekly/scripts/report_collect.py --outline-file <profile.md>` take the profile itself. They recognise one and project it, so no category list is retyped.
- The run looks for a note titled `Weekly report profile` first, then `Weekly report outline`. The older `Weekly report spec` title is no longer read. The ledger records which title answered, and whether the text was read as a profile or an outline.
- An outline written by hand before the profile existed still parses. A section only the profile has, Leadership team, Never recorded or Form rules, comes back in `missing_sections` as a warning and never as an error that stops the run.

The reference material that used to live here, the three kinds of category, the signal syntax, where the note lives and what the checker rejects, is in the profile template now, beside the section it belongs to. What is left here is the field list for anyone reading an old outline note, and two worked examples.

## The fields a hand-written outline carries

Every label is spelled exactly as this table spells it, in one of the forms the parser reads (`- **Field.** text`, `**Field**: text`, `## Field` or `Field: text`). A relabelled field is not read at all. Write a new one as a profile instead; this list is for reading old notes.

| Field | What it holds | Where the profile holds it |
|---|---|---|
| **Report title** | The title line without the date. | Built from the seats. |
| **Author and seats** | One numbered item per seat, a colon, then what the position answers for. | `## Seats` |
| **Audience and recipients** | Who reads it, in one line. | Built from `## Leadership team`. |
| **Leadership team** | One item per member: their role, a colon, what that role answers for. | `## Leadership team` |
| **Length** | The word target and the hard cap. | `## Form rules` |
| **Materiality** | The amount below which a figure is not reportable on its own. Optional. | `## Form rules` |
| **Names to roles** | One item per person: the name, a colon, their role. Optional, and the one field that holds names. | `## Names to roles` |
| **Form rules** | One item per rule about the shape of the document. | `## Form rules` |
| **Never appears** | What never reaches the audience. | `## Never published` |
| **Never recorded** | What never enters the record, not even as evidence. | `## Never recorded` |
| **Delivery** | Where the file goes and who it is drafted to. | `## Delivery` |
| **Cadence** | How often, on what day, and the holiday rule. | `## Form rules` |
| **Prior reports to read** | How many previous reports are read back for continuity. | A fixed default. |
| **Direct reports** | One item each: who, what they report on, where their update arrives. | `## Direct reports` |
| **Meeting signals** | How this seat's meetings are recognised at all. | `## Collection tier and scope signals` |
| **Categories** | A `## Categories` heading, then one `### Name` block per category. | `## Standing categories` |

---

## Worked example one: a controller

Lakeview Hardware is invented, and so is every role in it. One seat, one report.

```
# Weekly report profile

## Author and organisation

- Role: the controller
- Organisation: a regional hardware wholesaler with three branches and about two hundred
  staff.

## Seats

1. Finance: answers for the monthly close and the results package, the annual budget, the
   cash position and the credit facility, the receivables ledger and collections, and the
   annual audit and the tax filings.

## Leadership team

1. Chief executive: answers for the plan, the capital and the company's results.
2. Head of operations: answers for the branches, the warehouse and delivery service.
3. Head of sales: answers for the order book, pricing and the customer relationships.
4. Head of people: answers for headcount, hiring and the payroll cost base.

## Standing categories

### Month-end close
- Seat: Finance
- Kind: operational
- Covers: closing the books each month and issuing the results package to the leadership team.
- Signals:
  - Titles: `close`, `month[- ]end`, `flux`, `trial balance`
  - Subjects: `close`, `journal`, `reconcil`
  - Keywords: `journal entry`, `accrual`, `reconciliation`
  - Projects: `Month-end close`
  - Goals: `Close in five business days`
- Standing metrics:
  - Business days to close from `facts:close_days`
- Owner: Head of accounting

### Cash and financing
- Seat: Finance
- Kind: operational
- Covers: the cash position, the thirteen-week outlook and the credit facilities.
- Signals:
  - Titles: `cash`, `financing`, `facility`, `covenant`, `bank`
  - Subjects: `cash`, `loan`, `facility`, `covenant`
  - Keywords: `thirteen week`, `drawdown`, `headroom`
  - Counterparties: `example-commercial-bank.test`
- Standing metrics:
  - Cash on hand from `facts:cash_on_hand`
  - Facility headroom from `facts:facility_headroom`

### Receivables and collections
- Seat: Finance
- Kind: operational
- Covers: the receivables ledger, the ageing and what is being collected.
- Signals:
  - Titles: `receivable`, `collection`, `ageing`, `aging`, `invoice`
  - Subjects: `invoice`, `payment`, `remittance`, `past due`
  - Keywords: `over 90`, `bad debt`, `credit limit`
- Standing metrics:
  - Cash collected in the week from `facts:cash_collected_week`
  - Receivables over 90 days from `facts:ar_over_90`
- Owner: Credit controller

### Audit, tax and compliance
- Seat: Finance
- Kind: operational
- Covers: the annual audit, the tax filings and the regulatory calendar.
- Signals:
  - Titles: `audit`, `tax`, `filing`, `compliance`, `insurance`
  - Subjects: `audit`, `tax`, `filing`
  - Keywords: `statutory`, `auditor`, `return`
  - Counterparties: `example-auditors.test`

### Annual budget
- Seat: Finance
- Kind: project
- Covers: building next year's budget with the branch managers, from the first assumptions
  to the board's approval.
- Signals:
  - Titles: `budget`, `plan review`, `assumptions`
  - Subjects: `budget`, `headcount plan`, `assumptions`
  - Keywords: `budget draft`, `board approval`
  - Projects: `Annual budget`
  - Goals: `Budget approved before year end`

### Other topics
- Seat: Finance
- Kind: other
- Covers: important smaller call-outs that belong to none of the categories above.

## Standing metrics

1. Business days to close from `facts:close_days`, monthly
2. Cash on hand from `facts:cash_on_hand`, weekly
3. Facility headroom from `facts:facility_headroom`, weekly
4. Cash collected in the week from `facts:cash_collected_week`, weekly
5. Receivables over 90 days from `facts:ar_over_90`, weekly
6. Open reconciling items, supplied by hand, monthly

## Direct reports

1. Head of accounting, reports on the close and the receivables ledger; mail from
   `accounts@lakeview-hardware.test` with subject `/weekly|close update/i`
2. Credit controller, reports on collections; file `collections/*.md`

## Collection tier and scope signals

- Tier: portal
- Attendee domains: `lakeview-hardware.test`
- Title patterns: `/close|budget|cash|audit|tax/i`
- Mail terms: `remittance`, `covenant`

## Form rules

- Length: one page, 450 to 600 words
- Hard cap: two pages, 1,100 words
- Deadline: Friday by 3 pm
- Holiday rule: when the Friday is a holiday the report goes out on the Thursday.
- Materiality: $10,000. A smaller figure appears only inside a pattern that carries its own
  count and total.

1. A bold topic label opens every top-level bullet, then what happened and what is expected
   next, with a date where one is known.
2. Figures go in a tight table, never in a paragraph, and the table is rendered by code.
3. No preamble, no summary paragraph and no section that only says a category was quiet.
4. Cut the budget detail first, never the cash position.

## Names to roles

1. Dana: the head of accounting
2. Marcus: the credit controller
3. Priya: the budget analyst

## Delivery

- Recipients: the chief executive, the head of operations, the head of sales and the head of
  people
- Folder: the leadership folder in the company document store

## Never published

1. Individual salaries.
2. Anything about a named employee's performance.
3. Numbers that have not been through the close, unless the same sentence labels them
   preliminary.
4. A branch's results before the head of operations has seen them.

## Never recorded

1. Anything from a personnel file.
2. Bank account numbers.

## Review date

- Last reviewed: YYYY-MM-DD
- Next review: YYYY-MM-DD
```

## Worked example two: a head of operations

Acme Components is invented, and so is every role in it. One seat, a shorter profile.

```
# Weekly report profile

## Author and organisation

- Role: the head of operations
- Organisation: a precision engineering manufacturer with two plants and about four hundred
  staff.

## Seats

1. Operations: answers for output against the production plan at both plants, quality and
   returns, plant safety, inbound supply and the supplier base, and the capital projects on
   the factory floor.

## Leadership team

1. Managing director: answers for the plan and the company's results.
2. Finance director: answers for cash, margin and the capital budget.
3. Commercial director: answers for the order book and what has been promised to customers.

## Standing categories

### Output against plan
- Seat: Operations
- Kind: operational
- Covers: units produced at both plants against the production plan, and the causes of any gap.
- Signals:
  - Titles: `production`, `output`, `line \d`, `schedule`, `downtime`
  - Subjects: `production`, `schedule`, `shortfall`
  - Keywords: `units produced`, `changeover`, `takt`
- Standing metrics:
  - Units produced against plan from `facts:units_vs_plan_pct`
  - Unplanned downtime hours from `facts:downtime_hours`
- Owner: Plant one manager

### Quality and returns
- Seat: Operations
- Kind: operational
- Covers: scrap, rework, customer returns and the open corrective actions.
- Signals:
  - Titles: `quality`, `scrap`, `rework`, `return`, `corrective`
  - Subjects: `complaint`, `return`, `nonconform`
  - Keywords: `first pass yield`, `root cause`
- Standing metrics:
  - First pass yield from `facts:first_pass_yield`
- Owner: Quality manager

### Safety
- Seat: Operations
- Kind: operational
- Covers: incidents, near misses, and the safety actions still open.
- Signals:
  - Titles: `safety`, `incident`, `near miss`, `toolbox`
  - Subjects: `safety`, `incident`, `inspection`
  - Keywords: `lost time`, `risk assessment`
- Standing metrics:
  - Days since the last lost-time incident from `facts:days_since_lti`

### Supply and suppliers
- Seat: Operations
- Kind: operational
- Covers: inbound material, supplier performance and the sourcing decisions in front of us.
- Signals:
  - Titles: `supplier`, `supply`, `sourcing`, `material`, `shortage`
  - Subjects: `delivery`, `lead time`, `quote`, `shortage`
  - Keywords: `on time in full`, `second source`
  - Counterparties: `example-castings.test`

### Line four automation
- Seat: Operations
- Kind: project
- Covers: the automation of line four at plant two, its build, its acceptance and its budget.
- Signals:
  - Titles: `line four`, `automation`, `robot`, `cell`
  - Subjects: `automation`, `acceptance`, `commissioning`
  - Projects: `Line four automation`
  - Goals: `Cut line four cycle time by a fifth`
- Standing metrics:
  - Spend against the approved capital budget from `facts:line4_spend_pct`

### Other topics
- Seat: Operations
- Kind: other
- Covers: important smaller call-outs that belong to none of the categories above.

## Standing metrics

1. Units produced against plan from `facts:units_vs_plan_pct`, weekly
2. Unplanned downtime hours from `facts:downtime_hours`, weekly
3. First pass yield from `facts:first_pass_yield`, weekly
4. Days since the last lost-time incident from `facts:days_since_lti`, weekly
5. Spend against the approved capital budget from `facts:line4_spend_pct`, monthly

## Direct reports

1. Plant one manager, reports on plant one output and safety; mail from
   `plantone@acme-components.test` with subject `/plant one weekly/i`
2. Quality manager, reports on quality and returns; note titled `/quality weekly/i`

## Collection tier and scope signals

- Tier: portal
- Attendee domains: `acme-components.test`
- Title patterns: `/production|safety|quality|supplier/i`
- Mail terms: `shortage`, `nonconform`

## Form rules

- Length: one page, 450 to 600 words
- Hard cap: two pages, 1,100 words
- Deadline: Thursday by 5 pm
- Holiday rule: when the Thursday is a holiday the report goes out on the Wednesday.
- Materiality: $25,000. A smaller figure appears only inside a pattern that carries its own
  count and total.

1. Output and quality lead, in that order, because that is the order the room asks in.
2. A bold topic label opens every top-level bullet.
3. Safety is never cut for length.

## Names to roles

1. Sam: the shift superintendent
2. Jordan: the quality lead

## Delivery

- Recipients: the managing director, the finance director and the commercial director
- Folder: the operations folder in the company document store

## Never published

1. Any named operator's disciplinary record.
2. Supplier pricing that is under negotiation.
3. An injury before the family has been told.

## Never recorded

1. Anything from a disciplinary file.
2. The detail of an injury before the family has been told.

## Review date

- Last reviewed: YYYY-MM-DD
- Next review: YYYY-MM-DD
```
