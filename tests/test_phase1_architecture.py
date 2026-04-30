import inspect
import unittest
from pathlib import Path


class Phase1ArchitectureTests(unittest.TestCase):
    def test_app_package_layers_exist(self):
        expected = [
            "app/__init__.py",
            "app/routes/inbox.py",
            "app/routes/queue.py",
            "app/routes/library.py",
            "app/routes/monitor.py",
            "app/routes/settings.py",
            "app/routes/api/__init__.py",
            "app/routes/api/helpers.py",
            "app/routes/api/ai.py",
            "app/routes/api/feedback.py",
            "app/routes/api/queue.py",
            "app/routes/api/state.py",
            "app/routes/api/collections.py",
            "app/routes/api/saved_searches.py",
            "app/routes/api/subscriptions.py",
            "app/routes/api/keywords.py",
            "app/routes/api/inbox.py",
            "app/routes/api/evaluation.py",
            "app/routes/api/paper.py",
            "app/services/queue_service.py",
            "app/services/library_service.py",
            "app/services/monitor_service.py",
            "app/services/settings_service.py",
            "app/services/feedback_service.py",
            "app/services/recommendation_service.py",
            "app/services/scoring_service.py",
            "app/services/arxiv_source.py",
            "app/services/zotero_service.py",
            "app/services/citation_service.py",
            "app/viewmodels/inbox_viewmodel.py",
            "app/viewmodels/queue_viewmodel.py",
            "app/viewmodels/library_viewmodel.py",
            "app/repositories/__init__.py",
            "app/models/__init__.py",
        ]

        missing = [path for path in expected if not Path(path).exists()]

        self.assertEqual(missing, [])

    def test_web_server_uses_blueprints_instead_of_direct_route_decorators(self):
        source = Path("web_server.py").read_text(encoding="utf-8")

        self.assertNotIn("@app.route", source)
        self.assertIn("register_blueprints(app)", source)

    def test_core_pages_are_served_by_blueprints(self):
        import web_server

        client = web_server.app.test_client()
        for path in ["/", "/queue", "/library", "/monitor", "/settings"]:
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_compatibility_page_routes_redirect_or_remain_available(self):
        import web_server

        client = web_server.app.test_client()
        expectations = {
            "/search": {200},
        }
        for path, allowed in expectations.items():
            response = client.get(path)
            self.assertIn(response.status_code, allowed, path)

    def test_legacy_redirect_routes_removed(self):
        """Legacy redirect routes were removed in Phase 5 cleanup."""
        import web_server

        client = web_server.app.test_client()
        for path in ["/track", "/scholars", "/journal", "/liked", "/disliked", "/stats"]:
            response = client.get(path)
            self.assertEqual(response.status_code, 404, path)

    def test_api_shapes_survive_blueprint_split(self):
        import web_server
        from state_store import StateStore
        import tempfile

        client = web_server.app.test_client()
        with tempfile.TemporaryDirectory() as tmp:
            original_store = web_server.STATE_STORE
            web_server.STATE_STORE = StateStore(str(Path(tmp) / "state.db"))
            try:
                collection_response = client.post(
                    "/api/collections",
                    json={"name": "Blueprint Test", "description": "kept shape"},
                )
                queue_response = client.post(
                    "/api/queue",
                    json={"paper_id": "2604.12345v2", "status": "Skim Later", "note": "read intro"},
                )
                searches_response = client.post(
                    "/api/saved-searches",
                    json={"name": "Query Test", "query_text": "conformal prediction"},
                )
            finally:
                web_server.STATE_STORE = original_store

        self.assertEqual(collection_response.status_code, 200)
        self.assertIn("collection", collection_response.get_json())
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(queue_response.get_json()["item"]["paper_id"], "2604.12345")
        self.assertEqual(queue_response.get_json()["item"]["note"], "read intro")
        self.assertEqual(searches_response.status_code, 200)
        self.assertIn("saved_search", searches_response.get_json())

    def test_recommender_public_imports_remain_compatible(self):
        import arxiv_recommender_v5
        from app.services.scoring_service import EnhancedScorer
        from app.services.citation_service import CitationAnalyzer
        from app.services.arxiv_source import search_by_keywords

        self.assertIs(arxiv_recommender_v5.EnhancedScorer, EnhancedScorer)
        self.assertIs(arxiv_recommender_v5.CitationAnalyzer, CitationAnalyzer)
        self.assertIs(arxiv_recommender_v5.search_by_keywords, search_by_keywords)
        self.assertTrue(inspect.isclass(EnhancedScorer))


if __name__ == "__main__":
    unittest.main()
