"""Test OpenAlex API integration and paper normalization."""
import unittest
from unittest.mock import patch

from app.services.unified_search_service import (
    normalize_openalex_paper,
    search_openalex,
    merge_and_dedupe_papers,
)


class TestNormalizeOpenAlexPaper(unittest.TestCase):
    def test_basic_normalization(self):
        raw = {
            "id": "https://openalex.org/W12345",
            "title": "A Survey on Federated Learning",
            "authorships": [
                {"author": {"display_name": "Alice Smith", "id": "https://openalex.org/A111"}},
                {"author": {"display_name": "Bob Jones", "id": "https://openalex.org/A222"}},
            ],
            "publication_year": 2025,
            "primary_location": {
                "source": {"display_name": "Nature ML", "type": "journal"}
            },
            "abstract_inverted_index": None,
            "cited_by_count": 42,
            "referenced_works_count": 15,
            "doi": "https://doi.org/10.1234/test",
            "ids": {"openalex": "https://openalex.org/W12345"},
        }
        result = normalize_openalex_paper(raw)
        self.assertEqual(result["paper_id"], "openalex:W12345")
        self.assertEqual(result["source"], "openalex")
        self.assertEqual(result["title"], "A Survey on Federated Learning")
        self.assertEqual(result["authors"], ["Alice Smith", "Bob Jones"])
        self.assertEqual(result["year"], 2025)
        self.assertEqual(result["venue"], "Nature ML")
        self.assertEqual(result["citation_count"], 42)
        self.assertEqual(result["reference_count"], 15)
        self.assertIn("10.1234/test", result["external_ids"].get("doi", ""))

    def test_missing_fields_graceful(self):
        raw = {"id": "https://openalex.org/W999", "title": "Minimal Paper"}
        result = normalize_openalex_paper(raw)
        self.assertEqual(result["paper_id"], "openalex:W999")
        self.assertEqual(result["authors"], [])
        self.assertIsNone(result["year"])
        self.assertEqual(result["venue"], "")


class TestSearchOpenAlex(unittest.TestCase):
    @patch("app.services.unified_search_service._openalex_request")
    def test_returns_normalized_papers(self, mock_req):
        mock_req.return_value = {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "Test Paper",
                    "authorships": [],
                    "publication_year": 2025,
                    "cited_by_count": 10,
                }
            ]
        }
        papers = search_openalex("test", max_results=5)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["source"], "openalex")

    @patch("app.services.unified_search_service._openalex_request")
    def test_raises_on_error(self, mock_req):
        mock_req.side_effect = Exception("network error")
        with self.assertRaises(RuntimeError):
            search_openalex("test", max_results=5)


class TestDeduplicationWithOpenAlex(unittest.TestCase):
    def test_openalex_deduped_by_doi(self):
        arxiv_paper = {
            "paper_id": "arxiv:2401.12345",
            "source": "arxiv",
            "title": "Same Paper",
            "external_ids": {"doi": "10.1234/test"},
            "authors": ["Alice"],
        }
        openalex_paper = {
            "paper_id": "openalex:W1",
            "source": "openalex",
            "title": "Same Paper",
            "external_ids": {"doi": "10.1234/test"},
            "authors": ["Alice"],
            "citation_count": 42,
        }
        merged = merge_and_dedupe_papers([arxiv_paper, openalex_paper])
        self.assertEqual(len(merged), 1)
        # Should merge sources
        self.assertIn("arxiv", merged[0]["source"])
        self.assertIn("openalex", merged[0]["source"])


if __name__ == "__main__":
    unittest.main()
