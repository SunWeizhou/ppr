"""Unit tests for digest generation services and paper utilities."""

import tempfile
import unittest
from pathlib import Path


class DigestServicesTests(unittest.TestCase):
    def test_generate_summary_extracts_first_sentences(self):
        from app.services.digest_writer import generate_summary

        abstract = "First sentence. Second sentence. Third sentence. Fourth sentence."
        summary = generate_summary(abstract, max_sentences=2)
        # Note: generate_summary joins split sentences with '. ',
        # and each original sentence ends with '.', so the result
        # naturally contains double periods.
        self.assertIn("First sentence", summary)
        self.assertIn("Second sentence", summary)
        self.assertEqual(summary.count("sentence"), 2)

    def test_generate_summary_empty_returns_default(self):
        from app.services.digest_writer import generate_summary

        self.assertEqual(generate_summary(""), "No abstract available.")

    def test_generate_summary_truncates_long_text(self):
        from app.services.digest_writer import generate_summary

        long = ". ".join(["This is a very long sentence number " + str(i) + " with extra padding to push the total length over the limit" for i in range(10)]) + "."
        summary = generate_summary(long, max_sentences=10)
        self.assertLessEqual(len(summary), 353)
        self.assertTrue(summary.endswith("..."), f"Expected '...' at end, got: {summary[-20:]}")

    def test_markdown_generator_produces_valid_output(self):
        from app.services.digest_writer import MarkdownGenerator

        papers = [
            {
                "id": "2604.12345",
                "title": "Test Paper Title",
                "authors": ["Author A", "Author B"],
                "link": "https://arxiv.org/abs/2604.12345",
                "summary": "This is a test summary.",
                "abstract": "Test abstract.",
                "score": 4.5,
                "relevance_reason": "Keyword match",
            }
        ]
        themes = ["machine learning", "deep learning"]
        date = "2026-04-26"
        md = MarkdownGenerator().generate(papers, themes, date)
        self.assertIn("Test Paper Title", md)
        self.assertIn("2604.12345", md)
        self.assertIn("machine learning", md)
        self.assertIn("deep learning", md)
        self.assertIn("4.5", md)
        self.assertIn("Daily Digest", md)
        self.assertIn("Keyword match", md)

    def test_markdown_generator_authors_et_al(self):
        from app.services.digest_writer import MarkdownGenerator

        papers = [
            {
                "id": "2604.99999",
                "title": "Many Authors Paper",
                "authors": ["A", "B", "C", "D", "E", "F"],
                "link": "https://arxiv.org/abs/2604.99999",
                "summary": "Summary.",
                "abstract": "Abstract.",
                "score": 2.0,
                "relevance_reason": "Test",
            }
        ]
        md = MarkdownGenerator().generate(papers, ["test"], "2026-04-26")
        self.assertIn("et al.", md)
        self.assertIn("A, B, C, D, E", md)

    def test_html_generator_produces_valid_output(self):
        from app.services.html_digest_service import HTMLGenerator

        papers = [
            {
                "id": "2604.12345",
                "title": "Test Paper",
                "authors": ["Author A"],
                "link": "https://arxiv.org/abs/2604.12345",
                "summary": "A test summary.",
                "abstract": "A test abstract.",
                "score": 3.0,
                "categories": ["cs.LG"],
                "relevance_reason": "Keyword match",
            }
        ]
        themes = ["test topic"]
        date = "2026-04-26"
        stats = {"total_seen": 100, "days_with_recommendations": 5}
        html = HTMLGenerator().generate(papers, themes, date, stats)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Test Paper", html)
        self.assertIn("2604.12345", html)
        self.assertIn("test topic", html)
        self.assertIn("100", html)
        self.assertIn("5", html)

    def test_html_generator_stats_in_output(self):
        from app.services.html_digest_service import HTMLGenerator

        papers = []
        html = HTMLGenerator().generate(papers, ["empty"], "2026-04-26", {})
        self.assertIn("Papers Today", html)
        self.assertIn("0", html)

    def test_parse_arxiv_identity_normalizes_urls(self):
        from app.services.paper_utils import parse_arxiv_identity

        identity = parse_arxiv_identity("https://arxiv.org/abs/2604.12345v2")
        self.assertEqual(identity["base_id"], "2604.12345")
        self.assertEqual(identity["version"], "v2")
        self.assertEqual(identity["canonical_id"], "2604.12345")

    def test_parse_arxiv_identity_handles_bare_id(self):
        from app.services.paper_utils import parse_arxiv_identity

        identity = parse_arxiv_identity("2101.00001v3")
        self.assertEqual(identity["base_id"], "2101.00001")
        self.assertEqual(identity["version"], "v3")

    def test_parse_arxiv_identity_handles_pdf_url(self):
        from app.services.paper_utils import parse_arxiv_identity

        identity = parse_arxiv_identity("https://arxiv.org/pdf/2003.12345.pdf")
        self.assertEqual(identity["base_id"], "2003.12345")
        self.assertEqual(identity["version"], "")

    def test_parse_arxiv_identity_empty_returns_raw(self):
        from app.services.paper_utils import parse_arxiv_identity

        identity = parse_arxiv_identity("")
        self.assertEqual(identity["base_id"], "")
        self.assertEqual(identity["version"], "")

    def test_download_pdfs_no_network_when_min_score_high(self):
        """min_score above paper score skips the PDF download entirely."""
        from app.services.paper_utils import download_pdfs

        with tempfile.TemporaryDirectory() as tmp:
            result = download_pdfs(
                [{"id": "fake123", "score": 5.0}],
                tmp,
                min_score=10,
            )
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)

    def test_download_pdfs_creates_cache_dir(self):
        """The function creates the cache/pdfs directory even without downloads."""
        from app.services.paper_utils import download_pdfs

        with tempfile.TemporaryDirectory() as tmp:
            download_pdfs(
                [{"id": "fake123", "score": 5.0}],
                tmp,
                min_score=10,
            )
            self.assertTrue((Path(tmp) / "cache" / "pdfs").is_dir())
