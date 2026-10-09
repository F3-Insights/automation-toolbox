# Process flow: the Run contract

What a process-flow Run holds and what each agent in it writes or returns: the staged folder, the ids, the map file, the commands and the reviewers' json blocks. `SKILL.md` in this skill is the method and the conduct; this file is the reference it points to.

## The staged folder

`process-flow-prepare` stages one engagement process into the Run's work folder. Everything happens there; `process-flow-publish` writes it back after the session.

| Path | Holds | Written by |
|---|---|---|
| `PROCESS-FLOW-RULES.md` | Scope, audience, lanes, reference model, red team bar, the four stakeholder decisions. It wins over everything here. | the owner |
| `BACKGROUND.md` | The client, its systems, the roles by title | the owner |
| `REFERENCE-MODEL.md` | The standard process the completeness audit compares against | prepare |
| `sources.json`, `sources/<id>.*` | The source register and each source as readable text (`T01` a transcript, `B01` background; `half` A or B; `duplicate_of`) | prepare, claim-ledger |
| `inventories/<id>.md` | One transcript reader's return per transcript | the orchestrator |
| `CLAIM-LEDGER.csv` | Every claim, pain, wish, number and contradiction with its id, quote and `quote_found` | claim-ledger build |
| `maps/map v<N>.json` | The map, one file per version, never edited once written | the mapper |
| `renders/` | `<process> v<N> as-is.html`, `... as-is and to-be.html`, `... narrative.md`, `... as-is.png` | process-flow-render |
| `reviews/` | The assertions and each recorded review of a map version | claim-ledger |
| `VERIFICATION v<N>.md` | The verification memo and open questions | claim-ledger memo |
| `STATUS.md`, `LOG.md` | Where it stands; the session log | the orchestrator |
| `returns/` | Agents' returns saved for recording; stays in the Run | the orchestrator |

Ids never change: a source keeps its id across sessions, and a claim is `<source>-<letter><n>` (`T03-C12` claim 12 of T03; `P` pain, `W` wish, `N` number, `X` contradiction; claims added by hand from a background document are `B02-C101` upward).

## The map file

`maps/map v<N>.json`, schema `process-flow-map/1`. The exact form is the map check in this skill's `scripts/_common.py`, which `process_flow_check.py` and `process_flow_render.py` both run. In short:

```json
{"schema": "process-flow-map/1", "version": 1, "process": "quote-to-order", "title": "Quote to order",
 "client": "Acme Components", "date": "October 2026", "audience": "the client's leadership team",
 "scope": "as-is-and-to-be", "proposed_system": "PLATFORM",
 "lanes": [{"id": "CUST", "label": "Customer", "external": true}, {"id": "SALES", "label": "Sales"}],
 "abbreviations": {"ERP": "the enterprise resource planning system"},
 "changes": ["v2: split 'Process order' into entry and confirmation (fact-check, T02-C7)"],
 "sections": [{"num": "01", "title": "Quote to order", "headline": "...", "narrative": "two to four plain sentences",
   "delta": {"today": "quotes typed line by line", "proposed": "quotes drafted for review", "claims": ["T01-P2"]},
   "asis": {"caption": "...",
     "nodes": [{"id": "a1", "lane": "SALES", "col": 1, "kind": "step", "title": "Create quote",
                "sub": "line by line", "systems": ["ERP"], "badge": "PAIN", "note": 1, "claims": ["T01-C12"]}],
     "edges": [{"from": "a1", "to": "a2", "style": "solid", "label": ""}],
     "callouts": [{"n": 1, "type": "pain", "text": "Each quote takes about two hours (estimate).", "claims": ["T01-N3"]}]},
   "tobe": {"caption": "...",
     "nodes": [{"id": "t1", "lane": "SALES", "col": 1, "kind": "step", "title": "Review drafted quote",
                "systems": ["PLATFORM"], "badge": "NEW", "replaces": ["a1"], "answers": ["T01-P2"],
                "why": "Removes the retyping the sales lead named as the slowest step."},
               {"id": "t2", "lane": "CUST", "col": 0, "kind": "doc", "title": "Purchase request", "same_as": "a0"}],
     "edges": [], "callouts": []},
   "removed": [{"node": "a4", "answers": ["T02-P1"], "why": "..."}]}]}
```

The rules that make it citable:

