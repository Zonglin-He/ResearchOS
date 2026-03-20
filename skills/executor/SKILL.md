---
name: researchos-executor
description: Execute experiment specs safely and produce reproducible run manifests plus registered artifacts. Use when an approved experiment spec is ready to run.
---

# ResearchOS Executor

Use this skill for execution, retry, and failure capture around concrete experiment specs.

Do not use this skill when no concrete spec exists.

Expected inputs:
- experiment_spec
- repo_state
- dataset_snapshot

Expected outputs:
- run_manifest
- artifact_registrations

Procedure:
1. Confirm execution preconditions and required tools.
2. Run the spec with explicit config, seed, and environment capture.
3. Register artifacts and record failures without suppression.

Validation checklist:
- Run manifest captures config, dataset snapshot, seed, and artifacts.
- Failure state is explicit when execution fails.
- Provenance links remain intact.

Safety notes:
- Do not mutate frozen specs silently.
- Stop when sandbox, approval, or environment gates block execution.
