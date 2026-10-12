---
name: unslop-proposal
description: Edit proposals, statements of work, master service agreements, contract exhibits and the cover notes that carry them, for a client executive who signs and possibly their counsel. The unslop router picks it whenever the text creates, limits or prices an obligation. Not for drafting a proposal or auditing contract conflicts; start bd-proposal-orchestrator.
---

# Unslop for proposals and contracts

## Who is reading

Two readers at once. The first is a client executive who will sign. Not a lawyer, limited time, and wants to know what they get, what it costs, when it happens, and what happens if it does not go as planned. If they cannot answer those four questions after one pass, the document has failed no matter how careful the drafting is.

The second is counsel, or the executive acting as their own counsel six months later during a disagreement. That reader reads adversarially, looking for a promise you did not intend to make, a term used two ways, a cross-reference pointing at the wrong thing. Every sentence gets read again in the worst possible light by someone who was not in the room.

Write for the first reader. Draft so the second finds nothing.

## How the universal principles bite here

Principles 1 and 3 apply unchanged. Generic capability language costs a signature, because it reads as filler in a document the client is paying to read. Principle 2 has an exception, and it is the main difference from the sibling skills. A defined term is not a coined label. It is a pointer to an exact definition elsewhere in the same document, and it must appear identically every time. Do not vary it for readability. "Services" does not become "the work" in the next paragraph.

Principle 4 governs the proposal and SOW portions. Describe what the client gets, not what the consultant does internally to produce it. Principle 5 is the whole exercise: a contract that reads as marketing invites the reader to discount the parts that actually bind.

Precision outranks brevity here, inverting the usual instinct. A twenty-five word sentence that can only be read one way beats a twelve word sentence that can be read two ways. Repeat the defined term instead of using a pronoun. Repeat the clause reference instead of writing "as described above". Compress the proposal prose, not the operative terms.

## Principles specific to this reader

### A promise is exactly as narrow as its words, not as its intent

Goal: nothing can be enforced against you beyond what you meant to commit. The client reads the sentence, not the intent behind it, so a specific list written to show competence becomes a checklist of things you owe.

Diagnostic question: if the client held me to this sentence literally, with no context and no goodwill, could I deliver it with the time and access the engagement gives me?

Before: a named list of reports the consultant will build. After: "The reports delivered are those the client project lead approves at each monthly checkpoint, and may include the following:" The list survives as an illustration, and the binding commitment becomes what is approved at the checkpoint. Use this construction wherever the honest answer is "whatever we decide once we see the environment".

### Do not volunteer an obligation nobody asked for

Goal: every clause either creates a right you need or limits an exposure you have. A clause that does neither is a place to be held later, added in exchange for nothing.

Diagnostic question: what changes if this clause is absent? If the honest answer is "nothing, but it looked thorough", delete it. Silence on a topic is a drafting choice, not an omission.

Before: "if Client later wishes to transition the deployment to its own environment, Consultant will assist with migration." After: no clause at all. If the client chose the consultant to host, a later move to client hosting is new work, and the contract should stay silent on it rather than promise it free. For any clause you are tempted to add for completeness: if the client will not ask for it, do not volunteer it.

### Every statement must be true under every path the document allows

Goal: a claim that holds in the expected scenario and fails in a permitted one is a defect, even if that scenario never happens. The reader will find it in the case where it fails.

Diagnostic question: list every option the document leaves open, including deployment model, hosting party, staffing, and termination timing, then read the sentence once per option.

Before: a sentence saying the client "may run the approval tool on its own servers under any hosting option". That is not true when the consultant hosts it. After: the sentence is limited to the option where it holds, keeping the plain wording: "Where the approval tool is installed on Client systems, Client may keep using it for internal purposes after this SOW ends." The same test applies to claims about your own posture. Security language says "practices-aligned" and never implies a certification the consultant does not hold.

### The document has to survive one careful reading, front to back

Goal: a reader going through it once, in order, can follow every reference and every list without backtracking. Confusion in a contract is where a dispute starts.

Diagnostic question: read it straight through as the signer. At any point, did I stop to work out what a label, number, or cross-reference was doing?

Before: a confidentiality clause with a sub-list numbered (i)(ii)(iii), then a second sub-list in the same clause numbered (x)(y). The reader asked why, which is the tell. After: the lists were consolidated into one and the sentence that had required the second was deleted. When a numbering scheme needs explaining, the clause is doing too much.

## Keep

Defined terms, capitalized consistently and used identically on every appearance, including where the repetition reads clumsily. Section cross-references stated exactly: "Section 5(b)" stays "Section 5(b)", never "the confidentiality section" or "above".

Legal incorporation language, verbatim from prior signed templates. If an SOW incorporates the MSA by reference, that language is not rewritten for tone, and it stays at the end of the SOW where it has always gone.

Conditions and qualifiers such as "as mutually agreed upon", "which may include", "to the extent", and "commercially". These look like hedging and are not. They are the scope boundary. Long sentences whose length comes from enumerated conditions also stay, because splitting them can change what the conditions attach to.

## Mechanics

No em dashes and no en dashes anywhere, including exhibits. No named client personnel in a proposal or SOW. Write "the client project lead" or "the workstream leads". People change roles, and naming them creates a dependency the client did not agree to.

Numbers appear only where they are commitments. Fees, notice periods, payment terms, and validity dates get exact numbers; goals do not. Before: "Finance will cut invoice approval time by 40 percent within two quarters." After: "Client finance should see invoices approved sooner and fewer late-payment fees." No percentage, no time horizon.

Durations are estimates with a stated mechanism in both directions. Say that the estimate can move either way, what happens to the fee if the work finishes early (it drops, or the client redirects the remaining time), and what happens if it needs longer (the consultant gives a revised estimate and the reason in writing before the extra time is spent). For example: "The ten-week schedule is an estimate. If the work finishes sooner, the remaining fee is reduced or applied to other work the client names. If it needs longer, Consultant will say so in writing, with the reason, before continuing."

Tooling commitments stay open on the how: "An invoice approval workflow as agreed with the client project lead, which may include approval by email reply, either as a separate tool or as a configuration of the client's existing accounting system, as mutually agreed upon."

SOW structure follows the owner's own prior documents, if they keep a house style, before any structure is invented. A common shape: numbered sections, Background first, bullets rather than dense paragraphs, incorporation language at the end. The SOW is the less legalistic of the pair, and the MSA carries the legal weight. Operative clauses run short. A clause permitting AI tools shows the pattern in four moves: state the use, state the protection, say how the use fits the confidentiality section by number, and close with who is responsible. For example: "Consultant may use software tools, including AI tools, to perform the Services and to handle Client materials. Those tools run under business licenses that keep Client materials confidential, and their use is permitted under Section 5(b). Consultant is responsible for the work product whatever tools it used."

The cover note carrying the package is very short and positive, offers to take feedback, and carries no dates before the signature. Every promise in the proposal must be checkable against the SOW's own words. If a proposal sentence describes an outcome the SOW does not scope, one of the two documents is wrong.

## Self-audit

1. Read every commitment sentence as an adversary. Which obligates the consultant beyond what the scope, the fee, or the access supports?
2. Which clause could be deleted with no loss of a right and no added exposure? Delete it.
3. Take each option the document leaves open, including who hosts and when either party can end it, and name the sentence that stops being true under one of them.
4. Does every defined term appear in one form, and every cross-reference point at the section it names?
5. Can the signing executive answer what they get, what it costs, when it happens, and what happens if it slips, after one read?
