"""Rank the Icebox in Python — the canonical ordering the scheduler/UI use.

Reads the Icebox via the repo and applies `ranking.rank_jobs` over live
`profile.ranking_weights`. Each result carries `ScoredJob.components`, the seam
that `ranking_debug` telemetry (#80) will persist.
"""

from __future__ import annotations

from typing import Any

import psycopg

from aeroapply.config import RankingWeights
from aeroapply.db import repo
from aeroapply.sourcing.ranking import RankingPersona, ScoredJob, rank_jobs


def rank_icebox(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights, persona: RankingPersona
) -> list[tuple[str, ScoredJob]]:
    rows = repo.fetch_icebox(conn, user_id)
    return rank_jobs(rows, weights, persona)


def ranking_debug_payload(
    components: dict[str, float], execution_priority: float, weights: RankingWeights
) -> dict[str, Any]:
    """The `application.ranking_debug` snapshot shape: ranker features + the weights used."""
    return {
        "components": components,
        "execution_priority": execution_priority,
        "weights": weights.model_dump(),
    }


def snapshot_ranking_debug(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights, persona: RankingPersona
) -> list[tuple[str, ScoredJob]]:
    """Persist each Icebox row's ranking snapshot (#80) and return the same ranking.

    Reuses ``rank_icebox`` so the canonical ordering is unchanged — this only writes
    the explanatory features (``components`` + ``execution_priority`` + the ``weights``
    used) into ``application.ranking_debug`` for calibration. Does NOT mutate ranking
    behavior; the caller owns the transaction and commits.
    """
    ranked = rank_icebox(conn, user_id, weights, persona)
    for app_id, scored in ranked:
        repo.set_ranking_debug(
            conn,
            app_id,
            ranking_debug_payload(scored.components, scored.execution_priority, weights),
        )
    return ranked


__all__ = ["rank_icebox", "snapshot_ranking_debug", "ranking_debug_payload"]
