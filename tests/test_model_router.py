import importlib

import pytest

from aeroapply.models.router import OPUS, SONNET, ModelRouter


def test_resolve_defaults_and_unknown():
    r = ModelRouter()
    assert r.resolve("tailor.generator").model_id == OPUS
    assert r.resolve("tailor.critic").model_id == SONNET
    assert r.resolve("unknown.node").provider == "anthropic"  # safe default


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("MODEL__TAILOR_GENERATOR", "anthropic:claude-sonnet-4-6")
    assert ModelRouter().resolve("tailor.generator").model_id == "claude-sonnet-4-6"


@pytest.mark.parametrize("module", ["langchain_anthropic", "langchain_openai", "langchain_ollama"])
def test_provider_adapter_packages_importable(module):
    # No-network smoke test: CI fails loudly if a provider adapter package is undeclared.
    importlib.import_module(module)
