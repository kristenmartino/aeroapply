# ADR-006: Streamlit internal UI for v1 (Next.js as documented future path)

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Architecture, Product
- **Related:** `docs/PROJECT_BRIEF.md` §4, §5, §11; ADR-002

## Context

AeroApply is a single-operator internal tool needing three views — **Inbox**
(HITL queue), **Ledger** (audit/applications), and **Kanban** (Icebox
promote/drop). The priority is shipping a working control surface fast over the
Postgres data model, not a polished public product. UI effort should not compete
with the agent engine for v1 attention.

## Decision

We will build the v1 UI in **Streamlit** as a dual-view internal app reading
directly from Postgres. A separate **FastAPI + Next.js** frontend is the
**documented future path**, not v1 scope. The email/webhook **service** is already
FastAPI (ADR-002); the *operator UI* stays Streamlit until product needs outgrow it.

## Alternatives considered

- **FastAPI + Next.js now** — better UX, real-time, and multi-user readiness, but
  a much larger build (API layer, auth, client app, deploy) for a single operator;
  diverts effort from the engine in v1.
- **No UI / CLI + SQL only** — cheapest, but HITL review, the Kanban promote/drop
  loop, and the Ledger need a visual surface to be usable.

## Consequences

- **Positive:** fastest path to a usable control surface; minimal code; trivial
  binding to the existing Postgres schema; one less service to design now.
- **Negative:** Streamlit's rerun model limits rich interactivity/real-time and
  doesn't suit multi-tenant or public use; some logic may need porting later.
- **Follow-ups:** when multi-user, mobile, or richer UX is required, build the
  Next.js frontend against a FastAPI API; keep business logic out of the UI layer
  to ease that migration.
