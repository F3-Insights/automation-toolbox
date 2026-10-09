---
name: product-costing-revision
description: "Re-issue a spreadsheet model the client has already seen without ever editing the shared file: copy to a dated revision, refresh source extracts by schema not row position, recalculate in dependency order, write a Revision Log of old versus new metrics and a Client Requests sheet of what the client still owes, and prove the original byte-identical, separating \"the model was corrected\" from \"the result changed\". Use for any monthly cost model, forecast workbook or analysis file re-issued after review. For the product P&L itself, use product-costing-variance."
argument-hint: "[shared workbook path] [revision reason]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/product-costing-workstream/scripts/fg_pl_extract.py:*), Bash(python3 ~/.claude/skills/product-costing-workstream/scripts/costmodel_audit.py:*), Bash(sha256sum:*), Bash(python3:*)
---

# Controlled revision of a shared workbook

Once a client has a file, that file is evidence. The revision is a new file that says exactly how it differs and why, so that a revision touching thousands of cells can still be defended line by line. The same rules hold for versioned results memos.

## Rules

1. **Never edit the shared file.** Record its SHA-256 first. Copy it to `<name> rev<N> YYYY-MM-DD.xlsx`. At the end, prove the original's hash is unchanged.
2. **Refresh source extracts by schema, not by row position.** Locate columns by header text and rows by key, never by "row 47." An inserted row in a client export is the normal case.
3. **Regenerate helper columns; never hand-edit them.** If a column is a formula, it is regenerated from its inputs; if it was a paste, it becomes a formula or a documented import.
4. **Connect existing override flags rather than adding new ones.** Where the model already has an "override standard" column, use it; a second override mechanism is how models rot.
5. **Recalculate in dependency order.** Full rebuild first; if the engine cannot, sheet by sheet from sources to summaries, checking each stage ties before the next.
6. **Separate the corrected model from the changed result.** A fix to a wrong-month reference is a correction; a new production quantity is a business change. The Revision Log labels every delta as one or the other, so the client never reads a bug fix as a profit swing or a profit swing as a bug fix.
7. **List exactly what the client still owes.** Missing extracts, unanswered questions, unconfirmed standards, each with an owner and the rows it blocks.

## The three sheets a revision adds

**Revision Log**: one row per changed metric, with old value, new value, delta, reason (correction / business change / new data), and the source that forced it. Then a paragraph in plain language for the reader who will not open the sheet.

**Client Requests**: owner, ask, rows or products blocked, date asked, status.

**Review** (named for what was reviewed, e.g. Routing Review): the items examined this revision with accept / reject / pending and the evidence for each.

## Process

1. `sha256sum` the shared file; record it in the Revision Log header.
2. Copy to the dated revision name.
3. Audit the copy before touching it, so the baseline defects are recorded separately from your changes. For a per-finished-good cost model run `python3 ~/.claude/skills/product-costing-workstream/scripts/costmodel_audit.py <copy> --year YYYY --month M --layout <layout file>` (the layout file, or the `cost_model_layout` setting under `[product-costing-workstream]`, says where the model's tabs and columns are; `product-costing-workstream` describes it). For any other workbook, run the equivalent checks by hand: cached errors, duplicate keys, margin arithmetic, YTD against the sum of months, ties to the source totals.
4. Apply the revision: refresh extracts, connect overrides, regenerate helpers, recalc.
5. Run the audit again; every finding is either fixed or listed under Client Requests.
6. Write the three sheets. Re-run `sha256sum` on the original; if it differs, stop and say so.
7. Issue with a note that says what kind of change dominated (correction or business) in its first sentence, using the `comms-client-status-update` voice.

## Never

- Overwrite a file a client has opened.
- Accept a row-position formula from a client export.
- Present a correction as a result, or a result as a correction.
- Mark a Client Requests item done on the tool's own authority.
