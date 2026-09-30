"""RegressGuard standalone-UI API endpoint. POST /run wraps eval_runner.cli.run_suite over HTTP; GET / serves the web UI."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from eval_runner.cli import run_suite
from eval_runner.providers import build_provider
from eval_runner.store import RunsStore


REQUIRED_FIELDS = ("prompt", "cases", "provider")
DEFAULT_DB_PATH = ".agent/regressguard.db"
WEBUI_PATH = Path(__file__).resolve().parent.parent / "webui" / "index.html"
_HTML_CACHE: str | None = None


def _read_html() -> str:
    global _HTML_CACHE
    if _HTML_CACHE is None:
        _HTML_CACHE = WEBUI_PATH.read_text(encoding="utf-8")
    return _HTML_CACHE


def _write_json(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _record_best_effort(prompt: str, cases: list, report: dict, provider: str, session_id: str) -> None:
    db_path = os.environ.get("REGRESSGUARD_DB", DEFAULT_DB_PATH)
    try:
        RunsStore(db_path).record_run(prompt, cases, report, provider, session_id)
    except Exception as exc:
        print(f"regressguard: persistence skipped ({type(exc).__name__}: {exc})", file=sys.stderr)


def handle_run(body: dict[str, Any], session_id: str = "anonymous") -> tuple[int, dict[str, Any]]:
    missing = [f for f in REQUIRED_FIELDS if f not in body]
    if missing:
        return HTTPStatus.BAD_REQUEST, {"error": f"missing required fields: {', '.join(missing)}"}

    prompt = body["prompt"]
    cases = body["cases"]
    provider_name = body["provider"]
    if not isinstance(cases, list):
        return HTTPStatus.BAD_REQUEST, {"error": "'cases' must be a list"}

    stub_responses_path = body.get("stub_responses")
    stub_responses_inline = body.get("stub_responses_inline")
    model = body.get("model", "claude-haiku-4-5-20251001")

    tmp_stub: str | None = None
    if provider_name == "stub" and not stub_responses_path and stub_responses_inline is not None:
        if not isinstance(stub_responses_inline, dict):
            return HTTPStatus.BAD_REQUEST, {"error": "'stub_responses_inline' must be a JSON object"}
        fd, tmp_stub = tempfile.mkstemp(prefix="rg-stub-", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(stub_responses_inline, f)
            stub_responses_path = tmp_stub
        except Exception:
            if tmp_stub and os.path.exists(tmp_stub):
                os.unlink(tmp_stub)
            raise

    try:
        provider = build_provider(provider_name, model, stub_responses_path)
    except Exception as exc:
        if tmp_stub and os.path.exists(tmp_stub):
            os.unlink(tmp_stub)
        return HTTPStatus.BAD_REQUEST, {"error": f"provider init failed: {type(exc).__name__}: {exc}"}

    try:
        report = run_suite(prompt, cases, provider)
    except Exception as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        if tmp_stub and os.path.exists(tmp_stub):
            os.unlink(tmp_stub)

    _record_best_effort(prompt, cases, report, provider_name, session_id)
    return HTTPStatus.OK, report


class EvalHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/run":
            _write_json(self, HTTPStatus.NOT_FOUND, {"error": "unknown path"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _write_json(self, HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON: {exc}"})
            return

        if not isinstance(body, dict):
            _write_json(self, HTTPStatus.BAD_REQUEST, {"error": "request body must be a JSON object"})
            return

        session_id = self.headers.get("X-Session-Id", "anonymous")
        status, response = handle_run(body, session_id=session_id)
        _write_json(self, status, response)

    def do_GET(self) -> None:
        if self.path == "/health":
            _write_json(self, HTTPStatus.OK, {"status": "ok"})
            return
        if self.path in ("/", "/index.html"):
            try:
                html = _read_html().encode("utf-8")
            except OSError as exc:
                _write_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"webui missing: {exc}"})
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        _write_json(self, HTTPStatus.NOT_FOUND, {"error": "unknown path"})


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = HTTPServer((host, port), EvalHandler)
    server.serve_forever()


if __name__ == "__main__":
    host = os.environ.get("REGRESSGUARD_HOST", "127.0.0.1")
    port = int(os.environ.get("REGRESSGUARD_PORT", "8787"))
    serve(host=host, port=port)
