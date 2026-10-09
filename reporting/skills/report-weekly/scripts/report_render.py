#!/usr/bin/env python3
# /// script
# dependencies = ["pypdf"]
# ///
"""report-render: the approved report and its facts set into the files that are published.

Three mechanical steps. Each `{{table:<key>}}` marker is replaced with that table from the
facts set (a marker naming no table is left visible and listed, never silently deleted). Every
evidence reference (portal://, pack://, owner://, facts://, ledger://, mail://, calendar://,
file://) is lifted out of the text into evidence-map.json beside it, one entry per line, so the
published document carries none of them and the trace survives. Then Markdown goes through
pandoc into Word against the house reference document, and Word through LibreOffice into PDF,
and the page count is read back off the PDF.

Inputs: --report (Markdown, markers still in it), --facts (the facts set), --out-dir, --name
(the base file name), --format md|docx|pdf|all, --max-pages (default 2). The reference document
is --reference-docx, else the setting reference_docx under [report-weekly], else one built for
this run by build_reference_docx.py.

Exit 0 within the page cap, 3 over it (the files are still written: cut detail, never a
category), 2 when it could not run (pandoc or LibreOffice missing; --format md needs neither).

Example:
  python3 report_render.py --report approved.md --facts facts.json --out-dir ~/reports/out \\
      --name weekly-2027-11-12 --format all --max-pages 2 --json
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _facts as fx
from _common import (ANY_BULLET, FAILED, OK, REFERENCE, SHORT_REFERENCE, Fail, now_utc, run_main,
                     run_script, safe, settings)

WRAPPED = re.compile(r"\s*[\(\[]\s*(?:" + REFERENCE.pattern + r")(?:\s*(?:,|;|and)?\s*(?:"
                     + REFERENCE.pattern + r"))*\s*[\)\]]")


def tidy(line):
    """One line with the holes the references left closed up; leading indent kept."""
    indent = re.match(r"^[ \t]*", line).group(0)
    text = indent + re.sub(r"[ \t]{2,}", " ", line[len(indent):])
    text = re.sub(r"\(\s*[,;:\s]*\)|\[\s*[,;:\s]*\]", "", text)
    return re.sub(r"\s+([,.;:)])", r"\1", text).rstrip()


def strip_evidence(text, name):
    """(the published text, the evidence map from each line to the references it carried)."""
    published, entries, total = [], [], 0
    for number, line in enumerate(text.splitlines(), 1):
        refs = [m.group(0).rstrip(".:") for m in REFERENCE.finditer(line)] + \
               [m.group(0) for m in SHORT_REFERENCE.finditer(line)]
        if not refs:
            published.append(line)
            continue
        total += len(refs)
        cleaned = tidy(SHORT_REFERENCE.sub("", REFERENCE.sub("", WRAPPED.sub("", line))))
        if re.fullmatch(r"[\s.,;:!?)\]]*", cleaned) and published and published[-1].strip():
            published[-1] = tidy(published[-1] + cleaned.strip())
            cleaned = published[-1]
        else:
            published.append(cleaned)
        entries.append({"line": number, "kind": "bullet" if ANY_BULLET.match(line) else "line",
                        "text": cleaned.strip(), "refs": refs})
    return "\n".join(published), {"schema": "report-render/evidence-map/1", "report": name,
                                  "generated": now_utc(), "lines_with_evidence": len(entries),
                                  "refs": total, "entries": entries}


def page_count(pdf):
    """The PDF's page count and how it was read, or None with the reason."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf)).pages), "pypdf"
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 - a broken PDF is worth naming, not a crash
        return None, f"pypdf could not read the file: {type(exc).__name__}"
    if shutil.which("pdfinfo"):
        done = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
        hit = re.search(r"^Pages:\s+(\d+)", done.stdout, re.MULTILINE)
        return (int(hit.group(1)), "pdfinfo") if hit else (None, "pdfinfo printed no page count")
    return None, "neither pypdf nor pdfinfo is available, so the page count is unknown"


def reference_document(given, scratch):
    chosen = given or str(settings("report-weekly").get("reference_docx") or "")
    if chosen:
        path = Path(chosen).expanduser()
        if not path.is_file():
            raise Fail(f"no Word reference document at {path}; build one with build_reference_docx.py --out {path}")
        return path
    built = Path(scratch) / "reference.docx"
    code, _, err = run_script("build_reference_docx", ["--out", built])
    if code:
        raise Fail(f"the reference document could not be built: {err.strip()[:300]}")
    return built


