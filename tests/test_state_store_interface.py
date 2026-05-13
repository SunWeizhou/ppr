"""Conformance tests: verify InMemoryStateStore matches StateStore behavior.

Both implementations satisfy StateStoreProtocol. These tests verify
that key behavioral contracts are consistent across implementations.
"""

import tempfile
import unittest
from pathlib import Path

from app.data.in_memory_state_store import InMemoryStateStore
from state_store import StateStore


def _sqlite_store():
    tmp = tempfile.TemporaryDirectory()
    store = StateStore(str(Path(tmp.name) / "state.db"))
    return store, tmp


class QueueConformanceTests:
    """Mixin-style test for queue operations — run against both backends."""

    def setUp(self):
        self._cleanup = []
        self._make_store()

    def tearDown(self):
        for obj in self._cleanup:
            if hasattr(obj, "cleanup"):
                obj.cleanup()

    def _make_store(self):
        raise NotImplementedError

    def test_upsert_and_get_queue_item(self):
        item = self.store.upsert_queue_item("2604.60001", "Inbox", source="test", note="hello")
        self.assertEqual(item["status"], "Inbox")
        self.assertEqual(item["note"], "hello")

        fetched = self.store.get_queue_item("2604.60001")
        self.assertEqual(fetched["status"], "Inbox")

    def test_upsert_updates_existing(self):
        self.store.upsert_queue_item("2604.60001", "Inbox", note="v1")
        self.store.upsert_queue_item("2604.60001", "Completed", note="v2")
        item = self.store.get_queue_item("2604.60001")
        self.assertEqual(item["status"], "Completed")
        self.assertEqual(item["note"], "v2")

    def test_list_queue_items_filters_by_status(self):
        self.store.upsert_queue_item("2604.60001", "Inbox")
        self.store.upsert_queue_item("2604.60002", "Completed")
        inbox = self.store.list_queue_items(status="Inbox")
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["paper_id"], "2604.60001")

    def test_list_queue_items_returns_all(self):
        self.store.upsert_queue_item("2604.60001", "Inbox")
        self.store.upsert_queue_item("2604.60002", "Completed")
        all_items = self.store.list_queue_items()
        self.assertEqual(len(all_items), 2)

    def test_mark_as_completed(self):
        self.store.upsert_queue_item("2604.60001", "Inbox")
        result = self.store.mark_as_completed("2604.60001")
        self.assertEqual(result["status"], "Completed")
        fetched = self.store.get_queue_item("2604.60001")
        self.assertEqual(fetched["status"], "Completed")

    def test_mark_as_completed_creates_item_when_missing(self):
        result = self.store.mark_as_completed("2604.60001")
        self.assertEqual(result["status"], "Completed")

    def test_mark_as_completed_records_event(self):
        self.store.mark_as_completed("2604.60001")
        events = self.store.list_interaction_events(paper_id="2604.60001")
        self.assertTrue(any(e["event_type"] == "queue_status_changed" for e in events))

    def test_canonical_id_handling(self):
        self.store.upsert_queue_item("2604.60001v2", "Inbox")
        item = self.store.get_queue_item("2604.60001")
        self.assertIsNotNone(item)
        item_v = self.store.get_queue_item("2604.60001v2")
        # Both should resolve to the same canonical entry
        self.assertEqual(item["paper_id"], item_v["paper_id"])

    def test_upsert_preserves_research_question_context(self):
        q = self.store.create_research_question("test query")
        self.store.upsert_queue_item("2604.60001", "Inbox", research_question_id=q["id"],
                                     decision_context="test decision")
        item = self.store.get_queue_item("2604.60001")
        self.assertEqual(item["research_question_id"], q["id"])
        self.assertEqual(item["decision_context"], "test decision")


