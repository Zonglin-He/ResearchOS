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

Gap-writing standard:
- Every gap description must name a concrete method, setting, or paper cluster.
- Every gap description must explain why existing papers have not solved the problem yet.
- Every gap description must cite at least one concrete finding from the supporting evidence.
- Prefer the structure: "Although [specific method or paper cluster] achieved [specific result] under [specific condition], it has not been tested or does not hold under [missing condition or scenario]. This matters because [technical reason or application value]. Evidence from [paper A / paper_id] and [paper B / paper_id] points to this gap through [specific findings]."

Hard constraints:
- FORBIDDEN: Copying or lightly paraphrasing abstract text as a gap description.
- FORBIDDEN: Using filler templates such as "Investigate limitations around ..." or "Explore potential improvements to ...".
- FORBIDDEN: Leaving `gap_id` empty.
- FORBIDDEN: Setting `cluster_name` to `?`, empty, or another placeholder.
- REQUIRED: Every gap must state why existing papers do not already solve it.
- REQUIRED: `supporting_papers` must contain at least 2 concrete `paper_id` values when a gap is emitted.
- REQUIRED: `novelty_score` must have an explicit rationale tied to evidence, not a free-floating number.

Bad outputs to reject:
- "Investigate limitations or underexplored extensions around [abstract text]"
- "Explore potential improvements to [method name]"
- A description that mostly repeats one paper's abstract without synthesis
- A gap entry with `cluster_name: "?"`

Good output shape:
- "PGD adversarial training reaches strong robustness on CIFAR-10, but papers in this cluster do not test robustness under distribution shift such as CIFAR-10-C or transfer settings. This matters because the training objective assumes the training distribution is stable. `arxiv:2103.15670` shows robustness drops sharply once that assumption breaks, while `arxiv:2002.11569` suggests augmentation-based distribution expansion may partially close the gap."

Validation checklist:
- Each gap links to supporting papers when available.
- Novelty, difficulty, and uncertainty remain explicit.
- Contradictions are not flattened into fake consensus.
- Check that each gap description contains at least one concrete finding from a specific paper.
- Check that `cluster_name` is a meaningful research topic label.
- Check that `novelty_score` has a rationale.
- Check that `supporting_papers` contains real `paper_id` values rather than placeholders or an empty list.
- Check that the final gap set is not just the same sentence pattern repeated with different nouns.

When you are unsure:
If you catch yourself writing generic language such as "investigate limitations", "explore potential", or "this could improve", stop. That is a low-quality signal.

Recover by:
1. Going back to the input evidence.
2. Pulling the most concrete fact available, ideally a numeric result or an explicit negative finding.
3. Rewriting the gap from that fact, including why the current literature leaves it unresolved.

If the evidence base is too weak to support a real gap map, do not force one. Record that the evidence is insufficient in `audit_notes` when available; otherwise put the same note in the nearest uncertainty field.

Safety notes:
- Do not suppress contradictory evidence.
