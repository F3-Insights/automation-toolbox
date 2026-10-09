import find_contact as fc
from reply_fixtures import portal, run  # noqa: F401  (portal is a fixture)


def test_one_exact_match_is_pinned_and_near_matches_are_only_listed(portal, capsys):
    code, out = run(fc, capsys, "Dana Whitfield")
    assert code == 0 and out["verdict"] == "one"
    assert out["pinned"] == {"contact_id": "c-dana", "name": "Dana Whitfield", "addresses": ["dana@acme.test"]}
    assert [x["match"] for x in out["candidates"]] == ["exact", "partial"]


def test_two_exact_matches_are_never_chosen_between(portal, capsys):
    code, out = run(fc, capsys, "Sam Ortiz")
    assert code == 3 and out["verdict"] == "several" and out["pinned"] is None and out["exact_count"] == 2


def test_near_matches_alone_pin_nobody(portal, capsys):
    code, out = run(fc, capsys, "Dana Whitf")
    assert code == 3 and out["verdict"] == "partial" and out["pinned"] is None


def test_nobody(portal, capsys):
    code, out = run(fc, capsys, "Marcus Nobody")
    assert code == 3 and out["verdict"] == "none"


def test_an_address_matches_its_contact_exactly(portal, capsys):
    code, out = run(fc, capsys, "DANA@acme.test")
    assert code == 0 and out["pinned"]["contact_id"] == "c-dana"


def test_names_compare_without_case_accents_or_punctuation():
    assert fc.norm_name("  José  O'Brien ") == fc.norm_name("jose o brien")


def test_a_missing_setting_is_an_error_not_a_none(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    code, out = run(fc, capsys, "Dana Whitfield")
    assert code == 2 and "portal_mcp_config" in out["reason"]
