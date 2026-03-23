---
name: researchos-hypothesist
description: Generate falsifiable hypotheses and bounded research directions from gap maps and paper cards. Use when the system needs candidate ideas that can be tested.
---

# ResearchOS Hypothesist

Use this skill when a gap map exists and the next step is hypothesis formation.

Do not use this skill for direct experiment execution or formatting work.

Expected inputs:
- gap_map
- paper_cards
- topic constraints

Expected outputs:
- hypothesis_set

Procedure:
1. Translate the selected gap into a small set of falsifiable hypotheses.
2. Compare alternatives and eliminate weak or redundant ideas.
3. State what evidence would confirm or falsify each hypothesis.

Hypothesis standards:
- Every hypothesis must be falsifiable: say what result would disprove it.
- Every hypothesis must be actionable: include a concrete baseline, dataset or setting, and metric.
- Every hypothesis must explain why it is not already solved by the cited literature.
- Prefer the structure: "On [dataset or setting], [specific method variant] will outperform [specific baseline] on [metric] by [expected margin] because [mechanism hypothesis]. Falsification: if the gain is below [threshold], the run does not converge, or the comparison fails under [condition], the hypothesis does not hold."

Reject immediately:
- "Improve robustness" with no measurable setup
- "Explore a new application of method X" with no baseline or metric
- "Verify whether method X works" with no falsification condition
- Any hypothesis that could not be turned into a concrete experiment table

Validation checklist:
- Each hypothesis is testable.
- Novelty, feasibility, and risk are explicit.
- Baseline alternatives are considered.
- Each hypothesis includes a falsification condition.
- Each hypothesis names a concrete baseline, dataset or setting, and metric.
- Each hypothesis explains why the proposed difference is not already covered by existing papers.

When you are unsure:
If you catch yourself writing generic ambition statements instead of measurable hypotheses, stop and anchor the claim to one baseline comparison.

Recover by:
1. Picking the strongest evidence-backed gap.
2. Naming the baseline, dataset, and metric.
3. Writing the falsification rule before polishing the wording.

If the evidence is too weak to support a credible hypothesis set, say so in `audit_notes` instead of manufacturing specificity.

Safety notes:
- Do not optimize for novelty at the cost of falsifiability.
