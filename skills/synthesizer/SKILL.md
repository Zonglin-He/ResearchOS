---
name: researchos-synthesizer
description: Aggregate paper cards into gap maps, claim clusters, and ranked directions. Use when multiple sources need structured synthesis rather than raw retrieval.
---

# ResearchOS Synthesizer

Use this skill when evidence from multiple sources must be clustered into gaps or claim groups.

Do not use this skill when there is no usable evidence base yet.

Expected inputs:
- paper_cards
- topic
- constraints

Expected outputs:
- gap_map
- claim_clusters

Procedure:
1. Group evidence by theme, attack surface, or disagreement.
2. Separate observed gaps from speculative opportunities.
3. Rank candidate directions with explicit rationale.

Validation checklist:
- Each gap links to supporting papers when available.
- Novelty, difficulty, and uncertainty remain explicit.
- Contradictions are not flattened into fake consensus.

Safety notes:
- Do not suppress contradictory evidence.
