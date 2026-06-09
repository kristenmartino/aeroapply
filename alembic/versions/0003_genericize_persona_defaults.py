"""Genericize persona defaults (PII scrub)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-09

Removes the operator-specific values that were baked into the schema: the
`v_icebox_ranked` debug view's title/location CASE arms now encode the FICTIONAL
example persona (config/profile.example.yaml / ranking.EXAMPLE_PERSONA), and
`search_profile.salary_floor` defaults to 0 (no floor until configured).

Migration 0001 was scrubbed in place to match (no prod DB exists yet — Railway is
M6); this revision exists so dev databases migrated before the scrub converge on
the same view without a rebuild. Fresh databases get the generic view from 0001 and
this CREATE OR REPLACE is a no-op-equivalent. Canonical ranking remains the
profile-driven Python ranker (`ranking.rank_jobs`); the view is debug/fallback only.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENERIC_VIEW = """
CREATE OR REPLACE VIEW v_icebox_ranked AS
SELECT
    a.id              AS application_id,
    a.job_id,
    j.company,
    j.title,
    j.remote_mode,
    j.posted_at,
    j.closing_date,
    j.applicant_count,
    (
      (CASE WHEN a.manual_override THEN 100.0 ELSE 0.0 END)
      + 0.35 * (CASE
          WHEN j.title ILIKE '%Product Manager%'
            OR j.title ILIKE '%Solutions Architect%' THEN 1.0
          WHEN j.title ILIKE '%Business Analyst%'
            OR j.title ILIKE '%Project Manager%' THEN 0.6
          ELSE 0.3 END)
      + 0.25 * (CASE
          WHEN j.remote_mode = 'remote' THEN 1.0
          WHEN j.location ILIKE '%Springfield%' THEN 0.8
          ELSE 0.0 END)
      + 0.20 * (CASE
          WHEN j.posted_at >= now() - INTERVAL '2 days' THEN 1.0
          WHEN j.posted_at >= now() - INTERVAL '7 days' THEN 0.5
          ELSE 0.1 END)
      + 0.10 * (CASE
          WHEN j.applicant_count < 50  THEN 1.0
          WHEN j.applicant_count < 150 THEN 0.5
          ELSE 0.0 END)
      + 0.10 * (CASE
          WHEN j.closing_date IS NOT NULL AND j.closing_date <= now() + INTERVAL '3 days' THEN 1.0
          ELSE 0.0 END)
    ) AS execution_priority
FROM application a
JOIN job j ON j.id = a.job_id
WHERE a.wip_status = 'icebox'
  AND a.status = 'sourced'
ORDER BY execution_priority DESC
"""


def upgrade() -> None:
    op.execute(GENERIC_VIEW)
    op.execute("ALTER TABLE search_profile ALTER COLUMN salary_floor SET DEFAULT 0")


def downgrade() -> None:
    # Intentionally NOT restoring the pre-scrub persona arms (that would re-commit
    # operator-specific values). The generic view stands; only the default reverts.
    op.execute("ALTER TABLE search_profile ALTER COLUMN salary_floor SET DEFAULT 0")
