# Training & Community

Building and delivering teaching: business-led AI seminars, workshop and lab decks built as self-contained HTML, and the running of a peer learning community that meets on a cadence (agenda, invitation, recap). For a practice that teaches executives and teams how to put AI to work.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `learning-seminar-orchestrator` | Builds or revises one seminar, workshop or lab deck in passes: outline and questions, then build, verify and red-team | setting `training_dir`; agent `executive-red-team` |
| `seminar-builder` | Runs one pass of the seminar method (outline, build or revise) and verifies the deck in a browser | Playwright MCP server; setting `training_dir` |
| `learning-community-orchestrator` | Prepares a community session (agenda, invitation draft) and recaps it from the recording, fact-checked | Insights Portal; agents `email-drafter`, `meeting-analyst`, `fact-check` |
| `community-writer` | Writes one session's agenda, invitation, recap, record and topic proposals | setting `voice_guide` |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `writing-seminar-builder` | The seminar method: interview, content map, outline gate, HTML deck from the slide library, Playwright checks, executive red team. Holds the deck kit, slide types, elements, the hands-on lab kit and the teaching style | setting `training_dir`; Playwright MCP server |
| `community-workstream` | What is specific to running a learning community's sessions: rules file, member-chosen topics, staged invitation, recap traced to the transcript, DONE checklists | a `COMMUNITY-RULES.md` per group |

Both skills extend `orchestration-workstream` (software department). The seminar skill's voice section also uses `brand-guide` (marketing department).

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`writing-seminar-builder`** (the older PowerPoint pipeline; the HTML deck needs none of them)
- `deckbuilder.py`: python-pptx layout primitives for seminar slides, imported by a build script.
- `flowkit.py`: flowchart primitives for seminar decks, built on `deckbuilder.py`.
- `render_previews.py`: renders each slide of a generated .pptx to a PNG preview.

These three need `python-pptx` and `pillow`. Planned and not yet written: `seminar-check` (`writing-seminar-builder`), `community-pack` and `community-check` (`community-workstream`). The `training_dir` and `voice_guide` settings in the tables above are read by the agents, not by a script.
