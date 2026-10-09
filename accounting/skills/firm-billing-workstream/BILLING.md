# Firm billing: the contract

The files, formats and commands firm billing's tools, workers and orchestrator share. The tools enforce it; the agents work to it. Everything specific to the firm and its clients is in the billing folder, never here. The billing bases a contract may combine, and the rate `kind` each maps to, are in the `firm-billing-workstream` skill.

## The billing folder

| Path | Holds | Written by |
|---|---|---|
| `BILLING-RULES.md` | Authority, thresholds, the definition of done, how questions are asked | the owner |
| `BILLING.yaml` | Settings, the firm's invoice header, and one entry per contract with its rate basis | the owner (agents propose changes in STATUS.md) |
| `STATUS.md` | Current period, open items, Waiting on, next action | the orchestrator |
| `{yyyy}/{yyyy-mm}/STATUS.md`, `LOG.md` | The period's state and log | the orchestrator |
| `{yyyy}/{yyyy-mm}/BILLING-EVIDENCE-{yyyy-mm}.csv` | One row per contract | `firm-billing-record` only |
| `{yyyy}/{yyyy-mm}/work/source/billing-pull.json`, `pulled.md` | The period's billing pull | `firm-billing-pull` only |
| `{yyyy}/{yyyy-mm}/work/lines/<contract>.json` | The lines a preparer proposes | the preparer |
| `{yyyy}/{yyyy-mm}/invoices/<contract> <yyyy-mm> invoice DRAFT.{json,md,html}` | The draft invoice | `firm-billing-draft` only |
| `{yyyy}/{yyyy-mm}/invoices/<contract> <yyyy-mm> cover email DRAFT.md` | The cover email draft | the preparer |
| `{yyyy}/{yyyy-mm}/review/<contract> <yyyy-mm> review.md` | The reviewer's note | the reviewer |
| `{yyyy}/{yyyy-mm}/work/delivery-<contract>.json` | A staged reply draft in the Insights Portal (`draft_id`, `check`, `contact_id`, `email_ref`) | the orchestrator |
| `{yyyy}/{yyyy-mm}/work/delivery-result-<contract>.json` | What `firm-billing-deliver` placed | `firm-billing-deliver` only |

The period is the month billed (`yyyy-mm`). Blank, on every tool, means the month before `--as-of` (else today). Nothing is deleted or overwritten: a second draft of the same invoice is `... invoice DRAFT v2.*`.

**Dry run.** `python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_pull.py --dry-run-if=true --run-dir=R` writes the period folder under `R/billing/{yyyy}/{yyyy-mm}/` instead, and every other tool takes `--period-dir DIR` to work there. Nothing in the billing folder changes on a dry run.

## BILLING.yaml

```yaml
version: 1
settings:
  invoice_folders: [<folder>, ...]     # where issued invoices live; read only, searched two levels deep
  invoice_pattern: '<regex>'           # named groups number, client, date (yyyy-mm-dd); default below
  payment_terms_days: 30
  time_records_dir: <folder>           # optional; the time records source, needed only for hourly lines (see below)
  uncontracted_min_hours: 1            # client time in the period at or above this, with no contract, is named
  currency: USD
firm:                                  # the invoice header
  name: <firm name>
  address: [<line>, ...]
  email: <address>
  payment_instructions: <text>
contracts:
  - id: acme-ops                       # kebab; the evidence row's id and the file names' prefix
    client: Acme Components            # display name
    invoice_tag: Acme                  # the client group in issued invoices' file names
    bill_to: {name: ..., attention: ..., address: [...], email: ...}
    context: acme-engagement           # optional: names the engagement whose folders hold milestone evidence
    time_records_client_key: acme      # optional: the client key in the time records whose hours are this client's
    start: 2026-01-01
    end: null                          # or yyyy-mm-dd
    cadence: monthly                   # monthly | quarterly | milestone
    timing: arrears                    # arrears (dated the month after) | month-end (dated in the month billed) | advance
    po: {required: false, number: null}
    email_delivery: file               # file | outlook-drafts (the drafts folder of the owner's mail client, for example Outlook)
    confirmed: false                   # false: seeded from the contract, not yet confirmed by the owner
    source: <the contract file the terms came from>
    rates:                             # the rate basis; every invoice line names one id; use only the kinds the contract has
      - {id: retainer, kind: retainer, amount: 1000.00, description: Monthly retainer}   # also a recurring fixed fee
      - {id: hours, kind: hourly, rate: 100.00, cap_hours: null, description: Additional hours}
      - {id: m1, kind: milestone, amount: 2000.00, due: 2026-03, description: Phase 1 readout}   # also a one-off fixed fee
      - {id: travel, kind: pass-through, markup_pct: 0, description: Travel at cost}
```

