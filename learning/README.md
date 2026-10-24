# Training & Community

Building and delivering teaching: business-led AI seminars, workshop and lab decks built as self-contained HTML, and the running of a peer learning community that meets on a cadence (agenda, invitation, recap). For a practice that teaches executives and teams how to put AI to work.

## The plugin

This folder is a standalone Claude Code plugin named `learning` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job and one `learning-reviewer`, the know-how in the jobs' skills as `##` sections. Neither job needs parallel or isolated slices, so there is no worker; there are no scripts, so no `bin/`.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/learning --agent learning:learning-seminar-builder
```

## Jobs and agents

| Agent | Automation | What it does | Needs |
|---|---|---|---|
| `learning-seminar-builder` | learning-seminar | Builds or revises one seminar, workshop or lab deck in passes: outline and questions, then build, verify in Playwright and red-team | setting `training_dir`; Playwright MCP server |
| `learning-community-host` | learning-community | Prepares a community session (agenda, one staged invitation draft) and recaps it from the recording, fact-checked | Insights Portal; a `COMMUNITY-RULES.md` per group; setting `voice_guide` |
| `learning-reviewer` | | Independent PASS or FAIL: a recap's claims against half the transcript (`review-facts`), a deck read cold as a skeptical executive (`review-red-team`); reads the deck in the browser, edits nothing | Playwright MCP server |

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `writing-seminar-builder` | the owner; learning-seminar-builder | The seminar method: interview, content map, outline gate, HTML deck from the slide library, Playwright checks, red team; the unattended passes as Steps; the deck kit, slide types, elements, the hands-on lab kit and the teaching style |
| `community-workstream` | learning-community-host | Steps; sections Read the recording, Write the agenda and invitation, Stage the invitation, Write the recap and record; the session files and both DONE checklists |
| `review-facts`, `review-red-team` | reviewer (shared copies) | The facts and red-team checklists |
| `brand-guide`, `unslop`, `unslop-email`, `orchestration-workstream` | shared copies | House brand and voice; the invitation's editing standard; the conduct and return block |

## Scripts

None as commands. The older PowerPoint kit (`deckbuilder.py`, `flowkit.py`, `render_previews.py`, needing `python-pptx` and `pillow`) sits in `writing-seminar-builder/scripts/lib/` for a deck built by `references/build-deck-howto.md`; the HTML deck needs none of it. Planned and not yet written: `learning-seminar-check` (`writing-seminar-builder`), `learning-community-pack` and `learning-community-check` (`community-workstream`).

## Decisions taken in the conversion

- The community host writes the invitation and reads the recording itself, from sections of `community-workstream`, instead of dispatching productivity's drafter and meeting analyst: one invitation and one transcript per pass need no isolation, and a plugin dispatches only its own agents.
- The PowerPoint kit moved to `scripts/lib/` rather than becoming commands (plan open question 2): nothing in the HTML method runs it, and it keeps working for a hand-built `.pptx`.
- The deck kit stays inside `writing-seminar-builder` for now (plan D3 proposed splitting out `html-deck-kit`): its consumers in reporting, projects and process-engineering name it in text only and are converted on other branches; the split is a copy build away once one of them needs the files.
- Community and seminar stay two main agents: different folders, rules, tools and cadence.

## Settings

`training_dir` (the seminars folder) and `voice_guide` (the owner's voice guide), read by the agents, not by a script; both are in [docs/settings.md](../docs/settings.md).
