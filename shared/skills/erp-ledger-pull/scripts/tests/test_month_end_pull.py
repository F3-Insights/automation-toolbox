"""month_end_pull.py on an invented Month-End folder for Lakeview Hardware. Offline; the live
path runs through a fake session and any network call fails the test."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
import _common
import month_end_pull as mep

PERIOD = "2026-05"
PULLED = "2026-06-02T07:00:00+00:00"
ACCOUNTS = {"1010": ("Bank", "balanceSheet", "debit"), "2010": ("Payables", "balanceSheet", "credit"),
            "3010": ("Capital", "balanceSheet", "credit"), "4010": ("Sales", "incomeStatement", "credit"),
            "6010": ("Utilities", "incomeStatement", "debit")}
SYSTEMS = """# Systems

## Close inputs

- ERP: {erp}
- Ledger pull: work/source
- Headerless line creators: feed-user
{extra}
## Access notes

Nothing secret lives here.
"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a test tried to reach the network")
    monkeypatch.setattr(_common, "http_json", refuse)


def write(path, rows, meta=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta or {}, "rows": rows}))
    return path


def gl(je, account, side, amount, day=f"{PERIOD}-31", creator="dana"):
    return {"id": f"{je}-{account}", "journalEntry.key": je, "glAccount.id": account, "entryDate": day,
            "txnType": side, "baseAmount": amount, "journalEntry.state": "posted", "audit.createdBy": creator,
            "journalEntry.glJournal.id": "GJ"}


def pair(je, dr, cr, amount, day=f"{PERIOD}-31", creator="dana"):
    return [gl(je, dr, "debit", amount, day, creator), gl(je, cr, "credit", amount, day, creator)]


BRIDGE = pair("B9", "6010", "1010", "80.00", "2026-03-15")
LATE = pair("L1", "6010", "2010", "35.00", "2026-04-30")  # entered after the bridge was taken
MAY = pair("51", "1010", "4010", "900.00") + pair("52", "6010", "2010", "80.00") + \
      pair("53", "1010", "4010", "15.00", creator="feed-user")


def month_end(tmp_path, erp="Sage Intacct", tb=False):
    folder = tmp_path / "Lakeview Month-End"
    folder.mkdir()
    extra = ""
    if tb:
        extra = ("- Trial balance history: ref/history.json\n- Trial balance bridge: ref/bridge.json\n"
                 "- Chart of accounts: ref/accounts.json\n")
        write(folder / "ref" / "accounts.json",
              [{"id": k, "name": v[0], "accountType": v[1], "normalBalance": v[2]} for k, v in ACCOUNTS.items()])
        write(folder / "ref" / "history.json", pair("H1", "1010", "3010", "2000.00", "2025-12-31"))
        write(folder / "ref" / "bridge.json", BRIDGE, {"pulled-at": "2026-04-02T00:00:00+00:00", "filters": [
            {"$gte": {"entryDate": "2026-01-01"}}, {"$lte": {"entryDate": "2026-04-02"}}]})
    (folder / "SYSTEMS.md").write_text(SYSTEMS.format(erp=erp, extra=extra))
    return folder


def export(directory, lines=None, lines_total=None, window=()):
    headers = [{"id": k, "key": k} for k in ("51", "52")]
    lines = MAY if lines is None else lines
    data = {"headers": headers, "lines": lines, "ap-bill-lines": [{"id": "A1", "bill.postingDate": f"{PERIOD}-12"}],
            "ar-invoice-lines": [{"id": "R1", "invoice.invoiceDate": f"{PERIOD}-20"}]}
    for name, rows in data.items():
        total = lines_total if name == "lines" and lines_total is not None else len(rows)
        write(directory / f"{name}-{PERIOD}.json", rows, {"pulled-at": PULLED, "server-total-count": total})
    if window:
        write(directory / f"lines-window-{PERIOD}.json", list(window), {"pulled-at": PULLED, "filters": [
            {"$gte": {"entryDate": "2026-01-01"}}, {"$lte": {"entryDate": f"{PERIOD}-31"}}]})
    return directory


def run(*args, capsys):
    code = mep.main([str(a) for a in args])
    return code, capsys.readouterr().out.splitlines()


def source(folder):
    return folder / PERIOD[:4] / PERIOD / "work" / "source"


