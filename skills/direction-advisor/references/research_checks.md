# ResearchOS Direction Checks

Use these checks when discussing whether a candidate idea should advance from `human_select` to `topic freeze`.

## What the operator needs

The operator usually wants four things:
- What the idea actually means in plain language.
- Whether the current evidence base is strong enough.
- Whether the idea is practical under time, compute, baseline, and reproducibility constraints.
- What single question should be frozen if the project continues.

## Minimum evaluation frame

Assess each candidate across:
- Evidence strength: are the supporting paper cards concrete enough to ground a real experiment?
- Baseline burden: do we already know the baselines, dataset, and metric, or would those still need fresh research?
- Implementation cost: is the direction lightweight, moderate, or heavy to build?
- Reproducibility risk: are there likely hidden dependencies, dataset quirks, or missing protocol details?
- Review risk: would a reviewer likely reject this because the novelty is weak, comparisons are unfair, or claims are too broad?

## Preferred answer shape

The best answer usually includes:
- One short paragraph that explains the idea and answers the operator's latest question.
- 2-4 strengths.
- 2-4 risks.
- 2-4 next checks.
- One research-question suggestion that is narrow enough for the next frozen step.

## Hard constraints

- Do not invent new papers.
- Do not cite papers that are not in the provided evidence.
- Do not promise that downstream execution will succeed.
- If evidence is thin, say so directly and recommend a bounded next check.
