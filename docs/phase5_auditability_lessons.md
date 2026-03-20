# Phase 5: Stronger Auditability, Verification Surfaces, and Lessons Memory

## Summary

This phase adds two explicit layers that were previously missing:

- structured lessons memory for cross-run reuse
- explicit verification records for artifact, claim, freeze, and run checks

The goal is not to pretend that ResearchOS can fully verify semantics it cannot observe. The goal is to make verification status explicit and retrievable, and to separate durable lessons from transient logs.

## New Data Models

### Lessons

`LessonRecord` stores reusable memory with dimensions that can be queried later:

- `lesson_kind`
  - `lesson`
  - `anti_pattern`
  - `playbook`
  - `failure_signature`
- `task_kind`
- `agent_name`
- `tool_name`
- `provider_name`
- `model_name`
- `failure_type`
- `repository_ref`
- `dataset_ref`
- `context_tags`
- `evidence_refs`
- `artifact_ids`
- `source_task_id`
- `source_run_id`
- `source_claim_id`

Lessons are stored in `registry/lessons.jsonl`.

### Verification

`VerificationRecord` makes verification state explicit instead of implied:

- `check_type`
  - `claim_evidence`
  - `artifact_completeness`
  - `freeze_consistency`
  - `run_manifest_sanity`
- `status`
  - `verified`
  - `incomplete`
  - `failed`
  - `not_checked`
- `rationale`
- `evidence_refs`
- `artifact_ids`
- `missing_fields`

Verification records are stored in `registry/verifications.jsonl`.

### Audit

`AuditReport` now includes structured `AuditEntry` objects with:

- rationale
- evidence references
- artifact references
- related runs
- related claims

This keeps the audit surface machine-readable while preserving existing summary fields.

## Practical Behavior Added

### Lessons before acting

The orchestrator now loads prior relevant lessons into `RunContext.prior_lessons` before agent execution. This gives future agents a structured retrieval surface without hardcoding special prompts into the UI.

### Lessons after failure or review blockage

When an agent returns a failure or blocker with audit notes or blocking issues, a lesson can be recorded automatically with:

- task kind
- agent
- resolved provider/model
- failure type
- artifact references
- source task reference

### Verification surfaces

This phase adds practical, honest verification hooks:

- run manifest sanity
  - required metadata present
  - referenced artifact IDs are registered
- claim evidence presence
  - explicit support exists
  - referenced run IDs exist
- results freeze consistency
  - results freeze aligns with spec freeze and registered claims

These checks do not claim to verify scientific truth. They only verify the parts the system can actually inspect.

## CLI/API Access

CLI:

- `researchos create-lesson ...`
- `researchos list-lessons ...`
- `researchos verify-run --run-id ...`
- `researchos verify-claim --claim-id ...`
- `researchos verify-results-freeze`
- `researchos list-verifications`
- `researchos audit-claims`
- `researchos audit-run --run-id ...`

API:

- `POST /lessons`
- `GET /lessons`
- `POST /verifications/runs/{run_id}`
- `POST /verifications/claims/{claim_id}`
- `POST /verifications/freezes/results`
- `GET /verifications`
- `GET /audit/claims`
- `GET /audit/runs/{run_id}`

## Compatibility Notes

- Existing CLI and API behavior is preserved.
- This phase is additive.
- Lessons are stored separately from task/run logs.
- Verification status is explicit and can be `not_checked` or `incomplete`; it is never implied.
