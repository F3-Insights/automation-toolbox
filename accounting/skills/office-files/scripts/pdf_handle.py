# /// script
# dependencies = ["pypdf"]
# ///
"""Read the text of a PDF, or merge several PDFs into one.

Operations (--operation):
  text   prints the PDF's text page by page, then any comments (annotations such
         as sticky notes and highlights with text) with their page numbers.
         This reads the PDF's text layer; a scanned PDF with no text layer
         prints empty pages, and the summary says how many came back empty.
  merge  joins two or more PDFs, in the order given, into --output-filename.

--format json prints one JSON object instead of plain text.

Examples:
  python3 pdf_handle.py --operation text --pdf-path agreement.pdf
  python3 pdf_handle.py --operation merge -f part1.pdf -f part2.pdf --output-filename all.pdf
"""

import argparse
import json
import sys
from pathlib import Path


def fail(message, code=1):
    print(message, file=sys.stderr)
    sys.exit(code)


def reader_for(path):
    from pypdf import PdfReader

    if not Path(path).exists():
        fail(f"file not found: {path}")
    try:
        return PdfReader(path)
    except Exception as error:  # pypdf raises several error types for a bad file
        fail(f"cannot read {path} as a PDF: {error}")


def page_comments(page, number):
    """Annotations on one page that carry text a person wrote."""
    found = []
    for ref in page.get("/Annots") or []:
        note = ref.get_object()
        text = note.get("/Contents")
        if text:
            found.append({"page": number, "type": str(note.get("/Subtype", "")).lstrip("/"),
                          "author": str(note.get("/T", "")), "text": str(text)})
    return found


def read_text(path):
    reader = reader_for(path)
    pages, comments = [], []
    for number, page in enumerate(reader.pages, start=1):
        pages.append({"page": number, "text": page.extract_text() or ""})
        comments.extend(page_comments(page, number))
    empty = sum(1 for p in pages if not p["text"].strip())
    return {"file": path, "pages": len(pages), "empty_pages": empty,
            "text": pages, "comments": comments}


def merge(paths, output):
    from pypdf import PdfWriter

    if len(paths) < 2:
        fail("merge needs at least two --file-paths")
    if not output:
        fail("merge needs --output-filename")
    if Path(output).resolve() in {Path(p).resolve() for p in paths}:
        fail(f"--output-filename {output} is one of the PDFs being merged; choose a new file")
    writer = PdfWriter()
    counts = []
    for path in paths:
        reader = reader_for(path)
        for page in reader.pages:
            writer.add_page(page)
        counts.append({"file": Path(path).name, "pages": len(reader.pages)})
    with open(output, "wb") as handle:
        writer.write(handle)
    return {"output": str(Path(output).resolve()), "files": counts,
            "total_pages": sum(c["pages"] for c in counts)}


def as_text(result):
    if "output" in result:
        return f"Merged {len(result['files'])} files, {result['total_pages']} pages, into {result['output']}"
    lines = [f"{result['file']}: {result['pages']} pages, {result['empty_pages']} with no text layer", ""]
    for page in result["text"]:
        lines += [f"--- page {page['page']} ---", page["text"], ""]
    if result["comments"]:
        lines.append("--- comments ---")
        for c in result["comments"]:
            author = f" ({c['author']})" if c["author"] else ""
            lines.append(f"page {c['page']} {c['type']}{author}: {c['text']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read a PDF's text or merge PDFs.")
    parser.add_argument("--operation", "-o", choices=["text", "merge"], required=True)
    parser.add_argument("--pdf-path", "-p", help="text: the PDF to read")
    parser.add_argument("--file-paths", "-f", action="append", default=[],
                        help="merge: a PDF to add, repeated, in merge order")
    parser.add_argument("--output-filename", help="merge: the PDF to write")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    if args.operation == "text":
        if not args.pdf_path:
            fail("text needs --pdf-path")
        result = read_text(args.pdf_path)
    else:
        result = merge(args.file_paths, args.output_filename)
    print(json.dumps(result, indent=2) if args.format == "json" else as_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
