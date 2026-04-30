"""Unit tests for :mod:`app.services.recall` -- arXiv recall pipeline."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.recall import recall_candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ARXIV_NAMESPACES = (
    'xmlns="http://www.w3.org/2005/Atom" '
    'xmlns:arxiv="http://arxiv.org/schemas/atom"'
)

SAMPLE_PAPER_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<feed {ns}>
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>Test Paper One</title>
    <summary>Abstract for test paper one.</summary>
    <published>{date1}T00:00:00Z</published>
    <author><name>Alice Researcher</name></author>
    <category term="cs.LG"/>
    <category term="stat.ML"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.67890v2</id>
    <title>Test Paper Two</title>
    <summary>Abstract for test paper two.</summary>
    <published>{date2}T00:00:00Z</published>
    <author><name>Bob Scientist</name></author>
    <category term="cs.CV"/>
    <arxiv:comment>Accepted at CVPR 2024</arxiv:comment>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2403.11111v1</id>
    <title>Test Paper Three</title>
    <summary>Abstract for test paper three.</summary>
    <published>{date3}T00:00:00Z</published>
    <author><name>Carol Scholar</name></author>
    <category term="cs.AI"/>
  </entry>
</feed>
"""


class MockResponse:
    """Simulate an HTTP response with pre-set content."""

    def __init__(self, content: bytes):
        self.content = content

    def read(self):
        return self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class RecallCandidatesTests(unittest.TestCase):
    """Test suite for :func:`recall_candidates`."""

    def setUp(self):
        # Pin "now" so date filtering is deterministic.
        self.fixed_now = datetime(2024, 1, 20)
        self.today = "2024-01-20"
        self.yesterday = "2024-01-19"
        self.week_ago = "2024-01-13"

    # ------------------------------------------------------------------
    # 1. Basic fetch returns correct number of papers
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_returns_correct_count(self, mock_dt, mock_cache_cls, mock_urlopen):
        """Three entries in XML yield three paper dicts."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()
        mock_cache.is_seen.return_value = False
        mock_cache_cls.return_value = mock_cache

        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.yesterday,
            date3=self.week_ago,
        )
        mock_urlopen.return_value = MockResponse(xml.encode("utf-8"))

        results = recall_candidates(["cs.LG", "stat.ML"], lookback_days=7)

        self.assertEqual(len(results), 3)

    # ------------------------------------------------------------------
    # 2. Deduplication
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_deduplication_by_id(self, mock_dt, mock_cache_cls, mock_urlopen):
        """Two entries with same canonical ID are deduplicated."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()
        mock_cache.is_seen.return_value = False
        mock_cache_cls.return_value = mock_cache

        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.today,
            date3=self.today,
        )
        # Override IDs so two share the same canonical id: 2401.12345
        dup_xml = xml.replace(
            "2402.67890v2", "2401.12345v2"
        )
        mock_urlopen.return_value = MockResponse(dup_xml.encode("utf-8"))

        results = recall_candidates(["cs.LG"], lookback_days=7)

        # Three entries in XML, but two have same canonical ID → 2 unique
        self.assertEqual(len(results), 2)
        ids = {p["id"] for p in results}
        self.assertIn("2401.12345", ids)
        self.assertIn("2403.11111", ids)

    # ------------------------------------------------------------------
    # 3. Seen-paper filtering
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_filters_seen_papers(self, mock_dt, mock_cache_cls, mock_urlopen):
        """Papers returned as seen by PaperCache are excluded."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()

        def is_seen(pid):
            return pid in {"2402.67890"}

        mock_cache.is_seen.side_effect = is_seen
        mock_cache_cls.return_value = mock_cache

        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.today,
            date3=self.today,
        )
        mock_urlopen.return_value = MockResponse(xml.encode("utf-8"))

        results = recall_candidates(["cs.LG"], lookback_days=7)

        self.assertEqual(len(results), 2)
        self.assertNotIn("2402.67890", {p["id"] for p in results})

    # ------------------------------------------------------------------
    # 4. Date filtering
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_date_filtering(self, mock_dt, mock_cache_cls, mock_urlopen):
        """Papers outside lookback_days are excluded."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()
        mock_cache.is_seen.return_value = False
        mock_cache_cls.return_value = mock_cache

        # date1=within range, date2=within range, date3=outside range (14 days ago)
        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.yesterday,
            date3="2024-01-06",  # 14 days before fixed_now
        )
        mock_urlopen.return_value = MockResponse(xml.encode("utf-8"))

        results = recall_candidates(["cs.LG"], lookback_days=7)

        self.assertEqual(len(results), 2)
        ids = {p["id"] for p in results}
        self.assertIn("2401.12345", ids)
        self.assertIn("2402.67890", ids)

    # ------------------------------------------------------------------
    # 5. Empty categories
    # ------------------------------------------------------------------

    def test_empty_categories_returns_empty(self):
        """Empty categories list returns [] without calling arXiv."""
        results = recall_candidates([], lookback_days=7)
        self.assertEqual(results, [])

    # ------------------------------------------------------------------
    # 6. All papers seen
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_all_seen_returns_empty(self, mock_dt, mock_cache_cls, mock_urlopen):
        """When PaperCache reports all papers seen, return []."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()
        mock_cache.is_seen.return_value = True
        mock_cache_cls.return_value = mock_cache

        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.today,
            date3=self.today,
        )
        mock_urlopen.return_value = MockResponse(xml.encode("utf-8"))

        results = recall_candidates(["cs.LG"], lookback_days=7)
        self.assertEqual(results, [])

    # ------------------------------------------------------------------
    # 7. Empty response
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    def test_empty_xml_returns_empty_list(self, mock_cache_cls, mock_urlopen):
        """XML with no entries yields an empty list."""
        empty_xml = (
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"/>'
        )
        mock_urlopen.return_value = MockResponse(empty_xml.encode("utf-8"))

        results = recall_candidates(["cs.LG"], lookback_days=7)

        self.assertEqual(results, [])

    # ------------------------------------------------------------------
    # 8. Error handling
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    def test_http_error_returns_empty_list(self, mock_cache_cls, mock_urlopen):
        """When safe_urlopen raises, an empty list is returned."""
        mock_urlopen.side_effect = IOError("Connection refused")

        results = recall_candidates(["cs.LG"], lookback_days=7)

        self.assertEqual(results, [])

    # ------------------------------------------------------------------
    # 9. Paper dict structure
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_paper_dict_keys(self, mock_dt, mock_cache_cls, mock_urlopen):
        """Each returned paper dict has the expected fields."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()
        mock_cache.is_seen.return_value = False
        mock_cache_cls.return_value = mock_cache

        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.today,
            date3=self.today,
        )
        mock_urlopen.return_value = MockResponse(xml.encode("utf-8"))

        results = recall_candidates(["cs.LG"], lookback_days=7)

        paper = results[0]
        expected_keys = {
            "id", "base_id", "version", "title", "abstract",
            "authors", "published", "link", "source_url", "source",
            "categories", "comment",
        }
        self.assertEqual(set(paper.keys()), expected_keys)
        self.assertEqual(paper["id"], "2401.12345")
        self.assertEqual(paper["base_id"], "2401.12345")
        self.assertEqual(paper["version"], "v1")
        self.assertEqual(paper["source"], "arXiv")
        self.assertEqual(paper["title"], "Test Paper One")
        self.assertEqual(paper["authors"], ["Alice Researcher"])

    # ------------------------------------------------------------------
    # 10. PaperCache directory argument
    # ------------------------------------------------------------------

    @patch("app.services.recall.safe_urlopen")
    @patch("app.services.recall.PaperCache")
    @patch("app.services.recall.datetime")
    def test_papercache_created_with_cache_dir(
        self, mock_dt, mock_cache_cls, mock_urlopen
    ):
        """PaperCache is instantiated with CACHE_DIR."""
        mock_dt.now.return_value = self.fixed_now
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        mock_cache = MagicMock()
        mock_cache.is_seen.return_value = False
        mock_cache_cls.return_value = mock_cache

        xml = SAMPLE_PAPER_XML.format(
            ns=ARXIV_NAMESPACES,
            date1=self.today,
            date2=self.today,
            date3=self.today,
        )
        mock_urlopen.return_value = MockResponse(xml.encode("utf-8"))

        recall_candidates(["cs.LG"], lookback_days=7)

        mock_cache_cls.assert_called_once()
        (call_dir,) = mock_cache_cls.call_args[0]
        self.assertIn("cache", call_dir)


if __name__ == "__main__":
    unittest.main()
