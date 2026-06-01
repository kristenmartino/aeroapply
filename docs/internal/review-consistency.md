# AeroApply — Cross-Document Consistency Review

> Reviewer: Claude Sonnet 4.6 (strict, different model than authors)
> Date: 2026-05-31
> Scope: All docs in `docs/` + `backlog/` vs `PROJECT_BRIEF.md` (source of truth)

---

## Summary

Seven real, actionable inconsistencies found across the documentation suite. No fabricated or low-confidence findings included. Documents are generally well-aligned; the issues cluster around (1) the OTP injection `as_node` value, (2) divergent gate ordering and count in `evaluate_submission_route`, (3) a state machine diagram discrepancy between `DATA_MODEL.md` and `LIFECYCLE_AND_EMAIL.md`, and (4) an ambiguous `ats_score` column scale note.

---

## Findings

### F1 — HIGH: `ARCHITECTURE.md` uses `as_node="account_submit"` for OTP injection; every other doc (and PROJECT_BRIEF §8) uses `as_node="account_node"`

**File:** `docs/ARCHITECTURE.md` §5, line ~171
**Issue:** The OTP injection call reads:
```
await graph.aupdate_state(config, {"verification_code": code}, as_node="account_submit")
```
`PROJECT_BRIEF.md` §8 explicitly says `as_node="account_node"`. `LIFECYCLE_AND_EMAIL.md`, `CREDENTIALS_AND_AUTOMATION.md`, `HITL_AITL.md` §6.1, `DATA_MODEL.md`, `PRD.md` §4.4, and `SPRINTS.md` §S5 all use `account_node`. `account_submit` is the node that *files* the application; `account_node` is the node that handles credential lookup and OTP wait. Using the wrong `as_node` value would inject the code at the wrong graph node and fail to resume the paused thread.
**Suggested fix:** Change `as_node="account_submit"` to `as_node="account_node"` in `ARCHITECTURE.md` §5.

---

### F2 — HIGH: `ARCHITECTURE.md` names the route return values `"account_submit"` / `"pause_and_checkpoint"` while all other docs (including PROJECT_BRIEF §6 and the canonical `routing.py` in HITL_AITL.md) use `"auto_submit"` / `"escalate_to_human_review"`

**File:** `docs/ARCHITECTURE.md` §4, lines ~127–140 (code block) and §2 state diagram
**Issue:** `ARCHITECTURE.md`'s code block declares:
```python
def evaluate_submission_route(state: AppState) -> Literal["account_submit", "pause_and_checkpoint"]:
    ...
    return "pause_and_checkpoint"
    ...
    return "account_submit"
```
`PROJECT_BRIEF.md` §6 specifies `escalate_to_human_review`. `HITL_AITL.md` §3 (canonical), `CONNECTORS.md` §6, `TAILORING_AND_ATS.md` §8, and `SECURITY_COMPLIANCE.md` all use `"auto_submit"` / `"escalate_to_human_review"`. The `ARCHITECTURE.md` state diagram also wires edges to `account_submit` (a node name) rather than using a semantic route label, conflating the route label with the downstream node name.
**Suggested fix:** Change `ARCHITECTURE.md` §4 code block to return `"auto_submit"` / `"escalate_to_human_review"` (matching the brief and all other docs), and update the §2 state diagram edge label from `account_submit` to `auto_submit`.

---

### F3 — HIGH: `evaluate_submission_route` gate ordering is inconsistent across docs

**Files:** `docs/HITL_AITL.md` §3 (canonical code + §5.1 flowchart), `docs/ARCHITECTURE.md` §4, `docs/SECURITY_COMPLIANCE.md` §2

**Issue:** The gate evaluation order differs:

| Document | Order |
|---|---|
| `PROJECT_BRIEF.md` §6 | Source → Quality → Preference → Honesty |
| `ARCHITECTURE.md` §4 (code) | Source → Quality → Preference → Honesty |
| `HITL_AITL.md` §3 (canonical code) | Source → Preference → Quality → Honesty |
| `HITL_AITL.md` §5.1 (flowchart) | Source → Preference → Quality → Honesty |
| `SECURITY_COMPLIANCE.md` §2 (flowchart) | Source → Quality(ats) → Confidence → Preference → Honesty (**5 steps**, splitting Quality into two) |

