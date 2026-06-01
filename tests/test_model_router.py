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


def test_build_anthropic_passes_model_beta_and_fast(monkeypatch):
    # Exercise build_chat_model with no network: the DRAFTING spec must map to the right
    # model id, the 1M-context beta header, and fast-mode service_tier.
    import langchain_anthropic

    captured: dict = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", FakeChatAnthropic)
    ModelRouter().build_chat_model("tailor.generator")
    assert captured["model"] == OPUS
    assert captured["default_headers"]["anthropic-beta"] == "context-1m-2025-08-07"
    assert captured["model_kwargs"]["service_tier"] == "fast"


def test_build_openai_routes_deepseek_base(monkeypatch):
    import langchain_openai

    captured: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setenv("MODEL__TAILOR_CRITIC", "deepseek:deepseek-reasoner")
    ModelRouter().build_chat_model("tailor.critic")
    assert captured["base_url"] == "https://api.deepseek.com"
    assert captured["model"] == "deepseek-reasoner"
