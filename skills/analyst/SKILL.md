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

Validation checklist:
- Observed outcomes are distinct from conjecture.
- The analyzed run is clearly referenced.
- Recommendations are specific.

Safety notes:
- Do not imply significance if it was not checked.
