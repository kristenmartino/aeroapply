from aeroapply.config import AutonomyCfg
from aeroapply.graph.routing import (
    Route,
    build_gate_state,
    decide_submission,
    evaluate_submission_route,
)

BASE = {
    "portal_type": "greenhouse",
    "ats_score": 0.95,
    "agent_confidence": 0.97,
    "auto_submit": True,
    "novel_questions": [],
    "sensitive_unanswered": False,
}


def test_clean_high_confidence_api_source_auto_submits():
    d = decide_submission(BASE)
    assert d.route is Route.AUTO_SUBMIT and d.is_auto


def test_browser_source_always_escalates():
    d = decide_submission({**BASE, "portal_type": "workday"})
    assert d.route is Route.HUMAN


def test_low_ats_score_escalates():
    d = decide_submission({**BASE, "ats_score": 0.70})
    assert d.route is Route.HUMAN


def test_sensitive_field_never_auto():
    d = decide_submission({**BASE, "sensitive_unanswered": True})
    assert d.route is Route.HUMAN


def test_requires_operator_optin():
    d = decide_submission({**BASE, "auto_submit": False})
    assert d.route is Route.HUMAN


def test_wrapper_returns_route_string():
    assert evaluate_submission_route(BASE) == "auto_submit"


# --- profile-driven gate (build_gate_state wires Profile.autonomy in) ---
def _autonomy(**kw):
    base = dict(
        default_mode="review",
        auto_submit_sources=["greenhouse"],
        always_human_sources=["workday"],
        min_ats_score=0.90,
        min_agent_confidence=0.95,
    )
    base.update(kw)
    return AutonomyCfg(**base)


def test_gate_state_listed_api_source_auto_submits():
    st = build_gate_state(_autonomy(), portal_type="greenhouse", ats_score=0.99,
                          agent_confidence=0.99, auto_submit=True)
    assert decide_submission(st).route is Route.AUTO_SUBMIT


def test_gate_state_always_human_source_escalates():
    st = build_gate_state(_autonomy(), portal_type="workday", ats_score=0.99,
                          agent_confidence=0.99, auto_submit=True)
    assert decide_submission(st).route is Route.HUMAN


def test_gate_state_unlisted_source_escalates():
    st = build_gate_state(_autonomy(), portal_type="lever", ats_score=0.99,
                          agent_confidence=0.99, auto_submit=True)
    assert decide_submission(st).route is Route.HUMAN


def test_gate_state_review_mode_blocks_without_optin():
    st = build_gate_state(_autonomy(default_mode="review"), portal_type="greenhouse",
                          ats_score=0.99, agent_confidence=0.99, auto_submit=False)
    assert decide_submission(st).route is Route.HUMAN


def test_gate_state_auto_mode_defaults_optin():
    st = build_gate_state(_autonomy(default_mode="auto"), portal_type="greenhouse",
                          ats_score=0.99, agent_confidence=0.99, auto_submit=False)
    assert decide_submission(st).route is Route.AUTO_SUBMIT


def test_gate_state_profile_thresholds_flow_through():
    st = build_gate_state(_autonomy(min_ats_score=0.99, min_agent_confidence=0.99),
                          portal_type="greenhouse", ats_score=0.95,
                          agent_confidence=0.96, auto_submit=True)
    assert decide_submission(st).route is Route.HUMAN


def test_gate_state_auto_mode_empty_allowlist_blocks_all():
    # Empty auto_submit_sources = NOTHING whitelisted -> always escalate (the secure-by-default fix).
    st = build_gate_state(_autonomy(default_mode="auto", auto_submit_sources=[]),
                          portal_type="random_ats", ats_score=0.99,
                          agent_confidence=0.99, auto_submit=False)
    assert decide_submission(st).route is Route.HUMAN


def test_gate_state_auto_mode_never_overrides_tier_b_source():
    st = build_gate_state(_autonomy(default_mode="auto"), portal_type="workday",
                          ats_score=0.99, agent_confidence=0.99, auto_submit=False)
    assert decide_submission(st).route is Route.HUMAN
