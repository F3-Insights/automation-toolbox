---
name: reference-process-models
description: Reference loaded by the completeness-audit agent and by process-flow or discovery Runs, not for a user request. Holds standard process models (order to cash, procure to pay, proposal to contract, record to report) listing the elements any business running the process has to handle; load it when a run needs a reference model to compare a process map against.
user-invocable: false
---

# Reference process models

Standard process models the `completeness-audit` agent compares a process map against. Each lists the elements any real business running that process has to handle, so a map that lacks one has either found undiscovered process or a genuine gap. They are checklists of standard elements, not best practice: the audit asks about what is missing, never about efficiency.

An engagement's `PROCESS-FLOW-RULES.md` names one with `Reference model: <name>` (the file name without `.md`), or a file of its own beside the rules file. `process-flow-prepare` copies it into the Run folder as `REFERENCE-MODEL.md`. Each model is a file in this skill's folder.

| Model | For |
|---|---|
| `order-to-cash` | Selling goods or services: request, quote, order, fulfil, invoice, collect |
| `procure-to-pay` | Buying: need, sourcing, purchase order, receipt, invoice, payment |
| `proposal-to-contract` | Winning work by proposal: opportunity, bid decision, proposal, award, contract |
| `record-to-report` | Closing the books: transactions, accruals, reconciliations, review, reporting |
