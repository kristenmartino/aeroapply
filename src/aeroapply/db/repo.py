"""Minimal synchronous DB access for read-only sourcing ingestion.

Scope: ensure the operator row, upsert survivors as `job` + icebox `application`,
read the Icebox for Python ranking, and apply operator Promote/Drop curation with
an audit event. **No submission / credential / apply code lives here.** The async
pool + full DAL is #14; the richer review telemetry (`ranking_debug`,
`human_approved_unchanged`, …) is #80 — this only opens those seams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aeroapply.config import Profile
from aeroapply.connectors.base import NormalizedPosting


@dataclass
class UpsertCounts:
    jobs_inserted: int = 0
    applications_inserted: int = 0
    deduped: int = 0


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def ensure_operator(conn: psycopg.Connection, profile: Profile) -> str:
    op = profile.operator
    row = conn.execute(
        "SELECT id FROM app_user WHERE primary_email = %s", (op.primary_email,)
    ).fetchone()
    if row is not None:
        return str(row[0])
    new = conn.execute(
        """INSERT INTO app_user (name, primary_email, agent_email, headline,
                                 home_lat, home_lon, work_auth)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (op.name, op.primary_email, op.agent_email, op.headline,
         op.home.lat, op.home.lon, op.work_auth),
    ).fetchone()
    assert new is not None
    return str(new[0])


_JOB_INSERT = """
INSERT INTO job (external_id, company, title, location, remote_mode, lat, lon,
                 salary_min, salary_max, currency, description, url, portal_url,
                 portal_type, posted_at, closing_date, applicant_count, fingerprint, raw)
VALUES (%(external_id)s, %(company)s, %(title)s, %(location)s, %(remote_mode)s, %(lat)s, %(lon)s,
        %(salary_min)s, %(salary_max)s, %(currency)s, %(description)s, %(url)s, %(portal_url)s,
        %(portal_type)s, %(posted_at)s, %(closing_date)s, %(applicant_count)s,
        %(fingerprint)s, %(raw)s)
ON CONFLICT (fingerprint) DO NOTHING
RETURNING id
"""


def upsert_icebox(
    conn: psycopg.Connection,
    user_id: str,
    survivors: list[NormalizedPosting],
    search_profile_id: str | None = None,
) -> UpsertCounts:
    counts = UpsertCounts()
    for p in survivors:
        fp = p.fingerprint()
        params: dict[str, Any] = {
            "external_id": p.external_id, "company": p.company, "title": p.title,
            "location": p.location, "remote_mode": p.remote_mode, "lat": p.lat, "lon": p.lon,
            "salary_min": p.salary_min, "salary_max": p.salary_max, "currency": p.currency,
            "description": p.description, "url": p.url, "portal_url": p.portal_url,
            "portal_type": p.portal_type, "posted_at": p.posted_at, "closing_date": p.closing_date,
            "applicant_count": p.applicant_count, "fingerprint": fp, "raw": Jsonb(p.raw),
        }
        row = conn.execute(_JOB_INSERT, params).fetchone()
        if row is not None:
            job_id = row[0]
            counts.jobs_inserted += 1
        else:
            existing = conn.execute(
                "SELECT id FROM job WHERE fingerprint = %s", (fp,)
            ).fetchone()
            assert existing is not None
            job_id = existing[0]
        app = conn.execute(
            """INSERT INTO application (user_id, job_id, search_profile_id, wip_status, status)
               VALUES (%s, %s, %s, 'icebox', 'sourced')
               ON CONFLICT (user_id, job_id) DO NOTHING RETURNING id""",
            (user_id, job_id, search_profile_id),
        ).fetchone()
        if app is not None:
            counts.applications_inserted += 1
        else:
            counts.deduped += 1
    return counts


def fetch_icebox(conn: psycopg.Connection, user_id: str) -> list[tuple[str, dict[str, Any], bool]]:
    rows = conn.execute(
        """SELECT a.id, j.title, j.location, j.remote_mode, j.posted_at,
                  j.applicant_count, j.closing_date, a.manual_override
           FROM application a JOIN job j ON j.id = a.job_id
           WHERE a.user_id = %s AND a.wip_status = 'icebox' AND a.status = 'sourced'""",
        (user_id,),
    ).fetchall()
    out: list[tuple[str, dict[str, Any], bool]] = []
    for r in rows:
        job = {
            "title": r[1], "location": r[2], "remote_mode": r[3],
            "posted_at": r[4], "applicant_count": r[5], "closing_date": r[6],
        }
        out.append((str(r[0]), job, bool(r[7])))
    return out


def _event(conn: psycopg.Connection, application_id: str, event_type: str) -> None:
    conn.execute(
        """INSERT INTO application_event (application_id, event_type, actor, payload)
           VALUES (%s, %s, 'human', '{}')""",
        (application_id, event_type),
    )


def promote(conn: psycopg.Connection, application_id: str) -> None:
    conn.execute(
        "UPDATE application SET manual_override = TRUE, updated_at = now() WHERE id = %s",
        (application_id,),
    )
    _event(conn, application_id, "promote")


def drop(conn: psycopg.Connection, application_id: str) -> None:
    conn.execute(
        "UPDATE application SET status = 'user_rejected', updated_at = now() WHERE id = %s",
        (application_id,),
    )
    _event(conn, application_id, "drop")


__all__ = [
    "UpsertCounts", "connect", "ensure_operator", "upsert_icebox",
    "fetch_icebox", "promote", "drop",
]
