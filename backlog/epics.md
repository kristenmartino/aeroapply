# AeroApply — Delivery Backlog: Epics

> Derived from `docs/PROJECT_BRIEF.md` (source of truth) and `scripts/bootstrap.sql`.
> Canonical 6 x 2-week sprint plan; Sprint 1 begins the week of 2026-06-08.
> Machine-readable backlog: `backlog/issues.json`. Issue detail: `backlog/issues.md`.

**9 epics · 67 issues** across 6 sprints.

| Key | Epic | Issues |
|---|---|---|
| `EPIC-FND` | Foundations: Repo, Infra, Config & Model Router | 10 |
| `EPIC-SRC` | Sourcing Daemon, SourcingBouncer & Connectors | 11 |
| `EPIC-ICE` | Icebox, Ranking View & WIP Scheduler | 3 |
| `EPIC-GRAPH` | LangGraph Supervisor & Execution Graph Core | 4 |
| `EPIC-TAILOR` | Tailoring Loop, Cover Letters & Embeddings | 6 |
| `EPIC-AITL` | AITL Question Answering, Routing & HITL Gate | 7 |
| `EPIC-APPLY` | Apply Connectors, Credential Vault & Submission | 7 |
| `EPIC-EMAIL` | Email-Event Service: Webhook OTP Injection & IMAP Lifecycle | 7 |
| `EPIC-UI` | Streamlit UI, Security/Compliance & Production Hardening | 12 |

## Sprint cadence

| Sprint | Dates | Theme | Issues |
|---|---|---|---|
| 1 | 06/08–06/19 | Foundations + Sourcing & Icebox | 21 |
| 2 | 06/22–07/03 | Execution graph core + Tailoring loop | 10 |
| 3 | 07/06–07/17 | Cover letter + AITL + HITL gate + Streamlit | 13 |
| 4 | 07/20–07/31 | Apply connectors + credentials | 8 |
| 5 | 08/03–08/14 | Email-event service | 7 |
| 6 | 08/17–08/28 | Hardening + deploy | 8 |

---

## EPIC-FND — Foundations: Repo, Infra, Config & Model Router

**Goal.** Stand up the AeroApply project skeleton: private repo, CI with a cross-model review gate, Docker Postgres+pgvector, the canonical schema applied via Alembic, the Pydantic config/profile loader, and the model-router skeleton that every node reads from. This is the substrate every other epic builds on.

**Spans sprints:** 1, 6 · **Issues:** 10

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| Apply bootstrap.sql as the initial Alembic migration | 1 | M | P0 |
| Async Postgres connection pool + DB access layer | 1 | M | P0 |
| CI pipeline: lint, type-check, tests on every PR | 1 | M | P0 |
| Cross-model build-time review gate in CI | 1 | M | P1 |
| Docker Compose dev stack: Postgres 16 + pgvector | 1 | S | P0 |
| Model-router skeleton with provider abstraction and per-node overrides | 1 | L | P0 |
| Pydantic config loader for profile.yaml + .env (PII boundary) | 1 | M | P0 |
| Scaffold aeroapply repo, packaging (uv/3.12), and tooling baseline | 1 | M | P0 |
| Seed data + fixtures: operator, profile, resumes, qa_history, sources | 1 | M | P1 |
| Documentation suite: align docs with brief, schema, and backlog | 6 | M | P2 |

## EPIC-SRC — Sourcing Daemon, SourcingBouncer & Connectors

**Goal.** Build the 24/7 sourcing subsystem: API connectors (Greenhouse, Lever, Ashby) plus DOM-portal stubs, the SourcingBouncer edge filters that drop junk before any DB write, dedupe/fingerprinting, and Icebox writes that create application rows in wip_status='icebox'. Exit: ranked jobs flow into the Icebox.

