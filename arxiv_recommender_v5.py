"""arXiv Daily Paper Recommender System v2.0 - re-export hub with feature-flag routing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict

from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from app.services.daily_pipeline import (
    load_daily_recommendation as load_daily_recommendation,
    save_daily_recommendation as save_daily_recommendation,
    save_recommendation_run as save_recommendation_run,
)
from app.services.digest_writer import (
    MarkdownGenerator as MarkdownGenerator,
    generate_summary as generate_summary,
)
from app.services.feedback_learning_service import (
    FeedbackLearner as FeedbackLearner,
    learn_from_feedback as learn_from_feedback,
)
from app.services.feedback_service import load_user_feedback as load_user_feedback
from app.services.html_digest_service import (
    HTMLGenerator as HTMLGenerator,
    generate_search_html as generate_search_html,
)
from app.services.paper_utils import parse_arxiv_identity as parse_arxiv_identity
from app.services.semantic_similarity import (
    SemanticSimilarity as SemanticSimilarity,
    get_best_embedding_model as get_best_embedding_model,
)
from app.services.settings_service import (
    get_priority_topics as get_priority_topics,
    load_keywords_config as load_keywords_config,
    load_user_config as load_user_config,
    save_keywords_config as save_keywords_config,
    save_user_config as save_user_config,
)
from app.services.scoring_service import EnhancedScorer as EnhancedScorer
from app.services.citation_service import CitationAnalyzer as CitationAnalyzer
from app.services.arxiv_source import (
    MultiSourceFetcher as MultiSourceFetcher,
    PaperCache as PaperCache,
    search_by_keywords as search_by_keywords,
    TOP_INSTITUTIONS as TOP_INSTITUTIONS,
    KNOWN_AUTHORS as KNOWN_AUTHORS,
)
from app.services.zotero_service import get_zotero_path as get_zotero_path

# Backward-compatible CONFIG for existing imports (e.g. routes/api.py)
CONFIG = {
    "cache_dir": str(CACHE_DIR),
    "output_dir": str(PROJECT_ROOT),
    "history_dir": str(HISTORY_DIR),
    "papers_per_day": 20,
    "arxiv_categories": ["cs.LG", "stat.ML", "cs.AI", "cs.CL", "math.ST", "stat.TH", "stat.ME"],
    "lookback_days": 1,
    "use_semantic_similarity": True,
    "embedding_model": "",
    "cache_expiry_days": 30,
}


def run_pipeline(force_refresh: bool = False) -> List[Dict]:
    """Run the daily recommendation pipeline.

    Feature flag: when ``STATDESK_RANKER=v2`` is set in the environment,
    delegates to the new recall->rank->top-K pipeline (``run_pipeline_v2``).
    Otherwise, uses the existing v1 pipeline (``run_pipeline`` from
    :mod:`app.services.daily_pipeline`).

    All existing callers (inbox, keywords, feedback) import this function,
    so a single env-var check in this module activates v2 everywhere.
    """
    if os.environ.get("STATDESK_RANKER") == "v2":
        from app.services.daily_pipeline import run_pipeline_v2

        return run_pipeline_v2(force_refresh)
    from app.services.daily_pipeline import run_pipeline as _run_pipeline_v1

    return _run_pipeline_v1(force_refresh)
