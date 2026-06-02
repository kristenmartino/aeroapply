"""Unit tests for the WIP scheduler promotion (EPIC-ICE-2) — pure, no DB (repo stubbed)."""

from aeroapply.config import RankingWeights
from aeroapply.db import repo
from aeroapply.sourcing import scheduler
from aeroapply.sourcing.ranking import ScoredJob

WEIGHTS = RankingWeights(title=0.35, location=0.25, recency=0.20, competition=0.10, urgency=0.10)


def _ranked(app_ids):
    """rank_icebox returns [(app_id, ScoredJob)] already sorted desc — fake it in order."""
    return [(aid, ScoredJob(components={"title": 1.0}, execution_priority=1.0)) for aid in app_ids]


def test_promotes_up_to_capacity_in_rank_order(monkeypatch):
    captured = []
    monkeypatch.setattr(repo, "count_active_wip", lambda conn, uid: 1)
    monkeypatch.setattr(scheduler, "rank_icebox", lambda conn, uid, w: _ranked(["a", "b", "c", "d"]))
    monkeypatch.setattr(repo, "mark_queued", lambda conn, app_id, payload: captured.append(app_id))

    promoted = scheduler.promote_to_queued(conn=None, user_id="u1", weights=WEIGHTS, wip_limit=3)

    # wip_limit 3 - active 1 = capacity 2 -> top 2 rows in rank order
    assert promoted == ["a", "b"]
    assert captured == ["a", "b"]


def test_no_promotion_when_wip_full(monkeypatch):
    marked = []
    monkeypatch.setattr(repo, "count_active_wip", lambda conn, uid: 5)
    monkeypatch.setattr(repo, "mark_queued", lambda conn, app_id, payload: marked.append(app_id))

    promoted = scheduler.promote_to_queued(conn=None, user_id="u1", weights=WEIGHTS, wip_limit=5)

    assert promoted == []   # capacity 0 -> idempotent, no over-fill
    assert marked == []


def test_promotion_payload_has_reason_and_priority(monkeypatch):
    captured = {}
    monkeypatch.setattr(repo, "count_active_wip", lambda conn, uid: 0)
    monkeypatch.setattr(
        scheduler, "rank_icebox",
        lambda conn, uid, w: [("a", ScoredJob(components={"title": 1.0}, execution_priority=42.0))],
    )
    monkeypatch.setattr(
        repo, "mark_queued",
        lambda conn, app_id, payload: captured.update(app_id=app_id, payload=payload),
    )

    scheduler.promote_to_queued(conn=None, user_id="u1", weights=WEIGHTS, wip_limit=5)

    assert captured["app_id"] == "a"
    assert captured["payload"] == {"reason": "scheduler", "execution_priority": 42.0, "wip_limit": 5}
