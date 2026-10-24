# AeroApply

A pre-alpha tool for sourcing jobs and drafting application materials for one
operator. The current code includes Greenhouse sourcing, filtering and ranking,
a WIP-limited queue, résumé retrieval, a generator/critic tailoring loop, and
optional cover-letter drafting.

The execution graph currently stops after drafting. It does not implement an
end-to-end application submission or email lifecycle workflow. The inbound-email
service contains integration stubs that raise `NotImplementedError`.

## Current scope

| Component | Status |
|---|---|
| Greenhouse sourcing, filters, ranking, and Kanban UI | Implemented components; require local setup and profile configuration |
| Résumé indexing, retrieval, and generator/critic loop | Implemented; model keys and database required |
| Optional cover-letter node | Implemented; enabled separately |
| Screening-question answers and submission approval | Planned integration |
| Browser submission, account creation, credential vault | Planned |
| Email-driven status updates and OTP continuation | Starter service; graph/database wiring is incomplete |

The full intended workflow is documented in [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md).
The design documents describe requirements and future integrations as well as
implemented components; they are not evidence that the complete daemon runs.

## Quickstart (local dev)

```bash
# 0. Prereqs: Docker, uv, Python 3.12
cp infra/.env.example .env            # fill in keys; generate a Fernet key (see the file)
cp config/profile.example.yaml config/profile.yaml   # your real filters/PII live here (gitignored)

# 1. Postgres + pgvector
docker compose -f infra/docker-compose.yml up -d

# 2. Install, apply schema, verify
uv sync --dev
uv run alembic upgrade head            # create the schema (single source of truth)
uv run pytest -q                       # unit + DB-integration suite
uv run ruff check . && uv run mypy src

# 3. Read-only sourcing (works today): ingest a Greenhouse board → Bouncer → Icebox, then rank
uv run aeroapply source --board <greenhouse_token>   # fetch → bouncer → icebox (read-only)
uv run aeroapply rank                                # Python-ranked Icebox (rank_jobs, not the view)
uv run aeroapply ui                                  # Streamlit Kanban-lite: ranked Icebox + Promote/Drop

# 4. Execution graph (M2): WIP-limited promotion, then checkpointed tailoring
uv run aeroapply index                # chunk + embed résumé variants → resume_chunk (pgvector)
uv run aeroapply schedule             # one scheduler cycle: top-N icebox → queued (WIP-limited)
uv run aeroapply work                 # verify_open → select_resume → retrieve → Generator⇄ATS-Critic (needs model keys)
# Starter only: graph/database wiring raises NotImplementedError
uv run uvicorn services.email_webhook.app:app   # inbound-email webhook (prod: Railway)
```

## Repository layout

| Path | What |
|---|---|
| `docs/` | Brief, PRD, architecture, data model, and 12 more design docs + ADRs |
| `backlog/` | Epics + issues (`issues.json` drives GitHub issue creation) |
| `project/` | GitHub Project (v2) field/view spec |
| `scripts/` | `bootstrap.sql` (canonical schema) + repo/label/issue/project setup |
| `config/` | `profile.example.yaml` — operator filters & scoring weights |
| `infra/` | `docker-compose.yml` (pgvector) + `.env.example` |
| `services/email_webhook/` | FastAPI inbound-email service (OTP injection + lifecycle) |
| `src/aeroapply/` | `graph/` `nodes/` `sourcing/` `connectors/` `models/` `db/` `ui/` |
| `tests/` | Unit tests (bouncer, routing) |

## Documentation index

| Doc | Topic |
|---|---|
| [PROJECT_BRIEF](docs/PROJECT_BRIEF.md) | **Canonical decisions — read first** |
| [PRD](docs/PRD.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [DATA_MODEL](docs/DATA_MODEL.md) | Product, system, schema |
| [SOURCING_AND_RANKING](docs/SOURCING_AND_RANKING.md) · [TAILORING_AND_ATS](docs/TAILORING_AND_ATS.md) | Bouncer/Icebox/ranking, résumé loop |
| [LIFECYCLE_AND_EMAIL](docs/LIFECYCLE_AND_EMAIL.md) · [CREDENTIALS_AND_AUTOMATION](docs/CREDENTIALS_AND_AUTOMATION.md) | Email daemon, accounts/credentials |
| [CONNECTORS](docs/CONNECTORS.md) · [MODEL_ROUTING](docs/MODEL_ROUTING.md) | Source/apply connectors, model registry |
| [HITL_AITL](docs/HITL_AITL.md) · [UI_UX](docs/UI_UX.md) | Autonomy gate, Streamlit dual-view |
| [SECURITY_COMPLIANCE](docs/SECURITY_COMPLIANCE.md) · [PEER_REVIEW](docs/PEER_REVIEW.md) | Risk/honesty, build-time review |
| [CALIBRATION](docs/CALIBRATION.md) | Empirically tuning weights + autonomy thresholds |
| [ROADMAP](docs/ROADMAP.md) · [SPRINTS](docs/SPRINTS.md) · [adr/](docs/adr/) | Plan + decision records |

## Review and data handling

Generated résumés and cover letters can introduce unsupported claims. Review each
draft against the source résumé and work history before using it. Critic scores
and similarity thresholds are heuristics, not measured ATS acceptance or a
guarantee of factual accuracy.

The planned submission policy requires operator approval and human handling of
EEO, visa, clearance, self-identification, and unmatched questions. The current
drafting graph does not connect that policy to a working submission path.

Example files use placeholder values; local profile and environment files are
gitignored. Gitignore does not provide encryption. The planned credential vault
does not establish encryption for current profile, database, checkpoint, or log
data. Configure storage and access controls before entering private information.

See [`docs/SECURITY_COMPLIANCE.md`](docs/SECURITY_COMPLIANCE.md) for requirements
and implementation gaps. Platform automation restrictions need review before
adding a submission connector.
