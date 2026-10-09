---
name: pressure-test-method
description: Pressure-tests one of the owner's systems, workflows or automations per run, picked from a rotation ledger so each target gets its turn and one audit gets full attention. Steelmans it from its own files and data, judges it against the specific goal it serves, compares at least three external practices, and ranks every finding KEEP, IMPROVE, REPLACE (at most one) or INVESTIGATE in one audit note the owner can argue with, then records the findings in the ledger. Use for "red-team the weekly reporting workflow" or "audit the next thing on the rotation". Not for reviewing a finished deliverable as its reader (executive-red-team) or code (software-review).
argument-hint: '[a ledger entry, something off the ledger, or next]'
---

# Pressure test

You pressure-test one thing, well, and hand the owner a judgment they can argue with. Targets come from a rotation ledger that records what was audited and when, so coverage evens out over time and each run is spent on a single target.

**Target for this run: `$ARGUMENTS`**

## Inputs

- **The rotation ledger** (setting `rotation_ledger` under `[pressure-test-method]`): a YAML list of audit targets, each with `name`, `last_audited` and `findings`.
- **The owner's goals document** (setting `goals_doc`): the strategic goals each target serves.
- **The owner's playbooks** (setting `playbooks_dir`, the same folder `decision-playbooks` keeps): their ratified decision rules, with an `_inbox/` folder for proposals.
- **The owner profile** (setting `owner_profile`): their scale and context, so external practice is judged for fit.

A missing setting is named in the note's Method section and the audit goes on without it; it never stops the run.

## Choosing the target

If the target is `next` or empty, take the stalest ledger entry: never audited first (`last_audited: null`), then the oldest date, ties broken by list order. If it names a ledger entry, audit that. If it names something outside the ledger, audit it anyway and say in the note that it was off the ledger.

**One audit per run.** Never two: attention split across targets produces shallow audits of each. This is judgment work; run it on a strong model.

## Standing constraints

- **Private material stays private.** The goals document, the principles and the profile are read for judgment and never republished. The note lands in the Portal, a shared surface: cite them by document and section, never by quoting private facts.
- **You never fix anything.** You audit, recommend, write one note and update the ledger. No code edits, no record changes beyond your own note, no message to anyone. Repairs go to whoever owns the thing.
- **Read only on everything but your note and the ledger.** Never touch deployed code or a secrets file, and never push to a main branch.
- **Degrade, never block.** What you could not inspect becomes an INVESTIGATE finding; the run still ends in a note.
- **Before the `create_note` call**, load the `portal-write-safety` skill and follow it.
- **Never edit the owner's playbooks.** A challenge to a principle is a proposal file in the playbooks' `_inbox/` (see "Challenging a principle"). Only the owner ratifies.
- **Ground every claim** about the current state in the artifact it came from: a file path, a log line, a Portal record, a date. Something you could not inspect is an INVESTIGATE finding, not a guess. That a newer approach exists is not, on its own, a finding.
- **The owner's own designs get the same scrutiny.** If the owner chose the thing you are auditing, state the case against it as plainly as you would for anything else.

## Method, in order. Do not skip a stage.

### (a) Steelman

Before criticising anything, state why the current approach exists and what it gets right, from its actual files and data. Read the thing, its logs and what it produced. Cite artifacts by path and date.

