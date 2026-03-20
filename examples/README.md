# Example Flows

These examples are intentionally small and copy-pastable. They assume you already ran:

```powershell
uv sync --dev
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
