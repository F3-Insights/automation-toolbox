---
name: client-update-workstream
description: "The job skill of reporting-client-update, not for a user request: one engagement's weekly client update (deck, or memo with cover email) as a first draft. Covers the standards every update keeps, the engagement context and its proposed revision, the window, sources by id, sections Read a batch, Write the update and Stage the cover email, the reviewer's checklists Check the facts (verdict JSON), Read the update cold and Check the cover email, and the claim shapes recorded with reporting-client-update-record. Done is reporting-client-update-check. Never sends. For a client update, start reporting-client-update."
---

# Client update workstream

This skill extends `orchestration-workstream`: keep its conduct. Load that skill if it is not loaded. What follows is what the client weekly update adds.

The result is a first draft of this week's client update that the engagement's builder can finish in an hour and the owner can approve in ten minutes: in the variant and house style the engagement's rules name, in the engagement's own Weekly Report folder, with every client-facing claim carrying its sources, two fact-checks over disjoint sources and a cold read behind it, and a review note that says exactly what the owner must confirm. The people who own the update keep their roles: this is the draft they would otherwise start from, and nothing is sent.

## Inputs

- **Engagement** (required): the engagement's Context name. Its rules folder holds `UPDATE-RULES.md` and the engagement context; its updates folder is the Weekly Report folder.
- **Week** (optional): `yyyy-Www`. Default: the current ISO week.
- **Length** (optional): `weekly` or `full`. Default: the rules' Default length.
- **Instructions** (optional): the owner's outline or notes. They outrank the defaults here, never the rules file.
- **The pack's first line**: `FRESH: <n> sources ... pack at <work>` or `STALE: <reason>; ... pack at <work>`. The week folder (`DIR`) is the folder that holds that `work` folder: on a dry run it is in the Run folder, otherwise in the Weekly Report folder. Pass `--week-dir DIR` to every command. STALE means some sources could not be read: carry on with what was packed and put the gap first in the review note.
- **Dry run**: the whole session runs into the dry-run week folder; no Portal draft is staged, no task is created, and the ledger goes to the Run folder.

## Steps

1. [script] Run `mkdir -p DIR/work/returns`, then `reporting-client-update-check ENGAGEMENT WEEK --week-dir DIR --format json`. Read `work/LOG.md` and resume from the first test not met; read the rules and every document they name, the engagement context, the previous update and its review note, and `sources.json`.
   → a person already filed an update dated this week: stop
   → every test met: done
2. [hand-off: reporting-worker] Read the sources (section Read a batch): batches of about twelve sources (or about 150 KB), each inside one half, one worker per batch in parallel. Save each return as `work/returns/reader-<n>.json`.
3. [judgment] Write the update (section Write the update): the draft, the review note, `work/claims.json`, `work/context-proposed.md` and, for a memo, the cover email.
4. [script] Record with `reporting-client-update-record ENGAGEMENT WEEK claims --from DIR/work/claims.json --week-dir DIR`, and for a memo `reporting-client-update-record ENGAGEMENT WEEK render --week-dir DIR` for the Word file.
   → refused: step 3 (max 2)
5. [hand-off: reporting-reviewer] Check the facts (section Check the facts), twice in parallel: half a with the claims, the draft and only the sources in `sources-a.md` plus the `previous` sources; half b with only those in `sources-b.md` plus the `context` and `previous` sources. Save each as `work/factcheck-<x>.json` and `.md`, and record it with `reporting-client-update-record ENGAGEMENT WEEK factcheck --checker <x> --from DIR/work/factcheck-<x>.json --week-dir DIR`.
6. [hand-off: reporting-reviewer] Read the update cold (section Read the update cold) with only what the client will see. Save it as `work/redteam.md`.
7. [judgment] Revise once: fix each contradicted or unsupported claim from the sources, cut it (`reporting-client-update-record ... cut --claim C7`) or flag it for the owner (`... flag --claim C7`); make the cold read's concrete fixes and the check's prose hits. Then record again, fact-check the changed claims only and read cold once more. Record the cold read with `reporting-client-update-record ENGAGEMENT WEEK review --kind redteam --state passed|failed --file DIR/work/redteam.md`.
   → contradicted or unsupported claims or blocking fixes left: step 5 (max 1)
