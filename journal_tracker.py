"""
Journal Tracker - Track latest papers from top journals
Uses multiple data sources: Crossref API + direct website scraping
Features:
- Citation tracking with weekly updates
- Smart detection frequency (daily for JMLR, weekly for traditional journals)
- Citation trend display
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ssl
import time
import re
import xml.etree.ElementTree as ET

from app_paths import CACHE_DIR as APP_CACHE_DIR, LEGACY_USER_CONFIG_PATH, PROJECT_ROOT, USER_PROFILE_PATH

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Detection frequency settings
DETECTION_CONFIG = {
    'JMLR': {
        'frequency': 'daily',      # Check every day
        'description': '持续出版，每日检测新论文'
    },
    'AoS': {
        'frequency': 'weekly',     # Check weekly
        'description': '传统期刊，每周检测新期'
    },
    'JASA': {
        'frequency': 'weekly',
        'description': '传统期刊，每周检测新期'
    },
    'Biometrika': {
        'frequency': 'weekly',
        'description': '传统期刊，每周检测新期'
    },
    'JRSS-B': {
        'frequency': 'weekly',
        'description': '传统期刊，每周检测新期'
    }
}

# Journal configurations
JOURNALS = {
    'JMLR': {
        'name': 'Journal of Machine Learning Research',
        'issn': '1533-7928',
        'short_name': 'JMLR',
        'color': '#10b981',
        'icon': '🤖',
        'url': 'https://www.jmlr.org',
        'type': 'continuous',  # Continuous publishing - papers added to volume
    },
    'AoS': {
        'name': 'Annals of Statistics',
        'issn': '0090-5364',
        'short_name': 'AoS',
        'color': '#3b82f6',
        'icon': '📊',
        'url': 'https://imstat.org/journals-and-publications/annals-of-statistics/',
        'type': 'traditional',  # Traditional issues
    },
    'JASA': {
        'name': 'Journal of the American Statistical Association',
        'issn': '0162-1459',
        'short_name': 'JASA',
        'color': '#8b5cf6',
        'icon': '📈',
        'url': 'https://www.tandfonline.com/action/journalInformation?journalCode=uasa20',
        'type': 'traditional',
    },
    'Biometrika': {
        'name': 'Biometrika',
        'issn': '0006-3444',
        'short_name': 'Biometrika',
        'color': '#f59e0b',
        'icon': '🧬',
        'url': 'https://academic.oup.com/biometrika',
        'type': 'traditional',
    },
    'JRSS-B': {
        'name': 'Journal of the Royal Statistical Society: Series B',
        'issn': '0035-9246',
        'short_name': 'JRSS-B',
        'color': '#ef4444',
        'icon': '👑',
        'url': 'https://rss.onlinelibrary.wiley.com/journal/14679868',
        'type': 'traditional',
    }
}

# Cache settings
CACHE_DIR = str(APP_CACHE_DIR)
CACHE_FILE = os.path.join(CACHE_DIR, 'journal_cache.json')
CITATION_HISTORY_FILE = os.path.join(CACHE_DIR, 'citation_history.json')
UPDATE_LOG_FILE = os.path.join(CACHE_DIR, 'update_log.json')
CACHE_EXPIRY_HOURS = 12


def fetch_citation_count(doi: str, title: str = '') -> Tuple[int, bool]:
    """Fetch citation count from Semantic Scholar API.

    Uses DOI if available, otherwise searches by title.

    Returns:
        Tuple of (citation_count, success) - success is False if rate limited
    """
    try:
        if doi:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=citationCount"
        else:
            # Search by title
            encoded_title = urllib.parse.quote(title[:200])
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded_title}&limit=1&fields=citationCount"

        req = urllib.request.Request(url, headers={
            'User-Agent': 'arXiv-Recommender/1.0'
        })

        with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as response:
            data = json.loads(response.read().decode('utf-8'))

            if doi:
                return data.get('citationCount', 0), True
            else:
                # Search results
                papers = data.get('data', [])
                if papers:
                    return papers[0].get('citationCount', 0), True
                return 0, True

    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"Rate limited by Semantic Scholar API")
            return 0, False
        print(f"HTTP Error fetching citations: {e}")
    except Exception as e:
        print(f"Error fetching citations: {e}")

    return 0, True


def load_citation_history() -> Dict:
    """Load citation history from file."""
    if os.path.exists(CITATION_HISTORY_FILE):
        try:
            with open(CITATION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_citation_history(history: Dict):
    """Save citation history to file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CITATION_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def update_citations(papers: List[Dict], journal_key: str) -> List[Dict]:
    """Update citation counts for papers and track history.

    Returns papers with updated citation info and trends.
    Note: Semantic Scholar API has rate limits (100 requests/5 min for unauthenticated).
    We use conservative rate limiting to avoid hitting limits.
    """
    history = load_citation_history()
    today = datetime.now().strftime('%Y-%m-%d')

    # Rate limit: max 50 papers per session to avoid API limits
    # Papers with existing history get priority skipped (they have historical data)
    MAX_PAPERS_PER_SESSION = 50
    papers_updated = 0
    rate_limited = False

    for paper in papers:
        paper_id = paper.get('doi') or paper.get('url', '').split('/')[-1]
        if not paper_id:
            continue

        # Check if we already have citation data for today
        if paper_id in history and today in history[paper_id]:
            paper['citations'] = history[paper_id][today]
            # Calculate trend
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            old_count = history[paper_id].get(week_ago, paper['citations'])
            paper['citation_trend'] = paper['citations'] - old_count if paper['citations'] else 0
            continue

        # Stop if rate limited or reached max papers
        if rate_limited or papers_updated >= MAX_PAPERS_PER_SESSION:
            # Use existing historical data if available
            if paper_id in history:
                last_date = sorted(history[paper_id].keys())[-1]
                paper['citations'] = history[paper_id][last_date]
                week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                old_count = history[paper_id].get(week_ago, paper['citations'])
                paper['citation_trend'] = paper['citations'] - old_count if paper['citations'] else 0
            continue

        # Get current citation count
        current_citations, success = fetch_citation_count(
            paper.get('doi', ''),
            paper.get('title', '')
        )

        if not success:
            rate_limited = True
            print(f"Rate limited after {papers_updated} papers")
            continue

        paper['citations'] = current_citations
        papers_updated += 1

        # Track history
        if paper_id not in history:
            history[paper_id] = {}

        history[paper_id][today] = current_citations

        # Calculate trend (compare to 7 days ago)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        old_count = history[paper_id].get(week_ago, current_citations)
        paper['citation_trend'] = current_citations - old_count

        # Rate limit - 1 request per second to stay within limits
        time.sleep(1)

    save_citation_history(history)
    if papers_updated > 0:
        print(f"Updated citations for {papers_updated} papers from {journal_key}")
    if rate_limited:
        print(f"Citation update paused due to rate limiting. Will continue next time.")

    return papers


