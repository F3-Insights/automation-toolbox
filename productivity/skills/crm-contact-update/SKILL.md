---
name: crm-contact-update
description: "Updates one Insights Portal contact from a one-line instruction (priority, title, relationship type, phone, or free-text context), shows the change before writing it, and always logs an activity so the change is traceable. Use for \"update Dana: promoted to VP Sales\" or \"make Sam a VIP\". Not for logging a call (comms-log-call) or a meeting (meeting-log), or for a CRM-wide cleanup (crm-data-hygiene-orchestrator)."
argument-hint: '[name] - [what changed]'
allowed-tools: mcp__insights-portal__search, mcp__insights-portal__get, mcp__insights-portal__update_contact, mcp__insights-portal__add_contact_fact, mcp__insights-portal__create_activity, mcp__insights-portal__create_note, mcp__insights-portal__sync_health, Read
---

# Contact update

A quick update to one contact after an interaction: their priority, role, relationship type or phone, or new context worth keeping. Every update logs an activity, so the change can be traced later.

**User provided:** $ARGUMENTS

Before any write, load the `portal-write-safety` skill and follow it. Notes follow the `portal-note-types` skill.

## Step 1: Parse the input

Split the input on the first ` - `, `--` or a dash used as a separator:

- **Left side**: the contact's name or email address.
- **Right side**: the update, free text describing what changed.

With no separator, ask: "Which contact, and what changed?"

## Step 2: Resolve the contact

`search(query="<left side>")` and pick the match. With two or more plausible matches, ask which one; never update on ambiguity. Then read the current record so you can show a diff:

```
get(entity_type="contact", id_or_query="<resolved id>")
```

## Step 3: Classify the update

Map the signals in the update text to `update_contact` fields:

| Signal in the update | Field |
|---|---|
| "promoted to X", "new title X", "now X at <company>" | `title` |
| "now VIP", "bump to priority 1", "top tier" | `priority=1` |
| "high priority", "important contact" | `priority=2` |
| "deprioritize", "low priority" | `priority=4` |
| "client", "vendor", "partner", "internal" | `relationship_type` |
| "phone X", "mobile X" | `phone` |
| "now at <company>", "moved to <company>", "joined <company>" | Resolve the company with `search` or `get(entity_type="company", ...)`. `update_contact` has no documented field for the contact's company, so record the move as a note and tell the user plainly that the company link was not changed. |
| "email is X", "new email X" | `email` is not a documented `update_contact` field either: capture it as a note and flag it for a manual fix rather than assuming the write succeeded. |
| a durable fact about the person (a credential, a preference, a past role) | `add_contact_fact` with its source |
| anything else (narrative) | a note, not a field |

**Never guess.** When a signal is ambiguous ("senior at Acme": a title modifier or a new role?), ask one clarifying question.

## Step 4: Show the diff, then apply

Always show what will change before writing, even when the user said "just update it":

```
Updating **Dana Whitfield**:
- Title: VP Sales -> SVP Sales
- Priority: 2 (High) -> 1 (VIP)
- New note: "Promoted at the end of Q1; now the main buyer for enterprise deals."

Proceed? (yes / edit)
```

On confirmation:

1. `update_contact(id=..., fields={<changed fields>})`, and `add_contact_fact` for any durable fact.
2. When there is narrative: `create_note(content="<narrative>", title="Contact update: <date>", note_type="episodic", associations=[{entity_type: "contact", entity_id: ...}])`.
3. Always: `create_activity(activity_type="note", title="Contact updated: <summary>", description="<the full update text>", contact_id=..., activity_date=<now>)`.

## Step 5: Confirm in one line

```
Updated **<Name>**: <changed fields>. Activity logged. [Note created.]
```

No further questions.

## Rules

- **Narrative is not a field change.** A purely narrative update ("good call, very engaged") skips `update_contact`: an episodic note and the activity only.
- **Company moves.** Resolve the new company first; when there is no match, ask before creating a company record. Never claim the contact was repointed to a new company.
- **Priority changes are audit-worthy.** Always write a short note saying why, even a brief one.
- **The Portal is a shared surface.** Everyone with Portal access can read a note; write only what all of them may read.

## Examples

**Input:** `Dana Whitfield - promoted to SVP Sales, now primary contact for Acme Components`

1. Resolve: Dana Whitfield, VP Sales at Acme Components, priority 2.
2. Classify: a title change, and a priority bump implied by "primary contact".
3. Show the diff; the user confirms.
4. `update_contact`, an episodic note, `create_activity`.
5. `Updated **Dana Whitfield**: title -> SVP Sales, priority -> 1 (VIP). Activity logged. Note created.`

**Input:** `Marcus Lee - good call, very interested in the Q3 proposal`

1. Resolve: Marcus Lee.
2. Classify: narrative only, no field change.
3. An episodic note and the activity; no `update_contact`.
4. `Updated **Marcus Lee**: note logged. Activity logged.`