8. [hand-off: reporting-worker] Stage the cover email (section Stage the cover email): a memo whose rules say Email delivery `outlook-drafts` and name one Recipient, not on a dry run.
   → a deck, `file` delivery, two or more Recipients, or a dry run: step 10
9. [hand-off: reporting-reviewer] Check the cover email (section Check the cover email) with the draft id, the pinned ids, the memo and the cover email file. Save its JSON verbatim as `work/email-check.json`; on PASS only, write `work/delivery.json`.
   → FAIL: step 8 (max 1)
10. [ask] One review request for the owner (section Ask the owner), as a task except on a dry run.
11. [script] Carry: `reporting-client-update-record ENGAGEMENT WEEK ledger --week-dir DIR` (on a dry run add `--ledger <Run folder>/UPDATES-LEDGER.csv`).
    → refused because a claim is contradicted: step 7 (max 1)
12. [script] Append the session to `work/LOG.md`, run `reporting-client-update-check` last and report.
    → written: done

Write the LOG line before each dispatch and record each return at once, so a session that stops part-way can be resumed by the next.

## Done is computed

`reporting-client-update-check ENGAGEMENT WEEK --week-dir DIR --format json` tests:

1. **sources**: the week is packed, with two disjoint, non-empty fact-check halves.
2. **files**: the variant's files are in the week folder (deck and review note; or memo, its Word file, the cover email and the review note), and a deck is well formed (timed notes on every slide, no blanks, inside the slot).
3. **claims**: every recorded claim appears in a source comment, and every comment's claim and source ids are known.
4. **factcheck**: both halves checked; every live claim verified, or flagged for the owner in the review note; none contradicted, unsupported or pending.
5. **redteam**: the cold read's verdict is recorded as passed.
6. **prose**: no banned character or phrase in the visible text.
7. **continuity**: every open item carried from earlier weeks answered as done, moved or dropped.
8. **context**: with an engagement context, `work/context-proposed.md` proposes its revision (numbered changes and the whole file) or says `No changes proposed`.
9. **review**: the owner's review request is recorded in `work/CONFIRMATIONS.md`.

Report its result, never your own view of it.

## Conduct here

- **The rules first.** The engagement's `UPDATE-RULES.md` and the documents it names say the variant, the audience, the house style, what never goes in and which document wins. They override this skill. Then the engagement context, then the week's sources.
- **Sources by id.** The week's sources are in `work/sources.json`, each with an id (`S001`), a role (`context`, `previous`, `folder`, `portal`, `repo`), a date and a `path`. Every fact and every claim names the ids it rests on. A source not in the pack is not a source: say what is missing.
- **Nothing invented.** No figure, date, owner, decision or status the sources do not state. Keep the source's hedges ("where possible", "being built"). A plan is never reported as done.
- **People's files are theirs.** The previous update, the playbook, the baselines and every file in the engagement folder are read only. Write only new files in this week's folder and its `work/`, plus the ledger through `reporting-client-update-record`.
- **The main agent alone keeps the books**: `reporting-client-update-record`, `work/LOG.md`, the evidence file, the ledger and the returns it saves. Workers and the reviewer never write them.
- **Never send anything**, never give a draft a final or client-facing name, never write to the reference or final folders the rules name, never edit or move a person's file.
- **Never write the engagement context or the rules file.** Their changes are proposals in the week folder (`work/context-proposed.md`, the review note's proposed rule changes) that the owner accepts.
- **Never open a file the rules' Never open list names**; figures come from the firm's own summaries.
- **Commercial matters, personnel news and anything said in confidence** are numbered questions in the review note, never text in the draft, unless the rules or the instructions say otherwise.
- **Briefing**: give a worker or the reviewer paths, ids and the instructions, never your view of the answer. A checker gets only the draft and its sources.
- One command per call, with no pipes, redirects, `&&` or variables.

## What the pack holds

`DIR/work/sources.json`: every source with its id, role, title, date, path and half (`a` or `b`); the week's `date`, `since` and `until`, the `window` (kind `since-previous`, `catch-up` or `first`, the last update's date, the gap and a one-line note), the engagement `context` (path, whether it exists, where the proposed revision goes), the cover email's `recipients`, the resolved file names (`files`), the carried open items (`carry`) and warnings. The context is source `S001` with role `context` when it exists. `sources-a.md` and `sources-b.md` list each half; `work/sources/` holds the materialised Portal items and the repo log.

