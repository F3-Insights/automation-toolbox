---
name: unslop-technical
description: "Edit technical writing for an engineer who has to act without being able to ask a question: README files, ADRs, CONTEXT.md glossaries, design docs, code comments, runbooks, commit messages and PR descriptions. The unslop router picks it for these. For a PR body's structure use software-pr; for where repository docs belong, software-doc-standards."
---

# Unslop: technical

## Who is reading

A future engineer who opened this file because they have to do something. Often the owner months from now. Often a Claude session with no memory of the conversation that produced the text. Either way the reader cannot ask a follow-up question, and will act on whatever the file says.

That fixes the standard. A sentence earns its place if it lets the reader act correctly.

Most technical slop is not decoration. It is a sentence that gestures at a capability without naming the thing that provides it, and the reader has to go read the source anyway. Naming the mechanism, the number, the file path, the command, or the decision and the reason behind it clears that bar. Telling the reader how the system feels to use does not.

## How the universal principles bite here

1. **Information, not rhythm.** A README paragraph that reads smoothly and names no function, no file, and no command is dead weight. Delete it or replace it with the call the reader has to make.
2. **State the thing; do not name it.** Technical writing needs proper nouns, so the line falls elsewhere. See "One word, one meaning, defined once" below.
3. **Specific to this reader, or gone.** "Built for speed and reliability" fits every repository on GitHub. Cut it, or replace it with the p95 latency and the retry policy.
4. **Write from the reader's side of the page.** They need the current state of the system and what to do next. A PR description that narrates the author's exploration buries both.
5. **Register is a promise.** Confident prose about a design that is still a guess will get the guess shipped. Say which parts are settled and which are not.

## Principles specific to this reader

### Name the mechanism, not the experience of it

**Goal.** The reader can do the thing after reading the sentence, or knows a fact they can check. Feelings about a system cannot be acted on and cannot be verified.

**Diagnostic.** After this sentence, what would the reader type, open, or check? If nothing, the sentence has no content.

**Example.** "The database stays close at hand" names a feeling and cannot be checked. "`.toSQL()` returns the exact string sent to the database" names a mechanism, and the reader can go call it.

### One word, one meaning, defined once

**Goal.** Every noun in the document either points at something in the code or has a definition the reader can find. A term that means one thing in the glossary and something else in the code sends the reader to the wrong file.

A defined term is not a violation of principle 2. Suppose an ADR for a small invoicing CLI defines "Ledger Entry" in its first paragraph, gives it a fixed shape (invoice id, line number, amount in cents, currency, posted date, source file), and the code uses the same word. That is vocabulary doing work. "Substrate", "harness", "north star", and "flywheel" dropped into prose without a definition do the opposite. They sound technical and leave the reader guessing which real component is meant. The test is whether the term is defined and used consistently, not whether it is a noun. If a repo's CONTEXT.md defines Store as the one module that persists invoices, that is fine, because the definition is right there and the codebase honors it.

**Diagnostic.** Can I point at the line that defines this term, and does the code use the same word? If no to either, use the plain name of the thing.

**Example.** "Invoices persist through the storage substrate" leaves the reader hunting. "Invoices are written by `invoicectl/store.py`, the Store module, to one SQLite file" names the file and the module.

### A decision is worth nothing without its reason and its date

**Goal.** The reader can tell whether a decision still applies to their situation, and what it would cost to reverse. A conclusion with no reason attached gets re-litigated by the next person, or worse, gets obeyed after the reason has expired.

So an ADR carries the date, the person who made the call, the options rejected, and why each was rejected. Amendments are appended with their own date and the session that produced them, rather than folded silently into the original text, so the reader can see what changed and when. A design doc states positions as claims that invite attack, not as settled conclusions, and says so in the status line.

**Diagnostic.** Could a reader who disagrees with this decision tell what evidence would change it?

**Example.** "We use SQLite" is an instruction with no defence. A better ADR records that the CLI runs on one machine with one writer, and that Postgres was rejected because it needs a server nobody wanted to run, which tells a future reader exactly which fact to re-check (a second concurrent writer) before changing the approach.

### Write the rule as the thing that catches the violation

**Goal.** Rules that live only in prose decay. Where a rule can be tied to a test, a lint, a type, or a build failure, say which one, so the reader learns both the rule and the point at which breaking it stops being possible.

**Diagnostic.** What fails, and where, when someone does the opposite? If the answer is "nothing", say that the rule is convention only, so the reader knows the enforcement is social.

**Example.** "Keep amounts in integer cents" is advice. "Amounts are integer cents, enforced by a CI type check that rejects `float` in `money.py`" tells the reader where the rule is checked and what will stop their PR.

## Keep

Do not strip these while editing.

- **Defined terms and their capitalization.** For example Invoice, Ledger Entry, Store, Customer, Batch, wherever the repo defines them. These are ratified vocabulary. Do not swap in synonyms for variety, and do not lowercase them into generic words.
- **Exact identifiers.** Table names, column names, file paths, function names, flags, env vars, error strings, version numbers. Never paraphrase one. `order_lines` is not "the join table".
- **Decision records in full.** Status line, date, attribution, rejected options, amendment log. Long is fine. An ADR is a record, not a summary.
- **Uncertainty stated as such.** "Rounding rule not yet decided", "unbuilt", "pending the first multi-currency customer", "revisit at 10,000 invoices". These are load-bearing. Deleting a hedge that marks real uncertainty turns a guess into an instruction.
- **Numbers, units, and limits.** Timeouts, row counts, retry limits, max depth. Keep the unit attached.

## Mechanics

- No em dashes and no en dashes. End the sentence or use a comma.
- Sentence case headings. No decorative emoji.
- File paths, commands, table names, columns, and function names in backticks. Commands in fenced blocks with the shell they run in.
- Numbers with units, always. "30s", "512 MB", "max depth 2".
- Active voice naming the actor. "The compiler validates queries", not "queries are validated". Passive only when the actor genuinely does not matter.
- Adverbs replaced by the measured number. "Runs quickly" becomes the benchmark figure or is cut.
- Plain word over the fancy synonym. Use, not utilize or leverage. Help, not facilitate. If, not in the event that.
- One idea per sentence. If the reader has to backtrack to parse it, split it.
- Commit messages say what changed and why in the imperative. PR descriptions state the current behavior after the merge, the risk, and how to verify, not the path the author took to get there.
- Code comments explain why this code and not the obvious alternative. A comment restating the line below it is noise.
- Runbooks are ordered steps with the command, the expected output, and what to do when the output differs. A runbook that describes the system instead of the procedure is a design doc filed in the wrong place.
- Glossary entries name where the thing lives in the code, and say which near-miss words to avoid, the way CONTEXT.md does with its `_Avoid_` notes.

## Self-audit

1. Pick any three sentences at random. For each, what would the reader type, open, or check next? If the answer is nothing, cut or rewrite.
2. Could this paragraph appear unchanged in another project's docs? If yes, it says nothing about this one.
3. Does every capitalized or unusual term have a definition the reader can reach, and does the code use that same word?
4. For every decision stated, is the reason, the date, and the person recorded, so a future reader knows what would justify reversing it?
5. Where the text tells the reader they must not do something, does it say what catches them if they do?
