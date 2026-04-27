"""Shared paper formatting, identity parsing, and status utilities."""

from __future__ import annotations

import html
import os
import re
import ssl
import urllib.request
from typing import Dict, List

from logger_config import get_logger

from utils import CATEGORY_NAMES

logger = get_logger(__name__)

# SSL context for HTTPS requests
_SSL_CONTEXT = ssl.create_default_context()


def parse_arxiv_identity(raw_id_or_url: str) -> Dict[str, str]:
    """Return stable arXiv identity fields from an id or abs/pdf URL."""
    raw = str(raw_id_or_url or '').strip()
    source_url = raw
    candidate = raw
    if '/abs/' in candidate:
        candidate = candidate.rsplit('/abs/', 1)[-1]
    elif '/pdf/' in candidate:
        candidate = candidate.rsplit('/pdf/', 1)[-1]
    candidate = candidate.split('?', 1)[0].split('#', 1)[0].removesuffix('.pdf')
    candidate = candidate.strip('/')

    match = re.match(r'^(?P<base>(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7}))(?P<version>v\d+)?$', candidate)
    if match:
        base_id = match.group('base')
        version = match.group('version') or ''
    else:
        base_id = candidate
        version = ''

    return {
        'base_id': base_id,
        'version': version,
        'canonical_id': base_id,
        'source_url': source_url or f'https://arxiv.org/abs/{base_id}',
    }


def download_pdfs(papers: List[Dict], output_dir: str, min_score: float = 2.5):
    """Download PDFs for high-scoring papers."""
    pdf_dir = os.path.join(output_dir, 'cache', 'pdfs')
    os.makedirs(pdf_dir, exist_ok=True)

    downloaded = []
    for paper in papers:
        if paper.get('score', 0) >= min_score:
            paper_id = paper['id']
            pdf_path = os.path.join(pdf_dir, f'{paper_id}.pdf')

            if not os.path.exists(pdf_path):
                pdf_url = f'https://arxiv.org/pdf/{paper_id}.pdf'
                try:
                    logger.debug(f"Downloading PDF: {paper_id}...")
                    req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as response:
                        with open(pdf_path, 'wb') as f:
                            f.write(response.read())
                    downloaded.append(paper_id)
                except Exception as e:
                    logger.warning(f"Failed to download {paper_id}: {e}")

    if downloaded:
        logger.info(f"Downloaded {len(downloaded)} PDFs to {pdf_dir}")
    return downloaded


# ---------------------------------------------------------------------------
# Original functions below
# ---------------------------------------------------------------------------


def normalize_queue_status(status) -> str:
    value = str(status or "").strip()
    if value.lower() in {"", "none", "null"}:
        return ""
    return value


def status_class(status) -> str:
    status = normalize_queue_status(status)
    if not status:
        return ""
    return "status-" + status.lower().replace(" ", "-")


def format_author_text(authors, *, limit: int = 3) -> str:
    if isinstance(authors, list):
        author_text = ", ".join(authors[:limit])
        if len(authors) > limit:
            author_text += f" et al. ({len(authors)} authors)"
        return author_text
    return authors or ""


def extract_primary_author(authors) -> str:
    if isinstance(authors, list) and authors:
        return authors[0]
    if isinstance(authors, str) and authors.strip():
        return authors.split(",")[0].strip()
    return ""


def generate_relevance_html(paper: dict) -> str:
    """Generate HTML for structured relevance reasons with icons.

    If the paper carries a ``recommendation_reason`` dict (from the
    PRD_V2 spec), it is rendered as a natural-language block.  Otherwise
    the function falls back to the legacy ``relevance_breakdown`` list.
    """
    reason = paper.get("recommendation_reason")
    if isinstance(reason, dict) and reason:
        return _render_structured_reason_html(reason)

    # Legacy path: relevance_breakdown list
    breakdown = paper.get("relevance_breakdown", [])
    if not breakdown:
        text = html.escape(str(paper.get("relevance") or paper.get("relevance_reason") or "匹配您的研究兴趣"))
        return f'<div class="paper-relevance-text">{text}</div>'

    html_items = []
    for reason_item in breakdown[:4]:
        if isinstance(reason_item, str):
            if reason_item.startswith("[Core]"):
                icon = "🎯"
                text = f"命中核心主题: {html.escape(reason_item.replace('[Core]', '').strip())}"
            elif reason_item.startswith("[Secondary]"):
                icon = "📌"
                text = f"相关主题: {html.escape(reason_item.replace('[Secondary]', '').strip())}"
            else:
                icon = "📌"
                text = html.escape(reason_item)
            location_badge = ""
            score_badge = ""
        else:
            icon = reason_item.get("icon", "📌")
            text = html.escape(reason_item.get("text", ""))
            location = html.escape(reason_item.get("location", ""))
            score_impact = reason_item.get("score_impact", 0)
            location_badge = f'<span class="relevance-location">{location}</span>' if location else ""
            score_badge = f'<span class="relevance-score-impact">+{score_impact:.1f}</span>' if score_impact > 0 else ""

        html_items.append(
            f'<div class="relevance-item">'
            f'<span class="relevance-icon">{icon}</span>'
            f'<span class="relevance-text">{text}</span>'
            f"{location_badge}"
            f"{score_badge}"
            f"</div>"
        )

    return f'<div class="paper-relevance-items">{"".join(html_items)}</div>'


