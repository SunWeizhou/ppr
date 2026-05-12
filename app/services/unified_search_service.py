"""Unified paper search across arXiv and Semantic Scholar."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable


SEMANTIC_FIELDS = ",".join([
    "title",
    "authors",
    "year",
    "venue",
    "abstract",
    "url",
    "externalIds",
    "citationCount",
    "referenceCount",
    "openAccessPdf",
])


def _clean_arxiv_id(value: str) -> str:
    value = str(value or "").strip()
    value = value.replace("arxiv:", "").replace("arXiv:", "")
    return re.sub(r"v\d+$", "", value)


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _paper_key(paper: dict) -> str:
    external = paper.get("external_ids") or {}
    doi = str(external.get("DOI") or external.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    arxiv_id = _clean_arxiv_id(external.get("ArXiv") or external.get("arxiv") or "")
    if arxiv_id:
        return f"arxiv:{arxiv_id.lower()}"
    title = _normalize_title(paper.get("title", ""))
    return f"title:{title}" if title else f"id:{paper.get('paper_id', '')}"


def normalize_arxiv_paper(paper: dict) -> dict:
    paper_id = _clean_arxiv_id(paper.get("paper_id") or paper.get("id") or "")
    authors = paper.get("authors") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in authors.split(",") if part.strip()]
    abstract = paper.get("abstract") or paper.get("summary") or ""
    published = str(
        paper.get("published_at")
        or paper.get("published")
        or paper.get("updated")
        or paper.get("date")
        or ""
    )
    year = published[:4] if published[:4].isdigit() else ""
    link = paper.get("link") or paper.get("source_url") or (f"https://arxiv.org/abs/{paper_id}" if paper_id else "")
    return {
        "paper_id": f"arxiv:{paper_id}" if paper_id else str(paper.get("id", "")),
        "id": f"arxiv:{paper_id}" if paper_id else str(paper.get("id", "")),
        "source": "arxiv",
        "title": paper.get("title", ""),
        "authors": authors,
        "year": year,
        "venue": "arXiv",
        "abstract": abstract,
        "summary": abstract,
        "published_at": published,
        "url": link,
        "link": link,
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}" if paper_id else "",
        "citation_count": None,
        "reference_count": None,
        "external_ids": {"ArXiv": paper_id} if paper_id else {},
        "categories": paper.get("categories") or [],
        "score": paper.get("score", 0),
        "relevance_reason": paper.get("relevance_reason") or paper.get("relevance") or "arXiv match",
    }


def normalize_semantic_paper(paper: dict) -> dict:
    external = paper.get("externalIds") or {}
    arxiv_id = _clean_arxiv_id(external.get("ArXiv") or "")
    semantic_id = str(paper.get("paperId") or "").strip()
    authors = [
        author.get("name", "")
        for author in (paper.get("authors") or [])
        if isinstance(author, dict) and author.get("name")
    ]
    pdf = paper.get("openAccessPdf") or {}
    paper_id = f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{semantic_id}"
    return {
        "paper_id": paper_id,
        "id": paper_id,
        "source": "semantic_scholar",
        "title": paper.get("title", ""),
        "authors": authors,
        "year": str(paper.get("year") or ""),
        "venue": paper.get("venue") or "Semantic Scholar",
        "abstract": paper.get("abstract") or "",
        "summary": paper.get("abstract") or "",
        "url": paper.get("url") or "",
        "link": paper.get("url") or "",
        "pdf_url": pdf.get("url") if isinstance(pdf, dict) else "",
        "citation_count": paper.get("citationCount"),
        "reference_count": paper.get("referenceCount"),
        "external_ids": external,
        "categories": [],
        "score": 0,
        "relevance_reason": "Semantic Scholar match",
    }


def search_arxiv(query: str, *, max_results: int = 25, search_fn: Callable | None = None) -> list[dict]:
    terms = [part for part in re.split(r"[\s,]+", query.strip()) if part]
    if not terms:
        return []
    if search_fn is None:
        from arxiv_recommender_v5 import search_by_keywords

        search_fn = search_by_keywords
    return [normalize_arxiv_paper(paper) for paper in search_fn(terms, max_results=max_results, days_back=365)]


def search_semantic_scholar(query: str, *, max_results: int = 25, opener=None) -> list[dict]:
    if opener is None:
        opener = urllib.request.urlopen
    params = urllib.parse.urlencode({
        "query": query,
        "limit": max_results,
        "fields": SEMANTIC_FIELDS,
    })
    request = urllib.request.Request(
        f"https://api.semanticscholar.org/graph/v1/paper/search?{params}",
        headers={"User-Agent": "PaperAgent/1.0"},
        method="GET",
    )
    with opener(request, timeout=20) as response:  # nosec B310 - fixed HTTPS Semantic Scholar API endpoint
        payload = json.loads(response.read().decode("utf-8"))
    return [normalize_semantic_paper(paper) for paper in payload.get("data", [])]


def merge_and_dedupe_papers(papers: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for paper in papers:
        key = _paper_key(paper)
        if key not in merged:
            merged[key] = dict(paper)
            order.append(key)
            continue
        existing = merged[key]
        sources = {part.strip() for part in str(existing.get("source", "")).split("+") if part.strip()}
        sources.add(str(paper.get("source", "")).strip())
        existing["source"] = " + ".join(sorted(sources))
        for field in (
            "title",
            "authors",
            "year",
            "venue",
            "abstract",
            "summary",
            "url",
            "link",
            "pdf_url",
            "citation_count",
            "reference_count",
            "categories",
            "score",
            "relevance_reason",
        ):
            if existing.get(field) in (None, "", [], 0) and paper.get(field) not in (None, "", []):
                existing[field] = paper.get(field)
        existing_ids = dict(existing.get("external_ids") or {})
        existing_ids.update(paper.get("external_ids") or {})
        existing["external_ids"] = existing_ids
    return [merged[key] for key in order]


def search_papers(
    query: str,
    *,
    max_results: int = 25,
    arxiv_fn: Callable | None = None,
    semantic_fn: Callable | None = None,
) -> dict:
    query = str(query or "").strip()
    if not query:
        return {"papers": [], "warnings": [], "errors": [], "sources": {}}
    semantic_fn = semantic_fn or search_semantic_scholar
    source_jobs = {
        "arxiv": lambda: search_arxiv(query, max_results=max_results, search_fn=arxiv_fn),
        "semantic_scholar": lambda: semantic_fn(query, max_results=max_results),
    }
    papers: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    sources: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(job): name for name, job in source_jobs.items()}
        for future in as_completed(futures):
            source = futures[future]
            try:
                source_papers = future.result()
                sources[source] = "ok"
                papers.extend(source_papers)
            except Exception as exc:
                sources[source] = "failed"
                if source == "semantic_scholar":
                    text = "Semantic Scholar is temporarily unavailable. Showing arXiv results."
                elif source == "arxiv":
                    text = "arXiv is temporarily unavailable. Showing Semantic Scholar results."
                else:
                    text = f"{source} unavailable: {exc}"
                warnings.append(text)
                errors.append(f"{source} unavailable: {exc}")
    return {
        "papers": merge_and_dedupe_papers(papers)[:max_results],
        "warnings": warnings,
        "errors": errors if not papers else [],
        "sources": sources,
    }
