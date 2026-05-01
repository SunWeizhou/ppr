"""Markdown digest generator and summary helper."""

from __future__ import annotations

import re
from typing import Dict, List


class MarkdownGenerator:
    """Generate Markdown archive."""

    def generate(self, papers: list[dict], themes: list[str], date: str) -> str:
        md = f'''# arXiv Daily Digest

**Date:** {date}

**Research Themes:** {', '.join(themes)}

**Papers Recommended:** {len(papers)}

---

'''
        for i, paper in enumerate(papers, 1):
            authors = ', '.join(paper['authors'][:5])
            if len(paper['authors']) > 5:
                authors += " et al."

            md += f'''## {i}. {paper['title']}

**Authors:** {authors}

**arXiv:** [{paper['id']}]({paper['link']})

**Summary:** {paper.get('summary', 'No summary available.')}

**Relevance:** {paper.get('relevance_reason', 'Matches your research interests')}

**Score:** {paper.get('score', 0):.1f}

---

'''
        return md


def generate_summary(abstract: str, max_sentences: int = 3) -> str:
    """Generate concise summary."""
    if not abstract:
        return "No abstract available."
    sentences = re.split(r'(?<=[.!?])\s+', abstract)
    summary = '. '.join(sentences[:max_sentences])
    if len(summary) > 350:
        summary = summary[:350] + '...'
    return summary


__all__ = ["MarkdownGenerator", "generate_summary"]
