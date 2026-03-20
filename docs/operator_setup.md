# Operator and Developer Setup

## Local Development

1. Install Python 3.11 and `uv`
2. Run:

```powershell
uv sync --dev
```

3. Use a local SQLite database for fast iteration:

```powershell
uv run researchos --db-path data\researchos.db init-db
```

Then open the terminal control plane directly:

```powershell
uv run researchos
```

If the workspace has no projects yet, the console now opens a guided setup flow so the operator can create the first project, choose a routing profile, state the primary research goal, receive a recommended first task kind, create the first task, and optionally dispatch it immediately.

Once a project exists, open `Projects -> Guide project` to let the onboarding guide agent inspect current project task state and recommend the next task kind in the workflow.
The guide also explains why that step is recommended, what artifact it typically produces, and what task kind usually follows it.

Equivalent explicit launch paths:

```powershell
uv run researchos console
uv run ros
```

4. Run tests:

```powershell
uv run pytest -q
```

5. For deterministic local runs, prefer the built-in local provider:

```powershell
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
```

If you want Gemini from the terminal model picker, the current presets use explicit Gemini 3 family names:

- `gemini-3.1-pro-preview`
- `gemini-3-flash-preview`
- `gemini-3.1-flash-lite-preview`

## Role Prompt and Skill Assets

ResearchOS keeps canonical role prompts and canonical role skills inside the repository:

- `prompts/roles/`
- `skills/`

These are the source of truth for role boundaries and reusable procedures. Provider-specific wrappers are thin exports, not separate logic sources.

To export wrappers for Codex / Claude / Gemini:

```powershell
uv run python scripts\export_role_assets.py
```

## Live Provider Notes

ResearchOS can run with env defaults or explicit dispatch profiles.

Common env setup:

```powershell
$env:RESEARCHOS_PROVIDER = "claude"
$env:RESEARCHOS_PROVIDER_MODEL = "sonnet"
```

Optional provider-health controls:

```powershell
$env:RESEARCHOS_DISABLED_PROVIDER_FAMILIES = "gemini"
$env:RESEARCHOS_PROVIDER_COOLDOWN_SECONDS = "300"
```

To isolate registry and artifact state per workspace, set:

```powershell
$env:RESEARCHOS_WORKSPACE_ROOT = "C:\\path\\to\\workspace"
```

For live execution, make sure the provider command path itself works before debugging ResearchOS.

## Production-Oriented Stack

Use Docker compose when you want:

- Postgres persistence
- Redis broker
- Celery worker
- FastAPI app

Start it with:

```powershell
docker compose up -d --build
```

Then run the smoke script:

```powershell
uv run python scripts\smoke_production_stack.py
```

## Data Locations

- SQLite by default: `data/researchos.db`
- registry-backed surfaces: `registry/`
- generated smoke output: `artifacts/`

These paths are resolved under `RESEARCHOS_WORKSPACE_ROOT` when it is set. Otherwise they resolve under the current working directory.

These paths are ignored in Git and treated as local runtime state.

## Operator Inspection Surfaces

Current operator-facing inspection endpoints include:

- `GET /artifacts`
- `GET /artifacts/{artifact_id}`
- `GET /artifacts/{artifact_id}/annotations`
- `POST /artifacts/{artifact_id}/annotations`
- `GET /verifications`
- `GET /verifications/summary`
- `GET /audit/claims`
- `GET /audit/runs/{run_id}`
- `GET /audit/summary`

Artifact annotations are intentionally constrained metadata. They allow operator review notes, review tags, and status updates without mutating the original artifact payload.

Routing transparency is exposed through task/run metadata:

- task `last_run_routing`
- run manifest `dispatch_routing`
- dispatch audit notes in agent results

These surfaces now include the resolved role, capability class, chosen provider family, chosen model, fallback chain, and health snapshots used during selection when available.
