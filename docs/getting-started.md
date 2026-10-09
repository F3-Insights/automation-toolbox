# Getting started

This guide takes you from a fresh clone to a working skill in a few minutes, then to a full workflow with sub-agents and a checker, then to the settings that let the bigger workflows run on your own folders. Read [CONTEXT.md](../CONTEXT.md) alongside it for the vocabulary.

## What you need

- [Claude Code](https://claude.com/claude-code), signed in.
- Python 3.11 or later, for the scripts the skills run.
- Git.
- For some pieces only: a web search tool, Sage Intacct API access, the GitHub CLI, or the Insights Portal MCP server. Each department README's "Needs" column says which.

## 1. Install the toolbox

```bash
git clone https://github.com/F3-Insights/automation-toolbox.git
cd automation-toolbox
git config core.hooksPath .githooks
python3 setup/link.py
```

`setup/link.py` builds `~/.local/share/f3i-toolbox`: one flat folder of links back into your clone, the shape Claude Code reads. It prints the commands that point `~/.claude/skills` and `~/.claude/agents` at that folder. Run them yourself; they move your current folders to a dated backup first. The [README's Install section](../README.md#install) explains each step and how to undo it.

Check it worked:

```bash
ls ~/.claude/skills | head        # skill folders, each a link into the clone
ls ~/.claude/agents               # one folder per department
```

## 2. Run your first skill

Skills that need nothing beyond Claude Code are the quickest way to see what the toolbox does. Open Claude Code anywhere and try the editing skills from [marketing](../marketing/):

> Use the unslop-email skill on this draft: *paste an email you were about to send*

> Use the unslop-technical skill on this README: *paste a README or design doc*

`unslop` itself is a router: give it any text and it picks the right editing pass for the reader (an email, a client deliverable, a proposal, an editorial piece or technical writing).

## 3. Run a full workflow: a pre-mortem

The [strategy](../strategy/) department's `pre-mortem` shows the whole pattern at small scale: an orchestrating skill, two sub-agents, two approval gates, and a written brief at the end. It needs only a web search tool.

1. In a working folder for a company (a git repository is ideal), create the knowledge base from the fictional examples the skill ships with:

   ```bash
   mkdir -p context initiatives/new-plant
   for f in ~/.claude/skills/pre-mortem/context-examples/*.example.md; do
     cp "$f" "context/$(basename "$f" .example.md).md"
   done
   ```

2. Write the plan you want stress-tested in `initiatives/new-plant/plan.md`, and its numbers (costs, volumes, timing) in `initiatives/new-plant/quant-inputs.yaml`.

3. Start Claude Code in that folder and ask:

   > Run a pre-mortem on the new-plant initiative.

The skill dispatches `pre-mortem-investigator` to surface the plan's stated, implied and missing assumptions, then stops at **Gate 1** for you to approve them. Next it dispatches `pre-mortem-researcher` for sourced outside evidence, writes the kill-shot risks and a decision brief, and stops at **Gate 2** for your decision. It is resumable: leave at either gate and ask again later, and it picks up from the files it has written.

Replace the fictional `context/` files with your own company's before relying on the result.

## 4. Add your settings

The larger workflows read your folders, thresholds and connections from one file, `~/.config/f3i-toolbox/settings.toml`. A skill whose setting is missing says what it needs and stops, so you can add settings as you adopt pieces.

[docs/settings.md](settings.md) lists every key with its default and the skills that read it, plus an example file. Secrets (API keys, tokens) never go in the file: the scripts read them from environment variables only.

Each workflow also reads a **rules file** you keep beside the work, such as `MONTH-END-RULES.md` for a close or `FORECAST-RULES.md` for a forecast. The skill that owns the workflow says what the rules file must contain.

## 5. Run an orchestrator

Orchestrators are agents. Run one as the main session:

```bash
claude --agent cash-forecast-orchestrator
```

or ask for it by name in an open session. Each orchestrator works in a **Run** folder: it gathers, plans, builds, has a checker review the result against its sources, and delivers drafts plus a **change set** of proposed writes. Nothing touches a live system until you approve the change set and its finish step applies it.

To run a workflow on a schedule, wrap it in an **automation**: a prepare step that runs the skill's scripts before the session (pulling data, picking a queue), the session itself, and a finish step that applies the approved change set. Any scheduler can do this; [CONTEXT.md](../CONTEXT.md) describes the contract.

## 6. Where to go next

| If you are | Start with |
|---|---|
| A controller or fractional CFO | [accounting](../accounting/) (`month-end-orchestrator`), [finance](../finance/) (`cash-forecast-orchestrator`), [reporting](../reporting/) (`board-package-orchestrator`) |
| An operations or process consultant | [process-engineering](../process-engineering/) (`discovery-synthesis-orchestrator`, `process-flow-orchestrator`) and [projects](../projects/) (`client-delivery-orchestrator`) |
| Running a small firm | [productivity](../productivity/), [recurring-summaries](../recurring-summaries/) and [chief-of-staff](../chief-of-staff/) (these expect the Insights Portal) |
| An engineer | [software](../software/) (`software-factory-orchestrator`) and the `orchestrator-scaffold` skill, then [templates/](../templates/) to write your own |

## Checking your own changes

```bash
python3 scripts/toolbox_check.py                    # structure, names, frontmatter, secrets
.venv/bin/python scripts/run_tests.py <department>  # the scripts' tests
```

The tests need a virtual environment with `pytest`, `pyyaml`, `pypdf`, `openpyxl`, `python-docx` and `python-pptx`. See [CONTRIBUTING.md](../CONTRIBUTING.md) before you open a pull request.
