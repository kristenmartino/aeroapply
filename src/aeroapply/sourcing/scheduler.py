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
from aeroapply.sourcing.ranking import ScoredJob, rank_jobs


def rank_icebox(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights
) -> list[tuple[str, ScoredJob]]:
    rows = repo.fetch_icebox(conn, user_id)
    return rank_jobs(rows, weights)


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
    conn: psycopg.Connection, user_id: str, weights: RankingWeights
) -> list[tuple[str, ScoredJob]]:
    """Persist each Icebox row's ranking snapshot (#80) and return the same ranking.

    Reuses ``rank_icebox`` so the canonical ordering is unchanged — this only writes
    the explanatory features (``components`` + ``execution_priority`` + the ``weights``
    used) into ``application.ranking_debug`` for calibration. Does NOT mutate ranking
    behavior; the caller owns the transaction and commits.
    """
    ranked = rank_icebox(conn, user_id, weights)
    for app_id, scored in ranked:
        repo.set_ranking_debug(
            conn,
            app_id,
            ranking_debug_payload(scored.components, scored.execution_priority, weights),
        )
    return ranked


def promote_to_queued(
    conn: psycopg.Connection, user_id: str, weights: RankingWeights, wip_limit: int
) -> list[str]:
    """Promote the top-ranked Icebox rows to queued, up to the WIP limit (EPIC-ICE-2).

    Tops the queue up to ``wip_limit`` (counting already queued/active rows), so it is
    idempotent: a re-run with a full queue promotes nothing. Selection reuses
    ``rank_icebox`` so ``manual_override`` rows (the +100 trump) lead organic ones. Each
    promotion writes a 'system' ``application_event`` via ``repo.mark_queued``. The caller
    owns the transaction and commits. Returns the promoted application ids.
    """
    capacity = max(0, wip_limit - repo.count_active_wip(conn, user_id))
    if capacity == 0:
        return []
    promoted: list[str] = []
    for app_id, scored in rank_icebox(conn, user_id, weights)[:capacity]:
        repo.mark_queued(
            conn,
            app_id,
            {
                "reason": "scheduler",
                "execution_priority": scored.execution_priority,
                "wip_limit": wip_limit,
            },
        )
        promoted.append(app_id)
    return promoted


__all__ = [
    "rank_icebox", "snapshot_ranking_debug", "ranking_debug_payload", "promote_to_queued",
]
