---
name: researchos-archivist
description: Curate durable lessons, archive entries, and provenance links for future reuse. Use when runs or reviews have produced reusable knowledge rather than transient logs.
---

# ResearchOS Archivist

Use this skill after runs, reviews, or verifications when durable memory should be preserved.

Do not use this skill to rewrite artifact contents or store transient debug noise as lessons.

Expected inputs:
- run_summary
- lesson_candidates
- provenance_notes

Expected outputs:
- archive_entry
- lesson_linkage

Procedure:
1. Distill durable lessons from transient logs.
2. Link lessons, artifacts, and provenance references cleanly.
3. Record archive entries that future roles can retrieve.

Validation checklist:
- Durable lessons are separated from transient logs.
- Source references remain intact.
- The archive entry is reusable by future tasks.

Safety notes:
- Do not curate lessons without source linkage when source linkage exists.
