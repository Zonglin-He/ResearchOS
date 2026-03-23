from __future__ import annotations

import json
from typing import Any

from app.providers.base import BaseProvider
from app.tools.base import BaseTool
from app.tools.arxiv_fetcher import search_arxiv
from app.tools.semantic_scholar import search_semantic_scholar


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


def broaden_query(query: str) -> str:
    noise_terms = {
        "survey",
        "benchmark",
        "reproducibility",
        "baseline",
        "low",
        "compute",
        "efficient",
        "training",
        "2024",
        "2025",
        "2026",
    }
    tokens = [token for token in query.replace("-", " ").split() if token]
    reduced = [token for token in tokens if token.lower() not in noise_terms]
    if len(reduced) >= 3:
        return " ".join(reduced[:5])
    if len(tokens) >= 3:
        return " ".join(tokens[:4])
    return query.strip()


def query_hit_count(query: str, *, probe_limit: int = 3) -> int:
    total = 0
    try:
        total += len(search_semantic_scholar(query, limit=probe_limit))
    except Exception:
        pass
    try:
        total += len(search_arxiv(query, max_results=probe_limit))
    except Exception:
        pass
    return total


def validate_queries(
    queries: list[str],
    *,
    min_papers_per_query: int = 3,
) -> list[str]:
    validated: list[str] = []
    for query in queries:
        candidate = query.strip()
        if not candidate:
            continue
        chosen = _broaden_until_hit(
            candidate,
            min_papers=min_papers_per_query,
            max_rounds=3,
        )
        if chosen not in validated:
            validated.append(chosen)
    return validated[:6]


def _broaden_until_hit(query: str, *, min_papers: int, max_rounds: int = 3) -> str:
    current = query.strip()
    for _ in range(max_rounds):
        if not current or query_hit_count(current) >= min_papers:
            return current
        broader = broaden_query(current)
        if not broader or broader == current:
            break
        current = broader
    return current


class QueryDecomposerTool(BaseTool):
    name = "query_decomposer"
    description = "Decompose a research goal into complementary literature search queries."
    input_schema = {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "min_papers_per_query": {"type": "integer"},
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
        min_papers_per_query = max(1, int(kwargs.get("min_papers_per_query", 3)))
        if self.provider is None:
            return {
                "queries": validate_queries(
                    fallback_decompose_research_goal(goal),
                    min_papers_per_query=min_papers_per_query,
                )
            }

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
        return {
            "queries": validate_queries(
                ordered[:6],
                min_papers_per_query=min_papers_per_query,
            )
        }
