"""Compatibility facade for arXiv source and search functions."""

from arxiv_recommender_v5 import (
    MultiSourceFetcher,
    PaperCache,
    load_daily_recommendation,
    run_pipeline,
    search_by_keywords,
)

__all__ = [
    "MultiSourceFetcher",
    "PaperCache",
    "load_daily_recommendation",
    "run_pipeline",
    "search_by_keywords",
]

