"""cover_letter node unit tests (#38) — no DB, no network, no API key."""

from __future__ import annotations

import httpx

from aeroapply.graph.execution import build_execution_graph, initial_state
from aeroapply.graph.state import OUTCOME_TAILORED
from aeroapply.nodes.cover_letter import make_cover_letter

APP_ROW = {
    "application_id": "app-1", "job_title": "Product Manager", "company": "Acme",
    "job_description": "Own the roadmap.", "job_location": "Remote",
    "portal_url": "https://boards.example.com/jobs/1", "portal_type": "greenhouse",
}
VARIANTS = [{"id": "v1", "profile_name": "base", "role_focus": "Product Manager",
             "raw_text": "BASE", "is_default": True}]


class FakeModel:
    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("Msg", (), {"content": self.replies.pop(0)})()


def http_ok():
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="open")))


def test_node_disabled_is_a_noop():
    model = FakeModel(["should not be used"])
    node = make_cover_letter(lambda n: model, enabled=False)
    assert node({"job_title": "x"}) == {}
    assert model.prompts == []          # no model call when disabled


def test_node_enabled_generates_grounded_in_the_tailored_resume():
    model = FakeModel(["Dear team, I shipped roadmaps..."])
    node = make_cover_letter(lambda n: model, enabled=True)
    out = node({"job_title": "Product Manager", "company": "Acme",
                "job_description": "roadmap", "draft_resume_text": "TAILORED RESUME TEXT"})
    assert out["cover_letter"].startswith("Dear team")
    prompt = model.prompts[0]
    assert "TAILORED RESUME TEXT" in prompt and "Acme" in prompt
    assert "HONESTY" in prompt          # the never-fabricate guard is in the prompt


def test_graph_generates_cover_letter_when_enabled():
    gen = FakeModel(["tailored draft"])
    crit = FakeModel(['{"ats_score": 0.95, "gaps": []}'])
    cover = FakeModel(["A grounded cover letter."])

    def factory(node):
        return {"tailor.generator": gen, "tailor.critic": crit, "cover_letter": cover}[node]

    graph = build_execution_graph(VARIANTS, model_factory=factory, http_client=http_ok(),
                                  cover_letter_enabled=True)
    final = graph.invoke(initial_state(APP_ROW))

    assert final["outcome"] == OUTCOME_TAILORED
    assert final["cover_letter"] == "A grounded cover letter."
    assert "tailored draft" in cover.prompts[0]   # grounded in the tailored résumé


def test_graph_skips_cover_letter_by_default():
    gen = FakeModel(["tailored draft"])
    crit = FakeModel(['{"ats_score": 0.95, "gaps": []}'])

    def factory(node):
        return gen if node == "tailor.generator" else crit

    graph = build_execution_graph(VARIANTS, model_factory=factory, http_client=http_ok())
    final = graph.invoke(initial_state(APP_ROW))    # cover_letter_enabled defaults False

    assert final["outcome"] == OUTCOME_TAILORED
    assert "cover_letter" not in final              # node was a no-op
