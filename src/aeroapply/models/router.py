"""Model router — per-node choice of model + settings.

Every graph node asks the router for its model by *node name*. Resolution order
(highest precedence first):

    1. Env override:  MODEL__<NODE>=provider:model_id
       (e.g. MODEL__TAILOR_GENERATOR=anthropic:claude-opus-4-8)
    2. DB row in model_config (node_name unique)  — editable at runtime from the UI
    3. DEFAULT_REGISTRY below

This is how you pin, say, the Generator to "Opus 4.8, 1M context, fast mode" while
the Critic runs Sonnet at temperature 0 and sourcing runs a local Llama — all as
*config*, never hard-coded in the nodes.

See: docs/MODEL_ROUTING.md
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# Current model IDs (Jan 2026). Never use legacy IDs like claude-3-opus-*.
OPUS = "claude-opus-4-8"
SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5"


@dataclass(frozen=True)
class ModelSpec:
    provider: str                       # anthropic | deepseek | openai | ollama
    model_id: str
    params: dict[str, Any] = field(default_factory=dict)
    fallback: ModelSpec | None = None


# Task-class defaults. Nodes map to one of these via DEFAULT_REGISTRY.
DRAFTING = ModelSpec(
    provider="anthropic", model_id=OPUS,
    # `context_1m` + `fast` are surfaced as betas/headers in build_chat_model().
    params={"temperature": 0.6, "max_tokens": 8192, "context_1m": True, "fast": True},
    fallback=ModelSpec("anthropic", SONNET, {"temperature": 0.6, "max_tokens": 8192}),
)
CRITIQUE = ModelSpec(
    provider="anthropic", model_id=SONNET,
    params={"temperature": 0.0, "max_tokens": 4096},
    fallback=ModelSpec("deepseek", "deepseek-reasoner", {"temperature": 0.0}),
)
EXTRACT = ModelSpec(
    provider="ollama", model_id="llama3.1",
    params={"temperature": 0.0, "format": "json"},
    fallback=ModelSpec("anthropic", HAIKU, {"temperature": 0.0}),
)

# node_name -> ModelSpec. Node names are dotted (subgraph.node).
DEFAULT_REGISTRY: dict[str, ModelSpec] = {
    "tailor.generator": DRAFTING,
    "cover_letter": DRAFTING,
    "tailor.critic": CRITIQUE,
    "answer_questions.validator": CRITIQUE,
    "sourcing.parser": EXTRACT,
    "email.classifier": EXTRACT,
}


class ModelRouter:
    def __init__(self, db_overrides: dict[str, ModelSpec] | None = None) -> None:
        self._db = db_overrides or {}

    def resolve(self, node: str) -> ModelSpec:
        env = self._env_override(node)
        if env is not None:
            return env
        if node in self._db:
            return self._db[node]
        if node in DEFAULT_REGISTRY:
            return DEFAULT_REGISTRY[node]
        # Unknown node -> safe, capable default.
        return CRITIQUE

    @staticmethod
    def _env_override(node: str) -> ModelSpec | None:
        key = "MODEL__" + node.upper().replace(".", "_")
        raw = os.getenv(key)
        if not raw or ":" not in raw:
            return None
        provider, model_id = raw.split(":", 1)
        return ModelSpec(provider=provider, model_id=model_id)

    def build_chat_model(self, node: str) -> Any:
        """Lazily construct the provider chat model for `node`.

        Imports are deferred so a node only pulls in the SDK it actually uses.
        """
        spec = self.resolve(node)
        p: dict[str, Any] = dict(spec.params)
        if spec.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            betas: list[str] = []
            if p.pop("context_1m", False):
                betas.append("context-1m-2025-08-07")  # 1M context beta
            if p.pop("fast", False):
                p.setdefault("model_kwargs", {})["service_tier"] = "fast"  # fast mode
            if betas:
                p["default_headers"] = {"anthropic-beta": ",".join(betas)}
            p["model"] = spec.model_id
            return ChatAnthropic(**p)
        if spec.provider in ("openai", "deepseek"):
            from langchain_openai import ChatOpenAI

            base = "https://api.deepseek.com" if spec.provider == "deepseek" else None
            key_env = "DEEPSEEK_API_KEY" if spec.provider == "deepseek" else "OPENAI_API_KEY"
            opts: dict[str, Any] = {"base_url": base, "api_key": os.getenv(key_env), **p}
            return ChatOpenAI(model=spec.model_id, **opts)
        if spec.provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(model=spec.model_id, base_url=os.getenv("OLLAMA_HOST"), **p)
        raise ValueError(f"unknown provider: {spec.provider}")


__all__ = ["ModelRouter", "ModelSpec", "DEFAULT_REGISTRY", "OPUS", "SONNET", "HAIKU"]
