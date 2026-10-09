# The nightly sweep's rules

What every phase worker applies. The orchestrator and each worker read this file before they start; each brief names the sections it needs. The names these rules refer to (the clients, the firm's domains, the default domain, the executive assistant) are in the owner's `NIGHTLY-SWEEP-RULES.md`, whose path the Run's inputs give; read it after this file. The addresses and names the scripts use are owner settings in `[nightly-sweep-workstream]` (see the skill).

## Which dates

The day is the owner's local day in the zone the setting `timezone` names, midnight to midnight. A date is swept only once it is over: the schedule runs shortly after midnight and sweeps yesterday, so mail that arrives late in the evening is in its own day's sweep. The Daily Note is titled for the swept date, not the run's. A night the machine was off is swept by the next run: at most 3 dates a run, oldest first, reaching back at most 7 days. An older unswept date is listed in the Daily Note and never swept on its own; sweep it with a date named in the request.

**With no ledger yet** (a first run, or a lost ledger), the newest "Daily Note - <date>" found in the Portal from the last 7 days is the starting point, and every closed date from the day before it to yesterday is swept, at most 3, the newest kept; an older gap is listed in the Daily Note. When no Daily Note is found, the newest closed date and the one before it are swept.

**An incomplete sweep is swept again.** A date whose email listing, phase 1 or phase 2 failed or did not run is recorded incomplete, and a later run sweeps it again, at most twice more; after that it is listed in the Daily Note and swept only when named. Every write is found by its marker first, so a re-sweep writes nothing twice.

**A date named in the request** is swept whatever the ledger says. It may be today, before the day is over (a daytime test): the mail so far is swept and the note written, but the date is not recorded as swept, so the night's run still sweeps the whole day.

**The email window is the local day.** `since` is local midnight and `until` the next local midnight, both as UTC instants; a message belongs to the day when since <= received_at < until. Never the UTC day (00:00Z to 00:00Z), which for an owner west of UTC starts the evening before.

**Catch-up runs the phases that still help.** Phases 1, 2 and 5 run for every date. Relationship health (phase 3) runs once a run, on the newest date. Calendar prep (phase 4) preps the day after the swept date, and runs only while that day is not over: on the scheduled run it is today, which has just started, and a morning catch-up still preps today's meetings; for an older catch-up date the meetings already happened, so it is skipped. `sweep-dates` sets both flags.

**When a VIP or High contact is stale.** Phase 3 counts a priority 1-2 contact as stale once its last touch is more than `vip_stale_days` days old: the owner's setting, 30 by default. `sweep-dates` reads it into `dates.json`, and the orchestrator passes it to the scout; a value that is not a whole number of days from 1 to 3650 falls back to 30, with a line in `dates.json`'s `notes`.

**Turn budgets per phase**: phase 1 100 turns (1 + 2 + 4 hops and 2 actions per email, plus 2 per item on a task list; 50 leaves no room for a fifteen-item list), phase 2 25, phase 3 35, phase 4 30, phase 5 20. A worker short of turns stops gathering context and returns what it has, with the shortfall under `errors`.

## What is written without asking

The owner authorises these writes for this job when they schedule it: tasks for what the day's email asks of them, a task to WAITING when someone confirms their request, a task to DONE when sent mail or a meeting recap shows it done with high confidence, significant FYI and intelligence notes, meeting prep notes for the day just starting, and the Daily Note. Never written: a cancelled task (stale tasks are reported, the owner decides), an email or draft, a pinned note, a deletion, a status change on a task someone else owns. A worker proposes; the Automation's finish step writes, through `sweep-apply` and `sweep-note-publish`, after the session.

**Each phase writes only its own kinds, with evidence.** Phase 1 may propose `create_task`, `set_status` WAITING and `create_note`; phase 2 only `set_status` DONE; phase 4 only `create_note`; `sweep-apply` refuses a plan holding anything else, whole. Every `set_status` carries `evidence_ref`: WAITING the `portal://email/<id>` of an email the date received, DONE the `portal://email/<id>` of an email the date sent or the `portal://note/<id>` of a meeting note written that date. A note attached to a calendar event (its `calendar_event_id` or a calendar_event association) is a meeting note only when an event it is attached to started on the date, whatever its `note_type`, so a recap filed on the date for an earlier meeting is not evidence; a note attached to no event is one when its `note_type` is a meeting type. A note the sweep wrote (tagged `nightly-sweep` or carrying a `nightly-sweep:` marker), a prep note, a Daily Note or a Brief is never evidence.

A DONE also names its `handle`, what the evidence shares with the task, and `sweep-apply` checks it by these rules, the same for an email and a note:

- The owner's own contact (whoami's) is never a handle. On sent mail the row's `contact_id` is the owner, the sender, so only `recipient_contact_ids` count, less the owner; a note's association with the owner counts for nothing; a task whose `task_contact_id` is the owner is treated as having no contact.
- A task with a contact or a company needs it: the contact among the sent email's recipients or the note's contact associations, or the company among the note's company associations or as the company of one of those contacts. Title words cannot stand in for it.
- Only a task with neither may be matched on words, and it needs at least two distinctive words of its title. A distinctive word has 4 or more letters or digits, is not all digits, and is not in the stopword list: common words, generic task verbs and nouns ("reply", "follow", "review", "meeting"), courtesy words ("thanks", "please", "regards", "attached", "best", "cheers", "hello", "hi"), month and weekday names, and every word of the owner's and the firm's names (the settings `owner_names` and `firm_names`). Before the test a possessive "'s" is cut and a hyphen or apostrophe inside a word joins it ("follow-up" is "followup").
- The words are taken from the note's title, or from the sent email's own words: its subject only when it is not a reply or forward (a "Re:" or "Fwd:" subject is the sender's), and its body cut at the first line that starts the quoted thread (a line starting with ">", a "From:" or "Sent:" header, "On ... wrote:", "-----Original Message-----", a forwarded-message rule) and at the signature (a "--" line, or a sign-off or one of the owner's names alone on its line after some text). Email addresses, links and domain names are removed before the words are read, so "dana@northwind.test" does not supply "northwind". The email's summary is not read.

