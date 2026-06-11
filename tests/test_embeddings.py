"""Embeddings layer unit tests — deterministic HashEmbedder, no DB, no API key."""

from __future__ import annotations

import math

import pytest

from aeroapply.embeddings import (
    EmbeddingDimMismatch,
    HashEmbedder,
    chunk_resume,
    validate_dim,
)


def test_hash_embedder_is_deterministic_and_unit_norm():
    e = HashEmbedder(dim=64)
    a1 = e.embed(["python data engineer"])[0]
    a2 = e.embed(["python data engineer"])[0]
    assert a1 == a2                                   # same text -> identical vector
    assert len(a1) == 64
    assert math.isclose(math.sqrt(sum(x * x for x in a1)), 1.0, rel_tol=1e-9)


def test_hash_embedder_distinguishes_texts():
    e = HashEmbedder(dim=128)
    py, sales = e.embed(["python kubernetes airflow", "retail sales associate cashier"])

    def cos(u, v):
        return sum(a * b for a, b in zip(u, v, strict=True))

    same = cos(py, e.embed(["python kubernetes airflow"])[0])
    diff = cos(py, sales)
    assert math.isclose(same, 1.0, rel_tol=1e-9)      # identical -> cosine 1
    assert diff < same                                # unrelated -> less similar


def test_empty_text_does_not_produce_a_zero_vector():
    v = HashEmbedder(dim=32).embed([""])[0]
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)


def test_validate_dim_guard():
    validate_dim(HashEmbedder(dim=1536), 1536)        # ok
    with pytest.raises(EmbeddingDimMismatch):
        validate_dim(HashEmbedder(dim=768), 1536)


def test_chunk_resume_splits_paragraphs_and_labels_sections():
    text = (
        "Summary\nSenior product manager.\n\n"
        "Experience\nLed a 0-to-1 launch.\n\n"
        "Skills\nSQL, Python, roadmapping."
    )
    chunks = chunk_resume(text)
    sections = [s for s, _ in chunks]
    texts = [t for _, t in chunks]
    assert "Summary" in sections and "Experience" in sections and "Skills" in sections
    assert any("0-to-1 launch" in t for t in texts)


def test_chunk_resume_hard_splits_oversized_paragraphs():
    big = "word " * 600  # ~3000 chars, one paragraph
    chunks = chunk_resume(big, max_chars=1000)
    assert len(chunks) >= 3
    assert all(len(t) <= 1000 for _, t in chunks)


def test_chunk_resume_empty():
    assert chunk_resume("") == []
    assert chunk_resume("   \n\n  ") == []
