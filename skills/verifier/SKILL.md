---
name: researchos-verifier
description: Verify evidence chains and methodological validity using recorded ResearchOS artifacts and registries. Use when claims, runs, or freezes require an honest verification report.
---

# ResearchOS Verifier

Use this skill for evidence-link and method-validity checks that must stay inside what the system actually knows.

Do not use this skill to fake citation validation or deep checks that were not performed.

Expected inputs:
- run_manifest
- claims
- freeze_state

Expected outputs:
- verification_report

Procedure:
1. Map each claim or result to recorded evidence.
2. Check completeness, missing links, and methodological red flags.
3. Emit status plus concrete remediation steps.

Validation checklist:
- Verification scope is explicit.
- Missing evidence is recorded as missing.
- Recommendations map to concrete evidence gaps.

Safety notes:
- Never claim verification beyond available evidence.
