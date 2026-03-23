---
name: researchos-librarian
description: Retrieve, screen, and normalize sources into ResearchOS paper cards. Use when a task needs literature search, source filtering, or structured paper-card extraction.
---

# ResearchOS Librarian

Use this skill for search-and-screen workflows that must end in paper cards.

Do not use this skill for hypothesis generation, execution, or publication drafting.

Expected inputs:
- topic
- source material or search scope
- screening criteria

Expected outputs:
- paper_card
- screening_notes

Procedure:
1. Search or parse candidate sources.
2. Screen for direct relevance and extract concrete evidence.
3. Emit paper cards with evidence refs and explicit uncertainties.

Screening rejection rules:
- REJECT sources whose `paper_id` looks like a fragment rather than a paper, including values containing `/table-`, `/figure-`, `/eq-`, or `/appendix`.
- REJECT sources whose title begins with `Table `, `Figure `, `Fig. `, or `Eq. `.
- REJECT sources that have no abstract and whose title is only a figure or table caption.
- REJECT Semantic Scholar candidates with `citation_count = 0` and `year < 2020` unless the result is clearly the only directly relevant paper in the niche.

Paper-card quality requirements:
- `problem` must state what research problem the paper solves.
- `method_summary` must say what was actually done, not "the paper proposes a new method".
- Include at least one `strongest_result` with a concrete number or measurable outcome, not "improves performance".
- Preserve source provenance for every concrete claim.

Encoding and text-quality handling:
- If the title or abstract contains garbled text, mojibake, or an unexpected language outside English or Chinese, do not promote that raw text into core paper-card fields.
- Record `encoding_issue: source text contains garbled or unexpected-language content` in `uncertainties`.
- Skip the corrupted field rather than guessing what it meant.

Validation checklist:
- Paper cards include problem, setting, and task type.
- Source provenance is preserved.
- Unsupported details are marked uncertain instead of guessed.
- Rejected non-paper fragments are not turned into paper cards.
- Method summaries are concrete enough that another agent can tell what the paper actually did.
- Strongest results use numbers when the source provides them.

When you are unsure:
If you catch yourself filling a paper card with generic phrases such as "proposes a novel approach" or "shows promising results", stop and go back to the source.

Recover by:
1. Extracting one concrete fact from the source.
2. Using that fact to write the `problem`, `method_summary`, or `strongest_result`.
3. Marking missing details as uncertain instead of smoothing over them.

If the source quality is too poor to support a reliable paper card, do not force completeness. Record the limitation in `audit_notes` when available; otherwise place it in `uncertainties` or `screening_notes`.

Safety notes:
- Do not fabricate citations.
- Do not approve a research direction from retrieval alone.
