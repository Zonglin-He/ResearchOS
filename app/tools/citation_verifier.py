from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.tools.base import BaseTool


_ARXIV_ID_PATTERN = re.compile(r"(?:arxiv[:\s]?)(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_DOI_PATTERN = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)

_TITLE_STRIP_PATTERNS = (
    re.compile(r"\barxiv[:\s]?\d{4}\.\d{4,5}(?:v\d+)?\b", re.IGNORECASE),
    re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE),
    re.compile(r"^\[[^\]]+\]\s*"),
    re.compile(r"^\([^)]+\)\s*"),
)


def _extract_arxiv_id(citation: str) -> str | None:
    match = _ARXIV_ID_PATTERN.search(citation)
    if match is not None:
        return match.group(1)
    text = citation.strip()
    if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", text):
        return text
    return None


def _extract_doi(citation: str) -> str | None:
    match = _DOI_PATTERN.search(citation)
    if match is None:
        return None
    return match.group(1).rstrip(").,;")


def _extract_title_hint(citation: str) -> str:
    text = citation.strip()
    for pattern in _TITLE_STRIP_PATTERNS:
        text = pattern.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -,:;.")


def _normalize_title(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, _normalize_title(left), _normalize_title(right)).ratio()


def _request_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "ResearchOS/0.2",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _request_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "ResearchOS/0.2"})
    with urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8", errors="ignore")


def _resolve_arxiv(arxiv_id: str) -> dict[str, Any] | None:
    try:
        body = _request_text(f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}")
        root = ET.fromstring(body)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", namespace)
        if entry is None:
            return None
        title = (entry.findtext("atom:title", default="", namespaces=namespace) or "").strip()
        if not title:
            return None
        return {
            "source": "arxiv",
            "match_type": "identifier",
            "matched_title": title,
            "matched_identifiers": {"arxiv_id": arxiv_id},
            "score": 1.0,
        }
    except Exception:
        return None


def _resolve_crossref_doi(doi: str) -> dict[str, Any] | None:
    try:
        payload = _request_json(f"https://api.crossref.org/works/{quote(doi)}")
        message = payload.get("message", {})
        titles = message.get("title", [])
        title = str(titles[0]).strip() if titles else ""
        if not title:
            return None
        return {
            "source": "crossref",
            "match_type": "identifier",
            "matched_title": title,
            "matched_identifiers": {"doi": doi},
            "score": 1.0,
        }
    except Exception:
        return None


def _resolve_datacite_doi(doi: str) -> dict[str, Any] | None:
    try:
        payload = _request_json(f"https://api.datacite.org/dois/{quote(doi)}")
        attributes = payload.get("data", {}).get("attributes", {})
        titles = attributes.get("titles", [])
        title = ""
        if titles:
            first = titles[0]
            if isinstance(first, dict):
                title = str(first.get("title", "")).strip()
        if not title:
            return None
        return {
            "source": "datacite",
            "match_type": "identifier",
            "matched_title": title,
            "matched_identifiers": {"doi": doi},
            "score": 1.0,
        }
    except Exception:
        return None


def _search_crossref_title(title: str) -> dict[str, Any] | None:
    try:
        payload = _request_json(
            "https://api.crossref.org/works"
            f"?query.title={quote(title)}&rows=3&select=DOI,title"
        )
        for item in payload.get("message", {}).get("items", []):
            titles = item.get("title", [])
            candidate_title = str(titles[0]).strip() if titles else ""
            score = _title_similarity(title, candidate_title)
            if score < 0.88:
                continue
            doi = str(item.get("DOI", "")).strip()
            return {
                "source": "crossref",
                "match_type": "title_search",
                "matched_title": candidate_title,
                "matched_identifiers": {"doi": doi} if doi else {},
                "score": score,
            }
    except Exception:
        return None
    return None


def _search_semantic_scholar_title(title: str) -> dict[str, Any] | None:
    try:
        payload = _request_json(
            "https://api.semanticscholar.org/graph/v1/paper/search"
            f"?query={quote(title)}&limit=3&fields=title,externalIds"
        )
        for item in payload.get("data", []):
            candidate_title = str(item.get("title", "")).strip()
            score = _title_similarity(title, candidate_title)
            if score < 0.88:
                continue
            external_ids = item.get("externalIds", {}) if isinstance(item.get("externalIds"), dict) else {}
            matched_identifiers = {
                key.lower(): str(value).strip()
                for key, value in external_ids.items()
                if str(value).strip()
            }
            return {
                "source": "semantic_scholar",
                "match_type": "title_search",
                "matched_title": candidate_title,
                "matched_identifiers": matched_identifiers,
                "score": score,
            }
    except Exception:
        return None
    return None


