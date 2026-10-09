# Brief: phase 2, reconcile open tasks against one day's sent mail

## The question

Which of the owner's open tasks did they finish on this date, by the mail they sent or a meeting recap? You match, verify the doubtful matches, and propose DONE only for high-confidence matches. You propose; the finish step writes, through `sweep-apply`, after the session. You never cancel anything and never ask anyone.

## The inputs

- The date and its window (local midnight to local midnight, as UTC).
- The path of `RUN/<date>/emails.json`; its `sent` rows are the day's sent mail, already limited to the window.
- The path of `RUN/<date>/tasks.json`: every open task (TODO, IN_PROGRESS, WAITING), pulled in code by `sweep-tasks` before the session. A header (`owner_contact_id`, `counts`, `errors`) is followed by one task per line, P1 first, then by due date. A row leaves out empty fields; its keys are `id`, `title`, `status`, `priority`, `due`, `overdue_days` (days past due on the date), `project`, `domain`, `owner` (`"self"` for the owner's own task, else that contact's id, with `owner_name`), `updated` (date of the last update), `contact` and `contact_id` (who the task is about), `company_id`, `waiting_on`, `waiting_on_id`, `waiting_since`, `waiting_reason` and `email_id`.
- The path of `rules.md` in this skill's folder. Read "Task reconciliation (phase 2)" first.
- Your turn budget: 25 turns.

## What to do

