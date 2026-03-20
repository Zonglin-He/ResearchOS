# Phase 4: Experiment Manager and Closed-Loop Research Execution

## Summary

This phase introduces a typed experiment-management layer for ResearchOS.

The goal is not a fully autonomous scientist loop. The goal is to make experiment execution explicit, auditable, and structurally compatible with the existing task, run, freeze, approval, and audit model.

## New Core Concepts

- `ExperimentProposal`
  - structured candidate experiment tied to a task and spec
- `ExperimentBudget`
  - deterministic control policy for attempts, cost cap, and approval threshold
- `ExperimentResultSummary`
  - structured evaluation payload for a completed run
- `ExperimentDecision`
  - keep/discard/block/approval/stop decision with explicit rationale
- `ExperimentManager`
  - orchestrates proposal queue, readiness checks, execution recording, and evaluation

## How This Differs From Plain Task Dispatch

Plain task dispatch answers:

- which agent should run this task
- what provider/model should it use
- what next task should be spawned

The experiment manager answers a different layer of questions:

- should this candidate experiment be allowed to run at all
- is it within budget
- does it require approval
- was the run better than baseline
- should the result be kept or discarded
- should the experiment branch be kept or rolled back

This means experiment management is not hidden inside prompts or widgets. It is a typed, deterministic policy layer.

## Lifecycle

Minimal lifecycle in this phase:

1. enqueue proposal
2. bind proposal to task
3. authorize execution
4. record run execution
5. evaluate run result
6. persist keep/discard decision

## Deterministic Policies Included

- max attempts
- total budget cap
- stop on no improvement
- require approval above a configured cost threshold
- require approved spec freeze before execution

## Auditability

Audit trail is explicit through persisted records:

- proposal registry
- budget registry
- result summaries
- experiment decisions
- approval records for expensive proposals
- run manifests linked back to experiment proposals

## Example Lifecycle

1. A builder task proposes `proposal-3` for `spec-1`
2. The manager stores the proposal and attaches it to the task
3. The manager checks:
   - approved spec freeze exists
   - attempts not exhausted
   - total budget not exceeded
   - approval threshold not violated
4. Execution is recorded with a `RunManifest`
5. A structured `ExperimentResultSummary` is submitted
6. The manager emits:
   - `keep` if improved and within budget
   - `discard` if no improvement and stop-on-no-improvement is enabled
   - `requires_approval` for expensive proposals without approval
   - `block` if freeze prerequisites are missing

## Compatibility Notes

- Existing task dispatch behavior is unchanged.
- Existing CLI/API behavior is unchanged in this phase.
- `Task` now has optional `experiment_proposal_id`.
- `RunManifest` now has optional:
  - `experiment_proposal_id`
  - `experiment_branch`
- SQLite schema upgrades are additive.
- Existing PostgreSQL deployments will need a real migration for the new task column if Phase 4 is used with SQLAlchemy-backed tasks.
