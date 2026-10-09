---
name: skill-harvest-workstream
description: What is specific to the monthly skill harvest, on top of orchestration-workstream and skills-extract. The harvest rules file first, the month's scopes mined from the owner's past sessions with skills-extract into one private candidate list, the skills inbox reviewed for entries applied or gone stale, one numbered list for the owner, then drafts of only what they pick, generic and name-checked, staged on a review branch of the toolbox and never merged. The DONE checklists, the files and the shapes, and the branch script. Loaded by skill-harvest-orchestrator, skill-harvest-worker and skill-harvest-checker; not for a user request on its own.
user-invocable: false
---

# Skill harvest workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. The method is `skills-extract` (pack, inventory, candidates, drafts, name check) and its `rules.md`; this skill adds the monthly loop, the inbox review, the review branch and done. The toolbox audit finds waste; the harvest finds methods worth keeping.

## Conduct here

- **The rules file first.** `SKILL-HARVEST-RULES.md` in the harvest folder says: the scopes to mine (topics, projects or repositories), the window, the owner context file for the name check, the skills inbox to review (a private list of skill ideas and changes the owner keeps), and the age after which an inbox entry is stale. It overrides this skill. Where the sessions are is a setting, not a rule: `claude_session_dirs` and `codex_session_dirs` under `[skills-extract]`.
- **Private stays private.** Packs, inventories and candidate lists hold prompts and names. They live only in the Run folder and the harvest folder, never in a draft, a harvest note or the toolbox.
- **Use before improve before new.** The recommendation order in `skills-extract`'s `rules.md` holds. A new skill needs the reason the earlier options do not fit.
- **Nothing drafted without a pick.** The harvest pass ends at the owner's list. The draft pass drafts exactly the numbers they picked.
- **Never touch live skills.** An improvement is a full copy of the surviving skill with the change; a retirement or an inbox removal is a proposal line. Drafts go to `RUN/drafts/`, laid out exactly as they would sit in the toolbox (`<department>/skills/<name>/` for a new or a changed skill, the department the one whose business function the skill serves), for the branch to carry.
- **The toolbox's rules apply to a draft.** Commands are scripts in the skill's own `scripts/` folder with underscores in their names, standard library plus only the packages the toolbox allows, each with a docstring, an inline `# /// script` block when it uses a package, and a test in `scripts/tests/`; owner facts are settings, never written into the skill.

## Files

- `<harvest folder>/<yyyy-mm>/candidates.md`: the month's merged list in `skills-extract`'s candidate format, existing skills first, numbered once across all scopes.
- `<harvest folder>/<yyyy-mm>/inbox-review.md`: each skills inbox entry with its date and a verdict, `live`, `applied` (it says so, or the change is in the toolbox) or `stale` (older than the rules' age with no action), and the proposed action.
- `RUN/harvest-note.md`: the generic harvest note, one line per draft (what it does, where it would live, what it replaces) and the retirement and inbox proposals. It becomes the review branch's commit message, so it is name-checked like a draft.

## The review branch

After a draft pass whose drafts all passed the checker, the finish step stages them:

```bash
python3 ~/.claude/skills/skill-harvest-workstream/scripts/skill_harvest_branch.py --run RUN --pack <the scope's pack.json> --names <owner context>
```

It refuses a Run folder inside any working tree of the toolbox (the live checkout above all), a draft that is a symbolic link and any draft outside `<department>/skills/<name>/` of an existing department, runs the `skills-extract` name check over the drafts and the commit message it writes from the note (which also reads the toolbox's private-name denylist files), adds a worktree in the Run folder on a new `skill-harvest/<date>` branch of the toolbox the `repo` setting under `[skill-harvest-workstream]` names, copies the drafts in, runs the toolbox's own check over them (no check script, no commit), commits them by name and removes the worktree. The live checkout's files and branch are never touched; it never merges and never pushes; the owner reviews the branch. A private name in anything it prints or stores is written `(withheld)`. `--dry-run` checks only.

## The return here

The shared block. `skill-harvest-worker`: item test `candidate` (harvest; item: the candidate's working name; state `new`, `improve`, `merge`, `retire`, `use`, `below-bar`) or `draft` (draft; item: the skill name; state `drafted`, `clean`, `hits`). `skill-harvest-checker`: item test `draft`, state `pass` or `fail` with the fix in `note`.

## DONE: harvest (the orchestrator checks each item and cites its evidence)

1. Every scope in the rules has a pack and a candidate list, or its `NOTHING` line.
2. Every candidate's counts come from the pack and meet the recurrence bar; the rest sit under "Seen once or twice".
3. Every candidate is mapped against the inventory, with its recommendation in the preference order and the reason.
4. Every skills inbox entry has a verdict with its date evidence.
5. The owner has one numbered list; nothing was drafted.

## DONE: draft

1. One draft per pick and nothing else.
2. Every draft and the harvest note are `CLEAN` under the name check, and the checker passed each draft.
3. Every improvement is a full copy of the surviving skill; no live skill or inbox entry was edited or removed.
4. The toolbox itself was not written; the drafts wait in `RUN/drafts/` for the branch script.
