"""intacct_snapshot.py and the gates in _common.py, offline, on invented Fabrikam Logistics data."""

import json
import subprocess
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
import _common
import intacct_snapshot as snap

SCRIPT = snap.__file__
T0 = "2026-06-01T09:00:00+00:00"


def write(path, rows, total=None, pulled=T0):
    meta = {"pulled-at": pulled}
    if total is not None:
        meta["server-total-count"] = total
    path.write_text(json.dumps({"meta": meta, "rows": rows}))
    return path


def export(tmp_path, orphan_creator="ops-bot"):
    folder = tmp_path / "export"
    folder.mkdir()
    write(folder / "headers-2026-05.json", [{"id": "501", "key": "501"}], 1)
    lines = [{"id": "1", "journalEntry.key": "501"},
             {"id": "2", "journalEntry.key": "999", "audit.createdBy": orphan_creator}]
    write(folder / "lines-2026-05.json", lines, 2)
    return folder


def test_gates():
    objs = [{"name": "a", "rows": 3, "server_total": 3, "pulled_at": T0},
            {"name": "b", "rows": 3, "server_total": 4, "pulled_at": "2026-06-02T09:00:00+00:00"},
            {"name": "c", "rows": 1, "server_total": None, "pulled_at": ""}]
    counts = _common.gate_counts(objs)
    assert [f["object"] for f in counts] == ["b", "c"] and "unverifiable" in counts[1]["detail"]
    assert _common.gate_vintage(objs)[0]["object"] == "b"
    orphan = _common.gate_lines_have_headers([{"journalEntry.key": "9", "audit.createdBy": "bot"}], [], ["bot"])
    assert orphan[0]["severity"] == "info"


def test_merging_dedupes_and_keeps_the_oldest_vintage(tmp_path):
    a = write(tmp_path / "a.json", [{"id": "1"}, {"id": "2"}], 2, "2026-06-01T10:00:00+00:00")
    b = write(tmp_path / "b.json", [{"id": "2"}, {"id": "3"}], 2, "2026-06-01T09:30:00+00:00")
    rows, meta = snap.merge_sources(_common.OBJECTS["lines"], [a, b])
    assert [r["id"] for r in rows] == ["1", "2", "3"]
    assert meta["pulled-at"] == "2026-06-01T09:30:00+00:00" and meta["server-total-count"] == 3


def test_pull_live_with_a_fake_session(tmp_path):
    class Fake:
        calls = []

        def query(self, obj, fields, filters=None, order_by=None):
            self.calls.append((obj, filters))
            return [{"id": "1"}], 1

    fake = Fake()
    pulled = _common.pull_live(fake, "2026-05", 2, tmp_path, _common.OBJECTS, ["lines", "ap_bill_lines_next"],
                               today="2026-06-03")
    assert fake.calls[0][1] == [{"$gte": {"entryDate": "2026-03-01"}}, {"$lte": {"entryDate": "2026-05-31"}}]
    assert fake.calls[1][1][0] == {"$gte": {"bill.postingDate": "2026-06-01"}}
    assert (tmp_path / "lines-2026-05.json").is_file() and pulled[0]["server_total"] == 1


def test_a_known_integration_passes_and_a_stranger_fails(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"known_creators": ["ops-bot"]}))
    base = [sys.executable, SCRIPT, "--period", "2026-05", "--out", str(tmp_path / "out"), "--config", str(cfg)]
    done = subprocess.run(base + ["--snapshot-dir", str(export(tmp_path)), "--format", "json"],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["passed"] is True
    other = tmp_path / "second"
    other.mkdir()
    done = subprocess.run(base + ["--snapshot-dir", str(export(other, "someone"))], capture_output=True, text=True)
    assert done.returncode == 1 and "FAIL" in done.stdout


def test_neither_live_nor_a_folder_is_a_bad_argument(tmp_path):
    done = subprocess.run([sys.executable, SCRIPT, "--period", "2026-05", "--out", str(tmp_path)],
                          capture_output=True, text=True)
    assert done.returncode == 2