Evidence that fails these is skipped, with the reason. Every `create_task` names one of the date's emails. A task moves only when the owner owns it (its `owner_contact_id` is the owner's contact). The workers read mail anyone can write; these checks are what keep an email from talking a worker into closing the owner's tasks.

**The Daily Note's visibility is the owner's choice.** By default it is written as an ordinary note: anyone in the organization who can read notes can read it, and it carries lines from every domain, Personal included. The setting `daily_note_private` makes it private. A Daily Note this job did not write, or one edited since this job wrote it, is never replaced: the new sweep is appended as a dated "## Re-sweep" section.

**Nothing waits on the owner.** The run never asks them anything. What needs them goes in the Daily Note under Priority Actions and in the run's `for_owner` lines, which the runner shows them.

## Routing a task to a domain

Routing is not a feel for what an email is "closest" to. Work these tests in order and stop at the first one that matches. The domain list comes from `list_entities(entity_type="domain")`; every task names one of them. The names the tests use (the clients and their other names, the firm's internal domains, the BD domain, the owner's own domains, the default domain) are in the owner's `NIGHTLY-SWEEP-RULES.md`.

**Test 1. Is an existing client named?** Route to that client's own domain, whatever the email is about. Billing, contracts, proposals, board matters, scheduling and disputes for a current client are all client work. The sender's contact card says which domain their work belongs to; trust it over the subject line. A client's other names and member companies, as the rules file lists them, count as the client.

**Test 2. Is it the firm's own internal work?** It splits three ways, into the firm's administrative domain (entity filings, legal, insurance, banking, payroll, HR and contractors, subscriptions, vendor billing, licensing, corporate cards), technical domain (the Insights Portal, MCP, agents and automation, repositories, infrastructure, tooling access) and marketing domain (website, content, LinkedIn, collateral, seminars, newsletters).

