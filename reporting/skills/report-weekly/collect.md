# Collecting the week

Read by `SKILL.md` at Step 3. Pick the tier once, per author, and keep it. Whichever tier ran, the evidence ledger is the same file, and its contract is at the top of `scripts/report_collect.py`.

**Portal tier**, the recommended one: work tracking, calendar and mail are in the Portal and collection is code, fast, repeatable and free of tokens. It needs `portal_mcp_config`.

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_collect.py --domain "<a distinctive part of the scope name>" \
  --since <start date> --until <end date> --lookahead-days 7 \
  --outline-file <store>/profile.md \
  --direct-report-dir <path, where a direct report's update arrives as a file> \
  --out <scratch>/<author>-ledger.json
```

**Manual tier**, where nothing is connected: the reports and notes go in a folder, folded in by code, one evidence item per Markdown or text file.

```bash
python3 ~/.claude/skills/report-weekly/scripts/report_collect.py --tier manual --from-dir <the folder> --domain "<the scope name>" \
  --since <start date> --until <end date> --outline-file <store>/profile.md \
  --out <scratch>/<author>-ledger.json
```

A file whose name starts "direct-report" or "report-from" is a direct report's report; anything else is the executive's own notes. Front matter overrides both, and the date comes from the front matter or the file's modified time. Run one `report-intake` per update that arrives as one long piece of prose and needs breaking into several items; the folder read does not do that and does not pretend to.

**Harvester tier**, where there is no Portal but a connector reaches mail and calendar. Dispatch one `report-harvester` with the period, the seats, the profile text and the output path. It writes the same file and records that the harvest was model-driven. Then check it with `python3 ~/.claude/skills/report-weekly/scripts/report_collect.py --validate <scratch>/<author>-ledger.json --out <scratch>/<author>-ledger.json`.

Where the Portal tier is in use, `report-collect` reads the profile from a note titled `Weekly report profile` on the scope, then an older `Weekly report outline`; `--outline-file` supplies it from the store instead. A `Weekly report spec` note is no longer read, by `report-collect` or by `report-pack`.
