"""Unit tests for Kanban-lite board assembly — pure, no DB (repo.fetch_icebox stubbed)."""

from aeroapply.config import RankingWeights
from aeroapply.db import repo
from aeroapply.sourcing.ranking import RankingPersona
from aeroapply.sourcing.scheduler import ranking_debug_payload
from aeroapply.ui import board

WEIGHTS = RankingWeights(title=0.35, location=0.25, recency=0.20, competition=0.10, urgency=0.10)
PERSONA = RankingPersona(
    title_alignments=(("ai product manager", 1.0), ("business analyst", 0.6)),
    hybrid_hints=("tampa",),
)


def _icebox_rows():
    """(application_id, job_dict, manual_override) like repo.fetch_icebox returns."""
    base = {"posted_at": None, "applicant_count": None, "closing_date": None}
    return [
        ("app-ai", {"title": "AI Product Manager", "company": "Acme",
                    "location": "Remote", "remote_mode": "remote", **base}, False),
        ("app-ba", {"title": "Business Analyst", "company": "Globex",
                    "location": "Tampa, FL", "remote_mode": "onsite", **base}, False),
    ]


def test_build_board_orders_by_execution_priority(monkeypatch):
    monkeypatch.setattr(repo, "fetch_icebox", lambda conn, uid: _icebox_rows())

    rows = board.build_board(conn=None, user_id="u1", weights=WEIGHTS, persona=PERSONA)

    # AI PM (title 1.0, remote 1.0) outranks Business Analyst (title 0.6) -> first.
    assert [r.application_id for r in rows] == ["app-ai", "app-ba"]
    assert rows[0].execution_priority >= rows[1].execution_priority
    # display fields are carried onto the BoardRow
    assert (rows[0].title, rows[0].company, rows[0].location) == ("AI Product Manager", "Acme", "Remote")
    # the five live score components are present (the #80 ranking_debug seam)
    assert set(rows[0].components) == {"title", "location", "recency", "competition", "urgency"}


def test_manual_override_trumps_to_top(monkeypatch):
    rows = _icebox_rows()
    rows[1] = (rows[1][0], rows[1][1], True)  # promote the otherwise-lower Business Analyst
    monkeypatch.setattr(repo, "fetch_icebox", lambda conn, uid: rows)

    board_rows = board.build_board(conn=None, user_id="u1", weights=WEIGHTS, persona=PERSONA)

    assert board_rows[0].application_id == "app-ba"
    assert board_rows[0].manual_override is True
    assert board_rows[0].execution_priority >= 100.0  # +100 trump dominates any organic score


def test_empty_icebox(monkeypatch):
    monkeypatch.setattr(repo, "fetch_icebox", lambda conn, uid: [])
    assert board.build_board(conn=None, user_id="u1", weights=WEIGHTS, persona=PERSONA) == []


def test_ranking_debug_payload_shape():
    payload = ranking_debug_payload({"title": 1.0}, 0.67, WEIGHTS)
    assert payload["components"] == {"title": 1.0}
    assert payload["execution_priority"] == 0.67
    assert payload["weights"] == WEIGHTS.model_dump()


def test_snapshot_row_persists_the_card_snapshot(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        repo, "set_ranking_debug",
        lambda conn, app_id, payload: captured.update(app_id=app_id, payload=payload),
    )
    row = board.BoardRow(
        application_id="app-ai", title="AI Product Manager", company="Acme",
        location="Remote", remote_mode="remote", manual_override=False,
        components={"title": 1.0, "location": 1.0, "recency": 0.1,
                    "competition": 0.5, "urgency": 0.0},
        execution_priority=0.67,
    )

    board.snapshot_row(conn=None, row=row, weights=WEIGHTS)

    assert captured["app_id"] == "app-ai"
    assert captured["payload"] == ranking_debug_payload(row.components, row.execution_priority, WEIGHTS)
