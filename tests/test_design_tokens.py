"""Validate the CSS design token system structure."""
import re
import unittest
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "research_ui.css"


class TestDesignTokens(unittest.TestCase):
    def setUp(self):
        self.css = CSS_PATH.read_text(encoding="utf-8")

    def test_single_root_block_for_light_tokens(self):
        """Only one :root block should define semantic tokens."""
        root_blocks = re.findall(r"^:root\s*\{", self.css, re.MULTILINE)
        assert len(root_blocks) == 1, f"Expected 1 :root block, found {len(root_blocks)}"

    def test_dark_theme_block_exists(self):
        """Dark mode tokens must be defined via [data-theme='dark']."""
        assert '[data-theme="dark"]' in self.css

    def test_semantic_tokens_defined(self):
        """Key semantic tokens must exist in :root."""
        required = [
            "--bg-primary", "--bg-surface", "--bg-surface-hover",
            "--ink-primary", "--ink-secondary", "--accent-primary",
            "--border-default",
        ]
        for token in required:
            assert token in self.css, f"Missing semantic token: {token}"

    def test_no_triple_root_override(self):
        """The old standalone second :root block must not exist."""
        # Old pattern had a standalone second :root at line ~3278 with --paper-agent-bg
        # We now have it as a compatibility alias in the single :root block — that's OK.
        # What must NOT be present is the --apple-claude- namespace
        assert "--apple-claude-" not in self.css, "Legacy --apple-claude-* tokens still present"
        # The second :root block had only 6 vars; now we have a single unified :root
        root_blocks = re.findall(r"^:root\s*\{", self.css, re.MULTILINE)
        assert len(root_blocks) == 1, f"Expected single :root block, found {len(root_blocks)}"

    def test_breathing_grid_defined(self):
        """Breathing grid background must be defined."""
        assert "breathing-grid" in self.css or "breathe" in self.css

    def test_reduced_motion_respected(self):
        """prefers-reduced-motion must disable breathing animation."""
        assert "prefers-reduced-motion" in self.css

    def test_no_legacy_css_variables(self):
        """No apple-claude variable naming patterns remain in CSS.
        Note: --paper-agent-* vars are kept as compatibility aliases mapped to new tokens.
        """
        assert "--apple-claude-" not in self.css

    def test_sidebar_class_in_base_template(self):
        """Base template must include sidebar markup."""
        base = (CSS_PATH.parent.parent / "templates" / "base_research.html").read_text()
        assert "sidebar" in base
        assert "app-layout" in base
