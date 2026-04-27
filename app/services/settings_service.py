"""Settings service — user profile, keywords CRUD, and settings persistence."""

from __future__ import annotations

import json
import os
from typing import Dict, List

from logger_config import get_logger

from config_manager import get_config

logger = get_logger(__name__)

# Default priority topics (fallback if user config not found)
DEFAULT_PRIORITY_TOPICS: List[str] = [
    'statistical learning theory', 'in-context learning', 'transformer theory',
    'transformer', 'prompt learning', 'prompt engineering',
    'nonparametric estimation', 'conditional density estimation',
    'conformal prediction', 'generalization theory', 'excess risk analysis',
    'large language model theory', 'LLM theory', 'attention mechanism',
    'theoretical machine learning', 'statistical inference', 'predictive inference',
    'bayesian inference', 'regression', 'generalization bound',
    'neural network theory', 'overparameterization', 'double descent', 'minimax optimality',
]

_KEYWORDS_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keywords_config.json')


# ---------------------------------------------------------------------------
# Standalone config helpers (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


def load_user_config() -> Dict:
    """Load user configuration - 使用统一配置管理器."""
    config = get_config()
    return {
        'research_focus': {
            'topics': list(config.core_keywords.keys()),
            'weight': 3.0
        },
        'dislike_topics': {
            'topics': list(config.dislike_keywords.keys())
        },
        'settings': {
            'papers_per_day': config._settings.papers_per_day,
            'prefer_theory': config._settings.prefer_theory,
            'theory_enabled': config._settings.theory_enabled,
        },
        'zotero': {
            'database_path': config._zotero.database_path,
            'enabled': config._zotero.enabled,
        }
    }


def save_user_config(config: Dict) -> bool:
    """Save user configuration - 使用统一配置管理器."""
    try:
        cm = get_config()

        # 更新关键词
        if 'research_focus' in config and 'topics' in config['research_focus']:
            for topic in config['research_focus']['topics']:
                if topic not in cm.all_keywords:
                    cm.set_keyword(topic, 3.0, 'core')

        # 更新不感兴趣主题
        if 'dislike_topics' in config and 'topics' in config['dislike_topics']:
            for topic in config['dislike_topics']['topics']:
                cm.set_keyword(topic, -1.0, 'dislike')

        return True
    except Exception as e:
        logger.error(f"Error saving user config: {e}")
        return False


def get_priority_topics() -> List[str]:
    """Get priority topics from unified config."""
    return list(get_config().core_keywords.keys())


def get_dislike_topics() -> List[str]:
    """Get topics to deprioritize from unified config."""
    return list(get_config().dislike_keywords.keys())


def get_topic_weights() -> Dict[str, float]:
    """Get topic weights from unified config."""
    return get_config().core_keywords


def load_keywords_config() -> Dict:
    """Load keywords configuration - 使用统一配置管理器."""
    cm = get_config()
    return {
        'core_topics': cm.core_keywords,
        'secondary_topics': cm.get_keywords_by_category('secondary'),
        'theory_keywords': cm._config.get('theory_keywords', []),
        'demote_topics': cm.demote_keywords,
        'dislike_topics': list(cm.dislike_keywords.keys())
    }


def save_keywords_config(config: Dict) -> bool:
    """Save keywords configuration - 使用统一配置管理器."""
    try:
        cm = get_config()

        # 更新核心主题
        if 'core_topics' in config:
            for topic, weight in config['core_topics'].items():
                cm.set_keyword(topic, weight, 'core')

        # 更新次要主题
        if 'secondary_topics' in config:
            for topic, weight in config['secondary_topics'].items():
                cm.set_keyword(topic, weight, 'secondary')

        # 更新降权主题
        if 'demote_topics' in config:
            for topic, weight in config['demote_topics'].items():
                cm.set_keyword(topic, weight, 'demote')

        # 更新不感兴趣主题
        if 'dislike_topics' in config:
            for topic in config['dislike_topics']:
                cm.set_keyword(topic, -1.0, 'dislike')

        return True
    except Exception as e:
        logger.error(f"Error saving keywords config: {e}")
        return False


def get_core_topics() -> Dict[str, float]:
    """Get core topics from unified config."""
    return get_config().core_keywords


def get_secondary_topics() -> Dict[str, float]:
    """Get secondary topics from unified config."""
    return get_config().get_keywords_by_category('secondary')


def get_theory_keywords() -> List[str]:
    """Get theory keywords from unified config."""
    return get_config()._config.get('theory_keywords', [
        "theorem", "proof", "bound", "convergence", "statistical",
        "bayesian", "estimation", "generalization", "asymptotic",
        "minimax", "optimal", "rate", "complexity", "guarantee"
    ])


def get_demote_topics() -> Dict[str, float]:
    """Get demote topics from unified config."""
    return get_config().demote_keywords


def get_dislike_topics_list() -> List[str]:
    """Get dislike topics from unified config."""
    return list(get_config().dislike_keywords.keys())


class SettingsService:
    def load_keywords_config(self) -> dict:
        try:
            from config_manager import get_config

            cm = get_config()
            return {
                "core_topics": cm.core_keywords,
                "secondary_topics": cm.get_keywords_by_category("secondary"),
                "theory_keywords": cm._config.get("theory_keywords", []),
                "demote_topics": cm.demote_keywords,
                "dislike_topics": list(cm.dislike_keywords.keys()),
            }
        except Exception as e:
            logger.error(f"Error loading keywords config: {e}")
            return {"core_topics": {}, "secondary_topics": {}, "theory_keywords": [], "demote_topics": {}, "dislike_topics": []}

    def save_keywords_config(self, config: dict) -> None:
        try:
            from config_manager import get_config

            cm = get_config()
            if "core_topics" in config:
                for topic, weight in config["core_topics"].items():
                    cm.set_keyword(topic, weight, "core", save=False)
            if "secondary_topics" in config:
                for topic, weight in config["secondary_topics"].items():
                    cm.set_keyword(topic, weight, "secondary", save=False)
            if "theory_keywords" in config:
                cm._config["theory_keywords"] = list(config["theory_keywords"])
            if "demote_topics" in config:
                for topic, weight in config["demote_topics"].items():
                    cm.set_keyword(topic, weight, "demote", save=False)
            if "dislike_topics" in config:
                dislike_list = config["dislike_topics"]
                if isinstance(dislike_list, dict):
                    for topic, weight in dislike_list.items():
                        cm.set_keyword(topic, weight, "dislike", save=False)
                elif isinstance(dislike_list, list):
                    for topic in dislike_list:
                        cm.set_keyword(topic, -1.0, "dislike", save=False)
            cm.save()
        except Exception as e:
            logger.error(f"Error saving keywords config: {e}")

    def get_config_manager(self):
        from config_manager import get_config

        return get_config()

    def reload_config(self):
        from config_manager import reload_config

        return reload_config()


__all__ = [
    "SettingsService",
    "DEFAULT_PRIORITY_TOPICS",
    "load_user_config",
    "save_user_config",
    "get_priority_topics",
    "get_dislike_topics",
    "get_topic_weights",
    "load_keywords_config",
    "save_keywords_config",
    "get_core_topics",
    "get_secondary_topics",
    "get_theory_keywords",
    "get_demote_topics",
    "get_dislike_topics_list",
]
