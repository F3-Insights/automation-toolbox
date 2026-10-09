---
name: client-update-workstream
description: Reference loaded by client-update-reader, client-update-writer and client-update-orchestrator, not for a user request; adds to orchestration-workstream. Covers the standards every client update keeps, the engagement's UPDATE-RULES.md and context file (background, stakeholders, recent feedback, meetings, deliverables, outstanding, timeline) and its proposed revision, the window (since the last update, or a catch-up after a gap), sources by id from sources.json, a hidden source comment on every client-facing claim, nothing invented, and the facts, claims, carry and next-steps shapes recorded with client-update-record.
---

# Client update workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill if it is not loaded. What follows is only what the client weekly update adds.

## Conduct here

- **The rules first.** The engagement's `UPDATE-RULES.md` and the documents it names say the variant, the audience, the house style, what never goes in and which document wins. They override your own instructions and this skill. Then the engagement context (below), then the week's sources.
- **Sources by id.** The week's sources are in `work/sources.json`, each with an id (`S001`), a role (`context`, `previous`, `folder`, `portal`, `repo`), a date and a `path`. Every fact and every claim names the ids it rests on. A source not in the pack is not a source: say what is missing.
- **Nothing invented.** No figure, date, owner, decision or status the sources do not state. Keep the source's hedges ("where possible", "being built"). A plan is never reported as done.
- **People's files are theirs.** The previous update, the playbook, the baselines and every file in the engagement folder are read only. You write only the files your brief names.
- **No bookkeeping.** The orchestrator alone runs `client-update-record`, writes `LOG.md`, the evidence file and the ledger.

## Standards every update keeps

These hold for every engagement, whatever its variant, length or house style. The rules file adds to them and wins where it is stricter; the writer applies them and the checkers test them.

1. **What was done, then what it means, then what is needed.** The first screen or paragraph says what moved since the last update and what, if anything, the reader must act on. No status word stands in for that ("on track", "great progress").
2. **Recent first.** The window is the time since the last update (`window` in `sources.json`). A catch-up window (`window.kind` `catch-up`) covers the most recent weeks only: say once, near the top, that this is a catch-up after a gap and the dates it covers, and do not try to account for everything that happened in the gap.
3. **Back-context, not re-explanation.** The engagement context file (below) tells the writer who the readers are, what they care about, what was promised and what is outstanding. Use it to choose and frame; do not restate the engagement's background in the update. A background sentence appears only where a new reader would misread the week without it.
4. **Every deliverable and outstanding item answered.** Each item the context file lists as outstanding or in progress, and each item carried from the last update, is either reported (done, moved with the reason and new date, dropped with the reason) or left out on purpose with the reason in the review note.
5. **Owners are people, with a date.** Every next step names a person (with their role the first time) and a date, or says why there is no date. Asks of the client are only asks the sources or the owner's instructions support; a reviewer's suggested ask goes to the owner as a question, never into the draft.
6. **Sourced or flagged.** Every claim carries its source comment. A statement only the owner can stand behind is flagged for the owner, never sourced to the context file alone when it is news.
7. **Sensitive things stay out.** Commercial terms, personnel news, anything said in confidence, attribution of feedback to a named person and single-person anecdotes become numbered questions in the review note. Recent politics in the context file shape the framing; they are never quoted.
8. **Plain words for the reader.** A system term or acronym the reader does not use is explained in one sentence at first use or left out. Figures carry their unit and what they change in money, time or risk where the sources say.
9. **The house voice.** `comms-client-status-update`'s voice principles and cut list, the rules' banned phrases and characters, and `unslop-deliverable` on every visible word.
10. **Nothing sent, nothing final.** The draft is a draft with a draft's name; the owner sends.

## The engagement context

The engagement's run settings say where it is kept, as a `background` source: a path to a file, to a folder (the file the rules' `Engagement context` setting names, default `ENGAGEMENT-CONTEXT.md`, inside it), or a Portal ref, `portal://note/<id>` or `portal://project/<id>` (the note's content or the project's description, read in prepare, read only). With no `background` source it is `ENGAGEMENT-CONTEXT.md` beside `UPDATE-RULES.md` in the engagement's private rules folder. The rules say how the update is written; the context says what the engagement is and where it stands. The owner owns it. The pack lists it as the `context` source, and every worker reads it before the week's sources. It changes from client to client; its sections do not:

