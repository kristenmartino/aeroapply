# ADR-008: Candidate-side submission is hosted-form automation; v1 autonomy ceiling is review-and-approve

- **Status:** Accepted
- **Date:** 2026-06-09
- **Deciders:** Architecture, Security, Product
- **Related:** `docs/PROJECT_BRIEF.md` §4, §6; `docs/CONNECTORS.md`; `docs/ROADMAP.md` M4/M6; amends ADR-007 in part

## Context

The original design (Brief §6, CONNECTORS.md §2–§3, ADR-007) defined **Tier A** as
"clean-API ATS (Greenhouse, Lever, Ashby)" and made it the only auto-submit-eligible
class, on the premise that filing an application there is "a single typed POST."

That premise is wrong for a **candidate-side** tool. Verified June 2026:

- **Greenhouse** — the Job Board API application endpoint
  (`POST /v1/boards/{token}/jobs/{id}`) authenticates with a Job Board API key from
  the **company's** API Credentials page; the docs explicitly warn the key is a
  secret that must be proxied by the company's own servers.
  ([developers.greenhouse.io/job-board](https://developers.greenhouse.io/job-board.html),
  [application endpoint spec](https://github.com/grnhse/greenhouse-api-docs/blob/master/source/includes/job-board/_applications.md))
- **Lever** — the postings apply `POST` requires an API key "a Super Admin of your
  account can generate," intended for companies building their own job sites.
  ([lever/postings-api](https://github.com/lever/postings-api),
  [Lever API credentials](https://help.lever.co/hc/en-us/articles/20087297592477-Generating-and-using-API-credentials))
- **Ashby** — same model: the application-submission API is keyed to the hiring
  organization.

These APIs exist so employers can embed their own boards. A job seeker cannot obtain
the keys, ever. The *read* side (public board/postings JSON) remains fully available
and unaffected — sourcing is fine; **applying via API is not a thing**.

The actual candidate-side channel for Greenhouse/Lever/Ashby is their **hosted
application form** — i.e., browser automation, which our own taxonomy classifies as
Tier B (always human-gated). Followed literally, the old design could never
legitimately auto-submit anywhere, and M4's exit criterion ("submit to a Tier-A
sandbox via API") was unreachable without an employer sandbox account, which proves
nothing about applying to real companies.

## Decision

1. **All v1 submissions go through the hosted application form via Playwright** —
   including Greenhouse, Lever, and Ashby. There is no API submit path; the
   `ApplyConnector.submit()` contract stays, but every implementation is a browser
   walk.
2. **Tier semantics are re-based on form predictability, not API availability:**
   - **Tier A — hosted ATS forms** (Greenhouse, Lever, Ashby): stable, structured
     markup, usually no login or account wall. Highest assist quality, cheapest to
     maintain.
   - **Tier B — login/multi-step/aggregator portals** (Workday, Taleo, company
     sites, LinkedIn, Indeed-hosted): accounts, OTP walls, fragile wizards.
   - **Tier C — blocked**: anything requiring fabrication or ToS-prohibited
     automation.
3. **v1's autonomy ceiling is review-and-approve.** Every submission requires
   explicit operator approval in the Inbox. `autonomy.auto_submit_sources` ships as
   `[]` (block-all); the gate machinery (`evaluate_submission_route`,
   `decide_submission`) is retained unchanged so posture stays config-driven, but no
   source is auto-submit-eligible in v1.
4. **Unattended auto-submit is deferred post-v1** and may be revisited only if a
   sanctioned candidate-side channel emerges (e.g., an ATS opens a candidate API).
   It will never be pursued via CAPTCHA defeat, anti-bot evasion, or impersonating an
   employer integration — those remain non-negotiables (Brief §13).

## Alternatives considered

- **Employer-keyed apply APIs** — unobtainable by design; dead end.
- **Reverse-engineering the hosted form's unauthenticated POST** — brittle,
  ToS-gray, increasingly CAPTCHA-protected, and indistinguishable from the browser
  path in risk while losing its observability. Rejected.
- **Aggregator partner APIs (e.g., Indeed ATS sync)** — also employer-side
  integrations; not available to candidates.
- **Keep the claim and discover this in Sprint 4** — sets M4 and M6 up to fail at
  the most expensive possible moment. Rejected; hence this ADR now.

## Consequences

- **M4 re-scoped:** build the Playwright hosted-form submitter for Greenhouse first
  (Lever/Ashby next); exit criterion becomes an **operator-approved submission filed
  end-to-end through a hosted form**, persisted with `status='submitted'` and an
  `application_event` audit row.
- **M6 re-scoped:** the prod demo is the **review-default daemon live on Railway**;
  "opt-in Tier-A auto-submit live" is dropped from v1 exit criteria.
- **Still needed, unchanged:** credential vault, account creation, and OTP injection
  (Tier-B portals require them); the submission gate and audit trail; the honesty
  gate. Tier-A hosted forms usually need none of that, which is exactly why they
  remain the best-assist class.
- **Docs:** PROJECT_BRIEF §6, CONNECTORS.md, ROADMAP M4/M6, SPRINTS S4/S6, README,
  and `config/profile.example.yaml` updated with this ADR; remaining doc sweep is
  tracked under #76. ADR-007's Tier-A definition is amended by this ADR.
- **Honest framing:** the product automates the drafting 90% and *assists* the
  submission; it does not (in v1) submit unattended. This is the claim the repo can
  actually keep.
