# Architecture review: the toolbox, Sentinel and the "one agent, a folder, some skills" shape

Date: 2026-10-11. Written after reading the Isenberg/"Ross Mike" notes and his repository,
the toolbox (204 agents, 153 skills, 404 scripts in 18 departments), Sentinel's transport,
Automations, Libraries and roster code, ADRs 0007, 0008, 0010, 0012, 0013 and 0017, the 71
live Automations and 68 roster overlays, and the current Claude Code docs (2.1.296 installed).
Three headless probes were run on this machine to check what a session actually sees. Numbers
in this review are counted from the files, not estimated, unless marked.

## 1. The answer

**Keep the agent as the unit you launch, but make it a different kind of agent.** A launched
agent should be a goal, a tool list and a list of skills, under 60 lines, that works to its
goal itself in a folder. Not a dispatcher of thin specialists. The method lives in skills; the
agent names which ones.

**Do not install the toolbox's skills globally.** Unlink `~/.claude/skills` from the toolbox.
Keep the merged folder `link.py` already builds (`~/.local/share/f3i-toolbox/skills/`) as the
one stable path scripts are run from, and give each session only the skills it needs:

- **Headless (Sentinel):** the session is already sealed (`--setting-sources ""`) and sees no
  user skills at all; verified by probe. Sentinel should build a tiny per-Run plugin folder
  holding links to the agent's `skills:` and pass `--plugin-dir`. Verified by probe: a sealed
  session then lists exactly those skills and nothing from `~/.claude/skills`. Until that lands,
  the agent reads `SKILL.md` by path, as today.
- **Interactive:** per project, either a `.claude/skills/` folder of links to the few skills that
  repo uses, or a department plugin enabled in that project's `.claude/settings.json`. Nothing
  from the toolbox appears in a session started elsewhere.

**Cut the agents from 204 to about 38:** one main agent per recurring job after merging jobs
that share a folder and a cadence (about 36), plus two shared agents, `reviewer` (independent
check, fresh context, briefed with the job's checklist) and `worker` (one slice of parallel work,
briefed with a skill section). Specialists dissolve into sections of their job's skill. The
software department goes from 20 agents to 4 main agents plus the two shared ones; keep
`software-factory-orchestrator`'s design and retire `software-orchestrator`.

The reason this is safe is in the probe numbers (section 2): today's global install costs about
8,000 tokens per turn in every interactive session and, because of Claude Code's listing
budget, shows the description of only about 37 of the 153 toolbox skills (on a 1M-context
model; about 10 on a 200k one). The rest are names only. The skills are not triggering by
description now; removing them from everyday sessions loses little.

## 2. Verified facts

### 2a. Claude Code docs (fetched 2026-10-11)

