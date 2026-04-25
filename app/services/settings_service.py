"""Settings service boundary around local profile and keyword files."""

from __future__ import annotations


class SettingsService:
    def load_profile(self):
        from config_manager import get_config

        return get_config()

    def reload_profile(self):
        from config_manager import reload_config

        return reload_config()

    def load_keywords(self):
        import web_server

        return web_server.load_keywords_config()

    def save_keywords(self, config):
        import web_server

        return web_server.save_keywords_config(config)

