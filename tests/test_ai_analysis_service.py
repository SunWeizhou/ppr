import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_not_configured_cache_regenerates_when_provider_becomes_available(self):
        from app.services.ai_analysis_service import AIAnalysisService, FakeProvider, NoProvider

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            no_provider = AIAnalysisService(store, provider=NoProvider())
            fallback = no_provider.get_or_create_analysis({"id": "2604.55555", "title": "Later"})
            real_provider = AIAnalysisService(store, provider=FakeProvider())
            regenerated = real_provider.get_or_create_analysis({"id": "2604.55555v2", "title": "Later"})
            cached = real_provider.get_or_create_analysis({"id": "2604.55555", "title": "Later"})

        self.assertEqual(fallback["status"], "not_configured")
        self.assertEqual(regenerated["status"], "ok")
        self.assertEqual(regenerated["model_name"], "fake-test-provider")
        self.assertEqual(cached["one_sentence_summary"], regenerated["one_sentence_summary"])

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

    def test_build_ai_provider_from_env_defaults_to_no_provider(self):
        from app.services.ai_providers import NoProvider, build_ai_provider_from_env

        with mock.patch.dict("os.environ", {}, clear=True):
            provider = build_ai_provider_from_env()

        self.assertIsInstance(provider, NoProvider)

    def test_build_ai_provider_from_env_uses_deepseek_when_key_exists(self):
        from app.services.ai_providers import DeepSeekProvider, build_ai_provider_from_env

        with mock.patch.dict(
            "os.environ",
            {
                "DEEPSEEK_API_KEY": "test-api-key",
                "DEEPSEEK_BASE_URL": "https://example.test",
                "DEEPSEEK_MODEL": "custom-chat",
            },
            clear=True,
        ):
            provider = build_ai_provider_from_env()

        self.assertIsInstance(provider, DeepSeekProvider)
        self.assertEqual(provider.base_url, "https://example.test")
        self.assertEqual(provider.model_name, "custom-chat")

    def test_deepseek_provider_payload_and_json_response_fallback(self):
        from app.services.ai_providers import DeepSeekProvider, ProviderError

        calls = []

        def fake_post(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            if "response_format" in payload:
                raise ProviderError("response_format unsupported")
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"one_sentence_summary":"short","problem":"p","method":"m",'
                                '"contribution":"c","limitations":"l","why_it_matters":"w",'
                                '"recommended_reading_level":"deep read"}'
                            )
                        }
                    }
                ]
            }

        provider = DeepSeekProvider(
            api_key="test-api-key",
            base_url="https://example.test/",
            model="custom-chat",
            timeout=12,
            post_json=fake_post,
        )
        analysis = provider.analyze(
            {"title": "Paper", "authors": "Ada", "abstract": "Abstract"},
            user_profile={"keywords": ["statistics"]},
            recommendation_context={"reason": "topic"},
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "https://example.test/chat/completions")
        self.assertEqual(calls[0][1]["model"], "custom-chat")
        self.assertIn("response_format", calls[0][1])
        self.assertNotIn("response_format", calls[1][1])
        self.assertEqual(calls[0][2]["Authorization"], "Bearer test-api-key")
        self.assertIn("Title:", calls[0][1]["messages"][1]["content"])
        self.assertEqual(analysis["recommended_reading_level"], "deep_read")

    def test_deepseek_provider_malformed_json_raises_safe_error(self):
        from app.services.ai_providers import DeepSeekProvider, ProviderError

        def fake_post(url, payload, *, headers, timeout):
            return {"choices": [{"message": {"content": "not-json"}}]}

        provider = DeepSeekProvider(api_key="test-api-key", post_json=fake_post)

        with self.assertRaises(ProviderError) as context:
            provider.analyze({"title": "Bad JSON"})

        self.assertIn("malformed analysis JSON", str(context.exception))
        self.assertNotIn("test-api-key", str(context.exception))

    def test_deepseek_provider_error_is_cached_without_exposing_key(self):
        from app.services.ai_analysis_service import AIAnalysisService
        from app.services.ai_providers import DeepSeekProvider

        def fake_post(url, payload, *, headers, timeout):
            raise RuntimeError("boom test-api-key")

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            provider = DeepSeekProvider(api_key="test-api-key", post_json=fake_post)
            service = AIAnalysisService(store, provider=provider)
            analysis = service.get_or_create_analysis({"id": "2604.77777", "title": "Failure"})

        self.assertEqual(analysis["status"], "failed")
        self.assertIn("[redacted]", analysis["error_text"])
        self.assertNotIn("test-api-key", analysis["error_text"])


if __name__ == "__main__":
    unittest.main()
