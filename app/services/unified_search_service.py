"""Unified paper search across arXiv, Semantic Scholar, and OpenAlex."""

from __future__ import annotations

import json
import os
import re
import threading
import time
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

# OpenAlex config
OPENALEX_BASE = "https://api.openalex.org/works"
OPENALEX_MAILTO = os.environ.get("OPENALEX_MAILTO", "")

# Semantic Scholar failure cache
_s2_failure_cache: dict[str, float] = {}
S2_FAILURE_CACHE_TTL = 60  # seconds


def _clean_arxiv_id(value: str) -> str:
    value = str(value or "").strip()
    value = value.replace("arxiv:", "").replace("arXiv:", "")
    return re.sub(r"v\d+$", "", value)


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _paper_key(paper: dict) -> str:
    """Generate a deduplication key for a paper."""
    external = paper.get("external_ids") or {}

    doi = str(external.get("doi") or external.get("DOI") or "").strip().lower()
    if doi:
        return f"doi:{doi}"

    arxiv_id = _clean_arxiv_id(external.get("ArXiv") or external.get("arxiv") or "")
    if arxiv_id:
        return f"arxiv:{arxiv_id.lower()}"

    openalex = str(external.get("openalex") or "").strip()
    if openalex:
        return f"openalex:{openalex.lower()}"

    title = _normalize_title(paper.get("title", ""))
    return f"title:{title}" if title else f"id:{paper.get('paper_id', '')}"


# ─────────────────────────────────────────
# arXiv
# ─────────────────────────────────────────

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


def search_arxiv(query: str, *, max_results: int = 25, search_fn: Callable | None = None) -> list[dict]:
    terms = [part for part in re.split(r"[\s,]+", query.strip()) if part]
    if not terms:
        return []
    if search_fn is None:
        from arxiv_recommender_v5 import search_by_keywords

        search_fn = search_by_keywords
    return [normalize_arxiv_paper(paper) for paper in search_fn(terms, max_results=max_results, days_back=365)]


# ─────────────────────────────────────────
# Semantic Scholar (hardened)
# ─────────────────────────────────────────

def normalize_semantic_paper(paper: dict) -> dict:
    external = paper.get("externalIds") or {}
    arxiv_id = _clean_arxiv_id(external.get("ArXiv") or "")
    semantic_id = str(paper.get("paperId") or "").strip()
    raw_authors = paper.get("authors") or []
    authors = []
    author_ids: list[dict[str, str]] = []
    for author in raw_authors[:3]:  # Cap at first 3 for quality
        if not isinstance(author, dict):
            continue
        name = author.get("name", "")
        if name:
            authors.append(name)
            s2_id = author.get("authorId", "")
            if s2_id:
                author_ids.append({"name": name, "semantic_scholar": s2_id})
    pdf = paper.get("openAccessPdf") or {}
    paper_id = f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{semantic_id}"
    doi_raw = str(external.get("DOI") or "").strip()
    ext_ids: dict[str, str] = {}
    if doi_raw:
        ext_ids["doi"] = doi_raw.lower()
    if arxiv_id:
        ext_ids["ArXiv"] = arxiv_id
    return {
        "paper_id": paper_id,
        "id": paper_id,
        "source": "semantic_scholar",
        "title": paper.get("title", ""),
        "authors": authors,
        "author_ids": author_ids,
        "year": str(paper.get("year") or ""),
        "venue": paper.get("venue") or "Semantic Scholar",
        "abstract": paper.get("abstract") or "",
        "summary": paper.get("abstract") or "",
        "url": paper.get("url") or "",
        "link": paper.get("url") or "",
        "pdf_url": pdf.get("url") if isinstance(pdf, dict) else "",
        "citation_count": paper.get("citationCount"),
        "reference_count": paper.get("referenceCount"),
        "external_ids": ext_ids or external,
        "categories": [],
        "score": 0,
        "relevance_reason": "Semantic Scholar match",
    }


def search_semantic_scholar(query: str, *, max_results: int = 25, opener=None) -> list[dict]:
    """Search Semantic Scholar with timeout, retry, and failure caching."""
    # Check failure cache
    last_fail = _s2_failure_cache.get("last_failure", 0)
    if time.time() - last_fail < S2_FAILURE_CACHE_TTL:
        raise RuntimeError("Semantic Scholar API is currently down or rate limited (cached failure)")

    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={urllib.parse.quote(query)}"
        f"&limit={min(max_results, 100)}"
        f"&fields={SEMANTIC_FIELDS}"
    )

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            if opener:
                resp_text = opener(url)
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                    resp_text = resp.read().decode("utf-8")

            data = json.loads(resp_text) if isinstance(resp_text, str) else resp_text
            papers = data.get("data") or []
            return [normalize_semantic_paper(p) for p in papers if p.get("title")]

        except Exception as e:
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))  # Exponential backoff: 1.5s, 3s
                continue
            _s2_failure_cache["last_failure"] = time.time()
            raise RuntimeError(f"Semantic Scholar API failed: {e}")

    raise RuntimeError("Semantic Scholar API failed after retries")


# ─────────────────────────────────────────
# OpenAlex (new)
# ─────────────────────────────────────────