**Test 3. Is this net-new revenue?** Only then use the firm's BD and sales domain: prospecting, pipeline, proposals and SOWs to people who are not yet clients, networking groups, referral partners, pricing for new work.

> **BD and sales is not the catch-all.** Work for an existing client never belongs there, even when it involves a proposal, a contract or money. If you are about to file something in BD and sales and the counterparty is already a client, you took a wrong turn at Test 1.

**Test 4. Is it the owner's own?** Learning and professional development go to the owner's development domain; household and family matters go to Personal; the owner's other ventures named in the rules file have their own domains.

**Test 5. Nothing matched.** Route to the default domain the rules file names and list the task under `defaulted_routing`. Do not guess at a closer fit, and never fall back to BD and sales. A short defaulted list each morning is useful signal; a silently misfiled task is not.

## Noise: skip these

- **Newsletters**: a subject with "unsubscribe", "newsletter", "digest", "weekly roundup"
- **Automated**: from "noreply@", "notifications@", "alerts@", "no-reply@", "mailer-daemon@", system services
- **Marketing**: "% off", "sale", "limited time", "promotion", "deal", "offer expires"
- **Spam signals**: ALL CAPS subjects, excessive punctuation (!!!), emoji-heavy subjects
- **Auto-replies**: "Out of office", "automatic reply", "auto-response"
- **CC'd threads**: the owner is CC'd but not TO'd, and the thread does not need their input
- **Pleasantries only**: no actionable content ("Thanks!", "Got it!", "Sounds good!")
- **The Portal's own Brief**: the automated "Brief" from the Portal's address (the setting `portal_brief_email`; `portal_brief` in `emails.json`). It is generated from Portal data, so its items already exist.

List what was skipped with a one-line reason each; batch similar skips ("12 newsletters" is one line).

**Archived mail is read like any other.** The day's mail is every message in the window, archived or not, and `sweep-emails` never filters on `is_archived`. Many people archive mail as they read it, so an archived email is one the owner has seen, not one with nothing to do.

**Sent mail is the resolution signal.** Propose no task for an ask that a message the owner sent the same day already resolved: read the date's `sent` rows before proposing.

## The executive assistant's mail

**Never skip mail from the owner's executive assistant** (the setting `assistant_email`; the rules file names the assistant). The assistant's daily brief, end-of-week reminders and plans are written by the assistant, not generated by the Portal, and they are lists of things the owner has to do. They are not an "internal digest", they are not the Portal's Brief, and their items are not "already tracked" unless a task for that exact item exists. `emails.json` flags the assistant's mail `from_assistant` and lists it first. An owner with no assistant leaves the setting empty and this section does not apply.

**Each of the assistant's lists is a task list, one task per item.** A task list is an email that sets out several separate things the owner has to do, decide, answer, sign, review or schedule: the assistant's briefs, reminders and plans above all, and any other email that numbers or bullets its asks. Read its full body, then treat every item as its own TASK or FOLLOW-UP. One email with twelve items is twelve tasks, never one "review the assistant's email" task and never one task whose title strings several items together. Skip only an item that is pure information, one the assistant says they are doing themselves, or a calendar fact. The assistant's briefs repeat open items from day to day; the per-item duplicate check is what stops a repeat becoming a second task.

**The assistant's lists come first.** Task lists from the assistant are processed before any other email, with the full body read and every item checked and proposed. Then, if more than 8 other non-noise emails remain, the VIP and High senders (priority 1-2) get the full context hops first and the rest get the sender lookup only.

**A task the assistant owns counts as existing.** A matching task the assistant created (owned by the assistant) is not duplicated; it is listed under `already_tracked_by_assistant`.

## The duplicate check

Before proposing any task, search for it: `list_entities(entity_type="task", filters={"search": "<key phrase>", "status": ["TODO", "IN_PROGRESS", "WAITING", "DONE", "CANCELLED"]}, limit=5)`. Pass the status list every time: without it the search returns open tasks only, and an item already done or cancelled looks new. For a task-list item, search on the item's own distinctive words, not the email's subject. A similar task in any status means no new task; list it under `already_tracked`. `sweep-apply` also finds a task this job already made for the same email and item by its marker, so a re-run of a date never makes a second one.

