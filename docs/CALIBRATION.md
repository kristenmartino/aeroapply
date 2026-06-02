# Calibration — Empirically Tuning Scoring Weights & Autonomy Thresholds

How AeroApply moves the two knob-sets from hand-picked defaults to data-driven values.
Operationalizes backlog issue **#58 (Autonomy calibration)**. Source of truth for the
defaults: `config/profile.yaml` (`ranking_weights`, `autonomy`) and `Settings`.

## The two knob-sets

| Knob-set | Where it lives today | What it decides | Default |
|---|---|---|---|
| **Scoring weights** | `v_icebox_ranked` view + `profile.ranking_weights` | *Which* Icebox jobs get worked first | title .35 / location .25 / recency .20 / competition .10 / urgency .10 |
| **Autonomy thresholds** | `Settings.min_ats_score`, `min_agent_confidence`, `autonomy.*` | *When* an app auto-submits vs escalates | ats ≥ 0.90 **and** confidence ≥ 0.95, Tier-A sources only |

They optimize different objectives and must be tuned **separately**:
- Weights → a **ranking** problem (maximize downstream reward per worked job).
- Thresholds → a **classification / decision** problem under **asymmetric loss** (a bad auto-submit costs far more than a missed automation).

## Why empirical (and why carefully)
- **Asymmetric loss.** An incorrect auto-submit can mean an inaccurate application to a real employer, a fabricated-looking answer, or an account flag. Treat one bad auto-submit as worth *N* missed automations (start `N ≈ 20`). Secure-by-default is the prior; data only *earns* more autonomy.
- **Survivorship bias.** You only observe outcomes (interview/offer) for jobs you actually applied to — never for the ones the ranker buried. Tuning weights only on worked jobs over-fits the current ranker.
- **Drift & seasonality.** The job market, ATS layouts, and the models all move. Calibration is continuous, time-validated, and reversible.

## Data substrate — log this from day one
Most already exists in the schema; the gaps are explicit below.

Per **application**, persist the *decomposed* score and decision so they can be replayed:
- `score_components` JSON: the five sub-scores (title/location/recency/competition/urgency) **at ranking time** — now persisted to `application.ranking_debug JSONB` (the `components` + `execution_priority` + `weights` snapshot written by `scheduler.snapshot_ranking_debug`, e.g. `aeroapply rank --persist`).
- `ats_score`, `agent_confidence` (already columns), the route (`auto_submit` / `escalate_to_human_review`), and the gate `reasons` (from `decide_submission`).

Per **operator review** (the ground-truth label for thresholds), emit `application_event` rows:
- `event_type='human_approved_unchanged'` — operator accepted the draft as-is ⇒ the gate *should* have auto-approved.
- `event_type='human_edited'` (payload = diff size) — operator changed it ⇒ gate *should* have held.
- `event_type='human_rejected'` / `'user_rejected'` — hard negative.

