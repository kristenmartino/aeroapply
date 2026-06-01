"""Config-driven execution-priority ranking — the CANONICAL ranking path.

Weights live in config (`profile.ranking_weights`) and are applied here in Python,
NOT in SQL, so they can be tuned live without a migration (see docs/CALIBRATION.md).
The `v_icebox_ranked` SQL view keeps the same formula with frozen weights and is now
a debug / fallback only — not the source of truth for ordering.

Feature sub-scores mirror the brief's rubric. One deliberate difference from the
frozen view: an unknown `applicant_count` scores a neutral 0.5 (unknown ≠ crowded)
rather than 0.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aeroapply.config import RankingWeights

CORE_TITLES = ("ai product manager", "ai solutions architect")
ADJACENT_TITLES = ("business analyst", "technical project manager")
HYBRID_HINTS = ("jupiter", "west palm")


def title_score(title: str | None) -> float:
    t = (title or "").lower()
    if any(k in t for k in CORE_TITLES):
        return 1.0
    if any(k in t for k in ADJACENT_TITLES):
        return 0.6
    return 0.3


def location_score(remote_mode: str | None, location: str | None) -> float:
    if (remote_mode or "").lower() == "remote":
        return 1.0
    if any(k in (location or "").lower() for k in HYBRID_HINTS):
        return 0.8
    return 0.0


def recency_score(posted_at: datetime | None, now: datetime) -> float:
    if posted_at is None:
        return 0.1
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    age_days = (now - posted_at).days
    if age_days <= 2:
        return 1.0
    if age_days <= 7:
        return 0.5
    return 0.1


def competition_score(applicant_count: int | None) -> float:
    if applicant_count is None:
        return 0.5  # unknown -> neutral (differs from the frozen view's 0.0)
    if applicant_count < 50:
        return 1.0
    if applicant_count < 150:
        return 0.5
    return 0.0


def urgency_score(closing_date: datetime | None, now: datetime) -> float:
    if closing_date is None:
        return 0.0
    if closing_date.tzinfo is None:
        closing_date = closing_date.replace(tzinfo=UTC)
    return 1.0 if closing_date <= now + timedelta(days=3) else 0.0


@dataclass
class ScoredJob:
    components: dict[str, float]
    execution_priority: float


def score_job(
    job: dict[str, Any],
    weights: RankingWeights,
    *,
    manual_override: bool = False,
    now: datetime | None = None,
) -> ScoredJob:
    """Compute execution_priority for one job dict using live config weights."""
    now = now or datetime.now(UTC)
    components = {
        "title": title_score(job.get("title")),
        "location": location_score(job.get("remote_mode"), job.get("location")),
        "recency": recency_score(job.get("posted_at"), now),
        "competition": competition_score(job.get("applicant_count")),
        "urgency": urgency_score(job.get("closing_date"), now),
    }
    weighted = (
        weights.title * components["title"]
        + weights.location * components["location"]
        + weights.recency * components["recency"]
        + weights.competition * components["competition"]
        + weights.urgency * components["urgency"]
    )
    priority = (100.0 if manual_override else 0.0) + weighted
    return ScoredJob(components=components, execution_priority=priority)


def rank_jobs(
    jobs: list[tuple[Any, dict[str, Any], bool]],
    weights: RankingWeights,
    now: datetime | None = None,
) -> list[tuple[Any, ScoredJob]]:
    """Rank ``(id, job_dict, manual_override)`` tuples by execution_priority desc."""
    now = now or datetime.now(UTC)
    scored = [(jid, score_job(job, weights, manual_override=mo, now=now)) for jid, job, mo in jobs]
    scored.sort(key=lambda pair: pair[1].execution_priority, reverse=True)
    return scored


__all__ = [
    "ScoredJob",
    "score_job",
    "rank_jobs",
    "title_score",
    "location_score",
    "recency_score",
    "competition_score",
    "urgency_score",
]
