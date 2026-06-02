"""Pure, Streamlit-free assembly of the ranked Icebox board.

`build_board` reads the Icebox via `db.repo.fetch_icebox` and orders it with
`ranking.rank_jobs` over live `profile.ranking_weights` — the same canonical ordering
`sourcing.scheduler.rank_icebox` uses — then joins the human-legible display fields onto
each `ScoredJob`. Kept import-light (no Streamlit) so it is unit-testable without a DB
(monkeypatch `repo.fetch_icebox`). The render shell is `ui/kanban.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from aeroapply.config import RankingWeights
from aeroapply.db import repo
from aeroapply.sourcing.ranking import rank_jobs
from aeroapply.sourcing.scheduler import ranking_debug_payload


@dataclass(frozen=True)
class BoardRow:
    """One Icebox card: ranking output joined with the fields the operator reads."""

    application_id: str
    title: str
    company: str
    location: str
    remote_mode: str
    manual_override: bool
    components: dict[str, float]
    execution_priority: float


def build_board(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights
) -> list[BoardRow]:
    """Return the Icebox as ranked `BoardRow`s (highest execution_priority first)."""
    rows = repo.fetch_icebox(conn, user_id)
    jobs_by_id = {app_id: (job, mo) for app_id, job, mo in rows}
    board: list[BoardRow] = []
    for app_id, scored in rank_jobs(rows, weights):
        job, mo = jobs_by_id[app_id]
        board.append(
            BoardRow(
                application_id=str(app_id),
                title=job.get("title") or "",
                company=job.get("company") or "",
                location=job.get("location") or "",
                remote_mode=job.get("remote_mode") or "",
                manual_override=mo,
                components=scored.components,
                execution_priority=scored.execution_priority,
            )
        )
    return board


def snapshot_row(conn: psycopg.Connection, row: BoardRow, weights: RankingWeights) -> None:
    """Persist this card's ranking snapshot so a subsequent Promote/Drop event is paired.

    Writes the BoardRow's already-computed ranker features (the same values rendered on
    the card) to `application.ranking_debug` via `repo.set_ranking_debug`. Caller commits.
    """
    repo.set_ranking_debug(
        conn,
        row.application_id,
        ranking_debug_payload(row.components, row.execution_priority, weights),
    )


__all__ = ["BoardRow", "build_board", "snapshot_row"]
