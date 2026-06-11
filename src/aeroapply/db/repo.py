"""Minimal synchronous DB access for read-only sourcing ingestion.

Scope: ensure the operator row, upsert survivors as `job` + icebox `application`,
read the Icebox for Python ranking, and apply operator Promote/Drop curation with
an audit event. **No submission / credential / apply code lives here.** The async
pool + full DAL is #14. Review telemetry (#80): `ranking_debug` is persisted via
`set_ranking_debug`, and Promote/Drop carry it on their `human` audit events; the
draft-review `human_*` events await the Inbox (EPIC-UI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from aeroapply.config import Profile
from aeroapply.connectors.base import NormalizedPosting

# --- Human-review event vocabulary (application_event.event_type, actor='human') -----
# Curation surfaces that exist today — Kanban Promote/Drop (#83):
EVENT_PROMOTE = "promote"
EVENT_DROP = "drop"
# Reserved for the draft-review Inbox (EPIC-UI/M3); the operator-review labels calibration
# needs (docs/CALIBRATION.md). Defined now so the vocabulary is standard once that surface lands:
EVENT_HUMAN_APPROVED_UNCHANGED = "human_approved_unchanged"
EVENT_HUMAN_EDITED = "human_edited"
EVENT_HUMAN_REJECTED = "human_rejected"

# The calibration label for a curation action, decoupled from the event_type verb.
_CURATION_LABELS = {EVENT_PROMOTE: "manual_override", EVENT_DROP: "hard_negative"}


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
    if new is None:
        raise RuntimeError("app_user INSERT ... RETURNING produced no row")
    return str(new[0])


_JOB_INSERT = """
INSERT INTO job (source_id, external_id, company, title, location, remote_mode, lat, lon,
                 salary_min, salary_max, currency, description, requirements, url, portal_url,
                 portal_type, posted_at, closing_date, applicant_count, fingerprint, raw)
VALUES (%(source_id)s, %(external_id)s, %(company)s, %(title)s, %(location)s, %(remote_mode)s,
        %(lat)s, %(lon)s, %(salary_min)s, %(salary_max)s, %(currency)s, %(description)s,
        %(requirements)s, %(url)s, %(portal_url)s, %(portal_type)s, %(posted_at)s,
        %(closing_date)s, %(applicant_count)s, %(fingerprint)s, %(raw)s)
ON CONFLICT (fingerprint) DO NOTHING
RETURNING id
"""


def upsert_icebox(
    conn: psycopg.Connection,
    user_id: str,
    survivors: list[NormalizedPosting],
    search_profile_id: str | None = None,
    source_id: str | None = None,
) -> UpsertCounts:
    """Persist already-bouncer-filtered survivors as job + icebox application rows.

    Callers MUST pass bouncer-filtered survivors (i.e. `plan_ingest(...).survivors`);
    this function does NOT filter. `source_id` is the optional FK to the `source`
    registry (NULL until that table is seeded — see #14 follow-up).
    """
    counts = UpsertCounts()
    for p in survivors:
        fp = p.fingerprint()
        params: dict[str, Any] = {
            "source_id": source_id,
            "external_id": p.external_id, "company": p.company, "title": p.title,
            "location": p.location, "remote_mode": p.remote_mode, "lat": p.lat, "lon": p.lon,
            "salary_min": p.salary_min, "salary_max": p.salary_max, "currency": p.currency,
            "description": p.description, "requirements": Jsonb(p.requirements),
            "url": p.url, "portal_url": p.portal_url, "portal_type": p.portal_type,
            "posted_at": p.posted_at, "closing_date": p.closing_date,
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
            if existing is None:
                raise RuntimeError(
                    f"job fingerprint {fp!r} vanished between insert-conflict and select"
                )
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
                  j.applicant_count, j.closing_date, a.manual_override, j.company, j.url
           FROM application a JOIN job j ON j.id = a.job_id
           WHERE a.user_id = %s AND a.wip_status = 'icebox' AND a.status = 'sourced'""",
        (user_id,),
    ).fetchall()
    out: list[tuple[str, dict[str, Any], bool]] = []
    for r in rows:
        # `company`/`url` are display-only (the UI Kanban shows them); ranking ignores them.
        job = {
            "title": r[1], "location": r[2], "remote_mode": r[3],
            "posted_at": r[4], "applicant_count": r[5], "closing_date": r[6],
            "company": r[8], "url": r[9],
        }
        out.append((str(r[0]), job, bool(r[7])))
    return out


def _event(
    conn: psycopg.Connection,
    application_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    actor: str = "human",
) -> None:
    conn.execute(
        """INSERT INTO application_event (application_id, event_type, actor, payload)
           VALUES (%s, %s, %s, %s)""",
        (application_id, event_type, actor, Jsonb(payload if payload is not None else {})),
    )


