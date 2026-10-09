# Marketing & Writing

Public content and case studies drafted from the owner's finished work, the house brand, and the unslop editing skills that every other department uses to make drafted writing read as a careful professional wrote it for a specific reader. Use it to keep a posting cadence, turn a closed engagement into a case study, or edit any draft before someone else reads it.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `marketing-content-orchestrator` | Mines finished work for candidate posts, drafts the Run's posts in the owner's public voice, has them checked for anonymity, voice and facts. Drafts only. | `MARKETING-RULES.md` and a content library; setting `voice_guide` |
| `marketing-case-study-orchestrator` | Turns a closed engagement's closeout into an anonymized, sourced case study, held internal until the owner records the client's consent. | `MARKETING-RULES.md` with a consent register; setting `engagements_dir` |
| `marketing-content-writer` | Finds candidate posts and drafts a post or case study with a hidden source on every claim. | none |
| `marketing-content-checker` | Independent PASS or FAIL on anonymity, topic rule, voice, length and no promises. | none |

The orchestrators also dispatch `fact-check` and `executive-red-team` (reporting), and optionally `content-scout` when it is installed.

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `marketing-content-workstream` | The rules, candidate list, draft shape and DONE checklists for posts and case studies. | none |
| `unslop` | Router: reads the text, picks the reader-specific sub-skill, applies five universal principles and the symptoms scan. | none |
| `unslop-deliverable` | Editing pass for billed client work product: decks, readouts, executive updates. | none |
| `unslop-email` | Editing pass for emails and short messages read on a phone. | none |
| `unslop-proposal` | Editing pass for proposals, SOWs, MSAs and exhibits, read by a signer and by counsel. | none |
| `unslop-editorial` | Editing pass for writing that teaches or persuades: posts, seminar scripts, newsletters. | none |
| `unslop-technical` | Editing pass for READMEs, ADRs, design docs, commit messages and PR text. | none |
| `brand-guide` | Reference: how to apply a house brand (palette, type, deck rules, voice and tone), with the F3 Insights brand as the worked example. | none |

## Scripts

None. This department runs on Claude Code alone.