No context file is a gap for the top of the review note: the draft goes ahead from the week's sources, and the writer proposes a first context from them. A `catch-up` window means the last update is old: the update covers the recent weeks only and says so near the top, and the review note offers the owner the full length.

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

`<week folder>/work/` holds `sources.json`, `sources.md`, `sources-a.md`, `sources-b.md`, `sources/S###.md` (materialised Portal items and the repo log), `context-proposed.md`, `UPDATE-EVIDENCE.csv`, `claims.json`, `factcheck-a.json` and `factcheck-b.json` (and their `.md`), `redteam.md`, `CONFIRMATIONS.md`, `email-check.json`, `delivery.json`, `delivery-result.json`, `LOG.md` and `returns/`. The engagement's cross-week ledger is `UPDATES-LEDGER.csv` in the Weekly Report folder.

`reporting-client-update-pack` writes the pack (the `sources*` files) before the session; `reporting-client-update-record` writes the evidence file and the ledger; `reporting-client-update-check` says what is done; `reporting-client-update-deliver`, the finish step, writes `delivery-result.json` after it, through productivity's email delivery.

## Read a batch

For `reporting-worker` (model sonnet), one batch per dispatch. The brief gives the `sources.json` path, the batch's source ids, the rules file's path, the context file's path and the window. The goal: every fact in the batch that a client update could use, extracted so exactly that the writer never has to open the source again and a fact-checker can find each one in seconds.

1. Read the rules file first (what the update covers, the never-include list, the Never open list), then the engagement context (so you know the people, the deliverables and what is outstanding, and can tell news from background), then `sources.json` for your batch's entries.
2. Read each source in your batch in full. A source you cannot open, or one the Never open list names, is a `notes` line ("S014 not readable: ..."), never guessed around. A `.docx`, `.pdf` or `.pptx` you cannot read as text is a note too.
3. Return facts in `extra.facts` (the shape below): one per distinct fact, decision, action, open question, risk or value signal, with its date, who, the source id, a verbatim quote of at most 25 words and where in the source it is. Copy figures, dates and names exactly as written. Take a meeting's date from inside the file, not its name.
4. Mark what the update must not carry, rather than dropping it: `"sensitive": "<why>"` for anything said in confidence, after the firm's people left, about a named person's performance, or commercial (fees, rates, invoices, scope, contracts).
5. Contradictions between your sources, or with the previous update or the engagement context (a date moved, a deliverable's state, a person's role), go in `findings` with both source ids. A fact that changes the context is an ordinary fact: the writer proposes the revision.

You judge nothing about importance and write no prose for the update. Return the `orchestration-workstream` block with `items` empty and the facts in `extra.facts`. You write nothing.

## Write the update

Run by the main agent, with `project-status-deck` (deck) or `comms-client-status-update` (memo) and `unslop-deliverable` loaded. The goal: a first draft the builder can finish in an hour and the owner can approve in ten minutes, in the engagement's own house style, where every claim can be traced in one step and nothing is said that the sources do not say.

