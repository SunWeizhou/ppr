"""Shared paper formatting and status utilities.

These are pure functions with no side effects, extracted from web_server.py
and queue_service.py to eliminate duplication.
"""

from __future__ import annotations

import re

from utils import CATEGORY_NAMES


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
        text = paper.get("relevance") or paper.get("relevance_reason") or "匹配您的研究兴趣"
        return f'<div class="paper-relevance-text">{text}</div>'

    html_items = []
    for reason_item in breakdown[:4]:
        if isinstance(reason_item, str):
            if reason_item.startswith("[Core]"):
                icon = "🎯"
                text = f"命中核心主题: {reason_item.replace('[Core]', '').strip()}"
            elif reason_item.startswith("[Secondary]"):
                icon = "📌"
                text = f"相关主题: {reason_item.replace('[Secondary]', '').strip()}"
            else:
                icon = "📌"
                text = reason_item
            location_badge = ""
            score_badge = ""
        else:
            icon = reason_item.get("icon", "📌")
            text = reason_item.get("text", "")
            location = reason_item.get("location", "")
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
            f'<span class="relevance-text">命中核心研究主题: {topic_text}</span>'
            "</div>"
        )

    # 2. Matched subscriptions (saved searches)
    matched_subscriptions: list[str] = reason.get("matched_subscriptions", []) or []
    if matched_subscriptions:
        sub_text = ", ".join(matched_subscriptions)
        rows.append(
            '<div class="relevance-item">'
            '<span class="relevance-icon">🔔</span>'
            f'<span class="relevance-text">来自研究问题订阅: {sub_text}</span>'
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
                f'<span class="relevance-text">{signal}</span>'
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
            f'<span class="relevance-text">来源: {source_text}</span>'
            "</div>"
        )

    # 6. Reason summary (always show as the lead line)
    summary = reason.get("reason_summary", "")
    if summary:
        rows.insert(
            0,
            '<div class="relevance-item relevance-summary">'
            '<span class="relevance-icon">💡</span>'
            f'<span class="relevance-text">{summary}</span>'
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
