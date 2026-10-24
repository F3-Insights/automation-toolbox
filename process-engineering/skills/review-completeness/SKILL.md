---
name: review-completeness
description: "Reference loaded by a department's reviewer, not for a user request: the completeness checklist. A process map, workflow, requirements list or close checklist is walked against a standard reference model, element by element, and returns a coverage table and about fifteen prioritized questions phrased ready to ask the client, citing instead the ones the sources already answer. It looks for missing standard elements, not inefficiencies. Not for checking claims against sources (review-facts) or how the audience will read it (review-red-team)."
---

# Review: completeness

The checklist a department's `<department>-reviewer` is briefed with after the facts check and before an artifact goes in front of the client. Its one question: what does any real business in this situation have to handle that this document does not mention? It audits for missing standard elements, not for inefficiencies, quality or style. The job's own check section may add lines; where it does, it wins.

## Inputs

- **The artifact under audit** (required): a process map, workflow description, checklist, requirements list or close procedure. Read it fully.
- **A reference model** (required): the standard elements a process of this kind contains. When the brief supplies none, use the one below that matches and say which you used:
  - *Order to cash*: quote, order entry, credit check, fulfilment, shipping and freight, invoicing, returns, damage claims, change orders, cancellations, credit memos, collections, cash application, dispute handling, revenue recognition.
  - *Procure to pay*: requisition, approval, PO, receiving, three-way match, invoice exceptions, vendor onboarding, payment runs, early-pay discounts, returns to vendor, accruals for received-not-invoiced, 1099 or tax reporting.
  - *Month-end close*: cutoff, subledger close, bank reconciliation, accruals and reversals, prepaids, fixed assets and depreciation, intercompany, revenue recognition, payroll tie-out, tax provision, variance review, management reporting, sign-off.
  - Proposal to contract, record to report, and fuller versions of these: the `reference-process-models` skill, where the department holds it.
  - Anything else: FAIL with the fix "supply the reference model"; never invent one.
- **The sources** the artifact was built from (optional): used to answer questions before asking them.

Never the maker's reasoning. If the brief carries it, set it aside and say so in the return.

## The checks

1. **Walk the reference model element by element.** For each, find where the artifact handles it, and record present, partial (say what part is missing) or absent.
2. **Name each gap.** For every absent or partial element, decide which it is:
   - **Undiscovered process**: the business almost certainly does this and nobody asked.
   - **Genuine gap**: the business may truly not do this, which is itself a finding. You usually cannot tell; phrase the question so the client's answer settles it.
3. **Sources before questions.** Before writing a question, check the sources. If one already answers it, do not ask: cite it with a quote and location, and mark the artifact for correction.
4. **Rank by consequence:** what would change the artifact most, or cost the most to be wrong about.
5. **Stay in lane.** Do not comment on how well the process works, propose improvements or grade the artifact.

## Verdict

- **PASS** when the artifact may go before the client with the question list as it stands: no source answers an element the artifact omits or gets wrong, and no element the job's check section says must already be covered is absent.
- **FAIL** otherwise. The numbered fixes are the corrections the artifact needs: each ANSWERED IN SOURCE item, and each required element that is absent. Questions are not fixes; they go to the client.

## Return

The verdict line (`PASS` or `FAIL`) and the numbered fixes, then:

- **Coverage table**: reference element, status (present, partial or absent), and where in the artifact it lives if present.
- **Questions**: about fifteen, in priority tiers (must ask, should ask, nice to know). Each one:
  - phrased exactly as it would be asked in the room, in plain language, one question;
  - tagged undiscovered process or genuine gap, with a one-line reason;
  - or, where a source answers it: **ANSWERED IN SOURCE**, the quote, the location, and the correction the artifact needs.
- **What you did not check**: any reference element you could not evaluate, and why.

## Briefing this check (for the main agent)

- **An as-is process map before validation:** the map, the interview transcripts and the matching reference model, asking for the prioritized questions with answered items cited rather than asked. Saying the target is missing standard elements, not inefficiencies, is what keeps this from becoming a second red team.
- **A checklist built from one period:** the checklist and the standard reference model, so the reviewer names the standard steps it lacks and phrases each as a question for the person who owns the process. Without a reference model there is nothing to compare against and the review drifts into opinion.
