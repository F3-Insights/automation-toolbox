"""build_reference_docx.py: the Word reference document is built from pandoc's own default."""

import shutil
import zipfile

import pytest

from conftest import run


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc")


def test_the_reference_document_carries_the_house_settings(tmp_path):
    target = tmp_path / "reference.docx"
    assert run("build_reference_docx", "--out", target).returncode == 0
    with zipfile.ZipFile(target) as built:
        styles = built.read("word/styles.xml").decode()
        document = built.read("word/document.xml").decode()
    assert 'w:sz w:val="20"' in styles and 'w:color w:val="000000"' in styles
    assert 'w:left="720"' in document


def test_the_output_path_is_required():
    assert run("build_reference_docx").returncode == 2
