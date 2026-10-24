# Decision Playbooks

Writes down how the owner decides, so people and agents can follow it. A **playbook** is a short set of rules for how the owner decides one category of matter (spend approvals, scoping, delegation), each rule cited to real decisions; it becomes the owner's rule only when the owner ratifies it. The method mines the owner's real decisions from their sent mail into cases, harvests the recorded narrations in which they explain their reasoning, distills both into a cited playbook proposal with the conflicts between what they say and what they do on top, and puts it to the owner a few questions at a time. A weekly pass keeps one ratification packet waiting and the pipeline topped up; nothing it writes is ratified until the owner says so.

The playbook folder, the ratification queue, the decision store and the recordings are the owner's; they are named by settings, never written here.

## The plugin

This folder is a standalone Claude Code plugin named `decision-playbooks` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent, one worker and one reviewer, the know-how in the skills as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py decision-playbooks`).

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/decision-playbooks --agent decision-playbooks:decision-playbooks-curator
```

## Jobs and agents

| Agent | Automation | What it does |
|---|---|---|
| `decision-playbooks-curator` | knowledge-doctrine | Weekly pass: one ratification packet, re-surfaced while unanswered; mines, distills and has the proposal checked only when the queue runs short |
| `decision-playbooks-worker` | | One batch of sent mail mined into cited decision cases (section Mine one batch), written to one file |
| `decision-playbooks-reviewer` | | Independent PASS or FAIL on a proposal's bullets against the cases, by section Check the proposal and the `review-facts` checklist; edits nothing |

The owner's own sessions use the method skills by hand: `decision-case-mining`, `playbook-distilling`, `recording-harvest` and `playbook-ratification`. They write the decision store and the ratified folders, so they stay owner-started; the curator's Never list forbids those paths.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `playbook-workstream` | curator, worker, reviewer | The unattended loop's Steps; sections Mine one batch, Distill one category, Check the proposal; the packet and proposal shapes; the DONE checklist |
| `decision-case-mining` | the owner; the worker | Mining sent mail into cases; owns the decision store |
| `playbook-distilling` | the owner; the curator | Typed, cited bullets at their earned altitude, conflicts, risk tier |
| `playbook-ratification` | the owner | The ratification session: menu, focused questions, verdicts kept, promotion, index rebuilt |
| `recording-harvest` | the owner | Harvests recording transcripts (Loom today), then triages and classifies them |
| `review-facts` | reviewer (shared copy) | The facts checklist |
| `task-stack-workstream`, `orchestration-workstream` | curator, worker (shared copies) | The change set for the ratification task; the conduct and return block |

## Commands

In `bin/`, each prints `--help`; standard library only:

- `decision-playbooks-decision-store`: the SQLite store of sources, cases, playbooks and bullets; refuses an uncited case or bullet; `audit` is the provenance check, `export-playbook` renders a draft for review.
- `decision-playbooks-playbook-index`: rebuilds the playbook folder's `INDEX.md` from the frontmatter of its playbooks, policies, drafts and briefs.
- `decision-playbooks-loom-harvest`: downloads Loom transcripts and captions (never video) into the archive and registers each as a `recording` source in the decision store.
- The shared copy's commands keep one unprefixed name: `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report`.

## The knowledge-doctrine Automation

- Session: `decision-playbooks-curator`, subagents `decision-playbooks-worker` and `decision-playbooks-reviewer`.
- Finish (proposed): `task-stack-apply --run RUN --dry-run-if=DRY` files the ratification task, under the `portal-tasks` lock. Mined case files stay in the Run folder until the owner loads them with `decision-playbooks-decision-store add-case --file`.

## Decisions taken in the conversion

- The fact-check stays, as `decision-playbooks-reviewer` with the shared `review-facts` checklist (plan open question 2): it is the department's only independent check.
- `recording-harvest` stays an owner-started skill, not a mode of the curator: Loom cookies and downloads in an unattended Run are a risk the owner has not taken on.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `playbooks_dir`: the owner's playbook folder. Read by the agents and skills, and by `decision-playbooks-playbook-index` when no folder is passed.
- `ratification_queue`: the ratification queue file; default `meta/RATIFICATION-QUEUE.md` inside the playbook folder. Read by the agents and skills.
- `[decision-case-mining] database`: the decision store's SQLite file; `--db` overrides it.
- `[playbook-ratification] function_labels`: optional table of function folder to heading, in index order.
- `[recording-harvest] video_list` and `archive_dir`: the recording source list and where transcripts are kept; `--videos` and `--archive` override them.
- `LOOM_COOKIES_FILE`: path to a cookies.txt exported from a signed-in Loom tab, for private videos; `--cookies` overrides it. A credential: keep it out of every repository.
- Python 3.11 or later.

## Needs

The Insights Portal for mining sent mail. The owner keeps, outside this repository, the playbook folder with its ratification queue and briefs, the pipeline rules file `PLAYBOOK-PIPELINE-RULES.md` (open-item threshold, queue order, mining window and category rotation, cap on cases per Run, how long a packet stands, where the ratification task goes), the decision store and the recording archive. Both the store and the archive hold the owner's own words; keep them in the owner's backup.
