"""Daily recommendation pipeline — fetch, score, generate, and persist."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.arxiv_source import MultiSourceFetcher, PaperCache
from app.services.digest_writer import MarkdownGenerator, generate_summary
from app.services.html_digest_service import HTMLGenerator
from app.services.paper_utils import download_pdfs
from app.services.scoring_service import EnhancedScorer
from app.services.settings_service import get_priority_topics
from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from logger_config import get_logger
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


def load_daily_recommendation(cache_dir: str) -> tuple[list[dict] | None, str | None]:
    """Load today's cached recommendation if exists."""
    cache_file = os.path.join(cache_dir, 'daily_recommendation.json')
    today = datetime.now().strftime('%Y-%m-%d')

    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding='utf-8') as f:
                data = json.load(f)
                if data.get('date') == today:
                    return data.get('papers', []), data.get('themes', [])
        except Exception:
            pass
    return None, None


def save_daily_recommendation(cache_dir: str, papers: list[dict], themes: list[str]):
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


def save_recommendation_run(cache_dir: str, date_str: str, papers: list[dict], themes: list[str]):
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


def _run_scoring(
    papers: list[dict],
    semantic: Any | None,
    topic_weights: dict,
    use_semantic: bool,
) -> list[dict]:
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
    top_papers: list[dict],
    themes: list[str],
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
        store.save_recommendation_run(date_str, "auto_homepage", top_papers, themes)
        logger.info(f"Recommendation saved to SQLite for {date_str}")
    except Exception as e:
        logger.warning(f"Failed to save recommendation to SQLite: {e}")


def run_pipeline_v2(force_refresh: bool = False) -> list[dict]:
    """
    New v2 pipeline: recall -> rank -> top-K -> persist.
    Feature flag: STATDESK_RANKER=v2 (default v1).
    """
    cache_dir = str(CACHE_DIR)
    output_dir = str(PROJECT_ROOT)
    history_dir = str(HISTORY_DIR)

    logger.info("=" * 60)
    logger.info("StatDesk Daily Pipeline v2 (recall -> rank -> top-K)")
    logger.info("=" * 60)

    # Initialize cache
    cache = PaperCache(cache_dir)

    # Check if today's recommendation already exists (pipeline-level cache)
    today = datetime.now().strftime('%Y-%m-%d')
    if not force_refresh:
        store = get_state_store()
        today_run = store.get_recommendation_run_by_date(today)
        if today_run:
            items = store.get_recommendation_items(today_run["run_id"])
            if items:
                logger.info("Found today's recommendation in SQLite (%s)", today)
                os.makedirs(output_dir, exist_ok=True)
                os.makedirs(history_dir, exist_ok=True)
                html_gen = HTMLGenerator()
                html = html_gen.generate(items, [], today, cache.get_stats())
                with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info("HTML updated: %s/index.html", output_dir)
                logger.info("Done! Open http://localhost:5555 for interactive view")
                return items

        cached_papers, cached_themes = load_daily_recommendation(cache_dir)
        if cached_papers:
            logger.info("Today's recommendation exists in JSON cache, backfilling SQLite (%s)", today)
            store.save_recommendation_run(today, "auto_homepage", cached_papers, cached_themes or [])
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(history_dir, exist_ok=True)
            html_gen = HTMLGenerator()
            html = html_gen.generate(cached_papers, cached_themes or [], today, cache.get_stats())
            with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info("HTML updated: %s/index.html", output_dir)
            logger.info("Done! Open http://localhost:5555 for interactive view")
            return cached_papers

    cache.cleanup_old_entries(_CONFIG['cache_expiry_days'])
    logger.info("Cache: %s", cache.get_stats())

    pipeline_start = time.time()

    # 1. RECALL: fetch candidates via recall module (single fetch, dedup + seen-skip)
    from app.services.recall import recall_candidates

    papers = recall_candidates(
        _CONFIG['arxiv_categories'],
        lookback_days=_CONFIG['lookback_days'],
        max_results=500,
    )

    if not papers:
        logger.warning("No papers found!")
        return []

    # 2. RANK: score each paper using the ranker (keyword + author signals)
    from app.services.ranker import score_paper

    try:
        from config_manager import get_config
        cfg = get_config()
        keywords = list(cfg.core_keywords.keys())
        papers_per_day = cfg._settings.papers_per_day or _CONFIG['papers_per_day']
    except Exception:
        keywords = list(get_priority_topics())
        papers_per_day = _CONFIG['papers_per_day']

    ctx: dict = {"keywords": keywords}

    # Enrich context with library embeddings, feedback model, and subscriptions
    try:
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService()
        emb_rows = get_state_store().get_all_embeddings_for_model(svc.model_name)
        if emb_rows:
            import numpy as np

            ctx["library_embeddings"] = [
                np.frombuffer(blob, dtype=np.float32).tolist()
                for _, blob, _ in emb_rows
            ]
    except Exception:
        logger.warning("Could not load library embeddings for context")

    try:
        fb_data = get_state_store().get_latest_feedback_model()
        if fb_data and fb_data.get("pickle_blob"):
            import pickle

            ctx["feedback_model"] = pickle.loads(fb_data["pickle_blob"])  # nosec B301
            ctx["feedback_model_auc"] = fb_data["auc"]
    except Exception:
        logger.warning("Could not load feedback model for context")

    try:
        ctx["subscriptions"] = get_state_store().list_subscriptions()
    except Exception:
        logger.warning("Could not load subscriptions for context")

    for paper in papers:
        score, explanation = score_paper(paper, ctx)
        paper["score"] = score
        paper["relevance_reason"] = explanation
        paper["summary"] = generate_summary(paper.get("abstract", ""))

    # 3. TOP-K: sort by score descending, take top papers_per_day
    papers.sort(key=lambda x: -x["score"])
    top_papers = papers[:papers_per_day]

    # 4. PERSIST: reuse existing output generation (HTML, Markdown, SQLite)
    date_str = datetime.now().strftime('%Y-%m-%d')
    _generate_outputs(top_papers, [], date_str, cache, output_dir, history_dir, cache_dir)

    _print_summary(top_papers, time.time() - pipeline_start)

    return top_papers


