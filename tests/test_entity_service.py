"""Test entity system schema, CRUD operations, and EntityService."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from state_store import StateStore


class TestEntitySchema(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_entities_table_exists(self):
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
            ).fetchone()
        self.assertIsNotNone(row, "entities table must exist")

    def test_entity_relations_table_exists(self):
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entity_relations'"
            ).fetchone()
        self.assertIsNotNone(row, "entity_relations table must exist")

    def test_user_profile_table_exists(self):
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile'"
            ).fetchone()
        self.assertIsNotNone(row, "user_profile table must exist")

    def test_subscriptions_has_entity_id_column(self):
        with self.store._connect() as conn:
            rows = conn.execute("PRAGMA table_info(subscriptions)").fetchall()
            column_names = {row["name"] for row in rows}
        self.assertIn("entity_id", column_names)

    def test_subscriptions_has_filters_json_column(self):
        with self.store._connect() as conn:
            rows = conn.execute("PRAGMA table_info(subscriptions)").fetchall()
            column_names = {row["name"] for row in rows}
        self.assertIn("filters_json", column_names)

    def test_subscriptions_type_check_includes_field_and_entity(self):
        """The subscriptions type CHECK should accept 'field' and 'entity'."""
        with self.store._connect() as conn:
            conn.execute(
                """INSERT INTO subscriptions(type, name, query_text, created_at, updated_at)
                   VALUES ('field', 'test-field', 'cs.AI', datetime('now'), datetime('now'))"""
            )
            conn.execute(
                """INSERT INTO subscriptions(type, name, query_text, created_at, updated_at)
                   VALUES ('entity', 'test-entity', '', datetime('now'), datetime('now'))"""
            )


class TestEntityCRUD(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_journal_entity(self):
        entity = self.store.create_entity(
            entity_id="journal:nature_ml",
            entity_type="journal",
            name="Nature Machine Intelligence",
            external_ids={"openalex": "S12345"},
            metadata_json={
                "publisher": "Nature Publishing Group",
                "issn": "2522-5839",
                "impact_factor": 25.9,
                "h_index": 89,
            },
        )
        self.assertEqual(entity["id"], "journal:nature_ml")
        self.assertEqual(entity["type"], "journal")
        self.assertEqual(entity["name"], "Nature Machine Intelligence")
        self.assertEqual(entity["metadata_json"]["publisher"], "Nature Publishing Group")

    def test_create_scholar_entity(self):
        entity = self.store.create_entity(
            entity_id="scholar:s2:12345",
            entity_type="scholar",
            name="Yann LeCun",
            aliases=["Y. LeCun", "Yann Le Cun"],
            metadata_json={
                "affiliations": ["Meta AI", "NYU"],
                "h_index": 178,
                "citation_count": 430000,
            },
        )
        self.assertEqual(entity["type"], "scholar")
        self.assertIn("Y. LeCun", entity["aliases"])
        self.assertEqual(entity["metadata_json"]["h_index"], 178)

    def test_create_conference_entity(self):
        entity = self.store.create_entity(
            entity_id="conference:neurips",
            entity_type="conference",
            name="NeurIPS",
            metadata_json={"tier": "A*", "acceptance_rate": 0.25},
        )
        self.assertEqual(entity["type"], "conference")
        self.assertEqual(entity["metadata_json"]["tier"], "A*")

    def test_create_field_entity(self):
        entity = self.store.create_entity(
            entity_id="field:cs.AI",
            entity_type="field",
            name="Artificial Intelligence",
            metadata_json={"arxiv_categories": ["cs.AI"]},
        )
        self.assertEqual(entity["type"], "field")
        self.assertIn("cs.AI", entity["metadata_json"]["arxiv_categories"])

    def test_create_entity_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity(entity_id="bad:1", entity_type="unknown", name="Bad")

    def test_create_entity_missing_id_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity(entity_id="", entity_type="journal", name="No ID")

    def test_create_entity_missing_name_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity(entity_id="journal:x", entity_type="journal", name="")

    def test_get_entity(self):
        self.store.create_entity(entity_id="journal:test", entity_type="journal", name="Test Journal")
        entity = self.store.get_entity("journal:test")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["name"], "Test Journal")

    def test_get_entity_not_found(self):
        self.assertIsNone(self.store.get_entity("nonexistent"))

    def test_list_entities_by_type(self):
        self.store.create_entity(entity_id="journal:a", entity_type="journal", name="Journal A")
        self.store.create_entity(entity_id="scholar:b", entity_type="scholar", name="Scholar B")
        journals = self.store.list_entities(entity_type="journal")
        self.assertEqual(len(journals), 1)
        self.assertEqual(journals[0]["name"], "Journal A")

    def test_list_entities_search(self):
        self.store.create_entity(entity_id="journal:ml", entity_type="journal", name="Machine Learning Journal")
        self.store.create_entity(entity_id="journal:cv", entity_type="journal", name="Computer Vision Quarterly")
        results = self.store.list_entities(search="Machine")
        self.assertEqual(len(results), 1)

    def test_update_entity(self):
        self.store.create_entity(entity_id="journal:test", entity_type="journal", name="Old Name")
        updated = self.store.update_entity("journal:test", name="New Name")
        self.assertEqual(updated["name"], "New Name")

    def test_delete_entity(self):
        self.store.create_entity(entity_id="journal:del", entity_type="journal", name="Delete Me")
        self.assertTrue(self.store.delete_entity("journal:del"))
        self.assertIsNone(self.store.get_entity("journal:del"))

    def test_delete_entity_not_found(self):
        self.assertFalse(self.store.delete_entity("nonexistent"))

    def test_upsert_entity_updates_existing(self):
        self.store.create_entity(
            entity_id="journal:upsert", entity_type="journal", name="V1",
            metadata_json={"impact_factor": 10.0},
        )
        updated = self.store.create_entity(
            entity_id="journal:upsert", entity_type="journal", name="V2",
            metadata_json={"impact_factor": 12.0},
        )
        self.assertEqual(updated["name"], "V2")
        self.assertEqual(updated["metadata_json"]["impact_factor"], 12.0)


class TestEntityRelations(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.store.create_entity(entity_id="scholar:alice", entity_type="scholar", name="Alice")
        self.store.create_entity(entity_id="journal:ml", entity_type="journal", name="ML Journal")

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_relation(self):
        rel = self.store.create_entity_relation("scholar:alice", "journal:ml", "publishes_in", weight=0.9)
        self.assertEqual(rel["source_id"], "scholar:alice")
        self.assertEqual(rel["target_id"], "journal:ml")
        self.assertEqual(rel["relation_type"], "publishes_in")
        self.assertAlmostEqual(rel["weight"], 0.9)

    def test_invalid_relation_type_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity_relation("scholar:alice", "journal:ml", "invalid_type")

    def test_list_relations(self):
        self.store.create_entity_relation("scholar:alice", "journal:ml", "publishes_in")
        relations = self.store.list_entity_relations("scholar:alice")
        self.assertEqual(len(relations), 1)

    def test_list_relations_direction_filter(self):
        self.store.create_entity_relation("scholar:alice", "journal:ml", "publishes_in")
        outgoing = self.store.list_entity_relations("scholar:alice", direction="outgoing")
        incoming = self.store.list_entity_relations("scholar:alice", direction="incoming")
        self.assertEqual(len(outgoing), 1)
        self.assertEqual(len(incoming), 0)

    def test_upsert_relation_updates_weight(self):
        self.store.create_entity_relation("scholar:alice", "journal:ml", "publishes_in", weight=0.5)
        self.store.create_entity_relation("scholar:alice", "journal:ml", "publishes_in", weight=0.9)
        relations = self.store.list_entity_relations("scholar:alice")
        self.assertEqual(len(relations), 1)
        self.assertAlmostEqual(relations[0]["weight"], 0.9)


from app.services.entity_service import EntityService


class TestEntityService(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.svc = EntityService(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_get_or_create_journal(self):
        entity = self.svc.get_or_create(
            entity_type="journal",
            name="Nature Machine Intelligence",
            external_ids={"openalex": "S12345"},
        )
        self.assertTrue(entity["id"].startswith("journal:"))
        self.assertEqual(entity["type"], "journal")
        self.assertEqual(entity["name"], "Nature Machine Intelligence")

    def test_get_or_create_returns_existing(self):
        e1 = self.svc.get_or_create(entity_type="journal", name="ML Journal", external_ids={"openalex": "S999"})
        e2 = self.svc.get_or_create(entity_type="journal", name="ML Journal", external_ids={"openalex": "S999"})
        self.assertEqual(e1["id"], e2["id"])

    def test_generate_entity_id_journal(self):
        eid = EntityService._generate_entity_id("journal", "Nature ML", {"openalex": "S123"})
        self.assertEqual(eid, "journal:openalex:S123")

    def test_generate_entity_id_scholar_with_s2(self):
        eid = EntityService._generate_entity_id("scholar", "Alice Smith", {"semantic_scholar": "12345"})
        self.assertEqual(eid, "scholar:s2:12345")

    def test_generate_entity_id_fallback_to_slug(self):
        eid = EntityService._generate_entity_id("field", "Deep Learning", {})
        self.assertEqual(eid, "field:deep-learning")

    @patch("app.services.entity_service.EntityService._fetch_openalex_source")
    def test_sync_metadata_journal(self, mock_fetch):
        mock_fetch.return_value = {"publisher": "Springer", "issn": "1234-5678", "impact_factor": None}
        entity = self.svc.get_or_create(entity_type="journal", name="Test Journal", external_ids={"openalex": "S999"})
        updated = self.svc.sync_metadata(entity["id"])
        self.assertIsNotNone(updated)
        mock_fetch.assert_called_once()

    def test_list_by_type(self):
        self.svc.get_or_create(entity_type="journal", name="J1")
        self.svc.get_or_create(entity_type="scholar", name="S1")
        journals = self.svc.list_by_type("journal")
        self.assertEqual(len(journals), 1)

    def test_subscribe_to_entity(self):
        entity = self.svc.get_or_create(entity_type="journal", name="Nature ML")
        sub = self.svc.subscribe(entity_id=entity["id"], filters={"min_citations": 5})
        self.assertEqual(sub["entity_id"], entity["id"])
        self.assertEqual(sub["type"], "venue")
        self.assertEqual(sub["name"], "Nature ML")


class TestEntityAutoExtraction(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.svc = EntityService(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_extract_entities_from_search_results(self):
        papers = [
            {"title": "Test Paper 1", "venue": "Nature Machine Intelligence",
             "authors": ["Alice Smith"], "external_ids": {"openalex": "W1"}},
            {"title": "Test Paper 2", "venue": "NeurIPS 2025",
             "authors": ["Bob Jones"], "external_ids": {}},
        ]
        entities = self.svc.extract_entities_from_results(papers)
        venue_names = [e["name"] for e in entities if e["type"] in ("journal", "conference")]
        self.assertIn("Nature Machine Intelligence", venue_names)


if __name__ == "__main__":
    unittest.main()
