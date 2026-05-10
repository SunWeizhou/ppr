"""Settings provider and diagnostics tests for Phase 5."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from state_store import StateStore


class SettingsProviderDiagnosticsTests(unittest.TestCase):
    def _swap_config(self, tmp_config: Path):
        import config_manager as cm_mod
        from config_manager import ConfigManager

        original_cf = cm_mod.CONFIG_FILE
        original_instance = ConfigManager._instance
        cm_mod.CONFIG_FILE = tmp_config
        ConfigManager._instance = None
        self.addCleanup(setattr, cm_mod, "CONFIG_FILE", original_cf)
        self.addCleanup(setattr, ConfigManager, "_instance", original_instance)

    def _swap_store(self, store: StateStore):
        import web_server
        from app.routes import api as api_routes

        original_web_store = web_server.STATE_STORE
        original_api_store = api_routes.STATE_STORE
        web_server.STATE_STORE = store
        api_routes.STATE_STORE = store
        self.addCleanup(setattr, web_server, "STATE_STORE", original_web_store)
        self.addCleanup(setattr, api_routes, "STATE_STORE", original_api_store)

    def test_ai_settings_provider_none_clears_stored_key_and_disables(self):
        import web_server
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(
                json.dumps({
                    "version": 1,
                    "keywords": {},
                    "ai": {
                        "provider": "deepseek",
                        "api_key": "sk-existing-secret",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                        "enabled": True,
                    },
                }),
                encoding="utf-8",
            )
            self._swap_config(tmp_config)

            response = web_server.app.test_client().post(
                "/api/settings/ai",
                json={"provider": "none", "api_key": "", "enabled": False},
            )
            ConfigManager._instance = None
            ai_cfg = get_config().get_ai_config()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(ai_cfg["provider"], "none")
        self.assertEqual(ai_cfg["api_key"], "")
        self.assertFalse(ai_cfg["enabled"])

    def test_ai_settings_keep_sentinel_preserves_key_and_enabled_state(self):
        import web_server
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(
                json.dumps({
                    "version": 1,
                    "keywords": {},
                    "ai": {
                        "provider": "deepseek",
                        "api_key": "sk-existing-secret",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                        "enabled": True,
                    },
                }),
                encoding="utf-8",
            )
            self._swap_config(tmp_config)

            response = web_server.app.test_client().post(
                "/api/settings/ai",
                json={
                    "provider": "deepseek",
                    "api_key": "__keep__",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-reasoner",
                },
            )
            ConfigManager._instance = None
            ai_cfg = get_config().get_ai_config()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(ai_cfg["provider"], "deepseek")
        self.assertEqual(ai_cfg["api_key"], "sk-existing-secret")
        self.assertEqual(ai_cfg["model"], "deepseek-reasoner")
        self.assertTrue(ai_cfg["enabled"])

    def test_ai_settings_rejects_unknown_provider(self):
        import web_server

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(json.dumps({"version": 1, "keywords": {}}), encoding="utf-8")
            self._swap_config(tmp_config)

            response = web_server.app.test_client().post(
                "/api/settings/ai",
                json={"provider": "unknown", "api_key": "sk-test"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])
