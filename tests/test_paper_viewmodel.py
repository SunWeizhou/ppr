"""Unit tests for PaperViewModel — paper detail context and canonical IDs."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from state_store import StateStore, _canonical_paper_id
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
    # 1. to_detail_context error handling
    # ------------------------------------------------------------------

    def test_to_detail_context_returns_error_for_missing_paper(self):
        """Error returned when the paper is not in any recommendation run."""
        ctx = self.vm.to_detail_context("nonexistent.12345")
        self.assertIn("error", ctx)
        self.assertEqual(ctx["paper_id"], "nonexistent.12345")
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


if __name__ == "__main__":
    unittest.main()
