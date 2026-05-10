"""Phase 6 product acceptance tests.

These tests guard the finished workspace-first product experience without
requiring live arXiv, live AI providers, Zotero, or browser goldens.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ACTIVE_COPY_FILES = [
    Path("app/viewmodels/search_viewmodel.py"),
    Path("app/viewmodels/queue_viewmodel.py"),
    Path("app/viewmodels/monitor_viewmodel.py"),
    Path("app/viewmodels/paper_viewmodel.py"),
    Path("app/viewmodels/eval_viewmodel.py"),
    Path("templates/onboarding.html"),
    Path("templates/queue_research.html"),
    Path("templates/generating.html"),
    Path("static/js/core.js"),
    Path("static/research_ui.js"),
    Path("static/js/modals.js"),
    Path("static/js/subscriptions.js"),
]


class Phase6ProductAcceptanceTests(unittest.TestCase):
    def test_active_surfaces_use_current_product_name(self):
        for path in ACTIVE_COPY_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "arXiv Recommender",
                text,
                msg=f"stale product name in {path}",
            )

    def test_active_surfaces_do_not_use_stale_monitor_or_library_labels(self):
        guarded_files = [
            Path("templates/onboarding.html"),
            Path("templates/queue_research.html"),
            Path("static/js/core.js"),
            Path("static/research_ui.js"),
            Path("static/js/subscriptions.js"),
        ]
        forbidden = [
            "Monitor subscription",
            "Monitor 中",
            "nav.monitor",
            "nav.library",
            "View Saved in Library",
            "Save to Library",
        ]
        for path in guarded_files:
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, text, msg=f"{needle!r} in {path}")

    def test_today_generation_copy_uses_inbox_language(self):
        files = [
            Path("templates/generating.html"),
            Path("static/js/modals.js"),
            Path("static/research_ui.js"),
        ]
        forbidden = ["刷新今日推荐", "今日推荐", "重新生成推荐"]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, text, msg=f"{needle!r} in {path}")
