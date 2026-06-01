from datetime import UTC, datetime, timedelta

from aeroapply.config import RankingWeights
from aeroapply.sourcing.ranking import (
    location_score,
    rank_jobs,
    recency_score,
    score_job,
    title_score,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)

TITLE_HEAVY = RankingWeights(title=0.8, location=0.05, recency=0.05, competition=0.05, urgency=0.05)
LOCATION_HEAVY = RankingWeights(title=0.05, location=0.8, recency=0.05, competition=0.05, urgency=0.05)

AI_PM_ONSITE = {"title": "AI Product Manager", "remote_mode": "onsite", "location": "Austin, TX"}
GENERIC_REMOTE = {"title": "Operations Coordinator", "remote_mode": "remote", "location": "Anywhere"}


def test_title_and_location_scores():
    assert title_score("Senior AI Product Manager") == 1.0
    assert title_score("Senior Business Analyst") == 0.6
    assert title_score("Operations Coordinator") == 0.3
    assert location_score("remote", None) == 1.0
    assert location_score("hybrid", "Jupiter, FL") == 0.8
    assert location_score("onsite", "Austin, TX") == 0.0


def test_weights_change_ordering_without_migration():
    jobs = [("A", AI_PM_ONSITE, False), ("B", GENERIC_REMOTE, False)]
    title_first = rank_jobs(jobs, TITLE_HEAVY, now=NOW)
    location_first = rank_jobs(jobs, LOCATION_HEAVY, now=NOW)
    assert title_first[0][0] == "A"      # title-heavy -> AI PM ranks first
    assert location_first[0][0] == "B"   # location-heavy -> remote ranks first


def test_manual_override_trumps():
    low = score_job(GENERIC_REMOTE, TITLE_HEAVY, manual_override=True, now=NOW)
    high = score_job(AI_PM_ONSITE, TITLE_HEAVY, manual_override=False, now=NOW)
    assert low.execution_priority > high.execution_priority


def test_recency_future_dated_is_clamped_fresh():
    # A future/clock-skewed posted_at must not yield a negative age (which would score top).
    assert recency_score(NOW + timedelta(hours=2), NOW) == 1.0
    assert recency_score(NOW - timedelta(days=30), NOW) == 0.1
