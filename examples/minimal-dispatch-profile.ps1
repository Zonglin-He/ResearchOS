$ErrorActionPreference = "Stop"

$db = "data\researchos.db"
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
$env:RESEARCHOS_WORKSPACE_ROOT = (Resolve-Path ".").Path

uv run researchos --db-path $db create-project `
  --project-id routing-demo `
  --name "Routing Demo" `
  --description "Task dispatch profile override example" `
  --dispatch-profile "{\"provider\":{\"provider_name\":\"local\",\"model\":\"deterministic-reader\"},\"max_steps\":12}"

uv run researchos --db-path $db create-task `
  --task-id routing-task-1 `
  --project-id routing-demo `
  --kind paper_ingest `
  --goal "Dispatch with explicit override" `
  --owner demo `
  --dispatch-profile "{\"provider\":{\"provider_name\":\"local\",\"model\":\"deterministic-reader\"},\"max_steps\":18}" `
  --input-payload "{\"topic\":\"routing\",\"source_summary\":{\"title\":\"Routing Example\",\"abstract\":\"Provider selection demo.\",\"setting\":\"classification\"}}"

uv run researchos --db-path $db dispatch-task --task-id routing-task-1
