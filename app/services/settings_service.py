"""Settings service — user profile, keywords CRUD, and settings persistence."""

from __future__ import annotations

from logger_config import get_logger

logger = get_logger(__name__)


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
