# Example Flows

These examples are intentionally small and copy-pastable. They assume you already ran:

```powershell
uv sync --dev
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
$env:RESEARCHOS_WORKSPACE_ROOT = (Resolve-Path ".").Path
uv run researchos --db-path data\researchos.db init-db
```

Available scripts:

- [`minimal-paper-ingest.ps1`](minimal-paper-ingest.ps1)
- [`minimal-gap-mapping.ps1`](minimal-gap-mapping.ps1)
- [`minimal-dispatch-profile.ps1`](minimal-dispatch-profile.ps1)

Run one directly:

```powershell
powershell -ExecutionPolicy Bypass -File .\examples\minimal-paper-ingest.ps1
```
