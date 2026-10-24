---
name: marketing-content-workstream
description: "Reference loaded by the marketing main agents (marketing-post-writer, marketing-case-study-writer) and the marketing-worker and marketing-reviewer they dispatch, not for a user request; adds to orchestration-workstream and unslop-editorial. Covers MARKETING-RULES.md and the content library first, nothing identifying a client without written consent, drafts never published, the candidate list and draft shapes, and the sections Mine candidates, Draft a post, Draft a case study, Revise on findings and Check a public draft. The job Steps and DONE lists are in marketing-posts and marketing-case-study."
---

# Marketing content workstream

This skill extends the `orchestration-workstream` skill: keep its conduct and return its block. Load it if it is not loaded. The editing standard is the `unslop-editorial` skill; read it before drafting. This skill adds what a public post or a case study needs before the owner reads it.

## Conduct here

- **The rules file first.** `MARKETING-RULES.md` (its path comes from the Run's marketing Context, or from the caller) names the content library (the backlog by lane, the topic rule, the cadence), the positioning document, the public voice rules, the source folders agents may mine, where drafts land, and the channels. It overrides this skill.
- **Drafts only.** Nothing is published, scheduled, uploaded to a CMS, posted to a social account or sent. A draft is a file in the Run folder; the owner and their team publish.
- **Anonymous by default.** No client, company, person, place, figure or detail that lets a reader identify a client appears in a draft unless the rules record that client's written consent for that piece. Use the rules' descriptors ("a regional health system", "a specialty manufacturer"). Figures are rounded or relative unless consent covers them.
- **Mine, never invent.** Every claim of what happened, what it cost and what changed traces to a source file (a finished deliverable, a narration transcript, a session's notes). A general point the owner teaches needs no source; a story about work does.
- **The owner's public voice.** First person, practitioner, plain, real numbers, short. The rules and the owner's voice guide (setting `voice_guide`, or the voice file the rules name) win over `unslop-editorial` where they differ. The `brand-guide` skill holds the house voice and tone rules for anything branded.
- **Consent is the owner's ask.** An agent never contacts a client about a case study and never drafts that request to the client; a consent request is a question to the owner.

## The candidate list

`candidates.json`, one row per idea: `id, lane, title, angle, source, source_ref, magnet, why_now, risk, state`. `magnet` says how the idea meets the library's topic rule; `risk` names anything that could identify a client; `state` is `proposed`, `drafted`, `parked`, `published` (only on the owner's evidence). A refresh of the library is proposed as rows, never written into it.

## The draft

`drafts/<id> <slug> v<n>.md`: a title, the body, and a hidden source comment after every claim about real work (`<!-- src: <source_ref> -->`), plus `drafts/<id>.notes.md` with the channel, the length against the rules, each anonymization made, and anything the owner must decide.

A case study adds the frame: situation, what was done, what changed, what the reader can take from it, each part sourced to the engagement's closeout and deliverables.

## Mine candidates

Run by the main agent. Read the content library and the sources the rules allow that were added since its last refresh (finished deliverables, narration transcripts, teaching sessions' notes, and the content scout's distillations in the research folder when the rules list it). Propose candidate rows in the shape of The candidate list, each meeting the topic rule as the rules state it, with its source, why now and the identification risk. A refresh of the library is proposed rows, never written into it.

## Draft a post

Run by the main agent for one post, or by `marketing-worker` (one post each, in parallel) when the Run drafts several. Given the rules file's path, the chosen candidate row, its sources, the owner's voice file and the output folder. Load `unslop-editorial` (and `unslop`, whose principles it applies first) before writing. Draft to the rules' channel and length, in the owner's public voice, anonymized by default, with a hidden source comment after every claim about real work, and the notes file beside it, in the shapes in The draft. Write only in the output folder; publish nothing.

Return the `orchestration-workstream` block with `workstream: "draft-a-post"`, the `claim` item for the draft, and `files` the draft and notes.

## Draft a case study

Run by the main agent. From the closeout's case study draft (the closeout's `Case Study <date>.md`, when there is one), the closeout, the deliverables and the consent entry, write the four parts (situation, what was done, what changed, what the reader can take from it), each sourced to the engagement's files, at the rules' channel and length. Without consent, mark the draft `INTERNAL: not for publication until consent` at the top.

## Revise on findings

Run by whoever drafted. Answer each numbered finding the reviewer returned: fix it, or say in the notes file why not. Change nothing a finding does not name. One revision per Run; a second FAIL is reported, not revised again.

## Check a public draft

For `marketing-reviewer`, given the drafts, the rules file's path and the client list it names, never the writer's notes or reasoning. Read each draft as a stranger who knows the owner's clients. Per draft:

1. **Anonymity.** No client, company, person, product, place, exact figure, date or quirk that lets a reader who knows the market identify the client, beyond what the rules' consent entry for this piece covers. Grep the draft for each name on the client list.
2. **Topic rule.** It meets the content library's topic rule as the rules state it.
3. **Voice and length.** It reads as the owner's public voice file says, at the rules' length.
4. **No promise.** It offers no price, guarantee, result or availability for the owner.

Return the `orchestration-workstream` block with `workstream: "check-a-public-draft"`, one `anonymity` item per draft, `PASS` or `FAIL`, `note` the failed test and one fix each.

## The return here

The shared block with these item tests and states, candidates in `extra.candidates`, drafts in `files`:

| Test | Item | States |
|---|---|---|
| `candidate` | an idea id | `proposed`, `drafted`, `parked` |
| `anonymity` | a draft | `PASS`, `FAIL` |
| `claim` | a draft | `sourced`, `unsourced` |