class ResearchQuestionConformanceTests:
    def setUp(self):
        self._cleanup = []
        self._make_store()

    def tearDown(self):
        for obj in getattr(self, '_cleanup', []):
            if hasattr(obj, "cleanup"):
                obj.cleanup()

    def test_create_and_get(self):
        q = self.store.create_research_question("conformal prediction", intent_statement="deep read")
        self.assertEqual(q["query_text"], "conformal prediction")
        fetched = self.store.get_research_question(q["id"])
        self.assertEqual(fetched["query_text"], "conformal prediction")

    def test_list_filters_by_status(self):
        self.store.create_research_question("q1", status="active")
        self.store.create_research_question("q2", status="archived")
        active = self.store.list_research_questions(status="active")
        self.assertEqual(len(active), 1)

    def test_update_question(self):
        q = self.store.create_research_question("original")
        updated = self.store.update_research_question(q["id"], query_text="updated")
        self.assertEqual(updated["query_text"], "updated")


class EvidenceClaimConformanceTests:
    def setUp(self):
        self._cleanup = []
        self._make_store()

    def tearDown(self):
        for obj in getattr(self, '_cleanup', []):
            if hasattr(obj, "cleanup"):
                obj.cleanup()

    def test_create_and_list(self):
        q = self.store.create_research_question("test")
        claim = self.store.create_evidence_claim(
            paper_id="2604.60001", claim="test claim",
            research_question_id=q["id"],
        )
        self.assertEqual(claim["claim"], "test claim")
        claims = self.store.list_evidence_claims(paper_id="2604.60001")
        self.assertEqual(len(claims), 1)

    def test_delete_by_paper(self):
        self.store.create_evidence_claim(paper_id="2604.60001", claim="c1")
        self.store.create_evidence_claim(paper_id="2604.60002", claim="c2")
        deleted = self.store.delete_evidence_claims(paper_id="2604.60001")
        self.assertGreater(deleted, 0)
        remaining = self.store.list_evidence_claims()
        self.assertEqual(len(remaining), 1)


class PaperMetadataConformanceTests:
    def setUp(self):
        self._cleanup = []
        self._make_store()

    def tearDown(self):
        for obj in getattr(self, '_cleanup', []):
            if hasattr(obj, "cleanup"):
                obj.cleanup()

    def test_save_and_get(self):
        self.store.save_paper_metadata("2604.60001", {
            "title": "Test Paper",
            "abstract": "Abstract here",
            "authors": ["Alice"],
            "categories": ["cs.AI"],
        })
        meta = self.store.get_paper_metadata("2604.60001")
        self.assertEqual(meta["title"], "Test Paper")

    def test_get_nonexistent(self):
        meta = self.store.get_paper_metadata("9999.99999")
        self.assertIsNone(meta)


class EventConformanceTests:
    def setUp(self):
        self._cleanup = []
        self._make_store()

    def tearDown(self):
        for obj in getattr(self, '_cleanup', []):
            if hasattr(obj, "cleanup"):
                obj.cleanup()

    def test_record_and_list(self):
        eid = self.store.record_event("like", "2604.60001", {"source": "test"})
        self.assertIsInstance(eid, int)
        events = self.store.list_interaction_events(paper_id="2604.60001")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "like")

    def test_list_empty(self):
        events = self.store.list_interaction_events()
        self.assertEqual(len(events), 0)


# ── Concrete test classes ──


class SqliteQueueConformanceTests(QueueConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self._cleanup.append(self.tmp)


class InMemoryQueueConformanceTests(QueueConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.store = InMemoryStateStore()


class SqliteResearchQuestionConformanceTests(ResearchQuestionConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self._cleanup.append(self.tmp)


class InMemoryResearchQuestionConformanceTests(ResearchQuestionConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.store = InMemoryStateStore()


class SqliteEvidenceClaimConformanceTests(EvidenceClaimConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self._cleanup.append(self.tmp)


class InMemoryEvidenceClaimConformanceTests(EvidenceClaimConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.store = InMemoryStateStore()


class SqlitePaperMetadataConformanceTests(PaperMetadataConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self._cleanup.append(self.tmp)


class InMemoryPaperMetadataConformanceTests(PaperMetadataConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.store = InMemoryStateStore()


class SqliteEventConformanceTests(EventConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self._cleanup.append(self.tmp)


class InMemoryEventConformanceTests(EventConformanceTests, unittest.TestCase):
    def _make_store(self):
        self.store = InMemoryStateStore()


if __name__ == "__main__":
    unittest.main()
