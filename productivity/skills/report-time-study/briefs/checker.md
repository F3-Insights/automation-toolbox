# Brief: check a sample of slot attributions against the raw evidence

## The question

Does the raw evidence support the domain and the tier each sampled slot was given? You check independently: you are given the finished slot files and the raw evidence, never the assembler's narrative or reasoning, and you re-derive each sampled slot yourself before you compare.

You check and report. You change no file.

## The inputs

The paths given after this brief, and only those:

- `days/<date>/slots.csv` for every day of the window.
- The window's raw evidence: `signals/<date>/` for every day, `meetings/*.md`, `owner_stated.md` and `calls_confirmed.csv`.
- The owner's `mapping.md` and `domains.csv`.

Do not read `days/<date>/day.md`; it carries the assembler's reasoning.

## The sample

Per day, at least 12 slots and at most 30:

- every slot where a call starts or ends;
- every owner-stated slot, up to 6;
- every split slot, up to 4;
- at least two slots of each tier present that day, chosen across the day;
- every verified slot whose evidence names no file or time.

## The rules

You judge against the same written standard the day assembler follows, set out below. Your independence comes from never seeing the assembler's reasoning or `day.md`, not from a different standard. Where this brief and the assembler's rules could read differently, the rules here are the ones you apply.

For each sampled slot, first from the raw evidence alone: what was the owner doing, for which domain, and on which tier. Then compare with the slot file.

**Tiers.** One per slot:

| Tier | When |
|---|---|
| verified | A system recorded the owner doing it in that slot: speaking in a transcript, a prompt typed, a message or email sent, a call joined |
| corroborated | Two indirect signals agree (the PC asleep and a block on the owner's own calendar; a shared-in calendar only where `mapping.md` allows it) |
| owner-stated | The owner said so, in `owner_stated.md`, an answer or a standing rule in `mapping.md` |
| inferred | One indirect signal (a page open, a save in a synced folder, sleep overnight with the PC off) |
| unaccounted | Nothing |

**Presence and domain are two tiers.** Settle them separately, and the slot takes the weaker of the two. Presence says the owner was there doing it; domain says for whom. A domain is verified only by content: the transcript block that says what was discussed, the words of a message or email, the repository of the owner's own commit, a recipient the map places. A domain that rests only on the Teams tenant, the organizer or a calendar event overlapping the slot is inferred, or corroborated when a second independent signal agrees. It is never verified, even when presence is verified.

**Calls.** A call slot is verified only for the minutes the owner was present in it, from the transcript's attendance section, the Teams join evidence and the webcam event that follows within 5 seconds of the owner leaving. Where presence covers under half of the slot, the slot is not verified, and its shares must give the remaining minutes to what the other evidence supports or to `unaccounted`. Shares normalised over only the evidenced minutes, crediting the whole slot to them, are a flag.

**What the signals do not prove.**
- Chrome visit time is tab time, not attention. A share resting on browser tabs alone is inferred, however long the tab was open.
- A merge or commit under the owner's identity that the signal file marks `owner=no`, together with a page visit, is corroborated at best, never verified.
- Outlook activity logs (`olk` files) are on a UTC clock. Convert to local time with the owner's timezone before comparing or citing, and cite the local time.
- A save in a synced folder without `lastModifiedBy` naming the owner is inferred at most.
- A calendar entry is booked time, not attendance.
- Fellow labels short lines to people who have already left; presence comes from substantive speech and explicit goodbyes.

**Standing splits and content.** A standing split for a person in `mapping.md` (for example, their calls split 70/30 between two projects) applies only to calls and chats with that person that have no recording and no clear content. A recorded session keeps the segmenter's topic blocks, whoever it was with. Content decides over the account: a chat about a home matter on a work account or a work tenant is personal, whatever the tenant.

**Flags.** Flag each disagreement:

- **tier_too_strong**: the tier claims more than the evidence holds (a page open called verified, a synced save counted as the owner's with no `lastModifiedBy`, a calendar entry taken as attendance, a domain resting on the tenant, organizer or calendar alone called verified, a call slot verified beyond the owner's present minutes, an `owner=no` merge called verified).
- **domain_contradicted**: the evidence points to another domain under `mapping.md`, including a standing split applied to a recorded or content-bearing call, or an account's domain taken over the content.
- **share_misallocated**: the shares were normalised over the evidenced minutes, a typed owner action in another domain has no share and no mention in `concurrent`, or `primary_domain` is not the largest share.
- **stated_over_verified**: an owner-stated time replaced a verified one.
- **absent_from_call**: a slot attributed to a recorded call the owner had left or never joined.
- **concurrent_missed**: activity in the slot the file does not record.
- **evidence_missing**: the evidence column cites a row or time that is not in the files, or an `olk` time cited in UTC rather than local time.
- **recurring_from_calendar**: an optional recurring event taken from the calendar alone.

**Your own work and tool refusals.** You write no file and run no script, so you have no scratch; never read or run anything in another worker's `work/` folder. If a tool call is blocked by a hook or a permission rule, stop and return `"verdict": "BLOCKED"` with the exact denial in `notes`. Never reroute the same action through another tool or a script.

## The return format

Answer with exactly one JSON block and nothing else:

```json
{
  "verdict": "PASS",
  "days": [
    {"date": "2030-03-04", "sampled": 18, "flags": [
      {"slot": "13:20", "flag": "tier_too_strong", "file_says": "verified, Client A",
       "evidence_says": "inferred: one page open at 13:24 in browser visits, no other signal",
       "cite": "signals/2030-03-04/browser_visits.tsv 13:24"}
    ]}
  ],
  "notes": "",
  "model": "sonnet"
}
```

`verdict` is `FAIL` when any flag changes a domain, a tier or a share, `BLOCKED` when a tool call was refused, else `PASS`. A day with no flags has an empty `flags` list. Every flag carries a `cite` the orchestrator can open.
