"""Paper ranking signals: keyword, author, semantic, feedback, subscription."""

from math import exp

import numpy as np

from app.services.arxiv_source import KNOWN_AUTHORS, TOP_INSTITUTIONS
from app.services.blend import blend
from logger_config import get_logger

logger = get_logger(__name__)

_TOP_VENUE_KEYWORDS = [
    'neurips', 'nips', 'icml', 'iclr', 'colt', 'jmlr', 'aistats',
]


def keyword_score(paper: dict, keywords: list[str]) -> float:
    """0~1. Title hits x3 weight, abstract hits x1. Normalize via 1-exp(-raw/4)."""
    title_lower = paper.get('title', '').lower()
    abstract_lower = paper.get('abstract', '').lower()
    hits_title = 0
    hits_abs = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            hits_title += 1
        elif kw_lower in abstract_lower:
            # Conservative: each keyword counted once, title takes priority (×3 vs ×1).
            hits_abs += 1
    raw = hits_title * 3 + hits_abs
    return 1.0 - exp(-raw / 4.0)


def author_score(paper: dict) -> float:
    """0~1. Known scholar +0.4, top institution +0.3, top venue +0.3, subscribed author +0.5, cap 1.0."""
    score = 0.0
    authors_text = ' '.join(paper.get('authors', [])).lower()
    all_text = ' '.join([
        paper.get('title', ''),
        paper.get('abstract', ''),
        paper.get('comment', '') or '',
    ]).lower()

    for author in KNOWN_AUTHORS:
        if author.lower() in authors_text:
            score += 0.4
            break

    for inst in TOP_INSTITUTIONS:
        if inst.lower() in all_text:
            score += 0.3
            break

    for venue in _TOP_VENUE_KEYWORDS:
        if venue in all_text:
            score += 0.3
            break

    try:
        from state_store import get_state_store
        for sub in get_state_store().list_subscriptions(type='author'):
            author_name = (sub.get('query_text') or '').lower()
            if author_name and author_name in authors_text:
                score += 0.5
                break
    except Exception:
        logger.warning("author_score: state_store unavailable")

    return min(score, 1.0)


def semantic_score(paper: dict, library_embeddings: list[list[float]] | None) -> float:
    """0~1. Cosine similarity between paper embedding and library embeddings.

    Computes the embedding for the paper's title+abstract, then finds the
    top-3 most similar library embeddings by cosine similarity and returns
    their mean. Returns 0.0 if no embeddings are available.
    """
    if not library_embeddings:
        return 0.0
    from app.services.embedding_service import EmbeddingService

    svc = EmbeddingService()
    paper_emb = svc.embed_paper(paper)
    if not paper_emb:
        return 0.0
    paper_vec = np.array(paper_emb, dtype=np.float32)
    lib_vecs = np.array(library_embeddings, dtype=np.float32)
    norm_product = np.linalg.norm(lib_vecs, axis=1) * np.linalg.norm(paper_vec)
    if not np.any(norm_product > 0):
        return 0.0
    sims = np.dot(lib_vecs, paper_vec) / np.where(norm_product > 0, norm_product, 1.0)
    top3 = sorted(sims, reverse=True)[:3]
    return float(np.mean(top3))


def feedback_score(paper: dict, fb_model) -> float:
    """0~1. Probability from the logistic regression feedback model.

    Uses the paper's embedding to obtain a ``predict_proba`` score for the
    positive (relevant) class.  Returns 0.0 if the model is None or if the
    paper cannot be embedded.
    """
    if fb_model is None:
        return 0.0
    from app.services.embedding_service import EmbeddingService

    svc = EmbeddingService()
    paper_emb = svc.embed_paper(paper)
    if not paper_emb:
        return 0.0
    X = np.array([paper_emb], dtype=np.float32)
    proba = fb_model.predict_proba(X)[0][1]
    return float(proba)


def subscription_score(paper: dict, subscriptions: list[dict] | None) -> float:
    """0~1. Each subscription text hit in title/abstract +0.3, cap 1.0."""
    if not subscriptions:
        return 0.0
    title_abs = ' '.join([
        paper.get('title', ''),
        paper.get('abstract', ''),
    ]).lower()
    score = 0.0
    for sub in subscriptions:
        query = (sub.get('query_text') or '').lower()
        if query and query in title_abs:
            score += 0.3
    return min(score, 1.0)


def matched_keywords(paper: dict, keywords: list[str]) -> list[str]:
    """Return keywords that appear in paper title or abstract (case-insensitive)."""
    title_lower = paper.get('title', '').lower()
    abstract_lower = paper.get('abstract', '').lower()
    return [
        kw for kw in keywords
        if kw.lower() in title_lower or kw.lower() in abstract_lower
    ]


def score_paper(paper: dict, ctx: dict) -> tuple[float, str]:
    """Return (match_score in [0,1], one-sentence explanation)."""
    signals: list[tuple[str, float]] = []

    kw = keyword_score(paper, ctx.get('keywords', []))
    if kw > 0:
        signals.append(('keyword', kw))

    au = author_score(paper)
    if au > 0:
        signals.append(('author', au))

    embeddings = ctx.get('library_embeddings')
    if embeddings is not None:
        sem = semantic_score(paper, embeddings)
        if sem > 0:
            signals.append(('library', sem))

    fb_model = ctx.get('feedback_model')
    fb_auc = ctx.get('feedback_model_auc')
    if fb_model is not None and fb_auc is not None and fb_auc >= 0.55:
        fb = feedback_score(paper, fb_model)
        if fb > 0:
            signals.append(('feedback', fb))

    subs = ctx.get('subscriptions')
    if subs:
        ss = subscription_score(paper, subs)
        if ss > 0:
            signals.append(('subscription', ss))

    return blend(signals), explain(signals, paper, ctx)


def explain(signals: list[tuple[str, float]], paper: dict, ctx: dict) -> str:
    """Generate <=35 char Chinese explanation based on strongest signal."""
    if not signals:
        return '基于你的研究领域'
    name = max(signals, key=lambda s: s[1])[0]
    if name == 'keyword':
        matched = matched_keywords(paper, ctx.get('keywords', []))
        kw = matched[0] if matched else ''
        return f'命中关键词：{kw}'
    if name == 'library':
        return '与你论文库中的论文高度相似'
    if name == 'feedback':
        return '与你标记相关的论文风格相近'
    if name == 'author':
        return '来自你关注的作者或团队'
    if name == 'subscription':
        return '命中订阅查询'
    return '基于你的研究领域'
