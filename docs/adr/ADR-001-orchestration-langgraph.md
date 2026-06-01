# ADR-001: Orchestrate with LangGraph (supervisor + cyclic subgraphs)

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Architecture
- **Related:** `docs/PROJECT_BRIEF.md` §4, §5, §6, §9; ADR-002

## Context

AeroApply is a persistent daemon whose execution graph must: pause mid-flow for
human review or an inbound email OTP and resume hours later (durable HITL/AITL);
run a cyclic Generator ⇄ ATS-Critic loop until a score threshold or iteration
cap; route each application through a runtime conditional submission gate; and
let every node pick its own model. This demands stateful, durable,
interruptible, cyclic orchestration — not a linear pipeline.

## Decision

We will use **LangGraph** with a supervisor/scheduler graph that pulls WIP-limited
work and dispatches into a nested **execution subgraph**. Cyclic subgraphs express
the critic loops; a Postgres **durable checkpointer** (`langgraph-checkpoint-postgres`)
persists every `thread_id` so paused threads survive restarts and resume via
`aupdate_state`. Per-node model selection reads `model_config[node]`.

## Alternatives considered

- **CrewAI** — role/agent abstraction is ergonomic but weaker at durable
  checkpointing, arbitrary cyclic control flow, and fine-grained interrupt/resume
  at a specific node; HITL-by-checkpoint is not first-class.
- **Raw / swarm (hand-rolled agent loop)** — maximal control, but we would
  re-implement checkpointing, resumable interrupts, and state reduction — the
  exact value LangGraph provides — at high cost and risk.

## Consequences

- **Positive:** native freeze/resume, cyclic loops, conditional submission edge,
  and per-node model control; HITL and OTP-injection fall out of the checkpointer.
- **Negative:** LangGraph's state/reducer model has a learning curve; ties us to
  its release cadence and its checkpoint table layout.
- **Follow-ups:** checkpointer chattiness makes a co-located Postgres important
  (ADR-002); revisit if graph complexity outgrows the supervisor pattern.
