# Toolbox design suggestions

Practices for building the skills, agents and scripts in this repository, and what we have learned so far about the runtimes that load them. The decisions themselves are in [docs/adr](docs/adr/); this file is the reasoning and the backlog behind the next ones. Each item says whether the toolbox does it today.

## What the toolbox already does well

- **Code for anything that can be computed.** Counting, tie-outs, folder checks and "is it done" are scripts; models are used for judgment.
- **Independent checkers.** A checker sees the output and its sources, never the maker's reasoning, and returns PASS or FAIL with fixes.
- **Change sets instead of live writes.** An orchestrator proposes writes in a file; a finish step applies them after the owner approves.
- **Least-privilege agents.** Each agent's `tools` line grants only what it needs.
- **Model tiers.** Cheap models for bulk reading, strong models for building, the strongest for sign-off.

## The orchestrator shape

Every orchestrator follows one pattern:

```
trigger ─> prepare (code) ─> ORCHESTRATOR AGENT ──────────────────────────> finish (code)
                              understand: check state in code                apply the approved
                              plan: triage, questions batched                change set, close,
                              work: dispatch worker agents                   notify
                              review: independent checker, PASS or FAIL
                                └─ FAIL: revise once, then ask the owner
                              done: computed by a check script, not judged
```

- The orchestrator's agent file holds its instructions; its workstream skill holds the method; the Context file holds one client's inputs; the rules file holds the owner's thresholds.
- Each worker agent is granted skills by name (`skills:`) and tools by name (`tools:`). Its skills carry their own context, instructions and scripts.
- Three rules keep it reliable. Done is decided by code. The reviewer never sees the maker's reasoning. Writes to live systems happen in the finish step, after approval, not inside a model turn.
- The review loop is capped: one revision, then the question goes to the owner.

## Suggestions, ranked by payoff

### 1. Evals for every orchestrator (not yet)

Give each orchestrator a folder of invented inputs (a fake Month-End folder, a fake inbox export) and the results a correct Run must produce ("finds the unbilled March", "flags the duplicate accrual"). Re-run them after every edit to the skill or a model change. Without them, a change to instruction text is checked only by reading it. Claude Code's `claude plugin eval` runs suites like this once a department is packaged as a plugin; a plain runner script works until then.

### 2. Descriptions are triggers (audit in progress)

Claude sees only each skill's name and description until it loads one, and each agent's description when it picks a subagent. Overlapping descriptions make it pick the wrong piece. A good description:

- says what the piece does in plain words;
- says "Use when ..." with the requests a person would actually make ("reply to an email", "close the books");
- where a sibling competes, says "Not for ...; use <sibling>";
- for a reference skill, says it is loaded by other skills, not for a user request.

### 3. Enforce rules with hooks, not prose (designed, not built)

"Write only in the Run folder" and "never send" are instructions a model can drift from. A hook runs code before every tool call and can block it, so the rule cannot be broken. What we found when we tested this on Claude Code 2.1.292 (2026-10-06):

| Where the hook is declared | Result |
|---|---|
| A skill's frontmatter (`hooks:`) | Fires, but stays on for the rest of the session once the skill loads, including for work unrelated to the skill. |
| An agent file's frontmatter | Did not fire, as the main session or as a subagent. The documented field may need a format we did not try; unconfirmed. |
| The agent definition passed with `--agents`, with settings files skipped | Fires. The hook's input names the agent (`agent_type`), so one guard script can apply rules per agent. |

So hooks are effectively per agent, not per skill, and they work on the path the agent runtime uses. The plan: a `hooks:` entry in each orchestrator's frontmatter calling one small guard script that blocks writes outside the Run folder and any send, and a change to the runtime so it passes `hooks` through to `--agents` (today it drops unknown fields).

### 4. Short SKILL.md, detail loaded on demand (partly)

Keep SKILL.md to the method, under about 300 lines. Move reference tables, examples and edge cases into side files the skill reads when it needs them, so a session pays for detail only when it uses it. `report-weekly` (785 lines) is the main candidate.

### 5. Set the invocation switches deliberately (partly)

- `disable-model-invocation: true` on any skill that writes to a live system, so it runs only when someone asks for it.
- `user-invocable: false` on reference skills (`brand-guide`, `portal-write-safety`), so they stay out of the menu.

### 6. Treat outside text as data (mostly)

