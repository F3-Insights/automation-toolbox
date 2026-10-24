import json

import pytest

import srt_transcript_collapse as sc

SRT = """1
00:03:12,400 --> 00:03:15,900
<v Dana>So the question is whether

2
00:03:15,900 --> 00:03:18,200
<v Dana>we move the close earlier.

3
00:03:18,500 --> 00:03:20,000
<v Sam>I think <i>yes</i>.

4
00:03:20,100 --> 00:03:21,000
And soon.
"""

VTT = """WEBVTT

01:02:03.000 --> 01:02:04.000
Priya: Hello there
"""


def test_cues_merge_by_speaker_and_strip_tags():
    turns = sc.collapse(SRT)
    assert [sc.render(t) for t in turns] == [
        "03:12 Dana: So the question is whether we move the close earlier.",
        "03:18 Sam: I think yes. And soon."]


def test_vtt_with_hours_and_name_prefix():
    assert [sc.render(t) for t in sc.collapse(VTT)] == ["1:02:03 Priya: Hello there"]


def test_not_a_transcript_raises():
    with pytest.raises(sc.NotATranscript):
        sc.parse_cues("just prose\nno timings")


def test_chunks_never_split_a_turn():
    turns = sc.collapse(SRT)
    chunks = sc.chunk(turns, 40)
    assert [len(c) for c in chunks] == [1, 1]


def test_cli_prints_text_and_json(tmp_path, capsys):
    f = tmp_path / "interview.srt"
    f.write_text(SRT)
    assert sc.main([str(f)]) == 0
    assert capsys.readouterr().out.startswith("03:12 Dana:")
    assert sc.main([str(f), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["cues"] == 4 and data["turns"] == 2 and data["speakers"] == ["Dana", "Sam"]


def test_cli_writes_out_files_and_parts(tmp_path, capsys):
    f = tmp_path / "interview.srt"
    f.write_text(SRT)
    assert sc.main([str(f), "--out", str(tmp_path / "sources")]) == 0
    assert (tmp_path / "sources" / "interview.txt").read_text().startswith("03:12 Dana:")
    assert sc.main([str(f), "--chunk-bytes", "40", "--out", str(tmp_path / "parts")]) == 0
    assert sorted(p.name for p in (tmp_path / "parts").iterdir()) == ["interview.part01.txt", "interview.part02.txt"]


def test_cli_errors_exit_2(tmp_path):
    bad = tmp_path / "notes.srt"
    bad.write_text("no cues here")
    assert sc.main([str(bad)]) == 2
    assert sc.main([str(tmp_path / "missing.srt")]) == 2
