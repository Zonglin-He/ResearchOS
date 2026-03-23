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

What qualifies as a durable lesson:
- The failure is likely to recur under similar conditions.
- The success depends on conditions that can be transferred to later tasks.
- A previous judgment standard turned out to be wrong and should be corrected for future work.

Do not save as lessons:
- One-off runtime logs such as "this run took 3 hours"
- Provider or infrastructure incidents such as temporary rate limits
- Single-run observations with no reusable decision value

Lesson quality rule:
- `lesson.summary` should answer: "Next time we face [same condition], do [specific action], because [evidence from this run or review]."
- If you cannot write that sentence, the item is probably not durable enough to archive as a lesson.

Validation checklist:
- Durable lessons are separated from transient logs.
- Source references remain intact.
- The archive entry is reusable by future tasks.
- Each saved lesson contains an actionable takeaway, not just a diary note.

When you are unsure:
If an item sounds like a timestamped incident report rather than a reusable rule, keep it out of lessons and leave it in raw provenance instead.

Safety notes:
- Do not curate lessons without source linkage when source linkage exists.