`HITL_AITL.md` is supposed to be the canonical routing reference (`src/aeroapply/graph/routing.py`) but its order (Source → Preference → Quality) disagrees with `PROJECT_BRIEF.md` §6 (Source → Quality → Preference). `SECURITY_COMPLIANCE.md` further splits the single Quality gate into two separate `ats_score` and `agent_confidence` checks, inflating the count to five gates — inconsistent with every other doc which treats these as one combined Quality gate (four total gates).

**Suggested fix:** Align all three files to the `PROJECT_BRIEF.md` §6 order: **Source → Quality → Preference → Honesty** (four gates). Update `HITL_AITL.md` §3 code (swap Gates 2 and 3), `HITL_AITL.md` §5.1 flowchart (swap G2/G3 labels), and `SECURITY_COMPLIANCE.md` §2 flowchart (merge the split Quality + Confidence nodes into one "Quality gate: ats_score ≥ 0.90 AND agent_confidence ≥ 0.95" node, giving four total).

---

### F4 — MED: `DATA_MODEL.md` and `LIFECYCLE_AND_EMAIL.md` state machine diagrams show conflicting `error` and `user_rejected` transition sources

**Files:** `docs/DATA_MODEL.md` §State machines, `docs/LIFECYCLE_AND_EMAIL.md` §7

**Issue:**

| Transition | `DATA_MODEL.md` | `LIFECYCLE_AND_EMAIL.md` |
|---|---|---|
| Source of `error` | `drafting --> error` | `submitting --> error` |
| Source of `user_rejected` | `sourced --> user_rejected` | `needs_review --> user_rejected` |

`PROJECT_BRIEF.md` §8 canonical text lists `error` as a terminal but does not pin which state it transitions from; the `DATA_MODEL.md` diagram (considered the closer schema document) shows `drafting --> error`. `LIFECYCLE_AND_EMAIL.md` shows `submitting --> error` instead. Similarly, the `user_rejected` source differs: `DATA_MODEL.md` shows only `sourced --> user_rejected` (Kanban/Icebox drop), while `LIFECYCLE_AND_EMAIL.md` shows `needs_review --> user_rejected` (Inbox drop). Both transitions are arguably valid use-cases but neither diagram is complete, and they contradict each other.

**Suggested fix:** Align both diagrams to show `error` can arise from both `drafting` and `submitting` (both are real failure points). Add `needs_review --> user_rejected` to `DATA_MODEL.md`'s diagram since the Inbox drop is a documented operator action. Optionally add `sourced --> user_rejected` to `LIFECYCLE_AND_EMAIL.md` for completeness, or add a prose note that `user_rejected` is reachable from any non-terminal state.

---

### F5 — MED: `TAILORING_AND_ATS.md` §5 leaves `ats_score` column convention ambiguous (0–1 vs 0–100)

**File:** `docs/TAILORING_AND_ATS.md` §5, last paragraph

**Issue:** The doc explicitly states:
> "Note `ats_score` here is the 0–1 form; the `application.ats_score` column is `NUMERIC(5,2)` and accepts either the 0–1 or 0–100 convention — **pick one project-wide** and keep the gate threshold consistent with it."

This is not a resolved decision — it is an open note deferred to the implementer. The gate threshold `0.90` is used throughout all docs in 0–1 form. `NUMERIC(5,2)` at scale 0–1 has two decimal places of precision (0.90, 0.91 etc.), which is adequate. All other references treat the threshold and values as 0–1. The column definition and the gate must use the same scale, and the "pick one" note should be resolved in the doc rather than left open.

