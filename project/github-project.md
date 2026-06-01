# GitHub Project (v2) — AeroApply

The delivery board. Created + populated by `scripts/setup_github_project.py` (run after `scripts/create_issues.py`).

## Project
- **Name:** AeroApply
- **Owner:** `kristenmartino` (user project)
- **Source of truth for items:** GitHub issues created from `backlog/issues.json`.

## Custom fields

| Field | Type | Options |
|---|---|---|
| **Status** | single-select | `Todo`, `In Progress`, `In Review`, `Blocked`, `Done` |
| **Sprint** | single-select | `Sprint 1` … `Sprint 6` (also mirrored as GitHub milestones) |
| **Area** | single-select | `sourcing`, `graph`, `ui`, `email`, `connectors`, `security`, `models`, `infra`, `data` |
| **Priority** | single-select | `P0`, `P1`, `P2` |
| **Estimate** | single-select | `S`, `M`, `L` (or points `1/2/3/5/8`) |
| **Epic** | text | epic key, e.g. `EPIC-SRC-1` |

Field values are derived from each issue's labels (`area:*`, `P*`, `epic:*`) and its milestone (`Sprint N`).

## Views
1. **Board** — group by `Status` (default kanban).
2. **By Sprint** — group by `Sprint`, the burn-down/working view.
3. **By Area** — group by `Area`, for focused subsystem work.
4. **Table** — all fields, sortable by `Priority`.

## Label → field mapping
- `type:feature|infra|test|docs|spike|bug` → issue type (lives as a label; surfaced in Table).
- `area:<x>` → **Area**.
- `P0|P1|P2` → **Priority**.
- `epic:<KEY>` → **Epic** + groups child issues under their epic tracking issue.
- milestone `Sprint N` → **Sprint**.

## Setup order
```bash
OWNER=kristenmartino REPO=aeroapply scripts/setup_all.sh
# == setup_repo.sh -> setup_labels.sh -> create_issues.py -> setup_github_project.py
```
