"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-01

Creates the full AeroApply schema. This mirrors scripts/bootstrap.sql (the
human-readable reference) and is the authoritative apply path. Raw DDL via
op.execute so pgvector types, the v_icebox_ranked view, HNSW indexes, and CHECK
constraints are exact. LangGraph checkpoint tables are created separately by the
checkpointer's setup(), not here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE app_user (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,
    primary_email VARCHAR(255) NOT NULL,
    agent_email   VARCHAR(255),
    headline      VARCHAR(255),
    home_lat      DOUBLE PRECISION,
    home_lon      DOUBLE PRECISION,
    work_auth     VARCHAR(120),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE search_profile (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    locations       TEXT[] DEFAULT '{}',
    distance_miles  INTEGER DEFAULT 40,
    remote_modes    TEXT[] DEFAULT '{remote,hybrid}',
    languages       TEXT[] DEFAULT '{English}',
    salary_floor    INTEGER DEFAULT 115000,
    currency        VARCHAR(8) DEFAULT 'USD',
    include_linkedin BOOLEAN DEFAULT TRUE,
    exclude_companies TEXT[] DEFAULT '{}',
    weights         JSONB DEFAULT '{}',
    extra           JSONB DEFAULT '{}',
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE target_role (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    title         VARCHAR(255) NOT NULL,
    seniority     VARCHAR(80),
    alignment     NUMERIC(3,2) DEFAULT 1.0,
    keywords      TEXT[] DEFAULT '{}',
    priority      INTEGER DEFAULT 0,
    active        BOOLEAN DEFAULT TRUE
);

CREATE TABLE resume_variant (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    profile_name  VARCHAR(255) NOT NULL,
    role_focus    VARCHAR(255),
    raw_text      TEXT NOT NULL,
    structured_json JSONB,
    is_default    BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE resume_chunk (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id     UUID NOT NULL REFERENCES resume_variant(id) ON DELETE CASCADE,
    section_name  VARCHAR(100),
    chunk_text    TEXT NOT NULL,
    embedding     vector(1536),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE qa_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    answer_text   TEXT NOT NULL,
    field_type    VARCHAR(80),
    sensitive     BOOLEAN DEFAULT FALSE,
    confidence    NUMERIC(4,3) DEFAULT 1.0,
    embedding     vector(1536),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE source (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key           VARCHAR(80) NOT NULL UNIQUE,
    name          VARCHAR(255) NOT NULL,
    kind          VARCHAR(20) NOT NULL CHECK (kind IN ('api','browser')),
    autonomy_tier CHAR(1) NOT NULL DEFAULT 'B' CHECK (autonomy_tier IN ('A','B','C')),
    enabled       BOOLEAN DEFAULT TRUE,
    config        JSONB DEFAULT '{}',
    rate_limit    JSONB DEFAULT '{}'
);

CREATE TABLE job (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID REFERENCES source(id) ON DELETE SET NULL,
    external_id   VARCHAR(255),
    company       VARCHAR(255) NOT NULL,
    title         VARCHAR(255) NOT NULL,
    location      VARCHAR(255),
    remote_mode   VARCHAR(20) CHECK (remote_mode IN ('remote','hybrid','onsite')),
    lat           DOUBLE PRECISION,
    lon           DOUBLE PRECISION,
    salary_min    INTEGER,
    salary_max    INTEGER,
    currency      VARCHAR(8) DEFAULT 'USD',
    description   TEXT,
    requirements  JSONB DEFAULT '{}',
    url           TEXT,
    portal_url    TEXT,
    portal_type   VARCHAR(60),
    posted_at     TIMESTAMPTZ,
    closing_date  TIMESTAMPTZ,
    applicant_count INTEGER,
    fingerprint   VARCHAR(64) NOT NULL UNIQUE,
    raw           JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portal_credentials (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    company_domain     VARCHAR(255) NOT NULL,
    username           VARCHAR(255) NOT NULL,
    encrypted_password TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, company_domain)
);

CREATE TABLE application (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    job_id           UUID NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    search_profile_id UUID REFERENCES search_profile(id) ON DELETE SET NULL,
    resume_variant_id UUID REFERENCES resume_variant(id) ON DELETE SET NULL,
    credential_id    UUID REFERENCES portal_credentials(id) ON DELETE SET NULL,
    tailored_resume_json JSONB,
    tailored_resume_text TEXT,
    cover_letter     TEXT,
    answers          JSONB DEFAULT '{}',
    ats_score        NUMERIC(5,4),
    agent_confidence NUMERIC(5,4),
    match_score      NUMERIC(5,2),
    wip_status       VARCHAR(20) NOT NULL DEFAULT 'icebox'
                       CHECK (wip_status IN ('icebox','queued','active','parked','done')),
    status           VARCHAR(40) NOT NULL DEFAULT 'sourced'
                       CHECK (status IN (
                         'sourced','queued','drafting','needs_review','approved','submitting',
                         'submitted','questionnaire','interview','offer','accepted','rejected',
                         'user_rejected','closed_before_execution','withdrawn','error')),
    auto_submit      BOOLEAN DEFAULT FALSE,
    manual_override  BOOLEAN DEFAULT FALSE,
    needs_human      BOOLEAN DEFAULT FALSE,
    blockers         JSONB DEFAULT '{}',
    thread_id        VARCHAR(255),
    submitted_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, job_id)
);

CREATE TABLE application_event (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES application(id) ON DELETE CASCADE,
    event_type     VARCHAR(80) NOT NULL,
    actor          VARCHAR(20) NOT NULL CHECK (actor IN ('agent','human','system')),
    payload        JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE email_event (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matched_application_id UUID REFERENCES application(id) ON DELETE SET NULL,
    from_addr          VARCHAR(320),
    to_addr            VARCHAR(320),
    subject            TEXT,
    body               TEXT,
    classification     VARCHAR(40),
    otp                VARCHAR(12),
    forwarded          BOOLEAN DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_config (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_name   VARCHAR(120) NOT NULL UNIQUE,
    provider    VARCHAR(40) NOT NULL,
    model_id    VARCHAR(120) NOT NULL,
    params      JSONB DEFAULT '{}',
    fallback    JSONB DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE run (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id      VARCHAR(255) NOT NULL,
    application_id UUID REFERENCES application(id) ON DELETE CASCADE,
    status         VARCHAR(40),
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at       TIMESTAMPTZ,
    meta           JSONB DEFAULT '{}'
);

CREATE INDEX idx_application_status ON application(status);
CREATE INDEX idx_application_wip    ON application(wip_status);
CREATE INDEX idx_application_thread ON application(thread_id);
CREATE INDEX idx_job_company_title  ON job(company, title);
CREATE INDEX idx_job_posted         ON job(posted_at);
CREATE INDEX idx_portal_domain      ON portal_credentials(company_domain);
CREATE INDEX idx_event_application  ON application_event(application_id);
CREATE INDEX idx_resume_chunk_embed ON resume_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_qa_history_embed   ON qa_history   USING hnsw (embedding vector_cosine_ops);

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
          WHEN j.title ILIKE '%AI Product Manager%'
            OR j.title ILIKE '%AI Solutions Architect%' THEN 1.0
          WHEN j.title ILIKE '%Business Analyst%'
            OR j.title ILIKE '%Technical Project Manager%' THEN 0.6
          ELSE 0.3 END)
      + 0.25 * (CASE
          WHEN j.remote_mode = 'remote' THEN 1.0
          WHEN j.location ILIKE '%Jupiter%' OR j.location ILIKE '%West Palm%' THEN 0.8
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
ORDER BY execution_priority DESC;
"""

DROP_DDL = """
DROP VIEW IF EXISTS v_icebox_ranked;
DROP TABLE IF EXISTS run CASCADE;
DROP TABLE IF EXISTS model_config CASCADE;
DROP TABLE IF EXISTS email_event CASCADE;
DROP TABLE IF EXISTS application_event CASCADE;
DROP TABLE IF EXISTS application CASCADE;
DROP TABLE IF EXISTS portal_credentials CASCADE;
DROP TABLE IF EXISTS job CASCADE;
DROP TABLE IF EXISTS source CASCADE;
DROP TABLE IF EXISTS qa_history CASCADE;
DROP TABLE IF EXISTS resume_chunk CASCADE;
DROP TABLE IF EXISTS resume_variant CASCADE;
DROP TABLE IF EXISTS target_role CASCADE;
DROP TABLE IF EXISTS search_profile CASCADE;
DROP TABLE IF EXISTS app_user CASCADE;
"""


def _exec_each(ddl: str) -> None:
    for statement in ddl.split(";"):
        stmt = statement.strip()
        if stmt:
            op.execute(stmt)


def upgrade() -> None:
    _exec_each(SCHEMA_DDL)


def downgrade() -> None:
    _exec_each(DROP_DDL)
