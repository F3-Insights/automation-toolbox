# Dispatching the workers

Read by `SKILL.md` at Steps 6, 7 and 12. Every worker is briefed with the digest's whole text inlined, never a path to it, and every worker's output is saved to a file as soon as it returns.

## The continuity worker (Step 6)

Dispatch one `report-continuity` with the candidates and this week's categories inlined. It returns three lists: must be answered, carry unchanged, leave out. Re-run Step 5 of `SKILL.md` with `--ledger-candidates` so the ones that must be answered arrive in the digest as carry-overs.

## The leadership test (Step 7)

Dispatch one `report-audience-editor` with the digest and the profile's **Leadership team** inlined. The reader is the rest of the leadership team, so every candidate item is tested with one question: what would a member of this leadership team think is important here?

**The editor applies the bar**, which is written once in `reference/weekly-highlights-style.md` beside this file under "What earns a bullet" and "What is never a bullet" and carried in short form by the editor and the writer both. Nothing is deleted by it: an item that fails the bar goes on the Leave out list with its reason, where the executive pulls it back at Gate 1. The materiality threshold the bar refers to comes from the profile's Form rules and is printed in the digest's outline block; a profile that states none has no figure judged immaterial.

**Above the bar sits the significance test, and it has three axes.** Risk, dollar value, and importance to the business. An item clears at least one of them or it is left out whatever its evidence weight, and every Keep line names the axis it cleared in its fourth field alongside the reader reason. That is what keeps the report off the week's minutiae, and the materiality threshold quantifies the second axis only.

It returns three lists. A **Keep** list, each line with the reason a leadership reader would care, the verdict field spelled `has to know`, `decides because of it` or `is affected`, and a `money not in the digest` note where a loss, a suspension, a dispute or a write-off carries no figure. `decides because of it` is what builds the report's `Decisions needed` block, so the line names the decider by role and the date it is needed by. A **Leave out** list, each line with the reason it was judged internal; that list is not a footnote, it is how the executive pulls something back at Gate 1. And a **Misfiled** list, one line per item that reads as belonging under a different category, which the editor never moves itself: a misfiled item is in its verdict list under the category the digest gave it **and** in Misfiled.

Save its output to a file and lift the three lists out of the prose, so Gate 1 is built from data rather than from a transcription:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_questions.py verdicts --from <scratch>/<author>-editor.txt \
  --out <scratch>/<author>-verdicts.json
```

`gate1_proposals` is the numbered "move <ref> to <category>?" list Gate 1 shows, `moves` is ready to paste into the Gate 1 answers file as `items.move`, and `strike_candidates` is every misfiled line that reads as belonging to no category in this scope at all.

Where the profile carries no leadership team the editor says so in one line and falls back on the seven reasons in principle 13 of `DESIGN.md`. That is a gap to fix in the profile, not a reason to skip the step.

## The writer (Step 12)

Read `<scratch>/<author>-digest.md` and **paste its whole text into the prompt**, with the gate answers, the answered questions, the continuity worker's Must be answered list and the audience editor's Keep list. The writer opens no file and makes no listing call, which is the whole reason it answers in one turn.

**The Keep list is not optional context.** Each of its lines carries the reader who has to know, decide or be affected and why, which is the most valuable thing this pipeline computes, and a draft written without it loses every one of those reasons. Paste it whole, reasons included. The materiality threshold rides in the digest's outline block, so it reaches the writer with everything else; where the profile states none, the block says so.

Dispatch one `report-writer` per author, **all in a single message** so they run in parallel. One author per agent is the contract.

```
Agent(
    subagent_type="report-writer",
    description="Weekly report for <author>",
    prompt="""
Write the weekly report for one author, in one turn. The digest below is everything: the
outline, the categories in order with their standing metrics, carry-overs and ranked
evidence (the top items with their material beneath them), the unassigned bucket, the Gate 1
proposals, the silent list, the goals, the calendar totals, and what could not be determined.
Open no file.

Write in the Weekly Highlights house style. Carry-overs come first in every category and you
say what happened to each one.

Apply the bar in your prompt file. Every bullet drawn from the Keep list below states, in the
bullet's own words, what the reader has to do, decide or expect: the reason on the Keep line
is what the leadership team is owed, and a bullet that ends as a task status has dropped it.
End the report with the Decisions needed block, built from the Keep lines marked "decides
because of it" plus anything the executive added at a gate, and reading "None this week."
where there is nothing.

Never type a table. Put {{table:<key>}} on a line of its own where a table goes; the keys
available are listed in the digest. Cite a figure, do not substitute one: write the number and put
facts://<key> beside it. The published document carries no references, so "cash on
hand is facts://cash_on_hand" reaches the leadership team as "cash on hand is".

The executive answered both gates and the numbered questions. Their answers are below and you
cite them as owner://gate1, owner://gate2 and owner://questions/<id>. Where they contradict
the data, they win and you say so.

Return your five parts: the report, the sources appendix, the could-not-determine list, the
covering note, and the questions block.

--- DIGEST ---
<the entire contents of <scratch>/<author>-digest.md>
--- END DIGEST ---

--- THE EXECUTIVE'S ANSWERS ---
<the entire contents of <scratch>/<author>-owner-input.md, and the answered questions>
--- END ANSWERS ---

--- CONTINUITY: MUST BE ANSWERED ---
<the continuity worker's first list, or "none: this author has no report ledger yet">
--- END CONTINUITY ---

--- AUDIENCE EDITOR: KEEP ---
<the audience editor's Keep list>
--- END KEEP ---
"""
)
```

A writer that returns `BLOCKED:` produced nothing. Relay its question at Gate 3 and move on; do not re-dispatch it with a guess.
