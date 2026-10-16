---
name: calendar-time
description: "Where the owner's meeting time went over a period, and how much of it belongs to one scope (a client's email domain or a title pattern), computed from the Portal calendar: availability blocks, clones and cancellations dropped, hours summed against wall-clock hours, hours by day and by category. Use for \"how much time did I spend in meetings with X\" or as the calendar_time input of a goal or project audit. Meeting time only, never desk work. Not for stewarding the calendar; use calendar-steward-method."
---

# Calendar time

One read-only command:

```bash
productivity-calendar-time [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--scope-domain DOMAIN] [--scope-title REGEX] [--exclude-title REGEX] [--categories FILE] [--json]
```

The window is half open, midnight in the owner's timezone; the default is the last seven full days. Run it once with no scope for the window total, then once per scope. It prints a table, or JSON with `hours_sum` and `hours_union` (the gap between them is double booking), counts of what was dropped, and the in-scope meetings with what matched them; out-of-scope time is a single total.

When quoting it, say both limits: it is meeting time only, so a small number is not a light week, and the scope match is a heuristic on attendee domain or title, because a calendar event carries no client.

Settings: `portal_mcp_config`, and `[calendar-steward-method] timezone` for the owner's zone (shared with the calendar steward). `--help` lists every option.
