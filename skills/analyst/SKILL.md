---
name: researchos-analyst
description: Analyze run results, explain anomalies, and produce evidence-backed result summaries. Use when run manifests and metrics need interpretation.
---

# ResearchOS Analyst

Use this skill after execution when the system needs structured analysis rather than raw metrics.

Do not use this skill to rerun experiments or invent statistical claims.

Expected inputs:
- run_manifest
- metrics
- artifacts

Expected outputs:
- result_summary

Procedure:
1. Identify the main result deltas against baselines.
2. Call out anomalies and plausible causes separately.
3. Recommend next actions tied to evidence gaps or anomalies.

Decision standards:
- Recommend `PROCEED` only when at least 2 of the following hold.
- The main metric improves by more than 0.5% over the baseline or exceeds the stated noise floor.
- The loss curve is visibly converged, for example the last 5 epochs have low variance rather than ongoing instability.
- The train/validation accuracy gap stays below 15 percentage points, suggesting no severe overfitting.
- Recommend `REFINE` when training is learning something but the failure mode looks local and patchable.
- Recommend `PIVOT` when the experiment no longer tests the intended hypothesis or repeated refinement has failed.

Refine signals:
- Training loss decreases while validation accuracy stays flat or worsens: likely overfitting; suggest regularization, stronger augmentation, or earlier stopping.
- Early epochs produce `nan` loss or exploding values: likely optimizer or learning-rate instability; suggest lowering `learning_rate` or checking normalization.
- The run hits OOM or similar resource limits: suggest reducing `batch_size`, model size, or evaluation frequency.

Pivot signals:
- More than 3 refinement rounds fail to improve the relevant metric.
- Validation performance falls below the random or trivial baseline.
- The implemented experiment no longer matches the hypothesis in the spec.

Validation checklist:
- Observed outcomes are distinct from conjecture.
- The analyzed run is clearly referenced.
- Recommendations are specific.
- Numerical judgments are tied to explicit metrics, not vague language.
- `PROCEED`, `REFINE`, or `PIVOT` is justified by evidence rather than tone.
- Anomalies are separated from the main result summary.

Language rule:
- Do not say "there is some improvement" or "results are promising" without numbers.
- Always include the metric, the delta, and the reason for the recommendation.

When you are unsure:
If you catch yourself writing a conclusion that could fit any experiment, stop and anchor it to one metric and one comparison.

Recover by:
1. Naming the baseline.
2. Naming the key metric and its delta.
3. Stating whether the evidence supports `PROCEED`, `REFINE`, or `PIVOT`.

If the metrics are too incomplete for a reliable judgment, record that limitation in `audit_notes` when available; otherwise put it in the uncertainty section and avoid overclaiming.

Safety notes:
- Do not imply significance if it was not checked.
