"""Tests for Paper Detail page — canonicalization, loading, and context assembly."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from app.data._constants import canonical_paper_id as _canonical_paper_id
from state_store import StateStore


# ---------------------------------------------------------------------------
# Paper ID canonicalization
# ---------------------------------------------------------------------------


class TestPaperIdCanonicalization(unittest.TestCase):
    def test_canonicalize_strips_version(self):
        self.assertEqual(_canonical_paper_id("2604.12345v2"), "2604.12345")

    def test_canonicalize_preserves_base_id(self):
        self.assertEqual(_canonical_paper_id("2604.12345"), "2604.12345")

    def test_canonicalize_handles_empty(self):
        result = _canonical_paper_id("")
        self.assertEqual(result, "")

    def test_canonicalize_strips_multi_digit_version(self):
        self.assertEqual(_canonical_paper_id("2604.12345v10"), "2604.12345")


# ---------------------------------------------------------------------------
# PaperViewModel — SQLite, canonicalization, and context assembly
# ---------------------------------------------------------------------------


class TestPaperViewModel(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.store = StateStore(db_path=self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_recommendation_run(self, paper_id, title, abstract, authors, categories, score_details):
        import uuid
        run_id = str(uuid.uuid4())
        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                "INSERT INTO recommendation_runs(run_id, run_date, trigger_source, status, paper_count, created_at) "
                "VALUES (?, date('now'), 'test', 'completed', 1, datetime('now'))",
                (run_id,),
            )
            conn.execute(
                "INSERT INTO recommendation_items(run_id, paper_id, rank, score, score_details_json, title, authors_json, abstract, categories_json) "
                "VALUES (?, ?, 1, 4.5, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    paper_id,
                    json.dumps(score_details),
                    title,
                    json.dumps(authors),
                    abstract,
                    json.dumps(categories),
                ),
            )
        return run_id

    # ------------------------------------------------------------------
    # 1. ViewModel loads paper from SQLite
    # ------------------------------------------------------------------

    def test_viewmodel_loads_paper_from_sqlite(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Test Paper Title",
            abstract="This is a test abstract.",
            authors=["Alice Smith", "Bob Jones"],
            categories=["cs.LG", "stat.ML"],
            score_details={"relevance": 3.0, "semantic": 1.5, "affinity": 0.8},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345")

        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["id"], "2604.12345")
        self.assertEqual(ctx["paper"]["title"], "Test Paper Title")
        self.assertIn("author_text", ctx["paper"])
        self.assertIn("category_labels", ctx["paper"])
        self.assertEqual(ctx["paper"]["abstract"], "This is a test abstract.")

    # ------------------------------------------------------------------
    # 2. ViewModel canonicalizes IDs with version suffix
    # ------------------------------------------------------------------

    def test_viewmodel_canonicalizes_with_version_suffix(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Versioned Paper",
            abstract="Abstract here.",
            authors=["Author One"],
            categories=["cs.AI"],
            score_details={"relevance": 2.0},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345v2")

        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["title"], "Versioned Paper")

    # ------------------------------------------------------------------
    # 3. Paper not found returns error context (no crash)
    # ------------------------------------------------------------------

    def test_paper_not_found_returns_graceful_shell(self):
        """Paper not in any data source returns a detail shell with arXiv link
        instead of an error context."""
        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("9999.99999")

        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["id"], "9999.99999")
        self.assertIn("arXiv", str(ctx["paper"].get("abstract", "")))

    # ------------------------------------------------------------------
    # 4. Score details include affinity field
    # ------------------------------------------------------------------

    def test_score_details_affinity_in_context(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Affinity Test",
            abstract="Testing affinity in score details.",
            authors=["Author"],
            categories=["cs.LG"],
            score_details={"relevance": 2.0, "semantic": 1.0, "affinity": 0.8},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345")

        sd = ctx["paper"].get("score_details", {})
        self.assertIn("affinity", sd)
        self.assertEqual(sd["affinity"], 0.8)

    # ------------------------------------------------------------------
    # 5. Collections filter to only those containing the paper
    # ------------------------------------------------------------------

    def test_collections_only_containing_paper(self):
        paper_id = "2604.12345"
        self._seed_recommendation_run(
            paper_id=paper_id,
            title="Collection Test",
            abstract="Testing collection filtering.",
            authors=["Author"],
            categories=["cs.LG"],
            score_details={"relevance": 1.0},
        )

        import uuid
        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                "INSERT INTO research_collections(name, description, created_at, updated_at) "
                "VALUES ('Test Col', 'desc', datetime('now'), datetime('now'))"
            )
            col_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO collection_papers(collection_id, paper_id, note, added_at) "
                "VALUES (?, ?, '', datetime('now'))",
                (col_id, paper_id),
            )
            conn.execute(
                "INSERT INTO research_collections(name, description, created_at, updated_at) "
                "VALUES ('Empty Col', 'desc', datetime('now'), datetime('now'))"
            )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context(paper_id)

        collections = ctx["paper"].get("collections", [])
        # Should only include the collection that contains this paper
        col_names = [c.get("name") for c in collections]
        self.assertIn("Test Col", col_names)
        self.assertNotIn("Empty Col", col_names)

    # ------------------------------------------------------------------
    # 6. Fallback to Markdown history when SQLite has no match
    # ------------------------------------------------------------------

    def test_viewmodel_fallback_to_markdown_history(self):
        from app.viewmodels.paper_viewmodel import PaperViewModel

        with tempfile.TemporaryDirectory() as hist_dir:
            digest_path = os.path.join(hist_dir, "digest_2026-04-27.md")
            with open(digest_path, "w") as f:
                # Write content in the format expected by _parse_markdown_digest.
                # The parser splits on "\n## \d+\. " so we need a header line first.
                f.write("# Test Digest Header\n\n")
                f.write("## 1. Markdown Paper Title\n\n")
                f.write("**Authors:** Markdown Author\n\n")
                f.write("**arXiv:** [2604.99999](http://arxiv.org/abs/2604.99999)\n\n")
                f.write("**Summary:** Markdown abstract text.\n\n")
                f.write("**Score:** 3.2\n")

            # Patch the paper_viewmodel's module-level HISTORY_DIR reference
            with patch("app.viewmodels.paper_viewmodel.HISTORY_DIR", Path(hist_dir)):
                vm = PaperViewModel(self.store)
                ctx = vm.to_detail_context("2604.99999")

                self.assertNotIn("error", ctx)
                self.assertIn("Markdown Paper Title", str(ctx["paper"].get("title", "")))

    # ------------------------------------------------------------------
    # 7. Paper detail context includes Abstract, Score Breakdown, AI Analysis keys
    # ------------------------------------------------------------------

    def test_paper_detail_page_contains_key_modules(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Module Test Paper",
            abstract="Testing page modules.",
            authors=["Author Name"],
            categories=["cs.LG"],
            score_details={"relevance": 3.0, "semantic": 1.0, "author": 0.5, "depth": 1.0, "affinity": 0.8},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345")

        paper = ctx["paper"]
        self.assertTrue(paper.get("abstract") or paper.get("summary"),
                        "Paper should have abstract or summary")
        self.assertIn("score_details", paper,
                      "Paper should have score_details")
        self.assertIn("ai_analysis", paper,
                      "Paper should have ai_analysis key")


# ---------------------------------------------------------------------------
# Paper Detail Route — HTTP-level smoke test
# ---------------------------------------------------------------------------


class TestPaperDetailRoute(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.test_store = StateStore(db_path=self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_paper_detail_404_does_not_crash(self):
        """Requesting a non-existent paper should not crash and should
        return a graceful detail shell instead of error."""
        import web_server

        # The paper_detail route calls get_state_store() — patch it to use
        # our isolated test store so we don't pollute the shared singleton.
        with mock.patch("state_store.get_state_store", return_value=self.test_store):
            client = web_server.app.test_client()
            resp = client.get("/papers/9999.99999")

        self.assertEqual(resp.status_code, 200)
        data = resp.data.decode("utf-8", errors="replace").lower()
        # Should render a page (not crash) with the paper id visible
        self.assertIn("9999.99999", data)


if __name__ == "__main__":
    unittest.main()