def test_a_fresh_offline_pull_puts_the_files_in_place(tmp_path, capsys):
    folder = month_end(tmp_path)
    code, out = run(folder, "--period", PERIOD, "--offline-from", export(tmp_path / "x"), "--today", "2026-06-02",
                    capsys=capsys)
    assert code == 0
    assert out[0].startswith("FRESH: pulled 2026-06-02 JE headers 2, JE lines 6, AP bill lines 1, "
                             "AR invoice lines 1; PRELIMINARY; TB not rebuilt: SYSTEMS.md sets no")
    text = (source(folder) / "pulled.md").read_text()
    assert text.startswith("# Pulled data, 2026-05 (PRELIMINARY, period may still be open)")
    assert "2 line(s) in 1 entry have no header" in text and "JE lines 6 of 6" in text
    assert not list(source(folder).parent.glob(".pull-staging-*"))


def test_a_gate_failure_keeps_the_old_pull(tmp_path, capsys):
    folder = month_end(tmp_path)
    write(source(folder) / f"lines-{PERIOD}.json", [])
    (source(folder) / "pulled.md").write_text("Pulled 2026-06-01 by hand.\n")
    before = {p.name: p.read_bytes() for p in source(folder).iterdir()}
    code, out = run(folder, "--period", PERIOD, "--offline-from", export(tmp_path / "x", lines_total=9),
                    "--today", "2026-06-02", capsys=capsys)
    assert code == 0
    assert out[0] == "STALE: gate counts_tie failed on lines: 6 row(s) but the server reported 9; using the pull of 2026-06-01"
    assert {p.name: p.read_bytes() for p in source(folder).iterdir()} == before


def test_an_empty_month_is_refused_and_its_folders_removed(tmp_path, capsys):
    folder = month_end(tmp_path)
    code, out = run(folder, "--period", PERIOD, "--offline-from", export(tmp_path / "x", lines=[]),
                    "--today", "2026-06-02", capsys=capsys)
    assert code == 0 and out[0].startswith("STALE: gate lines_present failed")
    assert not (folder / "2026").exists()


def test_a_second_pull_supersedes_the_first(tmp_path, capsys):
    folder = month_end(tmp_path)
    for _ in range(2):
        run(folder, "--period", PERIOD, "--offline-from", export(tmp_path / "x"), "--today", "2026-07-30",
            capsys=capsys)
    assert len(list(source(folder).glob("superseded-*"))) == 1
    assert "(FINAL)" in (source(folder) / "pulled.md").read_text().splitlines()[0]


def test_the_trial_balance_is_rebuilt_from_an_offline_window(tmp_path, capsys):
    folder = month_end(tmp_path, tb=True)
    code, out = run(folder, "--period", PERIOD, "--offline-from",
                    export(tmp_path / "x", window=BRIDGE + LATE + MAY), "--today", "2026-06-02", capsys=capsys)
    assert code == 0 and out[0].endswith("TB rebuilt (5 accounts, balanced)"), out[0]
    result = json.loads((source(folder) / f"trial-balance-{PERIOD}.json").read_text())
    assert {r["Account"]: r["Ending balance"] for r in result["rows"]}["6010"] == 80 + 35 + 80
    assert (source(folder) / f"trial-balance-{PERIOD}.xlsx").stat().st_size > 0
    assert not list(source(folder).glob("lines-window-*"))


class Fake:
    def __init__(self, data, extra=0):
        self.data, self.calls, self.extra = data, [], extra

    def query(self, obj, fields, filters=None, order_by=None, **_):
        self.calls.append((obj, filters))
        rows = self.data[obj]
        if filters:
            (field, lo), = filters[0]["$gte"].items()
            (_, hi), = filters[1]["$lte"].items()
            rows = [r for r in rows if field not in r or lo <= r[field] <= hi]
        return rows, len(rows) + (self.extra if obj.endswith("entry-line") else 0)


def erp(tmp_path, lines):
    x = export(tmp_path / "erp", lines=lines)
    names = {"headers": "general-ledger/journal-entry", "lines": "general-ledger/journal-entry-line",
             "ap-bill-lines": "accounts-payable/bill-line", "ar-invoice-lines": "accounts-receivable/invoice-line"}
    return {obj: json.loads((x / f"{n}-{PERIOD}.json").read_text())["rows"] for n, obj in names.items()}


