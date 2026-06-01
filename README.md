# AeroApply

> Your autonomous job-application co-pilot — sources, tailors, applies, and tracks, with you in the loop only when it matters.

AeroApply is a persistent, always-on multi-agent daemon that sources relevant roles 24/7, tailors a chosen résumé variant for each (with ATS-keyword optimization via a writer⇄critic loop), writes cover letters, answers screening questions from your history, applies through the right channel (clean API or browser), and tracks the full lifecycle through email — pausing for **you** only on genuine product/judgment decisions.

**Status:** pre-alpha / planning + skeleton. Private, single-operator tool. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## What it does

```
24/7 sourcing → Bouncer edge-filter → Icebox backlog → rank (execution_priority) → WIP scheduler
   → [verify open → select résumé → tailor (Generator⇄ATS-Critic) → cover letter → answer questions]
   → submission gate (tiered, secure-by-default) → API/Playwright submit → email-driven lifecycle tracking
```

- **Multi-résumé intake** + many target roles + rich filters (location, distance, remote/hybrid/onsite, language, salary floor, on-LinkedIn-or-not).
- **Two-tier backlog** so 200 scraped jobs don't spin up 200 expensive agents: a cheap-model **Icebox** feeds a WIP-limited **execution queue**.
- **Résumé tailoring + ATS** via a cyclic Generator (Opus) ⇄ ATS-Critic (Sonnet/DeepSeek) loop with an overstatement guard.
- **Tiered autonomy, secure-by-default:** auto-submit only for clean-API sources at high confidence; Workday/LinkedIn/novel-questions/EEO always pause for you.
- **Account creation + Fernet-encrypted credential vault**; OTP codes injected into a paused browser thread via an inbound-email webhook.
- **Lifecycle tracking:** hourly IMAP poll → classifier → status updates + forward-to-your-inbox.
- **Explicit per-node model routing:** pin any node to a specific model + settings (e.g. `claude-opus-4-8`, 1M context, fast mode) as config — never hard-coded.

Full design: **[`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md)** is the canonical source of truth; **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** has the diagrams.

## Quickstart (local dev)

```bash
# 0. Prereqs: Docker, uv, Python 3.12
cp infra/.env.example .env            # fill in keys; generate a Fernet key (see the file)
cp config/profile.example.yaml config/profile.yaml   # your real filters/PII live here (gitignored)

# 1. Postgres + pgvector (bootstrap.sql auto-applies on first init)
docker compose -f infra/docker-compose.yml up -d

# 2. Install + verify
uv sync --dev
uv run pytest -q                      # 12 passing: bouncer + submission-gate logic
uv run ruff check . && uv run mypy src

# 3. (scaffolds — wired up across Sprints 1–6)
uv run aeroapply source               # sourcing daemon → Icebox
uv run aeroapply schedule             # WIP scheduler → execution graph
uv run aeroapply ui                   # Streamlit Inbox/Ledger/Kanban
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
| [ROADMAP](docs/ROADMAP.md) · [SPRINTS](docs/SPRINTS.md) · [adr/](docs/adr/) | Plan + decision records |

## Security & honesty

AeroApply **never fabricates** answers — EEO, visa/sponsorship, clearance, and self-ID fields that can't be matched to your history with high confidence always escalate to you. It is **secure-by-default** (review-before-submit), does **not** defeat CAPTCHAs or anti-bot systems, and respects platform ToS and rate limits. Credentials and PII are encrypted at rest; no real data is committed. See [`docs/SECURITY_COMPLIANCE.md`](docs/SECURITY_COMPLIANCE.md).

> **Disclaimer:** personal automation tool. Automating applications and account creation on some job platforms (notably LinkedIn) may violate their Terms of Service and carries account-ban risk — those sources are human-gated by default. Not legal advice.
