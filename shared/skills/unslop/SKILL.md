---
name: unslop
description: Router that removes AI-sounding writing from any text by principle, not by rule list. Reads the text, identifies who will read it, invokes the matching sub-skill (unslop-deliverable, unslop-email, unslop-proposal, unslop-editorial, unslop-technical) and applies the five universal principles. Must always apply to any drafted writing. Use for "unslop this", "make it sound less like AI", or when the audience is unclear; call a sub-skill directly when the audience is obvious.
---

# Unslop (router)

Edit text so it reads as written by a careful professional for a specific reader. This skill holds the principles that apply to all writing and decides which reader-specific sub-skill to run. The sub-skills hold what changes by reader. The old rule list survives as `symptoms.md` in this directory; it is a scanning aid, not the instruction.

## The five universal principles

Each principle states the goal, then the question to ask of a sentence. Apply the question; do not pattern-match.

1. **Information, not rhythm.** A sentence earns its place by what it tells the reader, never by how it sounds. Ask: can a clause be removed or reordered without losing a fact? If yes, the shape was doing the work. Rewrite flat. This one question catches the escalating series, the matched two-part contrast, the fragment followed by a maxim, and the closing epigram, without naming any of them.

2. **State the thing; do not name it.** A coined label, a metaphor, a nickname, or a clever heading asks the reader to decode before they can understand. Ask: does the reader learn more from the label than from the plain statement it replaces? If not, write the statement. Exception: a term that is defined once and used consistently (a glossary entry, a defined contract term, a named component in a design record) is vocabulary, not decoration. The test is definition and consistent use, not part of speech.

3. **Specific to this reader, or gone.** If a sentence could appear unchanged in a document for a different client, project, or audience, it says nothing about this one. Ask: swap the name; does the sentence still hold? If yes, delete it or replace it with the fact that only applies here.

4. **Write from the reader's side of the page.** The reader wants what they learn or must decide, not what the author did to produce it. Ask: does this line change what the reader knows or does? Process narration, reassurance, and transitions fail this test.

5. **Register is a promise.** The reader has an expectation of how this kind of text behaves. A paying client reads a deliverable as a record of work and judgment; a signer reads a contract as a set of obligations; an engineer reads a doc as instructions. Anything that reads as performance (cleverness, drama, rhythm for effect) spends the trust that register promised. The editorial sub-skill is the one place this principle relaxes, because that reader expects a voice.

## Invariants that do not change by reader

- No em dashes and no en dashes, anywhere, including ranges. Write "30 to 45 minutes" or "Weeks 2-3".
- Sentence-case headings except proper nouns.
- Straight quotes.
- No decorative emoji.

## Process

1. **Identify the reader.** Read the whole text first. Decide who receives it and what they will do with it. That decides the sub-skill, not the format of the text. A deck can be editorial; an email can carry a contract term.

2. **Invoke the sub-skill.** Use the Skill tool to load exactly one of the following, and say which one you chose in one line so the user can override.

   | Sub-skill | Pick it when |
   |---|---|
   | `unslop-deliverable` | The text is billed work product handed to a client who will act on it: decks, report-outs, executive updates, findings readouts, workshop summaries. |
   | `unslop-email` | The text is addressed to named people and sent as a message rather than delivered as a document, client-facing or internal. |
   | `unslop-proposal` | The text creates, limits, or prices an obligation: proposals, SOWs, MSAs, exhibits, and the cover notes that carry them. |
   | `unslop-editorial` | The reader is being taught or persuaded rather than receiving work product: seminar scripts, posts, newsletters, landing pages, teaching decks, thought leadership. |
   | `unslop-technical` | The reader is an engineer who has to act without asking: READMEs, ADRs, glossaries, design docs, code comments, runbooks, commit messages, PR descriptions. |

   If the text mixes readers (a deck with a contract slide, an email that attaches a proposal), split it and run each part under its own sub-skill. If the reader is genuinely unclear, state your assumption in one line and proceed; do not stop to ask unless the two candidate readers would produce different edits.

3. **Edit by principle.** Work through the text applying the five questions above and the sub-skill's reader-specific principles. Preserve meaning. Compress, do not cut substance.

4. **Scan the symptoms appendix.** Read `symptoms.md` in this directory and check the text against it. A match is a prompt to ask the relevant principle's question, never an automatic edit. In particular, a word on the metaphor list that the document has defined and uses consistently stays.

5. **Self-audit before returning.** Ask, in order: What in this text would make a careful reader suspect a model wrote it? Would the author say this sentence out loud to this reader? Did I remove any fact, number, name, or commitment while editing? Fix what those questions surface, then return the edited text with a short list of what changed and why, grouped by principle.

## What this skill does not do

It does not add voice, opinion, or texture to text whose reader did not ask for it. Deliverables, proposals, and technical docs are finished when every sentence carries a fact the reader needs and nothing else. Only `unslop-editorial` carries guidance on voice.
