"""
Shared utilities for arXiv Recommender.
Consolidates common functionality to reduce code duplication.
"""

import re
import time
import json
import ssl
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any
import logging

from app_paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

# ==================== SSL Context ====================
# Configurable SSL context - can be made stricter in production
SSL_CONTEXT = ssl.create_default_context()


# ==================== Keyword Utilities ====================
def count_keyword(text: str, keyword: str) -> int:
    """Count keyword occurrences with flexible matching.

    Handles:
    - Multi-word keywords (e.g., "conformal prediction")
    - Hyphenated keywords (e.g., "in-context learning")
    - Case insensitive matching
    - Word boundary matching for single words

    Args:
        text: The text to search in
        keyword: The keyword to search for

    Returns:
        The number of occurrences
    """
    keyword_lower = keyword.lower()
    text_lower = text.lower()

    # Multi-word or hyphenated: use simple substring matching
    if ' ' in keyword_lower or '-' in keyword_lower:
        return text_lower.count(keyword_lower)
    else:
        # Single word: use word boundary matching
        pattern = r'\b' + re.escape(keyword_lower) + r'\b'
        return len(re.findall(pattern, text_lower))


# ==================== JSON Utilities ====================
def safe_load_json(filepath: str, default: Any = None) -> Any:
    """Safely load JSON file with error handling.

    Args:
        filepath: Path to JSON file
        default: Default value if loading fails

    Returns:
        Parsed JSON data or default value
    """
    if default is None:
        default = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, OSError):
        return default
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Invalid JSON in {filepath}: {e}")
        return default


def safe_save_json(filepath: str, data: Any, indent: int = 2) -> bool:
    """Safely save data to JSON file.

    Args:
        filepath: Path to JSON file
        data: Data to save
        indent: JSON indentation level

    Returns:
        True if successful, False otherwise
    """
    try:
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except (IOError, TypeError) as e:
        logger.error(f"Failed to save JSON to {filepath}: {e}")
        return False


