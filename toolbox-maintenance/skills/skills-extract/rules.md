# Standards and mechanics for skills-extract

The first half is the standard the judgment steps apply: what makes a candidate, how coverage by existing skills is judged, the candidate list, the house format a draft follows, and the privacy rules. The second half is how the three scripts behave.

## What makes a candidate (step 4)

A candidate is work the owner did by hand more than once that a skill or an automation could do the same way next time. Look for:

- **The same opening.** Prompts that start the same job in similar words ("run the close for August", "refresh the forecast with the new actuals"). The opening prompt of each session is kept first in the pack for this reason.
- **The same commands.** The same programs or scripts run in the same order across sessions. That is the `[script]` half of a skill already written, by hand, every time.
- **The same files.** The same kinds of files written each period (a report, a workbook, a memo): the output a skill would produce.
- **The same corrections.** The owner telling the agent the same thing twice ("no, use the posted entries only", "round to thousands"). Those are the rules a `rules.md` should hold.
- **A cadence.** Work that lands at the same point each month, week or quarter.

The recurrence bar: three or more sessions on at least two different days, or the same monthly or weekly job seen in two or more periods. Below the bar, list it under "Seen once or twice" with no recommendation. Count sessions and distinct days from the pack; never estimate a count.

For each candidate decide:

