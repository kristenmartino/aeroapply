from datetime import UTC, datetime, timedelta

from aeroapply.config import RankingWeights, load_profile
from aeroapply.sourcing.ranking import (
    EXAMPLE_PERSONA,
    RankingPersona,
    location_score,
    rank_jobs,
    recency_score,
    score_job,
    title_score,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)

TITLE_HEAVY = RankingWeights(title=0.8, location=0.05, recency=0.05, competition=0.05, urgency=0.05)
LOCATION_HEAVY = RankingWeights(title=0.05, location=0.8, recency=0.05, competition=0.05, urgency=0.05)

# Fictional persona constructed inline — tests never depend on any real operator values.
PERSONA = RankingPersona(
    title_alignments=(
        ("ai product manager", 1.0),
        ("business analyst", 0.6),
    ),
    hybrid_hints=("tampa",),
)

AI_PM_ONSITE = {"title": "AI Product Manager", "remote_mode": "onsite", "location": "Austin, TX"}
GENERIC_REMOTE = {"title": "Operations Coordinator", "remote_mode": "remote", "location": "Anywhere"}


def test_title_and_location_scores_follow_the_persona():
    assert title_score("Senior AI Product Manager", PERSONA) == 1.0
    assert title_score("Senior Business Analyst", PERSONA) == 0.6
    assert title_score("Operations Coordinator", PERSONA) == 0.3  # baseline
    assert location_score("remote", None, PERSONA) == 1.0
    assert location_score("hybrid", "Tampa, FL", PERSONA) == 0.8
    assert location_score("onsite", "Austin, TX", PERSONA) == 0.0


def test_best_matching_alignment_wins():
    overlapping = RankingPersona(
        title_alignments=(("product manager", 0.6), ("ai product manager", 1.0)),
        hybrid_hints=(),
    )
    assert title_score("AI Product Manager", overlapping) == 1.0  # max, not first match


def test_persona_from_profile_derives_titles_and_hints():
    profile = load_profile("config/profiles/jordan-aipm.yaml")
    persona = RankingPersona.from_profile(profile)
    assert ("ai product manager", 1.0) in persona.title_alignments
    assert ("senior business analyst", 0.6) in persona.title_alignments
    assert "tampa" in persona.hybrid_hints
    assert "remote" not in persona.hybrid_hints  # 'Remote' is not a hybrid hint


def test_example_persona_matches_the_example_profile():
    persona = RankingPersona.from_profile(load_profile("config/profile.example.yaml"))
    assert persona.title_alignments == EXAMPLE_PERSONA.title_alignments
    assert persona.hybrid_hints == EXAMPLE_PERSONA.hybrid_hints


def test_weights_change_ordering_without_migration():
    jobs = [("A", AI_PM_ONSITE, False), ("B", GENERIC_REMOTE, False)]
    title_first = rank_jobs(jobs, TITLE_HEAVY, PERSONA, now=NOW)
    location_first = rank_jobs(jobs, LOCATION_HEAVY, PERSONA, now=NOW)
    assert title_first[0][0] == "A"      # title-heavy -> AI PM ranks first
    assert location_first[0][0] == "B"   # location-heavy -> remote ranks first


def test_manual_override_trumps():
    low = score_job(GENERIC_REMOTE, TITLE_HEAVY, PERSONA, manual_override=True, now=NOW)
    high = score_job(AI_PM_ONSITE, TITLE_HEAVY, PERSONA, manual_override=False, now=NOW)
    assert low.execution_priority > high.execution_priority


def test_recency_future_dated_is_clamped_fresh():
    # A future/clock-skewed posted_at must not yield a negative age (which would score top).
    assert recency_score(NOW + timedelta(hours=2), NOW) == 1.0
    assert recency_score(NOW - timedelta(days=30), NOW) == 0.1
