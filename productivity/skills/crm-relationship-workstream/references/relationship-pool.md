# Building the week's candidate pool

How the relationship-tending orchestrator finds who is going cold and picks the week's candidates, before the filters in `SKILL.md` ("Who may be picked") narrow them. It reads only and writes nothing.

## Health thresholds

The rules file may override these.

| Priority | Attention | Critical |
|---|---|---|
| VIP (priority 1) | 30 to 44 days since the last touch | 45 days or more |
| High (priority 2) | 45 to 59 days | 60 days or more |
| Normal (3 and 4) | not tracked, except a contact the rules list to nurture, which takes VIP thresholds | |

A touch is a call, a meeting or mail sent by the owner. Automated mail can count as a touch in the Portal's `last_touch_at`; when nothing reads as stale, suspect that before believing it.

Relationship type changes what a good touch is. Clients get shorter thresholds and business-focused touches; referral sources get appreciation; strategic partners are often fine quarterly.

## Steps

1. Call `priority_review()` (overdue items, stalled projects, VIP mail unread, grouped by domain), then page contacts with `list_entities(entity_type="contact", limit=200)`, following `next_offset` until `has_more` is false. Each row carries `last_touch_at` and `last_touch_kind`; derive staleness from them. There is no server-side priority filter: filter locally.
2. Split the stale contacts into two pools: VIP and High past their critical threshold, and everyone else (priority 3 and 4) stale six months or more.
3. Pick from the first pool, most valuable times most stale first; then at random from the second, so each week surfaces different people. Order by relationship value times staleness, never alphabetically. When nothing reads as stale, pick contacts that appear nowhere in recent activity, priority 1 and 2 first, and say so in `notes`.
   A contact with a meeting already on the calendar is not cold: leave them out, since the touch is coming. A pipeline prospect whose record carries no notes at all is a line for the owner, whatever its staleness.
4. For each pick, `get(entity_type="contact", id_or_query="<id>", detail="summary")` for the context the researcher will need.
5. **Unanswered inbound.** List the inbound mail from contacts in the last 21 days (the `direction` filter set to inbound) and flag each thread the owner has not answered: 7 days for a VIP, 14 for others. This is lens 1 in `SKILL.md`.
6. **Unanswered outreach.** List the owner's sent mail of the last 14 days (`list_entities(entity_type="email", filters={"direction": "sent", "since": "<14 days ago>"})`) and note a VIP with no reply after 7 days and a High contact with none after 14. A dangling "I'll send you..." with no later sent message is a line for the owner too.

## What it yields

One row per pick (`contact`, `name`, `company`, `priority`, `lens` (`cold-vip` or `serendipity`), `last_touch_days`, `last_touch_kind`, a line of context) and one row per unanswered thread, inbound or outreach (`contact`, `email`, `days`), plus the counts (stale found per pool, unanswered). These feed `outreach.json`.