**Suggested fix:** Remove the hedged "accepts either" language from `TAILORING_AND_ATS.md` §5 and replace with a firm statement: the project uses the **0–1 scale** project-wide for `ats_score` (consistent with `autonomy.min_ats_score: 0.90` in `profile.yaml` and all gate comparisons throughout the docs).

---

### F6 — MED: `DATA_MODEL.md` state machine diagram omits the `withdrawn` transition source

**File:** `docs/DATA_MODEL.md` §State machines

**Issue:** `withdrawn` appears as a terminal in `[*]` but no state has an arrow to it in the `stateDiagram-v2` block. The `LIFECYCLE_AND_EMAIL.md` diagram similarly has `withdrawn --> [*]` with no source state drawn. `PROJECT_BRIEF.md` §8 lists it as a terminal/branch token. In a real system, `withdrawn` must be reachable from some state (logically `submitted`, `questionnaire`, or `interview` — the operator pulls a submitted application). Without a source arrow the state is unreachable in the diagram and the CHECK constraint in `bootstrap.sql` will allow an update with no documented entry path.

**Suggested fix:** Add a source transition to `withdrawn` in `DATA_MODEL.md`'s diagram. Based on the system's intent, `submitted --> withdrawn` and/or `interview --> withdrawn` are the natural entry points (operator retracts an application after it was filed). Mirror the fix in `LIFECYCLE_AND_EMAIL.md` §7.

---

### F7 — LOW: `PRD.md` §4.3 gate code skips the explicit Preference gate check as a standalone step

**File:** `docs/PRD.md` §4.3

**Issue:** The illustrative code in `PRD.md` §4.3 combines the quality and preference checks in one block:
```python
if (state["ats_score"] >= 0.90
        and state["agent_confidence"] >= 0.95
        and state["auto_submit"]):
    return "auto_submit"
```
This puts the Honesty check *before* the Quality+Preference block, making the gate order Source → Honesty → (Quality + Preference combined). The brief and canonical docs order it Source → Quality → Preference → Honesty with preference as an independent step. While the final behavior is equivalent (all conditions must pass), the code structure misrepresents the gate order and the Preference gate is not given its own early-exit path. An implementer reading this as the routing template would write a function that tests honesty before preference, which is less efficient (honesty is the most expensive check).

**Suggested fix:** Update the `PRD.md` §4.3 code snippet to match the four-gate order in `PROJECT_BRIEF.md` §6: Source gate, then Quality gate, then Preference gate (early-exit on `auto_submit = FALSE`), then Honesty gate.

---

## Non-issues (verified consistent)

- **Model IDs** (`claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5`): uniform across all docs; no legacy `claude-3-*` IDs found.
- **Autonomy gate thresholds** (`ats_score ≥ 0.90`, `agent_confidence ≥ 0.95`): consistent in all docs.
- **Scoring weights** (title 35%, location 25%, recency 20%, competition 10%, urgency 10%): match across PROJECT_BRIEF, DATA_MODEL, SOURCING_AND_RANKING, and ARCHITECTURE.
- **Docker dev → Railway prod** (not Supabase): stated consistently in PROJECT_BRIEF, ARCHITECTURE, DATA_MODEL, LIFECYCLE_AND_EMAIL, PRD, SOURCING_AND_RANKING, SECURITY_COMPLIANCE.
- **`wip_status` tokens** (`icebox | queued | active | parked | done`): consistent everywhere.
- **Fernet key env var** (`AEROAPPLY_FERNET_KEY`): consistent.
- **`aupdate_state` on compiled graph, not checkpointer**: correctly stated in PROJECT_BRIEF §8 and all docs except the `as_node` value issue in F1.
- **Mailgun multipart form parsing** (`await request.form()`): consistent across all relevant docs.
- **Tier A sources** (Greenhouse, Lever, Ashby): consistent everywhere.
- **Tier B sources** (Workday, Taleo, LinkedIn, custom): consistent everywhere.
- **`thread_id == application.id`**: consistent across all docs.
- **Sprint dates** (06/08–08/28, 6 × 2-week sprints): consistent across ROADMAP, SPRINTS, backlog/epics.md.
