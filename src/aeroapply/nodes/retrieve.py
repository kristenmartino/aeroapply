"""retrieve (#34) — pull the most relevant resume chunks to ground the Generator.

Runs after `select_resume`: embeds the job (title + description), cosine-searches the
chosen variant's `resume_chunk` rows, and puts the top-k chunk texts into the state so
the Generator tailors from the operator's *actual* most-relevant experience rather than
the whole resume blob (and so it can't drift from grounded truth — Brief §13.1).

IO is injected as a `retriever(resume_variant_id, job_text) -> list[str]` callable, like
the model factory and http client. When no retriever is wired (e.g. embeddings not yet
indexed, or unit tests that don't exercise retrieval) the node is a no-op and the
Generator falls back to the full base resume.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aeroapply.graph.state import ExecutionState, NodeFn

Retriever = Callable[[str, str], list[str]]  # (resume_variant_id, job_text) -> chunk texts


def make_retrieve(retriever: Retriever | None) -> NodeFn:
    """Build the node. `retriever=None` makes it a pass-through (no grounding)."""

    def retrieve(state: ExecutionState) -> dict[str, Any]:
        if retriever is None:
            return {}
        variant_id = state.get("resume_variant_id")
        if not variant_id:
            return {}
        job_text = f"{state.get('job_title', '')}\n\n{state.get('job_description', '')}".strip()
        try:
            chunks = retriever(variant_id, job_text)
        except Exception as exc:  # retrieval must never crash the run — degrade to ungrounded
            return {"debug": {"retrieve_error": str(exc)}}
        return {"retrieved_context": [c for c in chunks if c and c.strip()]}

    return retrieve


__all__ = ["make_retrieve", "Retriever"]