def main():
    parser = argparse.ArgumentParser(description="Render the approved report: tables in, evidence out.")
    parser.add_argument("--report", required=True, help="the approved report, Markdown")
    parser.add_argument("--facts", default="", help="the facts set the table markers render from")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--name", default="", help="the base file name; the report's own without it")
    parser.add_argument("--format", default="all", choices=("md", "docx", "pdf", "all"))
    parser.add_argument("--reference-docx", default="", help="the Word reference document")
    parser.add_argument("--max-pages", type=int, default=2, help="the house style's hard cap")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = Path(args.report).expanduser()
    if not source.is_file():
        raise Fail(f"no report at {source}")
    facts = fx.load_set(args.facts) if args.facts.strip() else {"tables": {}}
    name, out = args.name.strip() or source.stem, Path(args.out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    used, missing = [], []

    def table(match):
        key = match.group(1)
        if key not in facts.get("tables", {}):
            missing.append(key)
            return match.group(0)
        used.append(key)
        return fx.render_markdown(facts["tables"][key], proportional=args.format != "md")

    published, evidence = strip_evidence(fx.TABLE_MARKER.sub(table, source.read_text(encoding="utf-8")), name)
    markdown = out / f"{name}.md"
    markdown.write_text(published.rstrip() + "\n", encoding="utf-8")
    (out / "evidence-map.json").write_text(json.dumps(evidence, indent=1) + "\n", encoding="utf-8")
    files, pages, how = {"md": str(markdown), "evidence_map": str(out / "evidence-map.json")}, None, "no PDF was rendered"
    if args.format != "md":
        if not shutil.which("pandoc"):
            raise Fail("pandoc is not installed, and it turns the text into the Word file; use --format md without it")
        with tempfile.TemporaryDirectory() as scratch:
            reference = reference_document(args.reference_docx, scratch)
            docx = out / f"{name}.docx"
            done = subprocess.run(["pandoc", str(markdown), "--from", "markdown+pipe_tables", "--to", "docx",
                                   f"--reference-doc={reference}", "--output", str(docx)], capture_output=True, text=True)
        if done.returncode or not docx.is_file():
            raise Fail(f"pandoc could not write the Word file: {done.stderr[:300]}")
        files["docx"] = str(docx)
    if args.format in ("pdf", "all"):
        office = shutil.which("soffice") or shutil.which("libreoffice")
        if not office:
            raise Fail("LibreOffice (soffice) is not installed, and it turns the Word file into the PDF")
        done = subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", str(out), files["docx"]],
                              capture_output=True, text=True)
        pdf = out / f"{name}.pdf"
        if done.returncode or not pdf.is_file():
            raise Fail(f"LibreOffice could not write the PDF: {done.stderr[:300]}")
        files["pdf"] = str(pdf)
        pages, how = page_count(pdf)
    form = {"pages": pages, "read_by": how, "cap": args.max_pages,
            "passed": None if pages is None else pages <= args.max_pages}
    result = {"files": files, "tables": used, "tables_missing": missing, "form_check": form,
              "evidence": {"lines": evidence["lines_with_evidence"], "refs": evidence["refs"]},
              "words": len(published.split())}
    if args.json:
        print(safe(json.dumps(result, indent=1)))
    else:
        print("\n".join(["# Report render", ""] + [f"- {k}: {v}" for k, v in files.items()] + [
            f"- pages: {pages} against a cap of {args.max_pages}" if pages is not None else f"- pages: not known ({how})",
            f"- tables rendered: {', '.join(used) or 'none'}"]
            + ([f"- markers with no table: {', '.join(missing)}"] if missing else [])
            + [f"- evidence lifted out: {evidence['refs']} references on {evidence['lines_with_evidence']} lines"]))
    if form["passed"] is False:
        print(f"ERROR the report renders to {pages} pages against a cap of {args.max_pages}. Cut detail, "
              f"never a category", file=sys.stderr)
        return FAILED
    return OK


if __name__ == "__main__":
    run_main(main)
