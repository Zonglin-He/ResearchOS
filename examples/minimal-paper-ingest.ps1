$ErrorActionPreference = "Stop"

$db = "data\researchos.db"
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
$env:RESEARCHOS_WORKSPACE_ROOT = (Resolve-Path ".").Path

uv run researchos --db-path $db create-project `
  --project-id paper-demo `
  --name "Paper Demo" `
  --description "Minimal paper ingest example"

uv run researchos --db-path $db create-task `
  --task-id paper-ingest-1 `
  --project-id paper-demo `
  --kind paper_ingest `
  --goal "Read a compact source summary" `
  --owner demo `
  --input-payload "{\"topic\":\"robustness\",\"source_summary\":{\"title\":\"Example Paper\",\"abstract\":\"A compact summary for ingestion.\",\"setting\":\"classification\"}}"

uv run researchos --db-path $db dispatch-task --task-id paper-ingest-1
uv run researchos --db-path $db list-tasks --project-id paper-demo
uv run researchos --db-path $db list-paper-cards
uv run researchos --db-path $db list-artifacts
