"""Unit tests for PaperViewModel — paper detail context and canonical IDs."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.data._constants import canonical_paper_id as _canonical_paper_id
from state_store import StateStore
from app.viewmodels.paper_viewmodel import PaperViewModel


class PaperViewModelTests(unittest.TestCase):
    """Tests for PaperViewModel.to_detail_context and helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = StateStore(str(self.tmp_path / "test.db"))
        self.vm = PaperViewModel(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    # ------------------------------------------------------------------
    # 1. to_detail_context graceful fallback
    # ------------------------------------------------------------------

    def test_to_detail_context_returns_shell_for_missing_paper(self):
        """A detail shell (not error) is returned when the paper is in no
        recommendation run — shows arXiv link instead of Paper not found."""
        ctx = self.vm.to_detail_context("nonexistent.12345")
        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["id"], "nonexistent.12345")
        self.assertIn("arXiv", str(ctx["paper"].get("abstract", "")))
        # Base template context fields should also be present
        self.assertIn("queue_counts", ctx)

    # ------------------------------------------------------------------
    # 2. to_detail_context happy path
    # ------------------------------------------------------------------

    def test_to_detail_context_finds_paper_from_recommendation_run(self):
        """A paper saved in a recommendation run can be looked up by detail."""
        self.store.save_recommendation_run(
            "2026-04-27",
            papers=[
                {
                    "paper_id": "2604.12345",
                    "title": "Test Paper",
                    "authors": ["Alice"],
                    "abstract": "A test paper abstract.",
                    "categories": ["cs.LG"],
                }
            ],
            themes=["theme1"],
        )
        ctx = self.vm.to_detail_context("2604.12345")
        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["title"], "Test Paper")
        self.assertIn("first_author", ctx["paper"])
        self.assertIn("category_labels", ctx["paper"])
        self.assertIn("collections", ctx["paper"])

    # ------------------------------------------------------------------
    # 3. Canonical paper ID
    # ------------------------------------------------------------------

    def test_canonical_paper_id_strips_version(self):
        """_canonical_paper_id removes the version suffix from paper IDs."""
        self.assertEqual(_canonical_paper_id("2604.12345v2"), "2604.12345")
        self.assertEqual(_canonical_paper_id("2604.12345"), "2604.12345")
        self.assertEqual(_canonical_paper_id(""), "")
        self.assertEqual(_canonical_paper_id("2604.12345v10"), "2604.12345")

    # ------------------------------------------------------------------
    # 4. Fallback to SQLite paper_metadata table
    # ------------------------------------------------------------------

    def test_fallback_to_paper_metadata_table(self):
        """PaperViewModel should find papers saved via save_paper_metadata."""
        self.store.save_paper_metadata("2604.22787", {
            "title": "Conformal Prediction Survey",
            "abstract": "A comprehensive survey of conformal prediction methods.",
            "authors": ["Author A", "Author B"],
        })
        ctx = self.vm.to_detail_context("2604.22787")
        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["title"], "Conformal Prediction Survey")

    # ------------------------------------------------------------------
    # 5. Graceful shell shows arXiv link for absolutely unknown paper
    # ------------------------------------------------------------------

    def test_graceful_shell_links_to_arxiv(self):
        """When no data source has the paper, render a detail shell
        with arXiv link in the abstract text."""
        ctx = self.vm.to_detail_context("9999.00001")
        self.assertNotIn("error", ctx)
        self.assertIn("arXiv", str(ctx["paper"].get("abstract", "")))
        self.assertEqual(ctx["paper"]["id"], "9999.00001")

    # ------------------------------------------------------------------
    # 6. Search context: store paper metadata during search so detail
    #    route can find it
    # ------------------------------------------------------------------

    def test_save_paper_metadata_during_search_makes_detail_findable(self):
        """Simulate what the search route should do: save metadata for each
        result so subsequent /papers/<id> can find it."""
        self.store.save_paper_metadata("2604.22787", {
            "title": "Conformal Prediction",
            "abstract": "Methods for conformal prediction.",
            "authors": ["Author X"],
            "categories": ["stat.ML"],
        })
        ctx = self.vm.to_detail_context("2604.22787")
        self.assertEqual(ctx["paper"]["title"], "Conformal Prediction")


if __name__ == "__main__":
    unittest.main()