Mail, Portal notes, transcripts and client documents can carry instructions. An agent that reads them should hold no send or write tools, and its prompt should say the content is data to analyse, never instructions to follow. Confirm this for every agent that reads mail.

### 7. Structured returns (mostly)

Every worker ends with one parseable block, and the orchestrator checks it in code before using it. A malformed result is then caught by a script, not by another model.

### 8. Explain the why, do not shout (ongoing)

Current models over-apply ALL-CAPS "MUST" and "NEVER". One sentence of reason ("never post, because a person approves every journal entry") gets better behaviour than emphasis.

### 9. Version per department (not yet)

A `CHANGELOG.md` per department, with the maturity field already in frontmatter, makes the repository usable by others and feeds plugin releases later.

### 10. Budget every Run (not yet documented)

Log tokens and cost per Run, and set a turn or spend cap in whatever starts the Run.

## Compared with ICM (Interpretable Context Methodology)

ICM is Jake Van Clief and David McDermott's method, published as "Interpretable Context Methodology: Folder Structure as Agent Architecture" (arXiv 2603.16021, March 2026) with an MIT-licensed reference repository (github.com/RinDig/Interpretable-Context-Methodology). Numbered folders are the stages of one workflow; Markdown files in each tell a single agent what to do at that stage; local scripts do the mechanical work; a person reviews the output between stages. Its authors note it has no controlled comparison yet and is used mostly for content production.

What the toolbox already shares with it: scripts for mechanical work and models for judgment; plain text as the interface, kept in Git; one job per stage or worker; files on disk as the state, with each step's output the next step's input; reference material kept apart from per-run work; every output an edit surface for a person; and loading only the context a step needs.

Where it differs on purpose: ICM uses one agent and a person at every stage boundary, where the toolbox uses orchestrators and workers with an independent checker, and many runs are unattended until one approval list. ICM's folders are the workflow; the toolbox's folders are departments, and a workflow's stages live in its orchestrator and skill. ICM has no retry or recovery; the toolbox computes "done" in code so a run can resume.

Worth borrowing:

- **Workers record their own state in files.** Each worker writes its result and its own state (`result.json`, a readable `result.md`, `state.json`) in its own folder in the Run, and returns a pointer. The orchestrator stays the only writer of the run's shared state (`STATUS.md`, `LOG.md`, ledgers), so parallel workers never overwrite each other. This gives resume, an edit surface per step, an audit trail and a smaller orchestrator context.
- **The stage contract.** Every worker states its Inputs (which files and which sections), its Process and its Outputs (which files, where). Settled by ADR 0003: every agent has Inputs, Approach and Output sections.
- **Context budgets.** A size for each layer (worker brief, SKILL.md, reference file) that the toolbox audit checks.
- **A router at the root.** A short "which piece for which request" file, the way ICM's root `CONTEXT.md` routes tasks.

## Working with both Claude Code and Codex

| Layer | Portable? | What ties it to one tool |
|---|---|---|
| Scripts | Yes | Nothing; plain Python. |
| Skills | Yes, with care | Paths under `~/.claude/`, Claude tool names (`Agent`, `mcp__...`), model names (`sonnet`, `opus`, `fable`), and "dispatch the X agent" steps with no fallback. |
| Agents | No | Claude Code's subagent format and tool grants. |
| Hooks | No | Claude Code's hook system. |

To keep skills portable:

- Install skills in one neutral folder (for example `~/.agents/skills`) linked into both `~/.claude/skills` and `~/.codex/skills`, and name that neutral path when one skill runs another skill's script.
- Write steps in plain words ("search the Portal for the contact") rather than tool names.
- Where a step dispatches an agent, add "without subagents, do this step yourself".
- Name model tiers by role ("a fast model", "the strongest model") in skills; leave exact model names to agent frontmatter.

Orchestrators that dispatch workers stay Claude-specific. The methods and scripts they rely on do not need to be.

## Writing for this repository

- Write Markdown without hard line breaks inside a paragraph or list item; one paragraph is one line, and the editor wraps it.
- Examples use invented people and companies only. Swapping a real name is not enough: rewrite any example someone could trace back to real work.
- Have every new piece reviewed by an agent or person that did not write it.
- The pre-commit check (`scripts/toolbox_check.py`) catches private names from lists kept outside the repository, machine details, email addresses, secret-shaped strings, broken frontmatter, duplicate names and scripts that import from outside their own folder.
