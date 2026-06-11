"""select_resume (#33) — pick the base `resume_variant` for this role.

v1 selection is deterministic and cheap: match each variant's `role_focus` (or its
`profile_name`) as a case-insensitive substring of the job title; fall back to the
`is_default` variant, then to the first one. Embedding-based selection arrives with
the retrieval layer (#34). No variants at all is an unrecoverable graph error — the
operator must load a resume before anything can be tailored.
"""

from __future__ import annotations

from typing import Any

from aeroapply.graph.state import OUTCOME_ERROR, ExecutionState, NodeFn

Variant = dict[str, Any]  # {id, profile_name, role_focus, raw_text, is_default}


def choose_variant(job_title: str, variants: list[Variant]) -> Variant | None:
    """Deterministic pick: role_focus/profile_name substring match > default > first."""
    if not variants:
        return None
    title = (job_title or "").lower()
    for v in variants:
        focus = (v.get("role_focus") or "").strip().lower()
        if focus and focus in title:
            return v
    for v in variants:
        name = (v.get("profile_name") or "").strip().lower()
        if name and name in title:
            return v
    for v in variants:
        if v.get("is_default"):
            return v
    return variants[0]


def make_select_resume(variants: list[Variant]) -> NodeFn:
    """Build the node over the operator's variants (loaded once by the driver)."""

    def select_resume(state: ExecutionState) -> dict[str, Any]:
        chosen = choose_variant(state.get("job_title", ""), variants)
        if chosen is None:
            return {
                "outcome": OUTCOME_ERROR,
                "error": "no resume_variant rows — load a base resume before tailoring",
            }
        return {
            "resume_variant_id": chosen["id"],
            "resume_profile_name": chosen.get("profile_name"),
            "resume_text": chosen.get("raw_text") or "",
        }

    return select_resume


__all__ = ["make_select_resume", "choose_variant"]
