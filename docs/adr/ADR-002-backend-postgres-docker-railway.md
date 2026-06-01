# ADR-002: Postgres on local Docker (dev) → Railway (prod)

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Architecture
- **Related:** `docs/PROJECT_BRIEF.md` §4, §5, §8; ADR-001, ADR-003

## Context

The backend must serve a LangGraph Postgres checkpointer that writes on **every
node transition** (chatty, latency-sensitive), host pgvector (ADR-003), and
receive **inbound email webhooks 24/7** to wake paused threads. Checkpoint write
latency directly gates graph throughput, so compute and database should be
co-located. We also want a zero-cost, instant dev loop.

## Decision

For **dev**, run **Postgres + pgvector in Docker** (`infra/docker-compose.yml`) —
local, free, sub-millisecond checkpoint writes. For **prod**, deploy on
**Railway** with the FastAPI engine and Postgres **co-located** in one project:
low checkpoint latency and a stable always-on HTTPS endpoint for inbound webhooks.
Alembic owns migrations; `scripts/bootstrap.sql` is the canonical schema.

## Alternatives considered

- **Supabase** — great DX, but compute is separate from our engine; per-transition
  checkpointer writes pay network round-trips, and pooler/PgBouncer modes
  complicate the persistent psycopg3 connections LangGraph wants.
- **Neon** — serverless/autoscaling and cold starts fight an always-on daemon with
  a hot connection pool and constant checkpoint traffic; latency is non-co-located.
- Both push us toward a separate webhook host anyway; Railway co-locates engine,
  DB, and webhook endpoint in one place.

## Consequences

- **Positive:** minimal checkpoint latency; one platform for engine + DB + webhooks;
  identical Postgres locally and in prod; no managed-DB lock-in.
- **Negative:** we self-manage backups/upgrades/monitoring on Railway (no Supabase
  dashboard/auth niceties).
- **Follow-ups:** revisit a managed Postgres if ops burden grows or we need
  multi-region; keep the connection layer portable.
