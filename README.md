# ResearchOS

ResearchOS is a code-first multi-agent research workflow runtime. It is a backend and control-plane system for running structured research tasks with:

- typed task and run state
- specialized agents
- role-driven execution contracts
- CLI and terminal control plane
- FastAPI control plane
- worker-based async dispatch
- routing policies for provider/model selection
- registries for claims, paper cards, gap maps, runs, freezes, lessons, and verifications

It is not a chat UI product. The core interface is still backend services plus CLI/TUI/API.

## What It Does

ResearchOS manages a research workflow around explicit objects:

- `Task`: unit of work with lifecycle and dispatch profile
- `Message`: structured cross-agent communication primitive
- `AgentResult`: structured output from agent execution
- `RunContext`: runtime state including resolved routing and prior lessons
- `RunManifest`: recorded execution metadata and metrics
- `Claim`, `PaperCard`, `GapMap`, `Freeze`: durable research artifacts
- `ExperimentProposal`, `ExperimentDecision`: explicit experiment loop primitives
- `LessonRecord`, `VerificationRecord`: reusable memory and verification surfaces

## Role System

ResearchOS now uses a typed workflow-role layer on top of the existing specialized agents.

The role layer is not just a label. Each workflow role now has an inspectable contract in
[`app/roles/catalog.py`](app/roles/catalog.py) and [`app/roles/models.py`](app/roles/models.py)
covering:

- mission
- required inputs
- required outputs
- allowed / forbidden tools
- success criteria
- review checklist
- default capability class
- default and fallback provider-family preferences

Workflow roles:

- Scoper
- Librarian
- Synthesizer
- Hypothesist
- ExperimentDesigner
- Executor
- Analyst
- Reviewer
- Verifier
- Publisher
- Archivist

Current specialized-agent overlay:

- Reader = Librarian + part of Scoper
- Mapper = Synthesizer
- Builder = Hypothesist + ExperimentDesigner + part of Executor
- Reviewer = Reviewer
- Writer = Publisher
- Style = Publisher post-processing
- Analyst = result analysis
- Verifier = evidence and methodology verification
- Archivist = lessons / provenance / registry curation

Fallback does not change role obligations. Provider family changes are allowed, but the expected artifact contract stays the same for the role.

Examples:

- Librarian -> `paper_card`
- Synthesizer -> `gap_map`
- Executor -> `run_manifest`
- Analyst -> `result_summary`
- Verifier -> `verification_report`
- Publisher -> `paper_draft`
- Archivist -> `archive_entry`

## Canonical Role Prompts and Skills

ResearchOS now keeps role-native prompt and skill assets as repo-owned canonical source material:

- canonical role prompts: [`prompts/roles/`](prompts/roles)
- canonical role skills: [`skills/`](skills)
- design/research note: [`docs/role-prompt-skill-architecture.md`](docs/role-prompt-skill-architecture.md)

The canonical layer is provider-agnostic. It defines responsibility boundaries, artifact obligations, review checklists, and reusable procedures once.

Thin provider-specific wrappers are exportable on demand:

```powershell
uv run python scripts\export_role_assets.py
```

This writes wrapper assets under `provider_exports/` for:

- Codex-style skills
- Claude-style markdown/subagent wrappers
- Gemini-style command wrappers

The runtime resolves role prompt text and skill metadata lazily. It does not eagerly inject every role skill into every run.

## Architecture Overview

High-level layers:

1. Schemas
   - typed dataclasses and enums in [`app/schemas/`](app/schemas)
2. Services
   - task lifecycle, claims, runs, freezes, experiments, lessons, verification, audit in [`app/services/`](app/services)
3. Providers and Tools
   - provider abstraction in [`app/providers/`](app/providers)
   - tool abstraction and registry in [`app/tools/`](app/tools)
4. Agents and Orchestration
   - specialized agents and orchestrator in [`app/agents/`](app/agents)
5. Control Plane
   - CLI in [`app/cli.py`](app/cli.py)
   - interactive terminal control plane in [`app/console/`](app/console)
   - FastAPI app in [`app/api/app.py`](app/api/app.py)
6. Worker / Async Dispatch
   - Celery integration in [`app/worker/`](app/worker)

## Local Quickstart

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- optional: Docker Desktop for the production stack
- optional: provider CLIs if you want live Codex / Claude / Gemini execution

Install dependencies:

```powershell
uv sync --dev
```

Recommended deterministic local setup for demos, CI-style checks, and first-time onboarding:

```powershell
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
$env:RESEARCHOS_WORKSPACE_ROOT = (Resolve-Path ".").Path
```

Initialize a local SQLite database:

```powershell
uv run researchos --db-path data\researchos.db init-db
```

Run the unit test suite:

```powershell
uv run pytest -q
```

## Provider Setup

ResearchOS keeps env defaults as a fallback, but provider/model can also be set explicitly through dispatch profiles.

Minimum env example:

```powershell
$env:RESEARCHOS_PROVIDER = "claude"
$env:RESEARCHOS_PROVIDER_MODEL = "sonnet"
$env:RESEARCHOS_MAX_STEPS = "12"
```

Supported provider families in the current repo:

- `codex`
- `claude`
- `gemini`
- `local`

Recommended usage:

- use `local` for deterministic local development, CI, demos, and teaching
- use `codex` / `claude` / `gemini` only when the corresponding external CLI is already installed and working
- in the terminal control plane, Gemini presets now use explicit Gemini 3 family model names rather than older 2.5-only presets

## Claude-First Routing Philosophy

ResearchOS is Claude-first for core reasoning roles, but Claude is not forced for every role.