def _search_openalex_title(title: str) -> dict[str, Any] | None:
    try:
        payload = _request_json(
            f"https://api.openalex.org/works?search={quote(title)}&per-page=3"
        )
        for item in payload.get("results", []):
            candidate_title = str(item.get("title", "")).strip()
            score = _title_similarity(title, candidate_title)
            if score < 0.88:
                continue
            doi = str(item.get("doi", "")).strip()
            return {
                "source": "openalex",
                "match_type": "title_search",
                "matched_title": candidate_title,
                "matched_identifiers": {"doi": doi.removeprefix("https://doi.org/")} if doi else {},
                "score": score,
            }
    except Exception:
        return None
    return None


def verify_citation(citation: str) -> dict[str, Any]:
    text = citation.strip()
    arxiv_id = _extract_arxiv_id(text)
    doi = _extract_doi(text)
    title_hint = _extract_title_hint(text)

    matches: list[dict[str, Any]] = []
    if arxiv_id:
        match = _resolve_arxiv(arxiv_id)
        if match is not None:
            matches.append(match)
    if doi:
        for resolver in (_resolve_crossref_doi, _resolve_datacite_doi):
            match = resolver(doi)
            if match is not None:
                matches.append(match)

    if not matches and title_hint:
        for resolver in (_search_crossref_title, _search_semantic_scholar_title, _search_openalex_title):
            match = resolver(title_hint)
            if match is not None:
                matches.append(match)

    unique_sources = list(dict.fromkeys(match["source"] for match in matches))
    matched_title = next(
        (match["matched_title"] for match in matches if str(match.get("matched_title", "")).strip()),
        "",
    )
    matched_identifiers: dict[str, str] = {}
    for match in matches:
        identifiers = match.get("matched_identifiers", {})
        if not isinstance(identifiers, dict):
            continue
        for key, value in identifiers.items():
            text_value = str(value).strip()
            if text_value and key not in matched_identifiers:
                matched_identifiers[str(key)] = text_value

    if any(match.get("match_type") == "identifier" for match in matches):
        confidence = "high"
    elif len(unique_sources) >= 2:
        confidence = "medium"
    elif matches:
        confidence = "low"
    else:
        confidence = "none"

    if matches:
        status = "verified"
        notes = (
            "Verified via "
            + ", ".join(unique_sources)
            + (" using direct identifiers." if confidence == "high" else " using title matching.")
        )
    else:
        status = "unresolved"
        notes = "No authoritative match found in arXiv, Crossref, DataCite, Semantic Scholar, or OpenAlex."

    return {
        "citation": text,
        "status": status,
        "confidence": confidence,
        "sources_hit": unique_sources,
        "matched_title": matched_title,
        "matched_identifiers": matched_identifiers,
        "notes": notes,
    }


def verify_citations(
    citations: list[str],
    *,
    resolver: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    valid: list[str] = []
    hallucinated: list[str] = []
    details: list[dict[str, Any]] = []
    resolve = resolver or verify_citation

    for citation in citations:
        text = citation.strip()
        if not text:
            continue
        try:
            detail = resolve(text)
        except Exception:
            detail = {
                "citation": text,
                "status": "unresolved",
                "confidence": "none",
                "sources_hit": [],
                "matched_title": "",
                "matched_identifiers": {},
                "notes": "Citation verification raised an unexpected error.",
            }
        if detail.get("status") == "verified":
            valid.append(text)
        else:
            hallucinated.append(text)
        details.append(detail)

    sources_used = list(
        dict.fromkeys(
            source
            for detail in details
            for source in detail.get("sources_hit", [])
            if str(source).strip()
        )
    )
    return {
        "valid": valid,
        "hallucinated": hallucinated,
        "details": details,
        "summary": {
            "total": len(details),
            "verified_count": len(valid),
            "unresolved_count": len(hallucinated),
            "sources_used": sources_used,
        },
    }


class CitationVerifierTool(BaseTool):
    name = "citation_verifier"
    description = (
        "Verify whether cited papers can be resolved through arXiv, Crossref, "
        "DataCite, Semantic Scholar, or OpenAlex."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "citations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["citations"],
    }

    async def execute(self, **kwargs) -> dict:
        return verify_citations([str(item) for item in kwargs.get("citations", [])])
