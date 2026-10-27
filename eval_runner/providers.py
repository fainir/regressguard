"""Provider adapters for the eval runner. Each provider exposes `.complete(prompt) -> str`."""

from __future__ import annotations

import importlib
import json
import os
from typing import Protocol


DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"
DEFAULT_TIMEOUT = 60.0  # seconds per request; the SDKs default to 10 minutes


class Provider(Protocol):
    def complete(self, prompt: str) -> str: ...


class StubProvider:
    """Deterministic provider that maps prompts to canned responses.

    Used for CI/offline runs. Responses are keyed by the model input verbatim
    (post-template-render) and come from a JSON file or an in-memory mapping.
    """

    def __init__(self, responses_path: str | None = None, *, responses: dict | None = None):
        if responses is None:
            if not responses_path:
                raise ValueError("StubProvider needs a responses file or mapping")
            try:
                with open(responses_path, encoding="utf-8") as f:
                    responses = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"stub responses file {responses_path!r} is not valid JSON: {exc}") from None
        if not isinstance(responses, dict):
            raise ValueError("stub responses must be a JSON object mapping prompt -> response")
        for prompt, response in responses.items():
            if not isinstance(response, str):
                raise ValueError(f"stub response for prompt {prompt!r} must be a string")
        self._responses: dict[str, str] = responses

    def complete(self, prompt: str) -> str:
        if prompt not in self._responses:
            raise KeyError(f"stub provider has no canned response for prompt: {prompt!r}")
        return self._responses[prompt]


def _import_sdk(name: str):
    try:
        return importlib.import_module(name)
    except ImportError:
        raise RuntimeError(
            f"--provider {name} needs the {name} SDK: pip install {name}"
        ) from None


class AnthropicProvider:
    def __init__(self, model: str, api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        anthropic = _import_sdk("anthropic")  # deferred import so stub-only runs don't need the SDK

        # Transient errors (429, 5xx, connection) are retried by the SDK (2 retries with backoff).
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"), timeout=timeout)
        self._model = model

    def complete(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts)


class OpenAIProvider:
    def __init__(self, model: str, api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        openai = _import_sdk("openai")

        self._client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"), timeout=timeout)
        self._model = model

    def complete(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


def build_provider(
    kind: str,
    model: str | None,
    stub_responses: str | dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Provider:
    """Build a provider. `stub_responses` is a file path or a prompt -> response mapping."""
    if kind == "stub":
        if stub_responses is None or stub_responses == "":
            raise ValueError("--stub-responses is required with --provider stub")
        if isinstance(stub_responses, dict):
            return StubProvider(responses=stub_responses)
        return StubProvider(stub_responses)
    if kind == "anthropic":
        return AnthropicProvider(model or DEFAULT_ANTHROPIC_MODEL, timeout=timeout)
    if kind == "openai":
        if not model:
            raise ValueError("--provider openai needs --model (there is no default OpenAI model)")
        return OpenAIProvider(model, timeout=timeout)
    raise ValueError(f"unknown provider: {kind!r}")
