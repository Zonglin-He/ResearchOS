---
name: researchos-experiment-designer
description: Convert hypotheses into executable experiment specs with baselines, metrics, ablations, and budget. Use when a research direction needs a concrete test plan.
---

# ResearchOS Experiment Designer

Use this skill when a hypothesis must become a runnable experiment spec.

Do not use this skill for raw retrieval or archival tasks.

Expected inputs:
- hypothesis_set
- resource_constraints
- topic/spec freeze if present

Expected outputs:
- experiment_spec

Procedure:
1. Pick baselines, metrics, datasets, and stop conditions.
2. Define ablations and cost-aware execution order.
3. Emit a spec an Executor can run without guessing missing setup.

Validation checklist:
- Baseline and ablation plan exist.
- Budget, success criteria, and failure criteria are explicit.
- Approval-sensitive expensive steps are called out.

Safety notes:
- Do not hide costly steps in vague implementation notes.
