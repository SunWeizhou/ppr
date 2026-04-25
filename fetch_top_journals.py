"""
Fetch paper metadata from top 4 statistics journals (2019-present)
Only fetches: title, authors, DOI/link - no full text download

Journals:
- Annals of Statistics (AoS)
- JASA
- Biometrika
- JRSS-B
"""

import json
import os
import time
import urllib.request
import urllib.parse
import ssl
from datetime import datetime

SSL_CONTEXT = ssl.create_default_context()

# Top 4 Statistics Journals
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

CACHE_DIR = 'cache/journals'
os.makedirs(CACHE_DIR, exist_ok=True)


def fetch_journal_papers(journal_key: str, issn: str, from_year: int = 2019) -> list:
    """Fetch all paper metadata from a journal since from_year."""
    all_papers = []
    offset = 0
    batch_size = 500

    filter_str = f'issn:{issn},type:journal-article,from-pub-date:{from_year}'

    print(f"\nFetching {journal_key} (ISSN: {issn}) from {from_year}...")

    while True:
        params = {
            'filter': filter_str,
            'sort': 'published',
            'order': 'desc',
            'rows': batch_size,
            'offset': offset,
            'select': 'DOI,title,author,published-print,published-online,volume,issue'
        }

        url = f"https://api.crossref.org/works?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Stats-Journal-Tracker/1.0'
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

                print(f"  Progress: {len(all_papers)}/{total} papers", end='\r')

                if len(items) < batch_size or offset + batch_size >= total:
                    break

                offset += batch_size
                time.sleep(0.3)

        except Exception as e:
            print(f"\n  Error: {e}")
            break

    print(f"\n  Done: {len(all_papers)} papers")
    return all_papers


def parse_paper(item: dict, journal_key: str) -> dict:
    """Parse paper metadata (title, authors, link only)."""
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
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0]) if len(date_parts[0]) > 0 else ''

        doi = item.get('DOI', '')

        return {
            'title': title,
            'authors': authors,
            'year': year,
            'volume': item.get('volume', ''),
            'issue': item.get('issue', ''),
            'doi': doi,
            'url': f"https://doi.org/{doi}" if doi else '',
            'journal': journal_key
        }
    except:
        return None


def fetch_all_journals(from_year: int = 2019):
    """Fetch metadata from all top journals."""
    all_papers = {}

    for journal_key, info in TOP_JOURNALS.items():
        print(f"\n{'='*50}")
        print(f"{info['name']}")
        print('='*50)

        # Try print ISSN first, then online ISSN
        papers = fetch_journal_papers(journal_key, info['issn'], from_year)
        if len(papers) < 100:  # If few results, try eISSN
            print(f"  Trying eISSN {info['eissn']}...")
            papers_e = fetch_journal_papers(journal_key, info['eissn'], from_year)
            if len(papers_e) > len(papers):
                papers = papers_e

        all_papers[journal_key] = papers

        # Save to cache
        cache_file = os.path.join(CACHE_DIR, f'{journal_key}_papers.json')
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'journal': info['name'],
                'fetched_at': datetime.now().isoformat(),
                'from_year': from_year,
                'count': len(papers),
                'papers': papers
            }, f, ensure_ascii=False, indent=2)

        time.sleep(1)

    return all_papers


if __name__ == '__main__':
    print("="*50)
    print("Top 4 Statistics Journals Tracker")
    print("Period: 2019 - present")
    print("Data: title, authors, DOI link only")
    print("="*50)

    papers = fetch_all_journals(from_year=2019)

    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    total = 0
    for jk, jp in papers.items():
        count = len(jp)
        total += count
        name = TOP_JOURNALS[jk]['name']
        print(f"  {jk}: {count} papers")
    print(f"\n  TOTAL: {total} papers")
    print("="*50)
