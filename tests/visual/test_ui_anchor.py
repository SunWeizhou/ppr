"""Visual regression tests anchored to committed golden screenshots.

Each test renders one (route, viewport, color_scheme) combination, screenshots
it, and compares pixel-by-pixel to the golden in tests/visual/golden/.

When a test fails:
  - actual screenshot      → tests/visual/diff/<name>-actual.png
  - golden                 → tests/visual/diff/<name>-golden.png
  - diff visualization     → tests/visual/diff/<name>-diff.png

To regenerate goldens (when an intentional UI change ships):
  python tests/visual/regenerate_goldens.py [--name <pattern>]

NOTE: tests are skipped automatically if Playwright or Pillow aren't
installed. Install with:
  pip install -r requirements-test.txt
  python -m playwright install chromium
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Tuple

import pytest

# pytest-playwright provides `page`, `context`, `browser` fixtures
playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="install with `pip install -r requirements-test.txt && playwright install chromium`",
)
PIL = pytest.importorskip("PIL", reason="install Pillow via requirements-test.txt")
from PIL import Image, ImageChops  # noqa: E402

from .conftest import stabilize  # noqa: E402
from ._surfaces import SURFACES  # noqa: E402

VISUAL_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = VISUAL_DIR / "golden"
DIFF_DIR = VISUAL_DIR / "diff"

# Threshold: fraction of pixels allowed to differ before the test fails.
# 1% is a balance — tighter trips on font antialiasing differences across
# OS / Chromium minor versions; looser misses real layout regressions.
DIFF_THRESHOLD = float(os.getenv("STATDESK_VISUAL_THRESHOLD", "0.01"))


def pixel_diff_ratio(a: Image.Image, b: Image.Image) -> float:
    """Return fraction (0..1) of pixels that differ."""
    if a.size != b.size:
        # Resize check is intentional — mismatched sizes are an immediate fail.
        return 1.0
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    bbox = diff.getbbox()
    if not bbox:
        return 0.0
    # Count non-zero pixels in the difference image
    pixels = diff.getdata()
    differing = sum(1 for p in pixels if p != (0, 0, 0))
    return differing / (a.size[0] * a.size[1])


@pytest.fixture(scope="session", autouse=True)
def _ensure_diff_dir():
    DIFF_DIR.mkdir(parents=True, exist_ok=True)


@pytest.mark.parametrize(
    "test_id,url,viewport,scheme",
    SURFACES,
    ids=[s[0] for s in SURFACES],
)
def test_visual_anchor(test_id, url, viewport, scheme, app_url, browser):
    golden_path = GOLDEN_DIR / f"{test_id}.png"
    if not golden_path.exists():
        pytest.skip(
            f"No golden at {golden_path}. "
            f"Run `python tests/visual/regenerate_goldens.py --name {test_id}` first."
        )

    ctx = browser.new_context(viewport=viewport, color_scheme=scheme, locale="zh-CN")
    page = ctx.new_page()
    try:
        page.goto(f"{app_url}{url}")
        stabilize(page)
        actual_bytes = page.screenshot(full_page=False)
    finally:
        ctx.close()

    actual = Image.open(io.BytesIO(actual_bytes))
    golden = Image.open(golden_path)

    ratio = pixel_diff_ratio(actual, golden)
    if ratio > DIFF_THRESHOLD:
        actual.save(DIFF_DIR / f"{test_id}-actual.png")
        golden.save(DIFF_DIR / f"{test_id}-golden.png")
        try:
            diff_img = ImageChops.difference(actual.convert("RGB"), golden.convert("RGB"))
            # Amplify diff for human readability
            diff_img = diff_img.point(lambda x: min(255, x * 4))
            diff_img.save(DIFF_DIR / f"{test_id}-diff.png")
        except Exception:
            pass
        pytest.fail(
            f"{test_id}: {ratio:.2%} of pixels differ from golden "
            f"(threshold {DIFF_THRESHOLD:.0%}). Diff written to tests/visual/diff/."
        )
