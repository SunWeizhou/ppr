"""Watch cockpit tests for workspace-aware subscriptions and hit triage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class WatchCockpitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = StateStore(str(self.tmp_path / "test.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def _question(self, query_text: str = "conformal prediction") -> dict:
        return self.store.create_research_question(
            query_text=query_text,
            intent_statement=f"Track papers about {query_text}.",
            source="manual",
        )

    def test_subscription_persists_research_question_id(self):
        question = self._question()

        sub = self.store.create_subscription(
            "query",
            "Conformal alerts",
            "conformal prediction",
            research_question_id=question["id"],
        )

        self.assertEqual(sub["research_question_id"], question["id"])
        fetched = self.store.get_subscription(sub["id"])
        self.assertEqual(fetched["research_question_id"], question["id"])

    def test_update_subscription_can_change_research_question_id(self):
        first = self._question("conformal prediction")
        second = self._question("distribution shift")
        sub = self.store.create_subscription(
            "query",
            "Conformal alerts",
            "conformal prediction",
            research_question_id=first["id"],
        )

        updated = self.store.update_subscription(
            sub["id"],
            research_question_id=second["id"],
        )

        self.assertEqual(updated["research_question_id"], second["id"])

    def test_subscription_rejects_unknown_research_question_id(self):
        with self.assertRaises(ValueError):
            self.store.create_subscription(
                "query",
                "Broken",
                "query",
                research_question_id=999999,
            )

    def test_subscription_api_accepts_research_question_id(self):
        import web_server

        question = self._question()
        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().post(
                "/api/subscriptions",
                json={
                    "type": "query",
                    "name": "Conformal alerts",
                    "query_text": "conformal prediction",
                    "research_question_id": question["id"],
                },
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["subscription"]["research_question_id"],
            question["id"],
        )

    def test_subscription_api_updates_research_question_id(self):
        import web_server

        first = self._question("conformal prediction")
        second = self._question("distribution shift")
        sub = self.store.create_subscription(
            "query",
            "Alerts",
            "conformal prediction",
            research_question_id=first["id"],
        )
        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().put(
                f"/api/subscriptions/{sub['id']}",
                json={"research_question_id": second["id"]},
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["subscription"]["research_question_id"],
            second["id"],
        )

    def test_watch_context_enriches_subscription_with_workspace_hit_metadata(self):
        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        question = self._question()
        sub = self.store.create_subscription(
            "query",
            "Conformal alerts",
            "conformal prediction",
            research_question_id=question["id"],
        )
        self.store.save_paper_metadata(
            "2604.11111",
            {
                "title": "Conformal Prediction Under Distribution Shift",
                "abstract": "A paper about conformal prediction under shift.",
                "authors": ["Alice Chen", "Bo Li"],
                "categories": ["stat.ML"],
                "score": 8.5,
            },
            source="watch-test",
        )
        self.store.upsert_subscription_hit(
            sub["id"],
            "2604.11111v2",
            matched_reason="query",
        )
        self.store.upsert_queue_item(
            "2604.22222",
            "Inbox",
            source="test",
            research_question_id=question["id"],
            decision_context="Existing undecided candidate",
        )

        context = MonitorViewModel(self.store).to_template_context()

        decorated = context["query_subs"][0]
        self.assertEqual(decorated["research_question"]["id"], question["id"])
        self.assertEqual(
            decorated["research_question"]["query_text"],
            "conformal prediction",
        )
        self.assertEqual(decorated["workspace_stats"]["undecided_count"], 1)
        self.assertEqual(len(decorated["recent_hits"]), 1)
        hit = decorated["recent_hits"][0]
        self.assertEqual(hit["paper_id"], "2604.11111")
        self.assertEqual(
            hit["title"],
            "Conformal Prediction Under Distribution Shift",
        )
        self.assertIn(
            f"research_question_id={question['id']}",
            hit["detail_url"],
        )
        self.assertIn("source_health", decorated)
        self.assertIn("Preview", decorated["available_hit_actions"])
        self.assertIn("Send to Reading", decorated["available_hit_actions"])

    def test_watch_context_filters_fixture_subscription_and_hit_data(self):
        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        dirty = self.store.create_subscription("query", "Stable identity", "Query A")
        clean = self.store.create_subscription("query", "Federated learning alerts", "federated learning")
        self.store.save_paper_metadata(
            "fixture-paper",
            {
                "title": "Test Paper Title",
                "abstract": "Fixture abstract.",
                "authors": ["Fixture"],
            },
            source="test",
        )
        self.store.save_paper_metadata(
            "2604.55555",
            {
                "title": "Federated Optimization for Edge Devices",
                "abstract": "A real watch hit.",
                "authors": ["Ada Lovelace"],
            },
            source="watch-test",
        )
        self.store.upsert_subscription_hit(dirty["id"], "fixture-paper")
        self.store.upsert_subscription_hit(clean["id"], "2604.55555")

        context = MonitorViewModel(self.store).to_template_context()

        names = [sub["name"] for sub in context["query_subs"]]
        hit_titles = [hit["title"] for hit in context["recent_hits"]]
        self.assertNotIn("Stable identity", names)
        self.assertNotIn("Test Paper Title", hit_titles)
        self.assertIn("Federated learning alerts", names)
        self.assertIn("Federated Optimization for Edge Devices", hit_titles)

    def test_watch_recent_hits_does_not_call_live_search_when_empty(self):
        from unittest.mock import patch

        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        self.store.create_subscription(
            "query",
            "No hits yet",
            "conformal prediction",
        )

        with patch("arxiv_recommender_v5.search_by_keywords") as mock_search:
            context = MonitorViewModel(self.store).to_template_context()

        self.assertEqual(context["recent_hits"], [])
        mock_search.assert_not_called()

    def test_send_subscription_hit_to_inbox_preserves_workspace_context(self):
        from app.services.subscription_runner import SubscriptionRunner

        question = self._question()
        sub = self.store.create_subscription(
            "query",
            "Conformal alerts",
            "conformal prediction",
            research_question_id=question["id"],
        )
        hit = self.store.upsert_subscription_hit(
            sub["id"],
            "2604.33333",
            matched_reason="query: conformal prediction",
        )

        ok = SubscriptionRunner(self.store).send_hit_to_inbox(hit["id"])

        self.assertTrue(ok)
        queue = self.store.list_queue_items(status="Inbox")
        item = next(q for q in queue if q["paper_id"] == "2604.33333")
        self.assertEqual(item["source"], f"subscription:{sub['id']}")
        self.assertEqual(item["research_question_id"], question["id"])
        self.assertIn("Conformal alerts", item["decision_context"])
        self.assertIn("query: conformal prediction", item["decision_context"])

    def test_watch_template_exposes_workspace_watch_contract(self):
        template = Path("templates/watch.html").read_text(encoding="utf-8")

        self.assertIn("Create a watch from Search", template)
        self.assertIn("Ask Paper Agent to monitor a topic", template)
        self.assertIn("research_question", template)
        self.assertIn("workspace_stats", template)
        self.assertIn("source_health", template)
        self.assertIn("Preview", template)
        self.assertIn("Create collection", template)
        self.assertIn("data-hit-id", template)
        self.assertIn("sendHitToInbox", template)
        self.assertIn("ignoreSubscriptionHit", template)
        self.assertIn("detail_url", template)

    def test_subscription_js_exposes_hit_triage_functions(self):
        script = Path("static/js/subscriptions.js").read_text(encoding="utf-8")

        self.assertIn("async function sendHitToInbox", script)
        self.assertIn("/api/subscription-hits/", script)
        self.assertIn("async function ignoreSubscriptionHit", script)
        self.assertIn("sendHitToInbox: sendHitToInbox", script)
        self.assertIn("ignoreSubscriptionHit: ignoreSubscriptionHit", script)

    def test_watch_route_renders_workspace_subscription_without_network(self):
        from unittest.mock import patch

        import app.routes.watch as watch_routes
        import web_server

        question = self._question()
        sub = self.store.create_subscription(
            "query",
            "Conformal alerts",
            "conformal prediction",
            research_question_id=question["id"],
        )
        self.store.save_paper_metadata(
            "2604.44444",
            {
                "title": "A Watch Paper",
                "abstract": "A paper discovered by a subscription.",
                "authors": ["Ada Lovelace"],
            },
            source="watch-route-test",
        )
        self.store.upsert_subscription_hit(
            sub["id"],
            "2604.44444",
            matched_reason="query",
        )

        with patch(
            "app.routes.watch.get_state_store",
            return_value=self.store,
        ), patch("arxiv_recommender_v5.search_by_keywords") as mock_search:
            response = web_server.app.test_client().get("/watch")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Watch", body)
        self.assertIn("Conformal alerts", body)
        self.assertIn("A Watch Paper", body)
        self.assertIn("sendHitToInbox", body)
        mock_search.assert_not_called()

    def test_watch_hit_title_falls_back_to_recommendation_items(self):
        """Hit title enriched from recommendation_items when paper_metadata is empty."""
        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        question = self._question()
        sub = self.store.create_subscription(
            "query",
            "Test subscription",
            "test query",
            research_question_id=question["id"],
        )
        # Create a recommendation run with this paper (no paper_metadata)
        self.store.save_recommendation_run(
            "2026-05-01",
            trigger_source="test",
            papers=[
                {
                    "id": "2604.99999",
                    "title": "Title from Recommendation Run",
                    "authors": ["Author One"],
                    "abstract": "Abstract from recommendation run.",
                    "categories": ["cs.LG"],
                    "score": 7.5,
                }
            ],
        )
        self.store.upsert_subscription_hit(
            sub["id"],
            "2604.99999",
            matched_reason="query match",
        )

        context = MonitorViewModel(self.store).to_template_context()
        query_subs = [s for s in context["query_subs"] if s["id"] == sub["id"]]
        self.assertEqual(len(query_subs), 1)

        hits = query_subs[0].get("recent_hits", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["paper_id"], "2604.99999")
        # Title should come from recommendation run, not paper_id
        self.assertEqual(hits[0]["title"], "Title from Recommendation Run")

    def test_watch_hit_title_shows_arxiv_id_when_no_metadata(self):
        """When no metadata at all, hit title falls back to paper ID."""
        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        sub = self.store.create_subscription("query", "No metadata sub", "no meta")
        self.store.upsert_subscription_hit(
            sub["id"],
            "9999.88888",
            matched_reason="no metadata",
        )

        context = MonitorViewModel(self.store).to_template_context()
        query_subs = [s for s in context["query_subs"] if s["id"] == sub["id"]]
        hits = query_subs[0].get("recent_hits", [])
        self.assertGreater(len(hits), 0)
        # Title falls back to paper_id
        self.assertIn(hits[0]["title"], ("9999.88888", f"Paper 9999.88888"))

    def test_watch_template_renders_sent_hit_inbox_disabled(self):
        """Template renders disabled Inbox button for sent_to_inbox hits."""
        template = Path("templates/watch.html").read_text(encoding="utf-8")
        # The template should use hit.hit_status to disable Inbox button
        self.assertIn("sent_to_inbox", template)
        self.assertIn("disabled", template)

    def test_watch_hit_title_uses_versioned_cache_key_when_canonical_cache_empty(self):
        """When paper_cache.json has canonical key with empty title but versioned key has full data,
        Watch resolves title from the versioned entry."""
        import json
        from unittest import mock
        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        # Create a minimal paper_cache.json in the temp dir
        cache_file = self.tmp_path / "paper_cache.json"
        cache_file.write_text(json.dumps({
            "2605.05770": {"title": "", "abstract": "", "authors": []},
            "2605.05770v1": {
                "title": "Confidence is the key: conformal prediction",
                "abstract": "A paper about conformal prediction.",
                "authors": ["Laura van Weesep", "Yuyao Wang"],
            },
        }), encoding="utf-8")

        question = self._question()
        sub = self.store.create_subscription(
            "query", "Conformal alerts", "conformal",
            research_question_id=question["id"],
        )
        self.store.upsert_subscription_hit(sub["id"], "2605.05770")

        with mock.patch.object(
            MonitorViewModel, "_resolve_path", return_value=str(cache_file)
        ):
            context = MonitorViewModel(self.store).to_template_context()

        query_subs = [s for s in context["query_subs"] if s["id"] == sub["id"]]
        hits = query_subs[0].get("recent_hits", [])
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["title"], "Confidence is the key: conformal prediction")
        self.assertIn("Laura van Weesep", hits[0].get("author_text", ""))

    def test_watch_route_renders_title_not_arxiv_id_from_versioned_cache(self):
        """The rendered /watch HTML contains the paper title, not just arXiv ID."""
        import json
        from unittest import mock
        import app.routes.watch as watch_routes
        import web_server

        # Write cache file with versioned title
        cache_file = self.tmp_path / "paper_cache.json"
        cache_file.write_text(json.dumps({
            "2605.05770": {"title": "", "abstract": "", "authors": []},
            "2605.05770v1": {
                "title": "Confidence is the key: conformal prediction",
                "abstract": "A paper about conformal prediction.",
                "authors": ["Laura van Weesep"],
            },
        }), encoding="utf-8")

        from app.viewmodels.monitor_viewmodel import MonitorViewModel

        question = self._question()
        sub = self.store.create_subscription(
            "query", "Conformal alerts", "conformal",
            research_question_id=question["id"],
        )
        self.store.upsert_subscription_hit(sub["id"], "2605.05770")

        with (
            mock.patch("app.routes.watch.get_state_store", return_value=self.store),
            mock.patch.object(MonitorViewModel, "_resolve_path", return_value=str(cache_file)),
            mock.patch("arxiv_recommender_v5.search_by_keywords") as mock_search,
        ):
            response = web_server.app.test_client().get("/watch")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        # The rendered HTML must contain the title, not arXiv ID
        self.assertIn("Confidence is the key: conformal prediction", body)
        # The arXiv ID should NOT appear as the primary hit text
        self.assertIn("2605.05770", body)  # may appear in data attributes
        mock_search.assert_not_called()