- **Every as-is step and callout cites a claim** in the ledger. A step no claim supports is not on the map; it is a question.
- **A to-be step is the same step** (`same_as` an as-is id; no badge) **or a change**: badge NEW or TBD, `answers` naming the pain claims it answers, `why` in one sentence. A removal names its pain and why too. TBD marks scope not yet designed; say so rather than invent it.
- **The as-is is strictly factual**: no NEW or TBD badge, no proposed system chip, no to-be callout, no word of the proposal. Badges there are PAIN and DELAY only.
- **Naming**: every step is an imperative verb and object, the lane its subject ("Confirm delivery date" in the Supplier lane). Decisions are questions. Stores and documents are nouns. Nodes stay skinny (a verb phrase, a subtitle of six words or fewer); numbers, quotes and explanations go in callouts. No jargon a chief executive would squint at; expand each abbreviation once in `abbreviations`.
- **Lanes are functional roles**, never people; external actors (customers, suppliers) are real lanes. Use the rules file's `Lanes` when it lists them. Every lane declared is used.
- **Numbers keep their basis**: an estimate on the map says it is one.
- **A version is written once.** To change the map, write `map v<N+1>.json` with a `changes` line for each change and the source or review that forced it.

## Commands

One command per call. Every one takes `--format json`.

| Command | Does |
|---|---|
| `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py build WORK` | Inventories to `CLAIM-LEDGER.csv`; checks each quote against its source |
| `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py add WORK --source B02 --text ... --quote ... --location ...` | Adds a claim from a background document (the quote must be in it); then `build` |
| `python3 ~/.claude/skills/process-flow-workstream/scripts/process_flow_check.py WORK --format json` | The six tests of done, with every map error by step |
| `python3 ~/.claude/skills/process-flow-workstream/scripts/process_flow_render.py WORK` | Draws the current map version; refuses a map with errors or a version already drawn |
| `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py brief WORK` | The current map's assertions, and the files each fact-check half reads |
| `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py record WORK --kind K --from FILE` | Checks and keeps a review of the current version (`factcheck-A`, `factcheck-B`, `completeness`, `redteam`) |
| `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py memo WORK` | `VERIFICATION v<N>.md` once both halves and the completeness audit are recorded |

## The json blocks the reviewers return

The orchestrator puts the matching block in each brief and asks for it as the last thing in the return; it saves the return under `returns/` and records it with `claim-ledger`.

**transcript-reader** (one per transcript, given the staged source file, the topic tags and `Source id: T03`), after its usual inventory:

```json
{"source": "T03",
 "claims": [{"n": 1, "topic": "quoting", "claim": "...", "speaker": "sales lead", "quote": "...", "location": "12:40", "leading": "no"}],
 "pains": [{"n": 1, "pain": "...", "speaker": "...", "quote": "...", "location": "...", "consequence": "rework"}],
 "wishes": [{"n": 1, "wish": "...", "speaker": "...", "quote": "...", "location": "..."}],
 "numbers": [{"n": 1, "number": "40", "unit": "hours a week", "measures": "...", "speaker": "...", "quote": "...", "location": "...", "basis": "estimated"}],
 "contradictions": [{"n": 1, "text": "...", "a_quote": "...", "a_location": "...", "b_quote": "...", "b_location": "..."}]}
```

**fact-check** (two, one per half, each given only its half's files from `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py brief` and the assertions file): one verdict per assertion key, `VERIFIED` or `CONTRADICTED` with the source id, quote and location from its half, else `NOT IN MY SOURCES`; then the facts its sources hold that the map omits.

```json
{"half": "A",
 "verdicts": [{"key": "01/asis/a2", "verdict": "VERIFIED", "source": "T01", "quote": "...", "location": "...", "note": ""}],
 "omissions": [{"fact": "...", "source": "B02", "location": "...", "quote": "..."}]}
```

**completeness-audit** (given the as-is render, the map file and `REFERENCE-MODEL.md`): about fifteen questions, highest priority first; a question a source already answers carries the answer instead of being asked.

```json
{"model": "order-to-cash",
 "questions": [{"n": 1, "priority": "high", "question": "...", "why": "...", "who": "the operations lead",
                "answered_by": null}]}
```

`answered_by` is `{"source": "T02", "location": "...", "quote": "..."}` when the sources answer it.

**executive-red-team** (given only the rendered page or its screenshot, the audience and a one-line purpose): a letter grade per section, every criticism with a concrete fix.

```json
{"overall": "B", "one_change": "...",
 "sections": [{"num": "01", "grade": "B+", "criticisms": [{"text": "...", "fix": "..."}]}]}
```
