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

Verification actions:
- To verify a claim about a result:
- Find the referenced `run_id` in the run manifest or registry.
- Find the cited metric or number in that run's recorded metrics.
- Compare the claim text against the recorded value.
- If the numbers do not match, mark it `BLOCKING`.
- If the run manifest does not exist, mark it `UNVERIFIED`, not `PASS`.
- To verify a citation:
- Check whether the cited `paper_id` exists in the paper-card registry.
- If it exists, mark the citation as found.
- If it does not exist, mark it `UNVERIFIED`.
- Do not claim you verified the paper's contents; only verify registry presence unless stronger local evidence exists.

Out of scope for verification:
- Whether a paper's interpretation is correct when the full paper content is not locally verified
- Whether the experiment is truly reproducible without rerunning it
- Whether baseline selection was fair; that belongs to Reviewer

Validation checklist:
- Verification scope is explicit.
- Missing evidence is recorded as missing.
- Recommendations map to concrete evidence gaps.
- Claims and numbers are checked against local run records, not memory.
- Citations are only verified to the level the registry allows.

When you are unsure:
If you cannot trace a statement to a local artifact or registry entry, do not upgrade it into a pass.

Safety notes:
- Never claim verification beyond available evidence.
