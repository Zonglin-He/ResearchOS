# Release Checklist

## Before Tagging

- update [`CHANGELOG.md`](../CHANGELOG.md)
- verify `version` in [`pyproject.toml`](../pyproject.toml)
- run unit tests
- run CLI smoke path
- run API smoke path if the release changes API behavior
- run production stack smoke path if the release touches worker, broker, or database wiring

## Required Commands

```powershell
uv sync --dev
python -m compileall app
uv run pytest -q
uv run researchos --help
```

Optional but recommended:

```powershell
uv run python scripts\smoke_production_stack.py
uv run python scripts\smoke_live_research_flow.py
```

## Notes

- keep examples in [`examples/README.md`](../examples/README.md) aligned with the current CLI
- do not commit local `.venv`, `data`, `registry`, or `artifacts` output
- if schema changes touch Postgres-backed models, document the migration explicitly
