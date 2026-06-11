"""Embeddings (#34) — provider-agnostic text → vector, plus resume chunking.

The retrieval layer is built behind an `Embedder` protocol so the provider is config,
never hard-coded (Brief §10/§12). Default is OpenAI `text-embedding-3-small` (1536-d,
matching the `vector(1536)` schema); a deterministic `HashEmbedder` backs offline dev
and the entire test suite (no API key, stable vectors → stable retrieval order).

Dimension is validated against `Settings.embedding_dim` up front — the schema hard-codes
`vector(1536)`, and silently swapping to a different-width embedder corrupts retrieval
(the roadmap's "validate dimension at startup" risk).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Protocol, runtime_checkable

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIM = 1536


@runtime_checkable
class Embedder(Protocol):
    """Maps texts to unit-comparable vectors. `dim` must match the schema vector width."""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingDimMismatch(RuntimeError):
    """Raised when an embedder's width doesn't match the schema/`Settings.embedding_dim`."""


def validate_dim(embedder: Embedder, expected: int) -> None:
    if embedder.dim != expected:
        raise EmbeddingDimMismatch(
            f"embedder dim {embedder.dim} != schema vector({expected}); "
            "re-index or align Settings.embedding_dim (see scripts/bootstrap.sql)"
        )


# --- chunking -------------------------------------------------------------
_HEADER = re.compile(r"^\s*(summary|experience|skills|education|projects|certifications)\b", re.I)


def chunk_resume(raw_text: str, *, max_chars: int = 1000) -> list[tuple[str | None, str]]:
    """Split a resume into ``(section_name, chunk_text)`` pairs for embedding.

    Paragraph-based (blank-line separated), with a light section-header detector so a
    chunk can be labelled (Experience / Skills / …). Oversized paragraphs are hard-split
    at `max_chars` so no single chunk blows past the embedder's context.
    """
    section: str | None = None
    chunks: list[tuple[str | None, str]] = []
    for para in re.split(r"\n\s*\n", raw_text or ""):
        para = para.strip()
        if not para:
            continue
        header = _HEADER.match(para)
        if header:
            section = header.group(1).title()
        for i in range(0, len(para), max_chars):
            piece = para[i : i + max_chars].strip()
            if piece:
                chunks.append((section, piece))
    return chunks


# --- embedders ------------------------------------------------------------
_TOKEN = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Deterministic, dependency-free embedder for offline dev + tests.

    Hashes tokens into a fixed-width bag-of-words vector and L2-normalizes it: identical
    text → identical vector (cosine distance 0), so retrieval order is reproducible. It
    is NOT semantic — it can't match synonyms — and must never be the production default.
    """

    def __init__(self, dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        self.dim = dim

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN.findall((text or "").lower()):
            h = int.from_bytes(hashlib.sha1(tok.encode()).digest()[:4], "big")
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0  # avoid a zero vector (undefined cosine)
            return vec
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class OpenAIEmbedder:
    """OpenAI embeddings (default production embedder). Lazy client; key from env."""

    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL, dim: int = DEFAULT_EMBEDDING_DIM):
        self.model = model
        self.dim = dim
        self._client: Any = None

    def _ensure(self) -> None:  # pragma: no cover - needs the SDK + a real key
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()  # OPENAI_API_KEY from env

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - network
        self._ensure()
        assert self._client is not None
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def build_default_embedder(
    model: str = DEFAULT_EMBEDDING_MODEL, dim: int = DEFAULT_EMBEDDING_DIM
) -> Embedder:
    """The embedder the CLI/driver uses. `AEROAPPLY_EMBEDDER=hash` forces the offline
    deterministic embedder (dev without a key); otherwise OpenAI."""
    if os.getenv("AEROAPPLY_EMBEDDER", "").lower() == "hash":
        return HashEmbedder(dim)
    return OpenAIEmbedder(model, dim)


__all__ = [
    "Embedder",
    "HashEmbedder",
    "OpenAIEmbedder",
    "EmbeddingDimMismatch",
    "validate_dim",
    "chunk_resume",
    "build_default_embedder",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_DIM",
]
