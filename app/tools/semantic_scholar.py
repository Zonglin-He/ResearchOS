from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.tools.base import BaseTool


def _recency_weight(year: int | None) -> float:
    current_year = datetime.now(timezone.utc).year
    if year is None:
        return 0.3
    return max(0.3, 1.0 - 0.08 * max(0, current_year - int(year)))


def semantic_scholar_score(item: dict) -> float:
    citation_count = int(item.get("citation_count", 0) or 0)
    year = item.get("year")
    try:
        normalized_year = int(year) if year is not None else None
    except (TypeError, ValueError):
        normalized_year = None
    return citation_count * _recency_weight(normalized_year)


def search_semantic_scholar(query: str, limit: int = 10) -> list[dict]:
    encoded = quote(query)
    fields = "title,abstract,authors,year,citationCount,externalIds,url"
    request = Request(
        f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded}&limit={limit}&fields={fields}",
        headers={"User-Agent": "ResearchOS/0.1"},
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    items = []
    for item in payload.get("data", []):
        external_ids = item.get("externalIds", {}) or {}
        items.append(
            {
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "authors": [author.get("name", "") for author in item.get("authors", []) if author.get("name")],
                "year": item.get("year"),
                "citation_count": item.get("citationCount", 0),
                "doi": external_ids.get("DOI"),
                "arxiv_id": external_ids.get("ArXiv"),
                "url": item.get("url", ""),
            }
        )
    items.sort(
        key=lambda item: (
            semantic_scholar_score(item),
            str(item.get("year") or ""),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )
    return items[:limit]


class SemanticScholarSearchTool(BaseTool):
    name = "semantic_scholar_search"
    description = "Search Semantic Scholar for papers with abstracts and citation counts."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs) -> dict:
        return {
            "items": search_semantic_scholar(
                str(kwargs["query"]).strip(),
                limit=max(1, int(kwargs.get("limit", 10))),
            )
        }
