import json

from conftest import make_window, slot_rows, topic_rows

import time_study_day_lint as lint


def test_a_good_day_passes_and_prints_its_hours(home, capsys):
    d = make_window(home, "2030-09-01_to_2030-09-01") / "days" / "2030-09-01"
    (d / "slots.csv").write_text(slot_rows(split_at=60))
    (d / "topics.csv").write_text(topic_rows(split_at=60))
    assert lint.main([str(d), "--domains", str(home / "domains.csv"), "--topics", str(home / "topics.csv")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("OK") and "Sleep 7.0" in out and "Fabrikam Logistics / finance 0.04" in out


def test_a_bad_day_names_every_problem(home, capsys):
    d = make_window(home, "2030-09-01_to_2030-09-01") / "days" / "2030-09-01"
    lines = slot_rows().splitlines()
    lines[50] = lines[50].replace("verified", "guessed").replace("Northwind Traders", "Contoso")
    lines[60] = lines[60].replace(",calendar,,", ",calendar,Northwind Traders:0.5;Fabrikam Logistics:0.4,")
    (d / "slots.csv").write_text("\n".join(lines[:-1]) + "\n")
    (d / "topics.csv").write_text(topic_rows().replace("00:00,Sleep,none", "00:00,Sleep,naps"))
    code = lint.main([str(d), "--domains", str(home / "domains.csv"), "--topics", str(home / "topics.csv"),
                      "--format", "json"])
    assert code == 1
    problems = " ".join(json.loads(capsys.readouterr().out)["problems"])
    for needed in ("143 rows", "tier 'guessed'", "'Contoso' is not in domains.csv", "sum to 0.9", "topic 'naps'"):
        assert needed in problems, needed


def test_lint_needs_its_arguments(home, tmp_path):
    assert lint.main([str(tmp_path)]) == 2
    assert lint.main([str(tmp_path), "--domains", str(home / "domains.csv")]) == 2
