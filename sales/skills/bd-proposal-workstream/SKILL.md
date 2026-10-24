---
name: bd-proposal-workstream
description: "One pursuit's proposal or SOW drafted and its contract documents audited, run by sales-proposal-writer and checked by sales-reviewer, not for a user request; adds to orchestration-workstream and unslop-proposal. Covers the rules file and the owner's own executed documents before any structure is invented, the owner's newest copy re-read before every revision, its Steps, the section Draft the proposal (short, scope as qualitative goals, price and terms left to the owner), the checklist Audit the contract documents (tracked changes opened, cross-references resolved, payment, term and termination compared across executed documents), the return shapes and the DONE checklist."
user-invocable: false
---

# Proposal and contract workstream

This skill extends `orchestration-workstream`: keep its conduct. The editing standard for the prose is `unslop-proposal`; read it before drafting. It gives the owner a first draft they can rewrite in minutes instead of writing from blank, and catches what a plain read misses: a changed fee in tracked changes, a reference to a section that does not exist, two signed documents that disagree.

## Inputs

- `bd_rules` (required): the owner's `BD-RULES.md`; its `## Proposals` section wins over this skill. The proposals folder and reference documents come from it or the BD Context.
- **Pursuit** (required): the pursuit's name; its folder and discovery notes come from the rules or the Context. An automation backlog filed for the engagement (`automation-backlog-format`) is discovery input: the chosen items are the scope, written as qualitative goals.
- **Pass** (optional): `draft` (draft, then audit) or `audit` (audit the folder's documents only). Default: `draft`.
- **Instructions** (optional): the owner's direction for this draft (scope they want, terms they have stated). They override the defaults, never the rules file.
- **Dry run** (optional): plan the draft and list the documents to audit; dispatch nothing.
- `RUN` is the working folder; write only there.

## Conduct here

- **The rules file first.** `BD-RULES.md`, section `## Proposals`, names the house style (section numbering, framing, the closing acceptance block), the reference documents (the owner's executed SOWs and master agreements), where drafts land and how they are named, and the positions the owner holds on terms.
- **The owner's newest copy wins.** The owner edits drafts in place and renames them. Before any draft or revision, find the newest file in the pursuit's folder by modified time, read it, and build from it. Never regenerate from an earlier agent version.
- **House precedent before structure.** Start from the reference document the rules name for this kind of work. Do not invent sections it does not have.
- **Short.** A first draft is shorter than feels complete. Background is plain narrative. Scope is written as qualitative goals; no hour commitments, milestone dates, acceptance tests or protective clauses the owner did not ask for. Binding language lives only where it binds.
- **Price and terms are the owner's.** Fees, rates, payment terms, term and termination are placeholders (`[FEE: owner]`) unless the brief or the record states them. Where a figure is given, also state the total over the term.
- **Confidential reasons stay out.** A reason the owner gave for a choice is input to judgment, never text in the document.
- **Read, never commit.** Contract folders and repositories are read only. Drafts are new files in the Run folder, named as the rules say, with a version suffix; the owner moves them. Nothing is sent, and no cover email is drafted.
- **Questions** go in the report as one numbered list, never asked live.

## Steps

For `sales-proposal-writer`.

1. [judgment] Orient. Read the rules, then the pursuit's folder listing with modified times: note the newest owner copy, the executed documents and the discovery notes.
   → no rules file or no pursuit folder: stop
   → dry run (the planned draft and the documents to audit, in the report): step 6
   → pass audit: step 3
2. [judgment] Draft the proposal (section Draft the proposal) into `RUN/drafts/`.
3. [hand-off: sales-reviewer] Check, all in one message, each with the documents only, never the notes or your reasoning: section Audit the contract documents with the draft and every document in the folder; `review-facts` with the draft's client-fact list and the discovery sources; `review-red-team` with only the draft, the client's buyer as reader and one line of purpose. On pass audit, the audit alone, on the folder's documents.
   → pass audit: step 6
4. [judgment] Revise once: answer the high and medium audit findings, the claims not verified and the red-team fixes in `v<n+1>`, re-reading the newest owner copy first.
5. [hand-off: sales-reviewer] Audit the revision only (section Audit the contract documents).
6. [judgment] Record and close. Write `RUN/audit.json` (the audit rows), `RUN/reviews/` (each return as received) and `RUN/DONE.md` item by item. Report: the draft's path and length against the reference; the audit findings by severity, high ones in full; the facts and red-team verdicts; the DONE checklist with evidence; and the placeholders and high findings as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## Draft the proposal

Run by the main agent. A draft short enough that the owner cuts little, built on the owner's own precedent, with every number and term left to the owner and every client fact traceable to the discovery notes.

1. Find the newest file in the pursuit's folder; if it is the owner's, build from it (a PDF with `pdf-handle --operation text --pdf-path FILE`; a .docx as Reading .docx says).
2. Read the reference document the rules name for this kind of work and follow its structure.
3. Draft from the discovery sources only (the notes, the record, a filed automation backlog); list each client fact with its source in the notes file.
4. Leave every price, rate and term as a placeholder unless the brief states it.
5. On a revision, answer each finding: fix it, or say in the notes why not.

`drafts/<name> v<n>.md` (and `.docx` when the rules ask and a converter is granted), plus `drafts/<name> v<n>.notes.md`: each placeholder the owner must fill, each choice made from a reference document with its source, every sentence that needs the owner's judgment, and the client-fact list the facts check reads.

## Audit the contract documents

For `sales-reviewer`, given the draft (on a draft pass) and every executed or in-flight document in the pursuit's folder, never the drafter's notes or reasoning. Edit nothing. You find what the owner cannot see in a plain read, and report nothing the text does not show.

1. List the documents and their dates; mark which are executed.
2. Per document: open tracked changes and comments (a PDF with `pdf-handle --operation text --pdf-path FILE`, which prints each page's text and then the comments; a .docx as Reading .docx says); resolve every internal reference.
3. Across documents: compare fees, payment terms, term and renewal, termination, precedence and the parties. A conflict with no precedence clause to settle it is `high`.

Each finding is one row:

`id, document, location, kind, finding, quote, against, severity, fix`

- `kind` is one of `tracked-change` (an insertion or deletion, with author and date when the file holds them), `cross-reference` (a section, exhibit or defined term that does not exist), `contradiction` (two documents, or two clauses, that cannot both hold: payment terms, term and renewal, termination, fees, precedence), `missing` (a term one document relies on that none defines), `drift` (a figure or name that differs between versions).
- `quote` is verbatim, at most 30 words; `against` is the other document and location.
- `severity` is `high` (money, term, termination, liability, signature authority), `medium`, or `low`.
- Tracked changes are always opened: read the revision markup, not only the visible text. A change that alters a fee, a term or a party is `high` whoever made it.

Return the `orchestration-workstream` block with `workstream: "contract-audit"`, one `audit` item per document (`clean`, `findings`, `unreadable`), `extra.audit` the rows, and `questions` one per `high` finding. The verdict is FAIL while a `high` finding stands.

## Reading .docx

No granted command reads a .docx's revision markup yet (`docx-redlines` below). Until it exists, read the text or PDF copy the owner saved beside the .docx, or ask the owner for one; for each .docx whose markup was not read, the audit row says `tracked changes not checked`, and DONE item 5 is open for that document. Never treat a .docx as clean because its markup could not be read.

## The return here

The draft's item tests and states, the draft and notes in `files`, the audit rows in `extra.audit`:

| Test | Item | States |
|---|---|---|
| `section` | a draft section | `drafted`, `placeholder`, `omitted` |
| `audit` | a document | `clean`, `findings`, `unreadable` |

## DONE (the main agent checks each item and cites its evidence)

1. The newest owner copy was read first, or there was none (cite the file and its modified time).
2. The draft follows the reference document the rules name (cite it) and is no longer than it.
3. Every price, rate, payment term, term and termination is the owner's stated figure or a placeholder; no hour commitment, milestone date or acceptance test the owner did not ask for.
4. Every fact about the client in the draft is in the discovery notes or the record (`review-facts` says VERIFIED or the claim is removed).
5. The contract audit ran on the draft and every document in the folder with tracked changes read (a document marked `tracked changes not checked` leaves this item open and is a question to the owner), and no `high` finding is left unanswered (each is fixed in the draft or a question to the owner).
6. The red-team check, reading as the client's buyer, finds no section graded below the bar without a fix applied or reported.
7. Nothing was sent, committed, or written outside the Run folder.

## Later tools

- `docx-redlines`: list tracked changes and comments from a .docx with author, date and location, so the audit's `tracked-change` rows come from code.
- `contract-xref-check`: resolve every section, exhibit and defined-term reference in a document and list the ones that do not exist.