Default intent:

- prefer Claude family for:
  - Scoper
  - Hypothesist
  - Analyst
  - Reviewer
  - Verifier
  - Publisher
- do not spend Claude by default for:
  - Librarian
  - Synthesizer
  - Archivist
  - Executor

Default role-family tendency:

- Librarian -> Gemini 3 Flash / Flash-Lite
- Synthesizer -> Gemini 3.1 Pro
- Executor -> Codex
- Archivist -> Gemini 3.1 Flash-Lite or local
- core reasoning roles -> Claude first

Fallback is capability-aware rather than one global order:

- planning / review / verification:
  - Claude -> Codex -> Gemini -> local
- retrieval / synthesis / archival:
  - Gemini -> Claude -> Codex -> local
- coding / execution:
  - Codex -> Claude -> local

If a provider family is unavailable, rate-limited, exhausted, disabled, or unhealthy, ResearchOS will fall back honestly. It does not pretend to know token quotas exactly; it relies on CLI availability, invocation failures, cooldowns, and known failure signatures.

You can override routing through dispatch profiles at the project or task level. If an explicit env provider is set, that still wins over role defaults.

If you use live provider execution, make sure the relevant provider CLI or command path is already working on your machine.

## CLI Quickstart

Create a project:

```powershell
uv run researchos --db-path data\researchos.db create-project `
  --project-id p1 `
  --name "ResearchOS Demo" `
  --description "Minimal local demo"
```

Create a task:

```powershell
uv run researchos --db-path data\researchos.db create-task `
  --task-id t1 `
  --project-id p1 `
  --kind paper_ingest `
  --goal "Read one paper summary" `
  --owner demo `
  --input-payload "{\"topic\":\"robustness\",\"source_summary\":{\"title\":\"Example Paper\",\"abstract\":\"A compact summary.\",\"setting\":\"classification\"}}"
```

Dispatch the task:

```powershell
uv run researchos --db-path data\researchos.db dispatch-task --task-id t1
```

List tasks and artifacts:

```powershell
uv run researchos --db-path data\researchos.db list-tasks --project-id p1
uv run researchos --db-path data\researchos.db list-artifacts
```

Open the interactive terminal control plane:

```powershell
uv run researchos
```

If there are no projects yet, ResearchOS now starts with a guided first-project flow that helps you:

- create the first project
- choose a default dispatch profile
- state the primary research goal
- get an automatic recommended first task kind
- create the first task
- optionally dispatch it immediately

Explicit console launch still works:

```powershell
uv run researchos console
uv run ros
```

## API Quickstart

Start the API:

```powershell
uv run uvicorn app.api.app:create_app --factory --reload
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Create a project:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/projects" `
  -ContentType "application/json" `
  -Body '{"project_id":"p1","name":"ResearchOS Demo","description":"API demo","status":"active"}'
```

Dispatch a task:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/tasks/t1/dispatch"
```

Inspect artifacts:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/artifacts"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/artifacts/<artifact-id>"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/verifications/summary"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/audit/summary"
```

## Docker / Production Quickstart

The production-oriented stack uses:

- FastAPI
- Postgres
- Redis
- Celery worker

Start the stack:

```powershell
docker compose up -d --build
```

Run the production smoke path:

```powershell
uv run python scripts\smoke_production_stack.py
```

## Registries and Artifacts

ResearchOS persists several durable research surfaces outside the task table.

By default they are created under the current workspace root. If `RESEARCHOS_WORKSPACE_ROOT` is unset, the current working directory is used.

Relative to the workspace root, the main registry files are:

- `registry/claims.jsonl`
- `registry/runs.jsonl`
- `registry/paper_cards.jsonl`
- `registry/gap_maps.jsonl`
- `registry/freezes/`
- `registry/lessons.jsonl`
- `registry/verifications.jsonl`

These are not transient logs. They are explicit workflow state that agents and operators can inspect and reuse.

Artifacts produced by runs are registered via [`app/services/artifact_service.py`](app/services/artifact_service.py), and run manifests can be checked through the verification layer.

The artifact registry file is:

- `registry/artifacts.jsonl`

Generated draft/style artifacts are written under:

- `artifacts/`

Operator-facing inspection surfaces now include:

- `GET /artifacts`
- `GET /artifacts/{artifact_id}`
- `GET /artifacts/{artifact_id}/annotations`
- `POST /artifacts/{artifact_id}/annotations`
- `GET /verifications`
- `GET /verifications/summary`
- `GET /audit/claims`
- `GET /audit/runs/{run_id}`
- `GET /audit/summary`

Artifact detail now includes a typed provenance view with:

- verification links
- audit subject references
- claim support references
- run evidence
- constrained operator annotations

## Example Flows

Copy-pastable examples live in:

- [`examples/README.md`](examples/README.md)
- [`examples/minimal-paper-ingest.ps1`](examples/minimal-paper-ingest.ps1)
- [`examples/minimal-gap-mapping.ps1`](examples/minimal-gap-mapping.ps1)
- [`examples/minimal-dispatch-profile.ps1`](examples/minimal-dispatch-profile.ps1)

## Operator and Developer Notes

- local developer notes: [`docs/operator_setup.md`](docs/operator_setup.md)
- release checklist: [`docs/release_checklist.md`](docs/release_checklist.md)
- changelog: [`CHANGELOG.md`](CHANGELOG.md)

## CI

GitHub Actions runs:

- dependency install with `uv`
- Python bytecode compilation for import sanity
- unit tests
- API dispatch smoke using the deterministic local provider
- a small CLI smoke path

Workflow file:

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
