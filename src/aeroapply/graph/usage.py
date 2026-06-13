"""Per-run token usage + cost telemetry (#31).

The execution graph calls models through an injected factory. To trace what a run
actually cost without touching the pure node code, the driver wraps that factory so
every `.invoke()` response is tallied into a `UsageTracker` — input/output tokens per
model — which is then persisted to the `run` row's `meta`.

Token counts are *factual* (read from the provider's `usage_metadata`). Dollar cost is
NOT — it depends on the operator's pricing, so `estimate_cost_usd` takes a caller-supplied
rates table and returns `None` when rates are unknown. We never invent prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CallUsage:
    node: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class UsageTracker:
    """Accumulates per-call token usage across a single graph run."""

    calls: list[CallUsage] = field(default_factory=list)

    def record(self, node: str, response: Any) -> None:
        """Tally one model response. Missing usage (e.g. test fakes) records zeros."""
        usage = getattr(response, "usage_metadata", None) or {}
        meta = getattr(response, "response_metadata", None) or {}
        model = str(meta.get("model") or meta.get("model_name") or "unknown")
        self.calls.append(
            CallUsage(
                node=node,
                model=model,
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
            )
        )

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    def by_model(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for c in self.calls:
            m = out.setdefault(c.model, {"input_tokens": 0, "output_tokens": 0, "calls": 0})
            m["input_tokens"] += c.input_tokens
            m["output_tokens"] += c.output_tokens
            m["calls"] += 1
        return out

    def to_meta(self) -> dict[str, Any]:
        """The JSON-serializable usage block stored in `run.meta`."""
        return {
            "calls": len(self.calls),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "by_model": self.by_model(),
        }


class _TrackingModel:
    """Proxy that records usage on `.invoke()` and delegates everything else."""

    def __init__(self, inner: Any, node: str, tracker: UsageTracker) -> None:
        self._inner = inner
        self._node = node
        self._tracker = tracker

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        response = self._inner.invoke(*args, **kwargs)
        self._tracker.record(self._node, response)
        return response

    def __getattr__(self, name: str) -> Any:  # delegate non-invoke access transparently
        return getattr(self._inner, name)


def wrap_factory_with_usage(
    model_factory: Any, tracker: UsageTracker
) -> Any:
    """Wrap a `node -> chat model` factory so each model's `.invoke()` is metered."""

    def wrapped(node: str) -> Any:
        return _TrackingModel(model_factory(node), node, tracker)

    return wrapped


# Rates: USD per 1,000,000 tokens, (input, output). Empty by default — the operator
# supplies their own pricing; we do not ship invented numbers.
Rates = dict[str, tuple[float, float]]


def estimate_cost_usd(usage: UsageTracker, rates: Rates) -> float | None:
    """Estimate run cost from per-model token counts, or None if any model lacks a rate.

    Returning None (rather than guessing) keeps token counts as the trustworthy metric
    and makes "rates not configured" explicit instead of a silently-wrong dollar figure.
    """
    if not rates:
        return None
    total = 0.0
    for model, m in usage.by_model().items():
        if model not in rates:
            return None
        rin, rout = rates[model]
        total += m["input_tokens"] / 1_000_000 * rin + m["output_tokens"] / 1_000_000 * rout
    return round(total, 6)


__all__ = [
    "CallUsage",
    "UsageTracker",
    "wrap_factory_with_usage",
    "estimate_cost_usd",
    "Rates",
]
