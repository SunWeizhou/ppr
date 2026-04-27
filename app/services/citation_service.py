"""Citation analysis via Semantic Scholar API."""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from typing import Dict

from logger_config import get_logger

from app.services.paper_utils import parse_arxiv_identity

logger = get_logger(__name__)

_SSL_CONTEXT = ssl.create_default_context()


class CitationAnalyzer:
    """Small Semantic Scholar citation client used by the Flask API."""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir

    def fetch_citation_data(self, paper_id: str) -> Dict[str, int]:
        identity = parse_arxiv_identity(paper_id)
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/"
            f"ARXIV:{urllib.parse.quote(identity['base_id'])}"
            "?fields=citationCount,influentialCitationCount,referenceCount"
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'arXiv-Recommender/1.0'})
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CONTEXT) as response:
            data = json.loads(response.read().decode('utf-8'))
        return {
            'citations': int(data.get('citationCount') or 0),
            'influential_citations': int(data.get('influentialCitationCount') or 0),
            'references': int(data.get('referenceCount') or 0),
        }


__all__ = ["CitationAnalyzer"]
