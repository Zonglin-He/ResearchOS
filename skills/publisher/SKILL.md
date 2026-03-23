---
name: researchos-publisher
description: Draft sections and papers from frozen evidence and approved claims. Use when the system needs publication-oriented writing that remains traceable to evidence.
---

# ResearchOS Publisher

Use this skill for section drafting, full-paper drafting, and evidence-backed narrative assembly.

Do not use this skill before claims and evidence are stable enough for writing.

Expected inputs:
- frozen_claims
- supporting_artifacts
- writing_scope

Expected outputs:
- section_draft
- paper_draft

Procedure:
1. Choose the requested scope and audience.
2. Translate approved evidence into concise structured prose.
3. Preserve claim-to-evidence traceability for review.

ML paper structure requirements:
- Include Abstract, Introduction, Related Work, Method, Experiments, Conclusion, and Limitations unless the requested scope is narrower.
- If any required section is omitted, explain why in `audit_notes`.
- Abstracts should stay concise, avoid more than 3 contribution claims, and only mention supported results.
- Related Work must explain how prior work differs from or limits the current approach; it is not a citation list.
- Method sections must be detailed enough that a reader could reproduce the setup from the paper plus appendix.
- Experiments must explain baseline choice, main results, and ablations when the evidence supports them.
- Limitations must be substantive and honest, not a one-line disclaimer.

Writing prohibitions:
- Do not write "significantly outperforms" without numbers or an actual significance check.
- Do not write "we propose a novel" without saying what is novel relative to prior work.
- Do not turn Related Work into sentence-by-sentence paper summaries.
- Do not collapse limitations into vague future work language.

Venue-oriented checks:
- If the draft claims significance, make sure the evidence includes the relevant statistical support.
- When the writing scope is a full ML paper, mention compute or training budget, reproducibility materials, and appendix-level hyperparameter detail when those artifacts exist.

Validation checklist:
- Only supported claims appear in the draft.
- Structure matches the requested scope.
- Traceability to claims or artifacts is preserved.
- Numerical claims include numbers.
- Related Work contains comparative framing rather than citation dumping.
- Limitations are specific enough to be useful to a reviewer.

When you are unsure:
If a sentence sounds persuasive but is not directly backed by an approved claim or artifact, cut it or rewrite it with a weaker supported formulation.

Safety notes:
- Do not add unsupported interpretation for rhetorical flow.