## Priority

- **P1**: VIP sender (priority 1-2) AND explicit urgency ("ASAP", "urgent", "today", "immediately")
- **P2**: VIP sender OR implied urgency ("this week", "soon", "by Friday")
- **P3**: known sender (priority 3), standard request
- **P4**: low-priority sender or informational request

If everything is P1, nothing is P1: rank a new item against the owner's existing list, not on its own.

## Due dates

**Resolve relative deadlines into absolute dates.** A source that says "due in 3 days", "by end of week" or "within 48 hours" has named a date: compute it from the email's received date (local) and propose that ISO date. Leaving `due_date` null because no calendar date appeared as literal text hides real deadlines. The same applies to a deadline anchored to a named day or a recurring meeting ("before Monday's leadership meeting", "at Friday's review", "this weekend"): resolve the next occurrence of that day on or after the email's received date.

**A due date comes from evidence, never from priority.** Use a date stated or clearly implied in the source (a named deadline, a meeting date, a promised turnaround). When the source names none, `due_date` is null and the priority stands alone. Never derive a due date from sender priority: an invented date is indistinguishable from a real one downstream and corrupts every overdue view that reads it.

## Delegation

When the work is fully someone else's, the task's owner is that person. When it is delegated but the owner still cares about the outcome, the owner stays the task's owner, the status is WAITING, and `task_contact_id` names the person doing it.

## Task reconciliation (phase 2)

Only HIGH confidence completes a task. Never cancel; stale tasks are reported only.

The open tasks come from `tasks.json`, pulled in code by `sweep-tasks` before the session, one compact row per task. The reconciler reads and greps that file; it never pages the open-task listing itself, because a list of hundreds of open tasks does not fit in a worker's turns as listing pages.

| Sent email pattern | Task pattern | Confidence |
|---|---|---|
| "Accepted: [Meeting]" sent | "Schedule meeting with X" | HIGH |
| Email to X about Y | "Follow up with X about Y" | HIGH |
| "Re: [Topic]" to X | "Respond to X about [Topic]" or "Reply to X re: [Topic]" | HIGH |
| Invitation sent to X | "Schedule [event] with X" | HIGH |
| "Attached: [Doc]" to X | "Send [Doc] to X" | MEDIUM |
| Reply in thread with X | "Reply to X" (generic) | MEDIUM |
| Email mentioning topic | Task mentioning same topic | LOW |

A MEDIUM match is read in full and upgraded to HIGH only when the email clearly resolves the task; otherwise it is reported as a possible completion. A meeting recap from the date that records the task's subject as discussed, decided or delivered is completion evidence at the same bar as a sent email; a recap whose sections hold only a note-taking tool's placeholder prompts is discarded. A HIGH match `sweep-apply` will skip (a task with a contact the evidence does not name, or a task with neither and fewer than two shared title words) is reported as a possible completion instead.

## Relationship health (phase 3)

Five contacts a night: 2 from the VIP/High pool (priority 1-2, stale after `vip_stale_days` days, most stale first) and 3 at random from priority 3-4 contacts stale 6 months or more; a short pool is filled from the other. One specific, low-effort recommendation each. Unanswered outreach: VIP flagged after 7 days without a reply, High after 14. Report only.

## Calendar prep (phase 4)

At most 5 meetings, chosen from a ranked list, never in calendar order: (1) events the owner organizes or is named as presenter, host or trainer of, (2) events with external attendees from a client or prospect domain, (3) first occurrences of a series or first-time meetings, (4) all other external meetings, (5) internal recurring reviews and syncs last. Never drop a higher rank to fit a lower one. Every meeting the cap drops is listed with its rank and the owner's role, never as a bare count. Personal events, internal recurring events, events with no external attendees and a generic title, and cancelled events get no prep.
