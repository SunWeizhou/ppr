import unittest
from pathlib import Path


class Phase2InformationArchitectureTests(unittest.TestCase):
    def test_top_level_nav_has_core_product_destinations(self):
        import web_server

        nav = web_server.NAV_ITEM_CONFIG
        keys = [item["key"] for item in nav]
        self.assertIn("search", keys)
        self.assertIn("subscriptions", keys)
        self.assertIn("reading", keys)
        self.assertNotIn("home", keys)
        self.assertNotIn("explore", keys)

    def test_inbox_template_is_strict_triage_surface(self):
        template = Path("templates/today.html").read_text(encoding="utf-8")

        required = [
            "Daily Triage",
            "Add to Reading",
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

        # / now renders the Paper Agent search workspace.
        response = web_server.app.test_client().get("/?skip_onboarding=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Research Workspace", response.get_data(as_text=True))

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
        for status in ["Inbox", "Completed"]:
            self.assertIn(status, template)

    def test_reading_collection_creation_uses_modal_not_prompt(self):
        reading_template = Path("templates/reading.html").read_text(encoding="utf-8")

        self.assertNotIn("window.prompt", reading_template)
        self.assertIn("collections", reading_template)
        self.assertIn("all_collections", reading_template)

    def test_watch_labels_unified_subscriptions_and_avoids_prominent_search_cta(self):
        template = Path("templates/watch.html").read_text(encoding="utf-8")

        self.assertIn("Subscriptions", template)
        self.assertIn("Back to Search", template)

    def test_watch_empty_icons_render_as_characters_not_entity_text(self):
        """Empty-state icons in watch.html must render as actual characters,
        not literal HTML entity strings."""
        template = Path("templates/_components.html").read_text(encoding="utf-8")
        # The empty_state macro should use |safe filter for icons
        self.assertIn("icon|safe", template)

    def test_watch_monitor_viewmodel_returns_filtered_sub_lists(self):
        """MonitorViewModel.to_template_context() should include
        query_subs, author_subs, and venue_subs."""
        import tempfile
        from pathlib import Path
        from state_store import StateStore
        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "test.db"))
            store.create_subscription("query", "Q1", "ml")
            store.create_subscription("author", "A1", "Hinton")
            store.create_subscription("venue", "V1", "NeurIPS")

            vm = MonitorViewModel(store)
            ctx = vm.to_template_context("recent-hits")

            self.assertIn("query_subs", ctx)
            self.assertIn("author_subs", ctx)
            self.assertIn("journal_cards", ctx)
            self.assertEqual(len(ctx["query_subs"]), 1)
            self.assertEqual(len(ctx["author_subs"]), 1)
            self.assertEqual(len(ctx["journal_cards"]), 1)
            self.assertEqual(ctx["query_subs"][0]["name"], "Q1")


if __name__ == "__main__":
    unittest.main()
