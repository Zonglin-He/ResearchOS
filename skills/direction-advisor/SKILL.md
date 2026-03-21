---
name: research-direction-advisor
description: Discuss candidate research directions at the human_select stage. Use when the operator needs a grounded explanation of what an idea means, whether it is feasible, and what should be checked before topic freeze.
---

# Research Direction Advisor

Use this skill when a project has already produced a `gap_map` and ranked candidates, and the next action is a human decision.

Do not use this skill for literature retrieval, experiment execution, or long-form paper writing.

Expected inputs:
- topic
- one selected gap / candidate
- supporting paper cards
- operator follow-up question

Expected outputs:
- plain-language explanation of the idea
- grounded feasibility judgment
- next checks before topic freeze
- a sharp research-question suggestion

Procedure:
1. Restate the selected gap in plain language.
2. Ground the idea in the provided paper cards only.
3. Judge feasibility across five axes: evidence strength, baseline burden, implementation cost, reproducibility risk, and review risk.
4. Answer the operator's latest concern directly before expanding.
5. End with the minimum next checks needed to decide whether to continue.

Validation checklist:
- The assistant explains what the idea is, not just its label.
- Every claimed paper reference appears in the provided evidence.
- Risks mention concrete blockers such as missing baselines, vague metrics, or compute burden.
- The suggested research question is testable in a bounded experiment cycle.

Read `references/research_checks.md` when you need the ResearchOS-specific evaluation frame.
Read `references/openai_prompt_notes.md` when tuning or updating this skill/prompt pair.
