---
name: waiting-on-tracker-method
description: "Reference loaded by the waiting-on-tracker agent, not for a user request: the step-by-step procedure for finding what the owner is waiting on in the Insights Portal. Covers whoami first, lens A (tasks in WAITING), lens B (delegated work overdue or stalled, with the task filter vocabulary), lens C (threads the owner wrote last, the 14-day window and 30-thread cap, and why a sent email has no recipient), lens D (the owner's promises, when asked), grouping and context lookups, and the five next actions. Not for drafting the nudges; use comms-follow-ups or comms-follow-up-orchestrator."
---

# Waiting-on tracker: the procedure

This is the procedure the `waiting-on-tracker` agent works through, in order, every run. The agent file holds the goal, the inputs, how to read this Portal without losing the run, the judgment calls, the hard rules and the fixed report format, including the promises and nudge marker blocks.

## Steps

### Step 1: whoami, always, first

Call `whoami` before anything else. Take `principal.contact_id` and `principal.org_member_id`, which are the owner, and `principal.timezone` with its `timezone_source`. Every timestamp this server returns is UTC; convert with that zone, not with a guess, and say so in the header if `timezone_source` is `"default"` (then the zone is UTC and nobody set it). Take `inboxes` as the set of mail you may read at all.

Everything below turns on knowing which person is the owner. An item is only "waiting on someone" because that someone is not them.

### Step 2, lens A: tasks parked in WAITING

```
list_entities(entity_type="task", filters={"status": "WAITING"}, limit=25, offset=0)
```

`status` takes one of TODO, IN_PROGRESS, WAITING, DONE, CANCELLED, and WAITING is the owner's own record that this is somebody else's move. Paginate to the end: the envelope is `{items, count, total, has_more, next_offset, limit_applied}`.

Narrow with `project_id`, `domain_id` or `related_contact` when the caller scoped you.

Who is being waited on comes from the task itself, and the field that should say it does not. `assignees` is often empty, so the two signals that work are `assigned_agent`, which names an agent the work was handed to, and the task's own title and description, which is where work handed to a person is actually recorded. The `owner` is who is accountable and `related_contact` is who the task is about; both are leads to confirm against the text, not names to print. Read the record with `get(entity_type="task", id_or_query="<id>")` where the listing does not carry enough, and say which signal you used. Where nothing but the owner is named anywhere, the task is WAITING on nothing the Portal can see: report it as `WAITING with no counterpart`, which is usually a task that should be TODO again or closed.

"Since when" is the date the task went into WAITING where the record shows it, and the task's last update otherwise. Say which you used.

### Step 3, lens B: delegated work that has stopped

Work the owner handed to somebody else, that is either past its date or has gone quiet.

```
list_entities(entity_type="task", filters={"assignee_contact_id": "<contact id>"}, limit=25)
list_entities(entity_type="task", filters={"assignee_user_id": "<user id>"}, limit=25)
list_entities(entity_type="task", filters={"assigned_agent": "<agent slug>"}, limit=25)
list_entities(entity_type="task", filters={"owner_contact_id": "<contact id>"}, limit=25)
list_entities(entity_type="task", filters={"due_before": "<today>"}, limit=25)
```

**The two assignee filters usually come back empty**, because nothing populates `assignees`. Run them anyway and never read an empty result as "nothing is delegated". The filter that works is `assigned_agent`, for work handed to an agent; work handed to a person lives in the task text, so read the titles and descriptions of the `due_before` and `owner_contact_id` results rather than waiting for a field to name somebody.

The filter vocabulary for tasks is `{domain_id, project_id, goal_id, status, priority, search, include_completed, due_before, due_after, assigned_agent, related_contact, owner_user_id, owner_contact_id, assignee_user_id, assignee_contact_id, no_domain, no_project, no_owner}`. Anything outside it is an error rather than a filter that quietly did nothing, so a response that came back is a response that was filtered.

Start from `due_before` today for the overdue half, and from the assignee filters for the people the owner has delegated to. Keep an item when **both** hold:

1. Somebody other than the owner has it: an `assigned_agent`, an accountable owner who is not them, or a person named in the task's own text. A task with nobody but the owner on it is theirs to do. `no_owner` finds the ones nobody is accountable for at all, which is its own finding, not a waiting-on item.
2. It is overdue against today, **or** nothing has moved on it inside the staleness window.

For "nothing has moved", use each record's own `updated_at`. A task whose `updated_at` is older than the start of the staleness window has not moved inside it. Do not reach for `activity_stream`: it takes `since` and `limit` only, has no offset, and personal-inbox noise fills it before older business items appear, so a task missing from the feed may simply have been pushed off the end of it. It cannot answer this question for a batch.

Exclude anything in DONE or CANCELLED. A `status` of WAITING here is already lens A; report it once, under A, and do not duplicate it.

### Step 4, lens C: threads the owner wrote last

The owner asked and nobody answered. This is the lens the Portal makes hardest, so follow it exactly.

**This lens can only catch silence after some contact.** A thread the owner started that nobody has ever answered has no counterpart anywhere in the Portal, so it can be listed but never chased by name. Count those separately in the header.

```
list_entities(
    entity_type="email",
    filters={"direction": "sent", "since": "<14 days ago, UTC ISO>"},
    limit=25, offset=0,
)
```

`direction` takes `received` or `sent` and nothing else. **Cap the window at 14 days** and work **most recent first**.

Two things in that response change what you keep. `direction="sent"` does not mean sent by the owner: an org-shared mailbox puts a colleague's message in the same listing with their `contact_id` on it, so check each message's `from_address` against the inboxes `whoami` gave you and drop the ones that are not the owner's. And the response carries an `inbox_scope` object with `accessible_inboxes` and `excluded_by_inbox`; a non-zero `excluded_by_inbox` means the sent history you read is provably incomplete, which goes in Gaps.

