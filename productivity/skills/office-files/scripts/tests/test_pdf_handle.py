import json

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text

import pdf_handle


def make_pdf(path, lines):
    """A small PDF with one page per line of text, written by hand."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for line in lines:
        stream = f"BT /F1 12 Tf 72 720 Td ({line}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        content = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    body, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    body += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(body)
    return str(path)


def test_text_reads_pages_and_comments(tmp_path, capsys):
    source = make_pdf(tmp_path / "plain.pdf", ["Fees are payable net 30", "Term is one year"])
    writer = PdfWriter(clone_from=source)
    writer.add_annotation(0, Text(text="Dana: confirm net 30", rect=(50, 550, 200, 650)))
    annotated = tmp_path / "agreement.pdf"
    writer.write(annotated)

    assert pdf_handle.main(["--operation", "text", "--pdf-path", str(annotated), "--format", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pages"] == 2 and out["empty_pages"] == 0
    assert "net 30" in out["text"][0]["text"]
    assert out["comments"][0]["text"] == "Dana: confirm net 30"
    assert out["comments"][0]["page"] == 1


def test_merge_keeps_given_order(tmp_path, capsys):
    first = make_pdf(tmp_path / "b.pdf", ["second file"])
    second = make_pdf(tmp_path / "a.pdf", ["first file", "more"])
    target = tmp_path / "merged.pdf"
    pdf_handle.main(["--operation", "merge", "-f", first, "-f", second,
                     "--output-filename", str(target)])
    assert "3 pages" in capsys.readouterr().out
    pages = PdfReader(target).pages
    assert "second file" in pages[0].extract_text()


def test_merge_needs_two_files(tmp_path):
    only = make_pdf(tmp_path / "one.pdf", ["x"])
    with pytest.raises(SystemExit) as exit_info:
        pdf_handle.main(["--operation", "merge", "-f", only, "--output-filename", "x.pdf"])
    assert exit_info.value.code == 1


def test_merge_refuses_to_overwrite_an_input(tmp_path, capsys):
    first = make_pdf(tmp_path / "a.pdf", ["keep me"])
    second = make_pdf(tmp_path / "b.pdf", ["other"])
    with pytest.raises(SystemExit) as stop:
        pdf_handle.main(["--operation", "merge", "-f", first, "-f", second, "--output-filename", first])
    assert stop.value.code == 1
    assert "keep me" in PdfReader(first).pages[0].extract_text()
