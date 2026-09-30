"""Provider adapters for the eval runner. Each provider exposes `.complete(prompt) -> str`."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class Provider(Protocol):
    def complete(self, prompt: str) -> str: ...


class StubProvider:
    """Deterministic provider that maps prompts to canned responses.

    Used for CI/offline runs. Responses live in a JSON file keyed by the model
    input verbatim (post-template-render).
    """

    def __init__(self, responses_path: str):
        with open(responses_path) as f:
            self._responses: dict[str, str] = json.load(f)

    def complete(self, prompt: str) -> str:
        if prompt not in self._responses:
            raise KeyError(f"stub provider has no canned response for prompt: {prompt!r}")
        return self._responses[prompt]


class AnthropicProvider:
    def __init__(self, model: str, api_key: str | None = None):
        import anthropic  # deferred import so stub-only runs don't need the SDK

        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
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
    def __init__(self, model: str, api_key: str | None = None):
        import openai  # deferred import

        self._client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self._model = model

    def complete(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


def build_provider(kind: str, model: str, stub_responses: str | None = None) -> Provider:
    if kind == "stub":
        if not stub_responses:
            raise ValueError("--stub-responses is required with --provider stub")
        return StubProvider(stub_responses)
    if kind == "anthropic":
        return AnthropicProvider(model)
    if kind == "openai":
        return OpenAIProvider(model)
    raise ValueError(f"unknown provider: {kind!r}")
