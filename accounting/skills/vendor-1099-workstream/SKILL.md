---
name: vendor-1099-workstream
description: "The job skill of accounting-vendor-1099, not for a user request: vendor 1099 and W-9 completeness. Covers 1099-RULES.md (filing entities, the year's thresholds, the GL-to-box mapping, where W-9s live, processor-reported payments, the AP owner), the year folder, vendor states, a complete W-9, TINs to last four only, the W-9 request draft, the fall backlog and year-end register passes, the Steps, the sections Work a vendor batch (accounting-worker) and Check the register (accounting-reviewer), and the DONE checklist. Not for the filing calendar."
---

# Vendor 1099s and W-9s

The chronic failure is a W-9 backlog found in January and a 1099 issued wrong. The fix is to work the backlog in the fall, so the year-end pass is arithmetic: by the filing deadline every vendor who must get a 1099 has a complete W-9 on file, the right box and the right amount, and no vendor who should not get one gets one. `accounting-vendor-1099` runs it; keep `orchestration-workstream`'s conduct and return its block.

## The rules file

`1099-RULES.md` in the 1099 folder names: the filing entities; the year's reporting thresholds by form and box (they change by law; this skill never assumes one); the GL-to-box mapping; where W-9s are kept; the payment methods reported by a card network or processor instead; the payments source's freshness window; the AP owner (a role) who sends requests; the request template. It wins over this skill.

## The folder

```
<1099 folder>/<year>/
  source/         year-to-date payments by vendor and the vendor master export, as saved
  REGISTER-<year>.csv   vendor, entity, state, box, reportable total, processor-paid total,
                        W-9 file, TIN last four, reason   (the main agent writes it from returns)
  requests/       one W-9 request draft per vendor
  STATUS.md  LOG.md  CONFIRMATIONS.md  reviews/
```

## Vendor states

| State | When |
|---|---|
| `reportable` | Over the threshold after exclusions, a box applies, complete W-9 on file |
| `missing-w9` | Would be reportable, no W-9 on file |
| `incomplete-w9` | W-9 unsigned, undated, no classification or no TIN |
| `not-reportable` | A corporation not in an excepted category, under the threshold, or all processor-paid; the reason cited |
| `unknown` | The record cannot settle it; a question |

A complete W-9 has the legal name, the classification box, the TIN, a signature and a date. A W-9 older than the rules' age limit, or one whose name differs from the vendor master, is `incomplete-w9`.

## TINs are sensitive

Never write a full TIN in any file, return or message; the last four digits identify it. Never copy a W-9 out of its folder.

## The passes

- **backlog** (October to December): every vendor paid this year so far; W-9 states, the requests, the mapping proposals. Re-run weekly until no `missing-w9` vendor is above the threshold.
- **year-end** (January): the full year's payments; final totals by vendor and box; the register a person files from.

## Inputs

- The 1099 folder and `1099-RULES.md`, from the launch.
- Tax year (yyyy): default the current calendar year. Pass: `backlog` or `year-end`, default by today's date.
- Instructions (override the defaults, never the rules) and dry run (work in the Run folder; write nothing in the 1099 folder and ask no one).

## Steps

1. [judgment] Orient. Read `1099-RULES.md`, `<year>/STATUS.md`, `LOG.md`, `CONFIRMATIONS.md` and last year's register. An answered question is input.
2. [judgment] Check the payments: the year-to-date payments by vendor and the vendor master export are in `<year>/source/`, dated inside the rules' freshness window.
   → missing or stale: step 7
3. [hand-off: accounting-worker] Work the vendors. One worker per batch of about 50 vendors (alphabetical), in parallel, model opus, told to follow this skill's section Work a vendor batch, with the folder, the year, the pass, its vendors, the rules file's path and the answers so far. Log before; save each return as `RUN/returns/<batch>.json` at once.
4. [judgment] Write `<year>/REGISTER-<year>.csv` from the returns, one row per vendor, last four of the TIN only; the request drafts stay in `requests/`.
5. [hand-off: accounting-reviewer] Check the register, told to use this skill's section Check the register, with the register, the payments source, the W-9 folder and the rules only, never the workers' reasoning; in the year-end pass, also `review-numbers` on the totals by box. Save each note under `<year>/reviews/`.
   → FAIL: step 3 (max 1)