> **Implemented (curation).** Kanban **Promote**/**Drop** (#83) emit `human` `application_event` rows whose payload carries `{action, label, ranking_debug, ranking_debug_present}` — pairing each curation label (`manual_override` for Promote, `hard_negative` for Drop) with the ranker features. The Kanban **auto-snapshots the card's `ranking_debug` before each action** (`ui.board.snapshot_row`, using the values already on screen), so curation events are paired **by default** (`ranking_debug_present: true`). `ranking_debug_present` is `false` only for direct/programmatic `repo.promote`/`repo.drop` calls made without a prior snapshot. The draft-review `human_approved_unchanged` / `human_edited` events still await the Inbox.

Per **outcome** (the reward signal for weights), already captured via `status` transitions + `application_event`: `submitted → questionnaire → interview → offer → accepted | rejected`. Derive labels: `responded` (any employer reply), `interview`, `offer`.

> **Gap to close (Sprint 3/6):** the `ranking_debug` JSON write now lands via `scheduler.snapshot_ranking_debug` (`aeroapply rank --persist`); what remains is the three `human_*` event types on the Inbox approve/edit/reject actions (EPIC-UI). Without those labels the analysis below has no ground truth.

## Phase 0 — Shadow / cold-start (secure-by-default)
Run **review-default, auto-submit OFF** (`DEFAULT_MODE=review`). Every draft is human-reviewed, which *manufactures the labels*: each review is a data point on "would the gate have been right to auto-submit this?" Collect **≥150–200 reviewed applications** before trusting any threshold, and a few weeks of outcomes before touching weights. Do not skip this — it is the only unbiased window.

## Phase 1 — Threshold calibration (autonomy)
1. **Check model calibration first.** Is `agent_confidence` honest? Bin predictions and plot predicted-confidence vs observed P(approved-unchanged) — compute **ECE / Brier score**. If miscalibrated (it usually is), fit a **Platt/isotonic** recalibrator and threshold the *recalibrated* score. A 0.95 cut on an uncalibrated score is meaningless.
2. **Build the precision/automation tradeoff.** Positive label = `human_approved_unchanged`. For each candidate `(ats_t, conf_t)`:
   - **auto-submit precision** = of apps that *would* auto-submit, fraction the operator approved unchanged.
   - **automation rate** = fraction of eligible apps cleared for auto.
   Sweep the grid; plot the precision–automation frontier.
3. **Pick by expected cost, not accuracy.** Choose the **lowest** thresholds that keep precision ≥ target (start **≥ 0.98**, i.e. ≤ 2% bad auto-submits) — equivalently, minimize `cost = N · false_auto + missed_auto`.
4. **Per-source thresholds.** Greenhouse/Lever (clean API) tolerate lower cuts than a custom DOM portal. Keep DOM/LinkedIn at Tier-B (human-gated) regardless — thresholds only relax *within* Tier A.
5. **Honesty gate is non-negotiable.** EEO/visa/clearance/novel-question escalation is never tuned away; it sits outside this optimization.

## Phase 2 — Weight tuning (ranking)
Objective: maximize a downstream reward among worked jobs — primary **interview-rate**, secondary **response-rate**, tertiary **operator Promote agreement**.

In increasing rigor:
- **(a) Descriptive / logistic.** Fit `logit(interview) ~ title + location + recency + competition + urgency` on the decomposed sub-scores. The normalized coefficients are *learned* weights and immediately show which components actually predict interviews vs which are dead weight.
- **(b) Learning-to-rank.** Pairwise ranker (logistic on pairs / LambdaMART) using operator **Promote/Drop** as a cheap relevance label *plus* outcomes. Promote/Drop is gold: it's the operator's revealed preference, available the moment they curate — no waiting weeks for outcomes.
- **(c) Black-box search.** Bayesian optimization (or grid) over the 5-weight simplex (sum = 1) maximizing offline reward on a **held-out time window** (train on weeks 1–4, validate on 5–6). Cross-validate by time, never by random split.

**Fight survivorship bias:** mix in (b)'s Promote/Drop labels (available for *un*-worked jobs too), and reserve a small **exploration budget** — occasionally work a random lower-ranked job — to get counterfactual signal on what the ranker is missing.

## Phase 3 — Online / continuous
- **Bandit over configs.** Maintain a few weight/threshold variants; Thompson-sample which the scheduler uses, with a hard guardrail: never exceed the Phase-1-validated precision.
- **Drift monitors (weekly):** auto-submit precision, operator-edit rate, interview-rate. If precision drops below target → **auto-revert to review-default** and alert.

## Metrics & stopping criteria

| Metric | Type | Target |
|---|---|---|
| Auto-submit precision (approved-unchanged) | guardrail | ≥ 0.98 |
| Automation rate (Tier-A) | maximize | ↑ subject to guardrail |
| Interview-rate among worked jobs | primary (weights) | ↑ vs baseline weights |
| `agent_confidence` ECE | calibration | ≤ 0.05 |
| Operator-edit rate | drift | stable / ↓ |

Stop tuning a knob-set when a config beats the incumbent on the held-out window with a non-overlapping bootstrap CI and clears the guardrail.

## Feeding results back (an architecture note)
- **Thresholds** are already live config: `Settings.min_ats_score` / `min_agent_confidence` / `autonomy.*`. Updating them is a config change, no deploy.
- **Weights live in `profile.ranking_weights`** and are applied live by `src/aeroapply/sourcing/ranking.py` — a `config/profile.yaml` edit is enough for the bandit to flip weights with **no migration**. The `v_icebox_ranked` SQL view keeps the same formula with **frozen** weights as a debug/fallback only.

## Caveats
Small-N early (don't trust < ~150 labels); time-based CV only (market seasonality confounds random splits); correct for multiple comparisons when grid-searching; the loss is asymmetric, so optimize expected cost, not accuracy; and re-run calibration after any model-router change (a new Generator/Critic shifts both `ats_score` and `agent_confidence`).
