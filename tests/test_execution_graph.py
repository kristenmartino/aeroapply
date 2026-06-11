"""Execution-graph unit tests — no DB, no network, no API keys.

Models are injected as deterministic fakes; HTTP via httpx.MockTransport. These
lock the M2 invariants: the critic loop terminates (threshold OR cap — never
infinite), verify_open short-circuits before any model call, and select_resume
errors cleanly when no resume exists.
"""

from __future__ import annotations

import httpx

from aeroapply.graph.execution import build_execution_graph, initial_state
from aeroapply.graph.state import OUTCOME_CLOSED, OUTCOME_ERROR, OUTCOME_TAILORED
from aeroapply.nodes.select_resume import choose_variant
from aeroapply.nodes.tailor import critic_route, parse_critic_response

VARIANTS = [
    {"id": "v-core", "profile_name": "Core track - base", "role_focus": "Product Manager",
     "raw_text": "BASE RESUME core", "is_default": False},
    {"id": "v-default", "profile_name": "General - base", "role_focus": None,
     "raw_text": "BASE RESUME default", "is_default": True},
]

APP_ROW = {
    "application_id": "app-1", "job_title": "Senior Product Manager", "company": "Acme",
    "job_description": "Own the roadmap. Keywords: strategy, analytics.",
    "job_location": "Remote", "remote_mode": "remote",
    "portal_url": "https://boards.example.com/jobs/1", "portal_type": "greenhouse",
}


class FakeModel:
    """Chat-model stand-in: pops the next canned reply; records every prompt."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("Msg", (), {"content": self.replies.pop(0)})()


def fake_factory(generator: FakeModel, critic: FakeModel):
    def factory(node: str):
        return generator if node == "tailor.generator" else critic

    return factory


def http_ok(body: str = "Apply now!", status: int = 200) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(status, text=body))
    )


def test_loop_revises_until_threshold():
    generator = FakeModel(["draft v1", "draft v2"])
    critic = FakeModel(
        ['{"ats_score": 0.5, "gaps": ["analytics"]}', '{"ats_score": 0.95, "gaps": []}']
    )
    graph = build_execution_graph(VARIANTS, model_factory=fake_factory(generator, critic),
                                  http_client=http_ok())

    final = graph.invoke(initial_state(APP_ROW))

    assert final["outcome"] == OUTCOME_TAILORED
    assert final["iterations"] == 2
    assert final["ats_score"] == 0.95
    assert final["draft_resume_text"] == "draft v2"
    # round 2's generator prompt carries round 1's critic feedback
    assert "analytics" in generator.prompts[1]
    # the matched (non-default) variant was selected and fed to the generator
    assert final["resume_variant_id"] == "v-core"
    assert "BASE RESUME core" in generator.prompts[0]


def test_iteration_cap_is_the_cost_circuit_breaker():
    cap = 3
    generator = FakeModel([f"draft v{i}" for i in range(1, cap + 2)])  # one spare
    critic = FakeModel(['{"ats_score": 0.2, "gaps": ["x"]}'] * (cap + 1))
    graph = build_execution_graph(VARIANTS, model_factory=fake_factory(generator, critic),
                                  http_client=http_ok())

    final = graph.invoke(initial_state(APP_ROW, max_iterations=cap))

    assert final["outcome"] == OUTCOME_TAILORED  # best effort kept; quality gate judges later
    assert final["iterations"] == cap            # exactly cap generator calls, never more
    assert len(generator.prompts) == cap
    assert final["ats_score"] == 0.2


def test_closed_posting_short_circuits_before_any_model_call():
    generator = FakeModel([])
    critic = FakeModel([])
    closed = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(404, text="gone"))
    )
    graph = build_execution_graph(VARIANTS, model_factory=fake_factory(generator, critic),
                                  http_client=closed)

    final = graph.invoke(initial_state(APP_ROW))

    assert final["outcome"] == OUTCOME_CLOSED
    assert final["verify_status_code"] == 404
    assert generator.prompts == [] and critic.prompts == []  # zero frontier tokens


def test_closed_marker_text_also_closes():
    gone = http_ok(body="This job is no longer available.", status=200)
    graph = build_execution_graph(VARIANTS, model_factory=fake_factory(FakeModel([]), FakeModel([])),
                                  http_client=gone)
    final = graph.invoke(initial_state(APP_ROW))
    assert final["outcome"] == OUTCOME_CLOSED


def test_network_error_does_not_close():
    def raise_err(req):
        raise httpx.ConnectError("boom", request=req)

    flaky = httpx.Client(transport=httpx.MockTransport(raise_err))
    generator = FakeModel(["draft"])
    critic = FakeModel(['{"ats_score": 0.95, "gaps": []}'])
    graph = build_execution_graph(VARIANTS, model_factory=fake_factory(generator, critic),
                                  http_client=flaky)

    final = graph.invoke(initial_state(APP_ROW))

    # transient network trouble is not evidence of closure — the run proceeds
    assert final["outcome"] == OUTCOME_TAILORED


def test_no_resume_variants_is_a_clean_error():
    graph = build_execution_graph([], model_factory=fake_factory(FakeModel([]), FakeModel([])),
                                  http_client=http_ok())
    final = graph.invoke(initial_state(APP_ROW))
    assert final["outcome"] == OUTCOME_ERROR
    assert "resume" in final["error"]


def test_choose_variant_precedence():
    assert choose_variant("Senior Product Manager", VARIANTS)["id"] == "v-core"  # focus match
    assert choose_variant("Marketing Lead", VARIANTS)["id"] == "v-default"       # default
    assert choose_variant("anything", []) is None


def test_critic_route_exits_only_on_threshold_or_cap():
    base = {"ats_threshold": 0.9, "max_iterations": 4}
    assert critic_route({**base, "ats_score": 0.95, "iterations": 1}) == "accept"
    assert critic_route({**base, "ats_score": 0.5, "iterations": 4}) == "accept"
    assert critic_route({**base, "ats_score": 0.5, "iterations": 1}) == "revise"


def test_unparseable_critic_output_scores_zero_not_crash():
    score, gaps = parse_critic_response("I think it looks pretty good!")
    assert score == 0.0 and gaps  # diagnostic gap recorded; cap will end the loop
    score, gaps = parse_critic_response('prose then {"ats_score": 1.7, "gaps": []} more prose')
    assert score == 1.0  # clamped into 0..1
