# Decision Playbooks

Writes down how the owner decides, so people and agents can follow it. A **playbook** is a short set of rules for how the owner decides one category of matter (spend approvals, scoping, delegation), each rule cited to real decisions; it becomes the owner's rule only when the owner ratifies it. The method mines the owner's real decisions from their sent mail into cases, harvests the recorded narrations in which they explain their reasoning, distills both into a cited playbook proposal with the conflicts between what they say and what they do on top, and puts it to the owner a few questions at a time. A weekly pass keeps one ratification packet waiting and the pipeline topped up; nothing it writes is ratified until the owner says so.

The playbook folder, the ratification queue, the decision store and the recordings are the owner's; they are named by settings, never written here.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `playbook-orchestrator` | Weekly pass: one ratification packet, re-surfaced while unanswered; mines and distills only when the queue runs short | Insights Portal, `PLAYBOOK-PIPELINE-RULES.md`, settings `playbooks_dir`, `ratification_queue` |
| `decision-case-miner` | Finds the owner's decisions in one batch of sent mail and writes them as cited cases | Insights Portal |
| `playbook-distiller` | Turns one category's cases into a cited playbook proposal with conflicts, gaps and a risk tier | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `playbook-workstream` | The unattended loop: the playbook folder's shape, what may be written, packet and proposal shapes, DONE checklist | `PLAYBOOK-PIPELINE-RULES.md` |
| `decision-case-mining` | Mines sent mail into decision cases; owns the decision store | Insights Portal, setting `[decision-case-mining] database` |
| `playbook-distilling` | Distills one category's cases and narration into typed, cited bullets | the decision store, setting `playbooks_dir` |
| `playbook-ratification` | The owner's ratification session: menu, focused questions, verdicts kept, promotion, index rebuilt | setting `playbooks_dir` |
| `recording-harvest` | Harvests recording transcripts (Loom today), then triages and classifies them for distilling | settings `[recording-harvest] video_list`, `archive_dir`; `LOOM_COOKIES_FILE` for private videos |

`playbook-workstream` builds on `orchestration-workstream` (software). The orchestrator also uses, by name: `fact-check` (reporting) and `task-stack-workstream` (productivity), whose `task_stack_apply.py` files the ratification task after a Run.

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. Standard library only.

**`decision-case-mining`**
- `decision_store.py`: the SQLite store of sources, cases, playbooks and bullets; refuses an uncited case or bullet; `audit` is the provenance check, `export-playbook` renders a draft for review.

**`playbook-ratification`**
- `playbook_index.py`: rebuilds the playbook folder's `INDEX.md` from the frontmatter of its playbooks, policies, drafts and briefs.

**`recording-harvest`**
- `loom_harvest.py`: downloads Loom transcripts and captions (never video) into the archive and registers each as a `recording` source in the decision store.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `playbooks_dir`: the owner's playbook folder. Read by the agents and skills, and by `playbook_index.py` when no folder is passed.
- `ratification_queue`: the ratification queue file; default `meta/RATIFICATION-QUEUE.md` inside the playbook folder. Read by the agents and skills.
- `[decision-case-mining] database`: the decision store's SQLite file; `--db` overrides it.
- `[playbook-ratification] function_labels`: optional table of function folder to heading, in index order.
- `[recording-harvest] video_list` and `archive_dir`: the recording source list and where transcripts are kept; `--videos` and `--archive` override them.
- `LOOM_COOKIES_FILE`: path to a cookies.txt exported from a signed-in Loom tab, for private videos; `--cookies` overrides it. A credential: keep it out of every repository.
- Python 3.11 or later.

## Needs

The Insights Portal for mining sent mail. The owner keeps, outside this repository, the playbook folder with its ratification queue and briefs, the pipeline rules file `PLAYBOOK-PIPELINE-RULES.md` (open-item threshold, queue order, mining window and category rotation, cap on cases per Run, how long a packet stands, where the ratification task goes), the decision store and the recording archive. Both the store and the archive hold the owner's own words; keep them in the owner's backup.
