import csv
import json

import pytest

import costing_fixtures  # noqa: F401  (puts the scripts folder on the path)
import sap_extract_normalize as sen


def test_norm_and_periods():
    assert sen.norm("Precio Estándar!") == "precio estandar"
    assert sen.period_from_tab("2026-03") == "2026-03"
    assert sen.period_from_tab("Mar 2026") == "2026-03"
    assert sen.period_from_tab("Enero 2026") == "2026-01"
    assert sen.period_from_tab("Sept") == "M09"
    assert sen.period_from_tab("03") == "M03"
    assert sen.period_from_tab("Summary") is None


def test_find_header_skips_title_rows():
    rows = [["Acme Components PPV report"], [], ["Material", "Vendor", "Variance"], ["AC-100", "Fabrikam Logistics", 5]]
    hdr, cols = sen.find_header(rows, sen.EXTRACTS["ppv"]["columns"], sen.EXTRACTS["ppv"]["required"])
    assert hdr == 2 and cols["material"] == 0 and cols["variance"] == 2


def workbook(path, tabs):
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in tabs.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)
    return path


def test_month_tabs_stacked_with_provenance_and_footer(tmp_path):
    p = workbook(tmp_path / "ppv.xlsx", {
        "Ene 2026": [["Material", "Proveedor", "Diferencia"], ["AC-100", "Northwind Traders", 12.5], [None, None, 12.5]],
        "Feb 2026": [["Part", "Supplier", "Price variance"], ["AC-200", "Fabrikam Logistics", -3]],
        "Notes": [["nothing here"]],
    })
    r = sen.normalize(p, "ppv")
    assert [x["period"] for x in r["rows"]] == ["2026-01", "2026-02"]
    assert r["rows"][0]["source_sheet"] == "Ene 2026" and r["rows"][0]["source_row"] == 2
    assert r["tabs_skipped"] == ["Notes"] and r["tabs_used"][0]["rows_skipped"] == 1


def test_extra_synonyms(tmp_path):
    p = tmp_path / "scrap.csv"
    p.write_text("﻿Item code,Rejected units\nAC-100,4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="DATA REQUEST"):
        sen.normalize(p, "scrap")
    extra = {"scrap": {"material": ["item code"], "qty": ["rejected units"]}}
    assert sen.normalize(p, "scrap", extra=extra)["rows"][0]["qty"] == "4"


def test_cli(tmp_path, capsys):
    p = tmp_path / "tb.csv"
    p.write_text("Account,Description,Balance\n5000,Materials,100\n", encoding="utf-8")
    out = tmp_path / "tb_long.csv"
    assert sen.main(["tb", str(p), "--out", str(out)]) == 0
    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["account"] == "5000" and row["source_file"] == "tb.csv"
    assert sen.main(["--types"]) == 0 and "wc-list" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        sen.main(["rates", str(p)])
    assert e.value.code == 1 and "DATA REQUEST" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        sen.main(["ppv"])
    assert e.value.code == 2
