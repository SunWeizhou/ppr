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
