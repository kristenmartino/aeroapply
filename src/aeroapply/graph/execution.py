"""Execution-graph assembly + the run driver (#30, #31).

Graph shape (answer_questions / the submission gate are M3):

    verify_open ──closed──────────────► END
        │ open
        ▼
    select_resume ──error─────────────► END
        │ ok
        ▼
    retrieve ──► generate ◄──── revise ─── critic
        └──────────────────────► critic ──accept──► finalize ──► cover_letter ──► END

All IO is injected: models via a `node -> chat model` factory (default ModelRouter),
HTTP via an optional httpx client, resume variants as plain dicts. The graph itself
only transforms state; DB persistence happens in `run_application` AFTER the graph
returns, keyed on `outcome`. Checkpointing: `thread_id = application_id` (Brief §11),
so a killed worker resumes mid-loop from the last checkpoint.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import psycopg
from langgraph.graph import END, StateGraph

from aeroapply.db import repo
from aeroapply.graph.state import (
    OUTCOME_CLOSED,
    OUTCOME_ERROR,
    OUTCOME_TAILORED,
    ExecutionState,
)
from aeroapply.graph.usage import UsageTracker, wrap_factory_with_usage
from aeroapply.nodes.cover_letter import make_cover_letter
from aeroapply.nodes.retrieve import Retriever, make_retrieve
from aeroapply.nodes.select_resume import Variant, VariantSelector, make_select_resume
from aeroapply.nodes.tailor import (
    DEFAULT_ATS_THRESHOLD,
    DEFAULT_MAX_ITERATIONS,
    ModelFactory,
    critic_route,
    finalize,
    make_critic,
    make_generate,
)
from aeroapply.nodes.verify_open import make_verify_open


def _default_model_factory() -> ModelFactory:
    from aeroapply.models.router import ModelRouter

    return ModelRouter().build_chat_model


def _after_verify(state: ExecutionState) -> str:
    return "closed" if state.get("outcome") == OUTCOME_CLOSED else "open"


def _after_select(state: ExecutionState) -> str:
    return "error" if state.get("outcome") == OUTCOME_ERROR else "ok"


def build_execution_graph(
    variants: list[Variant],
    *,
    model_factory: ModelFactory | None = None,
    http_client: httpx.Client | None = None,
    variant_selector: VariantSelector | None = None,
    retriever: Retriever | None = None,
    cover_letter_enabled: bool = False,
    checkpointer: Any = None,
    interrupt_before: list[str] | None = None,
) -> Any:
    """Compile the M2/M3 execution graph. Every dependency is injectable for tests.

    `variant_selector` ranks résumé variants by embedding similarity (#34); None falls
    back to the deterministic substring pick. `retriever` grounds the Generator on the
    chosen variant's most-relevant chunks; None makes `retrieve` a pass-through.
    `cover_letter_enabled` draws a cover letter after tailoring (#38); False is a no-op.
    """
    models = model_factory or _default_model_factory()

    g = StateGraph(ExecutionState)
    g.add_node("verify_open", make_verify_open(http_client))
    g.add_node("select_resume", make_select_resume(variants, variant_selector))
    g.add_node("retrieve", make_retrieve(retriever))
    g.add_node("generate", make_generate(models))
    g.add_node("critic", make_critic(models))
    g.add_node("finalize", finalize)
    g.add_node("cover_letter", make_cover_letter(models, enabled=cover_letter_enabled))

    g.set_entry_point("verify_open")
    g.add_conditional_edges("verify_open", _after_verify,
                            {"closed": END, "open": "select_resume"})
    g.add_conditional_edges("select_resume", _after_select,
                            {"error": END, "ok": "retrieve"})
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "critic")
    g.add_conditional_edges("critic", critic_route,
                            {"revise": "generate", "accept": "finalize"})
    g.add_edge("finalize", "cover_letter")
    g.add_edge("cover_letter", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=interrupt_before or [])


def initial_state(
    app_row: dict[str, Any],
    *,
    ats_threshold: float = DEFAULT_ATS_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> ExecutionState:
    """Seed the graph state from a `repo.fetch_next_queued` row + the cost/quality knobs."""
    return {
        "application_id": app_row["application_id"],
        "job_title": app_row.get("job_title", ""),
        "company": app_row.get("company", ""),
        "job_description": app_row.get("job_description", ""),
        "job_location": app_row.get("job_location"),
        "portal_url": app_row.get("portal_url"),
        "portal_type": app_row.get("portal_type"),
        "iterations": 0,
        "ats_threshold": ats_threshold,
        "max_iterations": max_iterations,
    }


def persist_outcome(conn: psycopg.Connection, final: ExecutionState) -> str:
    """Map the graph's terminal state onto application status + audit log; returns outcome."""
    app_id = final["application_id"]
    outcome = final.get("outcome") or OUTCOME_ERROR
    if outcome == OUTCOME_CLOSED:
        repo.mark_closed_before_execution(
            conn, app_id, {"status_code": final.get("verify_status_code")}
        )
    elif outcome == OUTCOME_TAILORED:
        repo.save_tailoring_result(
            conn,
            app_id,
            resume_variant_id=final.get("resume_variant_id"),
            tailored_resume_text=final.get("draft_resume_text", ""),
            ats_score=float(final.get("ats_score", 0.0)),
            iterations=int(final.get("iterations", 0)),
            cover_letter=final.get("cover_letter"),
        )
    else:
        repo.mark_graph_error(conn, app_id, final.get("error", "graph ended without outcome"))
    return outcome


def make_db_retriever(conn: psycopg.Connection, embedder: Any, *, k: int = 5) -> Retriever:
    """A `retriever(variant_id, job_text)` over `resume_chunk` via pgvector cosine (#34).

    Embeds the job text with the injected embedder and returns the chosen variant's
    top-k nearest chunk texts. Used by `run_application`; unit tests inject a fake.
    """

    def retrieve(variant_id: str, job_text: str) -> list[str]:
        query_vec = embedder.embed([job_text])[0]
        hits = repo.retrieve_resume_chunks(conn, variant_id, query_vec, k=k)
        return [text for text, _distance in hits]

    return retrieve


def make_db_variant_selector(
    conn: psycopg.Connection, embedder: Any, *, k: int = 8, min_similarity: float = 0.0
) -> VariantSelector:
    """A `selector(variants, job_text)` ranking variants by mean chunk similarity (#34).

    Embeds the job once, then scores each variant by the mean cosine similarity
    (`1 - distance`) of its top-k indexed chunks. Returns the best variant's id, or None
    when no variant has chunks or none clears `min_similarity` (the caller then falls back
    to the deterministic pick). `min_similarity` default 0.0 means "best non-empty wins";
    a real floor is a calibration decision (#58), not hard-coded here.
    """

    def select(variants: list[Variant], job_text: str) -> str | None:
        query_vec = embedder.embed([job_text])[0]
        best_id: str | None = None
        best_score: float | None = None
        for v in variants:
            hits = repo.retrieve_resume_chunks(conn, v["id"], query_vec, k=k)
            if not hits:
                continue
            score = sum(1.0 - dist for _text, dist in hits) / len(hits)
            if best_score is None or score > best_score:
                best_id, best_score = v["id"], score
        if best_id is None or (best_score is not None and best_score < min_similarity):
            return None
        return best_id

    return select


def run_application(
    conn: psycopg.Connection,
    app_row: dict[str, Any],
    variants: list[Variant],
    *,
    model_factory: ModelFactory | None = None,
    http_client: httpx.Client | None = None,
    variant_selector: VariantSelector | None = None,
    retriever: Retriever | None = None,
    cover_letter_enabled: bool = False,
    checkpointer: Any = None,
    ats_threshold: float = DEFAULT_ATS_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> ExecutionState:
    """Run one queued application through the graph, trace it in `run`, and persist.

    `thread_id = application_id`, so re-running after a crash resumes from the last
    checkpoint (a SEPARATE checkpointer connection) instead of re-spending Generator
    tokens. The `run` row records timing + per-model token usage (#31).

    Transaction model: `start_run`/`persist`/`finish_run` all share the caller's single
    transaction, which commits only on clean return. So a completed run leaves exactly
    one `run` row in its terminal state; an unhandled exception (or a kill) rolls the whole
    transaction back — no partial `run` row — and the application stays `queued` for the
    next `work` cycle to resume from its checkpoint. (Observing in-flight/crashed runs would
    need run telemetry on its own committed connection — deliberately out of scope here.)
    Caller commits.
    """
    app_id = app_row["application_id"]
    tracker = UsageTracker()
    base_factory = model_factory or _default_model_factory()
    graph = build_execution_graph(
        variants,
        model_factory=wrap_factory_with_usage(base_factory, tracker),
        http_client=http_client,
        variant_selector=variant_selector,
        retriever=retriever,
        cover_letter_enabled=cover_letter_enabled,
        checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": app_id}}
    run_id = repo.start_run(conn, app_id, app_id)
    started = time.monotonic()
    final: ExecutionState = graph.invoke(
        initial_state(app_row, ats_threshold=ats_threshold, max_iterations=max_iterations),
        config=config,
    )
    duration = round(time.monotonic() - started, 3)
    outcome = persist_outcome(conn, final)
    repo.finish_run(conn, run_id, outcome, {
        "duration_s": duration,
        "iterations": int(final.get("iterations", 0)),
        "ats_score": final.get("ats_score"),
        "usage": tracker.to_meta(),
    })
    return final


__all__ = [
    "build_execution_graph",
    "initial_state",
    "persist_outcome",
    "make_db_retriever",
    "make_db_variant_selector",
    "run_application",
]
