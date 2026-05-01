"""arXiv source fetcher, paper cache, and keyword search functions."""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from defusedxml import ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from logger_config import get_logger

from app.services.paper_utils import parse_arxiv_identity
from app.services.settings_service import load_user_config

logger = get_logger(__name__)

_SSL_CONTEXT = ssl.create_default_context()

# ---------------------------------------------------------------------------
# Institution / author lists (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------

TOP_INSTITUTIONS: List[str] = [
    'MIT', 'Stanford', 'CMU', 'Carnegie Mellon', 'Berkeley', 'UC Berkeley',
    'Oxford', 'Cambridge', 'ETH Zurich', 'Princeton', 'Harvard',
    'Tsinghua', 'Peking University', 'Caltech', 'Google DeepMind',
    'Google Research', 'Microsoft Research', 'OpenAI', 'Anthropic',
    'Meta AI', 'FAIR', 'NYU', 'University of Toronto', 'Weizmann',
    'INRIA', 'Max Planck', 'TTIC'
]

KNOWN_AUTHORS: List[str] = [
    'Peter Bartlett', 'Andreas Maurer', 'Massimiliano Pontil', 'Ben Recht',
    'Bin Yu', 'Trevor Hastie', 'Rob Tibshirani', 'Martin Wainwright',
    'Michael Jordan', 'Stuart Russell', 'Percy Liang', 'John Duchi',
    'Emmanuel Candes', 'Yoram Singer', 'Elad Hazan', 'Sham Kakade',
    'Sanjeev Arora', 'Avrim Blum', 'Nati Srebro', 'Nina Balcan',
    'Gabor Lugosi', 'Alexandre Tsybakov', 'Olivier Bousquet', 'Leon Bottou',
    'Francis Bach', 'Stephane Boucheron', 'Taiji Suzuki', 'Kenji Fukumizu',
    'Arthur Gretton', 'Bernhard Scholkopf', 'Jonas Peters', 'Dominik Janzing',
    'Jing Lei', 'Larry Wasserman', 'Aaditya Ramdas', 'Rina Barber',
    'Lihua Lei', 'Sayan Mukherjee', 'Cun-hui Zhang', 'Jason Lee',
    'Tengyu Ma', 'Yuanzhi Li', 'Zeyuan Allen-Zhu', 'Suriya Gunasekar'
]


# ---------------------------------------------------------------------------
# Paper Cache (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


