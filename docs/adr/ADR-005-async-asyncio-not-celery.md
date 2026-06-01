# ADR-005: Async task workers with asyncio (defer Celery)

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Architecture
- **Related:** `docs/PROJECT_BRIEF.md` §4, §5, §8, §12; ADR-001, ADR-002

## Context

AeroApply's work is overwhelmingly **I/O-bound**: LLM calls, HTTP to job
connectors, Playwright sessions, psycopg3 queries, IMAP/SMTP. The stack is already
async end-to-end (LangGraph async, `AsyncConnectionPool`, httpx, `aiosmtplib`). We
need concurrent execution of the WIP-limited graph, the sourcing daemon, the
hourly IMAP poller, and webhook handlers — without standing up heavy
infrastructure for a single-operator tool.

## Decision

We will run background work as **`asyncio` tasks** inside the engine process:
the supervisor schedules graph runs, the email poller runs on an async interval,
and FastAPI `BackgroundTasks` handle fire-and-forget sends. No broker, no separate
worker fleet. Concurrency is bounded by WIP limits and connection-pool sizing.

## Alternatives considered

- **Celery (+ Redis/RabbitMQ broker)** — mature distributed task queue, but adds a
  broker, worker processes, result backend, and serialization boundaries — premature
  for one operator, and its sync-worker model fights our async stack.
- **APScheduler / cron only** — handles periodic jobs but not the concurrent,
  resumable graph execution LangGraph already coordinates.

## Consequences

- **Positive:** one process to run and deploy; no broker to operate; natural fit
  with the async stack and the LangGraph checkpointer; lowest cost/complexity.
- **Negative:** no cross-host horizontal scale-out or broker-backed retry/visibility;
  durability of *in-flight* work rests on the checkpointer, not a queue.
- **Follow-ups (triggers to adopt Celery):** need for multi-host workers, durable
  retry/backoff queues, or isolating CPU-heavy tasks. Until then, asyncio stands.
