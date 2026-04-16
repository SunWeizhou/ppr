# Journal Trends Analysis Feature Design

## Overview

Add trend analysis functionality to the journal tracking page, showing:
1. **Research topic trends** - keyword frequency across recent issues
2. **Author/institution trends** - active authors and collaboration patterns

## Goals

- **Primary**: Personal research insights - understand field developments, discover emerging research directions
- **Secondary**: Enhance paper recommendations with trend data

## Scope

- **Time range**: Last 3-5 issues (approximately 1.5-2.5 years for traditional journals)
- **Display location**: Embedded in existing journal page (between issue banner and paper list)
- **Update frequency**: Compute once per journal update (keywords change slowly)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Flow                                 │
├─────────────────────────────────────────────────────────────┤
│  journal_update.py                                           │
│       │                                                      │
│       ▼                                                      │
│  update_journal() ──► save_papers() ──► extract_trends()    │
│                                              │               │
│                                              ▼               │
│                                    {journal}_trends.json     │
│                                              │               │
│  journal_tracker.py                          │               │
│       │                                      │               │
│       ▼                                      ▼               │
│  generate_journal_page() ◄── load_trends() ──┘               │
│       │                                                      │
│       ▼                                                      │
│  Render trends panel ──► HTML page                           │
└─────────────────────────────────────────────────────────────┘
```

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `keyword_extractor.py` | **New** | Keyword extraction and trend analysis logic |
| `journal_update.py` | Modify | Call trend extraction at end of `update_journal()` |
| `journal_tracker.py` | Modify | Render trends panel in `generate_journal_page()` |

## Data Structure

### Trends Cache File

**Location**: `cache/journals/{journal_key}_trends.json`

```json
{
  "journal": "AoS",
  "analyzed_at": "2026-04-08T10:00:00",
  "papers_analyzed": 125,
  "by_issue": {
    "V54I1": {
      "keywords": {
        "high-dimensional inference": 5,
        "causal inference": 4,
        "optimal transport": 3
      },
      "top_keywords": ["high-dimensional inference", "causal inference", "optimal transport"],
      "top_authors": ["Peter Bickel", "Cun-Hui Zhang"],
      "paper_count": 21
    }
  },
  "recent_trends": {
    "hot_keywords": [
      {"keyword": "optimal transport", "change": 3},
      {"keyword": "diffusion models", "change": 2}
    ],
    "recurring_authors": ["Peter Bickel", "Cun-Hui Zhang"]
  }
}
```

### Keyword Source

Use existing user keyword configuration from `user_profile.json`:
- `keywords.core` - Core research interests (weight > 3)
- `keywords.secondary` - Secondary interests

## UI Design

### Placement

Embed between `.issue-banner` and `.papers-grid` in the journal page.

### Layout

```
┌────────────────────────────────────────────────────────┐
│  📊 Annals of Statistics  Vol.54 Issue 1               │
│  21 papers | Updated: 2026-03-15                       │
├────────────────────────────────────────────────────────┤
│  📈 本期热门主题                    基于最近 3 期分析    │
│  ┌──────────────┬──────────────┬──────────────┐        │
│  │ #1 高维推断   │ #2 因果推断   │ #3 最优传输   │        │
│  │ 5 篇 ↑2      │ 4 篇 ↑1      │ 3 篇 NEW     │        │
│  │ ████░░░░░░   │ ███░░░░░░░   │ ██░░░░░░░░   │        │
│  └──────────────┴──────────────┴──────────────┘        │
│  👥 活跃作者: Peter Bickel, Cun-Hui Zhang, ...         │
├────────────────────────────────────────────────────────┤
│  Paper list...                                         │
└────────────────────────────────────────────────────────┘
```

### HTML Structure

```html
<div class="trends-panel">
    <div class="trends-header">
        <h3>📈 本期热门主题</h3>
        <span class="trends-subtitle">基于最近 {n} 期分析</span>
    </div>
    <div class="trends-grid">
        <div class="trend-card">
            <div class="trend-rank">#1</div>
            <div class="trend-keyword">Deep Learning</div>
            <div class="trend-count">12 篇论文 <span class="trend-change up">↑2</span></div>
            <div class="trend-bar">
                <div class="trend-fill" style="width: 85%"></div>
            </div>
        </div>
        <!-- More cards... -->
    </div>
    <div class="trends-authors">
        <span class="authors-label">👥 活跃作者:</span>
        <span class="author-tag">Peter Bickel</span>
        <span class="author-tag">Cun-Hui Zhang</span>
    </div>
