$ErrorActionPreference = "Stop"

$db = "data\researchos.db"

uv run researchos --db-path $db create-project `
  --project-id gap-demo `
  --name "Gap Demo" `
  --description "Minimal gap mapping example"

uv run researchos --db-path $db create-task `
  --task-id gap-map-1 `
  --project-id gap-demo `
  --kind gap_mapping `
  --goal "Map one explicit gap" `
  --owner demo `
  --input-payload "{\"topic\":\"streaming adaptation\",\"paper_cards\":[{\"paper_id\":\"paper-1\",\"title\":\"Example Paper\",\"problem\":\"Robustness\",\"setting\":\"streaming\",\"task_type\":\"classification\"}]}"

uv run researchos --db-path $db dispatch-task --task-id gap-map-1
uv run researchos --db-path $db list-tasks --project-id gap-demo
