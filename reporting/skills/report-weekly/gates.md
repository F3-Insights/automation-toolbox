# The gates

Read by `SKILL.md` at Steps 8, 9, 11 and 14. Everything here is put to the executive; nothing here is decided for them. Run unattended, Gates 1 and 2 become one numbered list on the owner's task list (`SKILL.md`, "When no one is present"), with the same content and wording.

## The workers' questions (Step 8)

Every worker ends with a parseable `QUESTIONS FOR THE EXECUTIVE` block and marks the item each question holds up as pending. Save each worker's output to a file, then:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_questions.py collect --from <scratch>/<author>-continuity.txt \
  --from <scratch>/<author>-editor.txt \
  --out <scratch>/<author>-questions.json
```

That gives one numbered list with the duplicates folded together. **Put it to the executive batched, at the next gate, never one at a time and never skipped.** Six questions in one numbered list are answered in a minute; six interruptions are answered over a day. Then record each answer:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_questions.py answer --questions <scratch>/<author>-questions.json \
  --id 2 --answer "<what the executive said>"
```

An answered question is citable as `owner://questions/<id>`, which the verifier accepts the way it accepts a gate answer. An item held up by a question nobody answered stays pending and the report says so; nothing resolves it by assumption.

## Gate 1: confirm this week's categories (Step 9)

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_workorder.py wait --period <period> --gate gate1 \
  --questions <how many> --store <store>
```

Then, where the Portal tier is in use, send **one** heads-up and nothing more (see "The Teams heads-up" below). Then put the gate itself in the terminal.

Its weight follows what the week found, and `proposals.gate_weight` in the pack says which: **one line** when there is nothing to propose, **full** when there is. Show, as a numbered list the executive can answer in a line per number:

1. **The standing categories**, in profile order, with their top items and, for each, the one-line reason from the audience editor's Keep list.
2. **Proposed additions**, from `proposals.add_category`: each cluster in the unassigned bucket that shares a project, a counterparty or a subject term, with its item count and its meeting hours. Code counted these; it did not judge them.
3. **Proposed drops and folds**, from `proposals.drop_this_week` and `proposals.fold_into_other`.
4. **Catch-all candidates**, from `proposals.other_topics_candidates`, and the audience editor's **Leave out** list, so anything judged internal can be pulled back.
5. **Misfiled items**, from `gate1_proposals` in the verdicts file, one numbered line each, in its own words: "move <ref> to <category>?", or "strike <ref>?" where the editor read it as belonging to no category in this scope. Show what it is filed under now and the editor's one line of why. Nothing has moved: the digest still has each of them where the signals put it, and this is the answer that moves it.
6. **Carry-overs that have to be answered**, from the continuity worker's Must be answered list, each with its ledger id.
7. **The workers' questions**, the numbered list from Step 8.

Then ask, in these words:

> Which of these categories is this week's report about? Answer per number: "ok", "drop",
> "add <name>", "fold <name>", "move <number>", "pull back <number>" or "strike <number>".
>
> Anything important this week that is not here?

For example: "1) ok 2) drop 3) add Vendor dispute 4) pull back 2 5) move 1". Then wait.

A repeated misfiling is a profile problem rather than a weekly one. Where the same category claims the wrong item two weeks running, say so and offer to fix the signal: a keyword matching more than it means is the usual cause, and `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py validate` names the ones that will.

### Writing the answers down

Write the answers into `<scratch>/<author>-gate1.json`. The file applies **to this week only**:

```json
{
  "schema": "gate1-answers/1",
  "answered_on": "YYYY-MM-DD",
  "categories": {
    "add": [{"name": "Vendor dispute", "seat": "Finance", "kind": "project",
             "covers": "the disputed invoices and the escalation",
             "signals": {"keywords": ["dispute", "escalation"]}}],
    "drop": ["Audit, tax and compliance"],
    "rename": [{"from": "Annual budget", "to": "Budget"}],
    "fold": [{"from": "Safety", "into": "Other topics"}]
  },
  "items": {"pull_back": [{"ref": "portal://task/t7"}],
            "move": [{"ref": "portal://task/t4", "category": "Vendor dispute"}],
            "strike": ["portal://email/e9"]},
  "carry_overs": {"strike": ["Conveyor fault"]},
  "notes": "<whatever the executive typed, verbatim>"
}
```

A pull-back with no category named goes to the catch-all, which is what "put that back in" means. `move` is the misfiled answer and it always names the category: it takes an item the signals assigned to one category and re-files it under another, and the re-organised digest in Step 10 of `SKILL.md` is where it lands. `moves` in the verdicts file is this list already written; the executive's yes is what puts it in the file. **A lasting change is a second question.** Where the executive adds, drops, renames or folds a category, ask once:

> Make this permanent, or just for this week?

Only on an explicit yes do you edit the author's profile, and only the categories they named. A category struck for one quiet week is not a category lost for good.

## Gate 2: the silences, the figures and the table (Step 11)

**Print the candidate list before you ask anything.** Take the audience editor's Keep list as Gate 1 left it, drop what the executive struck, add what they pulled back, and print it under the confirmed categories, one line per item with the reason a leadership reader would care. This is the whole of what the week produced and judged significant, and it has to be in front of the executive before the questions, because every question below is a question about that list rather than about the week. Asked cold, "what were your wins" is a memory test. Asked against the list, it is a gap check, which is an easier question and a better answer.

Then show the pack's `silent` block: the categories with no evidence, the projects the profile's signals name that nothing matched, and the goals nothing touched. Show every standing metric the pack marked MISSING. Then ask, in these words:

> That is what the week's evidence produced and what I judge significant.
>
> What big wins from last week are missing from it? For each one, what was the size or the
> effect?
>
> Were there updates on any of the silences, can you give me the missing figures, and is
> there any table to add this week?
>
> Does anything on that list reach another department before they have heard it directly?

**The wins question is asked in those words, every week, and it is not a general invitation.** The data side cannot see most of them: the work tracker's listing omits completed tasks and caps a completed listing at 1,000 rows in no date order, so a week's completions are largely invisible to `report-collect`. The answer is therefore the executive's, it is evidence like any other, and the writer cites it `owner://gate2`. A report that only ever carries risk teaches its readers to open it braced.

