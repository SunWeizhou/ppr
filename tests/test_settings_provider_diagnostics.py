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

        original_web_store = web_server.STATE_STORE
        web_server.STATE_STORE = store
        self.addCleanup(setattr, web_server, "STATE_STORE", original_web_store)

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

    def test_build_ai_provider_uses_statdesk_env_var(self):
        from app.services.ai_providers import DeepSeekProvider, build_ai_provider_from_env

        with mock.patch.dict(
            os.environ,
            {
                "STATDESK_AI_API_KEY": "sk-statdesk-env",
                "DEEPSEEK_API_KEY": "",
            },
            clear=True,
        ):
            provider = build_ai_provider_from_env()

        self.assertIsInstance(provider, DeepSeekProvider)
        self.assertEqual(provider.api_key, "sk-statdesk-env")

    def test_ai_connection_test_uses_env_sentinel_without_leaking_secret(self):
        import web_server

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(json.dumps({"version": 1, "keywords": {}}), encoding="utf-8")
            self._swap_config(tmp_config)

            fake_response = {
                "choices": [{"message": {"content": "ok"}}],
            }
            with mock.patch.dict(os.environ, {"STATDESK_AI_API_KEY": "sk-env-secret"}, clear=True):
                with mock.patch(
                    "app.services.ai_providers.DeepSeekProvider._request",
                    return_value=fake_response,
                ) as mock_request:
                    response = web_server.app.test_client().post(
                        "/api/settings/ai/test",
                        json={
                            "provider": "deepseek",
                            "api_key": "__env_var__",
                            "base_url": "https://api.deepseek.com",
                            "model": "deepseek-chat",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertNotIn("sk-env-secret", json.dumps(payload))
        mock_request.assert_called_once()

    def test_resolve_ai_env_empty_dict_does_not_read_real_env(self):
        from app.services.ai_settings_service import resolve_ai_env

        with mock.patch.dict(os.environ, {"STATDESK_AI_API_KEY": "sk-real"}, clear=True):
            result = resolve_ai_env({})

        self.assertFalse(result["has_key"])
        self.assertEqual(result["source"], "none")

    def test_onboarding_rejects_unsupported_ai_provider(self):
        import web_server
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            self._swap_config(tmp_config)
            store = StateStore(str(Path(tmp) / "state.db"))
            self._swap_store(store)

            with mock.patch.dict(os.environ, {}, clear=True):
                response = web_server.app.test_client().post(
                    "/api/onboarding/save",
                    json={
                        "topics": ["test"],
                        "areas": [],
                        "papers_per_day": 20,
                        "zotero_path": "",
                        "ai_provider": "openai_compat",
                        "ai_api_key": "sk-should-not-save",
                        "first_query": "",
                    },
                )
                ConfigManager._instance = None

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["success"])
            ai_cfg = get_config().get_ai_config()
            self.assertEqual(ai_cfg["provider"], "none")
            self.assertFalse(ai_cfg["enabled"])

    def test_settings_viewmodel_includes_system_diagnostics(self):
        from app.viewmodels.settings_viewmodel import SettingsViewModel

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            question = store.create_research_question(
                query_text="conformal prediction",
                intent_statement="Track conformal prediction.",
            )
            store.create_subscription(
                "query",
                "Conformal alerts",
                "conformal prediction",
                research_question_id=question["id"],
            )
            store.upsert_queue_item(
                "2604.55555",
                "Inbox",
                source="test",
                research_question_id=question["id"],
            )

            context = SettingsViewModel(store).to_template_context(tab="diagnostics")

        diagnostics = context["system_diagnostics"]
        self.assertEqual(diagnostics["product_name"], "Agent Literature Research Assistant")
        self.assertEqual(diagnostics["workspace"]["research_question_count"], 1)
        self.assertEqual(diagnostics["workspace"]["subscription_count"], 1)
        self.assertEqual(diagnostics["workspace"]["queue_counts"]["Inbox"], 1)
        self.assertIn("ai", diagnostics)
        self.assertIn("data", diagnostics)

    def test_settings_ai_tab_renders_without_raw_secret(self):
        import web_server
        from config_manager import ConfigManager

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(
                json.dumps({
                    "version": 1,
                    "keywords": {"conformal prediction": {"weight": 5.0, "category": "core"}},
                    "ai": {
                        "provider": "deepseek",
                        "api_key": "sk-raw-secret",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                        "enabled": True,
                    },
                }),
                encoding="utf-8",
            )
            self._swap_config(tmp_config)
            with mock.patch.dict(os.environ, {}, clear=True):
                response = web_server.app.test_client().get("/settings?tab=ai")
            ConfigManager._instance = None

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("AI Provider", html)
        self.assertIn("sk-...cret", html)
        self.assertNotIn("sk-raw-secret", html)
        self.assertIn("settings-nav-link", html)

    def test_settings_template_has_ai_tab_and_diagnostics_contract(self):
        template = Path("templates/settings_research.html").read_text(encoding="utf-8")

        self.assertIn("tab=ai", template)
        self.assertIn("system_diagnostics", template)
        self.assertIn("AI Provider", template)
        self.assertIn("effective_enabled", template)

    def test_onboarding_first_query_creates_bound_research_question_and_subscription(self):
        import web_server
        from config_manager import ConfigManager

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            self._swap_config(tmp_config)
            store = StateStore(str(Path(tmp) / "state.db"))
            self._swap_store(store)

            response = web_server.app.test_client().post(
                "/api/onboarding/save",
                json={
                    "topics": ["conformal prediction"],
                    "areas": ["statistics"],
                    "papers_per_day": 20,
                    "zotero_path": "",
                    "ai_provider": "none",
                    "ai_api_key": "",
                    "first_query": "Conformal prediction under distribution shift",
                },
            )
            ConfigManager._instance = None

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertIsNotNone(payload.get("research_question_id"))
            question = store.get_research_question(payload["research_question_id"])
            self.assertIsNotNone(question)
            self.assertEqual(question["query_text"], "Conformal prediction under distribution shift")

            subscriptions = store.list_subscriptions(type="query")
            self.assertEqual(len(subscriptions), 1)
            self.assertEqual(
                subscriptions[0]["research_question_id"],
                payload["research_question_id"],
            )
