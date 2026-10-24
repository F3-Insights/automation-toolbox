---
name: portal-write-safety
description: "Reference only, loaded by other skills before any Insights Portal create, update or draft call, not for a user request: the rules every Portal write follows (propose by default, sync_health first, resolve entities by UUID, close stale tasks as CANCELLED with evidence)."
user-invocable: false
---

# Portal write safety

Applies to every skill that writes to the Insights Portal.

- Default to propose. Show the write and make it only once someone confirms, or when the skill's rules say the owner authorised that kind of write for an unattended run. A write that skips the gate is a failure.
- Call `sync_health` first and degrade honestly when sync is stale: say what may be missing instead of writing as if the data were current.
- Resolve Portal entities by UUID, never by name. Address items awaiting approval by their ref, so a restated item cannot be approved by accident.
- Strip the U+2028 line separator from any text sent to the Portal; it breaks the stream's framing.
- Closing a task on staleness is `CANCELLED` carrying the evidence quote, never `DONE`. No quote, no verdict: an unsupported "looks done" is discarded.
