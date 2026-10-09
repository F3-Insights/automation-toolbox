"""report_facts.py: figures and tables, none of them from a model. Invented figures only."""

import json

import pytest

from conftest import PERIOD, run


PASTED = "| Line | October | September |\n|---|---:|---:|\n| Revenue | 4,812,000 | 4,455,000 |\n" \
         "| Operating Income | 677,300 | 505,100 |\n"


@pytest.fixture


def facts(tmp_path, store):
    path = tmp_path / "facts.json"
    assert run("report_facts", "init", "--facts", path, "--period", PERIOD, "--profile", store / "profile.md").returncode == 0
    return path


def test_init_seeds_every_standing_metric_unanswered(facts):
    figures = json.loads(facts.read_text())["figures"]
    assert set(figures) == {"close_days", "cash_on_hand"}
    assert all(f["value"] is None and f["reason"] == "not supplied" for f in figures.values())


def test_a_figure_needs_its_date_and_status_and_may_be_not_available(facts):
    assert run("report_facts", "set", "--facts", facts, "--key", "cash_on_hand", "--value", "1840000",
               "--as-of", PERIOD, "--status", "final").returncode == 0
    assert run("report_facts", "set", "--facts", facts, "--key", "close_days", "--not-available", "--reason",
               "the close is not signed off", "--unit", "days", "--as-of", PERIOD, "--status", "preliminary").returncode == 0
    bad = run("report_facts", "set", "--facts", facts, "--key", "x", "--value", "lots", "--as-of", PERIOD,
              "--status", "final")
    assert bad.returncode == 2 and "could not be read as a number" in bad.stderr
    figures = json.loads(facts.read_text())["figures"]
    assert figures["cash_on_hand"]["source"] == "the executive at Gate 2"
    assert figures["close_days"]["value"] is None and "not signed off" in figures["close_days"]["reason"]


def test_a_pasted_table_goes_in_verbatim_from_standard_input(facts):
    done = run("report_facts", "add-table", "--facts", facts, "--key", "october", "--title", "October results",
               "--as-of", "2027-10-31", stdin=PASTED)
    assert done.returncode == 0, done.stderr
    table = json.loads(facts.read_text())["tables"]["october"]
    assert table["kind"] == "supplied" and table["source"] == "supplied by the executive"
    assert [r["label"] for r in table["rows"]] == ["Revenue", "Operating Income"]
    assert table["rows"][1]["cells"]["c2"] == {"text": "677,300", "value": 677300.0}


def test_an_imported_table_computes_variances_and_refuses_one_that_does_not_foot(tmp_path, facts):
    good = tmp_path / "results.csv"
    good.write_text("row,type,components,favourable,percent_of_revenue,actual,budget,forecast\n"
                    "Revenue,amount,,higher,no,1000,900,950\nCosts,amount,,lower,yes,600,500,550\n"
                    "Margin,subtotal,Revenue;-Costs,higher,no,400,400,400\n")
    done = run("report_facts", "import-table", "--facts", facts, "--key", "results", "--csv", good, "--source",
               "the close package", "--as-of", "2027-10-31", "--status", "final", "--json")
    assert done.returncode == 0, done.stderr
    rows = {r["label"]: r for r in json.loads(done.stdout)["rows"]}
    assert rows["Revenue"]["cells"]["vs_budget"] == {"value": 100.0, "unit": "usd", "favourable": True}
    assert rows["Costs"]["cells"]["vs_budget_pct"]["value"] == 20.0 and not rows["Costs"]["cells"]["vs_budget"]["favourable"]
    assert rows["% of revenue"]["cells"]["actual"]["value"] == 60.0
    broken = tmp_path / "broken.csv"
    broken.write_text(good.read_text().replace("Margin,subtotal,Revenue;-Costs,higher,no,400", "Margin,subtotal,Revenue;-Costs,higher,no,450"))
    done = run("report_facts", "import-table", "--facts", facts, "--key", "x", "--csv", broken, "--source", "s",
               "--as-of", "2027-10-31", "--status", "final")
    assert done.returncode == 2 and "does not foot" in done.stderr


def test_validate_and_the_tie_out_at_the_precision_the_prose_used(tmp_path, facts):
    run("report_facts", "add-table", "--facts", facts, "--key", "october", "--title", "October results",
        "--as-of", "2027-10-31", stdin=PASTED)
    run("report_facts", "set", "--facts", facts, "--key", "cash_on_hand", "--value", "1840000", "--as-of", PERIOD,
        "--status", "final")
    assert run("report_facts", "validate", "--facts", facts).returncode == 0
    report = tmp_path / "draft.md"
    report.write_text("## Cash and collections\n\n- **Cash:** $1.8M on hand (facts://cash_on_hand).\n\n"
                      "{{table:october}}\n\n- **Results:** operating income of $677,300.\n")
    assert run("report_facts", "tie-out", "--facts", facts, "--report", report).returncode == 0
    report.write_text(report.read_text() + "- **Wrong:** operating income was $690,000.\n")
    done = run("report_facts", "tie-out", "--facts", facts, "--report", report, "--json")
    assert done.returncode == 3
    assert [f["kind"] for f in json.loads(done.stdout)["findings"]] == ["FIGURE_NOT_IN_FACTS"]
