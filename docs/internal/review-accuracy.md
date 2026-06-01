# AeroApply — Accuracy Review

> Reviewer: Claude Sonnet 4.6 (strict, cross-vendor). Date: 2026-05-31.
> Lens: TECHNICAL ACCURACY — wrong or misleading claims about LangGraph APIs,
> Postgres/pgvector, schema vs DATA_MODEL, model IDs, Mailgun wire format,
> Fernet internals, and connector API-vs-DOM descriptions.

---

## Summary

Six real accuracy issues were found. The most critical is a node-name mismatch in
`ARCHITECTURE.md` that would break OTP injection at runtime: the `as_node` argument
uses `"account_submit"` (the submission node) instead of `"account_node"` (the
credential/login node where the OTP pause actually occurs) — every other doc
including the canonical PROJECT_BRIEF uses `"account_node"`. A secondary issue is
that `SECURITY_COMPLIANCE.md` describes **five** independent submission gates while
the canonical PROJECT_BRIEF §6 and ARCHITECTURE.md define **four** (the quality gate
treats `ats_score` and `agent_confidence` as one combined check). Additionally,
`HITL_AITL.md` and `PRD.md` evaluate the preference gate *before* the quality gate,
reversing the order in the brief and ARCHITECTURE.md — functionally equivalent for
correctness but inconsistent and likely to confuse implementers reading multiple docs.

The remaining issues are lower severity: the `SECURITY_COMPLIANCE.md` §4 password
generator uses `secrets.token_urlsafe` (Base64, no special chars) which is inconsistent
with the correct `secrets.choice`-based implementation in `CREDENTIALS_AND_AUTOMATION.md`
§4; `CREDENTIALS_AND_AUTOMATION.md` §5 describes Fernet as "AES-128-CBC + HMAC" which
is technically accurate but omits the SHA-256 in HMAC; and the `ats_score` column's
`NUMERIC(5,2)` type is annotated in the schema as accepting "0-1 or 0-100" — an
unresolved convention ambiguity that `TAILORING_AND_ATS.md` acknowledges but doesn't
resolve.

No legacy model IDs were found. The `aupdate_state`-on-compiled-graph correctness note
is applied consistently (except for the node-name error). HNSW index syntax, vector
dimensions, and the Mailgun multipart-form-not-JSON claim are all correct.

---

## Findings

### HIGH

**1. `ARCHITECTURE.md §5` — OTP injection uses wrong node name (`as_node="account_submit"` should be `"account_node"`)**

Line 171 of `ARCHITECTURE.md` shows the OTP `aupdate_state` call with
`as_node="account_submit"`. Every other document — `PROJECT_BRIEF.md §8`,
`LIFECYCLE_AND_EMAIL.md §3`, `HITL_AITL.md §6.1`, `CREDENTIALS_AND_AUTOMATION.md §7`,
`DATA_MODEL.md`, `CONNECTORS.md §4`, `PRD.md §4.4`, `ROADMAP.md M5`, `SPRINTS.md S5`,
`UI_UX.md §4.1` — uses `as_node="account_node"`. The paused Playwright thread is parked
at `account_node` (the credential/login node), not at `account_submit` (the submission
node). Injecting into the wrong node name would either fail silently or resume at the
wrong point in the graph. Per the brief's correctness note (§8): `aupdate_state` is on
the compiled graph; the `as_node` must match the exact node name where the thread is
paused.

*Suggested fix:* Change line 171 of `ARCHITECTURE.md §5` from
`as_node="account_submit"` to `as_node="account_node"` to match the canonical name used
in every other document and the PROJECT_BRIEF.

---

### MED

**2. `SECURITY_COMPLIANCE.md §2` — Describes "five independent gates" while the canonical brief defines four**

`SECURITY_COMPLIANCE.md §2` opens with "Five independent gates must **all** pass" and
its Mermaid flowchart shows five sequential checks: Source → Quality (ats_score ≥ 0.90)
→ Confidence (agent_confidence ≥ 0.95) → Preference → Honesty. The canonical authority,
`PROJECT_BRIEF.md §6`, defines **four** gates — Source, Quality (combining both ats_score
and agent_confidence in one gate), Preference, and Honesty. `ARCHITECTURE.md §4`,
`TAILORING_AND_ATS.md §8`, and `HITL_AITL.md §3` all describe four gates. The split is
functionally equivalent but the inconsistent gate count creates confusion for implementers
and test-writers (does a test suite need four or five gate-failure scenarios?).

*Suggested fix:* Update `SECURITY_COMPLIANCE.md §2` to describe four gates consistent
with the brief, combining ats_score and agent_confidence into a single Quality gate. The
flowchart may separate them visually as sub-checks within one logical gate, but the
prose should not call them independent gates.

**3. `HITL_AITL.md §3` code and flowchart — Gate evaluation order (Preference before Quality) contradicts the brief**

