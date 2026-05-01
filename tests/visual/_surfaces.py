"""SURFACES — single source of truth for visual regression coverage.

Imported by both `test_ui_anchor.py` (the test suite) and
`regenerate_goldens.py` (the CLI). Kept dependency-free so the regen
script can show --help even without pytest installed.
"""

from __future__ import annotations

from typing import List, Tuple

# (test_id, url_path, viewport_dict, color_scheme)
SURFACES: List[Tuple[str, str, dict, str]] = [
    ("today-desktop-light",   "/",         {"width": 1440, "height": 900}, "light"),
    ("today-desktop-dark",    "/",         {"width": 1440, "height": 900}, "dark"),
    ("reading-desktop-dark",  "/reading",  {"width": 1440, "height": 900}, "dark"),
    ("watch-desktop-dark",    "/watch",    {"width": 1440, "height": 900}, "dark"),
    ("settings-desktop-dark", "/settings", {"width": 1440, "height": 900}, "dark"),
    # Mobile (375px) deliberately omitted: see tests/visual/README.md
    # "Why mobile (375px) is NOT a golden".
]
