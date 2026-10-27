"""GitHub webhook signature verification.

Verifies the `X-Hub-Signature-256` header GitHub sends alongside every webhook
delivery. See:
  https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
"""

from __future__ import annotations

import hashlib
import hmac


_SIG_PREFIX = "sha256="


def verify_signature(payload_bytes: bytes, header_value: str, secret: str) -> bool:
    """Return True iff `header_value` is a valid HMAC-SHA256 of `payload_bytes`.

    `header_value` is the raw string GitHub delivers in `X-Hub-Signature-256`,
    which is always of the form ``sha256=<hex>``. Missing / malformed headers
    return False rather than raising, so callers can treat rejection as data.

    Comparison is constant-time via `hmac.compare_digest` to avoid timing leaks.
    `payload_bytes` must be the raw request body exactly as received, not re-serialized JSON.
    An empty `secret` raises ValueError: it would make every signature forgeable.
    """
    if not secret:
        raise ValueError("webhook secret must be a non-empty string")
    if not header_value or not isinstance(header_value, str):
        return False
    if not header_value.startswith(_SIG_PREFIX):
        return False

    provided_hex = header_value[len(_SIG_PREFIX):]
    if not provided_hex or not provided_hex.isascii():
        # compare_digest raises TypeError on non-ASCII str input.
        return False

    expected_hex = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(provided_hex, expected_hex)
