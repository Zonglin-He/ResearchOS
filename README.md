# ResearchOS

<div align="center">

[English](README.md) | [简体中文](README.zh-CN.md)

### The operating system for trustworthy AI research

Turn `idea -> hidden agent steps -> draft` into an auditable execution loop with typed flow control, diagnosis-driven experiments, grounded metrics, and an operator-visible console.

![Python](https://img.shields.io/badge/python-3.11+-0f172a?style=for-the-badge&logo=python&logoColor=white)
![UV](https://img.shields.io/badge/package%20manager-uv-2dd4bf?style=for-the-badge)
![Control Plane](https://img.shields.io/badge/operator-first-true-c2410c?style=for-the-badge)
![Workflow](https://img.shields.io/badge/proof%20chain-guide%20to%20console-2563eb?style=for-the-badge)

</div>

## Why It Hits Different

Most research agents optimize for more autonomy.

ResearchOS optimizes for a harder problem:

- Can a team see what happened?
- Can a failed run resume from the right checkpoint?
- Can every number in a draft be traced back to an artifact?
- Can an operator compare branches before approving a direction?

ResearchOS answers those questions with product surfaces, not promises.

## Product Story

```text
idea -> guide -> typed flow -> experiment repair loop -> verified writing -> operator console
```

This is not an auto-paper bot.

It is a trustworthy research execution system that helps teams:

- guide vague goals into bounded research directions
- manage work through explicit `gate`, `rollback`, `retry`, `pause`, `resume`, `pivot`, and `refine`
- run diagnosis-driven experiments with attempt history and best-result promotion
- block unsupported numbers before they reach a draft
- inspect live events, checkpoints, branches, approvals, and provider health

## From Black Box To Control Plane

```mermaid
flowchart LR
    A["Plain-language goal"] --> B["Guide"]
    B --> C["Typed Flow State Machine"]
    C --> D["Diagnosis-Driven Experiment Loop"]
    D --> E["Verified Metrics Registry"]
    E --> F["Writer"]
    F --> G["Operator Console"]
    G --> H["Approve, resume, compare, or pivot"]
```

## Core Surfaces

| Surface | What it does | Why it matters |
|---|---|---|
| `Guide` | decomposes the topic, gathers seed papers, and pauses at human-visible direction choice | research starts with bounded intent instead of agent drift |
| `Typed Flow` | persists stage, transitions, checkpoints, and decision history | recovery and audit stop being afterthoughts |
| `Experiment Loop` | diagnoses failure, applies bounded repair, records attempts, and promotes best results | experiments become recoverable instead of brittle |
| `Verified Metrics Registry` | binds draft numbers to runs, artifacts, freezes, and evidence packages | unsupported claims do not enter the paper |
| `Operator Console` | exposes flow snapshots, events, branch compare, checkpoint resume, and health | the system stays inspectable while it scales |

## What Makes ResearchOS Stronger

ResearchOS does not try to win by sounding more magical.

It wins by making automation more trustworthy.

| Category | Typical autonomous research agent | ResearchOS |
|---|---|---|
| Main story | automate more steps | operationalize research responsibly |
| Flow control | implicit chaining | typed state machine |
| Failure handling | retry or regenerate | diagnose, repair, and promote best result |
| Draft numbers | trust agent output | require grounded metrics |
| Human role | review after the fact | intervene through explicit checkpoints |
| Product form | agent workflow | research execution system |

## Proof, Not Just Copy

The repository includes an integration proof chain for:

`guide -> flow -> experiment -> writer -> operator console`

It validates:

- guided project start and direction adoption
- autopilot progression through branches and experiments
- verified metrics grounding before draft output
- operator-facing branch comparison, event stream, and flow inspection

Key references:

- [tests/integration/test_research_proof_chain.py](tests/integration/test_research_proof_chain.py)
- [tests/integration/test_dispatch_workflow.py](tests/integration/test_dispatch_workflow.py)
- [scripts/run_operator_benchmark.py](scripts/run_operator_benchmark.py)

## Code Map

| Area | Primary files |
|---|---|
| Flow state machine | [app/workflows/research_flow.py](app/workflows/research_flow.py), [app/services/project_service.py](app/services/project_service.py) |
| Experiment repair | [app/tools/experiment_runner.py](app/tools/experiment_runner.py) |
| Grounded writing | [app/services/verified_metrics_registry.py](app/services/verified_metrics_registry.py), [app/agents/writer.py](app/agents/writer.py) |
| Operator inspection | [app/services/operator_inspection_service.py](app/services/operator_inspection_service.py), [app/api/app.py](app/api/app.py), [frontend/src/App.tsx](frontend/src/App.tsx) |

## Quick Start

Requirements:

- Python `3.11+`
- [uv](https://docs.astral.sh/uv/)
- Node.js `18+`

```bash
uv sync --dev
cd frontend
npm install
cd ..
uv run researchos --db-path data/researchos.db init-db
uv run researchos web
```

Open `http://127.0.0.1:5173`.

Local deterministic mode:

```bash
export RESEARCHOS_PROVIDER=local
export RESEARCHOS_PROVIDER_MODEL=deterministic-reader
```

CLI-backed provider mode:

```bash
export RESEARCHOS_PROVIDER=claude
export RESEARCHOS_PROVIDER_MODEL=sonnet
export RESEARCHOS_WORKSPACE_ROOT=$(pwd)
```

Supported provider families in the repo include `claude`, `codex`, `gemini`, and `local`.

## Repo Structure

```text
app/
  agents/        specialized research agents
  api/           FastAPI control plane
  services/      registries, freezes, approvals, operator inspection
  tools/         experiment execution, verification, retrieval helpers
  workflows/     typed research flow state machine
frontend/
  src/           operator console and workspace UI
scripts/
  run_operator_benchmark.py
tests/
  integration/   end-to-end proof chain coverage
  unit/          service, API, and agent regressions
docs/
  showcase/      public-facing capability narratives
```

## Marketing Assets

If you want the short-form product narrative instead of the engineering overview:

- [docs/github_project_intro.md](docs/github_project_intro.md)
- [docs/website_copy.md](docs/website_copy.md)
- [docs/comparison/AutoResearchClaw.md](docs/comparison/AutoResearchClaw.md)

## Current Status

ResearchOS already ships:

- typed flow control
- checkpoint-aware resume
- diagnosis-driven experiment repair
- verified metrics grounding
- branch comparison and operator inspection
- integration proof-chain coverage

The next frontier is not more opaque automation.

It is broader packaging around the same trustworthy execution core: public benchmarks, showcase projects, and more external entry points.