def _curation_payload(event_type: str, ranking_debug: dict[str, Any] | None) -> dict[str, Any]:
    """Audit payload for a human curation action: the calibration label + the ranking
    snapshot (ranker features) visible when the operator acted (#80).

    `ranking_debug` is only populated if a snapshot was taken first (``rank --persist`` /
    ``scheduler.snapshot_ranking_debug``); a bare Kanban Promote/Drop has none. The
    ``ranking_debug_present`` flag makes that explicit so calibration can tell a fully
    paired (features, label) record from a label with no features.
    """
    return {
        "action": event_type,
        "label": _CURATION_LABELS.get(event_type),
        "ranking_debug": ranking_debug,
        "ranking_debug_present": ranking_debug is not None,
    }


def promote(conn: psycopg.Connection, application_id: str) -> None:
    row = conn.execute(
        """UPDATE application SET manual_override = TRUE, updated_at = now()
           WHERE id = %s RETURNING ranking_debug""",
        (application_id,),
    ).fetchone()
    ranking_debug = row[0] if row else None
    _event(conn, application_id, EVENT_PROMOTE, _curation_payload(EVENT_PROMOTE, ranking_debug))


def drop(conn: psycopg.Connection, application_id: str) -> None:
    # user_rejected is terminal: also retire the scheduler state out of the Icebox.
    row = conn.execute(
        """UPDATE application SET status = 'user_rejected', wip_status = 'done', updated_at = now()
           WHERE id = %s RETURNING ranking_debug""",
        (application_id,),
    ).fetchone()
    ranking_debug = row[0] if row else None
    _event(conn, application_id, EVENT_DROP, _curation_payload(EVENT_DROP, ranking_debug))


def set_ranking_debug(
    conn: psycopg.Connection, application_id: str, payload: dict[str, Any]
) -> None:
    """Persist the ranking snapshot (components + execution_priority + weights) for one app."""
    conn.execute(
        "UPDATE application SET ranking_debug = %s, updated_at = now() WHERE id = %s",
        (Jsonb(payload), application_id),
    )


# --- M2: WIP queue + execution-graph persistence (EPIC-GRAPH) -------------------
EVENT_QUEUED = "queued"                # scheduler promoted Icebox -> queued (actor=system)
EVENT_CLOSED = "closed_before_execution"  # verify_open found the posting gone (actor=agent)
EVENT_TAILORED = "tailored"            # tailoring loop produced a draft + ats_score (actor=agent)
EVENT_GRAPH_ERROR = "graph_error"      # unrecoverable failure inside the graph (actor=agent)


