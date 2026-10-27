"""Provider construction: stub loading/validation, default models, timeouts, missing SDKs. No network."""

from __future__ import annotations

import json
import sys
import types

import pytest

from eval_runner import providers
from eval_runner.providers import DEFAULT_ANTHROPIC_MODEL, StubProvider, build_provider


class TestStubProvider:
    def test_from_file(self, tmp_path):
        path = tmp_path / "stub.json"
        path.write_text(json.dumps({"hi": "hello"}))
        assert StubProvider(str(path)).complete("hi") == "hello"

    def test_from_mapping(self):
        assert StubProvider(responses={"hi": "hello"}).complete("hi") == "hello"

    def test_unknown_prompt_raises_key_error(self):
        with pytest.raises(KeyError, match="no canned response"):
            StubProvider(responses={}).complete("hi")

    def test_non_object_file_rejected(self, tmp_path):
        path = tmp_path / "stub.json"
        path.write_text(json.dumps(["hi", "hello"]))
        with pytest.raises(ValueError, match="JSON object"):
            StubProvider(str(path))

    def test_non_string_response_rejected(self):
        with pytest.raises(ValueError, match="must be a string"):
            StubProvider(responses={"hi": 42})

    def test_malformed_json_names_the_file(self, tmp_path):
        path = tmp_path / "stub.json"
        path.write_text("{ nope")
        with pytest.raises(ValueError, match="stub.json"):
            StubProvider(str(path))

    def test_build_provider_requires_responses(self):
        with pytest.raises(ValueError, match="--stub-responses"):
            build_provider("stub", None)


def _fake_sdk(monkeypatch, name: str, attr: str) -> list[dict]:
    """Install a fake SDK module whose client class records its constructor kwargs."""
    calls: list[dict] = []

    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    module = types.ModuleType(name)
    setattr(module, attr, Client)
    monkeypatch.setitem(sys.modules, name, module)
    return calls


def test_anthropic_defaults_model_and_timeout(monkeypatch):
    calls = _fake_sdk(monkeypatch, "anthropic", "Anthropic")
    provider = build_provider("anthropic", None)
    assert provider._model == DEFAULT_ANTHROPIC_MODEL == "claude-haiku-5-5"
    assert calls[0]["timeout"] == providers.DEFAULT_TIMEOUT


def test_explicit_model_and_timeout_are_passed_through(monkeypatch):
    calls = _fake_sdk(monkeypatch, "openai", "OpenAI")
    provider = build_provider("openai", "my-model", timeout=5)
    assert provider._model == "my-model"
    assert calls[0]["timeout"] == 5


def test_openai_requires_model():
    with pytest.raises(ValueError, match="--model"):
        build_provider("openai", None)


def test_missing_sdk_gives_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)  # makes `import anthropic` raise ImportError
    with pytest.raises(RuntimeError, match=r"pip install"):
        build_provider("anthropic", None)


def test_unknown_provider():
    with pytest.raises(ValueError, match="unknown provider"):
        build_provider("llama", None)
