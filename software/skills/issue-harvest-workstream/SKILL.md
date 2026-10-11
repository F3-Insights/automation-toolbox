---
name: issue-harvest-workstream
description: "The issue harvest's method, loaded by issue-harvest-orchestrator and by the software-worker and software-reviewer it dispatches, not for a user request; adds to orchestration-workstream. Covers running a harvest, the five decisions, the issue shape the issue loop's Triage can take forward, the dedupe rules, the sections Decide a batch and Check the proposals, and the decision block the orchestrator writes to decisions.json."
---

# Issue harvest workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it if it is not loaded. What follows is only what the issue harvest adds.

The harvest turns what people say about the owner's software (email, Portal notes and tasks, and commitments people mention in meetings that no task or issue records, for example from a time study) into GitHub issues the issue loop (`software-orchestrator`) can work. Nobody in the session reaches GitHub: `software-issue-harvest-sync` read it before the session into `RUN/harvest.json`, and `software-issue-file` writes after it, only what `RUN/decisions.json` says and the checker passed, only on a repository the owner's repo map allows, each with the source's marker so nothing is filed twice; `software-issue-harvest-record` then writes every item's outcome to the harvest ledger so no item is decided twice. Whether the harvest is done overall is computed by `software-issue-harvest-check`.

## What you have

- `RUN/harvest.json`: `items` (the queued source items: `key`, `source`, `ref`, `date`, `title`, `text`, `from`, `repo_hints` with why each repository was matched, `marker`, and `previous` when an earlier Run saw it), `batches` (`b1`, `b2`, ... of eight), `deferred` (left for the next Run), `sources` (one report per source, `readable` false when it could not be read), `window`, `counts`, and `repos`: each repository the harvest may file on, with its `product`, `title` convention, `labels` by kind, `existing_labels`, and its `open` and `recently_closed` issues (number, title, state, labels, the first part of the body, and the `harvest_markers` it carries). If it is missing or queues nothing, the Run writes a `decisions.json` with no decisions and says so.
- The rules file (`ISSUE-HARVEST-RULES.md`, path in the inputs as `rules_file`) and the repo map (the file the `repos_file` setting under `[issue-harvest-workstream]` names). The rules override this skill.
- The Portal, read only (`whoami`, `get`, `search`, `list_entities`, `email_bodies`): an item's `text` is cut at 6,000 characters and an email's is only its summary, so read the whole note (`get`) or the message (`email_bodies`) before deciding anything but an obvious `not-software`.
- `RUN` is the working folder; only the orchestrator writes there, always by absolute path.

## Running the harvest

For `issue-harvest-orchestrator`. The queue was cut in code (window, max items, repositories); never widen it.

1. **Orient.** `whoami`; read the rules file and `RUN/harvest.json` (its counts, any unreadable source or repository, the window). Write `RUN/plan.json`: the batches and their item keys.
2. **Decide.** One `software-worker` per batch, all at once, never two on one item, each told to follow this skill's section Decide a batch, with the batch id and its item keys, the Run folder's absolute path, the rules file's path, today's date and the owner's instructions. With one or two batches, decide them yourself by the same section. Save each return as `RUN/returns/<batch>.json` as soon as it arrives; a reply without the json block goes back once for it.
3. **Reconcile across batches.** Two batches may propose a `new` for the same thing: keep the one with the fuller source, turn the other into `duplicate` with `of_source`, or add it to the first one's `also`.
4. **Check every write.** Send every `new` and `comment` to `software-reviewer`, told to use this skill's section Check the proposals, in batches of up to ten, with the proposals as written, the Run folder and the rules path, never the decider's reason or summary. Save its returns as `RUN/returns/check-<n>.json`. A FAIL is revised once with the fixes and checked again; a second FAIL becomes `ask` when there was a best guess, else `not-software` with the checker's reason. Only a PASS is filed.
5. **Write `RUN/decisions.json`:** `{"orchestrator": "issue-harvest-orchestrator", "dry_run": <true|false>, "decisions": [...], "questions": [{"source": <key>, "ask": "...", "why": "..."}]}`, one decision per queued item (several `new` with a `part` each when one item holds several pieces of work) in the shape of The return here, each `new` and `comment` carrying `"check": "PASS"` or `"FAIL"` as the checker last said.
6. **Close.** Report how many items became new issues, comments, duplicates, not software and questions, per repository; the questions as one numbered list; any source or repository that could not be read; the deferred count. Never claim a write: the finish step makes and counts them.

