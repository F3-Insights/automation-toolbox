# Setup: the role profile interview

Read by `SKILL.md` before the first weekly run and when the quarterly review comes due. **Only the executive starts it, and only with the executive present**: it is never run unattended and never filled in on their behalf.

Stage 0 of the weekly report: the **role profile**. One Markdown document with twelve headed sections that says what the position answers for, who reads the report, which figures it carries every week and where each one comes from, when it goes out, and what may never be published or even stored.

It is set once and reviewed every quarter. Everything downstream reads it, so an hour here is the difference between a weekly report that writes itself and a weekly interview.

**This is an interview, not a form to fill in on the executive's behalf.** Nothing is assumed. Where an answer is unclear, ask again rather than filling the gap. The executive owns the report; you are their admin.

## How to ask

- One round of questions at a time. Never more than one.
- A numbered list, so the answer can come back as "1) ... 2) ... 3) skip".
- A few questions per round, grouped by section. A round that runs past five questions is two rounds.
- Read back what you wrote after each section, in one or two lines, and move on when the executive confirms it.
- An answer you did not understand is asked again. An answer that contradicts an earlier one is put to the executive as a choice, not resolved by you.
- Keep every person in the document as a **role**. No name belongs in the profile.

## Before the first question

1. Ask where the author's **store folder** is, the one folder this workflow reads and writes: the profile, the continuity ledger, the weekly records, the edit-size series and the work orders all live in it. There is no default path in any of these commands. Then start the form: `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py init --out <store>/profile.md`. If the Portal collection tier is in use, the profile can also live as a note titled `Weekly report profile`, and the working file stays in the store so `report-profile` has something local to read.
2. Read the template so the questions follow its sections in order: `reference/weekly-report-profile.md` beside this file.
3. Tell the executive what the interview covers and roughly how long it takes: twelve sections, about half of them one question each.

## The rounds

Ask in this order. The order matters: the seats are what the categories are derived from, and the leadership team is what the audience test is run against.

**Round 1, the author and the seats.** What is the role, described as a position rather than by name? What does the organisation do, and roughly how large is it? Does this person hold one seat or two, for example operations and purchasing? For each seat, one paragraph on what the position answers for.

**Round 2, the audience.** Who reads this report, by role? For each of them, what do they answer for? Say why you are asking: every candidate item in the weekly report is tested against this list, so an item earns its place when one of these readers has to know it, has to decide something because of it, or is affected by it. Without the list there is nothing to test against and the report becomes a list of what the author was busy with.

**Round 3, the categories.** Propose a starting list derived from the seats they just described, one category per standing responsibility plus any project they lead, ending with `Other topics`. Present it like this:

> This is a proposal, not a list to approve. I drew it from what you said each seat answers
> for, and the first draft is usually wrong in one or two places. Strike what does not belong,
> rename what is misnamed, and add what I missed. Three to seven categories is the range a
> one-page report reads well at, not a rule: if the job needs eight, we write eight and I will
> ask later whether the report is too long or the week unfocused.

Then, per category the executive keeps: which seat it belongs to, whether it is a standing responsibility (`operational`) or something with an end (`project`), one line on what it covers, and the signals that let code recognise its evidence, which are title patterns, subject patterns, keywords, projects, goals and counterparty domains. Ask for signals a few categories at a time; that is the longest part of the interview and it is worth the time, because a category with no signals is silent every week.

Order the categories by how much the reader cares. That order is also the precedence when two categories could both claim the same thread.

**Round 4, the standing metrics.** Ask once, and take no for an answer: are there figures this report carries *every single week*, whatever else happened? Many roles have none, and **an empty list is a correct answer, not a gap**. Say why you are asking: a standing metric is a figure the report is expected to show whether or not it moved, so the weekly run can tell the executive when it is missing. A number that simply turned up in one week is not one of these; it arrives at Gate 2 with everything else.

For each one they do name: where the number comes from, either a figure the facts set supplies, written `facts:<key>`, or one they give at a gate, written `supplied by hand`; and how often it moves, weekly, monthly, quarterly or annual. Say plainly that a figure with no value is reported as not available that week and that nothing is ever invented.

**Do not ask about the financial table.** The narrative is the product. A table is a Gate 2 question every week, and whatever the executive has by then goes in verbatim through `python3 ~/.claude/skills/report-weekly/scripts/report_facts.py add-table`. The weekly flow never requires one and never asks the profile for its shape.

