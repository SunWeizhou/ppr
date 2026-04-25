import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class ApiCountingProvider:
    model_name = "api-counting-provider"

    def __init__(self):
        self.calls = 0

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        self.calls += 1
        return {
            "one_sentence_summary": f"API summary {self.calls}",
            "problem": "api problem",
            "method": "api method",
            "contribution": "api contribution",
            "limitations": "api limitations",
            "why_it_matters": "api why",
            "recommended_reading_level": "skim",
        }


class AIAnalysisApiTests(unittest.TestCase):
    def test_get_missing_analysis_returns_404(self):
        import web_server
        from app.routes import api as api_routes

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            web_server.STATE_STORE = store
            api_routes.STATE_STORE = store
            try:
                response = web_server.app.test_client().get("/api/papers/2604.12345v2/analysis")
            finally:
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"success": False, "error": "analysis_not_found"})

    def test_post_generate_with_no_provider_returns_not_configured(self):
        import web_server
        from app.routes import api as api_routes

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            original_provider = api_routes.AI_ANALYSIS_PROVIDER
            web_server.STATE_STORE = store
            api_routes.STATE_STORE = store
            api_routes.AI_ANALYSIS_PROVIDER = None
            try:
                response = web_server.app.test_client().post(
                    "/api/papers/2604.23456v2/analysis/generate",
                    json={"paper": {"id": "2604.23456v2", "title": "No provider"}, "force": False},
                )
                cached = web_server.app.test_client().get("/api/papers/2604.23456/analysis")
            finally:
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store
                api_routes.AI_ANALYSIS_PROVIDER = original_provider

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["analysis"]["paper_id"], "2604.23456")
        self.assertEqual(payload["analysis"]["status"], "not_configured")
        self.assertEqual(cached.status_code, 200)
        self.assertEqual(cached.get_json()["analysis"]["paper_id"], "2604.23456")

    def test_post_generate_uses_url_paper_id_over_body_id(self):
        import web_server
        from app.routes import api as api_routes

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            provider = ApiCountingProvider()
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            original_provider = api_routes.AI_ANALYSIS_PROVIDER
            web_server.STATE_STORE = store
            api_routes.STATE_STORE = store
            api_routes.AI_ANALYSIS_PROVIDER = provider
            try:
                response = web_server.app.test_client().post(
                    "/api/papers/2604.45678v2/analysis/generate",
                    json={"paper": {"id": "2604.99999v9", "title": "Path wins"}},
                )
                wrong_id = store.get_paper_ai_analysis("2604.99999")
                path_id = store.get_paper_ai_analysis("2604.45678")
            finally:
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store
                api_routes.AI_ANALYSIS_PROVIDER = original_provider

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["analysis"]["paper_id"], "2604.45678")
        self.assertIsNone(wrong_id)
        self.assertIsNotNone(path_id)

    def test_post_generate_uses_injected_provider_and_force_regenerates(self):
        import web_server
        from app.routes import api as api_routes

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            provider = ApiCountingProvider()
            original_store = web_server.STATE_STORE
            original_api_store = api_routes.STATE_STORE
            original_provider = api_routes.AI_ANALYSIS_PROVIDER
            web_server.STATE_STORE = store
            api_routes.STATE_STORE = store
            api_routes.AI_ANALYSIS_PROVIDER = provider
            try:
                client = web_server.app.test_client()
                first = client.post(
                    "/api/papers/2604.34567v3/analysis/generate",
                    json={"paper": {"id": "2604.34567v3", "title": "With provider"}},
                )
                second = client.post(
                    "/api/papers/2604.34567/analysis/generate",
                    json={"paper": {"id": "2604.34567", "title": "With provider"}},
                )
                forced = client.post(
                    "/api/papers/2604.34567/analysis/generate",
                    json={"paper": {"id": "2604.34567", "title": "With provider"}, "force": True},
                )
                cached = client.get("/api/papers/2604.34567v9/analysis")
            finally:
                web_server.STATE_STORE = original_store
                api_routes.STATE_STORE = original_api_store
                api_routes.AI_ANALYSIS_PROVIDER = original_provider

        self.assertEqual(provider.calls, 2)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(forced.status_code, 200)
        self.assertEqual(first.get_json()["analysis"]["paper_id"], "2604.34567")
        self.assertEqual(first.get_json()["analysis"]["one_sentence_summary"], "API summary 1")
        self.assertEqual(second.get_json()["analysis"]["one_sentence_summary"], "API summary 1")
        self.assertEqual(forced.get_json()["analysis"]["one_sentence_summary"], "API summary 2")
        self.assertEqual(cached.get_json()["analysis"]["one_sentence_summary"], "API summary 2")


if __name__ == "__main__":
    unittest.main()
