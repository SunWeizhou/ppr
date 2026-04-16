"""
Learn from a good paper you found.
Usage: python learn_paper.py <arxiv_id_or_url>
Example: python learn_paper.py 2303.12345
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET
import ssl
import json
import os

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# 使用相对路径
from pathlib import Path
_PROJECT_ROOT = Path(__file__).parent.resolve()
LEARNED_PATH = _PROJECT_ROOT / 'learned_papers.json'


def fetch_paper(arxiv_id: str):
    """Fetch paper info from arXiv."""
    # Clean ID
    arxiv_id = arxiv_id.replace('https://arxiv.org/abs/', '').replace('http://arxiv.org/abs/', '')
    arxiv_id = arxiv_id.split('v')[0]  # Remove version

    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
            xml_data = resp.read().decode('utf-8')

        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        entry = root.find('atom:entry', ns)
        if entry is None:
            return None

        paper = {}
        title = entry.find('atom:title', ns)
        paper['title'] = title.text.strip() if title is not None else ''

        abstract = entry.find('atom:summary', ns)
        paper['abstract'] = abstract.text.strip() if abstract is not None else ''

        link = entry.find('atom:id', ns)
        paper['id'] = link.text.split('/abs/')[-1] if link is not None else arxiv_id

        authors = []
        for author in entry.findall('atom:author', ns):
            name = author.find('atom:name', ns)
            if name is not None:
                authors.append(name.text)
        paper['authors'] = authors

        return paper

    except Exception as e:
        print(f"Error fetching paper: {e}")
        return None


def extract_topics(title: str, abstract: str) -> list:
    """Extract key topics from paper."""
    text = (title + ' ' + abstract).lower()

    patterns = [
        r'in-context learning',
        r'conformal prediction',
        r'statistical learning theory',
        r'generalization bound',
        r'sample complexity',
        r'rademacher',
        r'minimax',
        r'excess risk',
        r'bayesian inference',
        r'attention mechanism',
        r'transformer',
        r'reinforcement learning',
        r'self-supervised',
        r'contrastive learning',
        r'neural network',
        r'deep learning',
        r'optimization',
        r'stochastic gradient',
        r'overparameterization',
        r'double descent',
    ]

    found = []
    for p in patterns:
        if re.search(p, text):
            match = re.search(p, text)
            if match:
                found.append(match.group())

    # Also extract significant words
    import re
    words = re.findall(r'\b[a-z]{6,}\b', text)
    from collections import Counter
    word_freq = Counter(words)
    stop_words = {'learning', 'model', 'method', 'approach', 'propose', 'paper',
                  'result', 'study', 'analysis', 'using', 'based', 'propose'}
    for w, _ in word_freq.most_common(10):
        if w not in stop_words and w not in found:
            found.append(w)

    return list(set(found))[:10]


def add_to_learned(paper: dict):
    """Add paper to learned collection."""
    if os.path.exists(LEARNED_PATH):
        with open(LEARNED_PATH, 'r') as f:
            data = json.load(f)
    else:
        data = {'papers': [], 'topics': []}

    # Check if already exists
    if any(p['id'] == paper['id'] for p in data['papers']):
        print(f"Paper {paper['id']} already in learned collection.")
        return

    # Add paper
    data['papers'].append({
        'id': paper['id'],
        'title': paper['title'],
        'abstract': paper['abstract'][:1000],
        'added_date': __import__('datetime').datetime.now().strftime('%Y-%m-%d')
    })

    # Extract and add topics
    topics = extract_topics(paper['title'], paper['abstract'])
    for t in topics:
        if t not in data['topics']:
            data['topics'].append(t)

    with open(LEARNED_PATH, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nAdded to learned papers:")
    print(f"  Title: {paper['title'][:60]}...")
    print(f"  Extracted topics: {topics[:5]}")
    print(f"\nTotal learned papers: {len(data['papers'])}")
    print(f"Total topics: {len(data['topics'])}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python learn_paper.py <arxiv_id>")
        print("Example: python learn_paper.py 2303.12345")
        print("\nThis will extract topics from the paper and use them")
        print("to improve future recommendations.")
        sys.exit(1)

    arxiv_id = sys.argv[1]
    print(f"Fetching paper {arxiv_id}...")

    paper = fetch_paper(arxiv_id)
    if paper is None:
        print("Could not fetch paper.")
        sys.exit(1)

    print(f"\nTitle: {paper['title']}")
    print(f"Authors: {', '.join(paper['authors'][:3])}")

    add_to_learned(paper)

    print("\nRun the recommender again to see updated recommendations!")


if __name__ == '__main__':
    import re
    main()
