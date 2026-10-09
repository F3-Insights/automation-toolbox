#!/usr/bin/env python3
"""build-reference-docx: build the Word reference document the weekly report renders through.

pandoc's default reference document (12pt body, 24pt blue headings, one-inch margins) turns a
dense one-page update into three pages. This one has half-inch margins, a 10pt body, compact
black headings and a tight 9pt table style, so the report fits the two-page cap. It is built
from pandoc's own default rather than kept as a binary nobody can review: each setting is a
line in PATCHES below. Needs pandoc on the path.

Input: --out, where the .docx goes. Prints the path and size. Exit 0 ok, 2 error.

Example:
  python3 build_reference_docx.py --out ~/reports/finance/weekly-reference.docx
"""

import argparse
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from _common import OK, Fail, run_main

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
BODY, TABLE, CAPTION, MARGIN = 20, 18, 16, 720  # sizes in half-points, margin in twips
# The order the schema wants a style's children in; appending blindly makes Word "repair" it.
ORDER = ("name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden", "uiPriority", "semiHidden",
         "unhideWhenUsed", "qFormat", "locked", "personal", "personalCompose", "personalReply", "rsid",
         "pPr", "rPr", "tblPr", "trPr", "tcPr", "tblStylePr")
BORDERS = ('<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
           '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
           '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
           '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
           '<w:insideH w:val="single" w:sz="2" w:space="0" w:color="D9D9D9"/>'
           '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/></w:tblBorders>')
SIZE = lambda n: f'<w:sz w:val="{n}"/><w:szCs w:val="{n}"/>'  # noqa: E731
HEADING = lambda before, size, level: {  # noqa: E731
    "pPr": f'<w:keepNext/><w:keepLines/><w:spacing w:before="{before}" w:after="40"/><w:outlineLvl w:val="{level}"/>',
    "rPr": f'<w:b/><w:color w:val="000000"/>{SIZE(size)}'}
PATCHES = {
    "Normal": {"pPr": '<w:spacing w:before="0" w:after="40" w:line="240" w:lineRule="auto"/>', "rPr": SIZE(BODY)},
    "BodyText": {"pPr": '<w:spacing w:before="0" w:after="60"/>'},
    "FirstParagraph": {"pPr": '<w:spacing w:before="0" w:after="60"/>'},
    "Compact": {"pPr": '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'},
    # Black rather than coloured: a coloured heading prints badly and says nothing the words do not.
    "Title": {"pPr": '<w:spacing w:before="0" w:after="80"/>', "rPr": f'<w:b/><w:color w:val="000000"/>{SIZE(26)}'},
    "Subtitle": {"pPr": '<w:spacing w:before="0" w:after="80"/>', "rPr": f'<w:color w:val="000000"/><w:sz w:val="{BODY}"/>'},
    "Author": {"pPr": '<w:spacing w:before="0" w:after="40"/>', "rPr": f'<w:sz w:val="{BODY}"/>'},
    "Date": {"pPr": '<w:spacing w:before="0" w:after="80"/>', "rPr": f'<w:sz w:val="{BODY}"/>'},
    "Heading1": HEADING(160, 24, 0), "Heading2": HEADING(120, 22, 1), "Heading3": HEADING(100, BODY, 2),
    "Caption": {"pPr": '<w:keepNext/><w:spacing w:before="20" w:after="100"/>', "rPr": f"<w:i/>{SIZE(CAPTION)}"},
    "TableCaption": {"pPr": '<w:keepNext/><w:spacing w:before="20" w:after="100"/>', "rPr": f"<w:i/>{SIZE(CAPTION)}"},
    "Table": {"tblPr": '<w:tblInd w:w="0" w:type="dxa"/>' + BORDERS + '<w:tblCellMar><w:top w:w="20" w:type="dxa"/>'
                       '<w:left w:w="43" w:type="dxa"/><w:bottom w:w="20" w:type="dxa"/><w:right w:w="43" w:type="dxa"/>'
                       '</w:tblCellMar>', "rPr": SIZE(TABLE)},
}
# US Letter, half-inch margins all round.
SECTION = (f'<w:sectPr xmlns:w="{W}"><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="{MARGIN}" '
           f'w:right="{MARGIN}" w:bottom="{MARGIN}" w:left="{MARGIN}" w:header="360" w:footer="360" w:gutter="0"/>'
           f'</w:sectPr>')
DEFAULTS = {"rPrDefault": f"<w:rPr>{SIZE(BODY)}</w:rPr>",
            "pPrDefault": '<w:pPr><w:spacing w:after="40" w:line="240" w:lineRule="auto"/></w:pPr>'}


def q(tag):
    return f"{{{W}}}{tag}"


def fragment(inner):
    return list(ET.fromstring(f'<w:wrap xmlns:w="{W}">{inner}</w:wrap>'))


def put(parent, tag, inner):
    """Replace one child of a style, in the position the schema wants it."""
    for old in [c for c in parent if c.tag == q(tag)]:
        parent.remove(old)
    element = ET.Element(q(tag))
    element.extend(fragment(inner))
    rank = ORDER.index(tag)
    at = next((i for i, c in enumerate(parent) if c.tag.split("}")[-1] in ORDER
               and ORDER.index(c.tag.split("}")[-1]) > rank), len(parent))
    parent.insert(at, element)


def patch_styles(xml):
    root = ET.fromstring(xml)
    seen = set()
    for style in root.findall(q("style")):
        if style.get(q("styleId")) in PATCHES:
            seen.add(style.get(q("styleId")))
            for tag, inner in PATCHES[style.get(q("styleId"))].items():
                put(style, tag, inner)
    if set(PATCHES) - seen:
        raise Fail(f"pandoc's default reference document has no style {', '.join(sorted(set(PATCHES) - seen))}")
    defaults = root.find(q("docDefaults"))
    for tag, inner in DEFAULTS.items():
        holder = defaults.find(q(tag)) if defaults is not None else None
        if holder is not None:
            for old in list(holder):
                holder.remove(old)
            holder.extend(fragment(inner))
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def patch_document(xml):
    root = ET.fromstring(xml)
    body = root.find(q("body"))
    if body is None:
        raise Fail("pandoc's default reference document has no body")
    for old in body.findall(q("sectPr")):
        body.remove(old)
    body.append(ET.fromstring(SECTION))
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def build(out):
    """Write the reference document from pandoc's default and return where it went."""
    if not shutil.which("pandoc"):
        raise Fail("pandoc is not installed, and the reference document is built from its default")
    done = subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"], capture_output=True)
    if done.returncode or not done.stdout:
        raise Fail(f"pandoc could not print its default reference document: {done.stderr.decode()[:200]}")
    ET.register_namespace("w", W)
    target = Path(out).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = target.with_suffix(".building")
    with zipfile.ZipFile(BytesIO(done.stdout)) as source, zipfile.ZipFile(scratch, "w", zipfile.ZIP_DEFLATED) as made:
        for entry in source.infolist():
            data = source.read(entry.filename)
            if entry.filename == "word/styles.xml":
                data = patch_styles(data)
            elif entry.filename == "word/document.xml":
                data = patch_document(data)
            made.writestr(entry, data)
    scratch.replace(target)
    return target


def main():
    parser = argparse.ArgumentParser(description="Build the weekly report's Word reference document.")
    parser.add_argument("--out", required=True, help="where the .docx goes")
    args = parser.parse_args()
    target = build(args.out)
    print(f"{target}: {target.stat().st_size:,} bytes, {len(PATCHES)} styles patched, half-inch margins")
    return OK


if __name__ == "__main__":
    run_main(main)
