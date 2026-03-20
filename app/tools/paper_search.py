from __future__ import annotations

import json
from urllib.parse import quote
from urllib.request import urlopen

from app.tools.base import BaseTool


class PaperSearchTool(BaseTool):
    name = "paper_search"
    description = "Search papers using the Crossref API."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs) -> dict:
        query = quote(kwargs["query"])
        limit = kwargs.get("limit", 5)
        with urlopen(
            f"https://api.crossref.org/works?query={query}&rows={limit}",
            timeout=10,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

        items = payload.get("message", {}).get("items", [])
        return {
            "items": [
                {
                    "title": item.get("title", [""])[0],
                    "doi": item.get("DOI"),
                    "published": item.get("created", {}).get("date-time"),
                }
                for item in items
            ]
        }