**A win the executive names goes in, and it is not re-judged against the bar afterwards.** The size or the effect is part of the question because the bar asks a win to carry one and the executive is the only source for it: "we closed clean" is a feeling, "we closed on working day four, a day ahead, with no post-close adjustments" is a bullet. Where they give a win without either, ask once for the size or the effect and take the answer as it comes.

**The last question is about sequence, not content.** Where the answer names something, that item still goes in the report; the executive tells the other department first, and you note in the covering note that they have been told. The report is never where another department first learns of something that affects it.

**The table is the normal case and it is one command.** Whatever they have, a CSV, a Markdown pipe table, or a block of cells pasted out of a spreadsheet, goes in as it stands:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_facts.py add-table --facts <scratch>/<author>-facts.json --key october \
  --from <the file they gave you> --title "October results" \
  --as-of <YYYY-MM-DD> [--status final] [--source "<where it came from>"]
```

With no `--from` it reads standard input, which is what makes pasting one in work. Nothing in it is computed, nothing is footed and no shape is expected: what they pasted is what the report prints. `--source` defaults to "supplied by the executive".

A figure that is not in a table:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_facts.py init --facts <scratch>/<author>-facts.json --period <period> \
  --profile <store>/profile.md          # once, at the start of the week
python3 ~/.claude/skills/report-weekly/scripts/report_facts.py set --facts <scratch>/<author>-facts.json --key cash_on_hand \
  --label "Cash on hand" --value 1840000 --unit usd --as-of <date> --status final
python3 ~/.claude/skills/report-weekly/scripts/report_facts.py set --facts <scratch>/<author>-facts.json --key close_days \
  --not-available --reason "the close is not signed off" --unit days \
  --as-of <date> --status preliminary
```

A figure the week could not produce is **not available**, never zero and never an estimate. Then check the set and re-run Step 10 of `SKILL.md` so the metrics land in the digest:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_facts.py validate --facts <scratch>/<author>-facts.json
```

The computed month-end table, `python3 ~/.claude/skills/report-weekly/scripts/report_facts.py import-table`, exists for the weeks a close has just landed and the executive wants the variances and the footing check done in code. It is never required and you do not raise it unasked.

Write both gates' answers verbatim to `<scratch>/<author>-owner-input.md` with `Write`, under `## Gate 1` and `## Gate 2`, and pass that file's text to the writer. It cites them as `owner://gate1` and `owner://gate2`, and `report-verify` accepts both: they are evidence the pack cannot hold, so nothing is checked against them. Where an executive's answer contradicts the data, the executive wins and the report says so.

## Gate 3: the report itself (Step 14)

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_workorder.py wait --period <period> --gate gate3 --store <store>
```

Show the executive the full text, the verifier's counts and the tie-out's under it, the carry-overs it answered, any item the writer held out for an unanswered question, and the delivery the profile asks for.

**This is where an audience-bar finding is overruled.** Show each `ACTIVITY_HOURS`, `TRACKER_VOCABULARY`, `UNRESOLVED_PUBLISHED`, `IMMATERIAL_FIGURE`, `NO_DECISIONS_BLOCK`, `PERSON_BLAMED` or `AUTHOR_TASK_UPDATE` finding as a numbered line, quoting the sentence and the one-line rule, and say plainly that nothing has been removed. The executive keeps the line, rewords it, or cuts it. Their answer is the judgment; the check was only the prompt to make it.

Show the held-out items in the same list: an item whose answer nobody knew left the body, the covering note says which and why, and this is where the executive sees what they are not seeing and puts it back in a sentence.

Ask one question they can answer in a line:

> Which of these do I deliver? Answer per number: "ok", an instruction to change it, "note
> only", or "skip".

Then wait. Save their approved text to `<scratch>/<author>-approved.md`, even when they changed nothing: the difference between the draft and the approved text is the measure of whether this works, and it is measured from two files.

## The Teams heads-up

The gates run in the terminal. Where the Portal tier is in use, send the executive **one** text heads-up per gate through `teams_post`, to their own member and nobody else:

> Your weekly report is waiting on you at Gate 2: 4 questions.

One per gate, never twice, and **never the report's content, a figure, or a category name**. A heads-up says where the report is stuck, not what is in it. Where `teams_post` is not available, skip it silently and do not mention it. The gate itself is still answered in the terminal.