def _render_structured_reason_html(reason: dict) -> str:
    """Render a PRD_V2 ``recommendation_reason`` dict as natural-language HTML."""
    rows: list[str] = []

    # 1. Matched core/secondary topics
    matched_topics: list[str] = reason.get("matched_topics", []) or []
    if matched_topics:
        topic_text = ", ".join(matched_topics)
        rows.append(
            '<div class="relevance-item">'
            '<span class="relevance-icon">🎯</span>'
            f'<span class="relevance-text">命中核心研究主题: {html.escape(topic_text)}</span>'
            "</div>"
        )

    # 2. Matched subscriptions (saved searches)
    matched_subscriptions: list[str] = reason.get("matched_subscriptions", []) or []
    if matched_subscriptions:
        sub_text = ", ".join(matched_subscriptions)
        rows.append(
            '<div class="relevance-item">'
            '<span class="relevance-icon">🔔</span>'
            f'<span class="relevance-text">来自研究问题订阅: {html.escape(sub_text)}</span>'
            "</div>"
        )

    # 3. Zotero similarity
    zotero_sim = reason.get("zotero_similarity", 0)
    if isinstance(zotero_sim, (int, float)) and zotero_sim > 0:
        pct = int(zotero_sim * 100)
        rows.append(
            '<div class="relevance-item">'
            '<span class="relevance-icon">🧠</span>'
            f'<span class="relevance-text">与 Zotero 文献库中论文语义相似度: {pct}%</span>'
            "</div>"
        )

    # 4. Feedback signals
    feedback_signals: list[str] = reason.get("feedback_signals", []) or []
    if feedback_signals:
        for signal in feedback_signals:
            rows.append(
                '<div class="relevance-item">'
                '<span class="relevance-icon">📋</span>'
                f'<span class="relevance-text">{html.escape(signal)}</span>'
                "</div>"
            )

    # 5. Source tags
    source_tags: list[str] = reason.get("source_tags", []) or []
    meaningful = [t for t in source_tags if t not in ("arxiv_search", "unknown")]
    if meaningful:
        source_text = ", ".join(meaningful)
        rows.append(
            '<div class="relevance-item">'
            '<span class="relevance-icon">🏷️</span>'
            f'<span class="relevance-text">来源: {html.escape(source_text)}</span>'
            "</div>"
        )

    # 6. Reason summary (always show as the lead line)
    summary = reason.get("reason_summary", "")
    if summary:
        rows.insert(
            0,
            '<div class="relevance-item relevance-summary">'
            '<span class="relevance-icon">💡</span>'
            f'<span class="relevance-text">{html.escape(summary)}</span>'
            "</div>",
        )

    if not rows:
        rows.append(
            '<div class="relevance-item">'
            '<span class="relevance-text">基于综合相关性得分推荐</span>'
            "</div>"
        )

    return f'<div class="paper-relevance-items">{"".join(rows)}</div>'


def category_labels(categories, *, max_items: int = 4) -> list[str]:
    return [CATEGORY_NAMES.get(c, c) for c in (categories or [])[:max_items]]


def split_query_terms(query_text: str) -> list[str]:
    query_text = str(query_text or "").strip()
    if not query_text:
        return []
    if "," in query_text or "，" in query_text:
        return [part.strip() for part in re.split(r"[,，]+", query_text) if part.strip()]
    return [query_text]


def normalize_reason_type(text: str) -> tuple[str, str]:
    lowered = text.lower()
    if "核心主题" in text or "core" in lowered:
        return "🎯", "标题/摘要命中"
    if "相关主题" in text or "secondary" in lowered:
        return "📌", ""
    if "理论" in text or "theorem" in lowered or "proof" in lowered or "bound" in lowered:
        return "📐", ""
    if "zotero" in lowered or "语义" in text:
        return "🧠", ""
    if "作者" in text or "institution" in lowered or "google research" in lowered:
        return "🏛️", ""
    if "近" in text or "新论文" in text or "recency" in lowered:
        return "🆕", ""
    return "📌", ""


def breakdown_from_text(text: str) -> list[dict]:
    if not text:
        return []
    reasons = []
    for raw in [part.strip() for part in re.split(r"[;；]\s*", text) if part.strip()]:
        icon, location = normalize_reason_type(raw)
        reasons.append(
            {
                "type": "derived",
                "icon": icon,
                "text": raw,
                "location": location,
                "score_impact": 0,
            }
        )
    return reasons[:4]


__all__ = [
    "parse_arxiv_identity",
    "download_pdfs",
    "normalize_queue_status",
    "status_class",
    "format_author_text",
    "extract_primary_author",
    "generate_relevance_html",
    "category_labels",
    "split_query_terms",
    "normalize_reason_type",
    "breakdown_from_text",
]
