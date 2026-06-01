from aeroapply.graph.routing import Route, decide_submission, evaluate_submission_route

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