**Spans sprints:** 1, 4 · **Issues:** 11

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| Always-on sourcing daemon loop with per-source pacing | 1 | L | P1 |
| Ashby API connector (Tier A) | 1 | M | P0 |
| DOM-portal connector stubs (Workday, LinkedIn) with tier metadata | 1 | S | P2 |
| Dedupe fingerprinting for jobs | 1 | M | P0 |
| End-to-end integration test: sourced -> ranked -> queued | 1 | M | P0 |
| Greenhouse API connector (Tier A) | 1 | M | P0 |
| Icebox writes: persist survivors as jobs + icebox applications | 1 | M | P0 |
| Lever API connector (Tier A) | 1 | M | P0 |
| Source connector interface + registry seeded from source table | 1 | M | P0 |
| SourcingBouncer edge filters (drop before DB write) | 1 | L | P0 |
| Connector ToS/anti-ban policy doc + LinkedIn Tier B/C posture | 4 | S | P2 |

## EPIC-ICE — Icebox, Ranking View & WIP Scheduler

**Goal.** Implement the two-tier backlog: the v_icebox_ranked execution-priority view, the WIP-limited Supervisor/Scheduler that promotes the top-N icebox rows to queued on a schedule, and the stale-queue guard. This is the bridge between cheap sourcing and expensive execution.

**Spans sprints:** 1, 2 · **Issues:** 3

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| Validate and harden v_icebox_ranked execution-priority view | 1 | M | P0 |
| WIP-limited Supervisor/Scheduler promotes top-N icebox to queued | 1 | M | P0 |
| Scheduler trigger: cadence runner for promotion cycles | 2 | S | P2 |

## EPIC-GRAPH — LangGraph Supervisor & Execution Graph Core

**Goal.** Build the durable LangGraph execution graph with the Postgres checkpointer: shared state schema, supervisor wiring, the verify_open stale-job guard, select_resume variant selection, and the run/thread linkage. Provides the spine that tailoring, answering, routing, and submission hang off of.

**Spans sprints:** 2 · **Issues:** 4

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| LangGraph state schema + Postgres checkpointer setup | 2 | L | P0 |
| Supervisor graph wiring + run/thread linkage | 2 | L | P0 |
| select_resume node: choose best resume variant | 2 | M | P1 |
| verify_open node: stale-job HTTP guard | 2 | M | P0 |

## EPIC-TAILOR — Tailoring Loop, Cover Letters & Embeddings

**Goal.** Implement the runtime peer-review system: the Generator<->ATS-Critic cyclic subgraph producing a tailored resume + ats_score, cover-letter generation, and the resume/qa embedding + retrieval layer over pgvector that grounds tailoring and answering. Exit: a queued job yields a tailored resume + ats_score.

**Spans sprints:** 2, 3 · **Issues:** 6

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| ATS-Critic node: deterministic keyword-coverage scoring | 2 | M | P0 |
| End-to-end integration test: queued -> tailored resume + ats_score | 2 | M | P0 |
| Generator node: draft tailored resume (Opus, drafting class) | 2 | L | P0 |
| Generator<->ATS-Critic cyclic subgraph with max-iteration cap | 2 | L | P0 |
| Resume/Q&A embedding + pgvector retrieval layer | 2 | L | P0 |
| cover_letter node: generate when required | 3 | M | P1 |

## EPIC-AITL — AITL Question Answering, Routing & HITL Gate

**Goal.** Build answer_questions (AITL retrieval from qa_history with the never-fabricate honesty rule), the evaluate_submission_route conditional edge implementing the tiered-autonomy gates, and pause_and_checkpoint with the Streamlit HITL approval loop. Exit: end-to-end to a human-approved draft.

**Spans sprints:** 3 · **Issues:** 7

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| End-to-end integration test: through to a human-approved draft | 3 | M | P0 |
| Honesty rule: never fabricate EEO/visa/clearance/self-ID answers | 3 | M | P0 |
| agent_confidence computation feeding the quality gate | 3 | M | P1 |
| answer_questions node: AITL retrieval from qa_history | 3 | L | P0 |
| evaluate_submission_route conditional edge (tiered-autonomy gate) | 3 | L | P0 |
| pause_and_checkpoint HITL node + resume contract | 3 | L | P0 |
| qa_history capture: persist operator answers for future AITL reuse | 3 | M | P1 |