def _openalex_request(url: str, *, timeout: int = 10) -> dict:
    """Make a request to OpenAlex API."""
    req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def normalize_openalex_paper(paper: dict) -> dict:
    """Normalize an OpenAlex work to the common paper format."""
    oa_id = str(paper.get("id") or "")
    short_id = oa_id.replace("https://openalex.org/", "") if oa_id else ""

    authorships = paper.get("authorships") or []
    authors = []
    author_ids: list[dict[str, str]] = []
    for a in authorships[:3]:  # Cap at first 3 authors for quality/scale
        author_data = a.get("author") or {}
        name = author_data.get("display_name", "")
        if name:
            authors.append(name)
            author_id = author_data.get("id", "")
            if author_id:
                short_author_id = author_id.replace("https://openalex.org/", "")
                author_ids.append({"name": name, "openalex": short_author_id})

    primary = paper.get("primary_location") or {}
    source_info = primary.get("source") or {}
    venue = source_info.get("display_name", "")
    source_id_raw = source_info.get("id", "")
    source_id = source_id_raw.replace("https://openalex.org/", "") if source_id_raw else ""

    doi_raw = str(paper.get("doi") or "")
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

    external_ids: dict[str, str] = {}
    if doi:
        external_ids["doi"] = doi
    if short_id:
        external_ids["openalex"] = short_id
    if source_id:
        external_ids["openalex_source"] = source_id

    abstract = ""
    inverted = paper.get("abstract_inverted_index")
    if inverted and isinstance(inverted, dict):
        # Reconstruct abstract from inverted index
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        abstract = " ".join(w for _, w in word_positions)

    return {
        "paper_id": f"openalex:{short_id}" if short_id else "",
        "source": "openalex",
        "title": str(paper.get("title") or ""),
        "authors": authors,
        "author_ids": author_ids,
        "author_text": ", ".join(authors),
        "year": paper.get("publication_year"),
        "venue": venue,
        "abstract": abstract,
        "summary": abstract[:600] if abstract else "",
        "url": doi_raw if doi_raw.startswith("http") else (
            f"https://doi.org/{doi}" if doi else oa_id
        ),
        "pdf_url": "",
        "citation_count": paper.get("cited_by_count"),
        "reference_count": paper.get("referenced_works_count"),
        "external_ids": external_ids,
        "categories": [],
        "score": 0.0,
        "relevance_reason": "",
    }


def search_openalex(query: str, *, max_results: int = 25) -> list[dict]:
    """Search OpenAlex for papers matching query."""
    try:
        params: dict[str, object] = {
            "search": query,
            "per_page": min(max_results, 50),
            "sort": "relevance_score:desc",
        }
        if OPENALEX_MAILTO:
            params["mailto"] = OPENALEX_MAILTO
        url = f"{OPENALEX_BASE}?{urllib.parse.urlencode(params)}"
        data = _openalex_request(url)
        results = data.get("results") or []
        return [normalize_openalex_paper(r) for r in results if r.get("title")]
    except Exception as e:
        raise RuntimeError(f"OpenAlex API failed: {e}")


# ─────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────

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

    papers: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    sources: dict[str, str] = {}

    _arxiv_fn = arxiv_fn
    _s2_fn = semantic_fn or search_semantic_scholar

    with ThreadPoolExecutor(max_workers=3) as pool:
        arxiv_future = pool.submit(search_arxiv, query, max_results=max_results, search_fn=_arxiv_fn)
        scholar_future = pool.submit(_s2_fn, query, max_results=max_results)
        openalex_future = pool.submit(search_openalex, query, max_results=max_results)

        # Collect arXiv results
        try:
            arxiv_papers = arxiv_future.result(timeout=20)
            papers.extend(arxiv_papers)
            sources["arxiv"] = "ok" if arxiv_papers else "empty"
        except Exception as exc:
            sources["arxiv"] = "failed"
            errors.append(f"arXiv: {exc}")

        # Collect Semantic Scholar results
        try:
            scholar_papers = scholar_future.result(timeout=20)
            papers.extend(scholar_papers)
            sources["semantic_scholar"] = "ok" if scholar_papers else "empty"
        except Exception as exc:
            sources["semantic_scholar"] = "failed"
            warnings.append(f"Semantic Scholar: {exc}")

        # Collect OpenAlex results
        try:
            oa_papers = openalex_future.result(timeout=15)
            papers.extend(oa_papers)
            sources["openalex"] = "ok" if oa_papers else "empty"
        except Exception as exc:
            sources["openalex"] = "failed"
            warnings.append(f"OpenAlex: {exc}")

    merged = merge_and_dedupe_papers(papers)

    # Non-blocking entity extraction from search results
    _async_extract_entities(merged)

    return {
        "papers": merged[:max_results],
        "warnings": warnings,
        "errors": errors if not papers else [],
        "sources": sources,
    }


def _async_extract_entities(papers: list) -> None:
    """Non-blocking entity extraction from search results.

    Runs in a daemon thread so it never blocks the search response.
    """
    if not papers:
        return

    def _run():
        try:
            from state_store import get_state_store
            from app.services.entity_service import EntityService
            store = get_state_store()
            svc = EntityService(store)
            svc.extract_entities_from_results(papers)
        except Exception:
            import logging
            logging.getLogger(__name__).debug(
                "Async entity extraction failed", exc_info=True
            )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


