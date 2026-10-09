---
name: vendor-1099-workstream
description: Reference loaded by vendor-1099-analyst and vendor-1099-orchestrator, not for a user request; what vendor 1099 and W-9 completeness work adds to orchestration-workstream. Covers 1099-RULES.md (filing entities, the year's thresholds, the GL-to-box mapping, where W-9s live, processor-reported payments, the AP owner), the year folder, vendor states, a complete W-9, TINs to last four only, the W-9 request draft, the fall backlog and year-end register passes, and the DONE checklist.
---

# Vendor 1099s and W-9s

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded.

The chronic failure is a W-9 backlog found in January and a 1099 issued wrong. The fix is to work the backlog in the fall, so the year-end pass is arithmetic.

## The rules file

`1099-RULES.md` in the 1099 folder names: the filing entities; the year's reporting thresholds by form and box (they change by law; this skill never assumes one); the GL-to-box mapping; where W-9s are kept; the payment methods reported by a card network or processor instead; the AP owner (a role) who sends requests; the request template. It wins over this skill.

## The folder

```
<1099 folder>/<year>/
  source/         year-to-date payments by vendor and the vendor master export, as saved
  REGISTER-<year>.csv   vendor, entity, state, box, reportable total, processor-paid total,
                        W-9 file, TIN last four, reason   (the orchestrator writes it from returns)
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

- **backlog** (fall): every vendor paid this year so far; W-9 states, the requests, the mapping proposals. Re-run weekly until no `missing-w9` vendor is above the threshold.
- **year-end** (January): the full year's payments; final totals by vendor and box; the register a person files from.

## DONE checklist

The orchestrator checks each item with evidence; the reviewer confirms 3 and 5.

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