def load_update_log() -> Dict:
    """Load update log from file."""
    if os.path.exists(UPDATE_LOG_FILE):
        try:
            with open(UPDATE_LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_update_log(log: Dict):
    """Save update log to file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(UPDATE_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def should_check_for_updates(journal_key: str) -> Tuple[bool, str]:
    """Determine if we should check for updates based on detection frequency.

    Returns:
        Tuple of (should_check, reason)
    """
    config = DETECTION_CONFIG.get(journal_key, {'frequency': 'weekly'})
    update_log = load_update_log()

    last_check = update_log.get(journal_key, {}).get('last_check', '2000-01-01')
    last_check_date = datetime.strptime(last_check, '%Y-%m-%d')
    days_since_check = (datetime.now() - last_check_date).days

    if config['frequency'] == 'daily':
        if days_since_check >= 1:
            return True, f"每日检测，上次检查: {days_since_check}天前"
        return False, "今天已检测"
    else:  # weekly
        if days_since_check >= 7:
            return True, f"每周检测，上次检查: {days_since_check}天前"
        return False, f"本周已检测，{7 - days_since_check}天后再次检测"


def record_update(journal_key: str, papers_count: int, new_papers: int = 0):
    """Record that an update was performed."""
    update_log = load_update_log()

    if journal_key not in update_log:
        update_log[journal_key] = {}

    update_log[journal_key]['last_check'] = datetime.now().strftime('%Y-%m-%d')
    update_log[journal_key]['last_papers_count'] = papers_count
    update_log[journal_key]['new_papers'] = update_log[journal_key].get('new_papers', 0) + new_papers

    save_update_log(update_log)


class JournalCache:
    """Cache for journal data."""

    def __init__(self):
        self.cache_file = CACHE_FILE
        self.data = {}
        self._load()

    def _load(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except:
                self.data = {}

    def _save(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, journal_key: str) -> Optional[List[Dict]]:
        cached = self.data.get(journal_key)
        if not cached:
            return None
        cached_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
        if datetime.now() - cached_time > timedelta(hours=CACHE_EXPIRY_HOURS):
            return None
        return cached.get('papers')

    def set(self, journal_key: str, data):
        """Save data to cache."""
        self.data[journal_key] = {
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        self._save()


def load_cached_journal_papers(journal_key: str, target_volume: str = None, target_issue: str = None) -> Tuple[List[Dict], Dict]:
    """Load papers from local cache file (cache/journals/{journal_key}_papers.json).

    Args:
        journal_key: Journal identifier
        target_volume: Optional volume number to load
        target_issue: Optional issue number to load

    Returns:
        Tuple of (papers, issues_info)
    """
    cache_file = os.path.join(CACHE_DIR, 'journals', f'{journal_key}_papers.json')
    papers = []
    issues_info = {'volumes': [], 'issues': [], 'current_volume': None, 'current_issue': None}

    if not os.path.exists(cache_file):
        return papers, issues_info

    # Check if this is a continuous publishing journal
    journal_config = JOURNALS.get(journal_key, {})
    is_continuous = journal_config.get('type') == 'continuous'

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        raw_papers = data.get('papers', [])

        # Group papers by volume/issue
        volumes_dict = {}
        for p in raw_papers:
            vol = p.get('volume', 'Unknown') or 'Unknown'
            iss = p.get('issue', '1') or '1'

            if vol not in volumes_dict:
                volumes_dict[vol] = {'issues': {}, 'year': p.get('year', ''), 'all_papers': []}

            if iss not in volumes_dict[vol]['issues']:
                volumes_dict[vol]['issues'][iss] = []

            volumes_dict[vol]['issues'][iss].append(p)
            volumes_dict[vol]['all_papers'].append(p)

        # Build issues_info with ALL available volumes
        for vol_num in sorted(volumes_dict.keys(), key=lambda x: int(x) if str(x).isdigit() else 0, reverse=True)[:15]:
            vol_data = volumes_dict[vol_num]
            issues_info['volumes'].append({
                'number': vol_num,
                'year': vol_data.get('year', ''),
                'issue_count': len(vol_data['issues'])
            })

        # Determine which volume to show
        if target_volume:
            # Use specified volume if it exists
            if target_volume in volumes_dict:
                current_vol = target_volume
            else:
                # Volume not found, use latest
                current_vol = issues_info['volumes'][0]['number'] if issues_info['volumes'] else None
        else:
            # Default to latest volume
            current_vol = issues_info['volumes'][0]['number'] if issues_info['volumes'] else None

        issues_info['current_volume'] = current_vol

        # Get issues for current volume
        if current_vol and current_vol in volumes_dict:
            available_issues = sorted(
                volumes_dict[current_vol]['issues'].keys(),
                key=lambda x: int(x) if str(x).isdigit() else 0,
                reverse=True
            )
            issues_info['issues'] = available_issues

            # Determine which issue to show
            if target_issue:
                # Use specified issue if it exists
                if target_issue in volumes_dict[current_vol]['issues']:
                    current_iss = target_issue
                else:
                    # Issue not found, use latest
                    current_iss = available_issues[0] if available_issues else None
            else:
                # Default to latest issue
                current_iss = available_issues[0] if available_issues else None

            issues_info['current_issue'] = current_iss

            # Get papers for current volume/issue
            # For continuous publishing journals (like JMLR), show ALL papers in the volume
            if is_continuous:
                papers = volumes_dict[current_vol]['all_papers']
                # 按 issue 号排序（issue 号就是论文发布顺序）
                papers.sort(key=lambda x: int(x.get('issue', '0')) if str(x.get('issue', '0')).isdigit() else 0, reverse=True)
                print(f"Loaded {len(raw_papers)} papers for {journal_key}, showing Vol {current_vol} (continuous): {len(papers)} papers")
            elif current_iss and current_iss in volumes_dict[current_vol]['issues']:
                papers = volumes_dict[current_vol]['issues'][current_iss]
                print(f"Loaded {len(raw_papers)} papers for {journal_key}, showing Vol {current_vol} Issue {current_iss}: {len(papers)} papers")

        issues_info['total_papers'] = len(raw_papers)
        issues_info['total_in_issue'] = len(papers)

    except Exception as e:
        print(f"Error loading cached papers for {journal_key}: {e}")

    return papers, issues_info

    def set(self, journal_key: str, papers: List[Dict]):
        self.data[journal_key] = {
            'papers': papers,
            'timestamp': datetime.now().isoformat()
        }
        self._save()


def fetch_jmlr_papers(volume: str = None, issue: str = None) -> Tuple[List[Dict], Dict]:
    """Fetch papers from JMLR website, organized by volume/issue.

    Returns:
        Tuple of (papers, issues_info) where issues_info contains available volumes/issues
    """
    papers = []
    issues_info = {'volumes': [], 'current_volume': None, 'current_issue': None}

    try:
        # Get volumes index page
        url = 'https://www.jmlr.org/papers/'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
            html = response.read().decode('utf-8')

        # Find all volumes with their date ranges
        # <a href="v25"><font class="volume">Volume 25</font></a>
        # (January 2024 - December 2024)
        vol_pattern = r'<a href="v(\d+)"><font class="volume">Volume \d+</font></a>\s*\(([^)]+)\)'
        vol_matches = re.findall(vol_pattern, html)

        for vol_num, date_range in vol_matches[:20]:  # Keep last 20 volumes (covers 2019-present)
            issues_info['volumes'].append({
                'number': vol_num,
                'date_range': date_range.strip()
            })

        if not issues_info['volumes']:
            print("No volumes found on JMLR")
            return papers, issues_info

        # Determine which volume to fetch
        if volume:
            target_vol = volume
        else:
            target_vol = issues_info['volumes'][0]['number']

        issues_info['current_volume'] = target_vol

        # Fetch papers from target volume
        vol_url = f'https://www.jmlr.org/papers/v{target_vol}/'
        req = urllib.request.Request(vol_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
            vol_html = response.read().decode('utf-8')

        # Parse papers with issue numbers
        paper_pattern = r'<dt>([^<]+)</dt>\s*<dd><b><i>([^<]+)</i></b>;\s*\((\d+)\):([0-9&;a-z\-]+),\s*(\d{4})'
        matches = re.findall(paper_pattern, vol_html)

        # Group papers by issue, also keep all papers
        issues_dict = {}
        all_papers = []
        for title, authors, issue_num, pages, year in matches:
            issue_key = issue_num
            if issue_key not in issues_dict:
                issues_dict[issue_key] = []

            pages = pages.replace('&minus;', '-')

            # Find paper URL
            title_pos = vol_html.find(title)
            if title_pos > 0:
                search_region = vol_html[title_pos:title_pos+500]
                url_match = re.search(r'<a href=[\'"]/papers/v\d+/([a-z0-9\-]+)\.html[\'"]', search_region)
                paper_id = url_match.group(1) if url_match else f"{target_vol}-{issue_num}"
            else:
                paper_id = f"{target_vol}-{issue_num}"

            paper = {
                'title': title.strip(),
                'authors': [a.strip() for a in authors.split(',') if a.strip()],
                'volume': target_vol,
                'issue': issue_num,
                'pages': pages,
                'year': year,
                'month': '',
                'url': f'https://www.jmlr.org/papers/v{target_vol}/{paper_id}.html',
                'abstract': '',
                'doi': '',
                'journal': 'JMLR'
            }
            issues_dict[issue_key].append(paper)
            all_papers.append(paper)

        # Get available issues for this volume
        issues_info['issues'] = sorted(issues_dict.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
        issues_info['total_papers_in_volume'] = len(all_papers)

        # For JMLR continuous publishing: always show all papers in volume
        # Each "issue" is just a paper number, so showing all makes more sense
        target_issue = 'all'
        papers = all_papers
        issues_info['current_issue'] = 'all'

        print(f"JMLR Volume {target_vol}: {len(papers)} papers total (continuous publishing)")

    except Exception as e:
        print(f"Error fetching JMLR: {e}")

    return papers, issues_info


def fetch_crossref_papers(issn: str, journal_key: str, volume: str = None, issue: str = None, fetch_all: bool = True, from_year: int = 2019) -> Tuple[List[Dict], Dict]:
    """Fetch papers from Crossref API, organized by volume/issue.

    Args:
        issn: Journal ISSN
        journal_key: Short journal key (e.g., 'AoS', 'JASA')
        volume: Specific volume to fetch (optional)
        issue: Specific issue to fetch (optional)
        fetch_all: If True, fetch ALL papers using pagination

    Returns:
        Tuple of (papers, issues_info)
    """
    papers = []
    issues_info = {'volumes': [], 'issues': [], 'current_volume': None, 'current_issue': None}

    try:
        # Use pagination to fetch ALL papers from 2019 onwards
        all_items = []
        offset = 0
        batch_size = 500  # Crossref max per request

        # Build filter with year range
        filter_parts = [
            f'issn:{issn}',
            'type:journal-article',
            f'from-pub-date:{from_year}'  # Only papers from 2019 onwards
        ]

        while True:
            params = {
                'filter': ','.join(filter_parts),
                'sort': 'published',
                'order': 'desc',
                'rows': batch_size,
                'offset': offset,
                'select': 'DOI,title,author,published-print,published-online,abstract,volume,issue,page'
            }

            url = f"https://api.crossref.org/works?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(url, headers={
                'User-Agent': 'arXiv-Recommender/2.0 (mailto:research@example.com)'
            })

            with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
                data = json.loads(response.read().decode('utf-8'))
                message = data.get('message', {})
                items = message.get('items', [])
                total = message.get('total-results', 0)

                all_items.extend(items)

                print(f"  {journal_key}: Fetched {len(all_items)}/{total} papers...", end='\r')

                # Check if we have all papers
                if len(items) < batch_size or len(all_items) >= total:
                    break

                offset += batch_size

                # Rate limiting - be nice to Crossref
                time.sleep(0.5)

                # Safety limit
                if not fetch_all and len(all_items) >= 1000:
                    break

        print(f"  {journal_key}: Total {len(all_items)} papers fetched.          ")

        # Group papers by volume/issue
        volumes_dict = {}
        for item in all_items:
            vol = item.get('volume', 'Unknown')
            iss = item.get('issue', '1')

            if vol not in volumes_dict:
                volumes_dict[vol] = {'issues': {}, 'year': ''}

            if iss not in volumes_dict[vol]['issues']:
                volumes_dict[vol]['issues'][iss] = []

            paper = {
                'doi': item.get('DOI', ''),
                'title': '',
                'authors': [],
                'year': '',
                'month': '',
                'volume': vol,
                'issue': iss,
                'pages': item.get('page', ''),
                'abstract': item.get('abstract', ''),
                'journal': journal_key
            }

            # Title
            titles = item.get('title', [])
            paper['title'] = titles[0] if titles else 'Unknown Title'

            # Authors
            authors = []
            for author in item.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    authors.append(f"{given} {family}".strip())
            paper['authors'] = authors

            # Publication date
            pub_date = item.get('published-print') or item.get('published-online') or {}
            date_parts = pub_date.get('date-parts', [[]])
            if date_parts and date_parts[0]:
                parts = date_parts[0]
                paper['year'] = str(parts[0]) if len(parts) > 0 else ''
                paper['month'] = str(parts[1]).zfill(2) if len(parts) > 1 else ''

            if vol and paper['year'] and not volumes_dict[vol]['year']:
                volumes_dict[vol]['year'] = paper['year']

            paper['url'] = f"https://doi.org/{paper['doi']}" if paper['doi'] else ''

            volumes_dict[vol]['issues'][iss].append(paper)

        # Build issues_info
        for vol_num in sorted(volumes_dict.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)[:15]:
            vol_data = volumes_dict[vol_num]
            issues_info['volumes'].append({
                'number': vol_num,
                'year': vol_data.get('year', ''),
                'issue_count': len(vol_data['issues'])
            })

        # Determine current volume
        if volume and volume in volumes_dict:
            target_vol = volume
        elif issues_info['volumes']:
            target_vol = issues_info['volumes'][0]['number']
        else:
            target_vol = None

        issues_info['current_volume'] = target_vol

        if target_vol and target_vol in volumes_dict:
            # Get issues for this volume
            issues_info['issues'] = sorted(
                volumes_dict[target_vol]['issues'].keys(),
                key=lambda x: int(x) if x.isdigit() else 0,
                reverse=True
            )

            # Determine current issue
            if issue and issue in volumes_dict[target_vol]['issues']:
                target_issue = issue
            elif issues_info['issues']:
                target_issue = issues_info['issues'][0]
            else:
                target_issue = None

            issues_info['current_issue'] = target_issue

            # Get papers for target issue
            if target_issue:
                papers = volumes_dict[target_vol]['issues'][target_issue]

        # Total papers in this issue
        issues_info['total_in_issue'] = len(papers)
        issues_info['total_papers'] = len(all_items)

        print(f"Found {len(papers)} papers from {journal_key} Volume {target_vol}, Issue {target_issue}")

    except Exception as e:
        print(f"Error fetching from Crossref: {e}")

    return papers, issues_info


class JournalTracker:
    """Track papers from top journals."""

    def __init__(self, user_config_path: str = None):
        self.cache = JournalCache()
        self.user_topics = []
        resolved_path = self._resolve_user_config_path(user_config_path)
        if resolved_path:
            self._load_user_topics(resolved_path)

    def _resolve_user_config_path(self, user_config_path: Optional[str]) -> Optional[str]:
        candidate_paths = []
        if user_config_path:
            candidate_paths.append(Path(user_config_path))
        candidate_paths.extend([USER_PROFILE_PATH, LEGACY_USER_CONFIG_PATH])

        for path in candidate_paths:
            if path and Path(path).exists():
                return str(path)
        return None

    def _load_user_topics(self, config_path: str):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            return

        topics = []
        keywords = config.get('keywords', {})
        if isinstance(keywords, dict):
            for topic, meta in keywords.items():
                if not isinstance(meta, dict):
                    continue
                if meta.get('category') in {'core', 'secondary'}:
                    topics.append(topic.lower())

        if not topics:
            focus = config.get('research_focus', {})
            topics.extend(t.lower() for t in focus.get('topics', []))

        # Preserve order while removing duplicates.
        self.user_topics = list(dict.fromkeys(topics))

    def compute_relevance(self, paper: Dict) -> float:
        if not self.user_topics:
            return 0.0

        text = (paper.get('title', '') + ' ' + paper.get('abstract', '')).lower()
        score = 0.0

        for topic in self.user_topics:
            if topic in text:
                score += 1.0

        return min(score, 5.0)

    def get_papers(self, journal_key: str, volume: str = None, issue: str = None, force_refresh: bool = False) -> Tuple[List[Dict], Dict, Dict]:
        """Get papers for a journal, organized by volume/issue.

        Returns:
            Tuple of (papers, issues_info, journal_info)
        """
        journal = JOURNALS.get(journal_key)
        if not journal:
            return [], {}, {}

        # First, try to load from local cache (cache/journals/)
        if not force_refresh:
            cached_papers, cached_issues_info = load_cached_journal_papers(journal_key, volume, issue)
            if cached_papers:  # Only return if we have cached data
                for paper in cached_papers:
                    paper['relevance'] = self.compute_relevance(paper)
                return cached_papers, cached_issues_info, journal
            # If no cache, continue to fetch fresh data

        # Check if we should update based on detection frequency
        should_check, check_reason = should_check_for_updates(journal_key)
        print(f"[{journal_key}] {check_reason}")

        # Try cache first (cache key includes volume/issue)
        cache_key = f"{journal_key}_{volume or 'latest'}_{issue or 'latest'}"

        # Use cache if not forcing refresh and not due for scheduled check
        use_cache = not force_refresh and not should_check
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                papers, issues_info = cached
                # Still try to load citation data from history
                history = load_citation_history()
                today = datetime.now().strftime('%Y-%m-%d')
                for paper in papers:
                    paper_id = paper.get('doi') or paper.get('url', '').split('/')[-1]
                    if paper_id and paper_id in history:
                        paper['citations'] = history[paper_id].get(today, 0)
                        # Calculate trend
                        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                        old_count = history[paper_id].get(week_ago, paper['citations'])
                        paper['citation_trend'] = paper['citations'] - old_count if paper['citations'] else 0
                return papers, issues_info, journal

        # Fetch based on journal
        if journal_key == 'JMLR':
            papers, issues_info = fetch_jmlr_papers(volume, issue)
        else:
            papers, issues_info = fetch_crossref_papers(journal['issn'], journal_key, volume, issue)

        # Add relevance scores
        for paper in papers:
            paper['relevance'] = self.compute_relevance(paper)

        # Update citations (weekly) - only if we have papers and should check
        # Always update citations at most once per day, regardless of detection frequency
        update_log = load_update_log()
        last_citation_update = update_log.get(journal_key, {}).get('last_citation_update', '2000-01-01')
        last_citation_date = datetime.strptime(last_citation_update, '%Y-%m-%d')
        days_since_citation_update = (datetime.now() - last_citation_date).days

        if papers and days_since_citation_update >= 7:
            print(f"[{journal_key}] Updating citations (last update: {days_since_citation_update} days ago)...")
            papers = update_citations(papers, journal_key)
            # Record citation update
            if journal_key not in update_log:
                update_log[journal_key] = {}
            update_log[journal_key]['last_citation_update'] = datetime.now().strftime('%Y-%m-%d')
            save_update_log(update_log)
        else:
            # Load existing citation data from history
            history = load_citation_history()
            today = datetime.now().strftime('%Y-%m-%d')
            for paper in papers:
                paper_id = paper.get('doi') or paper.get('url', '').split('/')[-1]
                if paper_id and paper_id in history:
                    paper['citations'] = history[paper_id].get(today, 0)
                    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    old_count = history[paper_id].get(week_ago, paper['citations'])
                    paper['citation_trend'] = paper['citations'] - old_count if paper['citations'] else 0

        # Record update if we fetched fresh data
        if should_check or force_refresh:
            record_update(journal_key, len(papers))

        # Cache results
        self.cache.set(cache_key, (papers, issues_info))

        return papers, issues_info, journal

    def get_all_journals(self) -> List[Dict]:
        result = []
        for key, journal in JOURNALS.items():
            result.append({
                'key': key,
                'name': journal['name'],
                'short_name': journal['short_name'],
                'color': journal['color'],
                'icon': journal['icon'],
            })

        return result


def generate_journal_page(selected_journal: str = 'JMLR', volume: str = None, issue: str = None) -> str:
    """Generate HTML page for journal tracker with volume/issue navigation."""
    preferred_config = USER_PROFILE_PATH if USER_PROFILE_PATH.exists() else LEGACY_USER_CONFIG_PATH
    tracker = JournalTracker(str(preferred_config) if preferred_config.exists() else None)
    papers, issues_info, journal_info = tracker.get_papers(selected_journal, volume, issue)
    all_journals = tracker.get_all_journals()

    # Generate journal tabs
    tabs_html = ''
    for j in all_journals:
        active = 'active' if j['key'] == selected_journal else ''
        tabs_html += f'''
        <a href="/journal/{j['key']}" class="journal-tab {active}" style="--tab-color: {j['color']}">
            <span class="tab-icon">{j['icon']}</span>
            <span class="tab-name">{j['short_name']}</span>
        </a>'''

    # Generate volume selector
    volume_options = ''
    for vol in issues_info.get('volumes', [])[:10]:
        vol_num = vol.get('number', '')
        vol_year = vol.get('year', '')
        selected = 'selected' if vol_num == issues_info.get('current_volume') else ''
        label = f"Volume {vol_num}" + (f" ({vol_year})" if vol_year else "")
        volume_options += f'<option value="{vol_num}" {selected}>{label}</option>'

    # Generate issue selector - only for journals with traditional issues
    # JMLR uses continuous publishing, so skip issue selector
    current_issue = issues_info.get('current_issue', '')
    is_continuous = journal_info.get('type') == 'continuous' if journal_info else False

    if is_continuous:
        # For continuous publishing (JMLR), no issue selector needed
        issue_selector_html = ''
        issue_display = ''
        stats_issue_html = ''  # Don't show issue in stats for continuous publishing
    else:
        issue_options = ''
        for iss in issues_info.get('issues', [])[:50]:  # Limit to 50 issues
            selected = 'selected' if iss == current_issue else ''
            issue_options += f'<option value="{iss}" {selected}>Issue {iss}</option>'

        issue_selector_html = f'''
        <div class="nav-group">
            <label>期号:</label>
            <select class="nav-select" id="issueSelect" onchange="changeIssue()">
                {issue_options}
            </select>
        </div>'''
        issue_display = f"Issue {current_issue}" if current_issue else ""
        stats_issue_html = f'''
                <div class="stat-item">
                    <span class="stat-value">{issue_display}</span>
                    <span class="stat-label">期</span>
                </div>'''

    # Volume/Issue navigation
    current_vol = issues_info.get('current_volume', '')
    nav_html = f'''
    <div class="issue-nav">
        <div class="nav-group">
            <label>卷号:</label>
            <select class="nav-select" id="volumeSelect" onchange="changeVolume()">
                {volume_options}
            </select>
        </div>
        {issue_selector_html}
    </div>'''

    # Current issue info banner
    vol_display = f"Volume {current_vol}" if current_vol else ""
    total_papers = len(papers)
    relevant_count = sum(1 for p in papers if p.get('relevance', 0) > 0)

    # Calculate total citations and trending papers
    total_citations = sum(p.get('citations', 0) for p in papers)
    trending_papers = sum(1 for p in papers if p.get('citation_trend', 0) > 0)

    # Get update status
    should_check, update_reason = should_check_for_updates(selected_journal)
    update_log = load_update_log()
    last_update = update_log.get(selected_journal, {}).get('last_check', '从未')
    detection_config = DETECTION_CONFIG.get(selected_journal, {'frequency': 'weekly', 'description': ''})

    # Generate paper cards
    papers_html = ''
    for i, paper in enumerate(papers, 1):
        authors_str = ', '.join(paper.get('authors', [])[:3])
        if len(paper.get('authors', [])) > 3:
            authors_str += f" et al. ({len(paper['authors'])} authors)"

        # Publication info
        pub_info = ''
        if paper.get('pages'):
            pub_info += f"pp. {paper['pages']}"
        if paper.get('year'):
            pub_info += f", {paper['year']}"

        paper_url = paper.get('url', '') or f"https://doi.org/{paper.get('doi', '')}"

        # Relevance indicator
        relevance = paper.get('relevance', 0)
        relevance_html = ''
        if relevance > 0:
            stars = '⭐' * min(int(relevance), 5)
            relevance_html = f'<span class="relevance-badge">{stars}</span>'

        # Citation info with trend
        citations = paper.get('citations', 0)
        citation_trend = paper.get('citation_trend', 0)
        citation_html = ''
        if citations > 0:
            trend_icon = ''
            if citation_trend > 0:
                trend_icon = f'<span class="citation-trend up">↑{citation_trend}</span>'
            elif citation_trend < 0:
                trend_icon = f'<span class="citation-trend down">↓{abs(citation_trend)}</span>'
            citation_html = f'<span class="citation-count">📊 {citations}{trend_icon}</span>'

        abstract = paper.get('abstract', '')
        abstract_preview = abstract[:300] + '...' if len(abstract) > 300 else abstract

        papers_html += f'''
        <div class="paper-card">
            <div class="paper-header">
                <span class="paper-number">{i}</span>
                <a href="{paper_url}" class="paper-title" target="_blank">{paper.get('title', 'No Title')}</a>
                {relevance_html}
            </div>
            <div class="paper-authors">{authors_str}</div>
            <div class="paper-meta">
                <span class="meta-item">📄 {pub_info or 'N/A'}</span>
                {citation_html}
            </div>
            {f'<div class="paper-abstract">{abstract_preview}</div>' if abstract else ''}
            <div class="paper-actions">
                <a href="{paper_url}" class="action-btn" target="_blank">🔗 论文链接</a>
                <a href="https://scholar.google.com/scholar?q={urllib.parse.quote(paper.get('title', ''))}" class="action-btn" target="_blank">🎓 Google Scholar</a>
            </div>
        </div>'''

    if not papers:
        papers_html = '''
        <div class="empty-state">
            <div class="empty-icon">📭</div>
            <div class="empty-text">暂无数据</div>
        </div>'''

    journal_color = journal_info.get('color', '#7c3aed') if journal_info else '#7c3aed'
    journal_name = journal_info.get('name', 'Journal') if journal_info else 'Journal'
    journal_icon = journal_info.get('icon', '📚') if journal_info else '📚'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{journal_name} - {vol_display} {issue_display}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh; color: #e0e0e0; padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        .header {{
            text-align: center; padding: 25px 20px;
            background: rgba(255,255,255,0.03); border-radius: 20px;
            margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.08);
        }}
        .header h1 {{
            font-size: 2em;
            background: linear-gradient(135deg, #00d4ff 0%, #7c3aed 50%, #f472b6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .subtitle {{ color: #888; font-size: 0.95em; }}
        .nav-link {{ color: #00d4ff; text-decoration: none; margin-top: 12px; display: inline-block; font-size: 0.9em; }}
        .nav-link:hover {{ text-decoration: underline; }}

        /* Journal Tabs */
        .journal-tabs {{
            display: flex; justify-content: center; gap: 10px;
            margin-bottom: 20px; flex-wrap: wrap;
        }}
        .journal-tab {{
            display: flex; align-items: center; gap: 6px;
            padding: 10px 16px; background: rgba(255,255,255,0.05);
            border-radius: 10px; color: #888; text-decoration: none;
            transition: all 0.2s; border: 2px solid transparent;
            font-size: 0.9em;
        }}
        .journal-tab:hover {{
            background: rgba(255,255,255,0.1); color: #fff;
            border-color: var(--tab-color);
        }}
        .journal-tab.active {{
            background: color-mix(in srgb, var(--tab-color) 20%, transparent);
            border-color: var(--tab-color); color: #fff;
        }}
        .tab-icon {{ font-size: 1.2em; }}
        .tab-name {{ font-weight: 600; }}

        /* Issue Navigation */
        .issue-nav {{
            display: flex; justify-content: center; gap: 20px;
            margin-bottom: 20px; flex-wrap: wrap;
        }}
        .nav-group {{
            display: flex; align-items: center; gap: 8px;
        }}
        .nav-group label {{
            color: #888; font-size: 0.9em;
        }}
        .nav-select {{
            padding: 8px 16px; background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;
            color: #fff; font-size: 0.95em; cursor: pointer;
            min-width: 160px;
        }}
        .nav-select option {{ background: #1a1a2e; }}

        /* Issue Banner */
        .issue-banner {{
            background: linear-gradient(135deg, color-mix(in srgb, {journal_color} 15%, transparent), transparent);
            border: 1px solid color-mix(in srgb, {journal_color} 40%, transparent);
            border-radius: 14px; padding: 18px; margin-bottom: 20px;
        }}
        .issue-title {{
            font-size: 1.2em; font-weight: 600; color: {journal_color};
            margin-bottom: 10px;
        }}
        .issue-stats {{
            display: flex; gap: 25px; flex-wrap: wrap;
        }}
        .stat-item {{
            display: flex; align-items: center; gap: 6px;
        }}
        .stat-value {{ font-size: 1.3em; font-weight: bold; color: #fff; }}
        .stat-label {{ font-size: 0.8em; color: #888; }}
        .update-status {{
            display: flex; align-items: center; gap: 15px;
            margin-top: 12px; padding-top: 12px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 0.85em;
        }}
        .status-icon {{ font-size: 1em; }}
        .status-text {{ color: #888; }}
        .status-time {{ color: #666; margin-left: auto; }}

        /* Papers Grid */
        .papers-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 16px;
        }}
        .paper-card {{
            background: rgba(255,255,255,0.03); border-radius: 14px; padding: 18px;
            border: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease;
        }}
        .paper-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(124,58,237,0.3);
        }}
        .paper-header {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }}
        .paper-number {{
            background: linear-gradient(135deg, #7c3aed, #00d4ff);
            color: #fff; width: 26px; height: 26px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.75em; font-weight: bold; flex-shrink: 0;
        }}
        .paper-title {{
            color: #fff; text-decoration: none; font-weight: 600;
            line-height: 1.35; flex: 1; font-size: 0.95em;
        }}
        .paper-title:hover {{ color: #00d4ff; }}
        .relevance-badge {{ font-size: 0.75em; flex-shrink: 0; }}
        .paper-authors {{ color: #888; font-size: 0.8em; margin-bottom: 6px; }}
        .paper-meta {{ font-size: 0.75em; color: #666; margin-bottom: 10px; display: flex; gap: 15px; flex-wrap: wrap; }}
        .citation-count {{
            color: #10b981; font-weight: 500;
        }}
        .citation-trend {{
            font-size: 0.85em; margin-left: 4px; font-weight: bold;
        }}
        .citation-trend.up {{ color: #10b981; }}
        .citation-trend.down {{ color: #ef4444; }}
        .paper-abstract {{
            font-size: 0.8em; color: #aaa; line-height: 1.5;
            margin-bottom: 10px; padding: 8px;
            background: rgba(0,0,0,0.2); border-radius: 6px;
        }}
        .paper-actions {{ display: flex; gap: 6px; flex-wrap: wrap; }}
        .action-btn {{
            padding: 5px 10px; background: rgba(255,255,255,0.05);
            border-radius: 6px; color: #00d4ff; text-decoration: none;
            font-size: 0.75em; transition: all 0.2s;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .action-btn:hover {{
            background: rgba(0,212,255,0.1);
        }}

        .empty-state {{
            text-align: center; padding: 50px 20px;
            background: rgba(255,255,255,0.02); border-radius: 14px;
        }}
        .empty-icon {{ font-size: 3em; margin-bottom: 12px; }}
        .empty-text {{ color: #888; }}

        .footer {{
            text-align: center; padding: 25px; color: #555;
            font-size: 0.8em; margin-top: 25px;
        }}

        @media (max-width: 768px) {{
            .papers-grid {{ grid-template-columns: 1fr; }}
            .issue-nav {{ flex-direction: column; align-items: center; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 顶刊追踪</h1>
            <div class="subtitle">JMLR · 统计四大最新论文</div>
            <a href="/" class="nav-link">← 返回每日推荐</a>
        </div>

        <div class="journal-tabs">
            {tabs_html}
        </div>

        {nav_html}

        <div class="issue-banner">
            <div class="issue-title">{journal_icon} {journal_name}</div>
            <div class="issue-stats">
                <div class="stat-item">
                    <span class="stat-value">{vol_display}</span>
                    <span class="stat-label">卷</span>
                </div>
                {stats_issue_html}
                <div class="stat-item">
                    <span class="stat-value">{total_papers}</span>
                    <span class="stat-label">篇论文</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">{relevant_count}</span>
                    <span class="stat-label">与您相关</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">{total_citations}</span>
                    <span class="stat-label">总引用</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">↑{trending_papers}</span>
                    <span class="stat-label">引用增长</span>
                </div>
            </div>
            <div class="update-status">
                <span class="status-icon">🔄</span>
                <span class="status-text">检测策略: {detection_config.get('description', '')}</span>
                <span class="status-time">上次更新: {last_update}</span>
            </div>
        </div>

        <div class="papers-grid">
            {papers_html}
        </div>

        <div class="footer">
            <p>数据来源: Crossref API + JMLR 官网 + Semantic Scholar</p>
            <p>引用数据每周更新 | 检测策略: JMLR每日, 统计四大每周</p>
        </div>
    </div>

    <script>
    function changeVolume() {{
        const vol = document.getElementById('volumeSelect').value;
        location.href = '/journal/{selected_journal}/v/' + vol;
    }}
    function changeIssue() {{
        const vol = document.getElementById('volumeSelect').value;
        const iss = document.getElementById('issueSelect').value;
        location.href = '/journal/{selected_journal}/v/' + vol + '/i/' + iss;
    }}
    </script>
</body>
</html>'''


if __name__ == '__main__':
    # Test
    html = generate_journal_page('JMLR')
    with open(PROJECT_ROOT / 'journal_test.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Test page generated: journal_test.html")
