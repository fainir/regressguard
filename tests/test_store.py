"""RunsStore pytest coverage: record + read back, auto-schema, list ordering, prompt_hash stability."""

from __future__ import annotations

import re

import pytest

from eval_runner.store import RunsStore, hash_prompt


REPORT_PASS = {"pass": 2, "fail": 0, "cases": []}
REPORT_FAIL = {"pass": 0, "fail": 1, "cases": []}


@pytest.fixture
def db(tmp_path):
    return RunsStore(tmp_path / "runs.db")


def test_record_and_read_back(db):
    row_id = db.record_run("prompt A", [{"input": "x"}, {"input": "y"}], REPORT_PASS, "stub", "sess-1")
    assert isinstance(row_id, int) and row_id > 0
    rows = db.list_runs()
    assert len(rows) == 1
    row = rows[0]
    assert row["cases_count"] == 2
    assert row["pass"] == 2
    assert row["fail"] == 0
    assert row["provider"] == "stub"
    assert row["session_id"] == "sess-1"
    assert row["prompt_hash"] == hash_prompt("prompt A")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["ts"])


def test_auto_schema_on_empty_file(tmp_path):
    path = tmp_path / "fresh.db"
    assert not path.exists()
    store = RunsStore(path)
    assert path.exists()
    assert store.count() == 0
    store.record_run("p", [], REPORT_FAIL, "openai", "sess-x")
    assert store.count() == 1


def test_list_runs_limit_and_order(db):
    for i in range(5):
        db.record_run(f"prompt {i}", [], REPORT_PASS, "stub", f"sess-{i}")
    rows = db.list_runs(limit=3)
    assert len(rows) == 3
    assert [r["session_id"] for r in rows] == ["sess-4", "sess-3", "sess-2"]


def test_prompt_hash_is_stable_and_sensitive(db):
    id_1 = db.record_run("same prompt", [], REPORT_PASS, "stub", "a")
    id_2 = db.record_run("same prompt", [], REPORT_PASS, "stub", "b")
    id_3 = db.record_run("different prompt", [], REPORT_PASS, "stub", "c")
    rows = {r["id"]: r for r in db.list_runs()}
    assert rows[id_1]["prompt_hash"] == rows[id_2]["prompt_hash"]
    assert rows[id_1]["prompt_hash"] != rows[id_3]["prompt_hash"]


def test_hash_prompt_is_sha256_hex():
    h = hash_prompt("x")
    assert re.fullmatch(r"[0-9a-f]{64}", h)
