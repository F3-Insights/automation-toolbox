---
name: bd-proposal-workstream
description: Reference loaded by bd-proposal-drafter, bd-contract-auditor and bd-proposal-orchestrator, not for a user request; adds to orchestration-workstream and unslop-proposal. Covers the rules file and the owner's own executed documents before any structure is invented, the owner's newest copy re-read before every revision, a short first draft with scope as qualitative goals and price and terms left to the owner, the contract audit (tracked changes opened, cross-references resolved, payment, term and termination compared across the executed documents), the return shapes and the DONE checklist.
---

# Proposal and contract workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill first if it is not loaded. The editing standard for the prose is `unslop-proposal`; read it before drafting. This skill adds what a first draft of a proposal or SOW and an audit of contract documents need.

## Conduct here

- **The rules file first.** `BD-RULES.md`, section `## Proposals`, names the house style (section numbering, framing, the closing acceptance block), the reference documents (the owner's executed SOWs and master agreements), where drafts land and how they are named, and the positions the owner holds on terms. It overrides this skill.
- **The owner's newest copy wins.** The owner edits drafts in place and renames them. Before any revision, find the newest file in the pursuit's folder by modified time, read it, and build from it. Never regenerate from an earlier agent version.
- **House precedent before structure.** Start from the reference document the rules name for this kind of work. Do not invent sections it does not have.
- **Short.** A first draft is shorter than feels complete. Background is plain narrative. Scope is written as qualitative goals; no hour commitments, milestone dates, acceptance tests or protective clauses the owner did not ask for. Binding language lives only where it binds.
- **Price and terms are the owner's.** Fees, rates, payment terms, term and termination are placeholders (`[FEE: owner]`) unless the brief or the record states them. Where a figure is given, also state the total over the term.
- **Confidential reasons stay out.** A reason the owner gave for a choice is input to judgment, never text in the document.
- **Read, never commit.** Contract folders and repositories are read only. Drafts are new files in the Run folder, named as the rules say, with a version suffix; the owner moves them.

## The draft

`drafts/<name> v<n>.md` (and `.docx` when the rules ask and a converter is granted), plus `drafts/<name> v<n>.notes.md`: each placeholder the owner must fill, each choice made from a reference document with its source, and every sentence that needs the owner's judgment.

## The contract audit

Run on the draft and on every executed or in-flight document the pursuit's folder holds. Each finding is one row in `audit.json`:

`id, document, location, kind, finding, quote, against, severity, fix`

- `kind` is one of `tracked-change` (an insertion or deletion, with author and date when the file holds them), `cross-reference` (a section, exhibit or defined term that does not exist), `contradiction` (two documents, or two clauses, that cannot both hold: payment terms, term and renewal, termination, fees, precedence), `missing` (a term one document relies on that none defines), `drift` (a figure or name that differs between versions).
- `quote` is verbatim, at most 30 words; `against` is the other document and location.
- `severity` is `high` (money, term, termination, liability, signature authority), `medium`, or `low`.
- Tracked changes are always opened: read the revision markup, not only the visible text. A change that alters a fee, a term or a party is `high` whoever made it.

## Reading .docx

No granted command reads a .docx yet (`docx-redlines` below). Until it exists, read the text or PDF copy the owner saved beside the .docx, or ask the owner for one; for each .docx whose revision markup was not read, the audit row says `tracked changes not checked`, and DONE item 5 is open for that document. Never treat a .docx as clean because its markup could not be read.

## The return here

The shared block with these item tests and states, the draft and notes in `files`, the audit rows in `extra.audit`:

| Test | Item | States |
|---|---|---|
| `section` | a draft section | `drafted`, `placeholder`, `omitted` |
| `audit` | a document | `clean`, `findings`, `unreadable` |

`questions` go to `owner`: one per placeholder the owner must fill and one per high finding.

## DONE (bd-proposal-orchestrator checks each item and cites its evidence)

1. The newest owner copy was read first, or there was none (cite the file and its modified time).
2. The draft follows the reference document the rules name (cite it) and is no longer than it.
3. Every price, rate, payment term, term and termination is the owner's stated figure or a placeholder; no hour commitment, milestone date or acceptance test the owner did not ask for.
4. Every fact about the client in the draft is in the discovery notes or the record (`fact-check` says VERIFIED or the claim is removed).
5. The contract audit ran on the draft and every document in the folder with tracked changes read (a document marked `tracked changes not checked` leaves this item open and is a question to the owner), and `bd-contract-auditor` reports no `high` finding left unanswered (each is fixed in the draft or a question to the owner).
6. `executive-red-team`, reading as the client's buyer, finds no section graded below the bar without a fix applied or reported.
7. Nothing was sent, committed, or written outside the Run folder.

## Later tools

- `docx-redlines`: list tracked changes and comments from a .docx with author, date and location, so the auditor's `tracked-change` rows come from code.
- `contract-xref-check`: resolve every section, exhibit and defined-term reference in a document and list the ones that do not exist.
