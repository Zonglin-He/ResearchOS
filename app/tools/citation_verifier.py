from __future__ import annotations

import json
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.tools.base import BaseTool


_ARXIV_ID_PATTERN = re.compile(r"(?:arxiv[:\s]?)(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)


def _extract_arxiv_id(citation: str) -> str | None:
    match = _ARXIV_ID_PATTERN.search(citation)
    if match is not None:
        return match.group(1)
    text = citation.strip()
    if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", text):
        return text
    return None


def _check_arxiv_exists(arxiv_id: str) -> bool:
    request = Request(
        f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}",
        headers={"User-Agent": "ResearchOS/0.1"},
    )
    with urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", errors="ignore")
    return arxiv_id in body


def _check_semantic_scholar(title: str) -> bool:
    request = Request(
        f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(title)}&limit=1&fields=title",
        headers={"User-Agent": "ResearchOS/0.1"},
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return bool(payload.get("data"))


def verify_citations(citations: list[str]) -> dict[str, list[str]]:
    valid: list[str] = []
    hallucinated: list[str] = []
    for citation in citations:
        text = citation.strip()
        if not text:
            continue
        try:
            arxiv_id = _extract_arxiv_id(text)
            exists = _check_arxiv_exists(arxiv_id) if arxiv_id is not None else _check_semantic_scholar(text)
        except Exception:
            exists = False
        (valid if exists else hallucinated).append(text)
    return {"valid": valid, "hallucinated": hallucinated}


class CitationVerifierTool(BaseTool):
    name = "citation_verifier"
    description = "Verify whether cited papers exist on arXiv or Semantic Scholar."
    input_schema = {
        "type": "object",
        "properties": {
            "citations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["citations"],
    }

    async def execute(self, **kwargs) -> dict:
        return verify_citations([str(item) for item in kwargs.get("citations", [])])
