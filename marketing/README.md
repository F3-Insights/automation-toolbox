# Marketing & Writing

Public content and case studies drafted from the owner's finished work, the house brand, and the unslop editing skills that every other department uses to make drafted writing read as a careful professional wrote it for a specific reader. Use it to keep a posting cadence, turn a closed engagement into a case study, or edit any draft before someone else reads it.

## The plugin

This folder is a standalone Claude Code plugin named `marketing` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job, one `marketing-worker` and one `marketing-reviewer`, the know-how in the skills as `##` sections. It has no scripts, so no `bin/`.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/marketing --agent marketing:marketing-post-writer
```

## Jobs and agents

| Agent | Automation | What it does | Needs |
|---|---|---|---|
| `marketing-post-writer` | marketing-content | Mines finished work for candidate posts, drafts the Run's posts in the owner's public voice, has them checked for anonymity, voice and facts. Drafts only. | `MARKETING-RULES.md` and a content library; setting `voice_guide` |
| `marketing-case-study-writer` | marketing-case-study | Turns a closed engagement's closeout into an anonymized, sourced case study, held internal until the owner records the client's consent. | `MARKETING-RULES.md` with a consent register; setting `engagements_dir` |
| `marketing-worker` | | One post drafted when several are drafted in parallel (section Draft a post) | |
| `marketing-reviewer` | | Independent PASS or FAIL: Check a public draft (anonymity, topic rule, voice, length, no promise), `review-facts`, `review-red-team`; edits nothing | |

The case study follows projects' engagement closeout by a file contract: the closeout leaves `Case Study <date>.md` in the engagement's pack and names the marketing-case-study launch as the owner's next step; the case-study writer reads that file. Neither department dispatches the other.

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `marketing-content-workstream` | The rules, candidate list and draft shapes; sections Mine candidates, Draft a post, Draft a case study, Revise on findings, Check a public draft. | none |
| `marketing-posts` | The content Run's Steps and DONE checklist. | none |
| `marketing-case-study` | The case study's Steps and DONE checklist. | none |
| `review-facts`, `review-red-team` | Shared checklists the reviewer is briefed with. | none |
| `orchestration-workstream` | Shared conduct and return block. | none |
| `unslop` | Router: reads the text, picks the reader-specific sub-skill, applies five universal principles and the symptoms scan. | none |
| `unslop-deliverable` | Editing pass for billed client work product: decks, readouts, executive updates. | none |
| `unslop-email` | Editing pass for emails and short messages read on a phone. | none |
| `unslop-proposal` | Editing pass for proposals, SOWs, MSAs and exhibits, read by a signer and by counsel. | none |
| `unslop-editorial` | Editing pass for writing that teaches or persuades: posts, seminar scripts, newsletters. | none |
| `unslop-technical` | Editing pass for READMEs, ADRs, design docs, commit messages and PR text. | none |
| `brand-guide` | Reference: how to apply a house brand (palette, type, deck rules, voice and tone), with the F3 Insights brand as the worked example. | none |

## Scripts

None. This department runs on Claude Code alone.

## Decisions taken in the conversion

- The shared unslop family and `brand-guide` live in `shared/skills/` (plan D1); marketing holds copies like every other department.
- Posts and case studies stay two main agents: the case study is event-triggered after a closeout and has the consent gate, which stays a step that cannot be skipped.
