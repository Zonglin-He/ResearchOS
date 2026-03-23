---
name: researchos-reviewer
description: Review artifacts for completeness, consistency, and blocking issues. Use when deliverables need a structured pass/fail/revise style review.
---

# ResearchOS Reviewer

Use this skill for quality review before approval, publication, or downstream reuse.

Do not use this skill for source retrieval or archival curation.

Expected inputs:
- artifacts
- claims
- review_scope

Expected outputs:
- review_report

Procedure:
1. Check required artifacts against task obligations.
2. List blocking issues, missing evidence, and consistency failures.
3. Emit a decision with rationale and follow-up expectations.

ML experiment review standards:
- Treat any fairness or evaluation leak below as a blocking issue.
- Treat reproducibility gaps as at least warnings, and escalate them when they undermine the main claim.

Blocking checks for experimental fairness:
- The proposed method and the baseline use the same dataset split.
- If augmentation is used, the comparison explains whether the baseline received the same augmentation budget.
- The test set was not used for hyperparameter selection, early stopping decisions, or manual tuning.

Blocking checks for metric validity:
- If the dataset is imbalanced, do not accept plain accuracy alone; require F1, balanced accuracy, or another class-aware metric.
- If a "best accuracy" is reported, check whether it comes from a cherry-picked epoch rather than a predeclared selection rule.
- If a claimed gain depends on a changed evaluation protocol, mark it blocking until the comparison is normalized.

Warnings for reproducibility:
- Check whether the random seed is fixed and recorded.
- Check whether key hyperparameters such as learning rate, batch size, optimizer, and training epochs are recorded.
- Check whether the result is based on a single run or repeated runs.

Validation checklist:
- Decision and blocking issues are explicit.
- Missing baselines or evidence are flagged.
- Rationale is concise and actionable.
- Blocking issues are concrete enough to reproduce and fix.
- Warnings are kept separate from blockers.
- The review does not soften protocol violations into vague prose.

When you are unsure:
If you catch yourself writing "looks reasonable" or "appears fine" without checking protocol comparability, stop and verify the comparison basis.

Recover by:
1. Verifying the data split, augmentation policy, and metric definition.
2. Verifying how the reported epoch or checkpoint was selected.
3. Recording unresolved uncertainty in `audit_notes` when available; otherwise place it in the review rationale instead of inventing confidence.

Safety notes:
- Do not soften critical issues into vague prose.
