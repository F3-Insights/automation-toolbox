---
name: start-session
description: Starts the owner's working day, or reorients a session, with current priorities, the next meeting and one useful next action. Reads today's daily plan (the daily-plan orchestrator's private Insights Portal note) and works from it; with no plan yet, plans the morning by hand with daily-plan-pull and the daily-plan-method rubric. Writes nothing. Use when the owner says "start my day", "where were we" or "what's next". Not for producing the plan itself (daily-plan-orchestrator) or the evening close.
allowed-tools: mcp__insights-portal__whoami, mcp__insights-portal__search, mcp__insights-portal__get, mcp__insights-portal__briefing, Read, Bash(python3 ~/.claude/skills/daily-plan-method/scripts/daily_plan_pull.py:*)
---

# Start session

The interactive way into the day. The daily plan (`daily-plan-orchestrator`, a morning and an evening pass on weekdays) already chose the top three, fitted them to the calendar and named the conflicts; this skill puts that in front of the owner and turns it into the next action. It writes nothing.

## Read the plan

1. `whoami` for the owner's timezone and today's local date.
2. Find today's note, `Daily Plan - <yyyy-mm-dd>` (`search`, then `get` with detail full). Its morning block is the plan; an evening block, when there is one, is the day's close.
3. With no note, or a stale one (the owner asks after the evening close, or the morning plan is from before a big change), run `python3 ~/.claude/skills/daily-plan-method/scripts/daily_plan_pull.py --pass morning --out <a scratch file>` and plan by the `daily-plan-method` rubric yourself (load that skill if it is not loaded). Say that the plan is ad hoc and unpublished.

## Present a useful start

Lead with the most useful next action and why it matters now. Then:
- the next meeting or fixed deadline, with its local time and any prep it needs;
- the top three with their slots, each with its reference;
- the calendar proposals and questions still open from the plan, numbered, so each can be answered by its number.

Coverage gaps (a stale pull, a calendar that did not sync) are unknowns, never "nothing pending". End on the next action, without a menu of commands. If the owner gave a task with the request, do it within existing authority instead of offering to.
