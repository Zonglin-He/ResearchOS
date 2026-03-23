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

Executable-script standards:
- When generating or patching experiment code, ensure every imported library is either in project requirements or part of the standard library.
- Use relative dataset paths or environment variables, never hard-coded machine-specific absolute paths.
- Ensure runnable scripts expose an `if __name__ == "__main__":` entry point.
- Every critical hyperparameter must have a default value so the script can run without mandatory CLI arguments.
- Prefer reproducible defaults: fixed seed, explicit device selection, and explicit output locations.
- Add basic error handling around the main training or evaluation loop so a single bad batch or shard is captured explicitly instead of aborting without context.
- Emit parseable metric logs at a regular cadence, for example `METRICS epoch=5 loss=0.234 acc=0.873 val_acc=0.812`.

Pre-run checklist:
- Check that CUDA-dependent code has a CPU-safe fallback when GPU is unavailable.
- Check that `batch_size`, epochs, and evaluation cadence are realistic for the available hardware.
- Check that the experiment can run from repo state alone without hidden local assumptions.
- Check that failures in one batch or one data shard do not silently corrupt the full run.

Common error patterns to avoid:
- `import torch` with unconditional CUDA use and no availability check
- `batch_size = 512` without regard for memory limits
- Long default runs such as 100 epochs when the default environment is likely CPU-bound
- Hard-coded dataset paths such as `root="/data/cifar10"`
- Missing seed configuration, which makes results hard to reproduce

Validation checklist:
- Run manifest captures config, dataset snapshot, seed, and artifacts.
- Failure state is explicit when execution fails.
- Provenance links remain intact.
- Generated or patched scripts are runnable with sane defaults.
- Metric output is structured enough for downstream parsing.
- Environment assumptions are recorded instead of hidden in code.

When you are unsure:
If you catch yourself assuming a local dataset path, a GPU, or a non-default dependency without evidence, stop and make the assumption explicit.

Recover by:
1. Using repo-relative paths or environment variables.
2. Lowering resource defaults to the smallest credible runnable setting.
3. Recording any unresolved environment dependency in `audit_notes` when available; otherwise put it in the failure or uncertainty field.

Safety notes:
- Do not mutate frozen specs silently.
- Stop when sandbox, approval, or environment gates block execution.
