"""Config-driven execution-priority ranking — the CANONICAL ranking path.

Weights live in config (`profile.ranking_weights`) and are applied here in Python,
NOT in SQL, so they can be tuned live without a migration (see docs/CALIBRATION.md).
The `v_icebox_ranked` SQL view keeps the same formula with frozen weights and is now
a debug / fallback only — not the source of truth for ordering.

The *persona* (which titles count as core/adjacent, which locations count as
hybrid-friendly) is config too: `RankingPersona.from_profile(profile)` derives it
from `profile.target_roles` + `profile.search_profile.locations`, so no operator
target titles or locations are hard-coded here (PII boundary, Brief §2).
`EXAMPLE_PERSONA` mirrors the fictional persona in `config/profile.example.yaml`
and exists for tests/fixtures only.

Feature sub-scores mirror the brief's rubric. One deliberate difference from the
frozen view: an unknown `applicant_count` scores a neutral 0.5 (unknown ≠ crowded)
rather than 0.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aeroapply.config import RankingWeights

BASELINE_ALIGNMENT = 0.3  # any title not matching a target role still scores something


@dataclass(frozen=True)
class RankingPersona:
    """The operator-specific inputs to ranking, derived from config — never hard-coded.

    `title_alignments` are (lowercased substring, alignment) pairs; the best match
    wins. `hybrid_hints` are lowercased location substrings that mark a non-remote
    posting as commutable-hybrid (scores 0.8).
    """

    title_alignments: tuple[tuple[str, float], ...]
    hybrid_hints: tuple[str, ...]
    baseline_alignment: float = BASELINE_ALIGNMENT

    @classmethod
    def from_profile(cls, profile: Any) -> RankingPersona:
        """Build from a `config.Profile` (duck-typed to avoid an import cycle)."""
        titles = tuple(
            (r.title.strip().lower(), float(r.alignment))
            for r in profile.target_roles
            if r.title.strip()
        )
        hints = tuple(
            loc.split(",")[0].strip().lower()
            for loc in profile.search_profile.locations
            if loc.strip() and loc.strip().lower() != "remote"
        )
        return cls(title_alignments=titles, hybrid_hints=hints)


# Mirrors the FICTIONAL example persona in config/profile.example.yaml (and the frozen
# v_icebox_ranked debug view). For tests/fixtures — real runs derive from profile.yaml.
EXAMPLE_PERSONA = RankingPersona(
    title_alignments=(
        ("product manager", 1.0),
        ("solutions architect", 1.0),
        ("business analyst", 0.6),
        ("project manager", 0.6),
    ),
    hybrid_hints=("springfield",),
)


def title_score(title: str | None, persona: RankingPersona) -> float:
    t = (title or "").lower()
    matched = [a for needle, a in persona.title_alignments if needle in t]
    return max(matched, default=persona.baseline_alignment)


def location_score(remote_mode: str | None, location: str | None, persona: RankingPersona) -> float:
    if (remote_mode or "").lower() == "remote":
        return 1.0
    if any(hint in (location or "").lower() for hint in persona.hybrid_hints):
        return 0.8
    return 0.0


def recency_score(posted_at: datetime | None, now: datetime) -> float:
    if posted_at is None:
        return 0.1
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    age_days = max(0, (now - posted_at).days)  # future-dated/clock-skew -> fresh, never negative
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
    persona: RankingPersona,
    *,
    manual_override: bool = False,
    now: datetime | None = None,
) -> ScoredJob:
    """Compute execution_priority for one job dict using live config weights + persona."""
    now = now or datetime.now(UTC)
    components = {
        "title": title_score(job.get("title"), persona),
        "location": location_score(job.get("remote_mode"), job.get("location"), persona),
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
    persona: RankingPersona,
    now: datetime | None = None,
) -> list[tuple[Any, ScoredJob]]:
    """Rank ``(id, job_dict, manual_override)`` tuples by execution_priority desc."""
    now = now or datetime.now(UTC)
    scored = [
        (jid, score_job(job, weights, persona, manual_override=mo, now=now))
        for jid, job, mo in jobs
    ]
    scored.sort(key=lambda pair: pair[1].execution_priority, reverse=True)
    return scored


__all__ = [
    "RankingPersona",
    "EXAMPLE_PERSONA",
    "BASELINE_ALIGNMENT",
    "ScoredJob",
    "score_job",
    "rank_jobs",
    "title_score",
    "location_score",
    "recency_score",
    "competition_score",
    "urgency_score",
]
