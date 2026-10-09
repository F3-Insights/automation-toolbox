---
name: issue-harvest-workstream
description: Reference loaded by issue-harvest-analyst, issue-harvest-checker and issue-harvest-orchestrator, not for a user request; adds to orchestration-workstream. Covers the five decisions, the issue shape the software factory's triager marks build, the dedupe rules, the repo map, and the decision block the orchestrator writes to decisions.json.
---

# Issue harvest workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it if it is not loaded. What follows is only what the issue harvest adds.

The harvest turns what people say about the owner's software (email, Portal notes and tasks, and commitments people mention in meetings that no task or issue records, for example from a time study) into GitHub issues the software factory can build. Nobody in the session reaches GitHub: `issue-harvest-sync` read it before the session into `RUN/harvest.json`, and `issue-file` writes after it, only what `RUN/decisions.json` says and the checker passed, only on a repository the owner's repo map allows.

## What you have

- `RUN/harvest.json`: `items` (the queued source items: `key`, `source`, `ref`, `date`, `title`, `text`, `from`, `repo_hints` with why each repository was matched, and `previous` when an earlier Run saw it), `batches`, and `repos`: each repository the harvest may file on, with its `product`, `title` convention, `labels` by kind, `existing_labels`, and its `open` and `recently_closed` issues (number, title, state, labels, the first part of the body, and the `harvest_markers` it carries).
- The rules file (`ISSUE-HARVEST-RULES.md`, path in the brief). It overrides this skill.
- The Portal, read only: an item's `text` is cut at 6,000 characters and an email's is only its summary, so read the whole note (`get`) or the message (`email_bodies`) before deciding anything but an obvious `not-software`.

## The five decisions

Every queued item gets one (or, filed in parts, several `new`):

| Decision | When | Fields |
|---|---|---|
| `new` | It reports a bug, asks for a feature or records a decision about a repository in `repos`, and no open or recently closed issue holds it | `repo`, `kind` (bug, feature, decision), `title`, `body`, `labels` (optional, from the map), `also` (other item keys it carries), `part` (only when one item becomes several issues) |
| `comment` | An open issue holds it and the item adds a fact (a new occurrence, a repro step, a decision, who is affected) | `repo`, `issue`, `body` |
| `duplicate` | An open or recently closed issue already says all of it, or another item in this Run carries it | `repo` and `issue`, or `of_source` |
| `not-software` | Nothing to build: business work, logistics, a digest that only quotes other sources, chatter, something already shipped, a system a client owns that the repo map does not list | `reason` |
| `ask` | Only the owner can place it: two repositories plausible and none named, or a decision that may not be final | `question` (answerable with one word, your best choice in it) |

Bias to deciding. A repo hint is a hint: the item's own words decide the repository. One source item may hold several separate pieces of work (a tester's list of bugs, a meeting with three requests): give it one `new` decision per piece, each with its own `part` (`"1"`, `"2"`, ...), and decide the pieces other items already carry as those items, not here. Every other item gets exactly one decision. A piece that is not buildable yet stays in that decision's `reason`.

## Dedupe

Before any `new`, compare against every open and recently closed issue of that repository by meaning, not words. A `harvest_markers` entry equal to the item's marker means it was filed already: `duplicate`. An open issue on the same defect or request: `comment` if the item adds something, else `duplicate`. A closed one whose fix the item says failed again: `new`, linking the closed issue in the body. Two items in this batch about the same thing: one `new` with the other in `also`.

## The issue standard (what the triager marks build)

- **Title** in the repository's convention (the `title.convention` and `pattern`), under 90 characters, saying what is wrong or wanted. For a `YYYYMMDD` convention use the date the problem was reported in the source (a tester's report date), else the item's date.
- **Body**, markdown, in this order: `## What happens` (or `## What is wanted`) with a short quote of the source; `## Expected behaviour`; `## Where and how to reproduce` (screen, record, steps, the date seen; only what the source says, never invented; "Not stated in the source" otherwise); `## Acceptance` (two to five checkable points). Do not add a source section: `issue-file` appends the source line and the marker.
- Where the source cannot give expected behaviour or a repro, write it as an ask the triager can route (what is known, the one question that would make it buildable) and add the map's `info` label when it has one.
- **Nothing private:** no client names or figures beyond what the bug needs, no email addresses or phone numbers, no file paths on anyone's machine, no secrets. Refer to people by role ("the client's tester"). `issue-file` refuses private content anyway; a refusal costs a Run.

## The return here

The shared block, with `items` holding one decision per item you were given:

```json
{"items": [
  {"source": "portal-notes:<id>", "decision": "new", "repo": "owner/name", "kind": "bug",
   "title": "...", "body": "...", "labels": [], "also": [], "confidence": "high|medium",
   "reason": "one line: why this repository and why not a duplicate"},
  {"source": "portal-email:<id>", "decision": "comment", "repo": "owner/name", "issue": 12,
   "body": "...", "confidence": "high", "reason": "..."},
  {"source": "portal-tasks:<id>", "decision": "duplicate", "repo": "owner/name", "issue": 7,
   "reason": "..."},
  {"source": "portal-notes:<id>", "decision": "not-software", "reason": "..."},
  {"source": "said-not-seen:<id>", "decision": "ask", "question": "...", "reason": "..."}
]}
```

The checker adds `check` (`PASS` or `FAIL`) and `fixes`; only the orchestrator writes `decisions.json`. No bookkeeping: you write no file.
