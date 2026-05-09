import unittest
from pathlib import Path


class Phase2InformationArchitectureTests(unittest.TestCase):
    def test_top_level_nav_has_three_product_destinations(self):
        import web_server

        nav = web_server.NAV_ITEM_CONFIG
        self.assertEqual([item[0] for item in nav], ["inbox", "reading", "watch"])
        self.assertNotIn("search", [item[0] for item in nav])

    def test_inbox_template_is_strict_triage_surface(self):
        template = Path("templates/today.html").read_text(encoding="utf-8")

        required = [
            "Daily Triage",
            "Save",
            "Pass",
            "Regenerate",
            "paper-list-item",
            "data-paper-id",
            "data-action",
        ]
        for text in required:
            self.assertIn(text, template)

        forbidden_inbox_surface = [
            "detail-panel",
            "More actions",
            "AI Analysis",
            "data-ai-analysis",
        ]
        for text in forbidden_inbox_surface:
            self.assertNotIn(text, template)

        self.assertIn("why-line", template)
        self.assertIn("paper-list-title", template)
        self.assertIn("paper-authors", template)

    def test_inbox_page_still_serves(self):
        import web_server

        response = web_server.app.test_client().get("/")
        self.assertEqual(response.status_code, 200)

    def test_evaluation_page_serves_200(self):
        import web_server

        response = web_server.app.test_client().get("/evaluation")
        self.assertEqual(response.status_code, 200)

    def test_library_redirects_to_reading(self):
        import web_server

        response = web_server.app.test_client().get("/library?tab=collections&collection_id=1")
        self.assertIn(response.status_code, (200, 302))
        if response.status_code == 302:
            self.assertIn("/reading", response.location)

    def test_search_page_serves_200(self):
        import web_server

        response = web_server.app.test_client().get("/search")
        self.assertEqual(response.status_code, 200)

    def test_settings_diagnostics_link_points_to_valid_route(self):
        import web_server

        response = web_server.app.test_client().get("/settings?tab=diagnostics")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("Evaluation", html)  # Full evaluation panel link should be present

    def test_queue_defaults_to_inbox_and_has_only_canonical_tabs(self):
        template = Path("templates/queue_research.html").read_text(encoding="utf-8")

        self.assertNotIn("All <span", template)
        self.assertIn("active_status == status", template)
        for status in ["Inbox", "Skim Later", "Deep Read", "Saved", "Archived"]:
            self.assertIn(status, template)

    def test_reading_collection_creation_uses_modal_not_prompt(self):
        reading_template = Path("templates/reading.html").read_text(encoding="utf-8")

        self.assertNotIn("window.prompt", reading_template)
        self.assertIn("collections", reading_template)
        self.assertIn("all_collections", reading_template)

    def test_watch_labels_unified_subscriptions_and_avoids_prominent_search_cta(self):
        template = Path("templates/watch.html").read_text(encoding="utf-8")

        self.assertIn("研究方向", template)
        self.assertNotIn('href="/search" class="btn', template)


if __name__ == "__main__":
    unittest.main()
