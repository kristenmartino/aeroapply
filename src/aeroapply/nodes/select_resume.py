"""select_resume (#33, embedding-ranked #34) — pick the base `resume_variant` for this role.

Two strategies, in order:
  1. **Embedding-ranked** (when a `selector` is injected): score each variant by the mean
     cosine similarity of its indexed `resume_chunk`s to the job text and pick the best —
     the SQL sketched in docs/TAILORING_AND_ATS.md §2, built on the #34 retrieval layer.
  2. **Deterministic fallback** (no selector, or no variant has chunks / clears the floor):
     `role_focus`/`profile_name` substring of the job title > `is_default` > first.

No variants at all is an unrecoverable graph error — the operator must load a resume first.
Note: this does not set `agent_confidence` (that metric is #72); it only chooses the base.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aeroapply.graph.state import OUTCOME_ERROR, ExecutionState, NodeFn

Variant = dict[str, Any]  # {id, profile_name, role_focus, raw_text, is_default}

# (variants, job_text) -> chosen variant id, or None to defer to the deterministic pick.
VariantSelector = Callable[[list[Variant], str], str | None]


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


def make_select_resume(variants: list[Variant], selector: VariantSelector | None = None) -> NodeFn:
    """Build the node over the operator's variants (loaded once by the driver)."""

    def select_resume(state: ExecutionState) -> dict[str, Any]:
        if not variants:
            return {
                "outcome": OUTCOME_ERROR,
                "error": "no resume_variant rows — load a base resume before tailoring",
            }
        chosen: Variant | None = None
        method = "deterministic"
        if selector is not None:
            job_text = (
                f"{state.get('job_title', '')}\n\n{state.get('job_description', '')}".strip()
            )
            chosen_id = selector(variants, job_text)
            if chosen_id is not None:
                chosen = next((v for v in variants if v["id"] == chosen_id), None)
                if chosen is not None:
                    method = "embedding"
        if chosen is None:  # no selector, undecided, or stale id -> deterministic
            chosen = choose_variant(state.get("job_title", ""), variants)
        assert chosen is not None  # variants is non-empty, so choose_variant returns one
        return {
            "resume_variant_id": chosen["id"],
            "resume_profile_name": chosen.get("profile_name"),
            "resume_text": chosen.get("raw_text") or "",
            "selection_method": method,
        }

    return select_resume


__all__ = ["make_select_resume", "choose_variant", "VariantSelector"]
