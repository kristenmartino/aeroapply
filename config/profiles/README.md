# Test personas (fictional)

Every profile in this directory is **invented** — names, cities, coordinates, salary
floors, and target titles are fictional and exist so the pipeline can be exercised
end-to-end without anyone's real data in git (PII boundary, `PROJECT_BRIEF.md` §2).
Your real profile lives in `config/profile.yaml`, which is **gitignored**.

| Persona | What it exercises |
|---|---|
| `jordan-aipm.yaml` | Core/adjacent title alignment, hybrid geo fence (Tampa/St. Pete), $120k floor, industry exclusions |
| `sam-dataeng.yaml` | Remote-only (all hybrid/onsite drop), high $150k floor, title-heavy weights |
| `casey-ux.yaml` | **No** salary floor (low/unlisted bands pass), two hybrid hint cities, location-heavy weights |

`config/profile.example.yaml` (one level up) is the template to copy for your real
profile; it uses a fourth fictional persona ("Alex Example", Springfield, IL) whose
values also seed the code defaults and the frozen `v_icebox_ranked` debug view.

## Choosing a profile

Precedence: `--profile` flag → `PROFILE_PATH` env var → `config/profile.yaml`.

```bash
# Run any CLI command against a persona instead of your real profile
uv run aeroapply source --board <token> --profile config/profiles/jordan-aipm.yaml
uv run aeroapply rank --profile config/profiles/sam-dataeng.yaml
uv run aeroapply ui --profile config/profiles/casey-ux.yaml

# Or via env (also how the Streamlit app picks it up)
PROFILE_PATH=config/profiles/casey-ux.yaml uv run aeroapply rank
```

Note: `repo.ensure_operator` keys the operator row on `primary_email`, so each
persona gets its own `app_user` row and its own Icebox — switching personas won't
cross-contaminate rankings or curation events in your dev database.

## Live boards for smoke-testing the sourcing path

The Greenhouse public board API needs a real board token (the company slug in
`boards.greenhouse.io/<token>`). Tokens come and go as companies change ATS, so
verify before relying on one:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/<token>/jobs" | head -c 200
```

Known tokens to try (unverified — companies do switch ATS): `gitlab`, `stripe`,
`cloudflare`, `doordashusa`, `reddit`. Any company careers page hosted at
`boards.greenhouse.io/<slug>` or `job-boards.greenhouse.io/<slug>` gives you a
working token. Then:

```bash
uv run aeroapply source --board gitlab --profile config/profiles/sam-dataeng.yaml
uv run aeroapply rank --profile config/profiles/sam-dataeng.yaml
```

## Adding your own persona

Copy any file here, change the values, and keep two invariants:

1. `ranking_weights` must sum to **1.0** (the config loader enforces it).
2. Use a unique `operator.primary_email` so the persona gets its own operator row.

If a persona should be committed, keep it fictional — real values belong only in
`config/profile.yaml`.
