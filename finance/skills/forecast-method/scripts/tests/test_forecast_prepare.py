import json

import pytest
import yaml

import forecast_prepare
from _common import ForecastError
from conftest import amounts, open_vintage, write_book


def test_prepare_opens_the_newest_revision_against_the_one_before(folder):
    vdir = open_vintage(folder)
    meta = yaml.safe_load((vdir / "VINTAGE.yaml").read_text())
    assert meta["new_workbook"].endswith("rev5.xlsx") and meta["prior_workbook"].endswith("rev4.xlsx")
    evidence = json.loads((vdir / "work/source/evidence.json").read_text())["items"]
    assert [e["id"] for e in evidence] == ["E-001", "E-002", "E-003"]     # the header row plus two changes
    assert "retail chain" in evidence[1]["text"]
    assert (vdir / "work/source/pulled.md").is_file()
    assert forecast_prepare.prepare(folder)["line"].startswith("NOTHING:")


def test_evidence_ids_keep_their_meaning_and_a_changed_extract_is_kept(folder):
    vdir = open_vintage(folder)
    write_book(folder / "delivery" / "Northwind forecast rev5.xlsx", amounts(5),
               changes=[["2027-07-16", "A late change", "Controller"],
                        ["2027-07-14", "Wholesale up 8k a month from August for the new retail chain", "Sales director"]])
    result = forecast_prepare.prepare(folder, vintage="rev5")
    assert result["superseded"]
    ids = [e["id"] for e in json.loads((vdir / "work/source/evidence.json").read_text())["items"]]
    assert ids == ["E-001", "E-002", "E-003"]
    assert list((vdir / "work/source").glob("superseded-*/new.json"))


def test_a_different_workbook_for_an_existing_vintage_is_refused(folder):
    open_vintage(folder)
    with pytest.raises(ForecastError):
        forecast_prepare.prepare(folder, vintage="rev5", new=str(folder / "delivery" / "Northwind forecast rev4.xlsx"))


def test_dry_run_writes_nothing(folder, capsys):
    assert forecast_prepare.main([str(folder), "--dry-run"]) == 0
    assert capsys.readouterr().out.startswith("DRY RUN FRESH")
    assert not (folder / "vintages").exists()
