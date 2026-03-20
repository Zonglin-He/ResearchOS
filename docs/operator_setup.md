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

4. Run tests:

```powershell
uv run pytest -q
```

5. For deterministic local runs, prefer the built-in local provider:

```powershell
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
```

## Live Provider Notes

ResearchOS can run with env defaults or explicit dispatch profiles.

Common env setup:

```powershell
$env:RESEARCHOS_PROVIDER = "claude"
$env:RESEARCHOS_PROVIDER_MODEL = "sonnet"
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
