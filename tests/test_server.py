"""HTTP surface for the eval runner. Boots the stdlib server on a random port and exercises POST /run."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

from eval_runner.server import EvalHandler, handle_run
from eval_runner.store import RunsStore


REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def server(tmp_path, monkeypatch):
    # Isolate persistence to a per-test tmp DB so the real .agent/regressguard.db
    # is never touched by the suite.
    monkeypatch.setenv("REGRESSGUARD_DB", str(tmp_path / "runs.db"))
    httpd = HTTPServer(("127.0.0.1", 0), EvalHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _post(url: str, body: bytes | str, content_type: str = "application/json", headers: dict | None = None) -> tuple[int, dict]:
    if isinstance(body, str):
        body = body.encode("utf-8")
    req_headers = {"Content-Type": content_type}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_happy_path_stub(server, tmp_path):
    stub_path = tmp_path / "stub.json"
    stub_path.write_text(json.dumps({"say hi": "hello"}))
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "stub",
        "stub_responses": str(stub_path),
    }
    status, report = _post(f"{server}/run", json.dumps(body))
    assert status == 200
    assert report["pass"] == 1
    assert report["fail"] == 0
    assert len(report["cases"]) == 1
    assert report["cases"][0]["passed"] is True


def test_invalid_json_returns_400(server):
    status, body = _post(f"{server}/run", "{ not json")
    assert status == 400
    assert "invalid JSON" in body["error"]


def test_missing_field_returns_400(server):
    body = {"prompt": "{{input}}", "cases": []}
    status, resp = _post(f"{server}/run", json.dumps(body))
    assert status == 400
    assert "provider" in resp["error"]


def test_all_fail_suite_shape(server, tmp_path):
    stub_path = tmp_path / "stub.json"
    stub_path.write_text(json.dumps({"say hi": "hello", "say bye": "later"}))
    body = {
        "prompt": "{{input}}",
        "cases": [
            {"input": "say hi", "assertions": [{"type": "exact", "value": "goodbye"}]},
            {"input": "say bye", "assertions": [{"type": "exact", "value": "goodbye"}]},
        ],
        "provider": "stub",
        "stub_responses": str(stub_path),
    }
    status, report = _post(f"{server}/run", json.dumps(body))
    assert status == 200
    assert report["pass"] == 0
    assert report["fail"] == 2
    assert all(c["passed"] is False for c in report["cases"])


def test_unknown_path_returns_404(server):
    status, body = _post(f"{server}/nope", json.dumps({}))
    assert status == 404
    assert body["error"] == "unknown path"


def test_health_endpoint(server):
    with urllib.request.urlopen(f"{server}/health", timeout=5) as resp:
        assert resp.status == 200
        assert json.loads(resp.read().decode("utf-8")) == {"status": "ok"}


def test_stub_without_responses_returns_400(server):
    body = {"prompt": "{{input}}", "cases": [], "provider": "stub"}
    status, resp = _post(f"{server}/run", json.dumps(body))
    assert status == 400
    assert "stub-responses" in resp["error"] or "stub_responses" in resp["error"]


def test_handle_run_cases_must_be_list():
    status, resp = handle_run({"prompt": "x", "cases": "not-a-list", "provider": "stub"})
    assert status == 400
    assert "cases" in resp["error"]


def test_get_root_returns_html(server):
    with urllib.request.urlopen(f"{server}/", timeout=5) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        body = resp.read().decode("utf-8")
    assert "RegressGuard" in body
    assert "<form" in body


def test_get_unknown_path_returns_404(server):
    try:
        urllib.request.urlopen(f"{server}/nope", timeout=5)
        raised = False
    except urllib.error.HTTPError as exc:
        raised = True
        assert exc.code == 404
        payload = json.loads(exc.read().decode("utf-8"))
        assert payload["error"] == "unknown path"
    assert raised


def test_stub_inline_responses_happy_path(server):
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "stub",
        "stub_responses_inline": {"say hi": "hello"},
    }
    status, report = _post(f"{server}/run", json.dumps(body))
    assert status == 200
    assert report["pass"] == 1
    assert report["fail"] == 0


def test_post_run_persists_row_to_store(server, tmp_path, monkeypatch):
    stub_path = tmp_path / "stub.json"
    stub_path.write_text(json.dumps({"say hi": "hello"}))
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "stub",
        "stub_responses": str(stub_path),
    }
    status, _ = _post(f"{server}/run", json.dumps(body), headers={"X-Session-Id": "sess-xyz"})
    assert status == 200
    db_path = os.environ["REGRESSGUARD_DB"]
    rows = RunsStore(db_path).list_runs()
    assert len(rows) == 1
    row = rows[0]
    assert row["session_id"] == "sess-xyz"
    assert row["provider"] == "stub"
    assert row["cases_count"] == 1
    assert row["pass"] == 1
    assert row["fail"] == 0
