# When no one is present

Read by `SKILL.md`, and by `weekly-report-orchestrator` every session.

Unattended, this procedure is run by `weekly-report-orchestrator`, in two scheduled sessions a week: a collection run on Thursday and an assembly run on Friday. The gates are still asked, every week; they are asked on the owner's task list rather than in the terminal, and nobody waits for the answer.

- **Collection in code.** `report-weekly-prepare` runs Steps 1 to 5 before the session and writes the week into `<store>/work/<period>/`, one folder per week, so the second session and the owner's answers find the same files the first one left.
- **Gates 1 and 2 are one numbered list.** `python3 ~/.claude/skills/report-weekly/scripts/report_weekly_gates.py build` numbers every question the two gates ask (the categories, the proposals, the misfiled and left-out items, the carry-overs, the workers' questions, the wins, the silences, the missing figures, the table) and states a default beside each. One `comms-confirm` request puts it on the owner's list with the fallback `proceed`, and one message tells them it is there.
- **The answers, or the defaults.** At assembly, `python3 ~/.claude/skills/report-weekly/scripts/report_weekly_gates.py apply` turns the owner's reply into `gate1.json` and `owner-input.md`. A number nobody answered takes its stated default: the standing categories as the profile has them, nothing moved, pulled back or struck, no wins added, a missing figure "not available this week", and a question's item held out as pending. `owner-input.md` and the covering note name every default taken.
- **Gate 3 is the owner's approval, and it is never assumed.** The draft is rendered as `weekly-<period>-DRAFT` and a second request, fallback `wait`, asks the owner to approve it. Nothing is recorded to the ledger until they do.
- `report-weekly-check` computes where the week stands from those files, and its `--precheck` is what the schedules start on.
- Never create an email draft and never write a file outside the store and the report folder the run names. Do not run `outbound-check`: no delivery is made.
- Never record a report to the ledger that the executive has not approved.
- A profile that is missing, fails `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py validate` or is due for review stops the week: the setup interview needs the owner present.
