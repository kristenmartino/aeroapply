# AeroApply — Completeness Review

> Reviewer: Claude Sonnet 4.6 (strict, cross-vendor). Date: 2026-05-31.
> Lens: COMPLETENESS — gaps vs the PROJECT_BRIEF.md source-of-truth and requirements for a production job-application daemon.

---

## Summary

The documentation suite is unusually thorough and self-consistent. The core mechanics (sourcing, tailoring, HITL/AITL, credential vault, email service, submission gate) are well-specified and cross-referenced. However, 14 real gaps were found across security, operational failure modes, missing acceptance criteria, and items promised in the brief but absent or incomplete in the docs and backlog. The most critical issues are: no end-to-end Fernet key rotation procedure anywhere in the docs (a credential-loss risk), no ADR documents despite the brief's repository map promising `adr/ADR-0xx-*.md` files, no backlog issues covering Ollama/local-model startup failure, no acceptance criteria for the model-unavailable fallback-exhaustion path being tested end-to-end, and missing coverage of the `withdrawn` status transition (promised in the brief's state machine but never shown as a trigger).

---

## Findings

### HIGH severity

**1. `docs/adr/` — ADR directory exists but is empty; brief promises `adr/ADR-0xx-*.md`**
The `PROJECT_BRIEF.md §14` repository map explicitly lists `docs/adr/ADR-0xx-*.md` as committed artifacts. The `adr/` directory is empty. The 10+ canonical decisions locked in the brief (LangGraph, Railway, local Docker Postgres, Fernet, Playwright, Alembic, uv/3.12, `asyncio` not Celery, Streamlit, pgvector) have no corresponding ADR. Without ADRs, future contributors lack the rationale for why decisions were made, increasing the risk of accidental reversal (e.g., a contributor who doesn't read the brief adding Supabase or Celery). The brief states these files ship with the repo.
*Suggested fix:* Author at minimum ADR-001 (LangGraph vs alternatives), ADR-002 (Railway vs Supabase), ADR-003 (pgvector vs Pinecone), ADR-004 (Fernet at rest), ADR-005 (asyncio vs Celery), capturing decision/context/consequences per a standard ADR template.

**2. `docs/CREDENTIALS_AND_AUTOMATION.md`, `docs/SECURITY_COMPLIANCE.md` — Fernet key rotation is mentioned but no concrete procedure exists**
Both docs state "rotation = decrypt-with-old, re-encrypt-with-new across portal_credentials rows" and that `MultiFernet` supports staged rotation. Neither provides a concrete runbook: no step-by-step, no script reference, no mention of what happens to paused Playwright threads mid-rotation (their decrypted credentials are in flight), no rollback path. The brief flags credential leakage as a **Critical** risk (`SECURITY_COMPLIANCE.md §9`). The backlog has `EPIC-UI-10` (secrets management) but its acceptance criteria say only "Key rotation procedure for the vault is documented and validated against existing ciphertext" — no implementation path is specified anywhere in docs or backlog issues.
*Suggested fix:* Add a dedicated subsection in `CREDENTIALS_AND_AUTOMATION.md §5` with: (a) a `MultiFernet` migration script shape, (b) how to drain active threads before rotating, (c) Railway KMS key version procedure, (d) rollback if partial-migration fails.

**3. `docs/LIFECYCLE_AND_EMAIL.md` — No handling of the `withdrawn` status transition**
The brief (`PROJECT_BRIEF.md §8`) and `DATA_MODEL.md` include `withdrawn` as a distinct terminal status alongside `user_rejected`, `closed_before_execution`, `rejected`, and `error`. `LIFECYCLE_AND_EMAIL.md §7` shows the state machine diagram but `withdrawn` has no defined trigger: nothing in the docs or backlog explains what event sets `status='withdrawn'`, which actor does it, or whether it's operator-initiated or email-initiated. `EPIC-EMAIL-6` acceptance criteria do not mention `withdrawn`. The `DATA_MODEL.md` status machine diagram similarly shows `withdrawn` leading to `[*]` with no incoming arc shown. This is an unimplemented state promised by the brief.
*Suggested fix:* Define in `LIFECYCLE_AND_EMAIL.md §7` and `DATA_MODEL.md` when `withdrawn` is set (e.g., operator withdraws from Inbox after submission, or email classifier detects a withdrawal-request reply), which actor writes it, and add it to `EPIC-EMAIL-6` or a new backlog issue.

**4. `backlog/issues.md` / `docs/MODEL_ROUTING.md` — No backlog issue or doc coverage for Ollama being unavailable at daemon start**
The brief and `SOURCING_AND_RANKING.md` treat local Ollama as the primary sourcing/extraction model ("runs on the operator's Mac"). `MODEL_ROUTING.md §7.2` shows a fallback chain from local Llama to hosted Haiku, but the daemon's startup behavior when Ollama is not running (e.g., Mac is off, Ollama service crashed) is never specified. There is no acceptance criterion in any issue that tests cold-start with Ollama absent. The sourcing daemon must be resilient (`EPIC-SRC-1` says "one source failing does not halt others" but is silent on the extraction model being unavailable).
*Suggested fix:* Add an acceptance criterion to `EPIC-SRC-1` or a new issue: "Sourcing daemon starts and continues using the Haiku fallback when Ollama is unreachable at startup; operator is notified via structured log."

---

### MEDIUM severity

**5. `docs/HITL_AITL.md §6` — Resume handshake uses sync `graph.update_state` / `graph.invoke` but the runtime is fully async**
`HITL_AITL.md §6` shows the Streamlit resume pattern as synchronous: `graph.update_state(...)` and `graph.invoke(None, config)`. The rest of the system consistently uses `graph.aupdate_state` / `graph.ainvoke`. `UI_UX.md §4.1` also uses `graph.update_state` / `graph.stream(None)` (sync versions). If the compiled graph is built with `AsyncPostgresSaver` (as specified in `ARCHITECTURE.md §5`), calling the synchronous API inside Streamlit's event loop will either block or fail depending on event-loop configuration. No doc addresses this discrepancy, and no backlog issue calls for async-safe UI bridge code.
*Suggested fix:* `HITL_AITL.md §6` and `UI_UX.md §4.1` should specify async variants (`aupdate_state`, `astream`) and note how Streamlit handles them (e.g., `asyncio.run()` wrapper, or noting that Streamlit has an `asyncio` compatibility layer). Add an acceptance criterion to `EPIC-UI-2`.

**6. `docs/SECURITY_COMPLIANCE.md` / `docs/LIFECYCLE_AND_EMAIL.md` — No replay-window enforcement for webhook timestamps is specified concretely**
`SECURITY_COMPLIANCE.md §5` says "reject stale timestamps (replay window)" as a defense-in-depth bullet. No doc specifies the window size (Mailgun recommends 15 minutes), no doc specifies what happens to the OTP if the webhook fires twice (idempotency of `aupdate_state` is not discussed), and no backlog issue (`EPIC-EMAIL-3` or `EPIC-EMAIL-7`) has an acceptance criterion for timestamp staleness rejection. A forged or replayed webhook could still inject an OTP after the primary message was processed.
*Suggested fix:* Add to `SECURITY_COMPLIANCE.md §5` and `LIFECYCLE_AND_EMAIL.md §3`: explicit replay window (e.g., 15 min), idempotency contract for `aupdate_state` on duplicate OTP, and a corresponding acceptance criterion in `EPIC-EMAIL-7`.

**7. `docs/SOURCING_AND_RANKING.md §3` / `backlog/issues.md EPIC-SRC-10` — Bouncer regex patterns are illustrative; no canonical set is locked or tested for false-positive rate**
`PROJECT_BRIEF.md §5.3` and `SOURCING_AND_RANKING.md §3` show regex patterns for seniority/industry and clearance/visa drops as examples (e.g., `junior|associate|entry-level|...`). The actual patterns live in `config/profile.yaml` under `bouncer.drop_title_regex` and `bouncer.legal_blocker_regex`. Neither the docs nor `EPIC-SRC-10` acceptance criteria specify: (a) what the canonical default patterns are in `profile.example.yaml`, (b) how false-positive drops are monitored, (c) what happens if the regex accidentally drops a legitimate "AI Product Manager" posting because the description mentions "clinical AI" or "construction tech". No acceptance criterion tests the bouncer against false positives.
*Suggested fix:* Add to `SOURCING_AND_RANKING.md §3` a note that the canonical patterns ship in `config/profile.example.yaml` (not just docs prose), and add a false-positive test case to `EPIC-SRC-10` ACs: at minimum one valid AI PM posting with innocuous mentions of excluded industries must pass the bouncer.

**8. `docs/TAILORING_AND_ATS.md §3` — `agent_confidence` computation is described in prose but no formula is specified**
`TAILORING_AND_ATS.md §8` says `agent_confidence` is "a composite folding in the Critic's `confidence`, the resume-variant match strength from §2, whether the loop passed cleanly vs. hit the cap, and the `answer_questions` node's certainty." `HITL_AITL.md §3.2` references it. `EPIC-AITL-3` says "The computation is documented and deterministic given the same state" — but no doc actually provides the formula. Without a concrete formula or weights, it cannot be verified as deterministic or calibrated. This creates a gap at `PROJECT_BRIEF.md §6` ("Quality gate: `agent_confidence ≥ 0.95`") — the gate threshold is specified but the input is not.
*Suggested fix:* Add a formula subsection to `TAILORING_AND_ATS.md §8` (or `HITL_AITL.md §3.2`): define the exact weighting/floor logic (e.g., `min(critic_confidence, match_score_normalized, loop_pass_factor, answer_confidence_floor)`) that produces a deterministic `[0,1]` value, and update `EPIC-AITL-3` ACs to test the formula.

**9. `docs/ARCHITECTURE.md §6` / `docs/SPRINTS.md Sprint 6` — Streamlit in production is mentioned but no prod deployment path for it is specified**
`ARCHITECTURE.md §6` shows a prod diagram with `PUI["Streamlit (internal)"]` co-located on Railway. `SPRINTS.md Sprint 6` and `EPIC-UI-8` mention deploying the FastAPI engine but make no explicit mention of how Streamlit is served in prod (separate Railway service? same process? what port? authentication?). The brief says the UI is a single-operator internal tool with no auth layer, but running an unauthenticated Streamlit on a public Railway URL would expose all HITL drafts and the full ledger. `SECURITY_COMPLIANCE.md` does not address UI access control at all.
*Suggested fix:* Add a note to `ARCHITECTURE.md §6` and `SPRINTS.md Sprint 6` specifying how Streamlit is secured in prod (e.g., Railway private networking, basic auth via `st.secrets`, or VPN-only access), and add one AC to `EPIC-UI-8` covering this.

**10. `docs/LIFECYCLE_AND_EMAIL.md §4` / `backlog/issues.md EPIC-EMAIL-4` — SMTP forward failure mode is underdefined**
`LIFECYCLE_AND_EMAIL.md §4` describes forwarding as "fire-and-forget via FastAPI `BackgroundTasks`" with `email_event.forwarded = TRUE` set "once queued." `EPIC-EMAIL-4` AC says "failures are logged and retried/escalated" but no doc specifies: retry count, backoff, how many times to retry before giving up, or what the operator sees if forwarding silently fails (they could miss an interview invitation). The brief's Goal 4 ("full-lifecycle tracking with zero manual data entry") depends on reliable forwarding.
*Suggested fix:* Add to `LIFECYCLE_AND_EMAIL.md §4` and `EPIC-EMAIL-4`: explicit retry policy (e.g., 3 retries with exponential backoff), dead-letter handling (flag in Inbox if forward fails after retries), and `email_event.forwarded = FALSE` remaining set until success.

**11. `docs/CONNECTORS.md §3` — `hydrate()` step that resolves LinkedIn/Indeed to underlying ATS is mentioned but has no backlog issue**
`CONNECTORS.md §3` specifies that connectors should "always try to resolve to the underlying ATS during `hydrate()`" for LinkedIn/Indeed, potentially upgrading a Tier B posting to Tier A. This is an important cost-saving and autonomy-expanding step. However, no backlog issue covers ATS resolution from aggregators. `EPIC-SRC-3` only stubs the DOM connectors; no issue covers the `hydrate()` logic or ATS-type detection from LinkedIn/Indeed payloads.
*Suggested fix:* Add a backlog issue under `EPIC-SRC` (or `EPIC-APPLY`) for "ATS resolution from aggregators: `hydrate()` detects `portal_url` pointing to Greenhouse/Lever/Ashby and rewrites `portal_type` accordingly." Sprint 4 or backlog.

---

### LOW severity

**12. `docs/PRD.md §7` — Success metrics have no measurement mechanism specified for "Answer accuracy ≥ 98%"**
`PRD.md §7` lists "Answer accuracy ≥ 98%: AITL answers later confirmed correct by operator (no edits)." No doc or backlog issue defines how this is tracked: there is no "operator confirmed no edits" flag on `application.answers`, no `qa_history` feedback loop for confirmed-correct answers (only for "operator typed a new answer"), and no reporting query or dashboard. `EPIC-AITL-7` captures answers but does not track post-submission confirmation.
*Suggested fix:* Add a boolean `operator_confirmed` column or an `application_event` event type to `application.answers`, and add a metric query to the observability issue `EPIC-UI-7`.

**13. `docs/ROADMAP.md` / `docs/SPRINTS.md` — No acceptance criterion or test for the `model_unavailable` fallback-exhaustion escalation path**
`MODEL_ROUTING.md §7.2` specifies that when the entire fallback chain fails, the node sets `needs_human=TRUE` with a `model_unavailable` blocker. No backlog issue (including `EPIC-FND-6`) has an acceptance criterion that tests this end-to-end: a node whose chain is fully exhausted must park the application rather than crash or silently fail. Given this is a daemon running unattended, a silent crash here means a job is stuck with no human notification.
*Suggested fix:* Add to `EPIC-FND-6` or a Sprint-6 issue: "When the entire fallback chain is exhausted, the node parks the application to `needs_review` / `needs_human=TRUE` with `blockers.model_unavailable`; a test verifies the thread appears in the Inbox."

**14. `docs/DATA_MODEL.md §3` / `docs/ARCHITECTURE.md §5` — No mention of `application.submitted_at` column in DATA_MODEL.md**
`ARCHITECTURE.md §2` (node inventory for `track`) and `SPRINTS.md Sprint 4` both reference `submitted_at = now()` as a field written after successful submission. `PRD.md §7` uses it in the "Time-to-apply" metric. However, `DATA_MODEL.md §3` (the `application` table description) does not list `submitted_at` as a column, creating a doc-schema gap. If `bootstrap.sql` has it (likely, given all other docs reference it), `DATA_MODEL.md` is incomplete.
*Suggested fix:* Add `submitted_at TIMESTAMPTZ` to the `application` table column list in `DATA_MODEL.md §3` and verify it appears in `scripts/bootstrap.sql`.

---

## Gap matrix vs. brief non-negotiables

| Brief non-negotiable (§13) | Coverage | Gap |
|---|---|---|
| Never fabricate | Fully covered — honesty gate, `qa_history.sensitive`, multiple docs | None |
| Secure-by-default | Fully covered | None |
| No CAPTCHA defeat | Fully covered | None |
| Respect ToS & rate limits | Covered | Minor: aggregator hydrate() has no backlog issue (finding #11) |
| Credentials encrypted at rest | Covered; rotation is thin | Finding #2 (no rotation runbook) |
| Full audit log | Covered | Minor: answer accuracy metric has no tracking mechanism (finding #12) |
| Private repo / no PII in git | Fully covered | None |

## Items in brief promised but absent in docs/backlog

| Brief promise | Status |
|---|---|
| `docs/adr/ADR-0xx-*.md` files (§14 repo map) | **Missing** (finding #1) |
| `withdrawn` status trigger (§8 state machine) | **Undefined** (finding #3) |
| Key rotation procedure (§7, §13.5) | **Incomplete** (finding #2) |
| `agent_confidence` formula (§6 quality gate) | **Unspecified** (finding #8) |
| ATS resolution from aggregators during `hydrate()` (§5 diagram, CONNECTORS.md §3) | **No backlog issue** (finding #11) |
