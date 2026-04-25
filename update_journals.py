"""
定期更新期刊论文缓存.

可以通过以下方式运行：
1. 手动运行: python update_journals.py
2. Windows任务计划程序：每天自动运行
3. 或集成到现有的每日推荐流程
"""

import json
import os
import time
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from pathlib import Path

from app_paths import CACHE_DIR as APP_CACHE_DIR
from journal_tracker import JOURNALS, fetch_jmlr_papers

SSL_CONTEXT = ssl.create_default_context()

# 传统统计期刊通过 Crossref 分页抓取；JMLR 走站点解析。
TOP_JOURNALS = {
    'AoS': {
        'name': 'Annals of Statistics',
        'issn': '0090-5364',
        'eissn': '2168-8966',
    },
    'JASA': {
        'name': 'Journal of the American Statistical Association',
        'issn': '0162-1459',
        'eissn': '1537-274X',
    },
    'Biometrika': {
        'name': 'Biometrika',
        'issn': '0006-3444',
        'eissn': '1464-3510',
    },
    'JRSS-B': {
        'name': 'Journal of the Royal Statistical Society: Series B',
        'issn': '0035-9246',
        'eissn': '1467-9868',
    }
}

CACHE_DIR = Path(APP_CACHE_DIR) / 'journals'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_journal_papers(journal_key: str, issn: str, from_year: int = 2019) -> list:
    """Fetch all papers from Crossref API with pagination."""
    all_papers = []
    offset = 0
    batch_size = 500

    filter_str = f'issn:{issn},type:journal-article,from-pub-date:{from_year}'

    print(f"  Fetching {journal_key} (ISSN: {issn})...")

    while True:
        params = {
            'filter': filter_str,
            'sort': 'published',
            'order': 'desc',
            'rows': batch_size,
            'offset': offset,
            'select': 'DOI,title,author,published-print,published-online,volume,issue,page'
        }

        url = f"https://api.crossref.org/works?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Stats-Journal-Tracker/2.0'
            })

            with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
                data = json.loads(response.read().decode('utf-8'))
                message = data.get('message', {})
                items = message.get('items', [])
                total = message.get('total-results', 0)

                for item in items:
                    paper = parse_paper(item, journal_key)
                    if paper:
                        all_papers.append(paper)

                print(f"    Progress: {len(all_papers)}/{total}", end='\r')

                if len(items) < batch_size or offset + batch_size >= total:
                    break

                offset += batch_size
                time.sleep(0.3)

        except Exception as e:
            print(f"\n    Error: {e}")
            break

    print(f"\n    Done: {len(all_papers)} papers")
    return all_papers


def _journal_cache_path(journal_key: str) -> Path:
    return CACHE_DIR / f'{journal_key}_papers.json'


def _load_previous_count(journal_key: str) -> int:
    cache_file = _journal_cache_path(journal_key)
    if not cache_file.exists():
        return 0
    try:
        data = json.loads(cache_file.read_text(encoding='utf-8'))
        return int(data.get('count', 0) or 0)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _save_journal_cache(journal_key: str, journal_name: str, papers: list, from_year: int = 2019) -> None:
    cache_file = _journal_cache_path(journal_key)
    payload = {
        'journal': journal_name,
        'fetched_at': datetime.now().isoformat(),
        'count': len(papers),
        'papers': papers,
    }
    if journal_key != 'JMLR':
        payload['from_year'] = from_year
    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def update_journal(journal_key: str, from_year: int = 2019, force: bool = False) -> int:
    """Update a single journal cache file and return the number of new papers."""
    if journal_key == 'JMLR':
        papers, _ = fetch_jmlr_papers()
        journal_name = JOURNALS['JMLR']['name']
    else:
        info = TOP_JOURNALS.get(journal_key)
        if not info:
            raise ValueError(f'Unsupported journal key: {journal_key}')

        papers = fetch_journal_papers(journal_key, info['issn'], from_year)
        if len(papers) < 100 and info.get('eissn'):
            print(f"  Trying eISSN {info['eissn']}...")
            papers_e = fetch_journal_papers(journal_key, info['eissn'], from_year)
            if len(papers_e) > len(papers):
                papers = papers_e
        journal_name = info['name']

    previous_count = 0 if force else _load_previous_count(journal_key)
    _save_journal_cache(journal_key, journal_name, papers, from_year=from_year)
    return max(0, len(papers) - previous_count)


def parse_paper(item: dict, journal_key: str) -> dict:
    """Parse paper metadata."""
    try:
        titles = item.get('title', [])
        title = titles[0] if titles else None
        if not title:
            return None

        authors = []
        for author in item.get('author', []):
            given = author.get('given', '')
            family = author.get('family', '')
            if family:
                authors.append(f"{given} {family}".strip())

        pub_date = item.get('published-print') or item.get('published-online') or {}
        date_parts = pub_date.get('date-parts', [[]])
        year = ''
        month = ''
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            year = str(parts[0]) if len(parts) > 0 else ''
            month = str(parts[1]).zfill(2) if len(parts) > 1 else ''

        return {
            'title': title,
            'authors': authors,
            'year': year,
            'month': month,
            'volume': item.get('volume', ''),
            'issue': item.get('issue', ''),
            'pages': item.get('page', ''),
            'doi': item.get('DOI', ''),
            'url': f"https://doi.org/{item.get('DOI', '')}" if item.get('DOI') else '',
            'journal': journal_key
        }
    except (KeyError, ValueError, TypeError) as e:
        print(f"[WARN] Failed to parse item: {e}")
        return None


def update_all_journals(from_year: int = 2019):
    """Update all journals."""
    print("=" * 50)
    print(f"Updating Top 4 Statistics Journals")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    all_papers = {}
    total_new = 0

    for journal_key, info in TOP_JOURNALS.items():
        print(f"\n[{info['name']}]")
        previous_count = _load_previous_count(journal_key)
        diff = update_journal(journal_key, from_year=from_year)
        cache_data = json.loads(_journal_cache_path(journal_key).read_text(encoding='utf-8'))
        papers = cache_data.get('papers', [])
        all_papers[journal_key] = papers
        total_new += diff
        print(f"  Saved: {len(papers)} papers (+{len(papers) - previous_count} total delta, +{diff} new)")

        time.sleep(1)

    print("\n" + "=" * 50)
    print(f"Update complete! Total new papers: {total_new}")
    print("=" * 50)

    return all_papers


if __name__ == '__main__':
    update_all_journals()
