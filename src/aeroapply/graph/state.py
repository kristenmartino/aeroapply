"""Execution-graph state (#30) — the single TypedDict flowing through every node.

Keys are optional (``total=False``) because LangGraph nodes return *partial* updates
that are merged into the running state. ``thread_id`` for checkpointing is the
application id (Brief §5/§11), carried in the invoke config — not in this state.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class ExecutionState(TypedDict, total=False):
    # Identity / job facts (loaded from the DB by the driver before invoke)
    application_id: str
    job_title: str
    company: str
    job_description: str
    job_location: str | None
    portal_url: str | None
    portal_type: str | None

    # verify_open
    verify_status_code: int | None

    # select_resume
    resume_variant_id: str | None
    resume_profile_name: str | None
    resume_text: str

    # tailoring loop (Generator <-> ATS-Critic)
    draft_resume_text: str
    ats_score: float
    critic_gaps: list[str]
    iterations: int
    max_iterations: int
    ats_threshold: float

    # terminal routing
    outcome: str  # 'tailored' | 'closed' | 'error'
    error: str

    # free-form diagnostics (kept JSON-serializable for the checkpointer)
    debug: dict[str, Any]


class NodeFn(Protocol):
    """A graph node: takes the full state, returns a PARTIAL update to merge.

    Mirrors LangGraph's node protocol (the `state` parameter must be nameable —
    a bare `Callable[[ExecutionState], ...]` is positional-only and won't type-check).
    """

    def __call__(self, state: ExecutionState) -> dict[str, Any]: ...


OUTCOME_TAILORED = "tailored"
OUTCOME_CLOSED = "closed"
OUTCOME_ERROR = "error"

__all__ = ["ExecutionState", "NodeFn", "OUTCOME_TAILORED", "OUTCOME_CLOSED", "OUTCOME_ERROR"]
