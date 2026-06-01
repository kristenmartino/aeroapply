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


__all__ = ["rank_icebox"]
