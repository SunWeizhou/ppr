import sqlite3
import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class CountingProvider:
    model_name = "counting-provider"

    def __init__(self):
        self.calls = 0

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        self.calls += 1
        return {
            "one_sentence_summary": f"Summary {self.calls}: {paper.get('title', '')}",
            "problem": "problem",
            "method": "method",
            "contribution": "contribution",
            "limitations": "limitations",
            "why_it_matters": "why",
            "recommended_reading_level": "deep_read",
        }


class FailingProvider:
    model_name = "failing-provider"

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        raise RuntimeError("provider unavailable")


class AIAnalysisServiceTests(unittest.TestCase):
    def test_state_store_persists_and_canonicalizes_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            tables = sqlite3.connect(store.db_path).execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            item = store.upsert_paper_ai_analysis(
                "2604.12345v2",
                {"one_sentence_summary": "short", "recommended_reading_level": "skim"},
                model_name="test-model",
                prompt_version="v1",
            )
            loaded = store.get_paper_ai_analysis("2604.12345v9")

        self.assertIn(("paper_ai_analyses",), tables)
        self.assertEqual(item["paper_id"], "2604.12345")
        self.assertEqual(loaded["paper_id"], "2604.12345")
        self.assertEqual(loaded["one_sentence_summary"], "short")
        self.assertEqual(loaded["model_name"], "test-model")
        self.assertEqual(loaded["status"], "ok")

    def test_no_provider_fallback_returns_stable_cached_shape(self):
        from app.services.ai_analysis_service import AIAnalysisService, NoProvider

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            service = AIAnalysisService(store, provider=NoProvider())
            analysis = service.get_or_create_analysis({"id": "2604.11111v2", "title": "No provider"})
            cached = service.get_or_create_analysis({"id": "2604.11111", "title": "No provider"})

        self.assertEqual(analysis, cached)
        self.assertEqual(analysis["paper_id"], "2604.11111")
        self.assertEqual(analysis["model_name"], "none")
        self.assertEqual(analysis["prompt_version"], "v1")
        self.assertEqual(analysis["status"], "not_configured")
        self.assertEqual(analysis["recommended_reading_level"], "skim")
        for key in ["one_sentence_summary", "problem", "method", "contribution", "limitations", "why_it_matters"]:
            self.assertEqual(analysis[key], "")

    def test_fake_provider_generates_analysis(self):
        from app.services.ai_analysis_service import AIAnalysisService, FakeProvider

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            service = AIAnalysisService(store, provider=FakeProvider())
            analysis = service.get_or_create_analysis(
                {"id": "2604.22222", "title": "A useful paper", "abstract": "Abstract text"}
            )

        self.assertEqual(analysis["status"], "ok")
        self.assertEqual(analysis["model_name"], "fake-test-provider")
        self.assertIn("A useful paper", analysis["one_sentence_summary"])
        self.assertTrue(analysis["why_it_matters"])

    def test_cache_hit_avoids_provider_recall_and_force_regenerates(self):
        from app.services.ai_analysis_service import AIAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            provider = CountingProvider()
            service = AIAnalysisService(store, provider=provider)
            first = service.get_or_create_analysis({"id": "2604.33333", "title": "Cache"})
            second = service.get_or_create_analysis({"id": "2604.33333v5", "title": "Cache"})
            forced = service.get_or_create_analysis({"id": "2604.33333", "title": "Cache"}, force=True)

        self.assertEqual(provider.calls, 2)
        self.assertEqual(second["one_sentence_summary"], first["one_sentence_summary"])
        self.assertNotEqual(forced["one_sentence_summary"], first["one_sentence_summary"])

    def test_provider_failure_returns_failed_fallback(self):
        from app.services.ai_analysis_service import AIAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            service = AIAnalysisService(store, provider=FailingProvider())
            analysis = service.get_or_create_analysis({"id": "2604.44444v3", "title": "Failure"})
            cached = store.get_paper_ai_analysis("2604.44444")

        self.assertEqual(analysis["paper_id"], "2604.44444")
        self.assertEqual(analysis["status"], "failed")
        self.assertEqual(analysis["model_name"], "failing-provider")
        self.assertIn("provider unavailable", analysis["error_text"])
        self.assertEqual(cached["status"], "failed")


if __name__ == "__main__":
    unittest.main()
