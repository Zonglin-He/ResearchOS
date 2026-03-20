<!-- Generated from role prompt C:\Anti Project\ResearchOS\prompts\roles\scoper.md and skill C:\Anti Project\ResearchOS\skills\scoper\SKILL.md. -->
---
name: researchos-scoper
description: Thin Codex wrapper for the canonical ResearchOS scoper role skill. Use when the task matches the scoper role contract.
---

Follow the canonical ResearchOS role skill at `C:\Anti Project\ResearchOS\skills\scoper\SKILL.md`.

Required outputs: research_question_tree, task_decomposition
Validation checklist:
- Every subquestion is independently testable.
- The first task can run without hidden prerequisites.
