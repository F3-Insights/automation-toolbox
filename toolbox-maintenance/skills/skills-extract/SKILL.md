---
name: skills-extract
description: Look through past Claude Code and Codex sessions (and optionally a claude.ai chat export and a repository's history) on one topic or repo, find the work that keeps being done by hand, check it against every skill the owner already has, and say for each piece whether to use an existing skill, improve one, merge or retire overlapping ones, or, last, build a new one, with evidence counts and dates. Drafts the ones the owner picks in the house format, generic and name-checked, into a drafts folder. Use when someone asks "what should I turn into a skill", "mine my chats for automations" or "why don't I use the skill I built". Not for the monthly unattended harvest; use skill-harvest-orchestrator.
argument-hint: "[topic, or repo or folder] [optional: window, e.g. 90d] [optional: drafts folder]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(python3 ~/.claude/skills/skills-extract/scripts/session_pack.py:*), Bash(python3 ~/.claude/skills/skills-extract/scripts/skill_inventory.py:*), Bash(python3 ~/.claude/skills/skills-extract/scripts/name_check.py:*)
---

# Extract skills from past work

The evidence is the owner's own sessions. One script condenses them into a data pack; a second lists every skill the owner already has and how often those sessions used it. The model reads the two files, never the raw transcripts. Often the answer is not a new skill but "you built this already; here is why it went unused", so a new skill is the last resort. The owner picks; only then is anything drafted, and only into a drafts folder.

The three commands, all standard-library Python in this skill's `scripts/` folder:

```bash
python3 ~/.claude/skills/skills-extract/scripts/session_pack.py --terms "TERM,TERM" [--project NAME] [--since 90d] \
    [--repo PATH] [--claude-export FILE] --out WORK/pack.json
python3 ~/.claude/skills/skills-extract/scripts/skill_inventory.py --pack WORK/pack.json [--project-dir PATH] \
    [--projects-root PATH] [--skills-dir PATH] --out WORK/skills.json
python3 ~/.claude/skills/skills-extract/scripts/name_check.py DRAFTS/SKILL-NAME --pack WORK/pack.json [--names OWNER_CONTEXT]
```

The session folders the pack reads are settings, `claude_session_dirs` and `codex_session_dirs` under `[skills-extract]` in the owner's settings file, defaulting to Claude Code's and Codex's own folders. The name check also reads the private-name denylist files the toolbox check reads (`F3I_TOOLBOX_DENYLIST` and `~/.config/f3i-toolbox/denylist.txt`); the list never lives in a repository.

`rules.md` beside this file holds the standards: what counts as a candidate, how coverage is judged, the candidate list's format, the house format every draft follows, the privacy rules and the commands' mechanics. Read it before step 4.

## Inputs

- **Topic or scope** (required): a subject, a repository or folder, or both.
- **Window** (optional): how far back to look. Default: all history on the machine.
- **Owner context** (optional): a private file describing the owner, their clients and house rules, ideally with a "Private names" list. It sharpens the terms and the name check, and is never quoted into a draft.
- **Other skills folders** (optional): the inventory already looks in the owner's user, project, plugin and Codex skills folders; name any other folder that holds skills.
- **Working folder** (required): a private local folder outside any git repository for the pack, the inventory and the candidate list. Default: the session's scratch folder.
- **Drafts folder** (required before step 6): where drafted skills go. Never the live skills folder unless the owner says yes to that in this session.

If a required input was not given, ask. If no one can be asked, stop and name it.

## Steps

1. [judgment] Settle the inputs and turn the topic into search terms: word stems (`reconcil`, `accrual`), the names of the systems, reports and documents involved, and the folder or repository names the owner context ties to the topic. Prefer ten precise terms to three broad ones; a term that is a common word on its own (`close`, `report`) needs company.
   → a required input is missing and no one can be asked: stop
2. [script] Build the pack: `python3 ~/.claude/skills/skills-extract/scripts/session_pack.py --terms "..." --out WORK/pack.json` with `--project`, `--since`, `--repo` and `--claude-export` as the inputs allow. The first line of its output is `WORK: ...` or `NOTHING`. When most kept sessions turn out to be off topic, refine the terms and run it again.
   → `NOTHING`: stop
   → exit 2: stop
   → off topic: step 1 (max 2)
3. [script] Inventory the skills the owner already has: `python3 ~/.claude/skills/skills-extract/scripts/skill_inventory.py --pack WORK/pack.json --out WORK/skills.json`, with `--project-dir` for the repository or folder input, `--projects-root` for the folder holding the owner's repositories when the scope is all projects, and `--skills-dir` for any other folder. It lists every user, project, plugin and Codex skill and how often the matched sessions loaded it, with dates. The first line is `SKILLS: ...`.
   → exit 2: stop
4. [judgment] Read `pack.json` and `skills.json` and cluster the repeated work into candidates by the tests in `rules.md`. Map each to the existing skills that touch it: covered, partly covered or not covered. For covered or partly covered, find from the sessions and the skill's SKILL.md why it went unused and what is missing. Recommend, in this order of preference: use as is, improve a named skill, merge or retire, new skill. Open a raw transcript only to settle one question, cited by session id and date. Write `WORK/candidates.md` in the format in `rules.md`, existing skills first.
   → nothing recurs: stop
5. [ask] Put the list to the owner as one numbered list: first the existing skills with their use and recommendation, then each candidate with its evidence count, coverage, attended or unattended, and recommendation. Ask which to act on and where drafts go.
   → no one present: stop
   → none chosen: stop
   → chosen: step 6
6. [judgment] Draft each chosen item in the drafts folder in the house format in `rules.md`: frontmatter, `## Inputs`, tagged `## Steps`, a companion `rules.md` for standards, scripts where the seam test says code. An improvement or a merge is a full copy of the surviving skill with the change made; a retirement is a line in the report. No live skill is edited or deleted. "Use as is" needs no draft: report how to invoke it. Generic wording only: roles, not people; "a client", not a client; no paths, account numbers or quotes from the evidence.
7. [script] Check every draft: `python3 ~/.claude/skills/skills-extract/scripts/name_check.py DRAFTS/SKILL-NAME --pack WORK/pack.json --names OWNER_CONTEXT` (leave out `--names` when there is no owner context). `CLEAN` passes. `HITS` lists each file, line and kind of hit, never what matched (a file whose path holds a name shows as `(path withheld)`): rewrite those lines, or rename that file, generically.
   → `HITS`: step 6 (max 2)
   → `HITS` after the last round: stop
   → `CLEAN`: step 8
8. [judgment] Report: each draft's folder, what it does in one line, what was left out and why, the existing skills to use as they are and how, and what the owner does next (read each draft, try it once, then move it into the live skills folder, which is their call).
   → reported: done

On a stop, say why in one line and what would unblock it: the missing input, the terms that found nothing, or the lines the name check still flags.

## When no one is present

Steps 1 to 4 run the same. Step 5 does not guess: the candidate list in the working folder is the result, and the run ends there. Nothing is drafted without the owner's pick.
