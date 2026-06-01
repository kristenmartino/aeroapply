# AeroApply — Notion mirror (import-ready)

> This is the content prepared for the Notion mirror (overview + backlog database).
> The live Notion push failed transiently (`net::ERR_FAILED`); re-run it with the
> Notion MCP, or paste this into a Notion page. Source of truth remains the repo + GitHub Project.

## AeroApply — Autonomous Job-Application Daemon 🛩️

> Your autonomous job-application co-pilot — sources, tailors, applies, and tracks, with you in the loop only when it matters.

**Status:** planning + skeleton complete · **Operator:** Senior BA/PM → AI Product Manager (Jupiter, FL).

### Links
- **GitHub repo (public):** https://github.com/kristenmartino/aeroapply
- **GitHub Project board (69-issue backlog):** https://github.com/users/kristenmartino/projects/5

### What it does
24/7 sourcing → Bouncer edge-filter → **Icebox** → rank (`execution_priority`) → **WIP scheduler** → *[verify open → select résumé → tailor (Generator⇄ATS-Critic) → cover letter → answer questions]* → **tiered submission gate** → API/Playwright submit → email-driven lifecycle tracking.

### Canonical decisions
- LangGraph supervisor + cyclic subgraphs, durable Postgres checkpointer.
- Persistent always-on daemon; tiered autonomy **secure-by-default**.
- Local Docker Postgres + pgvector (dev) → **Railway** (prod); not Supabase/Neon.
- Streamlit dual-view UI (Inbox + Ledger + Kanban); FastAPI + Next.js later.
- FastAPI inbound webhook (OTP injection) + IMAP lifecycle poller; Fernet credential vault.
- **Never fabricate** EEO/visa/clearance/self-ID answers — unmatched escalates to the operator.

### Roadmap — six 2-week sprints (Jun–Aug 2026)
| Sprint | Dates | Goal |
|---|---|---|
| 1 | Jun 8–19 | Foundations + Sourcing & Icebox |
| 2 | Jun 22–Jul 3 | Execution graph core + Tailoring loop |
| 3 | Jul 6–17 | Cover letter + AITL + HITL gate + Streamlit |
| 4 | Jul 20–31 | Apply connectors + credentials |
| 5 | Aug 3–14 | Email-event service (OTP + IMAP lifecycle) |
| 6 | Aug 17–28 | Hardening + Railway deploy |

### Backlog — 9 epics · 69 issues

| Epic | Issues | Sprints | GitHub |
|---|---|---|---|
| Foundations: Repo, Infra, Config & Model Router | 10 | 1, 6 | [#1](https://github.com/kristenmartino/aeroapply/issues/1) |
| Sourcing Daemon, SourcingBouncer & Connectors | 12 | 1, 4 | [#2](https://github.com/kristenmartino/aeroapply/issues/2) |
| Icebox, Ranking View & WIP Scheduler | 3 | 1, 2 | [#3](https://github.com/kristenmartino/aeroapply/issues/3) |
| LangGraph Supervisor & Execution Graph Core | 5 | 2, 6 | [#4](https://github.com/kristenmartino/aeroapply/issues/4) |
| Tailoring Loop, Cover Letters & Embeddings | 6 | 2, 3 | [#5](https://github.com/kristenmartino/aeroapply/issues/5) |
| AITL Question Answering, Routing & HITL Gate | 7 | 3 | [#6](https://github.com/kristenmartino/aeroapply/issues/6) |
| Apply Connectors, Credential Vault & Submission | 7 | 4 | [#7](https://github.com/kristenmartino/aeroapply/issues/7) |
| Email-Event Service: Webhook OTP & IMAP Lifecycle | 7 | 5 | [#8](https://github.com/kristenmartino/aeroapply/issues/8) |
| Streamlit UI, Security/Compliance & Hardening | 12 | 3, 6 | [#9](https://github.com/kristenmartino/aeroapply/issues/9) |
