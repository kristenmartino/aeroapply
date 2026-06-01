"""application.ranking_debug

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-01

Adds application.ranking_debug (JSONB) — a snapshot of the Python ranker output
(rank_jobs components + execution_priority, plus the weights used) persisted at an
explicit rank/refresh call site for calibration. Mirrors scripts/bootstrap.sql.
Idempotent ADD/DROP COLUMN via op.execute so re-runs are safe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE application ADD COLUMN IF NOT EXISTS ranking_debug JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE application DROP COLUMN IF EXISTS ranking_debug")