**Round 5, the direct reports.** Who reports to this seat, by role, and what does each one report on? Where and when does their weekly report arrive: mail from an address with a subject pattern, a note with a title pattern, or a file under a glob. This is what makes the cascade work: their report is more detailed in their area and the head's report pulls out what the leadership team needs.

**Round 6, the collection tier and the scope signals.** Is the mail, calendar and work tracking in the Portal (`portal`), reachable only by a worker reading a mail connector (`harvester`), or not connected at all (`manual`)? Then the signals that say a meeting or a thread belongs to this scope at all: attendee email domains, title patterns, mail terms.

**Round 7, the form and the delivery.** Length target and hard cap. Which day, and by what time. What happens when that day is a holiday. Who the report goes to, by role, and which folder the file is filed in.

Then materiality, in one question: **below what amount is a figure not worth the leadership team's attention on its own?** Write the answer as `Materiality: $10,000` under Form rules. Say, in the same breath, that a smaller figure may still appear inside a pattern that carries its own count and total, so a single $81 billing error is not reportable and "eleven billing errors this quarter, $4,900 recovered" is. An executive who does not want a bar says so and the line is left out: with none stated no figure is judged immaterial, every amount may stand on its own, and `report-verify` skips its IMMATERIAL_FIGURE check and says so. That is a warning at validation, never an error. Leave the placeholder in its angle brackets where they decline: an answer still in `<angle brackets>` is read as no answer, which is the point of writing the form that way.

Then the names map, optional and a minute's work: **who comes up often enough in this seat's week to be worth writing down, and what is their role?** One `<name>: <role>` item each, under `Names to roles`, the only section of the profile that holds names. It exists for one rule: a person may be named in the report for credit or for joint work, and a person is never named in a sentence that attaches them to a mistake, a delay or an unmet obligation. With the map the writer puts the role in place of the person when it rewrites such a sentence; with none it states the event with no actor at all, which is also correct. Leaving it out is a warning at validation, never an error.

**Round 8, the two exclusion lists.** What may never appear in the report, whatever else is true? And separately, what may never even be stored in the record kept for continuity and audit? Two lists, because they are different questions. Ask the exclusion questions before the executive gets tired: this is the field that most often turns a usable report into one that cannot be sent, and the one people leave until last.

**Round 9, the review date.** Today's date as the last review, and three months on as the next, written as `YYYY-MM-DD`. Confirm the quarterly cadence.

## Then check it

Run `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py validate --profile <path>` and show the executive the result in full, warnings included. Errors and warnings are different things and say so:

- An **error** is something no correct profile has: a missing section, a tier that is not one of the three, a standing metric with no source, a category naming a seat the profile does not declare, a review date that does not parse. Fix every one before finishing.
- A **warning** is worth their eye and may still be right: a category count outside three to seven, a category with no signals, a metric with no cadence, an empty exclusion list, no standing metrics at all. Read each one out, ask whether to change it, and change only what they ask for. A warning the executive has considered and kept is a decision, not a defect, and "no standing metrics" is the commonest of those.

Re-run `validate` after each fix. Finish only on a clean exit.

Then show them the categories in the order the pipeline will use them: `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py show --profile <path> --outline`. That is a projection of this same document, not a second one to keep in step. **The weekly run reads the profile itself**, so there is one thing to edit and nothing to retype.

## Where it is stored

In the author's store folder, and where the executive says beyond that:

- `<store>/profile.md`, beside the continuity ledger, the records, the edit-size series and the work orders. Read the path back to them.
- And, when the Portal collection tier is in use, a note titled `Weekly report profile` attached to their domain, which is where the collection adapter looks first. Search for an existing note of that title before creating one; two profiles with the same title is a silent fork. The working file stays in the store either way, so `report-profile` has something local to read.

## Finishing

Tell the executive three things and stop:

1. Where the profile is stored and how to edit it. It is theirs, it is plain Markdown, and editing it is the supported way to change what the report covers.
2. The next step is the first weekly run (`SKILL.md` from Step 2), which reads this profile, sorts the week into its categories and comes back with two gates before a word is written. It will ask at Gate 2 whether there is a table to add, and anything they have, a spreadsheet range, a CSV, a pasted grid, goes in as it stands.
3. The review is due on the date in the profile. `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py due --profile <path>` answers whether it has come round, and this interview is run again to work through it.
