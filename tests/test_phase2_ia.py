import unittest
from pathlib import Path


class Phase2InformationArchitectureTests(unittest.TestCase):
    def test_top_level_nav_has_only_five_product_destinations(self):
        import web_server

        nav = web_server.NAV_ITEM_CONFIG
        self.assertEqual([item[0] for item in nav], ["inbox", "queue", "library", "monitor", "settings"])
        self.assertNotIn("search", [item[0] for item in nav])

    def test_inbox_template_is_strict_triage_surface(self):
        template = Path("templates/home_research.html").read_text(encoding="utf-8")

        required = ["Relevant", "Ignore", "Skim Later", "Deep Read", "Open arXiv", "Why Recommended"]
        for text in required:
            self.assertIn(text, template)

        forbidden_main_surface = [
            "Daily brief",
            "bulkBar",
            "bulkSelectVisible",
            "date-strip-card",
            "Ranking Rationale",
            "Read Lane",
            "Full diagnostics",
        ]
        for text in forbidden_main_surface:
            self.assertNotIn(text, template)

        self.assertIn("More actions", template)
        self.assertIn("Add to Collection", template)
        self.assertIn("Download PDF", template)
        self.assertIn("Export BibTeX", template)

    def test_queue_defaults_to_inbox_and_has_only_canonical_tabs(self):
        template = Path("templates/queue_research.html").read_text(encoding="utf-8")

        self.assertNotIn("All <span", template)
        self.assertIn("active_status == status", template)
        for status in ["Inbox", "Skim Later", "Deep Read", "Saved", "Archived"]:
            self.assertIn(status, template)

    def test_library_collection_creation_uses_modal_not_prompt(self):
        library_template = Path("templates/library_research.html").read_text(encoding="utf-8")
        ui_js = Path("static/research_ui.js").read_text(encoding="utf-8")

        combined = library_template + "\n" + ui_js
        self.assertNotIn("createCollectionPrompt", combined)
        self.assertNotIn("window.prompt", combined)
        self.assertNotIn("prompt(", combined)
        self.assertIn("openCollectionEditor", combined)

    def test_monitor_labels_query_subscriptions_and_avoids_prominent_search_cta(self):
        template = Path("templates/monitor_research.html").read_text(encoding="utf-8")

        self.assertIn("Query Subscriptions", template)
        self.assertNotIn('href="/search" class="btn', template)


if __name__ == "__main__":
    unittest.main()
