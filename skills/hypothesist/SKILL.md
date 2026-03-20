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
1. Translate gaps into falsifiable hypotheses.
2. Compare alternatives and eliminate weak ideas.
3. State what would confirm or falsify each hypothesis.

Validation checklist:
- Each hypothesis is testable.
- Novelty, feasibility, and risk are explicit.
- Baseline alternatives are considered.

Safety notes:
- Do not optimize for novelty at the cost of falsifiability.