def _print_summary(top_papers: list[dict], duration: float) -> None:
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


def run_pipeline(force_refresh: bool = False) -> list[dict]:
    """Run the complete enhanced pipeline."""
    cache_dir = str(CACHE_DIR)
    output_dir = str(PROJECT_ROOT)
    history_dir = str(HISTORY_DIR)

    logger.info("=" * 60)
    logger.info("arXiv Daily Paper Recommender v2.2")
    logger.info("=" * 60)

    # Initialize cache
    cache = PaperCache(cache_dir)

    # Check if today's recommendation already exists (SQLite first, then JSON)
    today = datetime.now().strftime('%Y-%m-%d')
    if not force_refresh:
        store = get_state_store()
        today_run = store.get_recommendation_run_by_date(today)
        if today_run:
            items = store.get_recommendation_items(today_run["run_id"])
            if items:
                logger.info(f"Found today's recommendation in SQLite ({today})")
                os.makedirs(output_dir, exist_ok=True)
                os.makedirs(history_dir, exist_ok=True)
                html_gen = HTMLGenerator()
                html = html_gen.generate(items, [], today, cache.get_stats())
                with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info(f"HTML updated: {output_dir}/index.html")
                logger.info("Done! Open http://localhost:5555 for interactive view")
                return items

        cached_papers, cached_themes = load_daily_recommendation(cache_dir)
        if cached_papers:
            logger.info(f"Today's recommendation exists in JSON cache, backfilling SQLite ({today})")
            store.save_recommendation_run(today, "auto_homepage", cached_papers, cached_themes)
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

    # Fetch papers from multiple sources
    t0 = time.time()
    fetcher = MultiSourceFetcher(_CONFIG['arxiv_categories'], cache)
    papers = fetcher.fetch_all_sources(_CONFIG['lookback_days'], force_refresh=force_refresh)
    logger.info(f"Fetched {len(papers)} papers from arXiv ({time.time()-t0:.1f}s)")

    if not papers:
        logger.warning("No new papers found!")
        return []

    # Score papers (keyword-only mode, no semantic/Zotero)
    themes: list[str] = []
    top_papers = _run_scoring(papers, semantic=None, topic_weights={}, use_semantic=False)

    # Generate and persist outputs
    date_str = datetime.now().strftime('%Y-%m-%d')
    _generate_outputs(top_papers, themes, date_str, cache, output_dir, history_dir, cache_dir)

    _print_summary(top_papers, time.time() - pipeline_start)

    return top_papers


__all__ = [
    "run_pipeline",
    "run_pipeline_v2",
    "load_daily_recommendation",
    "save_daily_recommendation",
    "save_recommendation_run",
]
