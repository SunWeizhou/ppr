"""Zotero path detection and model selection helpers."""

from __future__ import annotations

import glob as glob_module
import os
import platform

from logger_config import get_logger

from app.services.settings_service import load_user_config
from app.services.semantic_similarity import get_best_embedding_model

logger = get_logger(__name__)


def get_zotero_path() -> str:
    """Get Zotero database path with auto-detection."""
    # 1. Check user config
    config = load_user_config()
    if config.get('zotero', {}).get('database_path'):
        path = os.path.expanduser(config['zotero']['database_path'])
        if os.path.exists(path):
            return path

    # 2. Auto-detect based on OS
    system = platform.system()
    candidates = []

    if system == 'Windows':
        candidates = [
            'D:/zetero_data/zotero.sqlite',  # User's current path
            os.path.expanduser('~/Zotero/zotero.sqlite'),
            os.path.expanduser('~/AppData/Roaming/Zotero/Zotero/Profiles/*/zotero.sqlite'),
        ]
        # Also check other drives
        for drive in ['E:', 'F:', 'C:']:
            candidates.extend([
                f'{drive}/zetero_data/zotero.sqlite',
                f'{drive}/Zotero/zotero.sqlite',
            ])
    elif system == 'Darwin':  # macOS
        candidates = [
            os.path.expanduser('~/Zotero/zotero.sqlite'),
            os.path.expanduser('~/Library/Application Support/Zotero/Profiles/*/zotero.sqlite'),
        ]
    else:  # Linux
        candidates = [
            os.path.expanduser('~/Zotero/zotero.sqlite'),
            os.path.expanduser('~/.zotero/zotero.sqlite'),
        ]

    for path in candidates:
        expanded = os.path.expanduser(path)
        if '*' in expanded:
            matches = glob_module.glob(expanded)
            if matches:
                return matches[0]
        elif os.path.exists(expanded):
            return expanded

    # 3. Fallback to default
    return 'D:/zetero_data/zotero.sqlite'


__all__ = ["get_zotero_path", "get_best_embedding_model"]