def live(folder, fake, hour=7):
    return mep.refresh(folder, PERIOD, True, None, "", 15, datetime(2026, 6, 2, hour, tzinfo=timezone.utc),
                       lambda env, user: (mep.ReadOnlySession(fake), ["northwind-secret"]))


def test_a_live_pull_uses_one_window_query_and_catches_late_entries(tmp_path):
    folder = month_end(tmp_path, tb=True)
    fake = Fake(erp(tmp_path, BRIDGE + LATE + MAY))
    result = live(folder, fake)
    assert result["status"] == "FRESH" and result["line"].endswith("TB rebuilt (5 accounts, balanced)"), result["line"]
    lines_calls = [f for o, f in fake.calls if o.endswith("entry-line")]
    assert lines_calls == [[{"$gte": {"entryDate": "2026-01-01"}}, {"$lte": {"entryDate": "2026-05-31"}}]]
    sliced = json.loads((source(folder) / f"lines-{PERIOD}.json").read_text())
    assert all(r["entryDate"].startswith(PERIOD) for r in sliced["rows"]) and sliced["meta"]["server-total-count"] == 6
    assert "Read-only pull from Sage Intacct PROD" in (source(folder) / "pulled.md").read_text()


def test_the_window_is_gated_and_a_swing_is_reported(tmp_path):
    folder = month_end(tmp_path, tb=True)
    assert live(folder, Fake(erp(tmp_path, BRIDGE + MAY)))["status"] == "FRESH"
    second = live(folder, Fake(erp(tmp_path, BRIDGE + LATE + MAY)), hour=8)
    assert second["line"].endswith("vs the previous TB: 2 account(s) changed, YTD net income 755.00 -> 720.00 (-35.00)")
    third = live(folder, Fake(erp(tmp_path, BRIDGE + MAY), extra=1), hour=9)
    assert third["line"].startswith("STALE: gate counts_tie failed on tb_lines")


def test_an_api_error_is_stale_and_scrubbed(tmp_path):
    class Broken:
        def query(self, *a, **k):
            raise _common.IntacctError("token northwind-secret refused", 401)

    result = mep.refresh(month_end(tmp_path), PERIOD, True, None, "", 15, datetime(2026, 6, 2, tzinfo=timezone.utc),
                         lambda env, user: (Broken(), ["northwind-secret"]))
    assert result["line"].startswith("STALE: the pull failed: IntacctError: token *** refused (HTTP 401)")


def test_missing_credentials_are_stale_with_exit_zero(tmp_path, monkeypatch, capsys):
    for name in ("CLIENT_ID", "CLIENT_SECRET", "COMPANY_ID", "API_USER"):
        monkeypatch.delenv(f"SAGE_INTACCT_{name}", raising=False)
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    code, out = run(month_end(tmp_path), "--period", PERIOD, "--live", "--today", "2026-06-02", capsys=capsys)
    assert code == 0 and out[0].startswith("STALE: no Sage Intacct credentials: set SAGE_INTACCT_CLIENT_ID")


def test_other_erps_and_bad_arguments(tmp_path, capsys):
    code, out = run(month_end(tmp_path, erp="Business Central"), "--period", PERIOD, "--live", capsys=capsys)
    assert code == 0 and out[0].startswith("STALE: no puller for Business Central")
    plain = tmp_path / "plain"
    plain.mkdir()
    assert mep.main([str(plain), "--period", PERIOD, "--live"]) == 2
    assert mep.main([str(plain), "--period", "2026-13", "--live"]) == 2
    assert mep.main([str(plain), "--offline-from", str(tmp_path / "nowhere")]) == 2


def test_the_script_names_no_machine_or_person():
    text = Path(mep.__file__).read_text(encoding="utf-8")
    for word in ("/home/", "/Users/", "OneDrive", "—"):
        assert word not in text


def test_a_trial_balance_that_hangs_is_a_note_not_a_crash(tmp_path, monkeypatch):
    def hang(*a, **k):
        raise mep.subprocess.TimeoutExpired("trial_balance.py", 900)
    monkeypatch.setattr(mep.subprocess, "run", hang)
    folder = month_end(tmp_path, tb=True)
    result = live(folder, Fake(erp(tmp_path, BRIDGE + LATE + MAY)))
    assert result["status"] == "FRESH" and "TB not rebuilt: TimeoutExpired" in result["line"], result["line"]
    assert not (source(folder) / f"trial-balance-{PERIOD}.json").exists()
