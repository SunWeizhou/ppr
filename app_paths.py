"""Shared project paths and runtime constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / "cache"
HISTORY_DIR = PROJECT_ROOT / "history"
STATE_DB_PATH = CACHE_DIR / "app_state.db"
USER_PROFILE_PATH = PROJECT_ROOT / "user_profile.json"
LEGACY_USER_CONFIG_PATH = PROJECT_ROOT / "user_config.json"

SNAPSHOT_FILES = {
    "user_profile": PROJECT_ROOT / "user_profile.json",
    "user_config": PROJECT_ROOT / "user_config.json",
    "keywords_config": PROJECT_ROOT / "keywords_config.json",
    "user_feedback": CACHE_DIR / "user_feedback.json",
    "favorite_papers": CACHE_DIR / "favorite_papers.json",
    "paper_cache": CACHE_DIR / "paper_cache.json",
    "journal_update_log": CACHE_DIR / "journal_update_log.json",
}


def ensure_runtime_dirs() -> None:
    """Create runtime directories used by the app."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