**The time records source.** `time_records_dir` holds `hours.csv`, one row per client per day: `date` (yyyy-mm-dd), `client_key`, `hours`. Any timesheet export reduced to that shape will do. It is optional: a firm that bills only fixed fees (retainers, milestones, pass-through) leaves it out, and the pull then computes no hours and names no uncontracted work. A row whose date or hours do not parse is skipped and named in the pull's `time.warnings` (and on stderr), so hours that were not read are seen before the invoice goes out.

The default `invoice_pattern` matches `(<firm tag>) Invoice 0042 to (<client tag>) 2026-10-01.pdf`: `\((?P<firm>[^)]+)\) Invoice (?P<number>\d{3,6}) to \((?P<client>[^)]+)\) (?P<date>\d{4}-\d{2}-\d{2})`.

## The pull: `work/source/billing-pull.json`

`python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_pull.py FOLDER [--period P] [--as-of D] [--run-dir R] [--dry-run-if V] [--period-dir DIR] [--format text|json]`

First line `FRESH: <n> contracts, <k> billable, <u> with unbilled months; period folder <path>`, or `STALE: <reason>` (still exit 0; nothing written) when BILLING.yaml cannot be read. It also sets up the period folder (STATUS.md and LOG.md stubs only when missing). Fields:

- `period`, `first`, `last`, `as_of`, `computed_at`, `billing_yaml`, `billing_sha256` (of the file's bytes; the check compares it), `period_dir`, `dry_run`.
- `time`: `present`, `source`, per month the days covered and the days in the month, and `warnings`, one line per time-record row skipped because its date or hours do not parse.
- `invoices_found`: every issued invoice file matched (`number`, `client`, `date`, `file`), and `next_number`, the highest number found plus one, zero-padded: a proposal only.
- `contracts[]`, one per contract:
  - `id`, `client`, `confirmed`, `cadence`, `timing`, `po_required`, `po_number`;
  - `billable` (true or false) and `why`: active in the period and the cadence falls in it (quarterly: the quarter's last month; milestone: any milestone due on or before it);
  - `last_invoice` (the latest issued invoice for its `invoice_tag`) and `last_billed_month` (the invoice's month for advance and month-end, the month before for arrears);
  - `unbilled_months`: every month after `last_billed_month` (or from `start`) up to and including the period in which the contract was active, oldest first;
  - `invoices_since_period_start`: issued invoices dated on or after the period's first day (the period may already be billed);
  - `expected[month]` for each unbilled month: lines with `rate_id`, `kind`, `description`, `quantity`, `unit_price`, `amount`, `basis` (in words) and `needs_evidence`. A retainer is one month at its amount; an hourly rate is the time records' hours for the client key that month times the rate, capped; a milestone due by then and a pass-through are listed with `needs_evidence: true` and no amount;
  - `hours[month]` and `warnings` (time records short of the month, two contracts on one client key, a partial month at start or end, a PO required and missing, unconfirmed terms).
- `uncontracted[]`: each client key in the time records that no contract names and that took at least `uncontracted_min_hours` in the period: `id` (`client:<slug>`), `client_key`, `hours`, `why`. Work that may be owed with nothing to bill it against; each needs a `question` or `not-billable` row.

## The lines file: `work/lines/<contract>.json`

```json
{"contract": "acme-ops", "period": "2026-09", "invoice_date": "2026-10-01",
 "months": ["2026-08", "2026-09"],
 "lines": [
  {"rate_id": "retainer", "month": "2026-08", "description": "Monthly retainer, August 2026",
   "quantity": 1, "unit_price": 1000.00, "amount": 1000.00},
  {"rate_id": "hours", "month": "2026-09", "description": "Additional hours, September 2026",
   "quantity": 12.5, "unit_price": 100.00, "amount": 1250.00},
  {"rate_id": "hours", "month": "2026-09", "quantity": 10, "unit_price": 100.00, "amount": 1000.00,
   "override_reason": "the owner capped September at 10 hours (CONFIRMATIONS.md 3)"},
  {"rate_id": "travel", "month": "2026-09", "description": "Travel to the client site, at cost",
   "quantity": 1, "unit_price": 100.00, "amount": 100.00, "evidence": ["<file>", "..."]}
 ],
 "notes": "One line for the reviewer."}
```

`python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_draft.py FOLDER --period P --contract ID --lines FILE [--period-dir DIR] [--format text|json]` refuses (exit 1, `REFUSED: <reason>` per line, nothing written) when:

- the contract or a `rate_id` is not in BILLING.yaml, or a month is not in `months` or not in the pull's `unbilled_months` for the contract;
- `amount` is not `quantity` times `unit_price` to the cent, or a total does not add up;
- a retainer's `unit_price` is not its `amount` or its quantity is not 1 per month;
- an hourly line's `unit_price` is not its `rate`, or its `quantity` is not the pull's hours for that month (after the cap) and it has no `override_reason`;
- a milestone's amount is not its rate amount, or a milestone or pass-through line has no `evidence` naming a file that exists; a pass-through's `unit_price` is at cost plus its `markup_pct`;
- the contract requires a PO and BILLING.yaml has none.

Otherwise it writes the three draft files and prints `DRAFTED: <json path> total <amount>`. The JSON holds the contract, period, months, bill_to, firm header, `proposed_number` (from the pull; the owner assigns the real number when issuing), invoice and due dates, the lines with their `rate_id` and `basis`, the total, `pull_sha256`, and `content_sha256` (over everything but itself). The Markdown and the HTML say DRAFT and "proposed number" in the header. Exit 0 drafted, 1 refused, 2 bad argument.

`python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_draft.py --verify JSON` re-derives an existing draft against BILLING.yaml and the pull and prints `OK: ...` or `REFUSED: ...`; the reviewer and the check use the same code.

## The evidence file and its states

`python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_record.py FOLDER --period P --contract ID [--period-dir DIR] --state S [--draft JSON] [--amount A] [--rate-basis IDS] [--months M,...] [--evidence E] [--question Q] [--note N] [--review PASS|FAIL --review-file F] [--by WHO] [--format text|json]`

Columns: `id,client,state,draft,amount,rate_basis,months,evidence,question,note,content_sha256,review,review_file,review_sha256,updated_at,by`. `id` is the contract id, or `client:<slug>` from the pull's `uncontracted` list, which takes only `not-billable` or `question`. States:

| State | Means | Needs |
|---|---|---|
| `drafted` | A draft invoice exists | `--draft` (its `content_sha256` and amount are read from the file) |
| `already-billed` | An issued invoice covers the period | `--evidence` naming the invoice file |
| `not-billable` | Nothing is owed this period | `--note` with the reason (no PO, milestone not met, paused) |
| `question` | Only the owner can say | `--question` (the comms-confirm id or the question) and `--note` |
| `open` | Not yet worked | |

A review records `review_sha256`, the draft's `content_sha256` at the time; a new draft clears the review. A drafted row on an unconfirmed contract also carries `--question` (the terms to confirm).

## Done: `python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_check.py FOLDER [--period P] [--period-dir DIR] [--as-of D] [--format text|json] [--precheck]`

| Test | Met when |
|---|---|
| `pull` | The pull exists and its `billing_sha256` is BILLING.yaml's |
| `contracts` | Every billable contract (and every contract with unbilled months) has a row in a final state: drafted, already-billed, not-billable or question; every `uncontracted` client key has a not-billable or question row |
| `drafts` | Every drafted row's JSON exists, verifies, and its total is the row's amount; an earlier unbilled month is covered by the draft's `months` or named in the row's note |
| `review` | Every drafted row is PASS and its `review_sha256` is the draft's current `content_sha256` |
| `reasons` | Every not-billable and question row has a note, every question row a question, and every drafted row on an unconfirmed contract a question |

`--precheck`: `NOTHING: a weekend; ...` when the as-of date is a Saturday or Sunday (the schedule runs on the first days of the month, and cron cannot also say weekdays), else `WORK: ...` while the period is not pulled or not done, `NOTHING: ...` when done.

## Delivery: `python3 ~/.claude/skills/firm-billing-workstream/scripts/firm_billing_deliver.py FOLDER --period P [--period-dir DIR] [--dry-run] [--config F] [--format text|json]`

The finish step, skipped on a dry run. Per drafted, reviewed contract: `FILE` (its `email_delivery` is `file`, or no `work/delivery-<contract>.json`), `ALREADY`, `HELD` (the check is not done), or `email-deliver` with the staged draft: `DELIVERED`, `WOULD DELIVER`, `REFUSED`, one line per contract (`NONE: ...` when no contract is drafted and reviewed). `email-deliver` only places a reply to a pinned email in the Drafts folder of the owner's mail client (for example Outlook); nothing is ever sent, and an invoice with no thread to answer stays a file.