## EPIC-APPLY — Apply Connectors, Credential Vault & Submission

**Goal.** Build the submission layer: Tier-A API submit, Playwright submit for one DOM portal, account creation with the Fernet-encrypted domain-keyed credential vault, and the submit/track nodes that persist outcomes. Exit: a real submission to a Tier-A sandbox.

**Spans sprints:** 4 · **Issues:** 7

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| End-to-end integration test: Tier-A sandbox submission | 4 | M | P0 |
| Fernet credential vault: encrypt/decrypt domain-keyed logins | 4 | L | P0 |
| Playwright submit for one DOM portal (Tier B, HITL-gated) | 4 | L | P1 |
| Spike: resilient DOM extraction strategy (browser-use/Stagehand) for Workday/Taleo | 4 | M | P2 |
| Tier-A API submission connector (Greenhouse/Lever/Ashby) | 4 | L | P0 |
| account_node: portal account creation with credential storage | 4 | L | P1 |
| submit + track nodes: persist outcome and lifecycle entry state | 4 | M | P0 |

## EPIC-EMAIL — Email-Event Service: Webhook OTP Injection & IMAP Lifecycle

**Goal.** Build the always-on FastAPI inbound-email webhook (signature verify, multipart parse, OTP injection via aupdate_state into a paused thread) and the hourly IMAP poller (LLM classifier, status state machine, forward-to-primary). Exit: OTP auto-injected; lifecycle emails update status.

**Spans sprints:** 5 · **Issues:** 7

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| Email matching heuristics: link inbound mail to the right application | 5 | M | P1 |
| End-to-end integration test: OTP injection + lifecycle status update | 5 | M | P0 |
| FastAPI inbound-email webhook with provider signature verification | 5 | L | P0 |
| Forward-to-primary inbox via aiosmtplib BackgroundTasks | 5 | M | P1 |
| IMAP poller + LLM lifecycle classifier | 5 | L | P0 |
| Lifecycle status state machine: map classifications to application.status | 5 | M | P0 |
| OTP extraction + injection via aupdate_state into paused thread | 5 | L | P0 |

## EPIC-UI — Streamlit UI, Security/Compliance & Production Hardening

**Goal.** Deliver the Streamlit Inbox/Ledger/Kanban operator UI with Promote/Drop curation, the security/compliance and audit posture, autonomy calibration, rate-limiting/anti-ban, observability, and the Railway production deployment with KMS-backed secrets. Exit: running on Railway, review-default with opt-in Tier-A auto-submit.

**Spans sprints:** 3, 6 · **Issues:** 12

| Issue | Sprint | Est | Priority |
|---|---|---|---|
| Application event audit logging helper (append-only) | 3 | M | P1 |
| Inbox view: review/approve/edit/drop paused applications | 3 | L | P0 |
| Kanban view with Promote/Drop Icebox curation | 3 | M | P1 |
| Ledger view: full application table with scores and audit drill-down | 3 | M | P2 |
| Streamlit app shell with Inbox / Ledger / Kanban navigation | 3 | M | P1 |
| Autonomy calibration: tune gates and confidence thresholds | 6 | M | P1 |
| Observability: structured logging, run metrics, and health endpoints | 6 | M | P1 |
| Railway deployment: co-located FastAPI engine + Postgres | 6 | L | P0 |
| Rate-limiting + anti-ban pacing across connectors | 6 | M | P1 |
| Secrets management + KMS-backed Fernet key in production | 6 | M | P0 |
| Security/compliance review pass + secrets/PII scan in CI | 6 | M | P0 |
| model_config admin surface in Streamlit | 6 | S | P2 |

