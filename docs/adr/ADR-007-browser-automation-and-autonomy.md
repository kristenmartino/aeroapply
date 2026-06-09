# ADR-007: Browser automation (Playwright + optional browser-use) and tiered autonomy

- **Status:** Accepted — **amended in part by ADR-008** (the Tier-A "clean-API auto-submit" class below was based on apply APIs that are employer-keyed and unobtainable candidate-side; tiers are re-based on hosted-form predictability and v1's ceiling is review-and-approve)
- **Date:** 2026-05-31
- **Deciders:** Architecture, Security, Product
- **Related:** `docs/PROJECT_BRIEF.md` §4, §6, §7, §13; ADR-004; ADR-008

## Context

Many portals (Workday, Taleo, LinkedIn Easy Apply, custom company sites) have no
clean API and must be driven through the browser. Browser automation is fragile and
**ban-prone**, and applications touch legal/EEO/visa/clearance fields where a wrong
answer is unacceptable. We need a default posture that is safe, never dishonest, and
never adversarial toward anti-bot systems.

## Decision

We will use **Playwright** as the browser driver, with **`browser-use`/Stagehand
optional** for resilient, LLM-assisted DOM interaction on brittle portals. Autonomy
is **tiered and secure-by-default**, decided per-application by a runtime conditional
edge (`evaluate_submission_route`):

- **Tier A (auto-submit eligible):** clean-API ATS (Greenhouse, Lever, Ashby).
- **Tier B (HITL required):** all DOM/browser portals + account creation.
- **Tier C (blocked):** anything requiring fabrication or ToS-prohibited automation.

Auto-submit fires only when **all** gates pass (source, `ats_score ≥ 0.90`,
`agent_confidence ≥ 0.95`, `auto_submit = TRUE`, honesty). **We do not defeat
CAPTCHAs or evade anti-bot systems** — on block, escalate.

## Alternatives considered

- **Pure-API only (skip browser portals)** — safest, but abandons most of the job
  market (Workday/Taleo dominate); unacceptable coverage loss.
- **Full autonomy on browser portals** — maximizes throughput but invites bans and
  risks dishonest field answers; violates the secure-by-default mandate.
- **CAPTCHA-solving / stealth evasion** — explicitly rejected: ToS-violating and
  against project non-negotiables.

## Consequences

- **Positive:** broad portal coverage with a safe default; runtime per-application
  routing; legal/identity fields always human-verified; reputation and accounts
  protected from bans.
- **Negative:** Tier B throughput is gated by operator attention; DOM automation
  needs ongoing maintenance as portals change.
- **Follow-ups:** a source may graduate to Tier A only with sustained high-confidence
  evidence; pace conservatively and respect each portal's ToS and rate limits.
