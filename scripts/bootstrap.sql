-- AeroApply — canonical database schema (human-readable reference).
-- APPLY IT with `uv run alembic upgrade head` — migration 0001 mirrors this file and
-- is the authoritative apply path. You *can* psql this into a throwaway DB, but real
-- setup goes through Alembic so there is a single source of truth.
-- Dev DB: local Docker Postgres (see infra/docker-compose.yml).
-- LangGraph checkpoint tables (checkpoints, checkpoint_blobs, checkpoint_writes)
-- are created automatically by `await checkpointer.setup()` — do NOT hand-write them.
--
-- Embedding dimension defaults to 1536 (OpenAI text-embedding-3-small).
-- If you swap to a local embedder, change vector(1536) to match and re-index.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================================
-- 1. OPERATOR & PROFILE
-- =====================================================================
CREATE TABLE app_user (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,
    primary_email VARCHAR(255) NOT NULL,            -- where high-priority items are forwarded
    agent_email   VARCHAR(255),                     -- dedicated <name>.agents@domain address
    headline      VARCHAR(255),
    home_lat      DOUBLE PRECISION,                 -- commute anchor (Jupiter, FL)
    home_lon      DOUBLE PRECISION,
    work_auth     VARCHAR(120),                     -- drives the clearance/visa bouncer gate
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The "filters": locations, distance, remote modes, language, salary, LinkedIn on/off, etc.
CREATE TABLE search_profile (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    locations       TEXT[] DEFAULT '{}',            -- e.g. {'Remote','Jupiter, FL','West Palm Beach, FL'}
    distance_miles  INTEGER DEFAULT 40,
    remote_modes    TEXT[] DEFAULT '{remote,hybrid}', -- subset of remote|hybrid|onsite
    languages       TEXT[] DEFAULT '{English}',
    salary_floor    INTEGER DEFAULT 115000,         -- evaluated against the MAX of a band
    currency        VARCHAR(8) DEFAULT 'USD',
    include_linkedin BOOLEAN DEFAULT TRUE,          -- "on linkedin / not on linkedin"
    exclude_companies TEXT[] DEFAULT '{}',
    weights         JSONB DEFAULT '{}',             -- execution_priority weight overrides
    extra           JSONB DEFAULT '{}',
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Target role names + alignment multiplier used by the ranking formula.
CREATE TABLE target_role (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    title         VARCHAR(255) NOT NULL,            -- e.g. 'AI Product Manager'
    seniority     VARCHAR(80),
    alignment     NUMERIC(3,2) DEFAULT 1.0,         -- 1.0 core, 0.6 adjacent
    keywords      TEXT[] DEFAULT '{}',
    priority      INTEGER DEFAULT 0,
    active        BOOLEAN DEFAULT TRUE
);

-- =====================================================================
-- 2. KNOWLEDGE BASE (resumes + Q&A memory, for AITL retrieval)
-- =====================================================================
CREATE TABLE resume_variant (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    profile_name  VARCHAR(255) NOT NULL,            -- 'AI Product Manager - base', 'Senior BA - base'
    role_focus    VARCHAR(255),
    raw_text      TEXT NOT NULL,
    structured_json JSONB,                          -- parsed sections for targeted edits
    is_default    BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE resume_chunk (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id     UUID NOT NULL REFERENCES resume_variant(id) ON DELETE CASCADE,
    section_name  VARCHAR(100),                     -- Experience | Skills | Education | Summary
    chunk_text    TEXT NOT NULL,
    embedding     vector(1536),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Historical answers to application questions; AITL searches here before asking the human.
CREATE TABLE qa_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    answer_text   TEXT NOT NULL,
    field_type    VARCHAR(80),                      -- free_text | boolean | eeo | visa | clearance | ...
    sensitive     BOOLEAN DEFAULT FALSE,            -- eeo/visa/clearance => always HITL, never fabricate
    confidence    NUMERIC(4,3) DEFAULT 1.0,
    embedding     vector(1536),                     -- embeds the QUESTION for similarity match
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 3. SOURCES, JOBS (Icebox), CREDENTIALS
-- =====================================================================
CREATE TABLE source (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key           VARCHAR(80) NOT NULL UNIQUE,      -- 'greenhouse' | 'lever' | 'workday' | 'linkedin' ...
    name          VARCHAR(255) NOT NULL,
    kind          VARCHAR(20) NOT NULL CHECK (kind IN ('api','browser')),
    autonomy_tier CHAR(1) NOT NULL DEFAULT 'B' CHECK (autonomy_tier IN ('A','B','C')),
    enabled       BOOLEAN DEFAULT TRUE,
    config        JSONB DEFAULT '{}',
    rate_limit    JSONB DEFAULT '{}'                -- pacing / anti-ban hygiene
);

-- Raw scraped postings that survived the SourcingBouncer.
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
    salary_max    INTEGER,                          -- bouncer evaluates this vs the floor
    currency      VARCHAR(8) DEFAULT 'USD',
    description   TEXT,
    requirements  JSONB DEFAULT '{}',
    url           TEXT,
    portal_url    TEXT,                             -- where the application is actually filed
    portal_type   VARCHAR(60),                      -- greenhouse | lever | workday | taleo | custom
    posted_at     TIMESTAMPTZ,
    closing_date  TIMESTAMPTZ,
    applicant_count INTEGER,
    fingerprint   VARCHAR(64) NOT NULL UNIQUE,      -- dedupe key (hash of company+title+location)
    raw           JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Persistent, encrypted portal logins (one per company domain).
CREATE TABLE portal_credentials (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    company_domain     VARCHAR(255) NOT NULL,        -- 'company.wd5.myworkdayjobs.com'
    username           VARCHAR(255) NOT NULL,
    encrypted_password TEXT NOT NULL,                -- Fernet ciphertext; key from env/KMS
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, company_domain)
);

-- =====================================================================
-- 4. APPLICATIONS (the pipeline record) + AUDIT + EMAIL
-- =====================================================================
CREATE TABLE application (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    job_id           UUID NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    search_profile_id UUID REFERENCES search_profile(id) ON DELETE SET NULL,
    resume_variant_id UUID REFERENCES resume_variant(id) ON DELETE SET NULL,
    credential_id    UUID REFERENCES portal_credentials(id) ON DELETE SET NULL,

    -- AI artifacts
    tailored_resume_json JSONB,
    tailored_resume_text TEXT,
    cover_letter     TEXT,
    answers          JSONB DEFAULT '{}',            -- {question: {answer, source, confidence}}

    -- Scores
    ats_score        NUMERIC(5,4),                  -- ATS-Critic keyword coverage, 0-1 scale (project-wide)
    agent_confidence NUMERIC(5,4),                  -- 0-1; gates auto-submit
    match_score      NUMERIC(5,2),

    -- Routing / state
    wip_status       VARCHAR(20) NOT NULL DEFAULT 'icebox'
                       CHECK (wip_status IN ('icebox','queued','active','parked','done')),
    status           VARCHAR(40) NOT NULL DEFAULT 'sourced'
                       CHECK (status IN (
                         'sourced','queued','drafting','needs_review','approved','submitting',
                         'submitted','questionnaire','interview','offer','accepted','rejected',
                         'user_rejected','closed_before_execution','withdrawn','error')),
    auto_submit      BOOLEAN DEFAULT FALSE,         -- operator opt-in for this app/source
    manual_override  BOOLEAN DEFAULT FALSE,         -- "Promote" → absolute top priority
    needs_human      BOOLEAN DEFAULT FALSE,
    blockers         JSONB DEFAULT '{}',            -- why it's paused (novel question, low conf, ...)

    -- LangGraph linkage
    thread_id        VARCHAR(255),                  -- = application id, used as checkpoint thread
    submitted_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, job_id)
);

-- Append-only audit log of every action (agent / human / system).
CREATE TABLE application_event (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES application(id) ON DELETE CASCADE,
    event_type     VARCHAR(80) NOT NULL,
    actor          VARCHAR(20) NOT NULL CHECK (actor IN ('agent','human','system')),
    payload        JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Inbound email events (OTP + lifecycle), for traceability.
CREATE TABLE email_event (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matched_application_id UUID REFERENCES application(id) ON DELETE SET NULL,
    from_addr          VARCHAR(320),
    to_addr            VARCHAR(320),
    subject            TEXT,
    body               TEXT,
    classification     VARCHAR(40),                 -- otp | interview | questionnaire | rejection | offer | none
    otp                VARCHAR(12),
    forwarded          BOOLEAN DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 5. MODEL ROUTER CONFIG + LANGGRAPH RUN MAPPING
-- =====================================================================
CREATE TABLE model_config (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_name   VARCHAR(120) NOT NULL UNIQUE,       -- 'tailor.generator', 'tailor.critic', 'sourcing.parser'
    provider    VARCHAR(40) NOT NULL,               -- anthropic | deepseek | openai | ollama
    model_id    VARCHAR(120) NOT NULL,              -- claude-opus-4-8 | claude-sonnet-4-6 | ...
    params      JSONB DEFAULT '{}',                 -- {temperature, max_tokens, context, fast_mode, ...}
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

-- =====================================================================
-- 6. INDEXES
-- =====================================================================
CREATE INDEX idx_application_status      ON application(status);
CREATE INDEX idx_application_wip         ON application(wip_status);
CREATE INDEX idx_application_thread      ON application(thread_id);
CREATE INDEX idx_job_company_title       ON job(company, title);
CREATE INDEX idx_job_posted             ON job(posted_at);
CREATE INDEX idx_portal_domain           ON portal_credentials(company_domain);
CREATE INDEX idx_event_application       ON application_event(application_id);

-- Vector similarity (HNSW, cosine) for AITL retrieval.
CREATE INDEX idx_resume_chunk_embed ON resume_chunk USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_qa_history_embed   ON qa_history   USING hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- 7. RANKING VIEW  (DEBUG / FALLBACK ONLY — frozen weights)
--    Canonical ranking is Python: src/aeroapply/sourcing/ranking.py reads
--    profile.ranking_weights so weights are tunable live (no migration).
--    This view hard-codes the same formula for ad-hoc SQL / debugging.
-- =====================================================================
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
      -- Manual promote = absolute trump
      (CASE WHEN a.manual_override THEN 100.0 ELSE 0.0 END)
      -- Title alignment (35%)
      + 0.35 * (CASE
          WHEN j.title ILIKE '%AI Product Manager%'
            OR j.title ILIKE '%AI Solutions Architect%' THEN 1.0
          WHEN j.title ILIKE '%Business Analyst%'
            OR j.title ILIKE '%Technical Project Manager%' THEN 0.6
          ELSE 0.3 END)
      -- Location & flexibility (25%)
      + 0.25 * (CASE
          WHEN j.remote_mode = 'remote' THEN 1.0
          WHEN j.location ILIKE '%Jupiter%' OR j.location ILIKE '%West Palm%' THEN 0.8
          ELSE 0.0 END)
      -- Recency (20%)
      + 0.20 * (CASE
          WHEN j.posted_at >= now() - INTERVAL '2 days' THEN 1.0
          WHEN j.posted_at >= now() - INTERVAL '7 days' THEN 0.5
          ELSE 0.1 END)
      -- Competition / applicants (10%)
      + 0.10 * (CASE
          WHEN j.applicant_count < 50  THEN 1.0
          WHEN j.applicant_count < 150 THEN 0.5
          ELSE 0.0 END)
      -- Urgency / closing soon (10%)
      + 0.10 * (CASE
          WHEN j.closing_date IS NOT NULL AND j.closing_date <= now() + INTERVAL '3 days' THEN 1.0
          ELSE 0.0 END)
    ) AS execution_priority
FROM application a
JOIN job j ON j.id = a.job_id
WHERE a.wip_status = 'icebox'
  AND a.status = 'sourced'
ORDER BY execution_priority DESC;