</div>
```

### CSS Styling

Follow existing design patterns from `journal_tracker.py`:
- Background: `rgba(124, 58, 237, 0.08)`
- Border: `1px solid rgba(124, 58, 237, 0.2)`
- Border-radius: `14px`
- Use journal-specific color via `var(--tab-color)`

## Implementation Details

### 1. keyword_extractor.py (New File)

```python
"""
Keyword extraction and trend analysis for journals.
"""

import json
import os
from collections import Counter
from typing import Dict, List, Tuple

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache', 'journals')

def extract_keywords_from_papers(papers: List[Dict], config_keywords: Dict) -> Counter:
    """Extract keyword frequencies from papers."""
    from utils import count_keyword

    counts = Counter()
    for paper in papers:
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        for keyword in config_keywords:
            if count_keyword(text, keyword) > 0:
                counts[keyword] += 1
    return counts

def extract_author_stats(papers: List[Dict]) -> Dict:
    """Extract author statistics from papers."""
    author_counts = Counter()
    for paper in papers:
        for author in paper.get('authors', []):
            author_counts[author] += 1
    return {
        'top_authors': [a for a, _ in author_counts.most_common(5)],
        'author_count': len(author_counts)
    }

def compute_trends(journal_key: str, papers: List[Dict], config: Dict) -> Dict:
    """Compute trends for a journal."""
    # Group papers by issue
    by_issue = {}
    for paper in papers:
        vol = paper.get('volume', '')
        iss = paper.get('issue', '')
        key = f"V{vol}I{iss}"
        if key not in by_issue:
            by_issue[key] = []
        by_issue[key].append(paper)

    # Get config keywords
    config_keywords = list(config.get('keywords', {}).keys())

    # Analyze each issue
    issue_trends = {}
    for issue_key, issue_papers in by_issue.items():
        keyword_counts = extract_keywords_from_papers(issue_papers, config_keywords)
        author_stats = extract_author_stats(issue_papers)

        issue_trends[issue_key] = {
            'keywords': dict(keyword_counts.most_common(10)),
            'top_keywords': [k for k, _ in keyword_counts.most_common(5)],
            'top_authors': author_stats['top_authors'],
            'paper_count': len(issue_papers)
        }

    return {
        'journal': journal_key,
        'analyzed_at': datetime.now().isoformat(),
        'papers_analyzed': len(papers),
        'by_issue': issue_trends
    }

def save_trends(journal_key: str, trends: Dict):
    """Save trends to cache file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f'{journal_key}_trends.json')
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)

def load_trends(journal_key: str) -> Dict:
    """Load trends from cache file."""
    cache_file = os.path.join(CACHE_DIR, f'{journal_key}_trends.json')
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}
```

### 2. journal_update.py Modification

Add at end of `update_journal()` function (after line 304):

```python
# Extract and save trends
from keyword_extractor import compute_trends, save_trends
from config_manager import get_config

config = get_config()
trends = compute_trends(journal_key, all_papers, config)
save_trends(journal_key, trends)
```

### 3. journal_tracker.py Modification

In `generate_journal_page()` function, add trends panel generation after issue banner.

## Testing Plan

1. **Unit tests**: Test keyword extraction with sample papers
2. **Integration tests**: Verify trends are computed during journal update
3. **Visual tests**: Check panel renders correctly in browser

## Success Criteria

- [ ] Trends computed and cached when journals update
- [ ] Panel displays top 5 keywords with counts and trend indicators
- [ ] Panel displays top 3 active authors
- [ ] Panel matches existing UI design patterns
- [ ] No significant impact on page load time (< 100ms)