1. **The rules, the standards, the context.** Apply the Standards above, then the engagement context (who reads this, what they care about, what was promised): choose and frame the week's facts by it without restating it. Then the rules file and every document it names, in its order of what wins: for a deck the playbook, deck guides and the newest approved deck (copy its CSS, navigation and notes code exactly; its content is never a source); for a memo the previous memos and the cover emails. The rules' never-include list and banned words bind every line.
2. **The facts.** Work from the reader returns and the previous update. For a `catch-up`, say so once near the top with the dates, report the most recent weeks, and offer the full length in the review note. Open a source yourself only to settle a doubt. A fact marked `sensitive` stays out of the draft and becomes a numbered question in the review note.
3. **The draft** at the exact path in `sources.json` `files`. A deck follows `project-status-deck` (Build mode): slides by what happened, full-sentence headlines, timed speaker notes on every slide inside the slot, "Draft" in the footer. A memo follows `comms-client-status-update` at the length asked, in the structure the rules give, as Markdown that renders to Word, and the cover email beside it as the rules describe (a subject line, then the body; its `To:` line names every recipient in `sources.json` `recipients`, in the rules' order).
4. **Source every claim** with the source comment below. A claim is any number, name, date, decision, ownership, status or cause and effect a reader could challenge, in the visible text or the notes. Number claims C1, C2, ... in reading order; one comment carries one claim.
5. **Account for the carry and the context.** Every carried open item is done (with its source), moved (reason and new date) or dropped (reason), in the draft's next steps or the review note. So is every deliverable in progress and every outstanding item the context lists: reported, or left out with the reason in the review note.
6. **claims.json** at `work/claims.json`: every claim with its text, source ids and location, the carry outcomes and the week's next steps, in the shape below.
7. **The proposed context** at `work/context-proposed.md`, as The engagement context says. With no context file, propose a first one from the week's facts, marking what only the owner can supply. Never edit the context file itself.
8. **The review note** as `project-status-deck` describes: gaps and defaults first, then facts to confirm (numbered, every flagged claim id named), judgement calls, commercial and sensitive questions, carry outcomes, proposed rule changes, and an empty owner's feedback heading. Then run `unslop-deliverable` on every word the client will see.

**Revision.** Fix each finding from the sources, cut it, or flag it for the owner, and keep claim ids stable (a cut claim's id is never reused). Edit the draft in place only if no person has changed it since you wrote it (compare with the LOG times); otherwise the fixes go in the review note.

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

Claim ids match `C<number>`, are unique and never reused. Every source id exists in `sources.json`. Every `carry` id is an id from the pack's `carry` list; `state` is done, moved, dropped or open (open only with a reason in `note`). The main agent records the file with `reporting-client-update-record ... claims`; a refusal lists the problems to fix.

## Check the facts

For `reporting-reviewer`, once per half. The brief gives the half (`a` or `b`), `work/claims.json`, the draft's path and only that half's sources (`sources-a.md` or `sources-b.md`, plus the `previous` sources, and for half b the `context` source). Never the writer's notes, the other half or the reader returns. Load `review-facts` and follow its checklist, with these lines added:

1. Check every claim in `claims.json` against your half only. A claim your half does not speak to is NOT IN MY SOURCES; the other half may verify it.
2. A claim of news that rests only on the context file is NOT IN MY SOURCES: the context is background, not this week's evidence.
3. A claim that changes a source's hedge ("being built" reported as "built") or reports a plan as done is CONTRADICTED.
4. Look also for what the draft leaves out that your sources say the reader must know (a date moved, a deliverable slipped): list it under omissions.

Return exactly this, then your prose: a fenced JSON list, one entry per claim, `[{"claim": "C1", "verdict": "VERIFIED" | "NOT IN MY SOURCES" | "CONTRADICTED", "quote": "...", "location": "..."}]`. These three verdict words are the ones `reporting-client-update-record factcheck` reads; any other word is refused. The main agent saves the list as `work/factcheck-<x>.json` and the prose as `work/factcheck-<x>.md`. A claim neither half verified is unsupported.

## Read the update cold

For `reporting-reviewer`. The brief gives only what the client will see (the draft and, for a memo, the cover email), the audience the rules name, and the purpose "the client's weekly status update; the reader decides what to unblock". Load `review-red-team` and read it as that reader. A reviewer's suggested ask of the client goes to the owner as a question, never into the draft. Return `review-red-team`'s block; PASS when every section meets the bar and every blocking fix is made. The main agent saves it as `work/redteam.md`.

## Stage the cover email

For `reporting-worker` (model opus), only for a memo whose rules say Email delivery `outlook-drafts` with exactly one Recipient. With two or more the cover email stays the file, addressed to every one of them on its `To:` line, because a pushed reply reaches only the sender of the email it answers; the finish step reports FILE and the owner addresses it in Outlook. The brief gives the recipient's address, the cover email file and the memo's path.

1. **Pin the contact**: `search` the Portal for the address, then `get` the contact. Exactly one contact holding that address, or return `BLOCKED:` with the candidates.
2. **Pin the thread**: `list_entities` with `entity_type` email, filters `contact_id` and `direction` received, newest first; the latest email from that contact is the one the draft answers. None means a new message (no `related_email_id`).
3. **Stage it**: `draft_create` with `subject` and `content` copied from the cover email file exactly (no rewording: the owner's review is of that text), `recipient_to` the one address, `related_contact_id` the contact id and `related_email_id` the email's bare id, no Cc, no Bcc, no `thread_id`; provenance `agent_slug="reporting-client-update"`.
4. Return the `orchestration-workstream` block with `extra`: `{"draft_id", "contact_id", "email_ref"}` (`email_ref` as `portal://email/<id>`). `draft_create` is your only write; you never update or delete another draft and never push one.

## Check the cover email

For `reporting-reviewer`. The brief gives the draft id, the pinned contact id and email ref, the memo, the cover email file and the rules file. Never the worker's return beyond those ids.

1. Run `reporting-client-update-draft-show DRAFT_ID`. Keep its `content_hash` exactly as printed: the record is valid for that content and no other.
2. **Same text.** The draft's subject and body are the cover email file's, word for word.
3. **Facts.** Every date, number, name and status in the body is in the memo, said the same way.
4. **No commitment** the memo does not make; **no ask** the memo does not carry.
5. **Recipient and thread.** `contact_id` is the pinned contact, `email_ref` is the pinned email, `recipient_to` holds only that contact's address, `recipient_cc` and `recipient_bcc` are empty, and the address is the rules' one Recipient.
6. **Voice.** The rules' banned phrases and characters; no em-dashes.

Any problem is FAIL. Return exactly one fenced JSON block, which the main agent saves verbatim as `work/email-check.json` and the finish step's email delivery validates (it refuses unless the verdict is PASS for this draft id and this content hash):

```json
{"verdict": "PASS", "draft_id": "<id>", "content_hash": "<exactly as printed>",
 "contact_id": "<pinned contact id>", "email_ref": "<pinned email ref>",
 "checked": {"dates": "ok", "numbers": "ok", "commitments": "ok", "coverage": "ok",
             "tone": "ok", "recipient_and_thread": "ok"},
 "fixes": []}
```

On FAIL, `verdict` is `"FAIL"`, each failing entry in `checked` is `"fail"`, and `fixes` is `[{"n": 1, "what": "...", "where": "...", "source": "..."}]`. On PASS the main agent writes `work/delivery.json`: `{"draft_id", "check", "contact_id", "email_ref"}`, `check` being the absolute path of `work/email-check.json`. Still failing after one redraft, there is no `delivery.json` and the review note says why.

## Ask the owner

One review request with the `comms-confirm` skill: `confirm new DIR/work/CONFIRMATIONS.md --question "Review the <date> update draft <draft file>; <n> facts to confirm in <review note>; accept or edit the proposed engagement context in work/context-proposed.md" --of "the owner" --channel task --due <update date> --by reporting-client-update`, then, except on a dry run, `confirm task DIR/work/CONFIRMATIONS.md <id>` so it is on the owner's task list.

## The Automation's steps

Before the session, the prepare step packs the week: `reporting-client-update-pack ENGAGEMENT --week WEEK` (with `--run-dir RUN --dry-run-if true` on a dry run). It reads the Portal domain through `report-weekly`'s collection and, for a Portal-backed engagement context, the settings `portal_mcp_config` and `portal_server`. After it, outside a dry run, the finish step runs `reporting-client-update-deliver ENGAGEMENT --week WEEK`. It delivers only when `reporting-client-update-check` says done and `work/delivery.json` is there, and only through productivity's email delivery (comms-reply-to-email's `email_deliver.py`, found in this toolbox checkout), which never sends.

## When no one is present

Everything runs the same. Questions for the owner go in the review note's numbered list and the one review task; the session never waits and never ends with `needs_owner`. Report the check's result, the files written, the claims by state, what the cold read changed, the gaps, and the owner's numbered questions.

## The return here

Workers return the `orchestration-workstream` block: a reader with `items` empty and its facts in `extra.facts`; the cover email stager with its ids in `extra`. The evidence rows come from `claims.json` and the verdicts, recorded by the main agent.