def count_in_flight(conn: psycopg.Connection, user_id: str) -> int:
    """Applications currently consuming WIP capacity (queued or actively worked)."""
    row = conn.execute(
        """SELECT count(*) FROM application
           WHERE user_id = %s AND wip_status IN ('queued', 'active')""",
        (user_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def promote_to_queue(conn: psycopg.Connection, application_ids: list[str]) -> int:
    """Move ranked Icebox winners into the WIP queue; thread_id = application id.

    Only flips rows still in ('icebox','sourced') so a concurrent Drop/Promote can't be
    clobbered (the Kanban write-back race in the brief's M3 risks). Writes one
    actor='system' audit event per promoted row. Returns how many actually moved.
    """
    promoted = 0
    for app_id in application_ids:
        row = conn.execute(
            """UPDATE application
               SET wip_status = 'queued', status = 'queued',
                   thread_id = id::text, updated_at = now()
               WHERE id = %s AND wip_status = 'icebox' AND status = 'sourced'
               RETURNING id""",
            (app_id,),
        ).fetchone()
        if row is not None:
            _event(conn, app_id, EVENT_QUEUED, {"thread_id": str(app_id)}, actor="system")
            promoted += 1
    return promoted


def fetch_next_queued(conn: psycopg.Connection, user_id: str) -> dict[str, Any] | None:
    """The oldest queued application + the job fields the execution graph needs."""
    row = conn.execute(
        """SELECT a.id, j.title, j.company, j.description, j.location, j.remote_mode,
                  j.portal_url, j.portal_type
           FROM application a JOIN job j ON j.id = a.job_id
           WHERE a.user_id = %s AND a.wip_status = 'queued'
           ORDER BY a.updated_at ASC LIMIT 1""",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "application_id": str(row[0]), "job_title": row[1] or "", "company": row[2] or "",
        "job_description": row[3] or "", "job_location": row[4], "remote_mode": row[5],
        "portal_url": row[6], "portal_type": row[7],
    }


def fetch_resume_variants(conn: psycopg.Connection, user_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT id, profile_name, role_focus, raw_text, is_default
           FROM resume_variant WHERE user_id = %s ORDER BY created_at""",
        (user_id,),
    ).fetchall()
    return [
        {"id": str(r[0]), "profile_name": r[1], "role_focus": r[2],
         "raw_text": r[3], "is_default": bool(r[4])}
        for r in rows
    ]


def mark_closed_before_execution(conn: psycopg.Connection, application_id: str,
                                 detail: dict[str, Any] | None = None) -> None:
    """verify_open found the posting gone: terminal status, WIP slot freed."""
    conn.execute(
        """UPDATE application SET status = 'closed_before_execution', wip_status = 'done',
                                  updated_at = now() WHERE id = %s""",
        (application_id,),
    )
    _event(conn, application_id, EVENT_CLOSED, detail or {}, actor="agent")


def save_tailoring_result(
    conn: psycopg.Connection,
    application_id: str,
    *,
    resume_variant_id: str | None,
    tailored_resume_text: str,
    ats_score: float,
    iterations: int,
) -> None:
    """Persist the tailoring loop's output; app stays in-flight at status='drafting'."""
    conn.execute(
        """UPDATE application
           SET resume_variant_id = %s, tailored_resume_text = %s, ats_score = %s,
               status = 'drafting', wip_status = 'active', updated_at = now()
           WHERE id = %s""",
        (resume_variant_id, tailored_resume_text, ats_score, application_id),
    )
    _event(conn, application_id, EVENT_TAILORED,
           {"ats_score": ats_score, "iterations": iterations}, actor="agent")


def mark_graph_error(conn: psycopg.Connection, application_id: str, error: str) -> None:
    """Unrecoverable graph failure: status='error', parked so it surfaces in the Inbox."""
    conn.execute(
        """UPDATE application SET status = 'error', wip_status = 'parked', updated_at = now()
           WHERE id = %s""",
        (application_id,),
    )
    _event(conn, application_id, EVENT_GRAPH_ERROR, {"error": error}, actor="agent")


# --- M2: resume embeddings + pgvector retrieval (#34) ----------------------------
def _register_vector(conn: psycopg.Connection) -> None:
    """Enable the pgvector type adapter on this connection (idempotent per call)."""
    from pgvector.psycopg import register_vector

    register_vector(conn)


def index_resume_chunks(
    conn: psycopg.Connection,
    resume_id: str,
    chunks: list[tuple[str | None, str]],
    embeddings: list[list[float]],
) -> int:
    """Replace a resume's `resume_chunk` rows with freshly-embedded chunks (re-index safe).

    Deletes any existing chunks for the resume first, so re-running is idempotent rather
    than duplicating. `chunks` and `embeddings` are zipped positionally. Caller commits.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) misaligned")
    from pgvector import Vector

    _register_vector(conn)
    conn.execute("DELETE FROM resume_chunk WHERE resume_id = %s", (resume_id,))
    for (section, text), emb in zip(chunks, embeddings, strict=True):
        conn.execute(
            """INSERT INTO resume_chunk (resume_id, section_name, chunk_text, embedding)
               VALUES (%s, %s, %s, %s)""",
            (resume_id, section, text, Vector(emb)),
        )
    return len(chunks)


def retrieve_resume_chunks(
    conn: psycopg.Connection,
    resume_id: str,
    query_embedding: list[float],
    k: int = 5,
) -> list[tuple[str, float]]:
    """Top-k `(chunk_text, cosine_distance)` for a resume, nearest first (pgvector `<=>`)."""
    from pgvector import Vector

    _register_vector(conn)
    rows = conn.execute(
        """SELECT chunk_text, embedding <=> %s AS distance
           FROM resume_chunk WHERE resume_id = %s
           ORDER BY distance ASC LIMIT %s""",
        (Vector(query_embedding), resume_id, k),
    ).fetchall()
    return [(r[0], float(r[1])) for r in rows]


__all__ = [
    "UpsertCounts", "connect", "ensure_operator", "upsert_icebox",
    "fetch_icebox", "promote", "drop", "set_ranking_debug",
    "EVENT_PROMOTE", "EVENT_DROP", "EVENT_HUMAN_APPROVED_UNCHANGED",
    "EVENT_HUMAN_EDITED", "EVENT_HUMAN_REJECTED",
    "EVENT_QUEUED", "EVENT_CLOSED", "EVENT_TAILORED", "EVENT_GRAPH_ERROR",
    "count_in_flight", "promote_to_queue", "fetch_next_queued",
    "fetch_resume_variants", "mark_closed_before_execution",
    "save_tailoring_result", "mark_graph_error",
    "index_resume_chunks", "retrieve_resume_chunks",
]
