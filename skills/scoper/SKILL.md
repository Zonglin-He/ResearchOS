---
name: researchos-scoper
description: Decompose research problems into bounded question trees, actionable first tasks, and dependency-aware plans. Use when a project or task needs scope clarification, task decomposition, or a research question tree.
---

# ResearchOS Scoper

Use this skill when a topic is broad, ambiguous, or not yet broken into tractable work.

Do not use this skill for experiment execution, writing polish, or archival curation.

Expected inputs:
- topic
- constraints
- current evidence

Expected outputs:
- research_question_tree
- task_decomposition

Procedure:
1. State the core question and operator constraints.
2. Split the question into answerable subquestions.
3. Mark blockers, dependencies, and the first actionable task.

Validation checklist:
- Each subquestion is independently actionable.
- Assumptions and missing evidence are explicit.
- The recommended first task is feasible now.

Safety notes:
- Do not invent evidence.
- Escalate if the topic remains ambiguous after one clarification pass.
