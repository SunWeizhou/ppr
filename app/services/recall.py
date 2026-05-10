"""Single arXiv fetch -- one combined-category query with dedup + cache filter."""

from __future__ import annotations

import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from defusedxml import ElementTree as ET
from logger_config import get_logger
from app_paths import CACHE_DIR
from app.services.arxiv_source import PaperCache
from app.services.paper_utils import parse_arxiv_identity
from app.services.safe_http import safe_urlopen

logger = get_logger(__name__)
_SSL = ssl.create_default_context()
_UA = "arxiv-recommender/2.3"
_ARXIV = "https://export.arxiv.org/api/query"


def recall_candidates(
    categories: list[str],
    lookback_days: int = 1,
    max_results: int = 500,
) -> list[dict]:
    """Fetch candidate papers from arXiv via a single combined-category query."""
    if not categories:
        logger.warning("recall_candidates called with empty categories")
        return []
    params = {
        "search_query": "({})".format(" OR ".join(f"cat:{c}" for c in categories)),
        "start": 0, "max_results": max_results,
        "sortBy": "submittedDate", "sortOrder": "descending",
    }
    url = f"{_ARXIV}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with safe_urlopen(req, timeout=60, context=_SSL) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception as exc:
        logger.error("arXiv fetch failed: %s", exc)
        return []
    papers = _parse_arxiv_xml(xml_data)
    cutoff = datetime.now() - timedelta(days=lookback_days)
    papers = [p for p in papers if _pub_after(p, cutoff)]
    papers = _dedup(papers)
    cache = PaperCache(str(CACHE_DIR))
    return [p for p in papers if not cache.is_seen(p["id"])]


def _parse_arxiv_xml(xml_data: str) -> list[dict]:
    """Parse arXiv API Atom XML into paper dicts."""
    papers: list[dict] = []
    try:
        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        for entry in root.findall("atom:entry", ns):
            id_elem = entry.find("atom:id", ns)
            ident = parse_arxiv_identity(id_elem.text if id_elem is not None else "")
            papers.append({
                "id": ident["canonical_id"], "base_id": ident["base_id"],
                "version": ident["version"], "link": ident["source_url"],
                "source_url": ident["source_url"], "source": "arXiv",
                "title": _et(entry, "atom:title", ns),
                "abstract": _et(entry, "atom:summary", ns),
                "published": _et(entry, "atom:published", ns),
                "authors": [
                    a.find("atom:name", ns).text
                    for a in entry.findall("atom:author", ns)
                    if a.find("atom:name", ns) is not None
                ],
                "categories": [
                    c.get("term")
                    for c in entry.findall("atom:category", ns)
                    if c.get("term")
                ],
                "comment": _et(entry, "arxiv:comment", ns),
            })
    except Exception as exc:
        logger.error("XML parsing error: %s", exc)
    return papers

def _et(entry, tag: str, ns: dict) -> str:
    e = entry.find(tag, ns)
    return e.text.strip() if e is not None and e.text else ""


def _pub_after(paper: dict, cutoff: datetime) -> bool:
    try:
        pub = datetime.strptime(paper["published"][:10], "%Y-%m-%d")
        return pub >= cutoff
    except (ValueError, KeyError):
        return True

def _dedup(papers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for p in papers:
        pid = p.get("id", "")
        if pid and pid not in seen:
            seen.add(pid)
            out.append(p)
    return out
