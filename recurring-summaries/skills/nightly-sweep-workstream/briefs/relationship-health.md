# Brief: phase 3, relationship health ("relationship roulette")

## The question

Which five relationships should the owner tend today, and with what small step each? VIPs get attention through regular work; the forgotten contacts, priority 3-4 people stale for six months or more, are where this adds most. Each night surfaces a different random mix. You report only: no tasks, notes or drafts, and no questions to anyone.

## The inputs

- The date.
- `vip_stale_days`: the days after which a VIP or High contact (priority 1-2) is stale, the owner's setting from `dates.json`. When the dispatch gives none, it is 30.
- The path of `rules.md` in this skill's folder. Read "Relationship health (phase 3)" first.
- Your turn budget: 35 turns.

## What to do

1. Call `priority_review()` (domain-grouped overdue tasks, stalled projects, deadlines, VIP unread mail) and page contacts with `list_entities(entity_type="contact", limit=200)`, following `next_offset`. Each row carries `last_touch_at` and `last_touch_kind`; derive staleness from them. `data_health` and `sync_health` are not on the live surface; do not call them.
2. Split the stale contacts into two pools: VIP/High (priority 1-2, last touch more than `vip_stale_days` days before the date) and everyone else (priority 3-4, stale 6 months or more). Put the threshold you used in `stats.vip_stale_days`.
3. Pick 2 from VIP/High, most stale first, and 3 at random from everyone else. Fill a short pool from the other. When nothing reads as stale (automated mail can count as a touch), pick 5 contacts that appear nowhere in recent activity, priority 1-2 first, and say so in `errors`.
4. For each pick, `get(entity_type="contact", id_or_query="<id>", detail="summary")`, then write one specific, low-effort recommendation from what you learned: a check-in, an article about their industry, a coffee, congratulations on an event, a question about a project they mentioned. Never a generic one.
5. Unanswered outreach: list the owner's sent mail of the last 14 days (`list_entities(entity_type="email", filters={"direction": "sent", "since": "<14 days before the date, local midnight, as UTC>"})`) and flag a VIP with no reply after 7 days and a High contact with none after 14.
6. Return the block below.

## The return format

Your final message is exactly one fenced JSON block, and nothing after it:

```json
{"phase": 3, "date": "2030-03-04",
 "picks": [{"contact_id": "<uuid>", "name": "...", "company": "...", "priority": 2, "pool": "vip",
            "last_touch_days": 41, "last_touch_kind": "email",
            "context": "<one or two sentences>", "recommendation": "<one specific step>"}],
 "unanswered": [{"contact_id": "<uuid>", "name": "...", "subject": "...", "email_id": "<uuid>", "days": 9}],
 "stats": {"vip_stale_days": 30, "stale_found": 37, "vip_stale": 4, "other_stale": 33, "unanswered": 1},
 "for_owner": ["<one line per critical relationship alert>"],
 "errors": []}
```

`pool` is `vip` or `serendipity`. When you cannot do the phase, return instead:

```json
{"phase": 3, "date": "2030-03-04", "status": "BLOCKED", "reason": "<one line>"}
```
