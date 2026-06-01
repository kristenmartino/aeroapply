"""Unit test for ranking_debug snapshotting (#80) — pure, no DB (repo stubbed)."""

from aeroapply.config import RankingWeights
from aeroapply.db import repo
from aeroapply.sourcing import scheduler

WEIGHTS = RankingWeights(title=0.35, location=0.25, recency=0.20, competition=0.10, urgency=0.10)


def _icebox_rows():
    """(application_id, job_dict, manual_override) like repo.fetch_icebox returns."""
    base = {"posted_at": None, "applicant_count": None, "closing_date": None}
    return [
        ("app-ai", {"title": "AI Product Manager", "company": "Acme",
                    "location": "Remote", "remote_mode": "remote", **base}, False),
        ("app-ba", {"title": "Business Analyst", "company": "Globex",
                    "location": "Jupiter, FL", "remote_mode": "onsite", **base}, False),
    ]


def test_snapshot_persists_payload_and_preserves_order(monkeypatch):
    captured: dict[str, dict] = {}
    monkeypatch.setattr(repo, "fetch_icebox", lambda conn, uid: _icebox_rows())
    monkeypatch.setattr(
        repo, "set_ranking_debug",
        lambda conn, app_id, payload: captured.__setitem__(app_id, payload),
    )

    ranked = scheduler.snapshot_ranking_debug(conn=None, user_id="u1", weights=WEIGHTS)

    # Ordering is exactly what rank_icebox would return: AI PM (title 1.0) first.
    assert [app_id for app_id, _ in ranked] == ["app-ai", "app-ba"]

    # Every ranked row got a set_ranking_debug call with a faithful payload.
    assert set(captured) == {"app-ai", "app-ba"}
    for app_id, scored in ranked:
        payload = captured[app_id]
        assert payload["components"] == scored.components
        assert payload["execution_priority"] == scored.execution_priority
        assert payload["weights"]["title"] == 0.35