An audit that cannot state the strongest case for the status quo has not understood it yet, and its criticism will be noise. If the decision behind it is recorded (a decision record, a principle, a dated note, the owner's journal), quote the reasoning as given. Check the record of past events before calling anything a fresh discovery: a fault already found and fixed is not a finding.

### (b) Effectiveness

Judge the target against the specific goal it serves in the goals document. Name the domain and the goal, not "the business". Then answer:

- Is this advancing that goal, or is it busy?
- What is the measurable signal, and does one exist at all? If nothing shows whether it works, that absence is itself a finding.
- Has the signal read zero or not moved for weeks? Report that as a finding rather than reading it as a quiet period.
- What would a ten-times-better version look like, and what stands between here and there?

Check it against the owner's ratified playbooks (setting `playbooks_dir`), by name, including any that govern this target specifically.

### (c) External practice

Search how strong practitioners solve this today. **At least three sources**, each named with what it is and when it is from. Internal opinion is not research.

For each source, say what transfers and what does not, against the owner's scale from their profile. Practices that assume a platform team, a compliance function or a large tooling budget usually do not transfer to a small operation, and saying so is as useful as the practice itself. A source you rejected, with the reason, belongs in the note.

### (d) Verdict

Put every finding in exactly one bucket:

- **KEEP.** Validated. Say specifically why it survived, so the next audit does not relitigate it.
- **IMPROVE.** A specific change to something that exists, with its migration cost (time, risk, what breaks during the change).
- **REPLACE.** **At most one per audit.** It must say why improving what exists cannot get there, and what the migration actually costs; an attractive end state is not a reason by itself. With two candidates, demote the weaker to IMPROVE or INVESTIGATE and say so.
- **INVESTIGATE.** An unknown that blocks judgment, with the specific question and the cheapest way to answer it.

Rank inside each bucket by impact on the goal, highest first.

### (e) Output

**One Portal note**, `create_note` with `note_type="research"`, titled `[Red Team] Audit: <target> YYYY-MM-DD` so every audit is found by one search. Build no notification of your own.

About 1000 words. Write out the reasoning so the owner can follow and dispute it. The verdict block on top must not understate the body: if the body holds a REPLACE or a failure, the block shows it.

```
**Verdict:** <one line: the headline judgment>

<one line per finding, tagged, highest impact first>
- KEEP: ...
- IMPROVE: ...
- REPLACE: ...
- INVESTIGATE: ...

## Steelman
Why this exists and what it gets right, with artifact citations.

## Effectiveness against the goals
The domain and goal. The signal, or its absence. The principles applied, by name.

## Alternatives considered
Each option weighed and why it was kept or rejected, including the ones rejected fast.

## External practice
Three or more sources, named and dated: what transfers, what does not, and why.

## Findings in full
Each finding: the evidence, the recommendation, the migration cost, and the cost of doing nothing.

## Weigh in
Two to four questions, each one a place where the owner's judgment changes the verdict.

## Method
The goals cited, the principles applied, the artifacts read, what could not be inspected, any setting that was missing.
```

**Weigh in** is not decorative. Each question is answerable in one line and changes something: not "does this seem right?" but "should the weekly export keep running while its upload step fails, or pause until that is fixed?" Ask where the owner's knowledge of their network, clients, industry or intentions beats yours.

**Write findings that stand on their own.** Each finding is actionable as written, without waiting for answers to the questions above. If a finding genuinely cannot proceed without a decision only the owner can make, say so in the finding as an escalation with a recommendation.

End the body with `**Tags**: red-team, audit` (the searchable substitute where tags cannot be set), and associate the note with the Portal domain that owns the target when one clearly applies.

### (f) The ledger

Edit the rotation ledger, which tracks findings to closure and not just coverage:

1. Set `last_audited: YYYY-MM-DD` on the target.
2. Append every finding to its `findings` list, one flow mapping per line:

```yaml
    findings:
      - {date: 2030-03-14, verdict: IMPROVE, summary: "The export reports success when its upload step fails", status: open, owner_verdict: null}
```

On the first audit replace `findings: []` with the block; later, append beneath the last line. One line per mapping, so appends never reformat the file. Every finding is `status: open` and `owner_verdict: null`; advancing them (dispatched, closed, overruled, the owner's verdict) is the job of whoever drives findings to closure, not yours.

Change nothing else in the ledger. A target missing from the rotation is a proposal under Findings; you do not add rows.

## Challenging a principle

If the finding is that one of the owner's ratified principles is wrong, write a proposal file in the playbooks' `_inbox/` named `YYYY-MM-DD-red-team-<slug>.md`: the principle as ratified, the evidence against it, the proposed wording, and what changes downstream if the owner ratifies it. Name the file in the audit note. Never apply it, and never treat your own proposal as settled in a later audit.

## Failure modes

- Generic best practice with no artifact citations. That is a blog post, not an audit.
- Recommending a rebuild because the new thing is interesting. The REPLACE rule above exists to stop this.
- Auditing three things badly instead of one well.
- Hedging every finding into unfalsifiability. Rank it or leave it out.
- Treating the current way of pursuing a goal as the goal itself. A method can be wrong while the goal it serves is sound.
- Leaving out the reasoning. Give the owner the argument, not only its conclusion.
