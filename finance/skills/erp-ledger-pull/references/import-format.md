# Intacct GL journal-entry import: the file format that imports

Rule: every journal-entry import CSV uses Intacct's own GL journal-entry import template, byte for byte. The `je-import` command is the only writer; do not hand-build CSVs. A company's reference sample (a file it imported successfully) is named in its `SYSTEMS.md`.

## The layout

- The template's 28 columns, in this order: DONOTIMPORT, JOURNAL, DATE, REVERSEDATE, DESCRIPTION, REFERENCE_NO, LINE_NO, ACCT_NO, LOCATION_ID, DEPT_ID, DOCUMENT, MEMO, DEBIT, CREDIT, SOURCEENTITY, CURRENCY, EXCH_RATE_DATE, EXCH_RATE_TYPE_ID, EXCHANGE_RATE, STATE, ALLOCATION_ID, BILLABLE, RPESENTRY, GLENTRY_CUSTOMERID, GLENTRY_VENDORID, GLENTRY_ITEMID, GLENTRY_CLASSID, GLENTRY_EMPLOYEEID. Unused columns stay present and empty.
- Header fields (JOURNAL, DATE, REVERSEDATE, DESCRIPTION, STATE) appear on the FIRST line of each entry only; continuation lines leave them blank. Repeating them on every line makes the importer read each line as a new entry.
- Dates are M/D/YYYY with no leading zeros (`8/31/2026`, `9/1/2026`), not ISO.
- Line columns are `LOCATION_ID` and `DEPT_ID` (not LOCATION / DEPARTMENT).
- LINE_NO restarts at 1 for each entry.
- Amounts are never negative: a net refund on an expense line goes in CREDIT (Intacct posts a negative DEBIT as a credit anyway, so the posted debit total then differs from the draft's).
- STATE is `Posted` on every CSV: a person uploads it, and that upload is the human review, so the entry posts on import. `Draft` is kept for an entry an agent creates in Intacct through its API with no person involved, which a person then posts there. Agents never upload or post.
- Each entity (LOCATION_ID) must balance on its own inside the entry. A bill coded to another entity is accrued with its own liability credit at that entity, not lumped into the main entity's offset (the vendor accrual writes one offset line per location).

## What a home-grown layout gets wrong

A writer with its own headers (DEPARTMENT, LOCATION), ISO dates and the header fields repeated on every line is rejected with `GL-0979-1  GL-0951-1` on line 1, and Intacct writes `err_<id>.csv` to the browser's downloads with an ERRORS column appended. The same entry in the template layout imports.