Bias to action, on evidence: a plain bug or request with no matching issue is filed without asking. Ask only what the source and the record cannot settle, all of a Run's questions as one list. With no one present everything runs the same, and questions go in `decisions.json` and the report.

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

## The issue standard (what the issue loop's Triage can take forward)

- **Title** in the repository's convention (the `title.convention` and `pattern`), under 90 characters, saying what is wrong or wanted. For a `YYYYMMDD` convention use the date the problem was reported in the source (a tester's report date), else the item's date.
- **Body**, markdown, in this order: `## What happens` (or `## What is wanted`) with a short quote of the source; `## Expected behaviour`; `## Where and how to reproduce` (screen, record, steps, the date seen; only what the source says, never invented; "Not stated in the source" otherwise); `## Acceptance` (two to five checkable points). Do not add a source section: `software-issue-file` appends the source line and the marker.
- Where the source cannot give expected behaviour or a repro, write it as an ask that Triage can route to needs-info (what is known, the one question that would make it buildable) and add the map's `info` label when it has one.
- **Labels for the issue loop:** a repository the issue loop works lists its status label `triage` under the map's `always` labels, so every filed issue lands on the lead's board waiting for Triage (`software-issue-loop`). Never set `ready` or a later status: Triage decides that.
- **Nothing private:** no client names or figures beyond what the bug needs, no email addresses or phone numbers, no file paths on anyone's machine, no secrets. Refer to people by role ("the client's tester"). `software-issue-file` refuses private content anyway; a refusal costs a Run.

## Decide a batch

For a `software-worker` given one batch (or the orchestrator deciding a small Run itself). The goal is a decision on every item given, each resting on the item's own words and the issue snapshot, never on a guess. Read the rules file first, then `RUN/harvest.json`: your items (by key) and the `repos` block. For each item:

1. Read the whole source in the Portal unless the title alone shows it is not software (`get` for a note or task, `email_bodies` for a message). A meeting note can hold one harvestable sentence in a long page; find it.
2. Decide which repository, from what the source says, not only the hint.
3. Dedupe against that repository's issues by meaning, and against the other items in your batch.
4. Write the decision. A `new` issue is written to the issue standard above, so Triage would mark it ready or send it to a plan; where the source cannot give that, a precise ask.

Ask the owner only what the source and the record cannot settle (which repository, whether a decision is final), with your best choice in the question. Write nothing: no file, no Portal record, no GitHub call. End with a short summary, then the block in The return here.

## Check the proposals

For `software-reviewer`, the last reader before an issue lands on GitHub. The goal is that nothing reaches a repository that is wrong, unsupported, duplicated or private. Read the rules file, then for each proposal the source item in `RUN/harvest.json` and in full in the Portal (`get`, `email_bodies`), and the target repository's `open` and `recently_closed` issues there. A proposal PASSES only when all of these hold:

1. **Right repository:** the source is about that product, and the repository is in `repos`.
2. **Supported:** every claim in the title and body is in the source; reproduction steps and expected behaviour are the source's, or marked as not stated. Nothing invented.
3. **Not a duplicate:** no open or recently closed issue holds it (for a comment: the issue it comments on is the right one, and the comment adds a fact).
4. **Nothing private:** no client names or figures beyond what the bug needs, no email addresses, phone numbers, machine paths or secrets.
5. **Buildable shape:** the title follows the repository's convention; the body has the sections of the issue standard and checkable acceptance points, or is a precise ask.

A FAIL names which test failed and the exact fix. End with a short summary, then exactly one fenced `json` block:

```json
{"items": [{"source": "<key>", "check": "PASS|FAIL", "failed": ["supported"], "fixes": ["..."]}]}
```

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

The checker adds `check` (`PASS` or `FAIL`) and `fixes`; only the orchestrator writes `decisions.json`. No bookkeeping: a worker writes no file.