class PaperCache:
    """Cache for seen papers to avoid duplicates."""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, 'paper_cache.json')
        self.history_file = os.path.join(cache_dir, 'recommendation_history.json')
        self.seen_papers: Dict[str, str] = {}  # paper_id -> first_seen_date
        self.recommendation_history: Dict[str, List[str]] = {}  # date -> [paper_ids]
        self._load()

    def _load(self):
        """Load cache from disk."""
        os.makedirs(self.cache_dir, exist_ok=True)

        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.seen_papers = json.load(f)
            except Exception:
                self.seen_papers = {}

        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.recommendation_history = json.load(f)
            except Exception:
                self.recommendation_history = {}

    def _save(self):
        """Save cache to disk."""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.seen_papers, f, ensure_ascii=False, indent=2)

        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.recommendation_history, f, ensure_ascii=False, indent=2)

    def mark_seen(self, paper_id: str):
        """Mark a paper as seen."""
        self.seen_papers[paper_id] = datetime.now().strftime('%Y-%m-%d')
        self._save()

    def is_seen(self, paper_id: str) -> bool:
        """Check if paper has been seen."""
        return paper_id in self.seen_papers

    def record_recommendation(self, date: str, paper_ids: List[str]):
        """Record daily recommendations."""
        self.recommendation_history[date] = paper_ids
        for pid in paper_ids:
            self.mark_seen(pid)
        self._save()

    def cleanup_old_entries(self, days: int = 30):
        """Remove entries older than specified days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        self.seen_papers = {
            k: v for k, v in self.seen_papers.items()
            if (isinstance(v, str) and v >= cutoff) or isinstance(v, dict)
        }
        self._save()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'total_seen': len(self.seen_papers),
            'days_with_recommendations': len(self.recommendation_history)
        }


# ---------------------------------------------------------------------------
# Multi-Source Fetcher (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


class MultiSourceFetcher:
    """Fetch papers from multiple sources."""

    def __init__(self, categories: List[str], cache: PaperCache):
        self.categories = categories
        self.cache = cache

    def fetch_all_sources(self, days: int = 1, *, force_refresh: bool = False) -> List[Dict]:
        """Fetch papers from all sources.

        When *force_refresh* is True the seen-paper filter is skipped so that
        re-scored candidates can be re-ranked after preference changes.
        """
        all_papers: List[Dict] = []

        # Source 1: arXiv (try combined query first, then fallback to individual)
        logger.info("Fetching from arXiv...")
        arxiv_papers = self._fetch_arxiv_combined(days)
        if not arxiv_papers:
            logger.warning("Combined query failed, trying individual categories...")
            arxiv_papers = self._fetch_arxiv(days)
        all_papers.extend(arxiv_papers)
        logger.info("Found %s papers from arXiv", len(arxiv_papers))

        # Source 2: Topic-focused search
        logger.info("Searching for priority topics...")
        topic_papers = self._fetch_by_topics(days)
        for p in topic_papers:
            if p['id'] not in [x['id'] for x in all_papers]:
                all_papers.append(p)
        logger.info("Found %s papers from topic search", len(topic_papers))

        # Source 3: Recent submissions (last 7 days if today is empty)
        if len(arxiv_papers) < 50:
            logger.info("Fetching from arXiv (extended range)...")
            extended_papers = self._fetch_arxiv_combined(min(days + 7, 14))
            if not extended_papers:
                extended_papers = self._fetch_arxiv(min(days + 7, 14))
            for p in extended_papers:
                if p['id'] not in [x['id'] for x in all_papers]:
                    all_papers.append(p)
            logger.info("Total: %s papers", len(all_papers))

        if not force_refresh:
            # Remove already seen papers (skip on force refresh so re-scored
            # candidates can be re-ranked after preference changes)
            all_papers = [p for p in all_papers if not self.cache.is_seen(p['id'])]
            logger.info("After removing seen papers: %s", len(all_papers))

        return all_papers

    def _fetch_by_topics(self, days: int) -> List[Dict]:
        """Fetch papers by searching for specific topics."""
        papers: List[Dict] = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        config = load_user_config()
        priority_topics = config.get('research_focus', {}).get('topics', [])

        if not priority_topics:
            priority_topics = ['in-context learning', 'ICL', 'prompt learning', 'conformal prediction']

        for topic in priority_topics[:5]:
            try:
                params = {
                    'search_query': f'all:"{topic}"',
                    'start': 0,
                    'max_results': 50,
                    'sortBy': 'submittedDate',
                    'sortOrder': 'descending'
                }

                url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

                req = urllib.request.Request(url, headers={'User-Agent': 'arxiv-recommender/2.4'})
                with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as response:
                    xml_data = response.read().decode('utf-8')
                    topic_papers = self._parse_arxiv_xml(xml_data)

                    for paper in topic_papers:
                        try:
                            pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                            if pub_date >= start_date:
                                paper['_topic_match'] = topic
                                papers.append(paper)
                        except Exception:
                            pass

                    if topic_papers:
                        logger.debug("'%s': %s papers", topic, len([p for p in topic_papers if datetime.strptime(p['published'][:10], '%Y-%m-%d') >= start_date]))

                time.sleep(3)

            except Exception as e:
                logger.warning("Error searching '%s': %s", topic, e)
                continue

        seen = set()
        unique: List[Dict] = []
        for p in papers:
            if p['id'] not in seen:
                seen.add(p['id'])
                unique.append(p)

        return unique

    def _fetch_arxiv_combined(self, days: int) -> List[Dict]:
        """Fetch papers using a SINGLE combined query (minimizes API calls)."""
        papers: List[Dict] = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        cat_query = ' OR '.join([f'cat:{cat}' for cat in self.categories])
        params = {
            'search_query': f'({cat_query})',
            'start': 0,
            'max_results': 500,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }

        url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'arxiv-recommender/2.3'
                })
                with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as response:
                    xml_data = response.read().decode('utf-8')
                    all_papers = self._parse_arxiv_xml(xml_data)

                    for paper in all_papers:
                        try:
                            pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                            if pub_date >= start_date:
                                papers.append(paper)
                        except Exception:
                            papers.append(paper)

                    logger.debug("Combined query: %s papers in date range", len(papers))
                    return papers

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = (attempt + 1) * 60
                    logger.warning("Rate limited (429), waiting %ss...", wait_time)
                    time.sleep(wait_time)
                else:
                    logger.error("HTTP error: %s", e.code)
                    break
            except Exception as e:
                logger.error("Fetch error: %s", e)
                if attempt < 2:
                    time.sleep(30)

        return papers

    def _fetch_arxiv(self, days: int) -> List[Dict]:
        """Fetch papers from arXiv API with retry and rate limiting."""
        papers: List[Dict] = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        def fetch_with_retry(url: str, max_retries: int = 3) -> Optional[str]:
            """Fetch URL with exponential backoff on rate limit errors."""
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'arxiv-recommender/2.3'})
                    with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as response:
                        return response.read().decode('utf-8')
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        wait_time = (attempt + 1) * 30
                        logger.warning("Rate limited, waiting %ss before retry %s/%s...", wait_time, attempt + 1, max_retries)
                        time.sleep(wait_time)
                    else:
                        raise
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(10)
            return None

        for i, category in enumerate(self.categories):
            params = {
                'search_query': f'cat:{category}',
                'start': 0,
                'max_results': 150,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }

            url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

            try:
                xml_data = fetch_with_retry(url)
                if xml_data:
                    category_papers = self._parse_arxiv_xml(xml_data)

                    for paper in category_papers:
                        try:
                            pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                            if pub_date >= start_date:
                                papers.append(paper)
                        except Exception:
                            papers.append(paper)
                    logger.debug("%s: %s papers", category, len(category_papers))
                else:
                    logger.warning("%s: Failed after retries", category)

            except Exception as e:
                logger.error("Error fetching %s: %s", category, e)

            if i < len(self.categories) - 1:
                time.sleep(5)

        seen = set()
        unique: List[Dict] = []
        for p in papers:
            if p['id'] not in seen:
                seen.add(p['id'])
                unique.append(p)

        return unique

    def _parse_arxiv_xml(self, xml_data: str) -> List[Dict]:
        """Parse arXiv API XML response."""
        papers: List[Dict] = []
        try:
            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

            for entry in root.findall('atom:entry', ns):
                paper: Dict = {}

                title_elem = entry.find('atom:title', ns)
                paper['title'] = title_elem.text.strip() if title_elem is not None else ''

                authors: List[str] = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                paper['authors'] = authors

                abstract_elem = entry.find('atom:summary', ns)
                paper['abstract'] = abstract_elem.text.strip() if abstract_elem is not None else ''

                published_elem = entry.find('atom:published', ns)
                paper['published'] = published_elem.text if published_elem is not None else ''

                link_elem = entry.find('atom:id', ns)
                identity = parse_arxiv_identity(link_elem.text if link_elem is not None else '')
                paper['id'] = identity['canonical_id']
                paper['base_id'] = identity['base_id']
                paper['version'] = identity['version']
                paper['source_url'] = identity['source_url']
                paper['link'] = identity['source_url']
                paper['source'] = 'arXiv'

                categories: List[str] = []
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term')
                    if term:
                        categories.append(term)
                paper['categories'] = categories

                comment_elem = entry.find('arxiv:comment', ns)
                paper['comment'] = comment_elem.text if comment_elem is not None else ''

                papers.append(paper)
        except Exception as e:
            logger.error("XML parsing error: %s", e)

        return papers


# ---------------------------------------------------------------------------
# Custom Keywords Search (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


def search_by_keywords(keywords: List[str], max_results: int = 20, days_back: int = 365) -> List[Dict]:
    """Search arXiv papers by custom keywords.

    Args:
        keywords: List of keywords to search for
        max_results: Maximum number of papers to return
        days_back: How many days back to search (default 365 days = 1 year)

    Returns:
        List of matching papers sorted by relevance score
    """
    logger.info("=" * 60)
    logger.info("Searching arXiv for: %s", ', '.join(keywords))
    logger.info("=" * 60)

    query_parts: List[str] = []
    for kw in keywords[:5]:
        query_parts.append(f'(ti:"{kw}"+OR+abs:"{kw}")')

    search_query = '+OR+'.join(query_parts)

    papers: List[Dict] = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    params = {
        'search_query': search_query,
        'start': 0,
        'max_results': min(max_results * 3, 100),
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }

    url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    logger.debug("Query URL: %s", url)

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as response:
            xml_data = response.read().decode('utf-8')
            logger.debug("Received %s bytes from arXiv", len(xml_data))

            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

            entries = root.findall('atom:entry', ns)
            logger.debug("Found %s entries in XML", len(entries))

            for entry in entries:
                paper: Dict = {}

                title_elem = entry.find('atom:title', ns)
                paper['title'] = title_elem.text.strip() if title_elem is not None else ''

                authors: List[str] = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                paper['authors'] = authors

                abstract_elem = entry.find('atom:summary', ns)
                paper['abstract'] = abstract_elem.text.strip() if abstract_elem is not None else ''

                published_elem = entry.find('atom:published', ns)
                paper['published'] = published_elem.text if published_elem is not None else ''

                link_elem = entry.find('atom:id', ns)
                identity = parse_arxiv_identity(link_elem.text if link_elem is not None else '')
                paper['id'] = identity['canonical_id']
                paper['base_id'] = identity['base_id']
                paper['version'] = identity['version']
                paper['source_url'] = identity['source_url']
                paper['link'] = identity['source_url']
                paper['source'] = 'arXiv'

                categories: List[str] = []
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term')
                    if term:
                        categories.append(term)
                paper['categories'] = categories

                comment_elem = entry.find('arxiv:comment', ns)
                paper['comment'] = comment_elem.text if comment_elem is not None else ''

                try:
                    pub_date = datetime.strptime(paper['published'][:10], '%Y-%m-%d')
                    if pub_date >= start_date:
                        papers.append(paper)
                except Exception:
                    papers.append(paper)

    except Exception as e:
        logger.error("Error fetching from arXiv: %s", e)
        import traceback
        logger.debug(traceback.format_exc())
        return []

    logger.info("Found %s papers from arXiv", len(papers))

    def compute_keyword_score(paper: Dict) -> Tuple[float, Dict]:
        """Compute score based on keyword matching."""
        text = (paper['title'] + ' ' + paper.get('abstract', ''))
        text_lower = text.lower()
        score = 0.0
        matched_keywords: List[str] = []

        for kw in keywords:
            kw_lower = kw.lower()
            pattern = r'\b' + re.escape(kw_lower) + r'\b'
            if re.search(pattern, text_lower):
                if re.search(pattern, paper['title'].lower()):
                    score += 3.0
                    matched_keywords.append(f"Title: {kw}")
                else:
                    score += 1.5
                    matched_keywords.append(f"Abstract: {kw}")
            else:
                words = kw_lower.split()
                if all(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in words):
                    score += 1.0
                    matched_keywords.append(f"Related: {kw}")

        authors_text = ' '.join(paper.get('authors', [])).lower()
        for author in KNOWN_AUTHORS:
            if author.lower() in authors_text:
                score += 1.0
                matched_keywords.append(f"Author: {author}")
                break

        all_text = (paper.get('abstract', '') + ' ' + (paper.get('comment') or '')).lower()
        for inst in TOP_INSTITUTIONS:
            if inst.lower() in all_text:
                score += 0.5
                matched_keywords.append(f"Institution: {inst}")
                break

        return score, {'matched_keywords': matched_keywords}

    for paper in papers:
        score, details = compute_keyword_score(paper)
        paper['score'] = score
        paper['matched_keywords'] = details['matched_keywords']
        paper['summary'] = _generate_summary(paper.get('abstract', ''))
        paper['relevance_reason'] = '; '.join(details['matched_keywords'][:3]) if details['matched_keywords'] else 'Keyword match'

    papers.sort(key=lambda x: -x['score'])
    results = papers[:max_results]

    logger.info("Top %s papers after scoring", len(results))
    return results


def _generate_summary(abstract: str, max_sentences: int = 3) -> str:
    """Generate a concise summary from an abstract. Used by search_by_keywords."""
    if not abstract:
        return "No abstract available."
    sentences = re.split(r'(?<=[.!?])\s+', abstract)
    summary = '. '.join(sentences[:max_sentences])
    if len(summary) > 350:
        summary = summary[:350] + '...'
    return summary


# ---------------------------------------------------------------------------
# Original fetch_arxiv_metadata (keep from old file)
# ---------------------------------------------------------------------------


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
    authors: List[str] = []
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
    "search_by_keywords",
    "TOP_INSTITUTIONS",
    "KNOWN_AUTHORS",
]