Then read the threads:

```
get(entity_type="email", id_or_query="<id>")
```

which returns the whole `thread` with `direction`, `received_at` and `sender` per message. **Cap the thread lookups at 30.** Thirty most recent sent messages is the budget; say in the header how many sent messages were in the window and how many threads you actually opened. Skip a message whose thread you have already opened rather than spending a lookup on the same conversation twice.

Keep a thread when its **last** message, by `received_at`, has `direction` of `sent`. That is the owner's word being the last word. Drop it when a later message has direction `received`; somebody answered.

Then apply the silence window: keep it only when that last sent message is older than the silence window in business days, counting Monday to Friday. A message the owner sent yesterday is not being ignored.

#### Who the counterpart is, and when you cannot know

**A sent email in this Portal carries no recipient.** Not in a listing, not in `email_bodies`, not in `get`. Its `contact_id` is the sender's own contact, which is the owner. There is no field anywhere in this surface that says who a sent message went to.

So the counterpart is whoever else appears as `sender` or `from_address` on that thread: any message with direction `received` names the person on the other side, and that is the person the owner is waiting on. Take the most recent such sender.

**Where nobody has ever answered, the recipient cannot be known at all.** Do not guess from the subject line, from a company, from who else has that surname, or from who the owner usually writes to. List the item by its subject and its `_ref` and nothing else, write the counterpart as `unknown: the Portal holds no recipient on sent mail`, and propose an action the owner can take without a name. It never becomes a nudge, because a nudge needs an address.

Read the body of a thread you are keeping, `email_bodies(ids=[...])`, **at most 10 ids per call**, so that "what is being waited on" is what was actually asked rather than what the subject line suggests. A `found: false` entry is an id you cannot see; count it and move on.

### Step 4b, lens D: what the owner promised

Only when the caller passes `lens_d: true` with a `since` date. Lenses A to C track what others owe the owner; this one tracks what the owner owes them.

Read the owner's sent mail since `since` (`direction: "sent"`, `from_address` among the owner's inboxes, most recent first, the same 30-thread cap shared with lens C). In the new text of each message only, before the first quoted `From:` line, find promises: "I'll", "I will", "let me check", "will get back", "will send", "by <day>". Discard pleasantries ("I will be in touch", "hope all is well") and promises already kept: a later sent message on the same thread, or to the same person, that does what was promised.

For each promise keep: the counterpart (the thread's other party, by the lens C rule; never guessed), the promise in 25 words or fewer, the stated date or `none stated`, the email `_ref`, and the evidence of delivery if you found any. A promise you are unsure is real is left out and counted in the header, never reported: a false promise becomes a task and a draft the owner must delete.

Report lens D items in their own group, "Owner promised", after lenses A to C, with `Lens: D`. The proposed action is one of: **deliver** (the thing exists and a cover note would deliver it), **re-date** (it does not exist yet; an honest new date is the message), **raise at a named upcoming meeting**, or **close as no longer needed**. Never propose a reminder to the owner. Lens D items do not count against the 15-item cap of lenses A to C; cap them at 10 of their own.

### Step 5: group first, then look up context only where it will change something

**Group before you look anything up.** Several small items waiting on the same person are one item and one nudge, never three. Name the person once, carry every `_ref`, and say in the item's ask what is outstanding across all of them. One message covering three things lands better than three messages.

Then take a provisional action per item and **look up context only for the items headed for a nudge**. A contact lookup per item is the most expensive part of the run, and it buys nothing on the items that were never going to become a message.

```
get(entity_type="contact", id_or_query="<their email address>", detail="summary")
```

An exact address resolves to the contact. A response carrying an `error` key is an address the Portal does not hold; say so and carry on with what the thread told you. **A contact record exposes no email address field at any detail level**, so the address you print is the one you resolved them by, or the `from_address` on a message they sent. It is not on the record and there is no point looking for it.

What that response changes is the ask: their priority, warmth and relationship context. A cold contact and a standing client contact take different asks.

The next meeting comes from one calendar read for the whole batch, not from the contact record:

```
list_entities(entity_type="calendar_event",
              filters={"since": "<now, UTC ISO>", "until": "<in 3 days, UTC ISO>"}, limit=25)
```

Match an event to a person by an attendee or by the title. Where one matches, the answer is not to write: raising it face to face is faster, lands better and costs nobody an email, so name the meeting and its date and propose raising it there.

### Step 6: propose exactly one next action per item

One of these five, no others, no inventions:

| Action | When it is the right one |
|---|---|
| **Nudge by email** | There is a named person with an address, the ask is clear, nothing is scheduled with them soon, and a message is genuinely the fastest route. |
| **Raise at a named upcoming meeting** | A meeting with that person is inside 3 days. Name the meeting and its date. |
| **Reassign or escalate** | The person has not moved on it twice, or has gone quiet past the point where another message helps. Name who it should go to only where the Portal shows that person: the project's owner, the task's accountable owner, their colleague already on the thread. Where the Portal shows nobody, write `escalate, to whom is the owner's call`. |
| **Convert to a decision the owner must make** | The item is stuck because of something only they can settle: a price, a scope, a commitment of their time, a yes or no to a person. State it as a question with the options the evidence supports. |
| **Close as no longer needed** | The evidence says it stopped mattering: the deadline passed, the project closed, the deliverable arrived another way. Give the evidence, not the impression. |

Never propose an action that needs a tool you do not have, and never propose two.

### Step 7: the report

Fixed format. The caller parses it. The format, the promises block and the nudge block are the agent file's Output section.
