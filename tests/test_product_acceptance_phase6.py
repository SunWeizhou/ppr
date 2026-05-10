"""Phase 6 product acceptance tests.

These tests guard the finished workspace-first product experience without
requiring live arXiv, live AI providers, Zotero, or browser goldens.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ACTIVE_COPY_FILES = [
    Path("app/viewmodels/search_viewmodel.py"),
    Path("app/viewmodels/queue_viewmodel.py"),
    Path("app/viewmodels/monitor_viewmodel.py"),
    Path("app/viewmodels/paper_viewmodel.py"),
    Path("app/viewmodels/eval_viewmodel.py"),
    Path("templates/onboarding.html"),
    Path("templates/queue_research.html"),
    Path("templates/generating.html"),
    Path("static/js/core.js"),
    Path("static/research_ui.js"),
    Path("static/js/modals.js"),
    Path("static/js/subscriptions.js"),
]


class Phase6ProductAcceptanceTests(unittest.TestCase):
    def test_active_surfaces_use_current_product_name(self):
        for path in ACTIVE_COPY_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "arXiv Recommender",
                text,
                msg=f"stale product name in {path}",
            )

    def test_active_surfaces_do_not_use_stale_monitor_or_library_labels(self):
        guarded_files = [
            Path("templates/onboarding.html"),
            Path("templates/queue_research.html"),
            Path("static/js/core.js"),
            Path("static/research_ui.js"),
            Path("static/js/subscriptions.js"),
        ]
        forbidden = [
            "Monitor subscription",
            "Monitor 中",
            "nav.monitor",
            "nav.library",
            "View Saved in Library",
            "Save to Library",
        ]
        for path in guarded_files:
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, text, msg=f"{needle!r} in {path}")

    def test_today_generation_copy_uses_inbox_language(self):
        files = [
            Path("templates/generating.html"),
            Path("static/js/modals.js"),
            Path("static/research_ui.js"),
        ]
        forbidden = ["刷新今日推荐", "今日推荐", "重新生成推荐"]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, text, msg=f"{needle!r} in {path}")

    def test_queue_paper_status_has_single_canonical_definition(self):
        action_files = [
            Path("static/js/paper_actions.js"),
            Path("static/research_ui.js"),
        ]
        definitions = []
        for path in action_files:
            text = path.read_text(encoding="utf-8")
            if "function queuePaperStatus" in text or "async function queuePaperStatus" in text:
                definitions.append(str(path))

        self.assertEqual(
            definitions,
            ["static/js/paper_actions.js"],
            msg=f"queuePaperStatus should only be defined in paper_actions.js, found {definitions}",
        )

    def test_core_routes_serve_without_external_network(self):
        import tempfile
        from unittest import mock

        import web_server
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            question = store.create_research_question(
                query_text="conformal prediction",
                intent_statement="Track conformal prediction.",
            )
            store.save_paper_metadata(
                "2604.77777",
                {
                    "title": "Conformal Prediction Acceptance Paper",
                    "abstract": "A paper used for acceptance tests.",
                    "authors": ["Alice"],
                },
                source="phase6-test",
            )
            store.upsert_queue_item(
                "2604.77777",
                "Inbox",
                source="phase6",
                research_question_id=question["id"],
                decision_context="Phase 6 acceptance candidate",
            )
            store.create_subscription(
                "query",
                "Conformal Watch",
                "conformal prediction",
                research_question_id=question["id"],
            )

            import app.routes.queue as queue_routes

            original_web_store = web_server.STATE_STORE
            original_queue_store = queue_routes.STATE_STORE
            web_server.STATE_STORE = store
            queue_routes.STATE_STORE = store
            self.addCleanup(setattr, web_server, "STATE_STORE", original_web_store)
            self.addCleanup(setattr, queue_routes, "STATE_STORE", original_queue_store)

            client = web_server.app.test_client()
            with mock.patch("arxiv_recommender_v5.search_by_keywords") as mock_search:
                routes = [
                    "/?skip_onboarding=1",
                    "/search",
                    f"/queue?status=Inbox",
                    f"/papers/2604.77777?research_question_id={question['id']}",
                    "/reading",
                    "/watch",
                    "/settings?tab=profile",
                    "/settings?tab=ai",
                    "/settings?tab=diagnostics",
                    "/evaluation",
                ]
                for route in routes:
                    response = client.get(route)
                    self.assertEqual(response.status_code, 200, msg=route)

            mock_search.assert_not_called()

    def test_workspace_flow_html_contains_decision_context(self):
        import tempfile

        import web_server
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            question = store.create_research_question(
                query_text="workspace acceptance",
                intent_statement="Track workspace acceptance.",
            )
            store.save_paper_metadata(
                "2604.88888",
                {
                    "title": "Workspace Flow Paper",
                    "abstract": "A paper that proves the workspace flow renders.",
                    "authors": ["Ada"],
                },
                source="phase6-test",
            )
            store.upsert_queue_item(
                "2604.88888",
                "Inbox",
                source="phase6",
                research_question_id=question["id"],
                decision_context="Acceptance flow decision context",
            )
            import app.routes.queue as queue_routes

            original_web_store = web_server.STATE_STORE
            original_queue_store = queue_routes.STATE_STORE
            web_server.STATE_STORE = store
            queue_routes.STATE_STORE = store
            self.addCleanup(setattr, web_server, "STATE_STORE", original_web_store)
            self.addCleanup(setattr, queue_routes, "STATE_STORE", original_queue_store)

            client = web_server.app.test_client()
            queue_html = client.get("/queue?status=Inbox").get_data(as_text=True)
            detail_html = client.get(
                f"/papers/2604.88888?research_question_id={question['id']}"
            ).get_data(as_text=True)

        self.assertIn("Workspace Flow Paper", queue_html)
        self.assertIn("Acceptance flow decision context", queue_html)
        self.assertIn("Evidence", detail_html)
