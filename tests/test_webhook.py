"""Fixture-driven tests for the webhook signature verifier + PR event handler.

Fixtures under `tests/fixtures/` are real-shape GitHub `pull_request` payloads
(one `opened`, one `synchronize`). Signatures are computed here at test time
against a per-test secret; no live GitHub call is ever made.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from webhook.handler import ActionResult, handle_pull_request_event
from webhook.verify import verify_signature


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SECRET = "test-webhook-secret-do-not-use-in-prod"


def _load(name: str) -> tuple[bytes, dict]:
    raw = (FIXTURES / name).read_bytes()
    return raw, json.loads(raw)


def _sign(payload_bytes: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class _HelloSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, pr_url: str) -> None:
        self.calls.append(pr_url)


def test_valid_signature_opened_returns_post_hello():
    raw, payload = _load("pr_opened.json")
    header = _sign(raw)

    assert verify_signature(raw, header, SECRET) is True

    spy = _HelloSpy()
    result = handle_pull_request_event(payload, hello_comment_fn=spy)

    assert result == ActionResult("post-hello", "action=opened")
    assert spy.calls == ["https://github.com/glasshouse-labs/regressguard-test/pull/42"]


def test_valid_signature_synchronize_returns_ignore():
    raw, payload = _load("pr_synchronize.json")
    header = _sign(raw)

    assert verify_signature(raw, header, SECRET) is True

    spy = _HelloSpy()
    result = handle_pull_request_event(payload, hello_comment_fn=spy)

    assert result.kind == "ignore"
    assert result.reason == "action=synchronize"
    assert spy.calls == []


def test_invalid_signature_rejected():
    raw, _ = _load("pr_opened.json")
    good = _sign(raw)
    # Flip one hex char to tamper the signature.
    tampered_hex = "0" if good[-1] != "0" else "1"
    tampered = good[:-1] + tampered_hex

    assert tampered != good
    assert verify_signature(raw, tampered, SECRET) is False

    # Also: right length, wrong secret.
    wrong_secret = _sign(raw, secret="not-the-real-secret")
    assert verify_signature(raw, wrong_secret, SECRET) is False


def test_missing_signature_header_rejected():
    raw, _ = _load("pr_opened.json")

    # Empty string, None, and malformed prefixes all return False without raising.
    assert verify_signature(raw, "", SECRET) is False
    assert verify_signature(raw, None, SECRET) is False  # type: ignore[arg-type]
    assert verify_signature(raw, "sha256=", SECRET) is False
    assert verify_signature(raw, "md5=deadbeef", SECRET) is False


def test_action_result_is_frozen():
    result = ActionResult("post-hello", "action=opened")
    with pytest.raises(Exception):
        result.kind = "ignore"  # type: ignore[misc]
