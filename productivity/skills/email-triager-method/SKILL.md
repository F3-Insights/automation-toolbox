---
name: email-triager-method
description: "Reference loaded by the email-triager agent, not for a user request: the step-by-step procedure for triaging the owner's inbound email from the Insights Portal. Covers whoami first, listing the window's inbound mail with the exact email filter vocabulary and pagination to the end, reading bodies ten ids per call, checking the thread for the owner's own answer, the four classes (REPLY, DELEGATE, FYI, NONE) and the one-call context packet per REPLY sender. Not for triaging and drafting a batch with the owner; use comms-inbox-replies."
---

# Email triager: the procedure

This is the procedure the `email-triager` agent works through, in order, every run. The agent file holds the goal, the inputs, the judgment calls, the hard rules and the fixed report format the caller parses.

## Steps

### Step 1: whoami, always, first

Call `whoami` before anything else. Take from it:

- `principal.timezone` and `timezone_source`. Every timestamp this server returns is UTC. Convert the window into UTC yourself using that zone before you build a filter, and convert times back into it before you write them in the report. If `timezone_source` is `"default"` the zone is UTC and nobody set it; say so in your report rather than assume a local zone.
- `inboxes`. This is the exact set of mail accounts you may read, each with `kind` (`owned`, `org_shared`, `shared_with_me`), provider and `sync_status`. An inbox whose `sync_status` is not healthy may be missing recent mail; name it in your report.
- `token.class`. A `user` token is fenced to one member's inboxes, so a thin result may be a permission boundary rather than a quiet week. Say which it was.
- `principal.contact_id`, which is the owner. Mail from that address is the owner's own.

### Step 2: list the inbound mail in the window

```
list_entities(
    entity_type="email",
    filters={"direction": "received", "since": "<window start, UTC ISO>",
             "until": "<window end, UTC ISO>", "is_archived": false},
    limit=25, offset=0,
)
```

The email filter vocabulary is exactly `{contact_id, direction, status, priority, priority_tier, is_archived, since, until, search}`. Anything else is an error rather than a silently dropped filter, so a response that came back is a response that was filtered. Add `contact_id` when the caller scoped you to one person. For a domain scope, resolve the domain's people first with `search` or `list_entities(entity_type="contact", ...)` and run one listing per contact, because the email filter has no domain key.

**Paginate to the end.** The response is `{items, count, total, has_more, next_offset, limit_applied}`. Keep calling with `offset=next_offset` until `has_more` is false. Do not advance the offset by your own limit and do not stop at the first page; check `total` to confirm you saw everything. Keep the limit at 25: a result above roughly 60,000 characters fails outright rather than truncating, and a larger page is how that happens. On a size error, halve and retry once, then report the gap.

The response also carries an `inbox_scope` object with `accessible_inboxes` and `excluded_by_inbox`. A non-zero `excluded_by_inbox` means the mail you read is provably incomplete; name the count in Gaps rather than reporting a total you cannot stand behind.

If the window is long or an inbox is busy and the listing runs past a few hundred items, narrow by `priority_tier` for the lower-value tail and say in your report that you did.

### Step 3: read the bodies of everything that could matter

Most inbound mail is machine mail, and reading every body is expensive, so sort before you read. A listing item carries `from_address`, `subject`, `summary` and `priority`. Classify as NONE from the listing alone ONLY when the sender is plainly a machine (a no-reply or notifications address, a newsletter platform, a payment, receipt, security, calendar or social notification) AND the summary shows no person asking the owner for anything. When in doubt, read it. Everything else is read in full before it is classified: never judge a message from a person by its subject line.

Batch the ids through `email_bodies(ids=[...])` TEN ids per call. A larger batch can exceed the response size limit, and then the whole call fails. Read the returned `body`. A `found: false` entry is an id you cannot see; count it and move on rather than failing the batch. A `truncated: true` body was cut at 15,000 characters; say so if the cut matters to your judgment.

Read every thread you intend to classify as REPLY or DELEGATE. For the obvious NONE bulk (newsletters, delivery notifications, receipts, calendar system mail) a body read is still the rule, but you may read them in one batch and dispose of them in a line each.

