"""Per-run usage telemetry unit tests (#31) — no DB, no network."""

from __future__ import annotations

from aeroapply.graph.usage import (
    UsageTracker,
    estimate_cost_usd,
    wrap_factory_with_usage,
)


class FakeMsg:
    def __init__(self, content: str, *, usage=None, model=None):
        self.content = content
        if usage is not None:
            self.usage_metadata = usage
        if model is not None:
            self.response_metadata = {"model": model}


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.prompts: list = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.response


def test_tracker_accumulates_tokens_per_model():
    tracker = UsageTracker()
    tracker.record("tailor.generator",
                   FakeMsg("draft", usage={"input_tokens": 100, "output_tokens": 400},
                           model="claude-opus-4-8"))
    tracker.record("tailor.critic",
                   FakeMsg("score", usage={"input_tokens": 50, "output_tokens": 20},
                           model="claude-sonnet-4-6"))
    tracker.record("tailor.generator",
                   FakeMsg("draft2", usage={"input_tokens": 120, "output_tokens": 380},
                           model="claude-opus-4-8"))

    assert tracker.input_tokens == 270
    assert tracker.output_tokens == 800
    by_model = tracker.by_model()
    assert by_model["claude-opus-4-8"] == {"input_tokens": 220, "output_tokens": 780, "calls": 2}
    assert by_model["claude-sonnet-4-6"]["calls"] == 1
    meta = tracker.to_meta()
    assert meta["calls"] == 3 and meta["input_tokens"] == 270


def test_missing_usage_records_zeros_not_crash():
    tracker = UsageTracker()
    tracker.record("tailor.generator", FakeMsg("draft"))  # no usage_metadata (a test fake)
    assert tracker.input_tokens == 0 and tracker.output_tokens == 0
    assert tracker.by_model()["unknown"]["calls"] == 1


def test_wrap_factory_meters_invoke_and_passes_response_through():
    tracker = UsageTracker()
    msg = FakeMsg("draft", usage={"input_tokens": 10, "output_tokens": 5}, model="m")
    factory = wrap_factory_with_usage(lambda node: FakeModel(msg), tracker)

    out = factory("tailor.generator").invoke("hi")

    assert out is msg                       # response passes through untouched
    assert tracker.input_tokens == 10 and tracker.output_tokens == 5
    assert tracker.calls[0].node == "tailor.generator"


def test_estimate_cost_none_without_rates_and_for_unknown_model():
    tracker = UsageTracker()
    tracker.record("g", FakeMsg("x", usage={"input_tokens": 1_000_000, "output_tokens": 0},
                                model="claude-opus-4-8"))
    assert estimate_cost_usd(tracker, {}) is None                      # no rates -> unknown
    assert estimate_cost_usd(tracker, {"other-model": (1.0, 1.0)}) is None  # model not priced


def test_estimate_cost_sums_per_model_when_rates_supplied():
    tracker = UsageTracker()
    tracker.record("g", FakeMsg("x", usage={"input_tokens": 2_000_000, "output_tokens": 1_000_000},
                                model="opus"))
    tracker.record("c", FakeMsg("y", usage={"input_tokens": 1_000_000, "output_tokens": 0},
                                model="sonnet"))
    rates = {"opus": (5.0, 25.0), "sonnet": (3.0, 15.0)}
    # opus: 2*5 + 1*25 = 35 ; sonnet: 1*3 + 0 = 3 ; total 38
    assert estimate_cost_usd(tracker, rates) == 38.0
