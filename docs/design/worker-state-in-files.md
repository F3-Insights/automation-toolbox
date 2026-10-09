# Workers record their state in files

Status: proposed, 2026-10-06. Becomes ADR 0004 when accepted.

## Why

Today a worker agent does its step and hands everything back to its orchestrator in one JSON block in its final message (`orchestration-workstream`, "The return"). The orchestrator is the only writer of state: it records what each worker returned in the Run's `STATUS.md`, `LOG.md`, ledgers and change sets. About 70 of the toolbox's agents, mostly analysts and checkers, hold no write access at all.

That keeps the Run's shared state trustworthy, but it has costs:

- **No resume at the worker level.** If a Run stops part way, whatever a worker found lives only in a message that is gone. The next Run dispatches it again.
- **No edit surface per step.** The owner can edit the Run's drafts, but not an analyst's findings before the writer uses them.
- **A thin audit trail.** A checker or a person tracing a claim back has the orchestrator's summary of a worker's return, not the worker's own record.
- **A crowded orchestrator.** Every worker's full return lands in the orchestrator's context at once.

The Interpretable Context Methodology (Van Clief and McDermott, arXiv 2603.16021) makes files on disk the state of a workflow: each stage writes its output to a folder, and the next stage reads it. This design borrows that idea while keeping the toolbox's rule that one writer owns shared state.

## The rule

1. **Every worker writes its own record, in its own folder, inside the Run.** Nowhere else.
2. **The orchestrator stays the only writer of the Run's shared state:** `STATUS.md`, `LOG.md`, ledgers, registers, change sets and outboxes. Parallel workers never write the same file.
3. **A worker returns a pointer, not its payload.** Its final message names its folder and its state in one or two lines. The JSON block it returns today becomes `result.json` in its folder.

## The worker folder

```
RUN/
  STATUS.md, LOG.md, ...          shared state, orchestrator only
  workers/
    <step>-<worker>-<item>/       one folder per dispatch
      state.json                  where this dispatch stands
      result.json                 the return block, as today
      result.md                   the same result for a person to read and edit
      evidence/                   optional: pulls, extracts, screenshots it relied on
```

The folder name is set by the orchestrator in the dispatch brief, so it is predictable and unique: the step (`analyse`, `check`, `draft`), the worker's name, and the item or batch it was given (`batch-03`, a contact id, a period).

### `state.json`

```json
{
  "worker": "collections-analyst",
  "dispatch": "analyse-collections-analyst-batch-03",
  "state": "done",
  "started": "2030-04-02T14:05:11Z",
  "finished": "2030-04-02T14:09:40Z",
  "inputs": ["RUN/inputs/aging.csv", "RUN/inputs/rules.md"],
  "outputs": ["result.json", "result.md"],
  "reason": ""
}
```

`state` is one of:

- `started`: written first, before any work. A Run that finds a folder still `started` knows the dispatch died.
- `done`: the result is complete.
- `blocked`: the worker needs an answer; `reason` names the question. The questions are also in `result.json` as today.
- `failed`: the worker could not do its step; `reason` says why in one line.

`inputs` lists every file the worker read, which gives ICM's stage contract (Inputs and Outputs) a record on disk.

### `result.json` and `result.md`

`result.json` is exactly today's return block (items, rows, files, findings, questions, proposals, notes, extra), so the orchestrators' recording logic does not change, only where it reads from. `result.md` renders the same content for a person: the findings and proposals as short lines, each with its source. If the owner edits `result.md` before the next step, the orchestrator treats the edit as the owner's answer: it records that the result was edited and uses the edited version.

## What the orchestrator does

- Before dispatch, it creates the worker's folder name and passes it in the brief.
- After the worker returns, it reads `state.json` and `result.json`, never the worker's message, and records them in shared state as today.
- On resume, it lists `RUN/workers/`: `done` folders are recorded and not dispatched again; `started` folders are treated as failed and dispatched again; `blocked` folders wait for their answer.
- It never edits a worker's folder. A correction is a new dispatch with a new folder.

## Writing safely

- Workers write files whole: write a temporary file in the same folder, then rename it. A reader never sees half a file.
- `state.json` is written first as `started` and last as `done`, `blocked` or `failed`.
- Checkers stay independent: a checker reads the maker's `result.json` and the sources, never the maker's reasoning, and writes its own verdict into its own folder.

## Permissions

Read-only workers gain one right: writing inside their own worker folder. The Run folder's path differs from Run to Run, so a fixed path cannot be named in an agent's `tools:` line.

Open question: whether Claude Code permission rules can name a path relative to the folder the session starts in. The agent runtime starts each Run with the Run folder as its working directory, so a rule such as "write only under `./workers/`" would fit exactly. If relative rules work, each worker's grant becomes that. If they do not, the per-agent hook on the [roadmap](../roadmap.md) is the enforcement: a hook that refuses any write outside the worker's own folder, keyed on the agent's name. Until one of those is in place, the rule is enforced by instruction and by the toolbox audit.

## Checks

- `orchestration-workstream` (the conduct every worker loads) changes from "you return; it records" to "you write your folder; it records".
- `orchestrator-scaffold` generates new orchestrators and workers in this shape.
- The toolbox audit gains a check: every worker brief names its folder and the three files; no worker writes outside `workers/`; orchestrators read results from files.
- Each converted department keeps its tests passing and gains one test per orchestrator that a Run with a `started` folder resumes correctly.

## Migration

One department at a time, each with an independent review, in this order:

1. `accounting`, month-end first: the most mature orchestrator, with a `STATUS.md` and `LOG.md` already, and the most to gain from resume.
2. `finance` and `reporting`, which share month-end's reviewers.
3. The Portal departments (`productivity`, `recurring-summaries`, `chief-of-staff`), where workers are many and parallel.
4. The rest.

Unconverted workers keep returning a JSON block; the orchestrator accepts either during the migration.

## What does not change

- The orchestrator is still the only writer of shared state.
- Change sets are still applied after approval by a finish step, in code.
- Done is still computed by a check script, not judged.
- The return block's fields are unchanged; they move from a message into a file.

## Costs and risks

- More files per Run. Mitigation: the Run folder is already per Run and is never committed.
- Write access for read-only workers, which is a wider surface until it is scoped by a relative rule or a hook.
- Two reading paths during the migration.

## Also borrowed from ICM, separately

- **The stage contract.** Every worker agent states its Inputs (files and sections), Process and Outputs under those three headings.
- **Context budgets.** A size limit per layer (worker brief, SKILL.md, reference file), checked by the toolbox audit.
- **A router at the root.** A short "which piece for which request" file.

These are independent of the rule above and can go in any order.
