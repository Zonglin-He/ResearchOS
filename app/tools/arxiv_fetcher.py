from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from app.tools.base import BaseTool

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def search_arxiv(query: str, max_results: int = 20) -> list[dict[str, Any]]:
    normalized_query = query.strip()
    if not normalized_query:
        return []
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{normalized_query}",
            "start": 0,
            "max_results": max(1, max_results),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    url = f"https://export.arxiv.org/api/query?{params}"
    with urllib.request.urlopen(url, timeout=15) as response:
        xml_payload = response.read()

    root = ET.fromstring(xml_payload)
    items: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        entry_id = (entry.findtext("atom:id", default="", namespaces=_ATOM_NS) or "").strip()
        title = " ".join((entry.findtext("atom:title", default="", namespaces=_ATOM_NS) or "").split())
        abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=_ATOM_NS) or "").split())
        published = (entry.findtext("atom:published", default="", namespaces=_ATOM_NS) or "").strip()
        authors = [
            (author.findtext("atom:name", default="", namespaces=_ATOM_NS) or "").strip()
            for author in entry.findall("atom:author", _ATOM_NS)
            if (author.findtext("atom:name", default="", namespaces=_ATOM_NS) or "").strip()
        ]
        arxiv_id = entry_id.rsplit("/", 1)[-1] if entry_id else ""
        pdf_url = ""
        for link in entry.findall("atom:link", _ATOM_NS):
            href = (link.attrib.get("href") or "").strip()
            title_attr = (link.attrib.get("title") or "").strip().lower()
            link_type = (link.attrib.get("type") or "").strip().lower()
            if title_attr == "pdf" or link_type == "application/pdf":
                pdf_url = href
                break
        items.append(
            {
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "arxiv_id": arxiv_id,
                "pdf_url": pdf_url,
                "published": published,
            }
        )
    return items


class ArxivFetcherTool(BaseTool):
    name = "arxiv_fetcher"
    description = "Search arXiv papers and return structured paper candidates."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        query = str(kwargs["query"]).strip()
        max_results = int(kwargs.get("max_results", 20))
        return {"items": search_arxiv(query, max_results=max_results)}
