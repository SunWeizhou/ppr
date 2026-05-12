"""Acceptance tests for the Paper Agent search and agent redesign."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from state_store import StateStore


class PaperAgentSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def client(self):
        import web_server

        return web_server.app.test_client()

    def test_root_renders_search_workspace_without_redirect(self):
        import app.routes.inbox as inbox_routes

        with mock.patch.object(inbox_routes, "get_state_store", return_value=self.store):
            response = self.client().get("/?skip_onboarding=1")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Paper Agent", html)
        self.assertIn("Search papers, authors, topics", html)
        self.assertIn("paper-agent-search-shell", html)
        self.assertNotIn("Ask a research question", html)
        self.assertNotIn("Explore", html)

    def test_top_navigation_uses_paper_agent_information_architecture(self):
        import web_server

        labels = [item[2] for item in web_server.NAV_ITEM_CONFIG]
        self.assertEqual(labels, ["Search", "Recommendations", "Reading", "Watch"])

    def test_search_api_returns_unified_dual_source_shape(self):
        import app.routes.api.keywords as keyword_routes

        unified_result = {
            "papers": [
                {
                    "paper_id": "arxiv:2604.12345",
                    "source": "arxiv",
                    "title": "Unified Paper",
                    "authors": ["A. Author"],
                    "year": "2026",
                    "venue": "arXiv",
                    "abstract": "Full abstract.",
                    "url": "https://arxiv.org/abs/2604.12345",
                    "pdf_url": "https://arxiv.org/pdf/2604.12345",
                    "citation_count": None,
                    "reference_count": None,
                    "external_ids": {"ArXiv": "2604.12345"},
                }
            ],
            "warnings": [],
            "errors": [],
            "sources": {"arxiv": "ok", "semantic_scholar": "ok"},
        }

        with (
            mock.patch.object(keyword_routes, "_current_state_store", return_value=self.store),
            mock.patch("app.services.unified_search_service.search_papers", return_value=unified_result),
        ):
            response = self.client().post("/api/search", json={"q": "federated learning"})

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["papers"][0]["paper_id"], "arxiv:2604.12345")
        self.assertEqual(payload["papers"][0]["source"], "arxiv")
        self.assertIn("external_ids", payload["papers"][0])
        self.assertEqual(self.store.get_paper_metadata("arxiv:2604.12345")["title"], "Unified Paper")

    def test_search_viewmodel_exposes_source_status_cards(self):
        from app.viewmodels.search_viewmodel import SearchViewModel

        context = SearchViewModel(self.store).to_template_context(
            [],
            ["federated", "learning"],
            raw_query="federated learning",
            search_sources={"arxiv": "ok", "semantic_scholar": "failed"},
            search_warnings=["Semantic Scholar is temporarily unavailable. Showing arXiv results."],
        )

        statuses = context["source_statuses"]
        self.assertEqual([item["key"] for item in statuses], ["arxiv", "semantic_scholar"])
        self.assertEqual(statuses[0]["state"], "ok")
        self.assertEqual(statuses[1]["state"], "failed")
        self.assertIn("Semantic Scholar", statuses[1]["label"])

    def test_search_template_has_preview_decision_actions_and_source_status(self):
        template = Path("templates/search_research.html").read_text(encoding="utf-8")

        self.assertIn("paperAgentSourceStatus", template)
        self.assertIn("Mark Skim", template)
        self.assertIn("Deep Read", template)
        self.assertIn("Create Watch", template)
        self.assertIn("agentQueueSelectedPaper", template)
        self.assertIn("agentCreateWatchFromSearch", template)

    def test_unified_search_deduplicates_by_doi_arxiv_and_title(self):
        from app.services.unified_search_service import merge_and_dedupe_papers

        papers = merge_and_dedupe_papers([
            {
                "paper_id": "arxiv:2604.12345",
                "source": "arxiv",
                "title": "Same Paper",
                "authors": ["A"],
                "external_ids": {"ArXiv": "2604.12345", "DOI": "10.1/example"},
                "abstract": "arxiv abstract",
            },
            {
                "paper_id": "s2:abc",
                "source": "semantic_scholar",
                "title": "Same Paper",
                "authors": ["A"],
                "external_ids": {"DOI": "10.1/example"},
                "citation_count": 12,
                "reference_count": 4,
            },
        ])

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["citation_count"], 12)
        self.assertEqual(papers[0]["reference_count"], 4)
        self.assertIn("arxiv", papers[0]["source"])
        self.assertIn("semantic_scholar", papers[0]["source"])

    def test_unified_search_degrades_when_semantic_scholar_fails(self):
        from app.services.unified_search_service import search_papers

        def fake_semantic(_query, *, max_results=25):
            raise RuntimeError("rate limited")

        result = search_papers(
            "federated learning",
            arxiv_fn=lambda _terms, **_kwargs: [{
                "id": "2604.22222",
                "title": "arXiv fallback paper",
                "abstract": "Fallback abstract.",
                "authors": ["A"],
            }],
            semantic_fn=fake_semantic,
        )

        self.assertEqual(len(result["papers"]), 1)
        self.assertEqual(result["sources"]["semantic_scholar"], "failed")
        self.assertIn("Semantic Scholar is temporarily unavailable", result["warnings"][0])

    def test_arxiv_normalization_extracts_year_from_published_field(self):
        from app.services.unified_search_service import normalize_arxiv_paper

        paper = normalize_arxiv_paper({
            "id": "2604.33333v2",
            "title": "Published Field Paper",
            "summary": "Abstract.",
            "authors": ["A"],
            "published": "2026-04-10T12:00:00Z",
        })

        self.assertEqual(paper["paper_id"], "arxiv:2604.33333")
        self.assertEqual(paper["year"], "2026")
        self.assertEqual(paper["published_at"], "2026-04-10T12:00:00Z")

    def test_paper_detail_renders_full_abstract_by_default(self):
        import app.routes.inbox as inbox_routes

        full_abstract = " ".join(f"sentence-{i}" for i in range(80))
        self.store.save_paper_metadata(
            "2604.44444",
            {
                "title": "Full Abstract Paper",
                "abstract": full_abstract,
                "authors": ["A"],
            },
            source="test",
        )
        with mock.patch.object(inbox_routes, "get_state_store", return_value=self.store):
            response = self.client().get("/papers/2604.44444")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(full_abstract, html)
        self.assertIn("Back to Search", html)

    def test_search_detail_links_preserve_query_context(self):
        template = Path("templates/search_research.html").read_text(encoding="utf-8")

        self.assertIn("paperAgentDetailUrl", template)
        self.assertIn("return_q", template)

    def test_detail_template_uses_compact_title_and_action_classes(self):
        template = Path("templates/paper_detail.html").read_text(encoding="utf-8")

        self.assertIn("paper-detail-title", template)
        self.assertIn("follow-author-action", template)
        self.assertIn("return_q", template)

    def test_mobile_css_contract_prevents_search_workspace_overflow(self):
        css = Path("static/research_ui.css").read_text(encoding="utf-8")

        self.assertIn("overflow-x: hidden", css)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn(".paper-agent-searchbar", css)
        self.assertIn("grid-column: 1 / -1", css)
        self.assertIn(".paper-preview-pane", css)
        self.assertIn("display: none", css)
        self.assertIn(".paper-agent-empty-actions", css)
        self.assertIn("grid-template-columns: 1fr", css)

    def test_agent_react_island_preserves_feedback_across_page_load(self):
        template = Path("templates/base_research.html").read_text(encoding="utf-8")
        script = Path("frontend/agent/main.tsx").read_text(encoding="utf-8")

        self.assertIn("paper-agent-root", template)
        self.assertIn("dist/agent-drawer.js", template)
        self.assertIn("ReactMarkdown", script)
        self.assertIn("rehypeSanitize", script)
        self.assertIn("paperAgentPendingEvent", script)
        self.assertIn("sessionStorage", script)
        self.assertIn("restorePaperAgentPendingEvent", script)

    def test_recommendations_page_renders_workbench(self):
        import app.routes.recommendations as recommendation_routes

        with mock.patch.object(recommendation_routes, "get_state_store", return_value=self.store):
            response = self.client().get("/recommendations")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Recommendations", html)
        self.assertIn("Run recommendations", html)
        self.assertIn("recommendations-workspace", html)

    def test_recommendations_api_creates_candidate_run(self):
        import app.routes.api.recommendations as recommendation_api

        def fake_search(query, *, max_results=20):
            return [
                {
                    "paper_id": "arxiv:2604.55555",
                    "id": "arxiv:2604.55555",
                    "title": "Recommended Paper",
                    "abstract": "A full recommendation abstract.",
                    "authors": ["Ada Lovelace"],
                    "year": "2026",
                    "venue": "arXiv",
                    "source": "arxiv",
                }
            ]

        with (
            mock.patch.object(recommendation_api, "_current_state_store", return_value=self.store),
            mock.patch(
                "app.services.recommendation_workspace_service.RecommendationWorkspaceService._search",
                side_effect=lambda query, max_results=20: fake_search(query, max_results=max_results),
            ),
        ):
            response = self.client().post(
                "/api/recommendations/runs",
                json={"mode": "for_you", "query": "federated learning"},
            )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["papers"][0]["title"], "Recommended Paper")
        self.assertEqual(self.store.get_paper_metadata("arxiv:2604.55555")["abstract"], "A full recommendation abstract.")


class PaperAgentProviderAndAgentTests(unittest.TestCase):
    def _swap_config(self, tmp_config: Path):
        import config_manager as cm_mod
        from config_manager import ConfigManager

        original_cf = cm_mod.CONFIG_FILE
        original_instance = ConfigManager._instance
        cm_mod.CONFIG_FILE = tmp_config
        ConfigManager._instance = None
        self.addCleanup(setattr, cm_mod, "CONFIG_FILE", original_cf)
        self.addCleanup(setattr, ConfigManager, "_instance", original_instance)

    def _swap_store(self, store: StateStore):
        import web_server

        original_web_store = web_server.STATE_STORE
        web_server.STATE_STORE = store
        self.addCleanup(setattr, web_server, "STATE_STORE", original_web_store)

    def client(self):
        import web_server

        return web_server.app.test_client()

    def test_openai_compatible_settings_save_and_env_provider(self):
        from app.services.ai_providers import OpenAICompatibleProvider, build_ai_provider_from_env
        from config_manager import ConfigManager, get_config

        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "user_profile.json"
            tmp_config.write_text(json.dumps({"version": 1, "keywords": {}}), encoding="utf-8")
            self._swap_config(tmp_config)

            response = self.client().post(
                "/api/settings/ai",
                json={
                    "provider": "openai_compatible",
                    "api_key": "sk-local",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                },
            )
            ConfigManager._instance = None
            ai_cfg = get_config().get_ai_config()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ai_cfg["provider"], "openai_compatible")
        with mock.patch.dict(os.environ, {"OPENAI_COMPATIBLE_API_KEY": "sk-env"}, clear=True):
            provider = build_ai_provider_from_env()
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "sk-env")

    def test_agent_api_can_save_selected_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            self._swap_store(store)
            store.save_paper_metadata(
                "2604.11111",
                {
                    "title": "Agent Paper",
                    "abstract": "Paper abstract.",
                    "authors": ["A"],
                    "external_ids": {"ArXiv": "2604.11111"},
                },
                source="test",
            )

            response = self.client().post(
                "/api/agent/messages",
                json={
                    "message": "save this paper",
                    "page_context": {
                        "selected_paper_id": "2604.11111",
                        "selected_paper_title": "Agent Paper",
                        "route": "/",
                    },
                },
            )

            payload = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["actions"][0]["type"], "queue")
            self.assertFalse(payload["requires_confirmation"])
            self.assertGreaterEqual(len(payload["tool_results"]), 1)
            self.assertEqual(payload["tool_results"][0]["status"], "succeeded")
            self.assertEqual(store.get_queue_item("2604.11111")["status"], "Saved")

    def test_agent_api_answers_general_chat_without_tool_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            self._swap_store(store)

            from app.services.ai_providers import NoProvider

            with mock.patch(
                "app.routes.api.agent.build_ai_provider_from_env",
                return_value=NoProvider(),
            ):
                response = self.client().post(
                    "/api/agent/messages",
                    json={
                        "message": "你好，你能帮我做什么？",
                        "page_context": {"route": "/watch"},
                    },
                )

            payload = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertTrue(payload["success"])
            self.assertFalse(payload["requires_confirmation"])
            self.assertEqual(payload["actions"], [])
            self.assertIn("Paper Agent", payload["reply"])
            self.assertIn("search", payload["reply"].lower())

    def test_agent_api_uses_provider_for_general_chat_when_available(self):
        class ChatProvider:
            model_name = "chat-test-model"

            def chat(self, messages, *, page_context=None):
                self.messages = messages
                self.page_context = page_context
                return "Provider chat reply"

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            self._swap_store(store)
            provider = ChatProvider()

            with mock.patch(
                "app.routes.api.agent.build_ai_provider_from_env",
                return_value=provider,
            ):
                response = self.client().post(
                    "/api/agent/messages",
                    json={
                        "message": "Help me understand this workspace",
                        "page_context": {"route": "/", "query": "federated learning"},
                    },
                )

            payload = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["reply"], "Provider chat reply")
            self.assertEqual(payload["tool_results"][0]["tool"], "chat")
            self.assertEqual(payload["tool_results"][0]["model"], "chat-test-model")

    def test_agent_api_can_create_collection_for_selected_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            self._swap_store(store)
            store.save_paper_metadata(
                "2604.22222",
                {
                    "title": "Collection Candidate",
                    "abstract": "Paper abstract.",
                    "authors": ["A"],
                },
                source="test",
            )

            response = self.client().post(
                "/api/agent/messages",
                json={
                    "message": "create collection for this paper",
                    "page_context": {
                        "selected_paper_id": "2604.22222",
                        "selected_paper_title": "Collection Candidate",
                        "query": "federated learning",
                    },
                },
            )

            payload = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["actions"][0]["type"], "collection")
            self.assertFalse(payload["requires_confirmation"])
            collection_id = payload["actions"][0]["collection_id"]
            papers = store.list_collection_papers(collection_id)
            self.assertEqual(papers[0]["paper_id"], "2604.22222")

    def test_prd_is_synced_to_paper_agent_direction(self):
        prd = Path("docs/PRD.md").read_text(encoding="utf-8")

        self.assertIn("# Paper Agent", prd)
        self.assertIn("search-first", prd)
        self.assertIn("AI Agent drawer", prd)
        self.assertIn("Current Implementation Gaps", prd)
        self.assertNotIn("Agent Literature Research Assistant", prd)

    def test_reading_and_watch_offer_explicit_back_to_search_actions(self):
        reading = Path("templates/reading.html").read_text(encoding="utf-8")
        watch = Path("templates/watch.html").read_text(encoding="utf-8")

        self.assertIn('href="/"', reading)
        self.assertIn("Back to Search", reading)
        self.assertIn('href="/"', watch)
        self.assertIn("Back to Search", watch)