6. [script] Ask. A vendor whose status only a person can settle, and the batch of W-9 requests ready to send, go to the AP owner's role through `confirm`, batched into one message a week at most and recorded in `CONFIRMATIONS.md`; on a dry run, list them instead. A second reviewer FAIL becomes a question here.
7. [judgment] Close. Write `<year>/STATUS.md` and `LOG.md`; walk the DONE checklist for the pass with evidence; report the pass and tax year, vendors by state, the W-9 requests drafted, the mapping proposals, in the year-end pass the totals by box, the reviewer's verdict, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## Work a vendor batch

For an `accounting-worker` given one batch of vendors. Read `1099-RULES.md` first. Your goal: a decision on every vendor that a reviewer can re-derive, and a request ready for every missing W-9.

For each vendor in your batch:
1. **Payments.** Total the year's payments from `<year>/source/` (`excel-handle` to read a workbook; `intacct-gl-detail` or `gl-normalize` when the rules say to read the ledger), split by payment method; the card and processor-paid part is excluded as the rules say. Map each payment's GL account to a box with the rules' mapping; an unmapped account is a proposal.
2. **W-9.** Find the vendor's W-9 where the rules say they are kept (`pdf-handle` to read it). Read it for the legal name, the federal tax classification, the exemption codes, the TIN type, the signature and date. Record the TIN's last four digits only.
3. **Decide** the vendor's state as this skill defines it, with its reason.
4. **Draft a request** for each `missing-w9` or `incomplete-w9` vendor in the rules' template, to the vendor's address of record, as a file under `requests/` for the AP owner.

A vendor whose classification the W-9 does not settle is a question, never a guess. Write only request drafts and the batch's rows file in the Run folder; never the register, the vendor master or the ledger, and never send.

Return the `orchestration-workstream` block with `workstream: "vendor-1099"`: `items` one row per vendor (`test` `vendor`, `item` the vendor id, `state`, `amount` the reportable total, `evidence` the W-9 file or "none", `note` the box and the reason); `files` (the rows file and the drafts); `proposals` for mapping changes with their source; `questions` with `of` a role.

## Check the register

For `accounting-reviewer`. From the register, the payments source, the W-9 folder and the rules only. Per vendor:

1. The reportable total re-derives from the payments source: the year's payments, less the card and processor-paid part, mapped to the box by the rules' mapping. A different figure is a FAIL with both.
2. The threshold is the rules' for that form and box, applied after exclusions; a vendor under it is not `reportable`.
3. A `reportable` vendor's W-9 exists where the register says and is complete (legal name, classification, TIN, signature, date, within the age limit, name matching the vendor master). A `not-reportable` reason is one the W-9 or the rules support; exemption is never assumed.
4. Every `missing-w9` and `incomplete-w9` vendor has a request draft in `requests/`.
5. No file in the year folder, the register or the drafts holds a full TIN.
6. In the year-end pass, the totals by box foot to the register (with `review-numbers`).

Return PASS or FAIL per vendor with numbered fixes, and the note text the main agent saves.

## DONE checklist

The main agent checks each item with evidence; `accounting-reviewer` confirms 3 and 5.

1. The payments source is dated inside the freshness window.
2. Every vendor paid in the year has a register row and a state with its reason.
3. Every reportable total re-derives from the payments source, with processor-paid amounts and the threshold applied as the rules say.
4. Every `missing-w9` and `incomplete-w9` vendor has a request draft, and the AP owner has been asked once this week at most.
5. In the year-end pass, the totals by box foot to the register.
6. No file holds a full TIN; nothing was sent or filed by an agent.

## Later tools

- `vendor-1099-register`: total payments by vendor and box, apply exclusions and thresholds, and write the register; proves DONE items 3 and 5.
- `w9-scan`: list the W-9 files by vendor with their date and completeness fields, last four only.
- `tin-match-file`: write the IRS TIN-matching bulk file for a person to submit.
