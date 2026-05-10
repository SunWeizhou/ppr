"""Visual regression test fixtures.

Boots the Flask app in a subprocess on a dedicated test port,
waits for it to be reachable, and provides a Playwright `page` fixture
pre-pointed at it.

Goldens live in tests/visual/golden/. Diff artifacts are written to
tests/visual/diff/ on failure. See tests/visual/README.md.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEST_PORT_DEFAULT = 5566


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port(start: int = TEST_PORT_DEFAULT) -> int:
    """Return the first free TCP port at or after `start`."""
    port = start
    while port < start + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError(f"No free port near {start}")


def _wait_until_ready(url: str, timeout_s: float = 30.0) -> None:
    """Poll /api/status until 200 or timeout."""
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/status", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_err = e
        time.sleep(0.4)
    raise TimeoutError(f"App at {url} did not become ready in {timeout_s}s. Last error: {last_err}")


# ---------------------------------------------------------------------------
# Session-scoped app process
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app_url() -> Iterator[str]:
    """
    Boot the app on a dedicated test port for the test session.

    NOTE: Currently uses the live cache/ directory (no DB isolation).
    Goldens are tied to whatever data is in that DB at capture time. When
    data evolves, run tests/visual/regenerate_goldens.py to refresh.

    TODO: add STATDESK_STATE_DIR env var to app_paths.py so tests can
    point at a frozen snapshot.
    """
    if reuse := os.getenv("STATDESK_TEST_URL"):
        yield reuse.rstrip("/")
        return

    port = _free_port()
    env = {**os.environ, "FLASK_RUN_PORT": str(port)}
    env.setdefault("PYTHONUNBUFFERED", "1")

    proc = subprocess.Popen(
        [sys.executable, "web_server.py"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_until_ready(base)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# Per-page setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Override pytest-playwright defaults: ignore HTTPS, fixed locale,
    fonts ready before screenshots.
    """
    return {
        **browser_context_args,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }


def stabilize(page) -> None:
    """
    Mute non-determinism before screenshot:
    - kill animations / transitions
    - wait for network idle
    - wait for fonts to be ready
    - hide caret blink
    """
    page.add_style_tag(content="""
        *, *::before, *::after {
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition-duration: 0s !important;
            transition-delay: 0s !important;
            caret-color: transparent !important;
        }
    """)
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