| Fact | Source |
|---|---|
| At start a session holds every skill's name and description; "full skill content only loads when invoked". Once invoked, the body stays in the conversation. | [skills](https://code.claude.com/docs/en/skills) |
| The listing is capped at 1% of the context window (`skillListingBudgetFraction`, default 0.01). Over the cap, "Claude Code keeps every skill's name but drops the descriptions of the least-used skills, so Claude can still invoke those skills but is less likely to choose one on its own." | [settings reference](https://code.claude.com/docs/en/settings-reference#skilllistingbudgetfraction) |
| Each entry's description is cut at 1,536 characters (`skillListingMaxDescChars`). | same |
| `/skill-doctor` reports each skill's context cost and use; `/doctor` estimates the listing's cost. | [skills](https://code.claude.com/docs/en/skills) |
| Skills are found in managed settings, `~/.claude/skills/`, `.claude/skills/` (the start folder and every parent up to the repo root), nested `.claude/skills/` below (loaded on first touch), an `--add-dir` folder's `.claude/skills/` (needs the project setting source), and plugins (`<plugin>/skills/`, named `plugin:skill`). | [skills](https://code.claude.com/docs/en/skills) |
| `skillOverrides` in settings: `on`, `name-only`, `user-invocable-only`, `off` per skill. `disable-model-invocation: true` in frontmatter keeps a skill out of automatic loading, sub-agent preloads and scheduled-task prompts. | [skills](https://code.claude.com/docs/en/skills), [settings reference](https://code.claude.com/docs/en/settings-reference#skilloverrides) |
| `--plugin-dir <path>` loads a plugin "for this session only", repeatable; `enabledPlugins` (`name@marketplace: true/false`) switches installed plugins per scope, including a project's `.claude/settings.json`. | [CLI reference](https://code.claude.com/docs/en/cli-reference), [plugin loading](https://code.claude.com/docs/en/plugins/loading) |
| `--bare` skips hooks, skills, commands, sub-agents, plugins, MCP servers, auto memory and CLAUDE.md; add back with `--plugin-dir`, `--agents`, `--settings`, `--mcp-config`, `--append-system-prompt`. | [headless](https://code.claude.com/docs/en/headless) |
| `--setting-sources ""`: documented as "comma-separated list of setting sources to load (user, project, local)"; the empty case is not described. Observed below. | [CLI reference](https://code.claude.com/docs/en/cli-reference) |
| A sub-agent's `skills:` preloads "the full skill content ... not only the description" at start, up to 32 names; the sub-agent can still invoke any other discoverable skill through the Skill tool; the field "controls which skills are preloaded, not which skills the subagent can access". | [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| Agents are found in managed settings, `--agents` (session only, JSON or a file), `.claude/agents/`, `~/.claude/agents/`, plugin `agents/`. `--agent <name>` makes "the main thread itself take on that subagent's tool restrictions and model", and its prompt replaces the default system prompt. | [sub-agents](https://code.claude.com/docs/en/sub-agents), [settings reference](https://code.claude.com/docs/en/settings-reference#agent) |
| `AGENTS.md` is read natively (2.1.277+), but only when no `CLAUDE.md`, `CLAUDE.local.md` or `.claude/CLAUDE.md` exists in the working folder or above; `pluginConfigs` can switch to `claude-md-and-agents-md`. A `CLAUDE.md` holding `@AGENTS.md` imports it in every case. | [memory](https://code.claude.com/docs/en/memory) |

Not stated anywhere in the docs: a per-skill token figure, and whether `--agent`/`--agents`
change what skills the main thread sees.

### 2b. Observed on this machine (three `claude -p` probes, haiku, one turn, Skill tool only)

| Session | Toolbox skills listed | System prompt tokens (cache write + read) |
|---|---|---|
| Default (user settings, `~/.claude/skills` linked) | 171 names in the listing | 13,543 + 1,467 ≈ 15,000 |
| `--setting-sources ""` (what Sentinel runs) | 0; only Claude Code's 14 built-ins | 2,764 + 4,227 ≈ 7,000 |
| `--setting-sources ""` plus `--plugin-dir` holding one probe skill | that one skill, as `acme-probe:acme-probe-skill`, plus the built-ins | ≈ 7,000 |
| `--bare --plugin-dir` | the session answered "Not logged in" | n/a |

`/skill-doctor` in a default session: 153 toolbox skills loaded, **37 with a description
(about 190 tokens each), 116 name-only (under 20 tokens)**, 148 "loaded but never invoked".
That is the 1% budget at work on a 1M-context model (about 10,000 tokens). On a 200k-context
model the budget is about 2,000 tokens, so roughly ten descriptions survive. The toolbox's
descriptions total 93,811 characters (mean 613, max 1,587): far over any budget.

So the global install costs about 8,000 tokens a turn (the listing plus the user `CLAUDE.md`)
and still leaves most skills undiscoverable by description. Both halves of the owner's worry
hold, and the second is the worse one.

### 2c. How a Sentinel session sees skills today (`engine/model_claude_code.py`, ADR 0013)

- Every session runs `--setting-sources ""`, so no user or project settings, no `CLAUDE.md`,
  no plugins, **no skills as Skill-tool entries** (ADR 0013, Consequences; confirmed by the
  probe). The owner's `AGENTS.md` working rules travel in `--append-system-prompt-file`.
- A toolbox agent runs as itself with `--agent <name>`, and because the CLI finds no agent
  files, its definition and those of every agent it may dispatch travel in `--agents` (JSON, or
  a file past 100 KB). `roster.subagent_definition` sends `description`, `prompt`, `tools` and
  `model` only: **the `skills:` lists of the 170 agents that have one are dropped on the way.**
  Even if sent, the preload would find nothing, since no skill is discoverable.
- Skills reach a session only by reading: the Automation's system prompt says "No skill is
  loaded as a tool in this session. A skill the task names is the file
  `{skills_dir}/<name>/SKILL.md`: read it first and follow it"; `libraries.read_roots` adds a
  `Read(//...)` rule for each Library folder, `{skills_dir}` and `~/.claude/skills`, following
  links to the checkout. 138 toolbox files carry the "read it at `~/.claude/skills/<name>/SKILL.md`
  if it is not loaded" sentence for this reason.
- Scripts are run by literal path. The Bash guard matches the command string and never expands
  `~` or a variable (ADR 0010 decision 8), so 126 agent files and 139 skill files name
  `~/.claude/skills/<skill>/scripts/<x>.py` (893 occurrences in 288 files, 134 distinct script
  paths in agent tool rules). Sidecars repeat each rule with `~` and with the absolute home path.
- `{skills_dir}` in a prepare/finish command is the runtime config's `skills_dir`, or
  `~/.claude/skills` when Libraries are set and it is not. The owner's `config.yaml` sets
  `libraries:` and no `skills_dir`.

The consequence: the agent's `skills:` list is documentation today. It scopes nothing, and
nothing in the chain hands a session a chosen set of skills. That is the gap to close.

## 3. Three designs side by side

| | The guest's | The owner's today | Recommended |
|---|---|---|---|
| Unit launched | A repo session; the person types the feature | A toolbox orchestrator agent, as a sealed Sentinel session (`--agent`), per Automation | A main agent: goal + tools + `skills:`, as a sealed session, into a folder with a Context |
| Who sequences | The person, 15 terminal tabs | The orchestrator, dispatching 2 to 9 specialists | The main agent itself; `worker` for parallel slices; `reviewer` for independence |
| Where the method lives | `AGENTS.md` (4 beats) + 6 skills (~4,200 lines) | 68 orchestrator bodies (median 32 lines, max 148) + 45 `-workstream` and 20 `-method` skills + `orchestration-workstream` + each department's specialists | One skill per job, sections per stage; `orchestration-workstream` kept as the one shared conduct skill |
| Independent review | Greptile, external, scored out of 5, loop to 5/5 | 30 checker/reviewer agents; 65 of 67 workflows end in one | One `reviewer` agent, fresh context, given the job's checklist and the output's sources only; same PASS/FAIL contract |
| "Done" | A review score | A check script per job (`*_check.py`, "done is its verdict, never yours") | Keep the check scripts; they are the best thing in the toolbox |
| Files per job to keep in sync | 1 (`AGENTS.md` per repo) | 5 to 12: orchestrator, 1 to 8 specialists, workstream skill, method or contract file, sidecar, overlay entry, Automation `SKILL.md` | 4: main agent, job skill, sidecar, overlay entry (the sidecar and overlay could merge later) |
| Sentinel wiring | none | `agent:` in the sidecar, an overlay entry (68 of them, 18 `no-github`), `subagents:` lists, extra tool grants per sub-agent, prepare/finish commands | the same sidecar; the overlay shrinks to transport, model, folder and network; plus a per-Run `--plugin-dir` built from `skills:` |
| Context per session at start | the repo's `AGENTS.md` and 6 skill descriptions | agent body + `AGENTS.md` rules + the `--agents` definitions of every dispatchable agent (one orchestrator carries 9) + skills read by hand | agent body + `AGENTS.md` rules + the listing of its own skills (a few hundred tokens) + two shared agent definitions |
| What it gives up | Independence of review inside the loop (the builder proves its own work); unattended running; finance-grade state | Simplicity: a change to a rule touches three layers; `skills:` does nothing; a sealed session re-reads skills by path | Sonnet-tier specialists (a `worker` brief can name a model, since the Agent tool takes one); the per-job reviewer's domain prompt (moved into the skill's checklist) |

The guest's design and the owner's agree on more than the owner's notes suggest: both keep the
workflow out of the code description, both insist on proof, both loop on a reviewer's verdict.
The owner's is stricter where it should be (no GitHub while agents work, computed done, a
reviewer that never sees the maker's reasoning). The difference is layers, not principles.

## 4. What to keep, what is overhead

### Keep

- **Computed "done"** (`firm_billing_check.py`, `software_factory_check.py`,
  `daily_plan_check.py`, ...; 57 skills ship scripts, 404 scripts, 143 test files). This is the
  toolbox's real asset and it survives any agent layout unchanged.
- **Prepare and finish in code, not in the model** (25 Automations with `prepare:`, 19 with
  `finish:`): the pull before, the ship or apply after. Writes to live systems happen in a script
  the owner can read. Keep as is.
- **Independent review for money and client-facing work.** The firm-billing reviewer re-derives
  every line from `BILLING.yaml` and the pull; the factory's tester and reviewer never see the
  builder's reasoning. Keep the principle; share the agent (section 5).
- **Least-privilege tool lists and the Bash guard.** Only 6 of 204 agents hold bare `Bash`;
  rules name one script each. Keep.
- **`network: no-github` sessions and the sync/ship split** for the factory (ADR 0013).
- **`orchestration-workstream`** as the one shared conduct and return contract. It is 70 lines
  and every worker needs exactly it.
- **Contexts, rules files and the "no client facts in the repo" line.** Nothing here changes.

### Overhead

- **Thin specialists.** 40 agents are 20 lines or fewer; the median body is 32 lines; 170 of 204
  carry a `skills:` list that does nothing at run time. `firm-billing-preparer` is 17 lines of
  "read the rules, then do what `firm-billing-workstream` says". The five
  `nightly-sweep-*` workers are 19 lines each. These are skill sections wearing frontmatter.
- **The same rule in three places.** "Already done?", "no bookkeeping", "one command per call",
  "read the skill at its path if it is not loaded" appear in `orchestration-workstream`, in the
  domain `-workstream` skill and in each agent body (138 files carry the "not loaded" sentence;
  22 carry "no bookkeeping"). A change to one rule is three edits per job.
- **66 of 153 skills (43%) describe themselves as "Reference loaded by X, not for a user
  request".** They exist to be read by an agent and should never be in an interactive listing.
  Today they are, and they crowd out the 87 skills a person might type.
- **Orchestrators that orchestrate little.** Counting the other agents each orchestrator's
  body names, 22 of 68 name three or fewer, and those usually include cross-references to
  other orchestrators ("not for X; use Y"). `email-reply-orchestrator` is 11 lines. Four shared
  reviewers (`numbers-reviewer`, `fact-check`, `executive-red-team`, `completeness-audit`) are
  already named by 35 orchestrators, which shows a shared reviewer works in practice.
- **Per-agent exact script paths** (134 distinct paths in tool rules, each also in the sidecar
  twice) tie every file to `~/.claude/skills`, the one place skills must not live.
- **Two software factories.** `software-orchestrator` (38 lines, `gh issue`, `gh pr` and `git`
  inside the session, one script, six 20-line workers) and `software-factory-orchestrator`
  (offline, sync and ship in code, ledger, computed verification, seven scripts with tests,
  tester separate from reviewer, `no-github`). Both have a live Automation. The first breaks the
  "no route to GitHub while agents work" invariant that the second was built to keep.
- **The `--agents` payload.** An orchestrator's session carries the full definition of every
  agent it may dispatch (`chief-of-staff-cycle-orchestrator`: nine). With bare `Agent` and no
  `subagents:`, `subagent_names` sends every toolbox agent in the roster.

## 5. The slimmed design

### The rule

One **main agent per recurring job**, where a job is what one Automation launches: the same
folder or repo, the same rules file, the same cadence. Two jobs merge when they share a folder
and a rules file. A main agent is: an opening sentence, `## Goal`, `## Inputs`, `## Done`
(the check script), `## Never`, `skills:` and `tools:`. It works to the goal itself. Its
specialists become `##` sections of the job's skill (`<job>-workstream` or `<job>-method`,
one per job, the two families merged), each section with the brief it needs and the return
shape. Dispatch happens in exactly two cases:

1. **Independence.** The output must be judged by someone who did not make it: dispatch
   `reviewer` with the skill's checklist section, the output and its sources, never the
   reasoning. One agent for the whole toolbox, about 40 lines: "You judge from the sources
   alone; walk the checklist you were given; PASS or FAIL with numbered fixes; edit nothing."
   It takes a model in the brief (`fable` for a sign-off, `opus` otherwise).
2. **Parallel or isolated context.** Several slices at once (one builder per issue in its own
   worktree; one preparer per three contracts), or a slice whose reading would flood the main
   context (five sweep phases over a day of mail): dispatch `worker` with the section name, the
   inputs and the return block. One agent for the toolbox, under 30 lines, holding
   `orchestration-workstream` conduct.

Sub-agent calls are already checked against the session's allowlist, so `worker` and
`reviewer` need no tool lists of their own; the session's rules bound them.

### The count

| Department | Today (agents / orchestrators) | Main agents proposed | How they merge |
|---|---|---|---|
| accounting | 22 / 9 | 5: `month-end`, `billing-and-collections`, `accounting-questions`, `audit-support`, `product-costing` | firm-books and intercompany are close variants, so sections of `month-end`; firm-billing and collections share the O2C folder; vendor-1099 becomes a season of `compliance` |
| finance | 13 / 5 | 2: `forecast` (forecast, budget, cash forecast as modes of one Forecast folder), `analysis` | investor-posting joins `board-package` |
| reporting | 16 / 3 | 2: `board-package`, `weekly-report` (leadership weekly and client update as two outputs of the same week's record) | |
| projects | 13 / 5 | 2: `client-delivery` (plan, health, kickoff, closeout as stages of one engagement), `tech-portfolio` | |
| productivity | 39 / 13 | 5: `comms` (reply, follow-ups, clerical routing, relationship tending: all staged drafts checked by one draft check), `meetings` (prep and transcripts), `task-stack` (capture, clarify, reconcile), `crm-hygiene`, `weekly-review` (with the time study) | calendar-steward joins `daily-plan` |
| recurring-summaries | 11 / 2 | 2: `daily-plan`, `nightly-sweep` | |
| process-engineering | 12 / 6 | 3: `discovery` (intake, synthesis, survey, workshop), `process-flow`, `automation-scoping` | |
| sales | 6 / 3 | 1: `bd` (pipeline, lead intake, proposal) | |
| compliance | 8 / 3 | 2: `compliance` (calendar, 1099, wind-down), `it-governance` | |
| personal | 11 / 5 | 2: `household` (household, home infrastructure, health routine), `personal-finance` (review and tax season) | |
| software | 20 / 5 | 4: `software-factory`, `issue-harvest`, `software-release`, `software-portfolio-review` | see below |
| strategy, decision-playbooks, chief-of-staff, learning, marketing, toolbox-maintenance | 5+3+8+4+4+8 / 1+1+1+2+2+2 | 6: one each (`goal-alignment`, `playbook`, `chief-of-staff`, `learning`, `marketing`, `toolbox-audit`) | skill-harvest is a mode of `toolbox-audit`; content-scout is a skill run through `worker` |
| shared | 4 reviewers used by 35 orchestrators | 2: `reviewer`, `worker` | `numbers-reviewer`, `fact-check`, `executive-red-team`, `completeness-audit` become four checklist skills the one `reviewer` is briefed with |
| **Total** | **204 / 68** | **38** | |

Thirty-six main agents is still many files, but each is short and each maps one to one to an
Automation, which is the number the owner already manages (71). Where a main agent has modes
(forecast: reforecast, budget, cash), the Automation's inputs pick the mode, as the factory's
`factory_mode` does today. If 36 still feels like too many, the next merges are
`accounting-questions` into `month-end` and `audit-support` into `compliance`; past that, merges
start joining folders that different clients own, which the Context model is there to keep apart.

### The software department, worked

Keep `software-factory-orchestrator`'s design. It is the one that matches both the owner's
invariant (no GitHub in the session; `software_factory_sync.py` before, `software_factory_ship.py`
after) and the guest's lessons (reproduce before fixing, evidence in the Run folder, a tester
and a reviewer that never see the builder's reasoning, a cap of two fix rounds). Take two things
from `software-orchestrator` before retiring it: the `max_builds`/`max_plans`/`max_triage` knobs
on the form, and `issue-planner`'s "plan before build" as a section for issues above a size.

| Today (20 agents) | Becomes |
|---|---|
| `software-factory-orchestrator` | main agent `software-factory` (about 50 lines: goal, inputs, the five "ready to ship" conditions, done = `software_factory_check.py`, never) |
| `software-factory-triager` | section "Triage" of `software-factory-workstream`, run by the main agent itself (it is reading and classifying; a `worker` brief if a model tier matters) |
| `software-factory-builder` | section "Build", dispatched to `worker`, one per issue, each in its own worktree (parallel and isolated: a real reason to dispatch) |
| `software-factory-tester` | section "Test", dispatched to `worker` with the issue and the diff only (independence) |
| `software-factory-reviewer`, `pr-reviewer` | the `software-review` skill's checklist, dispatched to `reviewer` |
| `software-factory-lookback` | section "Look back", a mode of the main agent |
| `software-orchestrator`, `issue-triager`, `issue-planner`, `issue-builder`, `pr-fixer` | retired; the planner's step and the form knobs move into the factory |
| `repo-steward` (117 lines, used by portfolio review) | section of `software-portfolio-review`'s skill, run through `worker` per repo |
| `issue-harvest-orchestrator`, `-analyst`, `-checker` | main agent `issue-harvest`; the analyst is a section; the checker is `reviewer` with the harvest checklist |
| `software-release-orchestrator`, `-writer`, `-checker` | main agent `software-release`; same pattern |
| `software-portfolio-review-orchestrator` | main agent `software-portfolio-review` |

Skills: 19 become about 16. `software-issue-loop` goes; `software-factory-workstream` grows the
four sections (and keeps `SOFTWARE-FACTORY.md` and `onboard.md`); `software-review` holds the
reviewer's checklist. `software-verify`, `software-pr`, `unslop-*` and the rest are unchanged.
Two Automations become one (`software-factory`); the overlay keeps `network: no-github`.

### Keeping 100+ skills out of everyday sessions: the mechanism

1. **Unlink.** `rm ~/.claude/skills` (it is one link to the merged folder). `link.py` keeps
   building `~/.local/share/f3i-toolbox/{agents,skills}`; change the two lines it prints so it
   no longer suggests the link. After this a plain `claude` anywhere lists only Claude Code's
   built-ins and the claude.ai-synced skills; the system prompt drops by about 8,000 tokens;
   `/skill-doctor` shows no toolbox entry.
2. **Repoint the script paths once.** Replace `~/.claude/skills/` with
   `~/.local/share/f3i-toolbox/skills/` in the 288 toolbox files (a scripted rewrite; the
   pre-commit check can refuse the old prefix afterwards), in the 68 overlay entries and in the
   sidecars that repeat the rules. Set `skills_dir: ~/.local/share/f3i-toolbox/skills` in
   Sentinel's `config.yaml` so `{skills_dir}` and `read_roots` follow. The guard matches the
   literal string, so one stable path outside Claude Code's discovery is exactly what is needed;
   `CONTEXT.md`'s "Loading a skill by name" entry changes its path and nothing else. Nothing is
   installed and nothing moves; only the name of the folder changes.
3. **Headless: Sentinel hands a session its skills.** In `model_claude_code.py`, for a working
   session, write `<tmp>/skills-plugin/.claude-plugin/plugin.json` (`{"name": "run"}`) and one
   link per name in the agent's `skills:` under `skills/`, pass `--plugin-dir <tmp>/skills-plugin`,
   and allow the `Skill` tool. The probe shows a sealed session then lists `run:<skill>` with its
   description and loads the body on invocation. Pass `skills` through `subagent_definition` as
   well, so `worker` and `reviewer` get the sections preloaded. The deny rules for Sentinel's temp
   folder must leave this one folder readable. About 40 lines and a test; the "read it at its
   path" fallback keeps working meanwhile.
4. **Interactive, per project.** Where the owner works by hand (a repo, the canon), either
   `.claude/skills/` with links to the handful of skills that place uses (the same link
   mechanism, project scope), or one plugin per department built by `link.py --plugins`
   (`plugins/<department>/.claude-plugin/plugin.json`, `skills/`, `agents/`; a
   `marketplace.json` at the toolbox root so `claude plugin install software@f3i-toolbox`
   works) and `enabledPlugins: {"software@f3i-toolbox": true}` in that project's
   `.claude/settings.json`. A session in a software repo then sees the software skills and
   agents; a session in the home folder sees none. Plugins also make `claude --agent
   software-factory` work interactively, which nothing does today (`~/.claude/agents` does not
   exist on this machine).

What the owner would see afterwards: a normal session with the built-in listing only; in a repo
with the department plugin on, that department's skills named `software:software-verify`; a
Sentinel Run page whose session lists exactly the agent's `skills:`.

### Migration path and trials

A rule for the shape of a job:

| The job | Shape | Sentinel wiring |
|---|---|---|
| Reads, decides, writes a draft or a change set; a script computes done; nobody's money or name is on the output | one main agent + one skill, no dispatch | sidecar `agent:`; the overlay's transport, model, folder; prepare/finish as today |
| The output is an invoice, a close, a board figure, a client-facing message, a PR | the same, plus `reviewer` before "done" | add `reviewer` to the overlay's `subagents:` and `Agent` to tools |
| Several independent slices (issues, contracts, repos, phases) or a slice too big to read inline | the same, plus `worker` per slice | add `worker` likewise; the session's allowlist is the union, as now |

Trial first, in this order:

1. **`daily-plan`** (routine, twice a weekday, has a pull, a publish and a check script; today 7
   agents named): one main agent, one skill with the planner's and closer's sections, no dispatch.
   Proves the simplest shape and the per-Run plugin folder.
2. **`firm-billing`** (monthly, money, a reviewer, a computed done): main agent + `worker` per
   three contracts + `reviewer` with the billing checklist. Proves a shared reviewer holds the
   finance bar.
3. **`software-factory`** merged with `software-orchestrator`: main agent + `worker` builders and
   testers + `reviewer`, `no-github`. Proves parallel isolation and the overlay shrink.

Measure per Run, before and after, from the trace (it already records tokens, turns, time and
corrections per model call): input and cache tokens at the first turn (the startup context),
total tokens, turns, wall time, the check script's verdict, reviewer FAIL rounds, corrections,
and the files touched to make one rule change (count them). The toolbox's own
`toolbox-audit` can count the agents, skills and path references as they fall.

Order of work: unlink and repoint paths (one afternoon, mechanical, reversible); the Sentinel
plugin-dir change; the three trials; then department by department, software first, retiring
each orchestrator and its specialists on the day its main agent passes its check script on a
dry run and a live run.

## 6. Risks and open questions

- **Namespacing.** Plugin skills are listed as `plugin:skill`. Whether an agent's `skills:` entry
  must be written `run:software-verify` to preload under a `--plugin-dir`, and whether
  `Skill(software-verify)` permission rules match the namespaced name, is not in the docs. One
  probe settles it before the Sentinel change.
- **The deny rules.** Sentinel denies the session its own temp folder; the plugin folder must be
  carved out, and the guard's private-path check must not refuse the listing's reads.
- **`--bare` is not usable here.** The probe with `--bare` answered "Not logged in". Sentinel's
  `--setting-sources ""` plus `--settings` is the right seal; do not switch to `--bare`.
- **Independence lost by accident.** Dissolving the tester into the builder's session would
  recreate the guest's weakness (the maker proving its own work). The rule in section 5 keeps the
  tester and the reviewer in fresh contexts; review the first factory Runs for this.
- **Model tiers.** 19 agents run on sonnet, 3 on haiku, by frontmatter. With `worker` the tier
  goes in the dispatch (the Agent tool takes a model), so the skill section must say which tier
  its slice earns, or the saving is lost to opus everywhere.
- **The rewrite touches 893 occurrences.** It is mechanical but it crosses the public toolbox,
  the private overlays and the sidecars at once; the pre-commit check and `sentinel doctor`'s
  "script exists with `{skills_dir}` filled" check will catch misses. Claude Desktop runs the
  Automation `SKILL.md` as is and reads no sidecar, so Desktop compatibility is unaffected.
- **Interactive `--agent` after unlinking.** It needs agents discoverable: the department plugin
  or a project `.claude/agents`. Until plugins exist, `claude --agents <file>` built by `link.py`
  is the workaround.
- **Merging jobs across clients.** `client-delivery` and `weekly-report` run for several
  engagements today as separate Automations with separate Contexts. Merging agents is fine;
  merging Automations is not, since each Context names a different client folder. Keep one
  Automation per client, one agent for all.
- **Not verified:** the cost delta on the owner's usual interactive model (the probe ran haiku,
  1M context; on a 200k model the budget and the delta are smaller, about 2,000 tokens of
  listing, but the descriptions dropped are more); whether a linked skill folder under a
  `--plugin-dir` plugin is followed (the probe used a real folder); whether 36 main agents is
  the right count rather than 30 or 45, which the trials should decide, not this review.

## The owner's decisions (2026-10-11)

Taken after reading this review; they amend its recommendation where they differ.

1. **Departments are standalone buckets.** Each department holds its own main agents, its own
   reviewer and its own skills, and is switched on as one unit (a plugin). No agent or skill is
   shared across departments, with the one exception in decision 3.
2. **One reviewer per department, not one shared reviewer.** For example `software-reviewer`
   and `accounting-reviewer`, each in its own department's `agents/`, with a fresh context and
   briefed with the job's checklist from that department's skill.
3. **One small `core` bucket** holds what nearly every department uses: the house rules
   (`orchestration-workstream`), putting tasks on the owner's list (`task-stack-workstream`),
   `office-files`, the `unslop` writing cleaners, and asking the owner or checking a draft
   (`comms-confirm`, `comms-draft-check`). Every department depends on it; it is the only
   dependency allowed.
4. ~~Finance and accounting merge.~~ **Withdrawn the same day: finance and accounting stay
   separate buckets.**
5. **Truly standalone buckets are preferred over a shared core** (leaning, not final). The owner
   would rather duplicate a shared skill into each bucket that uses it than have any bucket
   depend on another, which puts decision 3's `core` bucket in question. Undecided: how to keep
   duplicated copies from drifting (by hand, or one source that a build step copies into each
   bucket and a check keeps identical).
6. **One software factory.** `software-orchestrator` and its issue-loop agents are retired in
   favour of `software-factory-orchestrator`; whether that factory keeps `network: no-github`
   is under review.

7. **One lightweight main agent per job (option A), with the know-how in skills.** A job is
   what one Automation runs (accounting has nine: month-end, billing, collections, firm books,
   intercompany, costing, audit support, questions, 1099s, before any merging). Its agent is
   short: the goal, the inputs, what "done" means, its tools and the skills it loads. The
   procedure, checklists and formats live in skills fed to it through `skills:`.
8. **Scripts become named commands in each department plugin's `bin/`** (recommended after the
   probe below; the owner's call). Skills say `firm-billing-pull ...` instead of a path, and an
   agent's tool list allows `Bash(firm-billing-pull:*)`.

### Probe results: how a plugin skill reaches its scripts (2026-10-11)

A throwaway plugin (one skill, one script, one `bin/` command, one agent with `skills:`), run
with Claude Code 2.1.296 on haiku, sealed as Sentinel runs (`--setting-sources ""`,
`--plugin-dir`, `--permission-mode dontAsk`):

| How the skill calls its script | Runs? | Can a permission rule name it? |
|---|---|---|
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/hello/scripts/hello.py` | yes; replaced by the absolute path before the model sees the skill | only by that machine's absolute path; the variable is not expanded inside a rule (the call was denied) |
| `python3 ${CLAUDE_SKILL_DIR}/scripts/hello.py` | yes; same | same |
| `demo-hello` from the plugin's `bin/` | yes; the plugin's `bin/` is on PATH | yes, `Bash(demo-hello:*)` as written |

Also seen: `--agent demo:greeter` and `--agent greeter` both start the plugin's agent; its
`skills: [hello]` delivered the skill (listed as `demo:hello`); the sealed session listed only
the plugin's skill and Claude Code's built-ins, none of the 152 toolbox skills.

Still open:

- **Cross-bucket skills generally** (21 today; see decision 5): duplicate, or a core bucket.
- **Reporting** also uses accounting's `month-end-workstream`, `month-end-flux` and
  `erp-ledger-pull`. Under decision 1 it either joins the finance bucket, or those skills
  move or are split.
- **Smaller overlaps:** projects and strategy use productivity's `calendar-steward-method`;
  projects and reporting use process-engineering's `transcript-tools`. Each is either a core
  utility or moves to one department.
- **The agent count** in this review assumed one shared reviewer. With one reviewer per
  department, it is roughly 38 main agents plus one reviewer per department that needs one,
  about 50 in all, down from 204.
