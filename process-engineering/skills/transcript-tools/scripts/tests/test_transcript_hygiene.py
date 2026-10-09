import json

import transcript_hygiene as th

SRT = "1\n00:00:01,000 --> 00:00:02,000\n<v Jordan>Welcome to the vendor review for Lakeview Hardware.\n"
TXT = "00:01 Jordan: Welcome to the vendor review for Lakeview Hardware.\n"


def test_name_date_and_stem_key():
    assert th.name_date("Review 2026-09-14.txt") == "2026-09-14"
    assert th.name_date("review_20260914.srt") == "2026-09-14"
    assert th.name_date("review 2026-13-40.txt") is None
    assert th.name_date("review.txt") is None
    assert th.stem_key("Vendor_Review.transcript.txt") == "vendor review"


def test_fingerprint_ignores_timestamps_and_voice_tags(tmp_path):
    a, b = tmp_path / "a.srt", tmp_path / "b.txt"
    a.write_text(SRT)
    b.write_text("00:01 Welcome to the vendor review for Lakeview Hardware.\n")
    assert th.fingerprint(a) == "welcome to the vendor review for lakeview hardware."
    assert th.fingerprint(b) == th.fingerprint(a)


def test_name_duplicates_prefer_the_text_copy(tmp_path):
    (tmp_path / "Review 2026-09-14.srt").write_text(SRT)
    (tmp_path / "Review 2026-09-14.txt").write_text(TXT)
    r = th.scan(tmp_path)
    assert len(r["duplicate_sets"]) == 1
    d = r["duplicate_sets"][0]
    assert d["by"] == "name" and d["canonical"].endswith(".txt") and d["others"][0].endswith(".srt")
    assert r["undated"] == []


def test_content_duplicate_across_names_and_undated(tmp_path):
    (tmp_path / "Vendor call 2026-09-14.md").write_text("Some notes that are long enough to stand alone here.")
    (tmp_path / "copy of call.md").write_text("Some notes that are long enough to stand alone here.")
    r = th.scan(tmp_path)
    assert [d["by"] for d in r["duplicate_sets"]] == ["content"]
    assert [p.split("/")[-1] for p in r["undated"]] == ["copy of call.md"]


def test_cli_text_json_and_missing_folder(tmp_path, capsys):
    (tmp_path / "Kickoff 2026-09-01.txt").write_text(TXT)
    assert th.main([str(tmp_path)]) == 0
    assert "Clean: no duplicates" in capsys.readouterr().out
    assert th.main([str(tmp_path), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["files"] == 1
    assert th.main([str(tmp_path / "missing")]) == 2
