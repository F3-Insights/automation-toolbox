---
name: engagement-closeout
description: "The engagement closeout job, loaded by projects-engagement-closeout and by the projects-reviewer it dispatches, not for a user request; extends project-engagement-workstream. Covers the Steps from a finished engagement to the closeout pack as drafts (acceptance evidence, the final invoice check against the SOW and billing ledger, lessons with sources, a name-free method harvest, an anonymized case study, closing task ops), the DONE checklist and section Check the closeout pack. For a run, start projects-engagement-closeout."
---

# Engagement closeout

Load `orchestration-workstream`, `project-engagement-workstream` and `task-stack-workstream` first. The goal: when an engagement ends, the owner knows that every acceptance item was delivered and confirmed, that every fee was invoiced and paid or what is still owed, what was learned and what method is worth keeping, and has a case study draft ready for the client's consent. Open tasks are closed on evidence. Nothing is sent or posted.

## Inputs

- **Engagement**: its name and its Context; read the Context first.
- **Instructions** (optional): they override the defaults, never a rules file.
- **Dry run**: say what would be drafted, tied and asked; dispatch nothing.

## Steps

For `projects-engagement-closeout`. Write a `RUN/LOG.md` line before each hand-off.

1. [judgment] Orient. Read the Context, `DELIVERY-RULES.md`, `ENGAGEMENT-CONTEXT.md`, the SOW, the `working` ledgers (`PLAN.md`, `DELIVERY-EVIDENCE.csv`, `RAID.csv`), the `billing` folder, and the Portal domain's open tasks. Whether the engagement is closed (fixed fee delivered, or an ongoing one ended) is the owner's call.
   → the rules and instructions do not say it is closed: step 6
   → dry run: step 6
2. [judgment] Already done? A closeout already filed in `working` is improved on as a proposal, never replaced.
3. [judgment] Write the closeout pack yourself, by section Write the closeout pack, keeping `RUN/claims.json` as you go.
4. [hand-off: projects-reviewer] Three reviewers in one message, each with the drafts and their sources only: section Check the closeout pack (items 1 and 4, with the SOW and the evidence cited); `review-numbers` on the final invoice check with the SOW and the billing files it cites (item 2); `review-red-team` with only the case study, a prospective client as reader and the purpose "would I hire this firm for a problem like mine". Save each verdict to `RUN/reviews/`.
   → a FAIL, a finding or a grade under the bar: step 3 (max 1)
5. [judgment] Write `RUN/changes.json` from the closing ops in the `task-stack-workstream` shape, `"orchestrator": "projects-engagement-closeout"`, `dry_run` as this Run is. It is not applied: the owner approves it first.
6. [judgment] Close. Walk the DONE checklist into `RUN/DONE.md`, write `RUN/STATUS.md`, and report the owner's decisions as one numbered list, each with a recommendation: whether the engagement is closed (when step 1 could not tell); any acceptance without confirmation; any amount owed either way (for the firm's billing run); the client's consent for the case study (once given, the owner launches marketing's case-study Automation with `drafts/Case Study <date>.md`); which harvest drafts to file in the skills inbox.
   → reported: done

## Write the closeout pack

In `RUN/drafts/`:

| File | What |
|---|---|
| `Acceptance <date>.md` | Each SOW acceptance item: `accepted` (evidence and the owner's or client's confirmation), `delivered` (evidence, no confirmation), `missing`; the source of each |
| `Final Invoice Check <date>.csv` | `line,sow_ref,basis,amount_due,invoiced,invoice_ref,paid,difference,note`, one row per fee line or month the SOW bills |
| `Lessons <date>.md` | What happened, why, what to do next time, each with a source; in the `lessons-learned` entry format strategy's pre-mortem appends to |
| `harvest/` | Method worth keeping, one draft per pattern in the house skill format, name-free, for the owner to move into the skills inbox |
| `Case Study <date>.md` | Problem, approach, outcome, anonymized, marked DRAFT, edited with `unslop-editorial` |
| `context-closeout.md` | The proposed closing revision of `ENGAGEMENT-CONTEXT.md` |

And for the engagement's open Portal tasks: `complete` on evidence, `cancel` on the rules' conditions, else a question, kept for `RUN/changes.json`.

Harvest method, not facts: a pattern that would help any engagement, with every client detail removed. Every acceptance state and every fee line cites the SOW section and the evidence or invoice, and goes in `RUN/claims.json`.

## DONE

1. Every SOW acceptance item has a state and evidence, or a question for the owner (reviewer).
2. Every fee line ties: invoiced against the SOW basis, paid against the ledger, differences named (reviewer, `review-numbers`).
3. Every lesson cites a source (a transcript, a status memo, a RAID row, a log entry).
4. The harvest drafts hold no client, person, company or product name and no figure from the engagement (reviewer).
5. The case study is anonymized, marked DRAFT, and the client's consent is the owner's question.
6. Every open Portal task in the engagement's domain has an op or a question.
7. The red team, reading the case study as a prospective client, at or above the bar.

## Check the closeout pack

For the `projects-reviewer`, given the drafts' paths, the SOW, the sources and the checklist items to check, never the drafter's reasoning.

- **Acceptance (item 1).** Every `accepted` row has evidence and a confirmation from the owner or the client; every `delivered` row has evidence; every SOW acceptance item appears. Open each cited source and confirm it shows what the row says.
- **Harvest (item 4).** Search every harvest draft for the client's name, its people, companies, products, places and figures from the sources. Each hit is a FAIL with the line.

Return the `orchestration-workstream` block with `extra.checks`, one per item, as `project-engagement-workstream` gives it.
