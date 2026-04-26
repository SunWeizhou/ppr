"""Compatibility facade for arXiv source and search functions."""

import urllib.request
import xml.etree.ElementTree as ET

from arxiv_recommender_v5 import (
    MultiSourceFetcher,
    PaperCache,
    load_daily_recommendation,
    run_pipeline,
    search_by_keywords,
)


def fetch_arxiv_metadata(paper_id: str) -> dict | None:
    """Fetch paper metadata from the arXiv API by paper ID.

    Returns a dict with keys: paper_id, title, abstract, authors, published, link.
    Returns None if the paper is not found on arXiv.
    """
    normalized_id = paper_id.replace("v1", "").replace("v2", "")
    url = f"https://export.arxiv.org/api/query?id_list={normalized_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "arXiv-Recommender/1.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        xml_data = response.read().decode("utf-8")

    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return None

    title_elem = entry.find("atom:title", ns)
    summary_elem = entry.find("atom:summary", ns)
    published_elem = entry.find("atom:published", ns)
    authors = []
    for author in entry.findall("atom:author", ns):
        name_elem = author.find("atom:name", ns)
        if name_elem is not None:
            authors.append(name_elem.text.strip())

    return {
        "paper_id": paper_id,
        "title": title_elem.text.strip().replace("\n", " ") if title_elem is not None else "",
        "abstract": summary_elem.text.strip().replace("\n", " ") if summary_elem is not None else "",
        "authors": authors,
        "published": published_elem.text[:10] if published_elem is not None and published_elem.text else "",
        "link": f"https://arxiv.org/abs/{paper_id}",
    }


__all__ = [
    "MultiSourceFetcher",
    "PaperCache",
    "fetch_arxiv_metadata",
    "load_daily_recommendation",
    "run_pipeline",
    "search_by_keywords",
]

