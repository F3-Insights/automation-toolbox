import time_study_tool as tl


def test_the_tool_finds_its_checkout_beside_the_home_and_saves_output(home, tmp_path):
    saved = tmp_path / "summary.txt"
    assert tl.main(["--save", str(saved), str(home), "summary"]) == 0
    assert saved.read_text() == "Summary: 9 days studied\n"
    assert (home / "calls.log").read_text().strip() == "summary"


def test_extra_arguments_pass_through(home):
    assert tl.main([str(home), "build", "--lenient-topics"]) == 0
    assert (home / "calls.log").read_text().strip() == "build --lenient-topics"


def test_unknown_command_or_missing_checkout_exits_2(home, tmp_path):
    assert tl.main([str(home), "rm"]) == 2
    lonely = tmp_path / "elsewhere"
    lonely.mkdir()
    assert tl.main([str(lonely), "build"]) == 2
    assert tl.main(["--repo", str(tmp_path), str(home), "build"]) == 2
