---
name: evidence-check
description: "Reference loaded by a department's reviewer, not for a user request: the evidence checklist. For each claim that something was done (a filing made, a request already provided, support that answers a request, a control evidenced), the reviewer opens the cited evidence afresh and confirms it exists, is the right kind, covers the right entity and period, and supports the whole claim, against the job skill's evidence standard. Returns PASS or FAIL per claim in the orchestration-workstream block. Not for checking an artifact's statements against sources (review-facts) or re-deriving figures (review-numbers)."
---

# Review: evidence

The checklist a department's `<department>-reviewer` is briefed with before an evidence claim counts: a filing marked filed, an auditor's request marked already provided, support said to answer a request, a control placed as evidenced. The reviewer did not make the claims and is not told why the maker believed them. The bar is the evidence standard of the job skill the brief names (for example a calendar's "Placing an occurrence" or a governance skill's "Control states"); where that standard says more than this checklist, it wins.

## Inputs

- **The claims** (required): each with its id and the evidence it cites (a file path, a Portal note or email id, a message).
- **The job skill and its evidence section** (required): load the skill with the Skill tool and read that section first, and the rules file the brief names, if any.
- **The conduct skill** `orchestration-workstream`, whose return block this checklist uses.

Never the maker's reasoning. If the brief carries it, set it aside and say so in the summary.

## The checks

For each claim, open the evidence itself with the reviewer's read tools (a file with Read, a Portal record with `get` or `email_bodies`, a PDF with the `pdf-handle` command when the reviewer is granted it) and answer:

1. **Exists and readable.** Is it where the claim cites it, and can it be read?
2. **Right kind.** Is it a document that did the act (a filed copy, a receipt, a system export, a signed form), not one that only talks about it?
3. **Right scope.** Is it for the right entity, account, control or request, and the right date or period?
4. **Whole claim.** Does it support all of the claim, or only part of it?

A question you could not answer is a FAIL that says why. Edit nothing.

## Verdict

Per claim: **PASS** when all four answers are yes under the job's evidence standard; **FAIL** otherwise, with the fix (the evidence that would carry it, or the state the claim should go back to). The summary above the block gives the overall verdict, PASS only when every claim passes, and the numbered fixes for the failures.

## Return

A short summary for a person (the overall verdict and the numbered fixes), then the `orchestration-workstream` block with `workstream: "evidence-check"`: one `items` row per claim, with `test` `check`, `item` the claim's id, `state` `PASS` or `FAIL`, `evidence` what you opened, `amount` null, and `note` one line of why, plus the fix for a FAIL. The other fields are present and may be empty.
