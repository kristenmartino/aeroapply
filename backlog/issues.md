# AeroApply — Delivery Backlog: Issues

> Grouped by epic. Each issue lists body, acceptance criteria, labels, estimate, sprint, and dependencies.
> Source of truth: `docs/PROJECT_BRIEF.md` + `scripts/bootstrap.sql`. Machine-readable: `backlog/issues.json`.

**9 epics · 69 issues.**

## Contents

- [EPIC-FND — Foundations: Repo, Infra, Config & Model Router](#epic-fnd) (10 issues)
- [EPIC-SRC — Sourcing Daemon, SourcingBouncer & Connectors](#epic-src) (12 issues)
- [EPIC-ICE — Icebox, Ranking View & WIP Scheduler](#epic-ice) (3 issues)
- [EPIC-GRAPH — LangGraph Supervisor & Execution Graph Core](#epic-graph) (5 issues)
- [EPIC-TAILOR — Tailoring Loop, Cover Letters & Embeddings](#epic-tailor) (6 issues)
- [EPIC-AITL — AITL Question Answering, Routing & HITL Gate](#epic-aitl) (7 issues)
- [EPIC-APPLY — Apply Connectors, Credential Vault & Submission](#epic-apply) (7 issues)
- [EPIC-EMAIL — Email-Event Service: Webhook OTP Injection & IMAP Lifecycle](#epic-email) (7 issues)
- [EPIC-UI — Streamlit UI, Security/Compliance & Production Hardening](#epic-ui) (12 issues)

---

<a id="epic-fnd"></a>
## EPIC-FND — Foundations: Repo, Infra, Config & Model Router

_Stand up the AeroApply project skeleton: public-safe repo, CI with a cross-model review gate, Docker Postgres+pgvector, the canonical schema applied via Alembic, the Pydantic config/profile loader, and the model-router skeleton that every node reads from. This is the substrate every other epic builds on._

### EPIC-FND-1. Apply bootstrap.sql as the initial Alembic migration

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:infra`, `area:infra`, `P0`
- **Depends on:** “Docker Compose dev stack: Postgres 16 + pgvector”

Wire Alembic against the dev Postgres and author the initial migration that materializes scripts/bootstrap.sql exactly: all tables, CHECK constraints, indexes, HNSW vector indexes, and the v_icebox_ranked view. bootstrap.sql remains the canonical schema; Alembic is the application mechanism. LangGraph checkpoint tables are explicitly NOT hand-written here.

**Acceptance criteria**

- [ ] alembic upgrade head on an empty database produces a schema identical to bootstrap.sql (verified by introspection/diff)
- [ ] All CHECK constraints (wip_status, status, source.kind, autonomy_tier) are present
- [ ] HNSW cosine indexes on resume_chunk.embedding and qa_history.embedding exist
- [ ] v_icebox_ranked is created with the exact weighted CASE formula from the schema
- [ ] alembic downgrade base cleanly drops everything; migration is idempotent on re-run via upgrade
- [ ] Checkpoints tables are absent (left to checkpointer.setup())

### EPIC-FND-2. Async Postgres connection pool + DB access layer

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:infra`, `P0`
- **Depends on:** “Apply bootstrap.sql as the initial Alembic migration”, “Pydantic config loader for profile.yaml + .env (PII boundary)”

Provide a psycopg3 AsyncConnectionPool and a thin typed data-access module under src/aeroapply/db that the daemon, graph, email service, and UI all share. Centralize connection lifecycle, register the pgvector adapter, and expose helpers for the core tables. This avoids ad-hoc connections scattered across subsystems.

**Acceptance criteria**

- [ ] A single AsyncConnectionPool is constructed from DATABASE_URL and reused across subsystems
- [ ] pgvector type adapters are registered so vector columns round-trip as Python lists/arrays
- [ ] Pool size and timeouts are configurable via the config loader
- [ ] Graceful startup/shutdown hooks open and close the pool without leaking connections
- [ ] An integration test inserts and reads back a row against the Docker Postgres

### EPIC-FND-3. CI pipeline: lint, type-check, tests on every PR

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:infra`, `area:infra`, `P0`
- **Depends on:** “Scaffold aeroapply repo, packaging (uv/3.12), and tooling baseline”

Stand up CI (GitHub Actions) that runs ruff, mypy, and pytest with a Postgres service container for integration tests on every pull request. Block merge on failure. This is the always-green baseline the cross-model review gate plugs into.

**Acceptance criteria**

- [ ] CI runs ruff, mypy, and pytest against Python 3.12 with uv on every PR
- [ ] A Postgres+pgvector service container is available so DB integration tests run in CI
- [ ] Required status checks block merge to the default branch on any failure
- [ ] CI caches uv dependencies to keep runs fast
- [ ] A trivial passing test confirms the pipeline is wired end-to-end

### EPIC-FND-4. Cross-model build-time review gate in CI

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:infra`, `area:infra`, `P1`
- **Depends on:** “CI pipeline: lint, type-check, tests on every PR”

Implement the build-time peer-review gate from PROJECT_BRIEF section 9.2: one model authors code, a different vendor reviews it (Claude Code authors, Codex/Gemini reviews, or vice-versa) via the cross-review tool, enforced as a CI gate. Who-does-what is configurable. This is a process/automation control, distinct from the runtime ATS-Critic loop.

**Acceptance criteria**

- [ ] A CI job invokes the configured cross-review reviewer model on the PR diff and posts findings
- [ ] Reviewer vendor is configurable and defaults to a different vendor than the author
- [ ] The gate can block or warn per configuration, and its status is visible on the PR
- [ ] Documentation in PEER_REVIEW.md explains the author/reviewer rotation and how to configure it
- [ ] A dry-run on a sample diff demonstrates the gate end-to-end

### EPIC-FND-5. Docker Compose dev stack: Postgres 16 + pgvector

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** S  ·  **Priority:** P0
- **Labels:** `type:infra`, `area:infra`, `P0`
- **Depends on:** “Scaffold aeroapply repo, packaging (uv/3.12), and tooling baseline”

Provide infra/docker-compose.yml that runs a local Postgres 16 with the pgvector extension available, plus infra/.env.example documenting the connection string and required env vars. This is the zero-cost dev backend that gives instant checkpoint writes and the vector store in one engine.

**Acceptance criteria**

- [ ] docker compose up brings up Postgres reachable on a documented localhost port
- [ ] CREATE EXTENSION vector and uuid-ossp succeed inside the container
- [ ] infra/.env.example lists DATABASE_URL and all secrets referenced by the config loader (no real values)
- [ ] A named volume persists data across container restarts
- [ ] Healthcheck reports the database ready before dependents start

### EPIC-FND-6. Model-router skeleton with provider abstraction and per-node overrides

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:infra`, `P0`
- **Depends on:** “Async Postgres connection pool + DB access layer”

Build src/aeroapply/models/router.py: every node calls the router with its node_name and the router resolves model_config[node] -> {provider, model_id, params, fallback}. A routing policy assigns defaults by task class; explicit per-node overrides always win. Abstract providers (Anthropic, DeepSeek, OpenAI/Codex, Ollama) behind one interface. Seed model_config with the canonical roster (claude-opus-4-8 drafting, claude-sonnet-4-6 critique, claude-haiku-4-5 / local extraction).

**Acceptance criteria**

- [ ] router.resolve(node_name) returns provider/model_id/params/fallback, preferring DB model_config overrides over policy defaults
- [ ] Only current model IDs are used (claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5); no legacy IDs
- [ ] Provider interface is uniform so a node is provider-agnostic; at least Anthropic and a local/Ollama stub are wired
- [ ] Fallback model is invoked on a simulated primary-provider failure
- [ ] A seed routine populates model_config rows for tailor.generator, tailor.critic, sourcing.parser, and email.classifier
- [ ] Unit tests cover override-wins and fallback paths

### EPIC-FND-7. Pydantic config loader for profile.yaml + .env (PII boundary)

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:infra`, `P0`
- **Depends on:** “Scaffold aeroapply repo, packaging (uv/3.12), and tooling baseline”

Implement a typed Pydantic v2 settings layer that loads operator config from config/profile.yaml and secrets from .env, enforcing the PII boundary: concrete personal values (name, coords, salary floor, target titles, weights, credentials, emails) live only in untracked files. Ship config/profile.example.yaml with illustrative defaults. Expose ranking weights, search-profile filters, and target roles as typed objects.

**Acceptance criteria**

- [ ] Loader validates and exposes salary_floor, home coords, target roles+alignment, remote modes, and execution-priority weight overrides
- [ ] config/profile.example.yaml is committed; config/profile.yaml is gitignored and never required to be committed
- [ ] Missing required secret raises a clear, early validation error naming the missing key
- [ ] Weights from profile.yaml override the canonical defaults used by ranking
- [ ] Unit tests cover example-config load and a missing-secret failure

### EPIC-FND-8. Scaffold aeroapply repo, packaging (uv/3.12), and tooling baseline

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:infra`, `area:infra`, `P0`
- **Depends on:** _(none)_

Create the public-safe aeroapply repository skeleton matching the canonical repository map: pyproject.toml managed by uv on Python 3.12, the src/aeroapply package layout, docs/, infra/, scripts/, services/, tests/, README, CONTRIBUTING, and .gitignore. Wire ruff, mypy (strict), and pytest as the standard toolchain with Pydantic v2 as a core dependency. This is the first commit everything else branches from.

**Acceptance criteria**

- [ ] uv sync installs the project on a clean Python 3.12 environment with no system-Python-3.9 fallback
- [ ] Directory tree matches the repository map in PROJECT_BRIEF section 14 (graph/, nodes/, sourcing/, connectors/, models/, db/, ui/)
- [ ] ruff check, mypy, and pytest all run via documented commands and pass on an empty/placeholder test
- [ ] .gitignore excludes .env, config/profile.yaml, *.pdf resumes, and local secrets
- [ ] README documents local setup and the uv-based workflow

### EPIC-FND-9. Seed data + fixtures: operator, profile, resumes, qa_history, sources

- **Epic:** `EPIC-FND`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:test`, `area:infra`, `P1`
- **Depends on:** “Apply bootstrap.sql as the initial Alembic migration”, “Pydantic config loader for profile.yaml + .env (PII boundary)”

Provide a seeding routine and pytest fixtures that populate a realistic operator (app_user), a search_profile, target_roles with alignment, resume_variants + chunks, qa_history (including sensitive eeo/visa/clearance rows), and source rows with tiers. This unblocks every downstream test and the UI without using any real PII (illustrative example data only).

**Acceptance criteria**

- [ ] A seed script creates a complete operator graph: app_user, search_profile, target_role, resume_variant(+chunks), qa_history, source
- [ ] qa_history seeds include sensitive rows (eeo/visa/clearance) flagged sensitive=TRUE
- [ ] All seed values are illustrative (no real names, addresses, salaries, or credentials)
- [ ] Reusable pytest fixtures expose the seeded graph to integration tests
- [ ] Seeding is idempotent and safe to re-run against the dev database

### EPIC-FND-10. Documentation suite: align docs with brief, schema, and backlog

- **Epic:** `EPIC-FND`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P2
- **Labels:** `type:docs`, `area:infra`, `P2`
- **Depends on:** “Apply bootstrap.sql as the initial Alembic migration”, “evaluate_submission_route conditional edge (tiered-autonomy gate)”

Author/refresh the supporting docs referenced throughout the repository map (ARCHITECTURE.md, DATA_MODEL.md, SOURCING_AND_RANKING.md, TAILORING_AND_ATS.md, LIFECYCLE_AND_EMAIL.md, CREDENTIALS_AND_AUTOMATION.md, HITL_AITL.md, MODEL_ROUTING.md, UI_UX.md) so every doc agrees with PROJECT_BRIEF (source of truth), the schema, and this backlog. Drift between docs and the brief is treated as a bug.

**Acceptance criteria**

- [ ] Each listed doc exists and is consistent with PROJECT_BRIEF and bootstrap.sql
- [ ] Canonical formulas (execution_priority), gates, status machine, and model roster are stated identically to the brief
- [ ] Only current model IDs appear anywhere in docs
- [ ] Cross-references between docs and code paths are accurate
- [ ] A docs review confirms no conflict with the source-of-truth brief

---

<a id="epic-src"></a>
## EPIC-SRC — Sourcing Daemon, SourcingBouncer & Connectors

_Build the 24/7 sourcing subsystem: API connectors (Greenhouse, Lever, Ashby) plus DOM-portal stubs, the SourcingBouncer edge filters that drop junk before any DB write, dedupe/fingerprinting, and Icebox writes that create application rows in wip_status='icebox'. Exit: ranked jobs flow into the Icebox._

### EPIC-SRC-1. Always-on sourcing daemon loop with per-source pacing

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** L  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:sourcing`, `P1`
- **Depends on:** “Icebox writes: persist survivors as jobs + icebox applications”, “Model-router skeleton with provider abstraction and per-node overrides”

Build the persistent asyncio sourcing daemon that iterates enabled sources on their configured cadence, runs each connector through the bouncer and Icebox-write path, and respects per-source rate limits and anti-ban pacing. It uses cheap/local extraction models per the router. The daemon must be resilient: one source failing does not halt the others.

**Acceptance criteria**

- [ ] Daemon runs continuously and schedules each enabled source on its own cadence
- [ ] Per-source rate_limit/pacing is enforced; LinkedIn/DOM sources pace conservatively
- [ ] A connector exception is caught, logged, and isolated so other sources keep running
- [ ] Extraction/classification uses the router's cheap/local model class
- [ ] A run record or structured log captures per-cycle counts (fetched, dropped, inserted)
- [ ] Daemon can be started/stopped cleanly and is exercised by an integration test with fake connectors
- [ ] Sourcing daemon starts and falls back to claude-haiku-4-5 when Ollama is unreachable at startup; a structured log warns the operator

### EPIC-SRC-2. Ashby API connector (Tier A)

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:connectors`, `P0`
- **Depends on:** “Source connector interface + registry seeded from source table”

Implement the Ashby job-board API connector: fetch the public posting list for a configured org, normalize fields, and tag portal_type='ashby'. Ashby is Tier-A and supports clean structured apply payloads for later auto-submit. Follow the shared connector contract.

**Acceptance criteria**

- [ ] Connector fetches postings for a configurable Ashby org slug/token
- [ ] Postings normalize with portal_type='ashby', portal_url, external_id, posted_at, and salary where present
- [ ] Compensation bands are parsed into salary_min/salary_max when Ashby exposes them
- [ ] Pacing respects source rate_limit
- [ ] Fixture-based tests verify mapping and Tier-A tagging

### EPIC-SRC-3. DOM-portal connector stubs (Workday, LinkedIn) with tier metadata

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** S  ·  **Priority:** P2
- **Labels:** `type:feature`, `area:connectors`, `P2`
- **Depends on:** “Source connector interface + registry seeded from source table”

Provide connector stubs for Workday and LinkedIn that register as kind=browser with the correct autonomy tiers (Workday Tier B, LinkedIn Tier B/C) and conservative rate limits, but do not yet drive a browser. These reserve the seams for the Playwright-based submit work in Sprint 4 and keep tiering/anti-ban policy centralized now.

**Acceptance criteria**

- [ ] Workday and LinkedIn sources are registered as kind=browser with autonomy_tier B (LinkedIn flagged B/C per ToS posture)
- [ ] Stubs expose conservative rate_limit defaults and an enabled flag (LinkedIn gated by include_linkedin)
- [ ] Stubs raise a clear NotImplemented-style signal rather than silently returning empty when invoked for fetch
- [ ] Tier and ToS notes are documented in CONNECTORS.md
- [ ] No browser dependency is imported at this stage

### EPIC-SRC-4. Dedupe fingerprinting for jobs

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:sourcing`, `P0`
- **Depends on:** “Source connector interface + registry seeded from source table”

Implement the dedupe key: a deterministic SHA-256 fingerprint over normalized (company + title + location) written to job.fingerprint (UNIQUE). Sourcing must upsert on fingerprint so re-scrapes and cross-source duplicates do not create duplicate jobs or applications. Normalization (casing, whitespace, punctuation) must be stable.

**Acceptance criteria**

- [ ] fingerprint is a stable 64-char hash of normalized company+title+location
- [ ] Re-ingesting the same posting is a no-op (or refresh) rather than a duplicate insert, honoring the UNIQUE constraint
- [ ] The same role surfaced by two sources collapses to one job row
- [ ] Normalization is unit-tested against case/whitespace/punctuation variants producing identical fingerprints
- [ ] Conflict handling is race-safe under concurrent connector writes

### EPIC-SRC-5. End-to-end integration test: sourced -> ranked -> queued

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:sourcing`, `P0`
- **Depends on:** “Icebox writes: persist survivors as jobs + icebox applications”, “Validate and harden v_icebox_ranked execution-priority view”

Author an integration test that runs the full Sprint-1 slice against the Docker Postgres: fake connectors emit mixed postings, the SourcingBouncer drops junk, survivors are deduped and written as icebox applications, and `ranking.rank_jobs` returns them in the expected priority order. This is the Sprint-1 exit verification (ranked jobs flow into the Icebox).

**Acceptance criteria**

- [ ] Test seeds a mix of keep/drop postings through the real bouncer and Icebox-write path
- [ ] Dropped postings never appear as jobs/applications; survivors appear exactly once
- [ ] `ranking.rank_jobs` returns survivors ordered by execution_priority with a promoted row on top
- [ ] The test runs in CI against the Postgres service container
- [ ] Assertions cover dedupe, bouncer reasons, and ranking order

### EPIC-SRC-6. Greenhouse API connector (Tier A)

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:connectors`, `P0`
- **Depends on:** “Source connector interface + registry seeded from source table”

Implement the Greenhouse job-board API connector using httpx: enumerate board postings, map each to the normalized posting shape, and capture portal_type='greenhouse' plus the structured apply URL. Greenhouse is a clean-API Tier-A source eligible for later auto-submit. Pace requests per the source.rate_limit config.

**Acceptance criteria**

- [ ] Connector fetches live postings from a configurable Greenhouse board token via httpx
- [ ] Each posting maps to normalized fields including portal_url, portal_type='greenhouse', and external_id
- [ ] Salary, location, and remote hints are parsed where present and left null otherwise
- [ ] Requests honor the rate_limit/pacing from the source config
- [ ] Tests run against a recorded/fixture response with no live network dependency

### EPIC-SRC-7. Icebox writes: persist survivors as jobs + icebox applications

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:sourcing`, `P0`
- **Depends on:** “SourcingBouncer edge filters (drop before DB write)”, “Dedupe fingerprinting for jobs”, “Source connector interface + registry seeded from source table”

Wire bouncer survivors through dedupe into the job table and create a paired application row in wip_status='icebox', status='sourced' (respecting the UNIQUE (user_id, job_id) constraint). This is what makes a posting visible to the ranking view. Sourcing must never write a job that failed the bouncer.

**Acceptance criteria**

- [ ] Only bouncer survivors are persisted; dropped postings never reach the job table
- [ ] Each new job gets exactly one application row with wip_status='icebox' and status='sourced'
- [ ] UNIQUE (user_id, job_id) is respected so re-sourcing does not duplicate applications
- [ ] search_profile_id is attached to the application when the posting came from a profile-driven search
- [ ] Integration test: feed mixed postings, assert only survivors appear as icebox applications

### EPIC-SRC-8. Lever API connector (Tier A)

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:connectors`, `P0`
- **Depends on:** “Source connector interface + registry seeded from source table”

Implement the Lever postings API connector: fetch postings for a configured company handle, normalize to the posting shape, and tag portal_type='lever'. Lever is Tier-A (structured payloads) and a target for later API submit. Reuse the shared connector interface and httpx client.

**Acceptance criteria**

- [ ] Connector retrieves postings for a configurable Lever company handle
- [ ] Postings normalize with portal_type='lever', portal_url, external_id, and posted_at
- [ ] Remote/location and team metadata are mapped into normalized/raw fields
- [ ] Pacing respects the source rate_limit config
- [ ] Fixture-based tests cover parsing and field mapping

### EPIC-SRC-9. Source connector interface + registry seeded from source table

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:connectors`, `P0`
- **Depends on:** “Async Postgres connection pool + DB access layer”

Define a common async connector interface (fetch -> normalized RawPosting list) and a registry under src/aeroapply/connectors that is seeded from the source table (key, kind api|browser, autonomy_tier, enabled, config, rate_limit). Connectors must emit a normalized posting shape that maps cleanly onto the job table columns. This is the contract every concrete connector implements.

**Acceptance criteria**

- [ ] A Connector protocol defines an async fetch yielding normalized postings with fields aligned to the job table
- [ ] source rows are seeded for greenhouse, lever, ashby (kind=api, tier=A) and workday, linkedin (kind=browser, tier=B/C)
- [ ] Registry resolves an enabled connector by source key and respects the enabled flag
- [ ] Normalized posting carries company, title, location, remote_mode, salary_min/max, url, portal_url, portal_type, posted_at, external_id, raw
- [ ] A fake connector exercises the interface in tests without network access

### EPIC-SRC-10. SourcingBouncer edge filters (drop before DB write)

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:sourcing`, `P0`
- **Depends on:** “Pydantic config loader for profile.yaml + .env (PII boundary)”

Implement src/aeroapply/sourcing/bouncer.py with the five canonical edge filters that drop junk postings before any DB write: geo fence (geopy, 40mi of Jupiter unless remote), seniority/industry regex drop, salary-floor (band max < $115k, unlisted passes), clearance/visa gates per operator work_auth, and ghost-job (posted_at older than 45 days). Each drop records a structured reason for observability.

**Acceptance criteria**

- [ ] Geo fence keeps remote, keeps hybrid/onsite within distance_miles of home coords via geopy, drops the rest
- [ ] Regex drops titles matching junior|associate|entry-level|intern|grad|construction|civil|healthcare|clinical|mechanical
- [ ] Salary filter drops when parsed band max > 0 and < salary_floor; unlisted (0/None) passes through
- [ ] Clearance/visa filter drops on the canonical phrase set (ts/sci, top secret, polygraph, clearance required, no c2c, w2 only, us citizens only)
- [ ] Ghost-job filter drops postings older than 45 days; thresholds and coords come from config not hard-coded
- [ ] Unit tests cover each filter with keep and drop cases plus a drop-reason payload
- [ ] A valid AI PM posting that mentions an excluded-industry term in its body (not its title) still passes the bouncer

### EPIC-SRC-11. ATS resolution from aggregators: hydrate portal_type + autonomy_tier from the apply URL

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:connectors`, `P1`
- **Depends on:** “Source connector interface + registry seeded from source table”, “DOM-portal connector stubs (Workday, LinkedIn) with tier metadata”

Implement ATS resolution during hydrate(): when an aggregator-sourced posting (LinkedIn/Indeed) carries a portal_url that actually points to a Greenhouse/Lever/Ashby board, detect the underlying ATS from the URL and rewrite portal_type and autonomy_tier accordingly. This promotes otherwise Tier-B/C aggregator roles to Tier-A so they become eligible for clean-API submission and (per the gates) opt-in auto-submit.

**Acceptance criteria**

- [ ] hydrate() inspects portal_url and detects an underlying Greenhouse/Lever/Ashby board from the URL pattern
- [ ] On a positive match it rewrites portal_type to greenhouse/lever/ashby and sets autonomy_tier to A so LinkedIn/Indeed-sourced roles can become Tier A
- [ ] Non-ATS or ambiguous URLs are left untouched (portal_type/autonomy_tier unchanged) rather than misclassified
- [ ] Resolution is recorded as an application_event (or structured log) capturing the original and resolved portal_type/tier
- [ ] Unit tests cover Greenhouse/Lever/Ashby URL detection, a non-ATS URL no-op, and the tier/portal_type rewrite

### EPIC-SRC-12. Connector ToS/anti-ban policy doc + LinkedIn Tier B/C posture

- **Epic:** `EPIC-SRC`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** S  ·  **Priority:** P2
- **Labels:** `type:docs`, `area:connectors`, `P2`
- **Depends on:** “DOM-portal connector stubs (Workday, LinkedIn) with tier metadata”

Document the per-connector autonomy tiers, ToS constraints, and anti-ban posture in CONNECTORS.md, codifying that clean-API ATS are Tier A, DOM portals are Tier B (HITL), and anything requiring fabrication or ToS-prohibited automation (notably LinkedIn auto-apply/scraping) is Tier B/C with conservative pacing and no anti-bot evasion. Keeps engineering aligned with the compliance non-negotiables.

**Acceptance criteria**

- [ ] CONNECTORS.md enumerates each source with its kind, autonomy_tier, ToS notes, and pacing posture
- [ ] LinkedIn is documented as Tier B/C, ban-prone, human-gated, and gated by include_linkedin
- [ ] The no-CAPTCHA-defeat / no-anti-bot-evasion rule is stated as a hard constraint for browser connectors
- [ ] Tier definitions match source.autonomy_tier values in the seed data
- [ ] Doc cross-references the submission gate and rate-limiting implementation

---

<a id="epic-ice"></a>
## EPIC-ICE — Icebox, Ranking View & WIP Scheduler

_Implement the two-tier backlog: the v_icebox_ranked execution-priority view, the WIP-limited Supervisor/Scheduler that promotes the top-N icebox rows to queued on a schedule, and the stale-queue guard. This is the bridge between cheap sourcing and expensive execution._

### EPIC-ICE-1. Validate and harden v_icebox_ranked execution-priority view

- **Epic:** `EPIC-ICE`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:sourcing`, `P0`
- **Depends on:** “Apply bootstrap.sql as the initial Alembic migration”, “Icebox writes: persist survivors as jobs + icebox applications”

Verify the v_icebox_ranked view — the frozen-weight debug/fallback to the canonical Python ranker (`ranking.rank_jobs` in `src/aeroapply/sourcing/ranking.py`, which reads `profile.ranking_weights` live) — stays in sync with that execution-priority formula (manual_override +100 trump; title 35%; location 25%; recency 20%; competition 10%; urgency 10%) and behaves correctly on NULL applicant_count/closing_date. Add coverage that locks the weighting and ordering so future schema edits can't silently drift the fallback from the canonical Python ranking.

**Acceptance criteria**

- [ ] View returns rows only for wip_status='icebox' AND status='sourced', ordered by execution_priority DESC
- [ ] manual_override=TRUE produces a score above any non-promoted row regardless of other factors
- [ ] NULL applicant_count and NULL closing_date are handled without error and score as the 'else' branch
- [ ] Seeded fixtures assert exact execution_priority for representative postings (AI PM remote recent vs. adjacent onsite stale)
- [ ] A regression test fails if any weight or threshold changes unexpectedly

### EPIC-ICE-2. WIP-limited Supervisor/Scheduler promotes top-N icebox to queued

- **Epic:** `EPIC-ICE`  ·  **Sprint:** 1 (06/08–06/19)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Validate and harden v_icebox_ranked execution-priority view”

Implement the Supervisor/Scheduler that runs on a schedule (e.g., every few hours), reads the Python ranker (`ranking.rank_jobs` over `profile.ranking_weights`), and promotes the top-N (default 5) icebox applications to wip_status='queued', status='queued'. It enforces the WIP limit so only queued jobs ever consume frontier tokens, and it is idempotent under repeated runs.

**Acceptance criteria**

- [ ] Scheduler selects the top-N from the Python ranker (`ranking.rank_jobs` over `profile.ranking_weights`) and flips them to wip_status='queued', status='queued'
- [ ] N (WIP limit) is configurable and defaults to 5
- [ ] Active WIP is counted so the queue is topped up to N rather than over-filled
- [ ] Promotion is idempotent: re-running without new capacity promotes nothing
- [ ] manual_override rows are promoted ahead of organically-ranked rows
- [ ] Each promotion writes an application_event audit entry

### EPIC-ICE-3. Scheduler trigger: cadence runner for promotion cycles

- **Epic:** `EPIC-ICE`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** S  ·  **Priority:** P2
- **Labels:** `type:feature`, `area:graph`, `P2`
- **Depends on:** “WIP-limited Supervisor/Scheduler promotes top-N icebox to queued”

Provide the recurring trigger that invokes the Supervisor promotion cycle on a configurable interval within the always-on runtime (asyncio scheduling; no premature Celery). Promotion and execution-graph dispatch are decoupled so the queue fill rate is tunable independently of graph throughput.

**Acceptance criteria**

- [ ] A configurable interval drives promotion cycles without blocking other daemon work
- [ ] Interval and WIP limit are read from config, not hard-coded
- [ ] Overlapping cycles are prevented (a cycle does not start while the previous is running)
- [ ] The runner logs each cycle outcome (counts promoted, current WIP)
- [ ] Shutdown cancels the scheduled task cleanly

---

<a id="epic-graph"></a>
## EPIC-GRAPH — LangGraph Supervisor & Execution Graph Core

_Build the durable LangGraph execution graph with the Postgres checkpointer: shared state schema, supervisor wiring, the verify_open stale-job guard, select_resume variant selection, and the run/thread linkage. Provides the spine that tailoring, answering, routing, and submission hang off of._

### EPIC-GRAPH-1. LangGraph state schema + Postgres checkpointer setup

- **Epic:** `EPIC-GRAPH`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Model-router skeleton with provider abstraction and per-node overrides”, “Apply bootstrap.sql as the initial Alembic migration”

Define the typed LangGraph state (job/application context, tailored artifacts, ats_score, agent_confidence, answers, blockers, verification_code, routing decision) and wire langgraph-checkpoint-postgres against the AsyncConnectionPool. Call checkpointer.setup() to auto-create the checkpoints tables. thread_id equals the application id so freeze/resume is keyed per application.

**Acceptance criteria**

- [ ] A Pydantic/TypedDict graph state captures all fields the nodes read/write, including verification_code and the submission route decision
- [ ] AsyncPostgresSaver is configured from the shared pool and checkpointer.setup() creates the checkpoints tables
- [ ] thread_id is set to the application id for every run and stored on application.thread_id
- [ ] A minimal two-node graph checkpoints and resumes from the DB across process restart in a test
- [ ] Checkpoint tables are created only via setup(), not via Alembic/bootstrap.sql

### EPIC-GRAPH-2. Supervisor graph wiring + run/thread linkage

- **Epic:** `EPIC-GRAPH`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “LangGraph state schema + Postgres checkpointer setup”, “WIP-limited Supervisor/Scheduler promotes top-N icebox to queued”

Assemble the execution graph topology (verify_open -> select_resume -> tailor subgraph -> cover_letter -> answer_questions -> route -> submit/track) under a supervisor that dispatches queued applications. Create a run row per execution and keep application.wip_status in sync (queued -> active -> done/parked). Nodes resolve their model via the router by node name.

**Acceptance criteria**

- [ ] Compiled graph wires the canonical node sequence with the conditional submission edge as the only branch point
- [ ] Dispatching a queued application flips wip_status to 'active' and writes a run row with the thread_id
- [ ] On terminal completion wip_status becomes 'done'; on HITL pause it becomes 'parked'
- [ ] Each node fetches its model config through the router using its node_name
- [ ] An end-to-end test with stubbed node bodies walks a queued app through to a terminal run state

### EPIC-GRAPH-3. select_resume node: choose best resume variant

- **Epic:** `EPIC-GRAPH`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:graph`, `P1`
- **Depends on:** “Supervisor graph wiring + run/thread linkage”

Implement select_resume: given the job, pick the most appropriate resume_variant (e.g., AI Product Manager base vs. Senior BA base) using target-role alignment and a lightweight match signal, and record the chosen resume_variant_id on the application. This sets the starting point the tailoring loop refines.

**Acceptance criteria**

- [ ] Node selects among the operator's resume_variant rows and writes resume_variant_id to the application
- [ ] Selection prefers the variant whose role_focus best aligns with the job title/target roles, defaulting to is_default when ambiguous
- [ ] A match_score signal is computed and stored to inform downstream ranking/telemetry
- [ ] Selection rationale is recorded as an application_event
- [ ] Tests assert correct variant chosen for an AI PM posting vs. a BA posting

### EPIC-GRAPH-4. verify_open node: stale-job HTTP guard

- **Epic:** `EPIC-GRAPH`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Supervisor graph wiring + run/thread linkage”

Implement verify_open as the graph's first node: HTTP-ping job.portal_url and, on 404 or 'no longer accepting' signals, set status='closed_before_execution', mark wip_status='done', and stop the run so no frontier drafting is wasted. On success the graph proceeds to select_resume.

**Acceptance criteria**

- [ ] verify_open issues an httpx request to portal_url with a sane timeout
- [ ] 404 / closed-posting heuristics set status='closed_before_execution' and end the run before any drafting node
- [ ] Transient/network errors are retried briefly, then escalated rather than crashing the graph
- [ ] An application_event records the verify outcome
- [ ] Tests cover open, closed (404 and text-signal), and transient-error paths with a mocked HTTP layer

### EPIC-GRAPH-5. Model fallback-chain exhaustion parks the application to needs_review

- **Epic:** `EPIC-GRAPH`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:graph`, `P1`
- **Depends on:** “Model-router skeleton with provider abstraction and per-node overrides”, “Supervisor graph wiring + run/thread linkage”, “Inbox view: review/approve/edit/drop paused applications”

Harden the model-router/graph boundary so that when every model in a node's fallback chain is exhausted (all providers fail), the run does not crash: park the application to status='needs_review', wip_status='parked' with blockers.model_unavailable populated, and surface it in the operator's Inbox for manual attention. This keeps the always-on system resilient to provider outages and secure-by-default.

**Acceptance criteria**

- [ ] When the primary model and all configured fallbacks fail, the node raises a handled model-unavailable condition rather than crashing the graph
- [ ] The application is parked: status='needs_review', wip_status='parked', with a structured blockers.model_unavailable entry
- [ ] The parked item surfaces in the Inbox so the operator can retry or intervene
- [ ] The event is audited as a system-actor application_event (no secrets/keys in the payload)
- [ ] An integration test simulates full fallback-chain exhaustion and verifies the parked needs_review state and Inbox surfacing

---

<a id="epic-tailor"></a>
## EPIC-TAILOR — Tailoring Loop, Cover Letters & Embeddings

_Implement the runtime peer-review system: the Generator<->ATS-Critic cyclic subgraph producing a tailored resume + ats_score, cover-letter generation, and the resume/qa embedding + retrieval layer over pgvector that grounds tailoring and answering. Exit: a queued job yields a tailored resume + ats_score._

### EPIC-TAILOR-1. ATS-Critic node: deterministic keyword-coverage scoring

- **Epic:** `EPIC-TAILOR`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Generator node: draft tailored resume (Opus, drafting class)”

Implement the ATS-Critic: a strict reasoner at temperature=0 (claude-sonnet-4-6 or DeepSeek via router node tailor.critic) that scores the tailored resume's keyword coverage against the job description, emits an ats_score, and returns a concrete list of missing/weak keywords and gaps for the Generator to address. Determinism matters so the loop converges.

**Acceptance criteria**

- [ ] Critic returns a numeric ats_score plus a structured list of missing/weak keywords and gap notes
- [ ] Model is resolved via router node 'tailor.critic' at temperature=0 for deterministic scoring
- [ ] Scoring reflects the job's required keywords/skills, not generic prose quality
- [ ] Identical input yields an identical score and gap list (determinism verified)
- [ ] Tests with a stubbed critic assert the score+gaps schema and threshold comparison semantics

### EPIC-TAILOR-2. End-to-end integration test: queued -> tailored resume + ats_score

- **Epic:** `EPIC-TAILOR`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:graph`, `P0`
- **Depends on:** “Generator<->ATS-Critic cyclic subgraph with max-iteration cap”, “verify_open node: stale-job HTTP guard”, “select_resume node: choose best resume variant”

Author an integration test for the Sprint-2 exit: a queued application runs through verify_open, select_resume, and the Generator<->ATS-Critic subgraph (with stubbed models) and ends with a persisted tailored_resume_* and ats_score on the application, checkpointed in Postgres. Verifies the tailoring spine produces a scored draft.

**Acceptance criteria**

- [ ] A queued application is driven through the graph with deterministic stubbed Generator/Critic models
- [ ] verify_open passes (open posting) and select_resume sets resume_variant_id
- [ ] The tailoring loop converges or caps and writes tailored_resume_json/text and ats_score
- [ ] State is checkpointed in Postgres and resumable mid-run
- [ ] Assertions confirm the persisted artifacts and a numeric ats_score

### EPIC-TAILOR-3. Generator node: draft tailored resume (Opus, drafting class)

- **Epic:** `EPIC-TAILOR`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Resume/Q&A embedding + pgvector retrieval layer”, “select_resume node: choose best resume variant”

Implement the Generator side of the tailoring loop: using the selected resume variant, retrieved resume chunks, and the job description, draft a tailored resume (structured + text) with claude-opus-4-8 in fast mode at temperature ~0.6 via the router (node tailor.generator). On subsequent iterations it incorporates the ATS-Critic's gap feedback. Never fabricate experience the operator doesn't have.

**Acceptance criteria**

- [ ] Generator produces tailored_resume_json and tailored_resume_text grounded in retrieved resume chunks
- [ ] Model is resolved via router node 'tailor.generator' as claude-opus-4-8 with fast mode and the configured temperature
- [ ] On iterations >1 the prompt includes the critic's prior gaps and the draft visibly addresses them
- [ ] Output stays truthful: no invented employers, titles, dates, or credentials beyond source material
- [ ] Tests with a stubbed model assert the feedback-incorporation contract and JSON/text shape

### EPIC-TAILOR-4. Generator<->ATS-Critic cyclic subgraph with max-iteration cap

- **Epic:** `EPIC-TAILOR`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “ATS-Critic node: deterministic keyword-coverage scoring”, “LangGraph state schema + Postgres checkpointer setup”

Wire the Generator and ATS-Critic into a cyclic LangGraph subgraph that loops until ats_score clears the threshold (e.g., >= 0.90) or a max-iteration cap is hit, then writes the final tailored_resume_* and ats_score to the application. This is the runtime peer-review system; it must not loop forever and must persist the best result on cap.

**Acceptance criteria**

- [ ] Subgraph loops Generator->Critic and exits when ats_score >= threshold or iteration cap is reached
- [ ] Threshold and max iterations are configurable; the best-scoring draft is persisted if the cap is hit below threshold
- [ ] Final ats_score, tailored_resume_json, and tailored_resume_text are written to the application
- [ ] Per-iteration ats_score and gaps are logged as application_events for observability
- [ ] An integration test drives a stubbed loop that converges, and one that hits the cap, asserting persistence in both

### EPIC-TAILOR-5. Resume/Q&A embedding + pgvector retrieval layer

- **Epic:** `EPIC-TAILOR`  ·  **Sprint:** 2 (06/22–07/03)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Async Postgres connection pool + DB access layer”, “Model-router skeleton with provider abstraction and per-node overrides”

Build the embedding + retrieval layer over pgvector: embed resume_chunk and qa_history rows (default OpenAI text-embedding-3-small, 1536-d, matching the schema; swappable to a local embedder) and provide cosine-similarity retrieval helpers using the HNSW indexes. This grounds both tailoring (relevant resume chunks) and AITL answering (similar past questions).

**Acceptance criteria**

- [ ] An embedding provider abstraction defaults to text-embedding-3-small at 1536-d and is swappable, asserting dimension matches the schema
- [ ] Resume chunks and qa_history questions are embedded and persisted to their vector columns
- [ ] Retrieval helpers return top-k by cosine similarity using the HNSW indexes for both tables
- [ ] A backfill routine embeds existing rows that lack an embedding
- [ ] Tests verify dimension enforcement and that retrieval ranks a planted relevant chunk/question first

### EPIC-TAILOR-6. cover_letter node: generate when required

- **Epic:** `EPIC-TAILOR`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:graph`, `P1`
- **Depends on:** “Generator<->ATS-Critic cyclic subgraph with max-iteration cap”

Implement the cover_letter node: when the job/portal requires a cover letter, generate one with the drafting model (claude-opus-4-8, drafting class) grounded in the tailored resume and job description, and persist it to application.cover_letter. Skip cleanly when no cover letter is required. Truthful, role-aligned, human-sounding prose.

**Acceptance criteria**

- [ ] Node detects the cover-letter requirement and only generates when required, otherwise no-ops
- [ ] Generated letter is grounded in the tailored resume + job description and written via the drafting-class model
- [ ] cover_letter is persisted on the application and surfaced for HITL review
- [ ] Content is truthful and contains no fabricated claims
- [ ] Tests cover the required and not-required branches

---

<a id="epic-aitl"></a>
## EPIC-AITL — AITL Question Answering, Routing & HITL Gate

_Build answer_questions (AITL retrieval from qa_history with the never-fabricate honesty rule), the evaluate_submission_route conditional edge implementing the tiered-autonomy gates, and pause_and_checkpoint with the Streamlit HITL approval loop. Exit: end-to-end to a human-approved draft._

### EPIC-AITL-1. End-to-end integration test: through to a human-approved draft

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:graph`, `P0`
- **Depends on:** “pause_and_checkpoint HITL node + resume contract”, “Inbox view: review/approve/edit/drop paused applications”, “cover_letter node: generate when required”

Author an integration test for the Sprint-3 exit: a queued job flows through tailoring, cover letter, answer_questions, and evaluate_submission_route into pause_and_checkpoint, then the Inbox approval resumes it to status='approved'. Verifies the full HITL path from sourcing to a human-approved draft works end-to-end.

**Acceptance criteria**

- [ ] The graph reaches needs_review/parked with populated blockers and tailored artifacts
- [ ] A simulated Inbox approve action resumes the exact thread_id to status='approved'
- [ ] A sensitive/novel question correctly forces escalation rather than auto-answer
- [ ] All transitions emit application_events with the correct actors
- [ ] The test runs against Postgres in CI and asserts the final approved state

### EPIC-AITL-2. Honesty rule: never fabricate EEO/visa/clearance/self-ID answers

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:security`, `P0`
- **Depends on:** “answer_questions node: AITL retrieval from qa_history”

Enforce the non-negotiable honesty rule inside answer_questions: any field typed eeo/visa/clearance/self-ID (qa_history.sensitive=TRUE), and any novel/unseen question, must never be auto-filled and must mark needs_human with a blocker reason. This is the core compliance guarantee from PROJECT_BRIEF section 13.1 and feeds the honesty gate.

**Acceptance criteria**

- [ ] Questions classified as sensitive (eeo/visa/clearance/self-ID) are never answered autonomously, regardless of similarity
- [ ] Novel/unseen questions with no high-confidence match set needs_human=TRUE with a descriptive blocker
- [ ] field_type classification is recorded so the honesty gate and audit can inspect it
- [ ] No fabricated value is ever written for a sensitive/unknown field
- [ ] Tests prove a sensitive field and a novel question both escalate even when superficially similar to history

### EPIC-AITL-3. agent_confidence computation feeding the quality gate

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:graph`, `P1`
- **Depends on:** “answer_questions node: AITL retrieval from qa_history”, “Generator<->ATS-Critic cyclic subgraph with max-iteration cap”

Define and compute application.agent_confidence as an aggregate signal (tailoring convergence, answer-match confidences, absence of blockers) that the quality gate consumes (>= 0.95 required for auto). It must be conservative: any unanswered/sensitive/novel field drives confidence down so secure-by-default holds.

**Acceptance criteria**

- [ ] agent_confidence is computed from defined inputs (ats convergence, per-answer confidences, blocker presence) and stored on the application
- [ ] Any unanswered, sensitive, or novel field caps confidence below the 0.95 auto threshold
- [ ] The computation is documented and deterministic given the same state
- [ ] evaluate_submission_route reads this value for the quality gate
- [ ] Tests show a clean all-matched case can exceed 0.95 and any sensitive/novel field forces it below
- [ ] agent_confidence is computed by the documented deterministic formula; boundary conditions are unit-tested

### EPIC-AITL-4. answer_questions node: AITL retrieval from qa_history

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Resume/Q&A embedding + pgvector retrieval layer”, “Supervisor graph wiring + run/thread linkage”

Implement answer_questions: for each screening question, retrieve the most similar qa_history entries via pgvector and, when a high-confidence match exists, answer autonomously (AITL) recording {answer, source, confidence} into application.answers. This is agent-in-the-loop resolution that keeps the human out of routine questions while feeding the honesty gate.

**Acceptance criteria**

- [ ] Each question is embedded and matched against qa_history using cosine similarity
- [ ] A high-confidence match yields an autonomous answer with source and confidence stored in application.answers
- [ ] Below-threshold or no-match questions are flagged unanswered and recorded in blockers for routing
- [ ] Per-question provenance (matched qa_history id, similarity) is captured for audit
- [ ] Tests assert confident answers are filled and ambiguous ones are left for escalation

### EPIC-AITL-5. evaluate_submission_route conditional edge (tiered-autonomy gate)

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Generator<->ATS-Critic cyclic subgraph with max-iteration cap”, “answer_questions node: AITL retrieval from qa_history”, “Honesty rule: never fabricate EEO/visa/clearance/self-ID answers”

Implement src/aeroapply/graph/routing.py evaluate_submission_route(state) as a conditional edge (not static interrupt_before) deciding per-application between auto-submit and escalate_to_human_review. Apply all gates: source gate (browser/DOM -> always escalate), quality gate (ats_score >= 0.90 AND agent_confidence >= 0.95), preference gate (auto_submit=TRUE), and honesty gate (any unseen/sensitive unmatched field -> escalate). Default to escalation when any gate fails.

**Acceptance criteria**

- [ ] Returns 'auto' only when source is Tier-A API AND ats_score>=0.90 AND agent_confidence>=0.95 AND auto_submit=TRUE AND no unseen/sensitive unmatched field
- [ ] Any DOM/browser source (workday, taleo, LinkedIn Easy Apply, custom site) always routes to escalate
- [ ] Failing any single gate routes to escalate_to_human_review (secure-by-default)
- [ ] The decision and the gate that triggered escalation are recorded as an application_event
- [ ] Unit tests enumerate each gate's pass/fail combination including the all-pass auto case

### EPIC-AITL-6. pause_and_checkpoint HITL node + resume contract

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “evaluate_submission_route conditional edge (tiered-autonomy gate)”, “LangGraph state schema + Postgres checkpointer setup”

Implement pause_and_checkpoint: on escalate, set status='needs_review', wip_status='parked', needs_human=TRUE with blockers populated, then interrupt the graph so the thread freezes at a known node. Define the resume contract (approve/edit/drop) so the UI and email webhook can wake the exact thread_id. This is the HITL boundary the operator's Inbox acts on.

**Acceptance criteria**

- [ ] On escalation the application becomes status='needs_review', wip_status='parked', needs_human=TRUE with structured blockers
- [ ] The graph interrupts and the checkpoint freezes at a deterministic resume node
- [ ] A documented resume API takes an operator decision (approve / approve-with-edits / drop) keyed by thread_id
- [ ] Approve resumes toward submit; drop sets status='user_rejected'/withdrawn and ends the run
- [ ] Tests freeze a thread, then resume it from a fresh process to submit and to drop

### EPIC-AITL-7. qa_history capture: persist operator answers for future AITL reuse

- **Epic:** `EPIC-AITL`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:graph`, `P1`
- **Depends on:** “Inbox view: review/approve/edit/drop paused applications”, “answer_questions node: AITL retrieval from qa_history”, “Resume/Q&A embedding + pgvector retrieval layer”

When the operator answers a novel or sensitive question in the Inbox, capture that question+answer (with field_type and sensitive flag), embed it, and write it to qa_history so future similar questions can be resolved by AITL. This is the learning loop that grows autonomy over time without compromising the never-fabricate rule.

**Acceptance criteria**

- [ ] Operator-provided answers in the Inbox are written to qa_history with question_text, answer_text, field_type, and sensitive flag
- [ ] The new qa_history question is embedded so it is immediately retrievable for future matching
- [ ] Sensitive answers are stored but still always re-gated to HITL on future use (never auto-filled)
- [ ] Duplicate question capture updates/links rather than creating redundant rows
- [ ] Tests confirm a captured answer is retrievable and that sensitive capture still escalates next time

---

<a id="epic-apply"></a>
## EPIC-APPLY — Apply Connectors, Credential Vault & Submission

_Build the submission layer: Tier-A API submit, Playwright submit for one DOM portal, account creation with the Fernet-encrypted domain-keyed credential vault, and the submit/track nodes that persist outcomes. Exit: a real submission to a Tier-A sandbox._

### EPIC-APPLY-1. End-to-end integration test: Tier-A sandbox submission

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:connectors`, `P0`
- **Depends on:** “submit + track nodes: persist outcome and lifecycle entry state”, “Tier-A API submission connector (Greenhouse/Lever/Ashby)”

Author an integration test for the Sprint-4 exit: an approved (or all-gates-passing) Tier-A application submits to a Greenhouse/Lever/Ashby sandbox/mock endpoint through the submit+track nodes, persisting status='submitted', submitted_at, and the submission audit event. Verifies a real submission path to a Tier-A sandbox.

**Acceptance criteria**

- [ ] A Tier-A application reaches submit and posts a well-formed payload to a sandbox/mock endpoint
- [ ] On success status becomes 'submitted', submitted_at is set, wip_status='done'
- [ ] A submission application_event captures channel and provider reference
- [ ] An auto-eligible all-gates-pass case and a HITL-approved case are both covered
- [ ] Failure handling sets status='error' and is asserted

### EPIC-APPLY-2. Fernet credential vault: encrypt/decrypt domain-keyed logins

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:security`, `P0`
- **Depends on:** “Async Postgres connection pool + DB access layer”, “Pydantic config loader for profile.yaml + .env (PII boundary)”

Implement the credential vault in src/aeroapply/db: store portal logins in portal_credentials with the password Fernet-encrypted at rest (key from AEROAPPLY_FERNET_KEY in dev, KMS-backed in prod), keyed by (user_id, company_domain). Provide get-or-create semantics, strong random password generation via secrets, and guarantees that plaintext is never logged or returned to the UI.

**Acceptance criteria**

- [ ] Passwords are Fernet-encrypted before insert and decrypted only in-memory at use time
- [ ] Vault looks up by company_domain and returns decrypted credentials, or creates a new row with a secrets-generated strong password when missing
- [ ] The Fernet key is read from AEROAPPLY_FERNET_KEY (dev) with a documented KMS path for prod; key is never committed
- [ ] Plaintext passwords never appear in logs, events, or any UI-facing payload
- [ ] Tests cover encrypt/decrypt round-trip, get-or-create, and a log-scrub assertion

### EPIC-APPLY-3. Playwright submit for one DOM portal (Tier B, HITL-gated)

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** L  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:connectors`, `P1`
- **Depends on:** “Fernet credential vault: encrypt/decrypt domain-keyed logins”, “pause_and_checkpoint HITL node + resume contract”

Implement a Playwright-driven submit for a single DOM portal (e.g., a Workday-style flow): navigate, fill the form from application artifacts, and stop at the point requiring human approval or a verification code. DOM submits are Tier B and always HITL-gated; this respects ToS and the no-anti-bot-evasion rule. Pacing is conservative.

**Acceptance criteria**

- [ ] Playwright automates navigation and form-fill for one chosen DOM portal from application data
- [ ] The flow is always HITL-gated (never auto-submits) and pauses for approval/verification before final submit
- [ ] On encountering a CAPTCHA or anti-bot block the flow escalates rather than attempting to defeat it
- [ ] Conservative pacing/anti-ban hygiene is applied per source rate_limit
- [ ] A test exercises the fill flow against a local fixture page or recorded portal

### EPIC-APPLY-4. Spike: resilient DOM extraction strategy (browser-use/Stagehand) for Workday/Taleo

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** M  ·  **Priority:** P2
- **Labels:** `type:spike`, `area:connectors`, `P2`
- **Depends on:** “Playwright submit for one DOM portal (Tier B, HITL-gated)”

Spike whether to augment raw Playwright with browser-use/Stagehand for resilient DOM interaction on fragile portals (Workday, Taleo, company sites), to reduce selector breakage on Tier-B submits. Produce a recommendation with a small proof-of-concept and cost/complexity trade-offs; this informs how far Tier-B automation is worth pushing within the HITL gate.

**Acceptance criteria**

- [ ] A short proof-of-concept drives one fragile portal step via the candidate library
- [ ] Resilience, cost, and complexity trade-offs vs. raw Playwright are documented
- [ ] A clear recommendation (adopt / adopt-selectively / defer) is recorded in an ADR or CREDENTIALS_AND_AUTOMATION.md
- [ ] Any recommendation preserves the HITL gate and no-anti-bot-evasion constraints
- [ ] Follow-up issues are filed if adoption is recommended

### EPIC-APPLY-5. Tier-A API submission connector (Greenhouse/Lever/Ashby)

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:connectors`, `P0`
- **Depends on:** “evaluate_submission_route conditional edge (tiered-autonomy gate)”, “pause_and_checkpoint HITL node + resume contract”

Implement API submit for Tier-A sources: build the structured application payload (tailored resume, cover letter, answers) and POST it to the Greenhouse/Lever/Ashby apply endpoint via httpx. This is the only path eligible for auto-submit, and only after evaluate_submission_route returns 'auto'. Persist the submission result and external reference.

**Acceptance criteria**

- [ ] Connector assembles the provider-specific payload from tailored_resume, cover_letter, and answers
- [ ] Submission posts to the correct Tier-A endpoint and captures the provider response/reference id
- [ ] Submit is invoked only when routing returned 'auto' or after explicit HITL approval
- [ ] Failures surface a structured error, set status='error', and never silently drop the application
- [ ] Tests run against a sandbox/mock endpoint asserting payload shape and result handling

### EPIC-APPLY-6. account_node: portal account creation with credential storage

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** L  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:connectors`, `P1`
- **Depends on:** “Fernet credential vault: encrypt/decrypt domain-keyed logins”, “Playwright submit for one DOM portal (Tier B, HITL-gated)”

Implement the account_node: extract the base domain from portal_url, look up portal_credentials, decrypt-and-login when found, or generate a strong password, complete signup, store a new credential row, and attach credential_id to the application. Account creation is Tier B by definition (always HITL-gated). The node also exposes the as_node='account_node' resume point for OTP injection.

**Acceptance criteria**

- [ ] Base company_domain is correctly extracted from portal_url (e.g., company.wd5.myworkdayjobs.com)
- [ ] Existing credentials are decrypted and used to log in; missing ones trigger signup with a secrets-generated password and a new portal_credentials row
- [ ] credential_id is attached to the application after account resolution
- [ ] Account creation always runs HITL-gated and pauses at a checkpoint when a verification code is required
- [ ] The node is resumable as_node='account_node' so the email webhook can inject the OTP
- [ ] Tests cover found-credential login and missing-credential signup paths with a fixture portal

### EPIC-APPLY-7. submit + track nodes: persist outcome and lifecycle entry state

- **Epic:** `EPIC-APPLY`  ·  **Sprint:** 4 (07/20–07/31)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:graph`, `P0`
- **Depends on:** “Tier-A API submission connector (Greenhouse/Lever/Ashby)”, “Playwright submit for one DOM portal (Tier B, HITL-gated)”, “account_node: portal account creation with credential storage”

Implement the submit node (dispatches to API or Playwright submit based on source) and the track node that persists the outcome: set status='submitted', submitted_at, wip_status='done', write the submission application_event, and seed the lifecycle status machine so subsequent emails can advance it. This is the closing segment of the execution graph.

**Acceptance criteria**

- [ ] submit dispatches to the API connector for Tier-A and the Playwright connector for Tier-B based on source kind/tier
- [ ] On success status becomes 'submitted', submitted_at is set, and wip_status becomes 'done'
- [ ] A submission application_event records channel, timestamp, and any provider reference
- [ ] Failures set status='error' with a blocker payload and do not mark the run done
- [ ] Tests assert correct dispatch and the persisted post-submit state for both channels

---

<a id="epic-email"></a>
## EPIC-EMAIL — Email-Event Service: Webhook OTP Injection & IMAP Lifecycle

_Build the always-on FastAPI inbound-email webhook (signature verify, multipart parse, OTP injection via aupdate_state into a paused thread) and the hourly IMAP poller (LLM classifier, status state machine, forward-to-primary). Exit: OTP auto-injected; lifecycle emails update status._

### EPIC-EMAIL-1. Email matching heuristics: link inbound mail to the right application

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:email`, `P1`
- **Depends on:** “FastAPI inbound-email webhook with provider signature verification”, “Icebox writes: persist survivors as jobs + icebox applications”

Implement robust matching that links an inbound email to the correct application using sender domain, subject/company tokens, and known thread/portal hints, setting email_event.matched_application_id. Accurate matching is what makes OTP injection target the right paused thread and lifecycle updates touch the right row.

**Acceptance criteria**

- [ ] Matcher resolves the most likely application from sender domain plus company/subject signals
- [ ] Ambiguous matches are flagged (left unmatched + surfaced) rather than guessed wrong
- [ ] matched_application_id is set on email_event for both OTP and lifecycle messages
- [ ] Matching prefers an active/paused application when multiple candidates exist
- [ ] Tests cover unambiguous match, ambiguous (no match), and multi-candidate disambiguation

### EPIC-EMAIL-2. End-to-end integration test: OTP injection + lifecycle status update

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:email`, `P0`
- **Depends on:** “OTP extraction + injection via aupdate_state into paused thread”, “Lifecycle status state machine: map classifications to application.status”, “Forward-to-primary inbox via aiosmtplib BackgroundTasks”

Author an integration test for the Sprint-5 exit: a signed inbound verification email wakes a paused account_node via aupdate_state (OTP auto-injected), and a separate signed lifecycle email advances application.status and forwards to the primary inbox. Verifies the email-event service closes the loop both synchronously (OTP) and asynchronously (lifecycle).

**Acceptance criteria**

- [ ] A signed inbound webhook with an OTP resumes a frozen account_node thread without human action
- [ ] A signed lifecycle email is classified and advances status per the state machine
- [ ] email_event rows record classification, otp (where present), and forwarded=TRUE
- [ ] Invalid-signature posts are rejected and perform no state change
- [ ] The test runs against Postgres in CI asserting both the resumed thread and the status transition

### EPIC-EMAIL-3. FastAPI inbound-email webhook with provider signature verification

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:email`, `P0`
- **Depends on:** “Async Postgres connection pool + DB access layer”, “account_node: portal account creation with credential storage”

Build services/email_webhook/app.py: a FastAPI POST /v1/webhooks/inbound-email that parses multipart form fields (await request.form(), not JSON) from Mailgun/SendGrid, verifies the provider signature before doing any work, and persists an email_event row. This is the always-on endpoint OTP injection depends on; it must reject unsigned/forged posts.

**Acceptance criteria**

- [ ] Endpoint parses inbound mail via await request.form() (multipart), not a JSON body
- [ ] Provider signature/token is verified before any processing; invalid signatures return 401/403 and do no work
- [ ] A raw email_event row (from, to, subject, body) is persisted for traceability
- [ ] Sender domain is matched to an active application to set matched_application_id when possible
- [ ] Tests cover a valid signed payload, an invalid-signature rejection, and the form-parse path
- [ ] Requests with timestamps older than 15 minutes are rejected; duplicate OTP delivery is idempotent

### EPIC-EMAIL-4. Forward-to-primary inbox via aiosmtplib BackgroundTasks

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:email`, `P1`
- **Depends on:** “IMAP poller + LLM lifecycle classifier”, “Lifecycle status state machine: map classifications to application.status”

Implement fire-and-forget forwarding: after classification, forward the full message to the operator's primary_email via SMTP using aiosmtplib, dispatched through FastAPI BackgroundTasks so the webhook/poller returns promptly. Mark email_event.forwarded=TRUE on success. The operator never loses visibility of real correspondence.

**Acceptance criteria**

- [ ] The full original message is forwarded to app_user.primary_email via aiosmtplib
- [ ] Forwarding runs as a BackgroundTask (fire-and-forget) so request/poll latency is unaffected
- [ ] email_event.forwarded is set TRUE only after a successful send; failures are logged and retried/escalated
- [ ] Forwarding does not block or fail the OTP-injection or status-update path
- [ ] Tests assert a background send is scheduled and the forwarded flag is set on success
- [ ] Forward retries 3x with exponential backoff; permanent failure creates a dead-letter Inbox item; email_event.forwarded stays FALSE until success

### EPIC-EMAIL-5. IMAP poller + LLM lifecycle classifier

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:email`, `P0`
- **Depends on:** “FastAPI inbound-email webhook with provider signature verification”, “Model-router skeleton with provider abstraction and per-node overrides”

Build the hourly IMAP poller that logs into the agent mailbox, routes each message to a fast classifier (local/Haiku via router node email.classifier) mapping it to otp | interview | questionnaire | rejection | offer | none, matches it to an application, and persists an email_event with the classification. High-volume and cheap by design.

**Acceptance criteria**

- [ ] Poller authenticates via IMAP and fetches new messages on an hourly schedule
- [ ] Each message is classified by the router's email.classifier (local/Haiku, temperature=0, structured output) into the canonical labels
- [ ] Messages are matched to an application via sender domain/headers and recorded as email_event with classification
- [ ] Already-processed messages are not reclassified (idempotent on message id/UID)
- [ ] Tests classify fixture emails into each label and assert the matched application linkage

### EPIC-EMAIL-6. Lifecycle status state machine: map classifications to application.status

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:email`, `P0`
- **Depends on:** “IMAP poller + LLM lifecycle classifier”

Implement the status state machine that advances application.status from email classifications along the canonical path (submitted -> questionnaire -> interview -> offer -> accepted/rejected) plus terminal branches, and flags high-priority items (interview/offer) for the Inbox. Transitions must be valid per the schema CHECK constraint and idempotent.

**Acceptance criteria**

- [ ] interview/questionnaire/rejection/offer classifications drive the corresponding status transition on the matched application
- [ ] Only transitions valid under the status CHECK constraint are applied; invalid jumps are rejected and logged
- [ ] High-priority transitions (interview, offer) set the Inbox flag for operator attention
- [ ] Each transition writes an application_event and is idempotent for a re-delivered email
- [ ] Tests assert each classification produces the right status and audit entry
- [ ] withdrawn is set when the operator retracts after submission (from submitted/interview)

### EPIC-EMAIL-7. OTP extraction + injection via aupdate_state into paused thread

- **Epic:** `EPIC-EMAIL`  ·  **Sprint:** 5 (08/03–08/14)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:email`, `P0`
- **Depends on:** “FastAPI inbound-email webhook with provider signature verification”, “account_node: portal account creation with credential storage”, “pause_and_checkpoint HITL node + resume contract”

In the inbound webhook, extract an OTP (\b\d{4,7}\b) from verification emails, find the paused application thread by matched sender domain, and wake it with await graph.aupdate_state(config, {"verification_code": code}, as_node="account_node"). Note the correctness fix: aupdate_state is a method on the compiled graph, not the checkpointer. The agent then types the code and proceeds unsupervised.

**Acceptance criteria**

- [ ] OTP is extracted with the canonical regex and stored on the email_event.otp field
- [ ] The correct paused thread is located via matched_application_id/thread_id
- [ ] graph.aupdate_state is called on the compiled graph (not the checkpointer) with as_node='account_node' to inject verification_code
- [ ] After injection the paused account_node resumes and continues without human action
- [ ] An application_event audits the OTP injection (without logging the code in plaintext anywhere sensitive)
- [ ] Tests simulate a verification email waking a frozen thread end-to-end

---

<a id="epic-ui"></a>
## EPIC-UI — Streamlit UI, Security/Compliance & Production Hardening

_Deliver the Streamlit Inbox/Ledger/Kanban operator UI with Promote/Drop curation, the security/compliance and audit posture, autonomy calibration, rate-limiting/anti-ban, observability, and the Railway production deployment with KMS-backed secrets. Exit: running on Railway, review-default with opt-in Tier-A auto-submit._

### EPIC-UI-1. Application event audit logging helper (append-only)

- **Epic:** `EPIC-UI`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:security`, `P1`
- **Depends on:** “Async Postgres connection pool + DB access layer”

Provide a single audit helper that writes append-only application_event rows with (event_type, actor in agent|human|system, payload) and is called from every meaningful node, scheduler action, email transition, and UI action. This is the backbone of the full-audit-log non-negotiable in PROJECT_BRIEF section 13.6.

**Acceptance criteria**

- [ ] A reusable log_event helper enforces the actor enum and writes an immutable application_event row
- [ ] Graph nodes, scheduler, email service, and UI all emit events through this helper
- [ ] Payloads never contain plaintext credentials, OTP codes, or other secrets
- [ ] Events are queryable per application in chronological order for the Ledger drill-down
- [ ] Tests assert events are written for a representative agent, human, and system action

### EPIC-UI-2. Inbox view: review/approve/edit/drop paused applications

- **Epic:** `EPIC-UI`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:feature`, `area:ui`, `P0`
- **Depends on:** “Streamlit app shell with Inbox / Ledger / Kanban navigation”, “pause_and_checkpoint HITL node + resume contract”

Build the Inbox view that lists applications in status='needs_review' with their blockers, tailored resume, cover letter, and proposed answers, and lets the operator approve, approve-with-edits, or drop — invoking the pause_and_checkpoint resume contract to wake the exact thread_id. This closes the HITL loop to a human-approved draft.

**Acceptance criteria**

- [ ] Inbox lists needs_review items showing blockers, tailored resume, cover letter, and answer provenance
- [ ] Approve resumes the thread toward submission; approve-with-edits persists operator changes before resuming
- [ ] Drop sets the application to user_rejected/withdrawn and ends the run
- [ ] Sensitive (eeo/visa/clearance) fields are presented for the human to fill and are never pre-fabricated
- [ ] Actions are audited as human-actor application_events
- [ ] An end-to-end test drives a paused app to approved via the Inbox action
- [ ] HITL resume uses the async graph API (aupdate_state/astream) and does not block the Streamlit event loop

### EPIC-UI-3. Kanban view with Promote/Drop Icebox curation

- **Epic:** `EPIC-UI`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:ui`, `P1`
- **Depends on:** “Streamlit app shell with Inbox / Ledger / Kanban navigation”, “Validate and harden v_icebox_ranked execution-priority view”

Build the Kanban board that columns applications by status/wip_status and lets the operator curate the Icebox: Promote (manual_override=TRUE, absolute +100 trump into the queue) and Drop (status='user_rejected'). This is the manual curation arm feeding the ranking view alongside automated sourcing.

**Acceptance criteria**

- [ ] Kanban renders applications grouped by pipeline stage (status/wip_status columns)
- [ ] Promote sets manual_override=TRUE so the row jumps to the top of the Python ranking (manual_override +100 trump)
- [ ] Drop sets status='user_rejected' and removes it from the icebox ranking
- [ ] Curation actions write human-actor application_events
- [ ] Promote/Drop changes are reflected in the next scheduler promotion cycle
- [ ] A test asserts Promote raises execution_priority above organic rows

### EPIC-UI-4. Ledger view: full application table with scores and audit drill-down

- **Epic:** `EPIC-UI`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P2
- **Labels:** `type:feature`, `area:ui`, `P2`
- **Depends on:** “Streamlit app shell with Inbox / Ledger / Kanban navigation”

Build the Ledger view: a filterable/sortable table of all applications showing company, title, status, wip_status, ats_score, agent_confidence, submitted_at, and a drill-down into application_event history. This is the at-a-glance lifecycle tracker that fulfills the zero-manual-data-entry goal.

**Acceptance criteria**

- [ ] Ledger lists all applications with key columns and supports filter by status and sort by score/date
- [ ] Selecting a row reveals its application_event audit timeline
- [ ] ats_score and agent_confidence render with the per-application route decision
- [ ] No credential plaintext or other secrets are ever displayed
- [ ] Renders performantly against a few hundred seeded applications

### EPIC-UI-5. Streamlit app shell with Inbox / Ledger / Kanban navigation

- **Epic:** `EPIC-UI`  ·  **Sprint:** 3 (07/06–07/17)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:ui`, `P1`
- **Depends on:** “Async Postgres connection pool + DB access layer”

Build the Streamlit application shell under src/aeroapply/ui with three views — Inbox (HITL queue), Ledger (full application table), and Kanban (pipeline board) — sharing the async DB layer and a consistent layout. This is the operator's single pane of glass; later issues fill each view with interactive behavior.

**Acceptance criteria**

- [ ] Streamlit app launches and navigates between Inbox, Ledger, and Kanban views
- [ ] Views read live data through the shared DB access layer (no plaintext credentials ever shown)
- [ ] Layout is consistent and the app handles an empty database gracefully
- [ ] Connection/session handling does not leak DB connections across reruns
- [ ] A smoke test (or documented manual check) confirms each view renders against seeded data

### EPIC-UI-6. Autonomy calibration: tune gates and confidence thresholds

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:spike`, `area:security`, `P1`
- **Depends on:** “evaluate_submission_route conditional edge (tiered-autonomy gate)”, “submit + track nodes: persist outcome and lifecycle entry state”

Calibrate the tiered-autonomy gate against real/sandbox runs: tune the ats_score (0.90) and agent_confidence (0.95) thresholds, validate that secure-by-default holds (no unsafe auto-submit), and make thresholds operator-configurable. Produce a short calibration report and lock the default review-before-submit posture with opt-in Tier-A auto-submit.

**Acceptance criteria**

- [ ] Thresholds for the quality gate are configurable and documented with their rationale
- [ ] A calibration run demonstrates that no case lacking all gates ever auto-submits
- [ ] False-auto and false-escalate rates are measured on a labeled sample and summarized
- [ ] Default posture remains review-before-submit; Tier-A auto-submit is opt-in only
- [ ] Findings and final thresholds are captured in SECURITY_COMPLIANCE.md / SPRINTS.md

### EPIC-UI-7. Observability: structured logging, run metrics, and health endpoints

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:infra`, `area:infra`, `P1`
- **Depends on:** “Always-on sourcing daemon loop with per-source pacing”, “Supervisor graph wiring + run/thread linkage”, “IMAP poller + LLM lifecycle classifier”

Add structured logging and lightweight metrics across the daemon, graph, and email service (per-cycle sourcing counts, per-application token/iteration usage, submission outcomes, email classifications), plus health/readiness endpoints for the FastAPI service. This makes the always-on system debuggable in production on Railway.

**Acceptance criteria**

- [ ] Structured logs include correlation by thread_id/application_id across subsystems
- [ ] Key metrics are emitted: jobs fetched/dropped/inserted, tailoring iterations, ats_score distribution, submissions, email classifications
- [ ] The email/webhook service exposes health and readiness endpoints
- [ ] Secrets, credentials, and OTPs are scrubbed from all logs and metrics
- [ ] A documented dashboard/queries summarize daily pipeline throughput
- [ ] operator_confirmed answers are tracked and the answer-accuracy metric query is implemented

### EPIC-UI-8. Railway deployment: co-located FastAPI engine + Postgres

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** L  ·  **Priority:** P0
- **Labels:** `type:infra`, `area:infra`, `P0`
- **Depends on:** “Forward-to-primary inbox via aiosmtplib BackgroundTasks”, “submit + track nodes: persist outcome and lifecycle entry state”, “Observability: structured logging, run metrics, and health endpoints”

Deploy AeroApply to Railway: co-locate the FastAPI email/webhook engine with Postgres+pgvector for low checkpoint latency and 24/7 inbound-webhook reception, run the Alembic migration on deploy, and run checkpointer.setup() on boot. Configure the sourcing daemon and scheduler to run in the always-on service. Exit posture: running on Railway, review-default with opt-in Tier-A auto-submit.

**Acceptance criteria**

- [ ] Railway hosts the FastAPI service and a Postgres with pgvector enabled in the same region
- [ ] alembic upgrade head runs on deploy and checkpointer.setup() runs on boot, producing the full schema + checkpoints
- [ ] The inbound-email webhook is reachable over HTTPS 24/7 and verifies provider signatures
- [ ] Sourcing daemon, scheduler, and email poller run in the deployed always-on process
- [ ] A live smoke test sources a job, tails it through HITL approval, and receives a forwarded lifecycle email in prod

### EPIC-UI-9. Rate-limiting + anti-ban pacing across connectors

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P1
- **Labels:** `type:feature`, `area:security`, `P1`
- **Depends on:** “Always-on sourcing daemon loop with per-source pacing”, “submit + track nodes: persist outcome and lifecycle entry state”

Implement centralized rate-limiting and anti-ban pacing driven by source.rate_limit: per-source request budgets, jittered delays, and conservative pacing for DOM/LinkedIn sources, with backoff on throttling. Enforces the respect-ToS-and-rate-limits non-negotiable and protects the operator from bans across both sourcing and submission.

**Acceptance criteria**

- [ ] A shared limiter enforces per-source request budgets and minimum intervals from source.rate_limit
- [ ] DOM/LinkedIn sources use conservative pacing with jitter; Tier-A APIs use their own configured limits
- [ ] Throttling/429 responses trigger exponential backoff rather than hammering
- [ ] Limiter is applied uniformly by sourcing connectors and submission connectors
- [ ] Tests verify pacing intervals and backoff behavior under simulated throttling

### EPIC-UI-10. Secrets management + KMS-backed Fernet key in production

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:infra`, `area:security`, `P0`
- **Depends on:** “Fernet credential vault: encrypt/decrypt domain-keyed logins”, “Railway deployment: co-located FastAPI engine + Postgres”

Move production secrets (DATABASE_URL, provider API keys, email provider tokens, SMTP/IMAP creds) into Railway's secret manager and back the Fernet credential-vault key with KMS rather than a raw env var. Enforce that no secret is ever committed and that inbound-webhook signature secrets are present. This finalizes the credentials-encrypted-at-rest non-negotiable for prod.

**Acceptance criteria**

- [ ] All prod secrets are injected via the secret manager; none are present in the repo or images
- [ ] The Fernet key is sourced from KMS in prod (env-key path remains for dev only)
- [ ] Key rotation procedure for the vault is documented and validated against existing ciphertext
- [ ] Webhook signature secret and provider tokens are configured and verified at boot
- [ ] A startup check fails fast and clearly if any required prod secret is missing

### EPIC-UI-11. Security/compliance review pass + secrets/PII scan in CI

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** M  ·  **Priority:** P0
- **Labels:** `type:test`, `area:security`, `P0`
- **Depends on:** “Honesty rule: never fabricate EEO/visa/clearance/self-ID answers”, “Fernet credential vault: encrypt/decrypt domain-keyed logins”, “FastAPI inbound-email webhook with provider signature verification”, “Application event audit logging helper (append-only)”

Run a consolidated security/compliance pass against the PROJECT_BRIEF section 13 non-negotiables and add a CI secrets/PII scanner to prevent real resumes, credentials, or personal data from entering git. Confirm never-fabricate enforcement, secure-by-default routing, signature verification, encryption-at-rest, and full audit coverage are all in place.

**Acceptance criteria**

- [ ] A checklist verifies each section-13 non-negotiable is enforced in code with a pointer to the implementation/test
- [ ] CI runs a secret/PII scanner that blocks commits containing keys, credentials, or resume PII
- [ ] Webhook signature verification, Fernet-at-rest, and audit logging are confirmed by passing tests
- [ ] Honesty gate (never fabricate EEO/visa/clearance) is verified end-to-end against a sensitive-field scenario
- [ ] Findings and residual risks are recorded in SECURITY_COMPLIANCE.md

### EPIC-UI-12. model_config admin surface in Streamlit

- **Epic:** `EPIC-UI`  ·  **Sprint:** 6 (08/17–08/28)  ·  **Estimate:** S  ·  **Priority:** P2
- **Labels:** `type:feature`, `area:ui`, `P2`
- **Depends on:** “Streamlit app shell with Inbox / Ledger / Kanban navigation”, “Model-router skeleton with provider abstraction and per-node overrides”

Add a small Streamlit admin panel to view and edit model_config rows (per-node provider, model_id, params, fallback) so the operator can retune routing without code changes, honoring the model-is-config-never-hard-coded principle. Edits take effect on the next node resolution.

**Acceptance criteria**

- [ ] Panel lists all model_config rows with node_name, provider, model_id, params, and fallback
- [ ] Operator can edit params (temperature, max_tokens, fast_mode) and provider/model_id and persist them
- [ ] Only current model IDs are accepted; legacy IDs are rejected with a clear message
- [ ] Changes are picked up by the router on the next resolve without a restart
- [ ] Edits are audited (who/when) and validated against the provider abstraction

---

