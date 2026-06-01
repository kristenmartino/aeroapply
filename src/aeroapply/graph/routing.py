"""Submission routing — the secure-by-default autonomy gate.

This is the CONDITIONAL EDGE evaluated right before the submit node. We do NOT
use a static `interrupt_before=["submit"]` at compile time, because mode is
decided per-application at runtime. Anything that does not clear *every* gate
escalates to human review.

The function returns one of two SEMANTIC route labels — "auto_submit" or
"escalate_to_human_review" — NOT node names. The graph maps them to nodes:

    add_conditional_edges("review_gate", evaluate_submission_route, {
        "auto_submit": "account_submit",          # API/Playwright filing node
        "escalate_to_human_review": "pause_and_checkpoint",
    })

Gate order is canonical (PROJECT_BRIEF.md §6): Source -> Quality -> Preference -> Honesty.

See: docs/HITL_AITL.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Sources that must always be human-gated (fragile DOM / ban-prone / ToS-restricted).
BROWSER_SOURCES: frozenset[str] = frozenset({"workday", "taleo", "linkedin", "custom"})

DEFAULT_MIN_ATS_SCORE = 0.90
DEFAULT_MIN_AGENT_CONFIDENCE = 0.95


class Route(str, Enum):
    AUTO_SUBMIT = "auto_submit"
    HUMAN = "escalate_to_human_review"


@dataclass
class SubmissionDecision:
    route: Route
    reasons: list[str] = field(default_factory=list)

    @property
    def is_auto(self) -> bool:
        return self.route is Route.AUTO_SUBMIT


def decide_submission(state: dict) -> SubmissionDecision:
    """Evaluate all four gates and return an auditable decision.

    Expected state keys:
      portal_type: str            e.g. 'greenhouse' | 'lever' | 'workday'
      ats_score: float            0..1 (ATS-Critic keyword coverage)
      agent_confidence: float     0..1
      auto_submit: bool           operator opt-in for this application/source
      novel_questions: list       unseen questions not matched in qa_history
      sensitive_unanswered: bool  any EEO/visa/clearance/self-ID not high-confidence
      min_ats_score / min_agent_confidence: optional overrides
    """
    reasons: list[str] = []

    # 1. Source gate — DOM/ban-prone portals are never auto-submitted.
    if (state.get("portal_type") or "").lower() in BROWSER_SOURCES:
        reasons.append(f"source '{state.get('portal_type')}' requires human review")

    # 2. Quality gate — ats_score AND agent_confidence (one combined gate).
    min_ats = state.get("min_ats_score", DEFAULT_MIN_ATS_SCORE)
    min_conf = state.get("min_agent_confidence", DEFAULT_MIN_AGENT_CONFIDENCE)
    if (state.get("ats_score") or 0.0) < min_ats:
        reasons.append(f"ats_score {state.get('ats_score')} < {min_ats}")
    if (state.get("agent_confidence") or 0.0) < min_conf:
        reasons.append(f"agent_confidence {state.get('agent_confidence')} < {min_conf}")

    # 3. Preference gate — operator must have opted in.
    if not state.get("auto_submit", False):
        reasons.append("auto_submit not enabled for this application")

    # 4. Honesty gate — never auto-answer novel or sensitive questions.
    if state.get("novel_questions"):
        reasons.append(f"{len(state['novel_questions'])} unseen question(s) need human input")
    if state.get("sensitive_unanswered"):
        reasons.append("sensitive (EEO/visa/clearance) field unresolved — never fabricate")

    route = Route.AUTO_SUBMIT if not reasons else Route.HUMAN
    if route is Route.AUTO_SUBMIT:
        reasons.append("all gates passed")
    return SubmissionDecision(route=route, reasons=reasons)


def evaluate_submission_route(state: dict) -> str:
    """Thin string-returning wrapper for use as a LangGraph conditional edge."""
    return decide_submission(state).route.value


__all__ = ["Route", "SubmissionDecision", "decide_submission", "evaluate_submission_route"]
