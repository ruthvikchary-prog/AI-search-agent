"""Authoritative scholarly metadata enrichment.

The service is deliberately best-effort: missing metadata is returned as None,
never synthesized from a URL or search-result date.
"""

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


def _year(value: Any) -> Optional[int]:
    match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    return int(match.group(0)) if match else None


def _crossref(url: str, title: str) -> Dict[str, Any]:
    doi = ""
    if "doi.org/" in url:
        doi = url.split("doi.org/", 1)[1].split("?", 1)[0].strip("/")
    endpoint = f"https://api.crossref.org/works/{quote(doi, safe='')}" if doi else (
        f"https://api.crossref.org/works?query.bibliographic={quote(title)}&rows=1"
    )
    response = requests.get(
        endpoint,
        timeout=8,
        headers={"User-Agent": "AcademicResearchAssistant/1.0 (mailto:research@example.invalid)"},
    )
    response.raise_for_status()
    payload = response.json().get("message", {})
    if "items" in payload:
        payload = (payload.get("items") or [{}])[0]
        candidate_title = (payload.get("title") or [""])[0]
        expected = set(re.findall(r"[a-z0-9]{4,}", title.lower()))
        actual = set(re.findall(r"[a-z0-9]{4,}", candidate_title.lower()))
        overlap = len(expected & actual) / max(len(expected), 1)
        if overlap < 0.6:
            return {}
    authors = [
        " ".join(filter(None, [author.get("given"), author.get("family")]))
        for author in payload.get("author", [])
    ]
    return {
        "title": (payload.get("title") or [None])[0],
        "authors": [author for author in authors if author],
        "year": _year((payload.get("published-print") or payload.get("published-online") or {}).get("date-parts", [[]])[0]),
        "venue": (payload.get("container-title") or [None])[0],
        "doi": payload.get("DOI"),
        "url": payload.get("URL") or url,
        "abstract": payload.get("abstract"),
        "provider": "crossref",
    }


def _arxiv(url: str) -> Dict[str, Any]:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?/#]+)", url, re.I)
    if not match:
        return {}
    arxiv_id = match.group(1).removesuffix(".pdf")
    response = requests.get(
        f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}",
        timeout=8,
        headers={"User-Agent": "AcademicResearchAssistant/1.0"},
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        return {}
    title = (entry.findtext("atom:title", default="", namespaces=namespace) or "").strip()
    authors = [
        (node.findtext("atom:name", default="", namespaces=namespace) or "").strip()
        for node in entry.findall("atom:author", namespace)
    ]
    published = entry.findtext("atom:published", default="", namespaces=namespace)
    abstract = entry.findtext("atom:summary", default="", namespaces=namespace)
    return {
        "title": re.sub(r"\s+", " ", title),
        "authors": [author for author in authors if author],
        "year": _year(published),
        "abstract": re.sub(r"\s+", " ", abstract).strip() or None,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "provider": "arxiv",
    }


def enrich_source_metadata(url: str, title: str) -> Dict[str, Any]:
    """Return verified metadata from public scholarly registries when available."""
    if not url and not title:
        return {"metadata_status": "unavailable"}
    try:
        if "arxiv.org/" in url.lower():
            metadata = _arxiv(url)
            metadata["metadata_status"] = "verified" if metadata.get("title") else "unavailable"
            return metadata
        metadata = _crossref(url, title)
        metadata["metadata_status"] = "verified" if metadata.get("title") else "unavailable"
        return metadata
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {"metadata_status": "unavailable"}
