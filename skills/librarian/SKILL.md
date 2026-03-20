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

Validation checklist:
- Paper cards include problem, setting, and task type.
- Source provenance is preserved.
- Unsupported details are marked uncertain instead of guessed.

Safety notes:
- Do not fabricate citations.
- Do not approve a research direction from retrieval alone.
