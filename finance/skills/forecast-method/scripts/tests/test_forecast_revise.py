import json
import zipfile

import pytest
import yaml

import forecast_prepare
import forecast_revise
from _common import ForecastError, build_bridge, file_sha
from conftest import MONTHS, amounts, open_vintage


def write_upload_book(path):
    """An upload-shaped sheet: identity columns, then one column per month."""
    from openpyxl import Workbook
    book = Workbook()
    ws = book.active
    ws.title = "Upload"
    ws.append(["PLAN_ID", "GL", "DEPT", "SITE", "CLASS"] + [f"Month Ended {d:%B %Y}" for d in MONTHS])
    for account, (name, values) in amounts(4).items():
        if account == "41000":
            ws.append(["FCST", int(account), "SALES", "N1", "blank"] + [v / 2 for v in values])
            ws.append(["FCST", int(account), "SALES", "N2", "blank"] + [v / 2 for v in values])
        else:
            ws.append(["FCST", int(account), "blank", "N1", "blank"] + list(values))
    ws["F12"] = "=2+2"
    book.save(path)
    return path


def rolling_folder(folder):
    settings = yaml.safe_load((folder / "FORECAST-SETTINGS.yaml").read_text())
    settings["layouts"]["upload"] = {"sheet": "Upload", "header_row": 1, "blank_token": "blank",
                                     "columns": {"account": "GL", "department": "DEPT", "location": "SITE", "cls": "CLASS"}}
    settings["layouts"]["default"] = settings["layouts"]["upload"]
    settings["revise"] = {"layout": "upload", "name": "{vintage} forecast DRAFT.xlsx"}
    (folder / "FORECAST-SETTINGS.yaml").write_text(yaml.safe_dump(settings))
    return write_upload_book(folder / "delivery" / "Northwind forecast 2027-09 v1.xlsx")


def test_a_rolling_vintage_is_built_as_a_values_copy_and_bridged(folder):
    prior = rolling_folder(folder)
    before = file_sha(prior)
    opened = forecast_prepare.prepare(folder, vintage="2027-10", prior=str(prior), kind="rolling", last_actual="2027-09")
    assert "not built yet" in opened["line"]
    vdir = folder / "vintages" / "2027-10"
    rows = [{"account": "41000", "department": "SALES", "location": "N1", "amounts": {"2027-10": 46000.0, "2027-11": 46000.0},
             "node": "retail chain"},
            {"account": "42000", "department": "", "location": "N3", "amounts": {"2027-12": 2000.0}, "node": "new site"},
            {"account": "51000", "department": "", "location": "N1", "amounts": {"2027-03": 1.0}}]
    (vdir / "proposals.json").write_text(json.dumps({"rows": rows}))
    with pytest.raises(ForecastError, match="closed"):
        forecast_revise.revise(folder, "2027-10")
    (vdir / "proposals.json").write_text(json.dumps({"rows": rows[:2]}))
    assert forecast_revise.main([str(folder), "--vintage", "2027-10"]) == 0
    assert file_sha(prior) == before                                      # the prior is only read
    assert (vdir / "change-log.csv").read_text().count("\n") == 4          # header plus three cells
    assert "FCST" in (vdir / "upload.csv").read_text()
    forecast_prepare.prepare(folder, vintage="2027-10")
    walk = {l["key"]: l["amount"] for l in build_bridge(folder, "2027-10")["years"]["2027"]["walk"]}
    assert walk["actuals"] == 0.0
    assert walk["revenue"] == 2 * (46000.0 - 40000.0) + 2000.0


def test_revise_refuses_dynamic_arrays_and_issued_revisions(folder, tmp_path):
    open_vintage(folder)
    with pytest.raises(ForecastError, match="only a rolling vintage"):
        forecast_revise.revise(folder, "rev5")
    prior = rolling_folder(folder)
    forecast_prepare.prepare(folder, vintage="2027-10", prior=str(prior), kind="rolling", last_actual="2027-09")
    patched = tmp_path / "with-arrays.xlsx"
    with zipfile.ZipFile(prior) as src, zipfile.ZipFile(patched, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr("xl/metadata.xml", "<metadata/>")
    meta_path = folder / "vintages/2027-10/VINTAGE.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta_path.write_text(yaml.safe_dump(dict(meta, prior_workbook=str(patched))))
    (folder / "vintages/2027-10/proposals.json").write_text(json.dumps({"rows": []}))
    with pytest.raises(ForecastError, match="dynamic-array"):
        forecast_revise.revise(folder, "2027-10")