# ==================== Network Utilities ====================
def fetch_with_retry(
    url: str,
    max_retries: int = 5,
    timeout: int = 60,
    headers: Optional[Dict] = None,
    context: Optional[ssl.SSLContext] = None
) -> Optional[str]:
    """Fetch URL with exponential backoff on server errors.

    Handles: 429 (rate limit), 500, 502, 503, 504 (server errors)
    Uses exponential backoff: 10s, 20s, 40s, 80s, capped at 120s

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        headers: Optional request headers
        context: Optional SSL context

    Returns:
        Response content as string, or None if all retries failed
    """
    if headers is None:
        headers = {'User-Agent': 'arxiv-recommender/2.5'}
    if context is None:
        context = SSL_CONTEXT

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                return response.read().decode('utf-8')

        except urllib.error.HTTPError as e:
            # Retry on rate limits and server errors
            if e.code in (429, 500, 502, 503, 504):
                wait_time = min((2 ** attempt) * 10, 120)
                logger.warning(f"HTTP {e.code}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                # Client errors (4xx except 429) should not be retried
                logger.error(f"HTTP error {e.code} (non-retryable): {e}")
                raise

        except urllib.error.URLError as e:
            # Network/timeout errors - retry with backoff
            if attempt < max_retries - 1:
                wait_time = min((2 ** attempt) * 5, 60)
                logger.warning(f"URL error ({e}), waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"URL error after {max_retries} retries: {e}")
                raise

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = min((2 ** attempt) * 5, 30)
                logger.warning(f"Unexpected error, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Unexpected error after {max_retries} retries: {e}")
                raise

    return None


# ==================== Shared Constants ====================
CATEGORY_NAMES = {
    "stat.ML": "Stat ML",
    "stat.TH": "Stat Theory",
    "stat.ME": "Methodology",
    "stat.CO": "Computation",
    "cs.LG": "ML",
    "cs.AI": "AI",
    "cs.CL": "NLP",
    "cs.CV": "Vision",
    "cs.NE": "Neural",
    "cs.IT": "Info Theory",
    "math.ST": "Math Stats",
    "math.PR": "Probability",
    "math.OC": "Optimization",
    "econ.EM": "Econometrics",
}


def atomic_write_json(filepath: str, payload) -> None:
    """Atomically write JSON data to a file using a temp file + rename."""
    import os

    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = f"{filepath}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, filepath)


# ==================== Validation Utilities ====================
def validate_arxiv_id(paper_id: str) -> bool:
    """Validate arXiv ID format.

    Supports both old (e.g., math.GT/0309135) and new (e.g., 2103.12345) formats.

    Args:
        paper_id: The arXiv ID to validate

    Returns:
        True if valid format, False otherwise
    """
    # New format: YYMM.NNNNN or YYMM.NNNNNvN
    new_format = r'^\d{4}\.\d{4,5}(v\d+)?$'
    # Old format: subject-class/YYMMNNN
    old_format = r'^[a-z-]+/\d{7}$'

    return bool(re.match(new_format, paper_id) or re.match(old_format, paper_id))


def validate_paper_data(paper: Dict) -> bool:
    """Validate that paper data has required fields.

    Args:
        paper: Paper dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ['id', 'title', 'summary']
    return all(field in paper and paper[field] for field in required_fields)


# ==================== Digest Parsing Cache ====================
_digest_cache: dict = {}  # {date_or_key: (papers, keywords, timestamp)}
_DIGEST_CACHE_TTL = 300  # 5 minutes


def parse_markdown_digest(filepath: str):
    """Parse a markdown digest file to extract papers and keywords.

    Args:
        filepath: Path to the digest .md file

    Returns:
        Tuple of (papers: list, keywords: list)
    """
    import os

    from app.services.paper_utils import breakdown_from_text

    papers = []
    keywords = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract themes/keywords from the header
    themes_match = re.search(r'\*\*Research Themes:\*\*\s*(.+)', content)
    if themes_match:
        keywords = [k.strip() for k in themes_match.group(1).split(',')]

    # Try to load daily metadata for better keywords
    date_match = re.search(r'digest_(\d{4}-\d{2}-\d{2})', filepath)
    date_str = date_match.group(1) if date_match else None

    if date_str:
        metadata_path = os.path.join(str(PROJECT_ROOT), 'cache', 'daily_metadata.json')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    if metadata.get('date') == date_str and metadata.get('keywords'):
                        keywords = [k['word'] for k in metadata['keywords']]
            except Exception:
                pass

    # Try to load structured breakdown from daily_recommendation.json
    breakdown_map = {}
    if date_str:
        run_paths = [
            os.path.join(str(PROJECT_ROOT), 'cache', 'recommendation_runs', f'{date_str}.json'),
            os.path.join(str(PROJECT_ROOT), 'cache', 'daily_recommendation.json'),
        ]
        for rec_path in run_paths:
            if not os.path.exists(rec_path):
                continue
            try:
                with open(rec_path, 'r', encoding='utf-8') as f:
                    rec_data = json.load(f)
                    if rec_data.get('date') != date_str:
                        continue
                    for p in rec_data.get('papers', []):
                        pid = p.get('id')
                        if pid:
                            breakdown = p.get('score_details', {}).get('breakdown', []) or p.get('relevance_breakdown', [])
                            reason_text = p.get('relevance_reason') or p.get('relevance', '')
                            breakdown_map[pid] = {
                                'breakdown': breakdown or breakdown_from_text(reason_text),
                                'relevance_reason': reason_text,
                            }
                    if breakdown_map:
                        break
            except Exception as e:
                logger.error(f"Error loading breakdown: {e}")

    # Split into paper sections
    sections = re.split(r'## \d+\.', content)[1:]  # Skip header

    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue

        paper = {}
        paper['title'] = lines[0].strip()

        for line in lines[1:]:
            if line.startswith('**Authors:**'):
                paper['authors'] = line.replace('**Authors:**', '').strip()
            elif line.startswith('**arXiv:**') or line.startswith('**arXiv Link:**'):
                match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
                if match:
                    paper['id'] = match.group(1)
                    paper['link'] = match.group(2)
            elif line.startswith('**Summary:**'):
                paper['summary'] = line.replace('**Summary:**', '').strip()[:200] + '...'
            elif line.startswith('**Relevance:**'):
                paper['relevance'] = line.replace('**Relevance:**', '').strip()
            elif line.startswith('**Citations:**'):
                try:
                    paper['citations'] = int(line.replace('**Citations:**', '').strip())
                except Exception:
                    paper['citations'] = 0
            elif line.startswith('**Score:**'):
                try:
                    paper['score'] = float(line.replace('**Score:**', '').strip())
                except Exception:
                    paper['score'] = 0

        if paper.get('id'):
            # Merge structured breakdown if available
            pid = paper['id']
            if pid in breakdown_map:
                paper['relevance_breakdown'] = breakdown_map[pid]['breakdown']
                if breakdown_map[pid]['relevance_reason']:
                    paper['relevance'] = breakdown_map[pid]['relevance_reason']
            else:
                paper['relevance_breakdown'] = breakdown_from_text(paper.get('relevance', ''))
            papers.append(paper)

    return papers, keywords


def parse_markdown_digest_cached(filepath: str, use_cache: bool = True):
    """Parse a markdown digest file with caching to avoid redundant I/O.

    Args:
        filepath: Path to the digest .md file
        use_cache: Whether to use the module-level cache

    Returns:
        Tuple of (papers: list, keywords: list)
    """
    import os as _os

    # Extract date from file path for cache key
    date_match = re.search(r'digest_(\d{4}-\d{2}-\d{2})', filepath)
    cache_key = date_match.group(1) if date_match else filepath

    current_time = time.time()

    # Check cache
    if use_cache and cache_key in _digest_cache:
        cached_papers, cached_keywords, cached_time = _digest_cache[cache_key]
        try:
            file_mtime = _os.path.getmtime(filepath)
            if cached_time >= file_mtime and (current_time - cached_time) < _DIGEST_CACHE_TTL:
                logger.debug(f"Using cached digest for {cache_key}")
                return cached_papers, cached_keywords
        except OSError:
            pass

    # Parse file
    papers, keywords = parse_markdown_digest(filepath)

    # Update cache
    if use_cache and papers:
        _digest_cache[cache_key] = (papers, keywords, current_time)

    return papers, keywords
