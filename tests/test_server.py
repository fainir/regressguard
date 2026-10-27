"""HTTP surface for the eval runner. Boots the stdlib server on a random port and exercises POST /run."""

from __future__ import annotations

import json
import os
import http.client
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from eval_runner import server as server_module
from eval_runner.server import MAX_BODY_BYTES, handle_run, make_server
from eval_runner.store import RunsStore


REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def server(tmp_path, monkeypatch):
    # Isolate persistence to a per-test tmp DB so a real regressguard.db
    # is never touched by the suite.
    monkeypatch.setenv("REGRESSGUARD_DB", str(tmp_path / "runs.db"))
    httpd = make_server("127.0.0.1", 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
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


def test_happy_path_stub(server):
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


def test_all_fail_suite_shape(server):
    body = {
        "prompt": "{{input}}",
        "cases": [
            {"input": "say hi", "assertions": [{"type": "exact", "value": "goodbye"}]},
            {"input": "say bye", "assertions": [{"type": "exact", "value": "goodbye"}]},
        ],
        "provider": "stub",
        "stub_responses_inline": {"say hi": "hello", "say bye": "later"},
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


def test_post_run_persists_row_to_store(server):
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "stub",
        "stub_responses_inline": {"say hi": "hello"},
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


def test_server_side_stub_path_is_rejected(server, tmp_path):
    # Accepting a path let any client make the server read any JSON file it can access.
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"say hi": "hello"}))
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "stub",
        "stub_responses": str(secret),
    }
    status, resp = _post(f"{server}/run", json.dumps(body))
    assert status == 400
    assert "stub_responses_inline" in resp["error"]


def _post_with_content_length(server: str, length: str) -> tuple[int, dict]:
    """Send only the headers, so the server must decide from Content-Length alone."""
    host, port = server.removeprefix("http://").split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.putrequest("POST", "/run")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", length)
        conn.endheaders()
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    finally:
        conn.close()


def test_oversized_body_returns_413_without_reading_it(server):
    status, resp = _post_with_content_length(server, str(MAX_BODY_BYTES + 1))
    assert status == 413
    assert "too large" in resp["error"]


@pytest.mark.parametrize("length", ["abc", "-5"])
def test_bad_content_length_returns_400(server, length):
    status, resp = _post_with_content_length(server, length)
    assert status == 400
    assert "Content-Length" in resp["error"]


@pytest.mark.parametrize(
    "patch, needle",
    [
        ({"prompt": 5}, "prompt"),
        ({"model": 5}, "model"),
        ({"cases": [{"input": "say hi", "assertions": []}]}, "assertions"),
        ({"cases": [{"input": "say hi", "assertions": [{"type": "regex", "value": "("}]}]}, "invalid regex"),
        ({"stub_responses_inline": {"say hi": 1}}, "must be a string"),
    ],
)
def test_invalid_run_request_returns_400_not_500(server, patch, needle):
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "stub",
        "stub_responses_inline": {"say hi": "hello"},
    }
    body.update(patch)
    status, resp = _post(f"{server}/run", json.dumps(body))
    assert status == 400, resp
    assert needle in resp["error"]


def test_health_answers_while_a_slow_run_is_in_flight(server, monkeypatch):
    # The single-threaded server blocked every request (including the Docker
    # HEALTHCHECK) for as long as one LLM run took.
    started, release = threading.Event(), threading.Event()

    class SlowProvider:
        def complete(self, prompt: str) -> str:
            started.set()
            release.wait(10)
            return "hello"

    monkeypatch.setattr(server_module, "build_provider", lambda *a, **k: SlowProvider())
    body = {
        "prompt": "{{input}}",
        "cases": [{"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]}],
        "provider": "anthropic",
    }
    result: dict = {}
    worker = threading.Thread(target=lambda: result.update(r=_post(f"{server}/run", json.dumps(body))))
    worker.start()
    try:
        assert started.wait(5)
        with urllib.request.urlopen(f"{server}/health", timeout=2) as resp:
            assert resp.status == 200
    finally:
        release.set()
        worker.join(10)
    assert result["r"][0] == 200
