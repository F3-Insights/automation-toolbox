# The CRM hygiene method

The CRM hygiene pass keeps the Insights Portal trustworthy for every agent that reads it. A duplicate contact or a wrong title does not merely look untidy: it silently changes what every downstream agent believes, and nothing announces that it happened. A pass that reports a clean Portal that is not clean has done more harm than one that reported nothing.

This file holds the method: where evidence comes from, the duties the pass covers, the metrics block and the failure modes. `SKILL.md` beside it narrows the scope and makes the pass an orchestrated one.

## Standing constraints

- **Never invent a fact.** A field changes only on evidence named in the pass note. Absence of evidence is a flag, never a fix.
- **Never delete anything.** Duplicates are listed for merge; a merge happens only on the owner's yes.
- **Never send anything outbound.**
- **The Portal is a shared surface.** Write every note as if a colleague will read it: factual and professional. Deal terms, compensation, personal matters and strategy internals never appear. Counts, ids, dates and statuses are fine; commentary about people is not.
- **Grounding.** Every fix cites the record that justified it (an email id and date, a note id, a Portal field). Every flag says what evidence would settle it.

## Evidence sources, in order of authority

1. **Email already synced in the Portal.** The primary stream. A signature gives a title; a thread names a relationship. Use `list_entities(entity_type="email", filters={...})` for discovery and `email_bodies` only for the few you must read. A subject line is enough to flag; a body is what you need before you change a field.
2. **Notes written by other pipelines and people.** A newer note that contradicts a field is strong evidence. A missing note is not evidence that nothing happened.
3. **Calendar events.** A meeting that occurred shows a relationship is live. A meeting not yet held is evidence of nothing.
4. **Chat messages, where the Portal holds them.** They slot in beside email. Where a fact likely lives in a chat the Portal does not hold, say so in the note: that is a real gap.
5. **The owner.** Last, sparingly, and never as a first move. A question earns its place only when a one-line answer unblocks a specific update already identified.

## Asking the owner

- At most three questions a pass, and most passes ask none or one. A question earns its place only when the owner's one-line answer unblocks an update already identified: not "what is the status of the Acme Components work" but "Acme Components proposal: still pending, or dead? One word updates four records."
- Each question names the records it unblocks and what each becomes under each answer.
- Before asking, look for the same question still open from an earlier pass, and never ask it again. Re-asking is how a pass gets ignored.
- Batch them: three questions in one pass beats one question in each of three passes.

## Gaps worth researching

A thin explanation on an active, important record (priority 1 or 2, or a gap impairing current work) belongs on the research queue, not on the owner's question list. Read the linked notes first: a short field does not prove the context is missing. Propose the entity for the enrichment queue (`crm-context-enrichment` holds the queue's rules); never propose everyone connected to the owner.

## Duty: integrity

1. **Duplicate contacts and companies.** Same name, near-identical names, one person under two email addresses, split interaction histories. Use `search` on surnames and company tokens. Rank candidate pairs by how much history each side holds: a duplicate with real history on both sides is the damaging kind.
2. **Wrong or missing `title` and `relationship_context` on active contacts.** Only contacts that are active and matter (priority 1 and 2, recent interaction). A blank field on a dormant contact is not a defect worth a line.
3. **Ownerless and unfiled tasks** are counted for the metrics only. The task-stack orchestrators own them.

Fix a missing factual field only when the fact is evidenced elsewhere in the Portal. Fill `relationship_context` only when a note or thread states the relationship plainly; if you would be summarising an impression, leave it blank and flag it. Never guess a title from a domain name or a company's industry.

## Duty: errors

1. **Exercise `data_health`** at `scope="summary"` and `scope="by_domain"`. Record the totals; their trend over passes is the point.
2. **Anomaly hunting.** Look for records changing in ways no person did, for example active contacts deactivated by something automated. Ask: does the change correlate with inbound mail arriving, with a sync run, with one sender domain? Is it a bulk pattern in one window or a trickle? A correlation reproduced across more than one record is a Portal defect: say so plainly, with the ids and timestamps.
3. **Other error classes**: references to ids that do not resolve, tasks attached to closed projects, contacts with no company where the email domain plainly matches an existing company, `sync_health` reporting a stale or failing inbox.

Data problems are fixed or flagged. Software problems are issue drafts. A duplicated contact is data; a tool that returns the wrong contacts is software. A good issue draft carries the evidence (the exact call, actual against expected), the impact (what silently breaks downstream) and a specific ask, and says plainly when the Portal behaves correctly and the fault is a client's.

## Duty: metrics

Every pass ends here, without exception: the trend across passes is what tells the owner whether the Portal is getting more trustworthy or less.

| Metric | How |
|---|---|
| Overdue count | open tasks due before today |
| Untouched-30d count | open tasks with no update in 30 or more days |
| Ownerless count | open tasks with no `owner_contact_id` |
| Duplicate-pair count | candidate pairs found this pass |
| `data_health` totals | the summary totals, and the by-domain worst offender |
| Open questions | open question tasks this pass raised and earlier passes left open |

A metric that could not be computed is printed as `unavailable` with the reason. Never print a zero you did not measure: a fabricated zero in a trend line is worse than a gap in one.

## Failure modes

- **Changing a record because it looks wrong.** Evidence or a flag, never a guess.
- **Reporting a clean Portal you did not verify.** Unmeasured is `unavailable`, not zero.
- **Filing a data problem as a software issue, or the reverse.** Different channels, readers and fixes.
- **Asking the owner what a synced email already answers.** The owner is the last source.
- **Nagging.** A repeated question is worse than none.
- **Editorialising in a Portal note.** Counts, ids, dates, statuses; no opinions about people.
- **Running a second pass because the first found a lot.** One pass; the rest goes under "Not covered" for the next one.
