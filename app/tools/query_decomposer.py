from __future__ import annotations

import json
from typing import Any

from app.providers.base import BaseProvider
from app.tools.base import BaseTool


def fallback_decompose_research_goal(goal: str) -> list[str]:
    cleaned = goal.strip()
    if not cleaned:
      return []
    fragments = [cleaned]
    lower = cleaned.lower()
    if "robust" in lower or "adversarial" in lower:
        fragments.extend(
            [
                f"{cleaned} survey",
                f"{cleaned} benchmark",
                f"{cleaned} reproducibility baseline",
                f"{cleaned} low compute",
            ]
        )
    elif "llm" in lower or "language model" in lower:
        fragments.extend(
            [
                f"{cleaned} evaluation",
                f"{cleaned} benchmark",
                f"{cleaned} alignment safety",
                f"{cleaned} efficient training",
            ]
        )
    else:
        fragments.extend(
            [
                f"{cleaned} survey",
                f"{cleaned} benchmark",
                f"{cleaned} dataset",
                f"{cleaned} baseline",
            ]
        )
    ordered: list[str] = []
    for item in fragments:
        normalized = " ".join(item.split())
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return ordered[:6]


class QueryDecomposerTool(BaseTool):
    name = "query_decomposer"
    description = "Decompose a research goal into complementary literature search queries."
    input_schema = {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
        },
        "required": ["goal"],
    }

    def __init__(self, provider: BaseProvider | None = None, *, model: str | None = None) -> None:
        self.provider = provider
        self.model = model

    async def execute(self, **kwargs) -> dict[str, Any]:
        goal = str(kwargs["goal"]).strip()
        if not goal:
            return {"queries": []}
        if self.provider is None:
            return {"queries": fallback_decompose_research_goal(goal)}

        system_prompt = (
            "Break the research goal into 4-6 complementary literature search queries. "
            "Cover survey, benchmark, method family, failure mode, and low-cost reproduction angle when relevant. "
            "Return JSON with a single key `queries`."
        )
        response_schema = {
            "type": "object",
            "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
            "required": ["queries"],
        }
        try:
            raw = await self.provider.generate(
                system_prompt=system_prompt,
                user_input=json.dumps({"goal": goal}, ensure_ascii=False),
                response_schema=response_schema,
                model=self.model,
            )
            queries = raw.get("queries", [])
        except Exception:
            queries = fallback_decompose_research_goal(goal)
        ordered: list[str] = []
        for query in queries:
            text = str(query).strip()
            if text and text not in ordered:
                ordered.append(text)
        if not ordered:
            ordered = fallback_decompose_research_goal(goal)
        return {"queries": ordered[:6]}