The Python snippet at `HITL_AITL.md §3` evaluates gates in order: Source (1) →
Preference (2) → Quality (3) → Honesty (4). The `HITL_AITL.md §5` decision-tree
Mermaid diagram shows the same order. The canonical `PROJECT_BRIEF.md §6` lists: Source
→ Quality → Preference → Honesty. `ARCHITECTURE.md §4` code also follows the brief's
order (Source → Quality → Preference → Honesty). The inversion is not a security hole
(all gates are AND-chained), but it is misleading when the `HITL_AITL.md` code is read
as the "canonical" routing implementation and `tests/test_routing.py` is written from
it.

*Suggested fix:* Reorder the gates in `HITL_AITL.md §3` code and the §5 decision-tree
to Source → Quality → Preference → Honesty, matching `PROJECT_BRIEF.md §6` and
`ARCHITECTURE.md §4`.

**4. `PRD.md §4.3` — Gate evaluation order (Honesty before Quality+Preference) contradicts the brief**

The Python snippet at `PRD.md §4.3` evaluates: Source → Honesty → (Quality+Preference
combined via `if ats_score >= 0.90 and agent_confidence >= 0.95 and auto_submit`). The
honesty gate fires second, before the quality gate. The brief and `ARCHITECTURE.md` check
quality before honesty. More significantly, the PRD combines quality and preference into
one `if` condition, meaning failing auto_submit (preference) produces no escalation
until the entire `if` block is evaluated — which obscures the distinct gate semantics.

*Suggested fix:* Update the `PRD.md §4.3` snippet to match the canonical gate order and
keep preference as a separate guard, matching `PROJECT_BRIEF.md §6` and
`ARCHITECTURE.md §4`.

**5. `SECURITY_COMPLIANCE.md §4` — Password generator uses `secrets.token_urlsafe` (Base64, no special chars); `CREDENTIALS_AND_AUTOMATION.md §4` uses the correct `secrets.choice`-based generator**

`SECURITY_COMPLIANCE.md §4` illustrates new-account password generation as
`secrets.token_urlsafe(20)`. URL-safe Base64 output contains only alphanumeric plus
`-` and `_`. Many enterprise portals (Workday, Taleo) require at least one special
character (`!@#$%^&*`). The canonical implementation in `CREDENTIALS_AND_AUTOMATION.md
§4` correctly uses `secrets.choice(alphabet)` with a while loop enforcing complexity
requirements (lower, upper, digit, symbol). The `SECURITY_COMPLIANCE.md` version would
produce passwords that fail portal complexity policies on first signup, causing a retry
loop that looks bot-like.

*Suggested fix:* Replace the `secrets.token_urlsafe(20)` line in
`SECURITY_COMPLIANCE.md §4` with a reference to the `generate_password()` function
defined in `CREDENTIALS_AND_AUTOMATION.md §4` (or an abbreviated version of it). The
password generator needs special chars to reliably clear portal complexity requirements.

---

### LOW

**6. `CREDENTIALS_AND_AUTOMATION.md §5` — Fernet described as "AES-128-CBC + HMAC" (correct but omits SHA-256)**

Section 5 describes the ciphertext as "Fernet ciphertext (AES-128-CBC + HMAC,
authenticated, with a timestamp)." Fernet uses HMAC-**SHA256** specifically. The
omission of SHA-256 is not wrong, but in a security-compliance document describing
credential encryption, the incomplete algorithm name could mislead a reviewer or
auditor. The actual implementation (`cryptography.fernet`) uses:
`signing_key = key[:16]`, `encryption_key = key[16:]` (both 16 bytes = AES-128),
`HMAC(signing_key, SHA256)`.

*Suggested fix:* Update the description to "Fernet ciphertext (AES-128-CBC + HMAC-SHA256,
authenticated, with a timestamp)" for technical precision.

**7. `scripts/bootstrap.sql` line 167 / `TAILORING_AND_ATS.md §5` — `ats_score` column typed `NUMERIC(5,2)` with comment "0-1 or 0-100" — unresolved convention**

The `ats_score` column is `NUMERIC(5,2)` with the comment "ATS-Critic keyword coverage
(0-1 or 0-100)". `TAILORING_AND_ATS.md §5` acknowledges: "pick one project-wide and
keep the gate threshold consistent with it (this doc uses 0–1)". No doc makes the
decision. `NUMERIC(5,2)` in the 0-1 range gives only two decimal places (e.g., 0.90)
while `agent_confidence` is `NUMERIC(5,4)`. If the convention is 0-1, `NUMERIC(5,2)`
loses precision beyond two decimal places (0.906 rounds to 0.91). The gate check
(`>= 0.90`) works correctly, but the ambiguity in the schema comment is a future
maintenance hazard.

*Suggested fix:* Lock the convention to 0-1 in the `bootstrap.sql` comment and in
`TAILORING_AND_ATS.md §5`, and change the column type to `NUMERIC(5,4)` (matching
`agent_confidence`) if sub-0.01 precision is ever needed. At minimum, remove "or 0-100"
from the comment.
