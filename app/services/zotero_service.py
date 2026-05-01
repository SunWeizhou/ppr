"""Zotero path detection and model selection helpers."""

from __future__ import annotations

import glob as glob_module
import os
import platform
from typing import Tuple

from logger_config import get_logger

from app.services.settings_service import load_user_config

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


def _detect_nvidia_gpu() -> Tuple[bool, int]:
    """Detect NVIDIA GPU and VRAM."""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            vram_mb = int(result.stdout.strip().split('\n')[0])
            return True, vram_mb // 1024
    except Exception:
        pass
    return False, 0


def _get_ram_gb() -> int:
    """Get system RAM in GB."""
    try:
        import psutil
        return psutil.virtual_memory().total // (1024**3)
    except ImportError:
        # Fallback for Windows without psutil
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'computersystem', 'get', 'totalphysicalmemory'],
                capture_output=True, text=True
            )
            ram_bytes = int(result.stdout.split('\n')[1].strip())
            return ram_bytes // (1024**3)
        except Exception:
            return 8  # Default assumption


def get_best_embedding_model() -> str:
    """Auto-detect best embedding model based on hardware."""
    # Check user config first
    config = load_user_config()
    user_model = config.get('settings', {}).get('embedding_model', '')
    if user_model:
        return user_model

    # Auto-detect based on hardware
    has_gpu, vram = _detect_nvidia_gpu()
    ram_gb = _get_ram_gb()

    if has_gpu and vram >= 6:
        model = 'BAAI/bge-large-en-v1.5'
        reason = f'GPU detected ({vram}GB VRAM)'
    elif ram_gb >= 16:
        model = 'sentence-transformers/all-mpnet-base-v2'
        reason = f'High RAM ({ram_gb}GB)'
    else:
        model = 'sentence-transformers/all-MiniLM-L6-v2'
        reason = f'Standard config ({ram_gb}GB RAM)'

    logger.info("Auto-selected model: %s (%s)", model, reason)
    return model


__all__ = ["get_zotero_path", "get_best_embedding_model"]
