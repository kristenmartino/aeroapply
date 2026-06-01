# ADR-003: pgvector in the same Postgres (not a separate vector DB)

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Architecture
- **Related:** `docs/PROJECT_BRIEF.md` §4, §11, §12; ADR-002

## Context

AeroApply needs semantic retrieval over `resume_chunk` and `qa_history`
embeddings (1536-d by default) to tailor resumes and answer screening questions
from history. The corpus is single-operator scale — thousands, not billions, of
vectors. We already run Postgres (ADR-002) for relational data and the LangGraph
checkpointer.

## Decision

We will store and query embeddings with **pgvector in the same Postgres instance**,
using **HNSW** indexes. Vectors live beside the rows they describe; retrieval is a
SQL query joined to relational filters. The embedding dimension must match the
schema column; swapping embedders requires a migration.

## Alternatives considered

- **Pinecone** — a strong managed ANN service, but adds a second backend to
  provision, secure, sync, and pay for; couples a network hop into every retrieval;
  and forces dual-write consistency between Postgres rows and remote vectors. Its
  scale advantages are irrelevant at our corpus size.
- **Redis / separate vector service** — same "second system" objection; more ops,
  no benefit at this scale.

## Consequences

- **Positive:** one backend, one connection pool, one backup; transactional
  consistency between rows and their vectors; metadata filters and vector search in
  one SQL statement; zero extra cost.
- **Negative:** at very large scale pgvector trails dedicated ANN engines on recall
  vs. latency; HNSW build/memory tuning is on us.
- **Follow-ups:** if vector volume or QPS outgrows pgvector, introduce a dedicated
  store behind the same retrieval interface — not before it is proven necessary.
