"""Daily recommendation pipeline — fetch, score, generate, and persist."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from logger_config import get_logger

from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from app.services.arxiv_source import MultiSourceFetcher, PaperCache
from app.services.digest_writer import MarkdownGenerator, generate_summary
from app.services.feedback_service import load_user_feedback
from app.services.feedback_learning_service import learn_from_feedback
from app.services.html_digest_service import HTMLGenerator
from app.services.paper_utils import download_pdfs
from app.services.scoring_service import EnhancedScorer
from app.services.semantic_similarity import SemanticSimilarity
from app.services.settings_service import get_priority_topics, load_user_config
from app.services.zotero_service import get_zotero_path
from state_store import get_state_store

logger = get_logger(__name__)

# Default configuration values (replaced from CONFIG dict)
_CONFIG = {
    'arxiv_categories': ['cs.LG', 'stat.ML', 'cs.AI', 'cs.CL', 'math.ST', 'stat.TH', 'stat.ME'],
    'lookback_days': 1,
    'papers_per_day': 20,
    'use_semantic_similarity': True,
    'embedding_model': '',
    'cache_expiry_days': 30,
}


# ---------------------------------------------------------------------------
# Daily recommendation cache helpers
# ---------------------------------------------------------------------------


def load_daily_recommendation(cache_dir: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """Load today's cached recommendation if exists."""
    cache_file = os.path.join(cache_dir, 'daily_recommendation.json')
    today = datetime.now().strftime('%Y-%m-%d')

    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('date') == today:
                    return data.get('papers', []), data.get('themes', [])
        except Exception:
            pass
    return None, None


