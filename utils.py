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

logger = logging.getLogger(__name__)

# ==================== SSL Context ====================
# Configurable SSL context - can be made stricter in production
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


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
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
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
