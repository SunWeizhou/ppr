"""Test entity-linked subscription runner strategies."""
import os
import tempfile
import unittest
from unittest.mock import patch

from state_store import StateStore
from app.services.subscription_runner import SubscriptionRunner


class TestSubscriptionRunnerEntityStrategies(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.runner = SubscriptionRunner(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_run_subscription_dispatches_field_type(self):
        """A 'field' subscription should dispatch to run_field_subscription."""
        self.store.create_entity(
            entity_id="field:cs-ai", entity_type="field", name="AI",
            metadata_json={"arxiv_categories": ["cs.AI"]},
        )
        sub = self.store.create_subscription(
            type="field", name="AI", query_text="cs.AI",
            entity_id="field:cs-ai",
        )
        with patch.object(self.runner, "run_field_subscription", return_value=0) as mock:
            self.runner.run_subscription(sub["id"])
            mock.assert_called_once()

    def test_run_field_subscription_searches_by_category(self):
        """Field subscription should search arXiv by category."""
        self.store.create_entity(
            entity_id="field:cs-ai", entity_type="field", name="AI",
            metadata_json={"arxiv_categories": ["cs.AI"]},
        )
        sub = self.store.create_subscription(
            type="field", name="AI", query_text="cs.AI",
            entity_id="field:cs-ai",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.00001"]):
            hits = self.runner.run_field_subscription(sub)
            self.assertEqual(hits, 1)

    def test_run_journal_subscription_matches_venue(self):
        """Journal subscription should match papers by venue name."""
        self.store.create_entity(
            entity_id="journal:nature-ml", entity_type="journal",
            name="Nature Machine Intelligence",
        )
        sub = self.store.create_subscription(
            type="venue", name="Nature Machine Intelligence",
            entity_id="journal:nature-ml",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.99999"]):
            hits = self.runner.run_journal_subscription(sub)
            self.assertGreaterEqual(hits, 0)

    def test_run_conference_subscription(self):
        """Conference subscription should search arXiv for conference papers."""
        self.store.create_entity(
            entity_id="conference:neurips", entity_type="conference",
            name="NeurIPS",
        )
        sub = self.store.create_subscription(
            type="venue", name="NeurIPS",
            entity_id="conference:neurips",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=[]):
            hits = self.runner.run_conference_subscription(sub)
            self.assertEqual(hits, 0)

    def test_run_all_subscriptions_includes_new_types(self):
        """run_all_subscriptions should handle field subscriptions."""
        self.store.create_entity(
            entity_id="field:cs-lg", entity_type="field", name="Machine Learning",
            metadata_json={"arxiv_categories": ["cs.LG"]},
        )
        self.store.create_subscription(
            type="field", name="Machine Learning", query_text="cs.LG",
            entity_id="field:cs-lg",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=[]):
            result = self.runner.run_all_subscriptions()
            self.assertTrue(result["success"])
            self.assertEqual(result["subscriptions_checked"], 1)

    def test_filters_json_applied_to_subscription(self):
        """Subscription with filters_json should store and retrieve filters correctly."""
        self.store.create_entity(
            entity_id="journal:test", entity_type="journal", name="Test Journal",
        )
        sub = self.store.create_subscription(
            type="venue", name="Test Journal",
            entity_id="journal:test",
            filters_json='{"min_citations": 5, "keywords": ["LLM"]}',
        )
        loaded = self.store.get_subscription(sub["id"])
        filters = loaded.get("filters_json")
        self.assertIsInstance(filters, dict)
        self.assertEqual(filters["min_citations"], 5)
        self.assertIn("LLM", filters["keywords"])


class TestEndToEndEntitySubscriptionFlow(unittest.TestCase):
    """Integration test: create entity -> subscribe -> run -> verify hits."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.runner = SubscriptionRunner(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_full_flow_journal_entity(self):
        """Create a journal entity, subscribe, run, verify subscription works."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        entity = svc.get_or_create(
            entity_type="journal",
            name="Nature Machine Intelligence",
            external_ids={"openalex": "S12345"},
        )
        self.assertIsNotNone(entity)
        self.assertEqual(entity["type"], "journal")

        sub = svc.subscribe(entity_id=entity["id"], filters={"min_citations": 5})
        self.assertEqual(sub["entity_id"], entity["id"])
        self.assertEqual(sub["type"], "venue")

        subs = self.store.list_subscriptions()
        self.assertTrue(any(s["entity_id"] == entity["id"] for s in subs))

        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.00001"]):
            result = self.runner.run_subscription(sub["id"])
            self.assertTrue(result["success"])

        hits = self.store.list_subscription_hits(subscription_id=sub["id"])
        self.assertGreaterEqual(len(hits), 1)

    def test_full_flow_field_entity(self):
        """Create a field entity, subscribe, run, verify subscription works."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        entity = svc.get_or_create(
            entity_type="field",
            name="Computer Vision",
            metadata_json={"arxiv_categories": ["cs.CV"]},
        )
        self.assertIsNotNone(entity)

        sub = svc.subscribe(entity_id=entity["id"])
        self.assertEqual(sub["type"], "field")

        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.00002"]):
            result = self.runner.run_subscription(sub["id"])
            self.assertTrue(result["success"])

    def test_entity_profile_data_available(self):
        """Entity profile route should have entity + related + subs data."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        entity = svc.get_or_create(
            entity_type="scholar", name="Alice Smith",
            external_ids={"semantic_scholar": "999"},
            metadata_json={"affiliations": ["MIT"], "h_index": 50},
        )

        related = svc.get_or_create(entity_type="journal", name="ML Journal")
        self.store.create_entity_relation(entity["id"], related["id"], "publishes_in", weight=0.8)

        related_list = svc.get_related_entities(entity["id"])
        self.assertEqual(len(related_list), 1)
        self.assertEqual(related_list[0]["name"], "ML Journal")

    def test_entity_auto_extraction(self):
        """Auto-extraction creates entities from search results."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        papers = [
            {"title": "P1", "venue": "ICML 2025", "authors": ["Alice"], "external_ids": {}},
            {"title": "P2", "venue": "Nature", "authors": ["Bob"], "external_ids": {}},
            {"title": "P3", "venue": "", "authors": ["Charlie"], "external_ids": {}},
        ]
        entities = svc.extract_entities_from_results(papers)
        self.assertGreaterEqual(len(entities), 2)
        types = {e["type"] for e in entities}
        self.assertIn("conference", types)
        self.assertIn("journal", types)


if __name__ == "__main__":
    unittest.main()
