# Verify, render, deliver and keep

Read by `SKILL.md` at Steps 13, 15, 16 and 17.

## Verify the draft (Step 13)

Save the returned report to `<scratch>/<author>-draft.md` with `Write`, taking the report alone and leaving the appendix, the could-not-determine list, the covering note and the questions block out of the file. Then both checks:

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_verify.py --report <scratch>/<author>-draft.md \
  --pack <scratch>/<author>-pack.json --json > <scratch>/<author>-verify.json
python3 ~/.claude/skills/report-weekly/scripts/report_facts.py tie-out --facts <scratch>/<author>-facts.json \
  --report <scratch>/<author>-draft.md
```

`report-verify` confirms that every `portal://`, `pack://`, `owner://` and `facts://` reference resolves, that every figure and date on a line appears in a record that line cites, that no term the profile's **Never published** list bars occurs, that nothing claims a completion with nothing cited, that the title line and the headers are right, that every top-level bullet opens with a bold label, that every carry-over in the pack is named somewhere, and that the report is inside the profile's length.

It also runs the **audience bar** as seven findings, never errors: `ACTIVITY_HOURS` for a line reporting hours spent or meetings held, `TRACKER_VOCABULARY` for a line carrying a work tracker's own flag words, `UNRESOLVED_PUBLISHED` for a line publishing an unknown instead of asking it, `IMMATERIAL_FIGURE` for a figure below the profile's threshold with no count or total beside it, `NO_DECISIONS_BLOCK` where the report does not end with one, `PERSON_BLAMED` where a person is named in the same bullet as fault-or-delay language, and `AUTHOR_TASK_UPDATE` where a bullet's whole claim is that work the author owns or is owed has not happened yet. Each quotes the line it fired on and states the rule in one sentence. **The verifier reports and never rewrites**: it deletes nothing, and Gate 3 is where the executive reads the line, disagrees, and says keep it anyway. A profile with no materiality threshold has the immaterial check skipped, and the output says so rather than passing it silently.

`AUTHOR_TASK_UPDATE` is the biggest of the seven, because a task update is the most common way an executive report degrades into a status list, and it fires whoever the bullet does or does not name. It stays silent the moment the bullet carries a date that binds somebody, a figure or a stated consequence, which is exactly the rewrite it asks for: the decision and the money at stake in place of "a reply is owed", the effect on another department in place of "the remaining lines still need loading".

`PERSON_BLAMED` fires only on the two together, so a name given for credit or for joint work raises nothing: "working with the controller to resolve the reconciliation" is right and a win may credit the people who delivered it. Expect the occasional false positive and show it anyway. The rewrite it asks for is the event without the actor, "the revenue variance summary is outstanding" in place of "still waiting on <a person> for the revenue variance summary", and the role or the team where a problem genuinely has to name somebody. A name the pack knows as a person raises it on any problem line; a capitalised pair the pack has never heard of raises it only where a fault phrase grammatically governs the pair, so a product or a model named on a line reporting an undone task comes back as `AUTHOR_TASK_UPDATE` instead, which is the defect that sentence actually has.

`python3 ~/.claude/skills/report-weekly/scripts/report_facts.py tie-out` checks every number in a bullet under a table marker, and on every line citing a facts reference, against the table's own cells and the named figures, to the precision the prose used. Both use the same convention: **exit 0 clean, exit 3 findings, exit 2 the check did not run, which is not a pass.**

- **Exit 3 on the verifier** stops that report. The two errors that matter are a reference to something not in the pack and a report over the two-page cap. Send the verifier's lines back to that writer **once**, with the instruction to fix or cut those sentences and nothing else. If the second pass still errors, hold the report.
- **Exit 3 on the tie-out** is a number in the prose that is in no table and no figure. That is the defect principle 3 of `DESIGN.md` exists to catch. Send it back the same way.
- `CARRY_OVER_NOT_ADDRESSED` on a clean exit is the finding to read closely: a carry-over nobody answered is the defect the ledger exists to remove.

Dispatch `fact-check` only when the executive asks, or when the verifier reports more than five `NOT_IN_CITED_RECORD` findings on one report; give it the pack, not an extract. Run `unslop` after a clean verify and only when the verifier's style lint found something, then re-run `report-verify`, because an editing pass can put back a phrase the exclusion list bars.

## Render (Step 15)

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_render.py --report <scratch>/<author>-approved.md \
  --facts <scratch>/<author>-facts.json \
  --out-dir <the folder the executive named> --name weekly-<period> \
  --format all --max-pages 2 --json
