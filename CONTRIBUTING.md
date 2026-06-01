# Contributing to AeroApply

Single-operator project, but built with real engineering hygiene — including **build-time cross-model peer review** (one model writes, a *different* model reviews).

## Setup

```bash
uv sync --dev
docker compose -f infra/docker-compose.yml up -d
uv run pytest -q
```

Python 3.12 (managed by uv). `src/` layout; tests resolve `aeroapply` via `pythonpath = ["src"]`.

## Quality gates (must pass before merge)

1. `uv run ruff check .`  — lint + import order
2. `uv run mypy src`      — strict typing
3. `uv run pytest -q`     — unit tests
4. **Cross-model peer review** (below)

CI runs 1–3 on every PR (`.github/workflows/ci.yml`). Gate 4 is a PR-time human-initiated step.

## Build-time cross-model peer review

This is distinct from the *runtime* Generator⇄ATS-Critic loop (that's a product feature — see [`docs/TAILORING_AND_ATS.md`](docs/TAILORING_AND_ATS.md)). Here we mean: **the model that authored a change must not be the model that reviews it.**

- If **Claude Code** authored the change, request review from **Codex/GPT** or **Gemini** (and vice-versa).
- Use the `cross-review` skill / `/cross-review <model>` to run the review, or open the PR and assign the other model.
- **Routing policy** (who reviews what), configurable:
  - Security-sensitive code (credentials, webhook, submission gate, EEO/honesty paths) → review by the strongest available *different* vendor, plus a human pass.
  - Connector/DOM automation → reviewer with strong web/automation knowledge.
  - Everything else → any different-vendor reviewer.
- Reviewer must check: correctness, the **never-fabricate** guardrail, secrets/PII hygiene, and consistency with [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md).

Full policy + sequence diagram: [`docs/PEER_REVIEW.md`](docs/PEER_REVIEW.md).

## Branching & PRs

- Branch off `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- One epic/issue per PR where possible; link the backlog issue.
- Fill in `.github/pull_request_template.md` (includes the cross-model review + honesty checklist).
- Conventional-ish commits: `feat(sourcing): …`, `fix(graph): …`, `docs(adr): …`.

## Non-negotiable guardrails

- **Never** add code that fabricates answers to EEO / visa / clearance / self-ID fields. Unmatched → escalate to the human Inbox.
- **Secure-by-default:** new submission paths must route through `decide_submission` / `evaluate_submission_route`. No bypasses.
- **No secrets or real résumés/PII** in git. Real values live in `.env` and `config/profile.yaml` (both gitignored).
- **No CAPTCHA defeat / anti-bot evasion.** If a portal blocks automation, escalate — don't fight it.

## Changing a locked decision

The canonical decisions in [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) §4 are backed by ADRs in [`docs/adr/`](docs/adr/). To reverse one (e.g., swap the backend, add Celery), write a new superseding ADR — don't silently diverge.