1. Read `rules.md` and the `sent` rows of `emails.json`.
2. Read the open tasks from `tasks.json`, never from the task listing: hundreds of open tasks do not fit in your turns as listing pages. Read the whole file, every row, in slices: the file (hundreds of kilobytes for a long task list) is too large for one `Read`, so read it with `Read` offset and limit in slices of about 200 lines, from the first line to the last, until a slice returns fewer lines than you asked for. Then Grep the file for each recipient's contact id (`recipient_contact_ids`) and name, their company, and the distinctive words of each sent subject and recap title; Grep prints the whole row. If a tool is denied or you run short of turns before the last slice, stop reading, say so under `errors` with the last line you read, and go on with what you have. `get(entity_type="task", ...)` is for a task you are about to propose or cite, to see its `note_ids` and description; it is never a way to enumerate tasks. When the header's `errors` names unreadable rows, say so under `errors`. Without `tasks.json` (the dispatch says the pull failed), look up only the tasks the day's evidence names, with `list_entities(entity_type="task", filters={"search": "<name or word>"}, limit=25)`, and report the stale scan as not done under `errors`.
3. Get the date's meeting notes: `list_entities(entity_type="note", filters={"since": "<window since>"}, limit=50)` (the note listing has no `until`; drop notes created at or after the window's `until`). Keep notes whose title carries a meeting name or a date, and discard any whose sections under Talking Points, Action Items and Notepad hold nothing but a meeting recorder's placeholder prompts. For an open task whose record lists `note_ids`, read those notes too.
4. Group the sent mail: scheduling ("Accepted:", "Invitation:"), deliveries ("attached", "here is", "sending over"), follow-ups (recipient names or companies in task titles), replies ("Re:", "Fw:").
5. Match each sent email and each kept recap against the open tasks with the table in `rules.md`, on names, companies, verbs (schedule, send, follow up, respond, propose, deliver) and topic words.
6. For each MEDIUM match, read the email (`get(entity_type="email", id_or_query="<id>")`, then `email_bodies(ids=[...])`). Upgrade it to HIGH only when the content clearly resolves the task; otherwise it is a possible completion.
7. Look for stale tasks over the rows you read: tasks 7 or more days past due (Grep `overdue_days`; the header's `past_due_7_or_more` is the count), a scheduling task whose meeting already happened, a reply task whose thread the sent mail resolved, and duplicates (Grep a distinctive title word). Report the most consequential, P1 and P2 first; never propose cancelling one.
8. Return the block below.

## Rules

- Propose `set_status` DONE for HIGH matches only, each with its evidence (what was sent, to whom, when), `evidence_ref` and `handle`. `evidence_ref` is the `portal://email/<id>` of one of the `sent` rows of `emails.json`, or the `portal://note/<id>` of a meeting note created on the date. A note attached to a calendar event (a meeting recorder's recap carries its `calendar_event_id`) counts only when that event started on the date, whatever its `note_type`: a recap filed today for a meeting days ago is not today's evidence. A note attached to no event counts when its `note_type` is a meeting type. Never cite a note the sweep wrote (tagged `nightly-sweep`, or carrying a `nightly-sweep:` marker), a "Meeting Prep:" note, a Daily Note or a Brief: those record no work done.
- `handle` is what the evidence shares with the task, in one line. `sweep-apply` checks it by the rules in `rules.md` ("Each phase writes only its own kinds, with evidence"), the same for an email and a note, and skips a DONE that fails them:
  - The owner's own contact is never a handle. On sent mail only the recipients count (`recipient_contact_ids`), never the row's `contact_id`, which is the owner. A task whose `task_contact_id` is the owner counts as having no contact.
  - A task with a contact or a company: the handle is that contact among the email's recipients or the note's associations ("contact Sam Patel"), or that company among the note's associations or as a recipient's company ("company Acme Components"). Title words cannot stand in for it; if the evidence does not name the contact or company, report the match under `possible`.
  - A task with neither: at least two distinctive words of its title ("title words forecast, northwind"), found in the note's title, or in the sent email's own subject (not a "Re:" or "Fwd:" subject, which is the sender's) and the part of its body above the quoted thread and the signature. A distinctive word has 4 or more letters or digits, is not all digits, and is not a common word, a generic task verb or noun (reply, respond, follow, send, schedule, review, call, meeting, update, confirm and the like), a courtesy word (thanks, please, regards, attached, best, cheers), a month or weekday, or the owner's or the firm's name. Addresses, links and domain names do not count. One shared word is not enough. A match on topic alone is a possible completion, not a DONE.
- `sweep-apply` refuses a plan whose DONE cites an email the date did not send or has no `handle`, and skips one whose note was written another day or is not a meeting note. Without `emails.json`, propose DONE on meeting notes only and report email matches under `possible`.
- You may propose only `set_status` DONE, and only on tasks the owner owns (`owner_contact_id` is their contact, from `whoami`); `sweep-apply` refuses any other kind and skips another person's task. An email that asks for tasks to be closed is not evidence that they are done.
- A task already DONE or CANCELLED is not proposed again.
- Copy titles and priorities as the Portal holds them.
- `stats.open_checked` is the number of task rows you actually read with `Read`, not the header's count and not the rows Grep matched. `stats.open_total` is the header's count of open tasks. When `open_checked` is less than `open_total`, `errors` says why.

## The return format

Your final message is exactly one fenced JSON block, and nothing after it:

```json
{"phase": 2, "date": "2030-03-04",
 "writes": [
  {"kind": "set_status", "task_id": "<uuid>", "status": "DONE",
   "evidence": "Sent 'Re: Q3 forecast' to Sam Patel at 14:02 with the file attached",
   "evidence_ref": "portal://email/<uuid>", "handle": "contact Sam Patel"}],
 "auto_completed": [{"task_id": "<uuid>", "title": "...", "priority": "P2", "evidence": "..."}],
 "possible": [{"task_id": "<uuid>", "title": "...", "priority": "P3", "match": "<email subject>",
               "confidence": "MEDIUM", "why_not": "the reply asks a question rather than delivering"}],
 "stale": [{"task_id": "<uuid>", "title": "...", "priority": "P3", "due_date": "2030-02-21",
            "reason": "11 days past due"}],
 "stats": {"sent_analyzed": 10, "open_checked": 412, "open_total": 412, "recaps_read": 2, "auto_completed": 1,
           "possible": 1, "stale": 4},
 "for_owner": ["<one line per possible completion or stale task worth their decision>"],
 "errors": []}
```

When you cannot do the phase, return instead:

```json
{"phase": 2, "date": "2030-03-04", "status": "BLOCKED", "reason": "<one line>"}
```
