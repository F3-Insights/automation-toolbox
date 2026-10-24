---
name: office-files
description: Reads Excel workbooks, PDFs and PowerPoint decks for other skills and agents, and writes CSV and JSON extracts and merged PDFs from them. It never saves over a person's workbook or deck. Use when a skill or agent needs a file's contents as text or data.
---

# Office files

Three scripts, each a named command in a department plugin that holds this skill (`excel-handle`, `pdf-handle`, `powerpoint-handler`; or `python3 scripts/<script>.py` from this folder). Each needs one package, declared at the top of the script, so `uv run` or `pipx run` installs it; with plain `python3` the package must be installed.

| Script | Package | What it does |
|---|---|---|
| `excel_handle.py` | openpyxl | Reads a .xlsx or .xlsm workbook read-only, with the values Excel last calculated |
| `pdf_handle.py` | pypdf | Prints a PDF's text and comments page by page, or merges PDFs |
| `powerpoint_handler.py` | python-pptx | Prints a .pptx deck's slide text, tables, speaker notes and pictures |

## Calling them

```
excel-handle analyze book.xlsx
excel-handle read book.xlsx --sheet Detail --columns "Account,Amount" --rows 50
excel-handle extract book.xlsx --column Amount --condition ">1000" --output big.csv
excel-handle convert book.xlsx --all-sheets
excel-handle process book.xlsx --column Status --col-operation frequency
pdf-handle --operation text --pdf-path agreement.pdf
pdf-handle --operation merge -f a.pdf -f b.pdf --output-filename both.pdf
powerpoint-handler --ppt-file deck.pptx --output-format markdown
```

Each script's `--help` lists every option. Excel output is JSON; the PDF and deck scripts print text by default and JSON on request. A failure exits non-zero with one line on stderr.

## Limits

- `read` and `extract` print at most 200 rows (`--limit N` to change it, `--limit 0` for all). When rows were cut, the JSON says so in `note` and `rows_shown`, while `rows` stays the full count. `--output` always writes every row, so write a long sheet to a file and read that.
- The first row of a sheet is its header. A formula cell shows its last calculated value, so a workbook never opened in Excel since it was written shows blanks there.
- `pdf_handle.py` reads the text layer only. A scanned PDF comes back with empty pages, which the summary counts; read it as an image instead.
- Legacy .xls and .ppt files are not read; save them as .xlsx or .pptx first.
