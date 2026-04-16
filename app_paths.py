"""Shared project paths for runtime and persistence."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / "cache"
HISTORY_DIR = PROJECT_ROOT / "history"
STATE_DB_PATH = CACHE_DIR / "app_state.db"
USER_PROFILE_PATH = PROJECT_ROOT / "user_profile.json"
LEGACY_USER_CONFIG_PATH = PROJECT_ROOT / "user_config.json"


def ensure_runtime_dirs() -> None:
    """Create runtime directories used by the app."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
