# ResearchOS Operator Console Showcase

This showcase demonstrates the five surfaces that move ResearchOS beyond a pure "auto research" loop.

## 1. Typed Research Flow

- `GET /projects/{project_id}/flow` exposes stage, status, active task, rollback target, checkpoint requirement, and transition history.
- `POST /projects/{project_id}/flow/{action}` supports operator-level `pause`, `resume`, `retry`, `pivot`, and `refine`.

## 2. Diagnosis-Driven Experiment Repair

- `app/tools/experiment_runner.py` records attempt history, structured diagnoses, repair actions, and promoted best results.
- The output now includes `attempts`, `best_result`, and `promoted_script_path`.

## 3. Verified Metrics Registry

- `WriterAgent` emits `verified_metrics_registry` and `metric_grounding_report` artifacts.
- Numeric claims in drafts are blocked when they cannot be grounded to registered runs or artifact-backed metrics.

## 4. Operator-First Console

- `frontend/src/components/OperationsTab.tsx` now shows:
  - flow snapshot and flow actions
  - realtime run events
  - checkpoint resume buttons
  - branch comparison by primary metric

## 5. Proof Surfaces

- `scripts/run_operator_benchmark.py` provides a reproducible smoke benchmark for flow, events, resume, and branch comparison.
- Regression coverage now includes flow persistence, experiment repair, metric grounding, resume, and branch compare APIs.