- **Coverage first.** Map it to the existing skills in `skills.json` and the automated runs in the pack, by the next section, before deciding anything else.
- **Skill or automation.** An automation runs unattended on a schedule or a trigger; it suits work whose every decision is already settled by rules. Work that needs the owner's judgment at a point (a number to approve, a client to answer) is an attended skill, with that point as an `[ask]` step. A skill can be both: attended now, unattended later, with a "when no one is present" section.
- **Script versus judgment, per step.** The seam test: does the step require judgment that varies with the input? No, it is a script (fetch, list, count, compare, format). Yes, it is judgment (decide, write, rank). Counting, listing, grouping and date arithmetic are never judgment.
- **Inputs.** What it needs, in plain words (a file, a folder, a system's tools), required or optional, never a path.

## Coverage by existing skills (step 4)

Every candidate is checked against every skill in `skills.json`, whatever kind of place it lives in: the owner's own, a project's, a plugin's, Codex's. Read the description, and open the SKILL.md of any skill that looks close. The question is often not "what new skill" but "the owner built this; why is it not used".

- **Verdict.** Covered: an existing skill does the repeated work as the sessions show it. Partly covered: it does some of the steps, or does them for a different case; name what is missing. Not covered: nothing touches it. Name every skill that touches the candidate, with its kind and its use (sessions, loads, first and last date).
- **Why it looks unused.** For covered and partly covered, find the reason in the evidence, never assume it. The usual ones, in the order to check:
  - It is not standalone: bound to a runner, one repository's engine or one client's system. `points_outside` lists the paths outside its own folder it depends on; a short SKILL.md that mostly points elsewhere is a thin pointer, not a skill.
  - It was never loaded where the work happened: the sessions on the topic show the owner doing it by hand with no load of the skill. Its description may not match the words the owner uses, or it lives in a project folder the sessions did not start in.
  - It was loaded and then abandoned: loads followed by the work done another way in the same session; say what the session did instead.
  - It is one of several overlapping skills (a plugin's, a project's and the owner's own on the same job), or a name in `unmatched` shows the owner still calls an older name.
  - It is maintained, not used: `edit_sessions` without loads.
- **Recommendation**, in this order of preference; a later one needs a reason the earlier ones do not fit:
  1. **Use as is**: it covers the work; say how to invoke it and when.
  2. **Improve <skill>**: say what blocks standalone use or what is missing, and the smallest change that fixes it (move the rules into a companion file, take the client's specifics out to a context input, add the missing step).
  3. **Merge or retire**: overlapping skills become one; say which survives and why. Retiring is a proposal to the owner, never a deletion.
  4. **New skill**: only when nothing covers it even partly, or when the nearest skill is bound so tightly that an improvement would be a rewrite; say which.
- An automated run that already does the work counts as coverage too: say so and propose nothing unless the sessions show the owner still redoing it by hand.

## The candidate list (`candidates.md`)

Written to the working folder only. It may name clients and projects, because it stays private; nothing from it is copied into a draft. It leads with the skills that already exist.

```markdown
# Candidates: <topic>, <window>

Pack: <generated_at>, <matched> sessions on <distinct_days> days; <automated_matched> automated runs.
Inventory: <skills> skills in <folders> folders; <used> used in the matched sessions.

## Existing skills on this topic

| Skill | Kind | Used: sessions, loads | First, last | Covers | Why it looks unused | Recommendation |
|---|---|---|---|---|---|---|
| <invoke name> | user, project, plugin or codex | <S>, <L> | <dates or "never"> | <which candidates> | <reason, with evidence> | use as is, improve, merge or retire |

## Candidates

| # | Repeated work | Evidence | Existing skills | Coverage | Recommendation |
|---|---|---|---|---|---|
| 1 | <one line> | <N> sessions, <D> days | <skill names, or "none"> | covered, partly or not | use <skill>, improve <skill>, merge or retire <skills>, new skill |

### 1. <the work, or the proposed skill name>
- Existing skills: <each skill that touches it, its kind and use, and what it does here>
- Coverage: covered | partly covered (missing: <what>) | not covered
- Why unused: <the reason and the sessions that show it, or "not applicable">
- Recommendation: use as is | improve <skill> | merge or retire <skills> | new skill, and why
  the earlier options do not fit
- Runs: attended | unattended | attended now, unattended later
- Evidence: <N> sessions on <D> days, <first date> to <last date>; <sessions by month>
- Seen as: <the repeated opening, commands, files or corrections, paraphrased>
- Inputs: <plain words>
- Steps: <numbered sketch, each tagged script or judgment or ask; for an improvement, the
  steps that change>
- Sessions: <session ids and dates, for the record>

## Seen once or twice
- <one line each, with its count>
```

Rank by evidence, then by the owner's time saved. A list of three strong candidates is a better answer than ten thin ones. An existing skill that touches nothing in the evidence is left out of the first table.

## The house format (step 6)

A drafted skill is a folder named for what it does, process first and then role (`month-end-accrual-drafts`, `meeting-prep`, `skill-harvest-workstream`). In a toolbox laid out by department it sits at `<department>/skills/<name>/`, in the department whose business function it serves, and its name is unique across the whole toolbox.

- **`SKILL.md` frontmatter**: `name` (the folder name), `description` (the use case first, then "Use when ..." with the phrases someone would say, then "Not for ...; use <sibling>" where a sibling competes; at most 700 characters), `argument-hint` when it takes arguments, and `allowed-tools` naming only what the steps use.
- **Body, in this order**: one paragraph saying what it does and what it never does; the commands it runs in one fenced block; `## Inputs`; `## Steps`; `## When no one is present` when it can run unattended.
- **`## Inputs`**: each input in plain words, required or optional, with no path or file name, then the line "If a required input was not given, ask. If no one can be asked, stop and name it." Anything specific to an owner or a client (accounts, thresholds, people, folders, house rules) is an input, usually "owner context: a private file describing the owner, their organization, clients and house rules" or "client context: a private file describing the client's systems, accounts and calendar". The skill reads it; it never holds it.
- **`## Steps`**: numbered from 1; each step starts with one tag, `[script]`, `[judgment]`, `[hand-off]` or `[ask]`. A `[script]` step names its command in backticks; a `[hand-off]` names the skill or agent it hands to as `[hand-off: name]`. A branch or loop is an indented line inside its step, `→ condition: destination`, the destination `step N` (optionally `(max K)`), `stop`, `ask` or `done`.
- **Companion files**: standards, checklists, thresholds and worked examples go in a `rules.md` beside `SKILL.md`, never in the steps. A sub-agent's instructions go in `briefs/<name>.md` with the question, the inputs and a fixed return format. Scripts go in `scripts/`, one file per command with underscores in its name (`lot_count.py`), run by name as `python3 ~/.claude/skills/<skill>/scripts/<script>.py`. Each is standard-library Python unless a library is unavoidable (then only `pyyaml`, `openpyxl`, `python-pptx`, `python-docx`, `pypdf` or `pillow`, declared in a `# /// script` block at the top), imports nothing outside its own folder, opens with a docstring saying what it does, its inputs and an example, prints a result a branch can name, and has a test in `scripts/tests/` with invented data. Owner facts and folders are settings read from the owner's settings file; secrets come only from environment variables.
- **No runner required.** The skill gives the same result in a plain Claude Code or Codex session and, where it needs no shell, in a chat app. A scheduler may run it; nothing in it names one.
- **Simple.** Under about 800 words in `SKILL.md`. The fewest steps that do the job. No state kept in the skill's folder; memory between runs is a plain log in the work's own folder.
- **Plain writing.** Short sentences, no em-dashes, no emojis, no sales language.

Where the skill-creator skill is installed, its guidance on descriptions and test prompts applies too; on any conflict this format wins.

## Privacy

- The pack and the candidate list hold private material: prompts, folder names, client and people's names. They stay in the working folder. They are never committed, never published and never pasted into a draft, an issue or a message.
- A draft is written at the altitude of a rule, not an instance. Roles, not people ("the approver", "the controller"). "A client", "the ERP", "the bank", not their names. An amount, an account number or a date from the evidence belongs to the evidence, not to the skill.
- Never quote a prompt or a transcript into a draft, even anonymized. Describe the work.
- The name check (step 7) is a backstop, not the method. It knows only the names it is given and the folder names in the pack; a name it does not know will pass. Read each draft once more for anything specific before reporting it.

## Mechanics

### session_pack.py

Reads Claude Code transcripts (top-level session files; sub-agent transcripts are skipped) from the folders the `claude_session_dirs` setting under `[skills-extract]` names, default `~/.claude/projects`, and Codex session logs from `codex_session_dirs`, default `~/.codex/sessions`; `--claude-dir` and `--codex-dir` override both. A claude.ai data export's `conversations.json` (`--claude-export`) adds chats from the web and desktop apps; the format is read as exported and has not been checked against every export version.

- **Matching**: a term matches case-insensitively at the start of a word, in the typed prompts, the working folder, files written, programs run and skills used. `--project` keeps only sessions whose working folder contains the text. Either, or both, is required.
- **Typed versus automated**: a session a runner or scheduler started (Claude Code's SDK entrypoint, a Codex `exec` session) is automated. Automated runs are not listed one by one; they are grouped under `automated_runs` by the opening of their prompt, which is the record of what already runs on its own.
- **Per session**: source, id, origin, start, end, minutes, working folder, branch, the terms it hit, up to 15 typed prompts (the first, then the matching ones, each clipped to 600 characters), programs run with counts, up to 30 files written, skills, sub-agents and connector tools used, and the transcript's path.
- **Across sessions**: counts by month, project, term, program, skill, sub-agent and file written, and the number of distinct days.
- **Skill use**: per session, `skill_use` rows (skill, how, count): a Skill tool call (`tool`), a slash command (`slash`), a SKILL.md named in a Read or in a shell command (`read`, recorded as the skill's folder, made absolute against the session's folder), a `$name` mention in a Codex prompt (`mention`), and a file written inside a skill's folder (`edit`). Across every matched session, typed and automated and before `--max-sessions` trims, these are `skill_events`; `cwds` lists the sessions' working folders. A shell command that names a SKILL.md counts as a read whatever it does with it.
- **Optional section**: `repo` (`--repo`: the git log's subjects and dates in the window, commits by month, the Markdown docs).
- **`private_terms`**: the folder names, mailbox addresses and login name the evidence carries, for the name check.
- **Output**: first line `WORK: ...` or `NOTHING`, exit 0. Exit 2 when it could not run: a bad date, no terms and no project, a missing export file, or an output path inside a git working tree, which it refuses because the pack is private.
- `--max-sessions` (default 400) keeps the best-matching typed sessions: most terms hit, then most matching prompts.

### skill_inventory.py

Reads the pack and looks for `<folder>/<skill>/SKILL.md` in four kinds of place:

- **user**: `~/.claude/skills`;
- **codex**: `~/.codex/skills`, its `.system` skills, and `~/.agents/skills`;
- **plugin**: every plugin's `skills` folder under the synced and cached plugin folders of Claude Code (`~/.claude/plugins/synced`, `~/.claude/plugins/cache`) and Codex (`~/.codex/plugins/cache`), the newest cached version of a plugin only. A folder named for trash is never read; a marketplace's catalog is not installed and is not read;
- **project**: `.claude/skills`, `.agents/skills` and `.codex/skills` in each of the pack's `cwds` and its git root, each repository whose project skill a session read or edited, the `--repo` the pack was built with, each `--project-dir`, and every folder directly under a `--projects-root`. Claude Code deletes old transcripts after a while, so a repository the owner worked in may not show in `cwds`; pass the folder of repositories when the scope is all projects.

`--skills-dir` adds any other folder (kind `given`); for a toolbox laid out by department that is not linked into `~/.claude/skills`, pass each department's `skills` folder. A skill reached several ways (a symlink, a synced copy, a worktree's identical copy) is one entry with every location; one name with different text is two entries. A plugin skill is invoked as `plugin:name`.

Per skill: `name`, `invoke`, `folder`, `plugin`, `description`, `kinds`, `locations`, `has_steps`, `words`, `scripts`, `points_outside` (up to eight paths the SKILL.md names that its own folder does not hold: home or system paths, and relative paths in backticks such as a repository's `scripts/` or `.venv/bin/` command), and `use`: sessions, loads, `by_how`, typed and automated sessions, first and last date, the dates, up to fifteen session ids, and edit sessions and dates kept apart. An event matches a skill by its folder's real path, else by `invoke`, else by name or folder name. A load that names a skill only by a name several skills share counts for each of them and is also counted in `shared_name_sessions`, so a fork or an old copy does not look used on another copy's evidence. A read of a SKILL.md is a load whatever the session did with it; a session that moved or reviewed skills reads them too, so check the session before calling a read use. `unmatched` lists tool calls and reads of names no skill carries now (renamed or removed); unmatched slash commands and mentions are dropped, since most are built-in commands.

Output: first line `SKILLS: ...`, exit 0. Exit 2 when it could not run: no pack, a missing `--projects-root`, or an output path inside a git working tree.

### name_check.py

Scans every text file under the given folders or files. Names come from `--names` files (the lines under a heading containing "Private names", or every line of a plain list) and from a pack's `private_terms`. Names match case-insensitively on whole words, also inside paths, handles and identifiers. It also reads the private-name denylist the toolbox check reads, from files kept outside any repository: each file in `F3I_TOOLBOX_DENYLIST` (separated by `:`) and `~/.config/f3i-toolbox/denylist.txt`, one term per line, `=` for a case-sensitive term, `@` to include another list (`--no-denylist` skips it). Patterns: an absolute home or user path, an email address (except `example.com`), a run of seven or more digits, a token-shaped secret. Each file's own path is checked for names too. First line `CLEAN`, exit 0; or `HITS: N` and one line per hit (`file:line: kind`, never what matched, and `(path withheld)` for a file whose path holds a name), exit 3; exit 2 when it could not run.

## External commands

The three scripts ship inside this skill's folder, so the skill travels as one folder with no install. Run them by their full path:

- `python3 ~/.claude/skills/skills-extract/scripts/session_pack.py`
- `python3 ~/.claude/skills/skills-extract/scripts/skill_inventory.py`
- `python3 ~/.claude/skills/skills-extract/scripts/name_check.py`
