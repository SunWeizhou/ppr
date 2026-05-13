"""Tests for user_profile table CRUD and auto-update logic."""

import json
import os
import tempfile
import unittest

def _make_store():
    """Create a StateStore with a temporary database."""
    from state_store import StateStore

    tmp = tempfile.mktemp(suffix=".db")
    store = StateStore(tmp)
    return store, tmp


class TestUserProfileCRUD(unittest.TestCase):
    def test_get_profile_returns_default_when_empty(self):
        store, tmp = _make_store()
        try:
            profile = store.get_user_profile()
            self.assertIsNotNone(profile)
            self.assertEqual(profile["interest_vector"], [])
            self.assertEqual(profile["topic_weights"], {})
            self.assertEqual(profile["entity_affinities"], {})
            self.assertEqual(profile["reading_pace"], {})
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_upsert_and_retrieve_profile(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                interest_vector=["deep learning", "NLP"],
                topic_weights={"deep learning": 2.0, "NLP": 1.5},
            )
            profile = store.get_user_profile()
            self.assertEqual(profile["interest_vector"], ["deep learning", "NLP"])
            self.assertEqual(profile["topic_weights"]["NLP"], 1.5)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_upsert_merges_partial_update(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(interest_vector=["ML"])
            store.upsert_user_profile(topic_weights={"ML": 1.0})
            profile = store.get_user_profile()
            # interest_vector should be preserved from first call
            self.assertEqual(profile["interest_vector"], ["ML"])
            self.assertEqual(profile["topic_weights"]["ML"], 1.0)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_entity_affinities(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                entity_affinities={"journal:nature": 0.9, "scholar:hinton": 0.8},
            )
            profile = store.get_user_profile()
            self.assertEqual(profile["entity_affinities"]["journal:nature"], 0.9)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_reading_pace(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                reading_pace={"avg_papers_per_week": 5, "preferred_depth": "skim"},
            )
            profile = store.get_user_profile()
            self.assertEqual(profile["reading_pace"]["avg_papers_per_week"], 5)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class TestUserProfileAutoUpdate(unittest.TestCase):
    def test_update_from_reading_behavior(self):
        store, tmp = _make_store()
        try:
            # Add some reading queue items with known topics
            store.upsert_queue_item("paper1", "Inbox", source="test")
            store.save_paper_metadata("paper1", {
                "title": "Transformers for NLP",
                "categories": ["cs.CL", "cs.LG"],
            })
            # The update_profile_from_behavior method should extract topics
            store.update_profile_from_behavior()
            profile = store.get_user_profile()
            # Profile should now have non-empty interest_vector
            self.assertIsInstance(profile["interest_vector"], list)
            self.assertGreater(len(profile["interest_vector"]), 0)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

class TestProfileIntegrationWithEngine(unittest.TestCase):
    def test_profile_feeds_into_engine(self):
        from app.services.recommendation_engine import RecommendationEngine
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                interest_vector=["machine learning", "optimization"],
                topic_weights={"machine learning": 2.0, "optimization": 1.5},
            )
            profile = store.get_user_profile()

            engine = RecommendationEngine()
            papers = [
                {"paper_id": "1", "title": "Machine Learning Optimization Methods", "abstract": "SGD and Adam", "authors": [], "citation_count": 10, "year": "2026"},
            ]
            result = engine.recommend(papers=papers, user_profile=profile)
            self.assertGreater(len(result["sections"]), 0)
            # ForYou section should match on "machine learning"
            for_you = [s for s in result["sections"] if s["strategy"] == "for_you"]
            self.assertEqual(len(for_you), 1)
            self.assertGreater(for_you[0]["candidates"][0].score, 0)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