### Step 4: check whether the owner already answered

Before calling a thread a REPLY, find out whether the owner replied after it arrived. The thread is the only place that answer lives.

```
get(entity_type="email", id_or_query="<the inbound message's id>")
```

The response carries the whole `thread`, one entry per message, each with `direction`, `received_at` and `sender`. Walk it and look for a message with `direction` of `sent` whose `received_at` is later than the inbound message you are judging, and whose `from_address` is one of the owner's own inboxes. `direction: "sent"` on its own does not mean the owner sent it: an org-shared mailbox puts a colleague's reply in the same place, under that colleague's `contact_id`. A colleague's answer is worth reporting as FYI, and it is not the owner's answer.

Do not try to confirm this by listing sent mail. A sent email in this Portal carries no recipient anywhere, in a listing, in `email_bodies` or in `get`, and its `contact_id` is the sender's own contact rather than the person it went to. So a `direction: "sent"` listing filtered by the sender's `contact_id` does not return the owner's replies to that person and cannot be used to answer this question. The `direction` filter itself takes only `received` or `sent`.

An answer already sent means the thread is not a REPLY. Say where it landed instead: FYI with a note that it is closed, or leave it out entirely if nothing turns on it.

A reply that answers only part of what was asked is still a REPLY. Say which part is open.

### Step 5: classify

Exactly one class per thread.

- **REPLY**: the owner has to answer, decide, approve, or say no. Anything where silence is itself an answer and the wrong one.
- **DELEGATE**: somebody else should handle it. Name who and why if the evidence says so (the message names them, the Portal shows them as the owner of that work, they are on the thread already). If you cannot tell who, say "owner unknown" rather than guessing a name.
- **FYI**: real correspondence that the owner should know about but that needs no answer.
- **NONE**: newsletters, marketing, system notifications, receipts, automated digests.

Where you are genuinely torn between REPLY and FYI, choose REPLY and say why it is borderline. A missed answer costs more than a line the owner skips.

### Step 6: one context packet per REPLY thread

The caller reads your report instead of the mail, so a REPLY block has to say who this person is to the owner as well as what they asked. Build that from the Portal, not from the message.

**Only for threads you classified REPLY.** Not DELEGATE, not FYI, not NONE. That cap is what keeps the report inside its length budget and the run inside its turn budget, and it holds even when a FYI sender looks interesting.

One call per REPLY sender, on their email address:

```
get(entity_type="contact", id_or_query="<sender email address>", detail="full")
```

An exact address resolves to the contact and returns hydrated context around it. Take only these, and take them from that one response:

| What you write | Where it comes from |
|---|---|
| Who they are to the owner | `contact.priority` or its tier, `company.name`, and `contact.relationship_context` reduced to a phrase |
| Open tasks with them | the task count, and the title and due date of the one most relevant to this thread |
| Last and next meeting | the most recent past meeting and the soonest upcoming meeting, with their dates |
| Unanswered mail | how many of their messages the Portal has as unanswered |

A response carrying an `error` key is an address the Portal does not hold. Write `Context: not a Portal contact` and move on; that is a fact about the sender worth knowing, not a failure.

Ask for `detail="full"` so the related sections come back hydrated and one call is enough. A busy contact can push that response past the size limit and fail the call outright; retry that one contact with `detail="summary"` and carry on. If a response comes back in the summary shape, with `task_ids` and `tasks_count` but no titles, report the counts and name no task. Do not spend a second call to hydrate them; the count alone is enough for the owner to decide, and a second call per thread is what turns a cheap step into an expensive one.

Two lines at most per thread. Write the phrase, not the record: "client CFO, priority 1, Acme; 2 open tasks, the contract review due Friday; met 3 Sep, next meeting 22 Sep; 1 other message unanswered" is the whole of it. Never invent a relationship, a priority or a meeting that the response did not carry.

### Step 7: the report

Fixed format. Follow it exactly; the caller parses it. The format is the agent file's Output section.
