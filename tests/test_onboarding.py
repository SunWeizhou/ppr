"""Unit tests for Onboarding wizard and AI Settings features."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from state_store import StateStore


class OnboardingAndAISettingsTests(unittest.TestCase):
    """Tests covering the onboarding flow, inbox redirect, and AI settings API."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _temp_state_store(tmp_dir):
        """Create an isolated StateStore inside *tmp_dir*."""
        return StateStore(str(Path(tmp_dir) / "state.db"))

    # ------------------------------------------------------------------
    # Onboarding page
    # ------------------------------------------------------------------

    def test_onboarding_page_returns_200(self):
        """GET /onboarding returns 200 and renders the setup page."""
        import web_server

        client = web_server.app.test_client()
        response = client.get("/onboarding")

        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Onboarding save
    # ------------------------------------------------------------------

    def test_onboarding_save_creates_profile(self):
        """POST /api/onboarding/save writes a valid user_profile.json."""
        import web_server
        from app.routes import api as api_routes
        import config_manager as cm_mod
        from config_manager import ConfigManager

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"

            # --- Swap globals ---
            original_cf = cm_mod.CONFIG_FILE
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None
            web_server.STATE_STORE = self._temp_state_store(tmp)
            api_routes.STATE_STORE = web_server.STATE_STORE

            try:
                client = web_server.app.test_client()
                payload = {
                    "topics": ["conformal prediction", "causal inference"],
                    "areas": ["statistics", "machine learning"],
                    "papers_per_day": 15,
                    "zotero_path": "",
                    "ai_provider": "deepseek",
                    "ai_api_key": "sk-test-key",
                    "ai_base_url": "",
                    "ai_model": "",
                    "first_query": "What's new in conformal prediction?",
                }
                response = client.post(
                    "/api/onboarding/save",
                    json=payload,
                    content_type="application/json",
                )

                # --- Assertions (inside try, before globals are restored) ---
                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertTrue(body["success"], msg=f"Expected success, got: {body}")

                self.assertTrue(tmp_config.exists(), "user_profile.json was not created")

                raw = json.loads(tmp_config.read_text(encoding="utf-8"))
                keywords = raw.get("keywords", {})
                self.assertIn("conformal prediction", keywords)
                self.assertEqual(keywords["conformal prediction"]["category"], "core")
                self.assertEqual(keywords["conformal prediction"]["weight"], 5.0)
                self.assertEqual(raw["settings"]["papers_per_day"], 15)
                self.assertEqual(raw["ai"]["provider"], "deepseek")
                self.assertTrue(raw["ai"]["enabled"])
            finally:
                cm_mod.CONFIG_FILE = original_cf
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

    def test_onboarding_save_creates_keywords(self):
        """Core keywords in ConfigManager match the submitted topics after save."""
        import web_server
        from app.routes import api as api_routes
        import config_manager as cm_mod
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"

            original_cf = cm_mod.CONFIG_FILE
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None
            web_server.STATE_STORE = self._temp_state_store(tmp)
            api_routes.STATE_STORE = web_server.STATE_STORE

            try:
                client = web_server.app.test_client()
                payload = {
                    "topics": ["bayesian deep learning", "differential privacy"],
                    "areas": ["theoretical ml"],
                    "papers_per_day": 25,
                    "zotero_path": "",
                    "ai_provider": "none",
                    "ai_api_key": "",
                    "first_query": "",
                }
                response = client.post(
                    "/api/onboarding/save",
                    json=payload,
                    content_type="application/json",
                )

                # Re-read config through ConfigManager (fresh load from saved file)
                ConfigManager._instance = None
                cm_mod._config_manager = None
                cm = get_config()
                core_kw = cm.core_keywords
            finally:
                cm_mod.CONFIG_FILE = original_cf
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertIn("bayesian deep learning", core_kw)
        self.assertIn("differential privacy", core_kw)
        self.assertEqual(core_kw["bayesian deep learning"], 5.0)
        # Areas become secondary keywords
        all_kw = {k: v.category for k, v in cm.all_keywords.items()}
        self.assertIn("theoretical ml", all_kw)
        self.assertEqual(all_kw["theoretical ml"], "secondary")

    def test_onboarding_save_creates_first_query_subscription(self):
        """The first research question creates both a saved_search and a subscription."""
        import web_server
        from app.routes import api as api_routes
        import config_manager as cm_mod
        from config_manager import ConfigManager

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"

            original_cf = cm_mod.CONFIG_FILE
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None
            temp_store = self._temp_state_store(tmp)
            web_server.STATE_STORE = temp_store
            api_routes.STATE_STORE = temp_store

            try:
                client = web_server.app.test_client()
                payload = {
                    "topics": ["causal inference"],
                    "areas": [],
                    "papers_per_day": 20,
                    "zotero_path": "",
                    "ai_provider": "none",
                    "ai_api_key": "",
                    "first_query": "Double machine learning for causal inference",
                }
                response = client.post(
                    "/api/onboarding/save",
                    json=payload,
                    content_type="application/json",
                )

                body = response.get_json()
                saved_search_id = body.get("saved_search_id")

                # Verify saved search was created
                searches = temp_store.list_saved_searches()
                matching = [s for s in searches if s.get("query_text") == "Double machine learning for causal inference"]
            finally:
                cm_mod.CONFIG_FILE = original_cf
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["success"])
        self.assertIsNotNone(saved_search_id, "Expected a saved_search_id in the response")
        self.assertEqual(len(matching), 1, "Expected exactly one saved search for the first query")
        self.assertEqual(matching[0]["name"], "Double machine learning for causal inference")

    def test_inbox_redirects_to_onboarding_when_no_profile(self):
        """GET / redirects to /onboarding when user_profile.json does not exist."""
        import web_server
        import config_manager as cm_mod

        with tempfile.TemporaryDirectory() as tmp:
            nonexistent = Path(tmp) / "no_user_profile.json"
            original_cf = cm_mod.CONFIG_FILE
            cm_mod.CONFIG_FILE = nonexistent

            try:
                client = web_server.app.test_client()
                response = client.get("/", follow_redirects=False)
            finally:
                cm_mod.CONFIG_FILE = original_cf

        self.assertEqual(response.status_code, 302)
        self.assertIn("/onboarding", response.headers.get("Location", ""))

    def test_inbox_skips_onboarding_with_param(self):
        """GET /?skip_onboarding=1 does not redirect even without a profile."""
        import web_server
        import config_manager as cm_mod
        from app.viewmodels.inbox_viewmodel import InboxViewModel

        with tempfile.TemporaryDirectory() as tmp:
            nonexistent = Path(tmp) / "no_user_profile.json"
            original_cf = cm_mod.CONFIG_FILE
            cm_mod.CONFIG_FILE = nonexistent

            try:
                with mock.patch.object(
                    InboxViewModel, "start_background_generation", return_value=None
                ):
                    client = web_server.app.test_client()
                    response = client.get("/?skip_onboarding=1", follow_redirects=False)
            finally:
                cm_mod.CONFIG_FILE = original_cf

        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # AI Settings
    # ------------------------------------------------------------------

    def test_ai_settings_save_and_read(self):
        """POST /api/settings/ai persists config, readable via ConfigManager."""
        import web_server
        import config_manager as cm_mod
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            # Start with an empty but valid profile so ConfigManager can load it
            tmp_config.write_text(json.dumps({"version": 1, "keywords": {}}), encoding="utf-8")

            original_cf = cm_mod.CONFIG_FILE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None

            try:
                client = web_server.app.test_client()
                response = client.post(
                    "/api/settings/ai",
                    json={
                        "provider": "deepseek",
                        "api_key": "sk-abc123",
                        "base_url": "https://api.deepseek.com/v1",
                        "model": "deepseek-chat",
                        "enabled": True,
                    },
                    content_type="application/json",
                )

                # Re-read via ConfigManager
                ConfigManager._instance = None
                cm_mod._config_manager = None
                ai_cfg = get_config().get_ai_config()
            finally:
                cm_mod.CONFIG_FILE = original_cf
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(ai_cfg["provider"], "deepseek")
        self.assertEqual(ai_cfg["api_key"], "sk-abc123")
        self.assertEqual(ai_cfg["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(ai_cfg["model"], "deepseek-chat")
        self.assertTrue(ai_cfg["enabled"])

    def test_ai_settings_default_to_none(self):
        """Default AI config has provider='none' and enabled=False."""
        import config_manager as cm_mod
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            # A minimal profile with no explicit 'ai' section
            tmp_config.write_text(json.dumps({"version": 1, "keywords": {}}), encoding="utf-8")

            original_cf = cm_mod.CONFIG_FILE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None

            try:
                ai_cfg = get_config().get_ai_config()
            finally:
                cm_mod.CONFIG_FILE = original_cf
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

        self.assertEqual(ai_cfg["provider"], "none")
        self.assertFalse(ai_cfg["enabled"])
        self.assertEqual(ai_cfg["api_key"], "")

    def test_ai_settings_provider_switch(self):
        """Switching provider from 'none' to 'deepseek' persists correctly."""
        import web_server
        import config_manager as cm_mod
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(json.dumps({"version": 1, "keywords": {}}), encoding="utf-8")

            original_cf = cm_mod.CONFIG_FILE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None

            try:
                client = web_server.app.test_client()

                # Round 1: set to none
                r1 = client.post(
                    "/api/settings/ai",
                    json={"provider": "none", "api_key": "", "enabled": False},
                    content_type="application/json",
                )
                self.assertTrue(r1.get_json()["success"])

                ConfigManager._instance = None
                cm_mod._config_manager = None
                self.assertEqual(get_config().get_ai_config()["provider"], "none")

                # Round 2: switch to deepseek
                r2 = client.post(
                    "/api/settings/ai",
                    json={
                        "provider": "deepseek",
                        "api_key": "sk-switched",
                        "enabled": True,
                    },
                    content_type="application/json",
                )
                self.assertTrue(r2.get_json()["success"])

                ConfigManager._instance = None
                cm_mod._config_manager = None
                final_cfg = get_config().get_ai_config()
            finally:
                cm_mod.CONFIG_FILE = original_cf
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

        self.assertEqual(final_cfg["provider"], "deepseek")
        self.assertTrue(final_cfg["enabled"])
        self.assertEqual(final_cfg["api_key"], "sk-switched")

    def test_ai_provider_builds_from_config(self):
        """build_ai_provider_from_env() returns DeepSeekProvider when config has api_key."""
        import config_manager as cm_mod
        from config_manager import ConfigManager, get_config
        from app.services.ai_providers import build_ai_provider_from_env, DeepSeekProvider

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(
                json.dumps({
                    "version": 1,
                    "keywords": {},
                    "ai": {
                        "provider": "deepseek",
                        "api_key": "sk-config-key",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-chat",
                        "enabled": True,
                    },
                }),
                encoding="utf-8",
            )

            original_cf = cm_mod.CONFIG_FILE
            original_instance = ConfigManager._instance
            original_cm = cm_mod._config_manager

            cm_mod.CONFIG_FILE = tmp_config
            ConfigManager._instance = None
            cm_mod._config_manager = None

            try:
                # Ensure env var does NOT interfere
                with mock.patch.dict(os.environ, {}, clear=True):
                    provider = build_ai_provider_from_env()
            finally:
                cm_mod.CONFIG_FILE = original_cf
                ConfigManager._instance = original_instance
                cm_mod._config_manager = original_cm

        self.assertIsInstance(provider, DeepSeekProvider)
        self.assertEqual(provider.api_key, "sk-config-key")
        self.assertEqual(provider.model, "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
