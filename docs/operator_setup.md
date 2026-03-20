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

## Live Provider Notes

ResearchOS can run with env defaults or explicit dispatch profiles.

Common env setup:

```powershell
$env:RESEARCHOS_PROVIDER = "claude"
$env:RESEARCHOS_PROVIDER_MODEL = "sonnet"
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

These paths are ignored in Git and treated as local runtime state.
