#!/usr/bin/env bash
# One-shot: create repo, labels, milestones+issues, and the GitHub Project board.
set -euo pipefail
OWNER="${OWNER:-kristenmartino}"
REPO="${REPO:-aeroapply}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== 1/4 repo =="     ; OWNER="$OWNER" REPO="$REPO" bash "$HERE/setup_repo.sh"
echo "== 2/4 labels =="   ; OWNER="$OWNER" REPO="$REPO" bash "$HERE/setup_labels.sh"
echo "== 3/4 issues =="   ; python3 "$HERE/create_issues.py" --owner "$OWNER" --repo "$REPO"
echo "== 4/4 project ==" ; python3 "$HERE/setup_github_project.py" --owner "$OWNER" --set-status

echo "Done. https://github.com/$OWNER/$REPO"
