<!-- Generated from role prompt C:\Anti Project\ResearchOS\prompts\roles\executor.md and skill C:\Anti Project\ResearchOS\skills\executor\SKILL.md. -->
---
name: researchos-executor
description: Thin Codex wrapper for the canonical ResearchOS executor role skill. Use when the task matches the executor role contract.
---

Follow the canonical ResearchOS role skill at `C:\Anti Project\ResearchOS\skills\executor\SKILL.md`.

Required outputs: run_manifest, artifact list
Validation checklist:
- Run manifest includes config, dataset snapshot, seed, and artifacts.
- Failed runs are still recorded honestly.
