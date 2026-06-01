#!/usr/bin/env bash
# Initialize git, create the public-safe GitHub repo, and push.
set -euo pipefail
OWNER="${OWNER:-kristenmartino}"
REPO="${REPO:-aeroapply}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .git ]; then
  git init -b main
fi

git add -A
if ! git diff --cached --quiet; then
  git commit -m "Initial commit: AeroApply planning, schema, and skeleton

Canonical brief, 15 design docs + ADRs, data model, model router,
sourcing bouncer, submission gate, email webhook, backlog, and infra.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
else
  echo "nothing to commit"
fi

if ! gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  gh repo create "$OWNER/$REPO" \
    --public \
    --source=. \
    --remote=origin \
    --description "Autonomous, human-in-the-loop job-application daemon (LangGraph + Postgres/pgvector)"
fi

git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
git push -u origin main
echo "Repo ready: https://github.com/$OWNER/$REPO"
