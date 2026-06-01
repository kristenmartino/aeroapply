"""Rank the Icebox in Python — the canonical ordering the scheduler/UI use.

Reads the Icebox via the repo and applies `ranking.rank_jobs` over live
`profile.ranking_weights`. Each result carries `ScoredJob.components`, the seam
that `ranking_debug` telemetry (#80) will persist.
"""

from __future__ import annotations

import psycopg

from aeroapply.config import RankingWeights
from aeroapply.db import repo
from aeroapply.sourcing.ranking import ScoredJob, rank_jobs


def rank_icebox(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights
) -> list[tuple[str, ScoredJob]]:
    rows = repo.fetch_icebox(conn, user_id)
    return rank_jobs(rows, weights)


def snapshot_ranking_debug(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights
) -> list[tuple[str, ScoredJob]]:
    """Persist each Icebox row's ranking snapshot (#80) and return the same ranking.

    Reuses ``rank_icebox`` so the canonical ordering is unchanged — this only writes
    the explanatory features (``components`` + ``execution_priority`` + the ``weights``
    used) into ``application.ranking_debug`` for calibration. Does NOT mutate ranking
    behavior; the caller owns the transaction and commits.
    """
    ranked = rank_icebox(conn, user_id, weights)
    weights_snapshot = weights.model_dump()
    for app_id, scored in ranked:
        repo.set_ranking_debug(
            conn,
            app_id,
            {
                "components": scored.components,
                "execution_priority": scored.execution_priority,
                "weights": weights_snapshot,
            },
        )
    return ranked


__all__ = ["rank_icebox", "snapshot_ranking_debug"]