```markdown
# <Engagement>: engagement context

Private. Owner: <owner>. As of <yyyy-mm-dd>. Read by the client weekly update every Run;
agents propose revisions in the week folder and never edit this file.

## Background and goals
What the client engaged the firm to do, the outcomes, the phase now. Short paragraphs.

## Stakeholders
| Person | Role | Cares about | Gets the update |

## Recent politics and feedback
- yyyy-mm-dd · what was said or shown, by whom (role) · how it should shape the update · [source]

## Recent meetings
- yyyy-mm-dd · meeting · who · what was decided or asked · [source]

## Deliverables
| Deliverable | State | Date | Where | Source |
State: not started, in progress, delivered, accepted, paused.

## Outstanding
| Item | Owner | Due | Waiting on | Source |

## Timeline
| Date | Milestone | Planned or actual | Source |

## Changes
- yyyy-mm-dd · what changed · accepted by the owner
```

Every line carries its trace in brackets: a file name and section, or a Portal ref, and a date. A line no source supports is marked `(owner to confirm)`. Recent sections keep about the last 30 days; older items move to Background or drop out when the owner accepts a revision.

**The proposed revision.** Each Run the writer compares the week's facts with the context and writes `work/context-proposed.md` (`client-update-check` tests it): a numbered list of changes, each with the section, the old line (or "new"), the new line and the fact ids or source ids behind it (new feedback, a meeting, a deliverable delivered, a date moved, an item closed, a stakeholder's role changed), then the full revised file below a `## Proposed file` heading. With nothing to change it says `No changes proposed` and why. The owner accepts by copying the proposed file over the context (or the lines they agree with) and adding a Changes line. No agent writes the context file itself, and a Portal-backed context is never written to: the proposal is always the file `work/context-proposed.md` in the Run folder.

## The work folder

`<week folder>/work/` holds `sources.json`, `sources.md`, `sources-a.md`, `sources-b.md`, `sources/S###.md` (materialised Portal items and the repo log), `context-proposed.md`, `UPDATE-EVIDENCE.csv`, `claims.json`, `factcheck-a.json` and `factcheck-b.json` (and their `.md`), `redteam.md`, `CONFIRMATIONS.md`, `delivery.json`, `delivery-result.json`, `LOG.md` and `returns/`. The engagement's cross-week ledger is `UPDATES-LEDGER.csv` in the Weekly Report folder.

`scripts/client_update_pack.py` writes the pack (the `sources*` files) before the session; `scripts/client_update_record.py` writes the evidence file and the ledger; `scripts/client_update_check.py` says what is done; `scripts/client_update_deliver.py` writes `delivery-result.json` after it, through `comms-reply-to-email`'s `email_deliver.py`.

## The source comment

Right after the element that makes the claim, in the deck's HTML or the memo's Markdown:

```html
<!-- Source: C7 · S012, S015 · Pilot review 2026-09-22.md, "Decisions", 2026-09-22 -->
```

The claim id, then the source ids, then the human trace (file or item, section, date). The memo's Word file is rendered without the comments; the Markdown keeps them.

## The reader's facts (`extra.facts`)

```json
{"id": "F12", "kind": "decision", "text": "Pilot moves to two teams in November",
 "when": "2026-09-22", "who": "the sponsor", "sources": ["S012"],
 "quote": "we'll take it to two teams in November", "location": "00:31:10",
 "sensitive": null}
```

`kind` is one of fact, decision, action (with `owner` and `due` when stated), open-question, risk, value-signal. `sensitive` is null or the reason it must stay out of the draft.

## The writer's claims.json

```json
{"claims": [{"id": "C1", "text": "Two outcomes moved into build", "sources": ["S012"],
             "location": "slide 2"}],
 "carry": [{"id": "L-1a2b3c4d", "state": "moved", "text": "Confirm the pilot teams",
            "note": "waiting on the sponsor's list", "new_due": "2026-10-16"}],
 "next_steps": [{"text": "Send the pilot team list", "owner": "the sponsor", "due": "2026-10-16"}]}
```

Claim ids match `C<number>`, are unique and never reused. Every source id exists in `sources.json`. Every `carry` id is an id from the pack's `carry` list; `state` is done, moved, dropped or open (open only with a reason in `note`). The orchestrator records the file with `python3 ~/.claude/skills/client-update-workstream/scripts/client_update_record.py ... claims`; a refusal lists the problems to fix.

## The fact-checker's verdicts

The orchestrator saves each checker's verdicts as `work/factcheck-<a|b>.json`: `[{"claim": "C1", "verdict": "VERIFIED" | "NOT IN MY SOURCES" | "CONTRADICTED", "quote": "...", "location": "..."}]`, one per claim.

## The return here

The shared block. `items` stays empty: the evidence rows come from claims.json and the verdicts, recorded by the orchestrator. The reader puts its facts in `extra.facts`; the writer lists its files in `files`, the owner's numbered questions in `questions`, and `extra.claims`, `extra.flagged` and `extra.unslop`.
