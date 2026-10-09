---
name: marketing-content-workstream
description: Reference loaded by marketing-content-writer, marketing-content-checker and the marketing orchestrators, not for a user request; adds to orchestration-workstream and unslop-editorial. Covers MARKETING-RULES.md and the content library first, candidate posts mined from finished work, narrations and teaching under the library's topic rule, drafts in the owner's public voice, nothing identifying a client or person without written consent, case studies from closed engagements, drafts never published, and the DONE checklists of marketing-content-orchestrator and marketing-case-study-orchestrator.
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

## The return here

The shared block with these item tests and states, candidates in `extra.candidates`, drafts in `files`:

| Test | Item | States |
|---|---|---|
| `candidate` | an idea id | `proposed`, `drafted`, `parked` |
| `anonymity` | a draft | `PASS`, `FAIL` |
| `claim` | a draft | `sourced`, `unsourced` |

## DONE: a content Run (marketing-content-orchestrator checks each item and cites its evidence)

1. The candidate list holds at least the rules' number of ideas, each with a source or marked a general teaching point, and each meeting the topic rule.
2. The Run's drafts (default one; the rules' cadence sets it) exist with a hidden source on every claim about real work.
3. `marketing-content-checker` says PASS on anonymity, voice and length for each draft.
4. `fact-check` finds every sourced claim VERIFIED, or the claim was removed.
5. Nothing was published, scheduled, uploaded or sent (cite the Run folder as the only output).

## DONE: a case study (marketing-case-study-orchestrator checks each item and cites its evidence)

1. The engagement is closed by the rules' definition, and its closeout is cited.
2. The draft has the four parts, each sourced to the engagement's files.
3. Consent: the rules record the client's written consent for this piece, or the draft is marked `INTERNAL: not for publication until consent` and the consent request is a question to the owner.
4. Without consent, `marketing-content-checker` says PASS on anonymity; with consent, it checks only what the consent covers.
5. `fact-check` finds every claim VERIFIED; `executive-red-team`, reading as a prospective buyer, finds no section below the bar without a fix applied or reported.
6. Nothing was published or sent, and no one outside the owner was contacted.