```

It substitutes the table markers, lifts every `portal://`, `facts://` and `owner://` reference out into `evidence-map.json` so the published text carries none of them, writes the Markdown, runs pandoc into Word against the house reference document and LibreOffice into PDF, then reads the page count back off the PDF.

- Exit 0 within the cap.
- Exit 3 over it, with the files still written so the author can see what to cut. **Cut detail, never a category.**
- Exit 2 on a missing prerequisite, naming pandoc or LibreOffice. `--format md` works without either. `python3 ~/.claude/skills/report-weekly/scripts/build_reference_docx.py --out <path>` rebuilds the reference document if it is lost.

**Open the PDF's page count in the result and say it.** An agent's claim of success is a claim.

The Word reference document is `--reference-docx` when given, else the owner setting `reference_docx` under `[report-weekly]`, else one built for the run by `build-reference-docx`. A path that is set but missing stops the render with the command to rebuild it.

## Deliver, per the profile (Step 16)

Only what that author's **Delivery** field says, and only for what the executive approved.

- **An email draft.** Run `python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to <recipient> --per-person-days 3 --json` once per recipient: three days rather than the default five, because a weekly report is an expected, recurring contact. Exit 0 is ALLOW. Exit 3 is HOLD: show the rule and the reason in one line and ask whether to draft anyway, except `OPEN_DRAFT_SAME_THREAD`, which is never overridden in any mode. Exit 2 means the gate could not run, which is not a pass. On ALLOW, dispatch one `email-drafter` per recipient, all in one message, with the recipient, the report as the source material, and the intent: a covering message carrying the report, not a rewrite of it. The executive attaches the PDF when they send. **Nothing is sent.**
- **A Portal note**, where the profile asks for one. Keep the `Weekly Highlights:` prefix exactly, attach it to the scope by uuid, and follow the `portal-write-safety` skill before the call.
- **A file.** Only to a path the executive named, in this conversation or in the profile. Never invent a location and never write into this repository.

## Keep the week (Step 17)

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_record.py save --store <store> --period <period> \
  --report <scratch>/<author>-approved.md --draft <scratch>/<author>-draft.md \
  --facts <scratch>/<author>-facts.json --pack <scratch>/<author>-pack.json \
  --evidence-map <the render out-dir>/evidence-map.json \
  --gate-answers <scratch>/<author>-gate1.json \
  --questions <scratch>/<author>-questions.json \
  --verify <scratch>/<author>-verify.json \
  --profile <store>/profile.md --seat "<the seat>" \
  --rendered <the render out-dir>/weekly-<period>.pdf \
  --rendered <the render out-dir>/weekly-<period>.docx --json
```

One command does the record and the ledger. It writes `<store>/records/<period>/` with a manifest carrying a sha256 per file, applies the profile's **never recorded** list to every stored text and JSON file (case-insensitive, anywhere in a word, so a rule barring "Falcon" also takes out "Projectfalcon") and says what was redacted and where. A Word or PDF file cannot be redacted, so when that list is not empty the rendered files are **kept by reference**, their path and sha256 in the manifest's `rendered` entries and the reason in `rendered_storage`, and are not copied into the record; with the list empty they are copied into `rendered/`. It refuses outright (exit 3, nothing written) when the approved text trips **never published**, measures the Gate 3 edit size and appends it to `<store>/edit-size.jsonl`, and hands the stored text to the report ledger so next week can retrieve it.

**Run it with `--draft` every week.** Without it the edit size is null with a reason rather than zero, which is right, but the series is the one measure of whether this workflow works.

Check the manifest before you say it is done: `ledger_pending` false, `redactions` as expected, `edit_size` present, and `rendered_storage` saying whether the Word and PDF files were copied or kept by reference. Where the executive told you at a gate that something is a decision rather than an issue, or that it recurs quarterly, pass a classification file to `python3 ~/.claude/skills/report-weekly/scripts/report_ledger.py add` separately; their answer beats a regular expression.

A recurring ledger entry answered this cycle is `python3 ~/.claude/skills/report-weekly/scripts/report_ledger.py answer --id <id> --on <date> --store <store>`, which leaves it open for the next cycle. `python3 ~/.claude/skills/report-weekly/scripts/report_ledger.py close` is for an entry that is finished, and it refuses a recurring one unless `--retire` says the recurrence itself is over.