def save_daily_recommendation(cache_dir: str, papers: List[Dict], themes: List[str]):
    """Save today's recommendation to cache."""
    cache_file = os.path.join(cache_dir, 'daily_recommendation.json')
    today = datetime.now().strftime('%Y-%m-%d')

    serializable_papers = []
    for p in papers:
        paper_copy = {k: v for k, v in p.items() if k != 'score_details' or isinstance(v, dict)}
        if 'score_details' in p:
            paper_copy['score_details'] = p['score_details']
        serializable_papers.append(paper_copy)

    data = {
        'date': today,
        'papers': serializable_papers,
        'themes': themes,
        'generated_at': datetime.now().isoformat()
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def save_recommendation_run(cache_dir: str, date_str: str, papers: List[Dict], themes: List[str]):
    """Persist a dated recommendation snapshot for history playback."""
    run_dir = os.path.join(cache_dir, 'recommendation_runs')
    os.makedirs(run_dir, exist_ok=True)
    run_path = os.path.join(run_dir, f'{date_str}.json')

    serializable_papers = []
    for paper in papers:
        paper_copy = dict(paper)
        if 'score_details' in paper_copy and not isinstance(paper_copy['score_details'], dict):
            paper_copy.pop('score_details', None)
        serializable_papers.append(paper_copy)

    with open(run_path, 'w', encoding='utf-8') as f:
        json.dump(
            {
                'date': date_str,
                'papers': serializable_papers,
                'themes': themes,
                'generated_at': datetime.now().isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


# ---------------------------------------------------------------------------
# Pipeline helper functions
# ---------------------------------------------------------------------------


def _load_zotero_papers() -> Tuple[List[Dict], List[str], bool]:
    """Load Zotero papers from the Zotero database and extract research themes.

    Returns:
        A tuple of (zotero_papers, themes, use_semantic_flag) where
        use_semantic_flag is True if Zotero papers were successfully loaded.
    """
    t0 = time.time()
    zotero_path = get_zotero_path()
    zotero_papers: List[Dict] = []

    user_cfg = load_user_config()
    use_zotero = user_cfg.get('zotero', {}).get('enabled', True)

    if use_zotero and os.path.exists(zotero_path):
        try:
            conn = sqlite3.connect(zotero_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.itemID, it.typeName,
                       MAX(CASE WHEN id.fieldID = 1 THEN idv.value END) as title,
                       MAX(CASE WHEN id.fieldID = 2 THEN idv.value END) as abstract
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                JOIN itemData id ON i.itemID = id.itemID
                JOIN itemDataValues idv ON id.valueID = idv.valueID
                WHERE i.itemTypeID IN (11, 22, 31)
                GROUP BY i.itemID HAVING title IS NOT NULL
            ''')
            zotero_papers = [{'id': r[0], 'title': r[2], 'abstract': r[3] or ''} for r in cursor.fetchall()]
            conn.close()
            logger.info(f"Loaded {len(zotero_papers)} papers from Zotero ({time.time()-t0:.1f}s)")
        except Exception as e:
            logger.error(f"Zotero load error: {e}")
    elif not use_zotero:
        logger.info("Zotero disabled in config - running in keyword-only mode")
    else:
        logger.info(f"Zotero not found at {zotero_path}")
        logger.info("  Running in keyword-only mode")
        logger.info("  Tip: Set zotero.database_path in user_profile.json")

    # Extract themes
    t0 = time.time()
    themes: List[str] = []
    if zotero_papers:
        all_text = ' '.join([p['title'] + ' ' + p['abstract'] for p in zotero_papers]).lower()
        theme_scores: Dict[str, int] = {}
        for topic in get_priority_topics():
            count = len(re.findall(r'\b' + re.escape(topic.lower()) + r'\b', all_text))
            if count > 0:
                theme_scores[topic] = count
        themes = [t[0] for t in sorted(theme_scores.items(), key=lambda x: -x[1])[:10]]
        logger.debug(f"Research themes: {themes} ({time.time()-t0:.1f}s)")

    return zotero_papers, themes, bool(zotero_papers)


def _run_scoring(
    papers: List[Dict],
    semantic: Optional[SemanticSimilarity],
    topic_weights: Dict,
    use_semantic: bool,
) -> List[Dict]:
    """Score all papers using the EnhancedScorer and return top papers.

    Args:
        papers: List of paper dicts to score.
        semantic: Semantic similarity instance (may be None).
        topic_weights: Learned topic weights from feedback.
        use_semantic: Whether to use semantic similarity scoring.

    Returns:
        Sorted list of top scored papers.
    """
    t0 = time.time()
    scorer = EnhancedScorer(semantic, use_semantic, topic_weights)
    for paper in papers:
        score, details = scorer.compute_score(paper)
        paper['score'] = score
        paper['score_details'] = details
        paper['summary'] = generate_summary(paper.get('abstract', ''))

        breakdown = details.get('breakdown', [])
        if breakdown:
            paper['relevance_reason'] = '; '.join([r['text'] for r in breakdown])
            paper['relevance_breakdown'] = breakdown
        else:
            paper['relevance_reason'] = 'Matches your research interests'
            paper['relevance_breakdown'] = []
    logger.info(f"Scored {len(papers)} papers ({time.time()-t0:.1f}s)")

    # Sort and select top papers
    papers.sort(key=lambda x: -x['score'])
    top_papers = papers[:_CONFIG['papers_per_day']]

    logger.debug(f"Top scores: {[round(p['score'], 1) for p in top_papers[:5]]}")

    return top_papers


def _generate_outputs(
    top_papers: List[Dict],
    themes: List[str],
    date_str: str,
    cache: PaperCache,
    output_dir: str,
    history_dir: str,
    cache_dir: str,
) -> None:
    """Generate and persist all recommendation outputs including PDFs, HTML, Markdown, and SQLite.

    Args:
        top_papers: List of top scored papers.
        themes: Extracted research themes.
        date_str: Current date string (YYYY-MM-DD).
        cache: PaperCache instance.
        output_dir: Output directory for generated files.
        history_dir: History directory for past digests.
        cache_dir: Cache directory for recommendation data.
    """
    # Download PDFs for high-scoring papers
    logger.info("Downloading PDFs for top papers...")
    download_pdfs(top_papers, output_dir, min_score=2.5)

    # Record recommendations
    cache.record_recommendation(date_str, [p['id'] for p in top_papers])

    # Generate output
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(history_dir, exist_ok=True)

    html_gen = HTMLGenerator()
    html = html_gen.generate(top_papers, themes, date_str, cache.get_stats())

    md_gen = MarkdownGenerator()
    md = md_gen.generate(top_papers, themes, date_str)

    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"HTML saved to: {output_dir}/index.html")

    with open(os.path.join(output_dir, 'daily_arxiv_digest.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    logger.info(f"Markdown saved to: {output_dir}/daily_arxiv_digest.md")

    # Save history
    history_path = os.path.join(history_dir, f'digest_{date_str}.md')
    with open(history_path, 'w', encoding='utf-8') as f:
        f.write(md)
    logger.info(f"History saved to: {history_path}")

    # Save daily recommendation cache
    save_daily_recommendation(cache_dir, top_papers, themes)
    save_recommendation_run(cache_dir, date_str, top_papers, themes)
    logger.info(f"Daily recommendation cached for {date_str}")

    # Save to SQLite as primary state source
    try:
        store = get_state_store()
        store.save_recommendation_run(date_str, "auto_homepage", top_papers)
        logger.info(f"Recommendation saved to SQLite for {date_str}")
    except Exception as e:
        logger.warning(f"Failed to save recommendation to SQLite: {e}")


def _print_summary(top_papers: List[Dict], duration: float) -> None:
    """Print pipeline completion summary."""
    logger.info("=" * 60)
    logger.info("Today's Top Recommendations:")
    logger.info("=" * 60)
    for i, p in enumerate(top_papers[:5], 1):
        logger.info(f"{i}. {p['title'][:70]}...")
        logger.info(f"   Score: {p['score']:.1f} | {p['link']}")

    logger.info("=" * 60)
    logger.info(f"Pipeline complete! Total time: {duration:.1f}s")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(force_refresh: bool = False) -> List[Dict]:
    """Run the complete enhanced pipeline."""
    cache_dir = str(CACHE_DIR)
    output_dir = str(PROJECT_ROOT)
    history_dir = str(HISTORY_DIR)

    logger.info("=" * 60)
    logger.info("arXiv Daily Paper Recommender v2.2")
    logger.info("=" * 60)

    # Initialize cache
    cache = PaperCache(cache_dir)

    # Check if today's recommendation already exists
    today = datetime.now().strftime('%Y-%m-%d')
    if not force_refresh:
        cached_papers, cached_themes = load_daily_recommendation(cache_dir)
        if cached_papers:
            logger.info(f"Today's recommendation already exists ({today})")
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(history_dir, exist_ok=True)
            html_gen = HTMLGenerator()
            html = html_gen.generate(cached_papers, cached_themes or [], today, cache.get_stats())
            with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML updated: {output_dir}/index.html")
            logger.info("Done! Open http://localhost:5555 for interactive view")
            return cached_papers

    cache.cleanup_old_entries(_CONFIG['cache_expiry_days'])
    logger.info(f"Cache: {cache.get_stats()}")

    pipeline_start = time.time()

    # Load user feedback and learn from it
    feedback = load_user_feedback(cache_dir)

    # Load Zotero papers
    zotero_papers, themes, use_semantic = _load_zotero_papers()

    # Initialize semantic similarity
    t0 = time.time()
    semantic = SemanticSimilarity(_CONFIG['embedding_model'], cache_dir)
    if _CONFIG['use_semantic_similarity'] and zotero_papers:
        logger.info("Computing semantic embeddings...")
        semantic.compute_zotero_embedding(zotero_papers, get_zotero_path())
        logger.info(f"Semantic init done ({time.time()-t0:.1f}s)")
    elif not zotero_papers:
        logger.info("Running in keyword-only mode (no Zotero library found)")
        semantic = None

    # Fetch papers from multiple sources
    t0 = time.time()
    fetcher = MultiSourceFetcher(_CONFIG['arxiv_categories'], cache)
    papers = fetcher.fetch_all_sources(_CONFIG['lookback_days'])
    logger.info(f"Fetched {len(papers)} papers from arXiv ({time.time()-t0:.1f}s)")

    if not papers:
        logger.warning("No new papers found!")
        return []

    # Learn topic weights from feedback
    t0 = time.time()
    topic_weights = learn_from_feedback(feedback, papers)
    logger.debug(f"Learned weights from feedback ({time.time()-t0:.1f}s)")

    # Score papers
    use_semantic_flag = _CONFIG['use_semantic_similarity'] and semantic is not None
    top_papers = _run_scoring(papers, semantic, topic_weights, use_semantic_flag)

    # Generate and persist outputs
    date_str = datetime.now().strftime('%Y-%m-%d')
    _generate_outputs(top_papers, themes, date_str, cache, output_dir, history_dir, cache_dir)

    _print_summary(top_papers, time.time() - pipeline_start)

    return top_papers


__all__ = [
    "run_pipeline",
    "load_daily_recommendation",
    "save_daily_recommendation",
    "save_recommendation_run",
]
