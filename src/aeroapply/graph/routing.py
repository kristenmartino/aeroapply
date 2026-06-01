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

The state the gate reads is built from config via `build_gate_state` (so
`profile.autonomy` — sources, thresholds, default_mode — actually drives the
decision). Gate order is canonical (PROJECT_BRIEF.md §6): Source -> Quality ->
Preference -> Honesty.

See: docs/HITL_AITL.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aeroapply.config import AutonomyCfg, Settings

# Fallback set if no `always_human_sources` is supplied (fragile DOM / ban-prone / ToS).
BROWSER_SOURCES: frozenset[str] = frozenset({"workday", "taleo", "linkedin", "custom"})

DEFAULT_MIN_ATS_SCORE = 0.90
DEFAULT_MIN_AGENT_CONFIDENCE = 0.95


class Route(StrEnum):
    AUTO_SUBMIT = "auto_submit"
    HUMAN = "escalate_to_human_review"


@dataclass
class SubmissionDecision:
    route: Route
    reasons: list[str] = field(default_factory=list)

    @property
    def is_auto(self) -> bool:
        return self.route is Route.AUTO_SUBMIT


def build_gate_state(
    autonomy: AutonomyCfg,
    *,
    portal_type: str | None,
    ats_score: float | None,
    agent_confidence: float | None,
    auto_submit: bool = False,
    novel_questions: list[Any] | None = None,
    sensitive_unanswered: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Build the state dict `decide_submission` reads from `profile.autonomy`.

    Env `Settings` (if passed) override the profile's thresholds — deployment wins.
    `default_mode='auto'` makes auto-submit the default; 'review' requires explicit
    per-application opt-in. Gates still apply either way (secure-by-default).
    """
    if settings is not None:
        min_ats, min_conf = settings.min_ats_score, settings.min_agent_confidence
    else:
        min_ats, min_conf = autonomy.min_ats_score, autonomy.min_agent_confidence
    effective_auto = auto_submit or (autonomy.default_mode == "auto")
    return {
        "portal_type": portal_type,
        "ats_score": ats_score,
        "agent_confidence": agent_confidence,
        "auto_submit": effective_auto,
        "novel_questions": novel_questions or [],
        "sensitive_unanswered": sensitive_unanswered,
        "min_ats_score": min_ats,
        "min_agent_confidence": min_conf,
        "always_human_sources": list(autonomy.always_human_sources) or sorted(BROWSER_SOURCES),
        "auto_submit_sources": list(autonomy.auto_submit_sources) or None,
    }


def decide_submission(state: dict[str, Any]) -> SubmissionDecision:
    """Evaluate all four gates and return an auditable decision.

    State keys (all optional; safe defaults): portal_type, ats_score,
    agent_confidence, auto_submit, novel_questions, sensitive_unanswered,
    min_ats_score, min_agent_confidence, always_human_sources, auto_submit_sources.
    """
    reasons: list[str] = []
    portal = state.get("portal_type") or ""
    pt = portal.lower()

    # 1. Source gate — DOM/ban-prone portals never auto-submit; only listed sources may.
    always_human = {s.lower() for s in (state.get("always_human_sources") or BROWSER_SOURCES)}
    if pt in always_human:
        reasons.append(f"source '{portal}' requires human review")
    auto_sources = state.get("auto_submit_sources")
    if auto_sources is not None and pt not in {s.lower() for s in auto_sources}:
        reasons.append(f"source '{portal}' is not in auto_submit_sources")

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


def evaluate_submission_route(state: dict[str, Any]) -> str:
    """Thin string-returning wrapper for use as a LangGraph conditional edge."""
    return str(decide_submission(state).route.value)


__all__ = [
    "Route",
    "SubmissionDecision",
    "build_gate_state",
    "decide_submission",
    "evaluate_submission_route",
    "BROWSER_SOURCES",
]
