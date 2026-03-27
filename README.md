# ResearchOS

<p align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=flat-square" alt="English" /></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/lang-中文-red?style=flat-square" alt="中文" /></a>
</p>

> The operating system for trustworthy AI research.

ResearchOS turns black-box research automation into an auditable execution loop. Instead of treating research as a single autonomous agent run, it treats research as an operator-visible system with explicit flow state, durable artifacts, grounded metrics, and human checkpoints where decisions actually matter.

## Positioning

ResearchOS is not an auto-paper bot.

It is a trustworthy research execution system that helps teams:

- guide a vague goal into a bounded research direction
- move work through a typed state machine with gate, rollback, retry, pause, resume, pivot, and refine
- run diagnosis-driven experiments with repair history and best-result promotion
- ground every reported number in verified run artifacts before it reaches a draft
- inspect live events, checkpoints, branches, and approvals from an operator console

## Why This Exists

Many research agents optimize for more automation. That is useful, but incomplete.

Real research teams also need:

- visibility: what happened, in what order, and why
- recoverability: where to resume after failure
- accountability: which artifact supports which claim
- controllability: where humans can intervene without breaking the whole run

ResearchOS is built around a different promise:

**do not automate research blindly; operationalize research responsibly.**

## Product Story

ResearchOS turns this:

`idea -> hidden agent steps -> draft`

into this:

`guide -> flow -> experiment -> writer -> operator console`

That loop is the product.

### 1. Guide

Start from a plain-language goal. The guide decomposes the problem, gathers seed papers, maps candidate gaps, and pauses at `human_select` when direction choice should stay human-visible.

### 2. Flow

The workflow is encoded as a typed state machine, not a loose sequence of task strings. Flow supports:

- `gate`
- `rollback`
- `retry`
- `pause`
- `resume`
- `pivot`
- `refine`

### 3. Experiment

Experiments are not just launched and forgotten. ResearchOS runs a diagnosis-driven repair loop with:

- structured failure diagnosis
- repair actions
- attempt history
- best-result promotion

### 4. Writer

Draft generation is constrained by evidence. The writer uses:

- citation verification
- verified metrics registry
- metric grounding reports
- results freezes

Unsupported numbers are blocked before they become paper claims.

### 5. Operator Console

The operator console exposes the full control plane:

- flow snapshots
- run events
- branch comparison
- checkpoint resume
- approval surfaces
- provider health

## Core Capabilities

### Typed Flow Control

Research flow is persisted as explicit state, including decision history and checkpoint requirements.

Relevant code:

- [app/workflows/research_flow.py](app/workflows/research_flow.py)
- [app/services/project_service.py](app/services/project_service.py)

### Diagnosis-Driven Experiment Repair

Experiment execution records attempts, diagnoses failures, applies bounded repairs, and promotes the strongest successful result.

Relevant code:

- [app/tools/experiment_runner.py](app/tools/experiment_runner.py)

### Verified Metrics Registry

Every numeric claim can be tied back to run manifests, artifact metadata, or approved result freezes before it is accepted into a draft.

Relevant code:

- [app/services/verified_metrics_registry.py](app/services/verified_metrics_registry.py)
- [app/agents/writer.py](app/agents/writer.py)

### Operator-First Inspection

ResearchOS is built for operators, not just background agents. The inspection layer powers:

- project dashboards
- branch comparison
- recent run events
- flow inspection
- checkpoint-aware resume

Relevant code:

- [app/services/operator_inspection_service.py](app/services/operator_inspection_service.py)
- [app/api/app.py](app/api/app.py)
- [frontend/src/App.tsx](frontend/src/App.tsx)

## What Makes ResearchOS Different

ResearchOS does not try to win by claiming maximum autonomy.

It wins by making automation more trustworthy.

| Category | Typical autonomous research agent | ResearchOS |
|---|---|---|
| Main story | Automate more steps | Make each step inspectable and recoverable |
| Flow control | Implicit task chaining | Typed workflow state machine |
| Failure handling | Retry or regenerate | Diagnose, repair, and promote best result |
| Numbers in drafts | Often trusted from agent output | Must be grounded in verified metrics |
| Human role | Approval after the fact | Explicit checkpoint and operator console |
| Product form | Agent workflow | Research execution system |

## End-to-End Proof Chain

The repo now includes an integration proof chain that exercises:

`guide -> flow -> experiment -> writer -> operator console`

It validates:

- guided start and direction adoption
- autopilot progression through branch planning and experiments
- result grounding and draft generation
- operator-facing branch comparison, event stream, and flow surfaces

Relevant tests:

- [tests/integration/test_research_proof_chain.py](tests/integration/test_research_proof_chain.py)
- [tests/integration/test_dispatch_workflow.py](tests/integration/test_dispatch_workflow.py)

Benchmark helper:

- [scripts/run_operator_benchmark.py](scripts/run_operator_benchmark.py)

## Quick Start

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+

```bash
uv sync --dev
cd frontend
npm install
cd ..
uv run researchos --db-path data/researchos.db init-db
uv run researchos web
```

Open `http://127.0.0.1:5173`.

### Provider Configuration

Deterministic local mode:

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

Other supported provider families in the repo include `codex` and `gemini`.

## Repository Map

```text
app/
  agents/        specialized research agents
  api/           FastAPI control plane
  services/      registries, freezes, operator inspection
  tools/         experiment execution, verification, retrieval helpers
  workflows/     typed research flow state machine
frontend/
  src/           operator console and workspace UI
scripts/
  run_operator_benchmark.py
tests/
  integration/   end-to-end proof chain coverage
  unit/          service, API, and agent regression coverage
docs/
  showcase/      public-facing capability narratives
```

## Marketing Assets In This Repo

If you want the concise product narrative rather than the engineering overview, see:

- [docs/github_project_intro.md](docs/github_project_intro.md)
- [docs/website_copy.md](docs/website_copy.md)
- [docs/comparison/AutoResearchClaw.md](docs/comparison/AutoResearchClaw.md)

## Status

ResearchOS already has:

- typed flow control
- checkpoint-aware resume
- diagnosis-driven experiment repair
- verified metrics grounding
- branch comparison and operator inspection
- integration proof-chain coverage

The next frontier is not “more opaque automation”.

It is broader ecosystem packaging: public benchmarks, showcase projects, and more external entry points around the same trustworthy execution core.
