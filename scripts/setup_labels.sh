#!/usr/bin/env bash
# Create the AeroApply label taxonomy (idempotent via --force).
set -euo pipefail
OWNER="${OWNER:-kristenmartino}"
REPO="${REPO:-aeroapply}"
R="$OWNER/$REPO"

mk() { gh label create "$1" --color "$2" --description "$3" --repo "$R" --force; }

# type:*
mk "type:feature" "1d76db" "Product feature"
mk "type:infra"   "0e8a16" "Infra / tooling / CI"
mk "type:test"    "fbca04" "Tests / QA"
mk "type:docs"    "5319e7" "Documentation"
mk "type:spike"   "c5def5" "Research / spike"
mk "type:bug"     "d73a4a" "Bug"
mk "type:epic"    "3e1f92" "Epic tracking issue"

# area:*
for a in sourcing graph ui email connectors security models infra data; do
  mk "area:$a" "bfdadc" "Area: $a"
done

# priority
mk "P0" "b60205" "Critical / must-have for the sprint"
mk "P1" "d93f0b" "High"
mk "P2" "fbca04" "Normal"

echo "Labels ready on $R (epic:* labels are created by create_issues.py)."
