#!/usr/bin/env python3
"""Regenerate visual regression goldens.

Boots the app, screenshots every surface in SURFACES, and writes the PNG
to tests/visual/golden/<test_id>.png.

Recommended workflow:
  1. Decide which baseline you want goldens for.
     - For an approved baseline commit: git checkout <commit>
     - For latest main:                git checkout main
  2. Make sure the app's cache/ has the data you want frozen as the baseline.
  3. Run this script.
  4. Inspect the generated goldens, then `git add tests/visual/golden/` and commit.

Usage:
  python tests/visual/regenerate_goldens.py            # all surfaces
  python tests/visual/regenerate_goldens.py --name today  # surfaces matching pattern
  python tests/visual/regenerate_goldens.py --port 5566   # custom port
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.visual._surfaces import SURFACES  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def free_port(start: int = 5566) -> int:
    port = start
    while port < start + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free port available")


def wait_ready(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/status", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.4)
    raise TimeoutError(f"App at {url} not ready after {timeout_s}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", help="Only regenerate surfaces whose test_id contains this string")
    parser.add_argument("--port", type=int, default=0, help="App port (default: auto-pick)")
    parser.add_argument("--reuse", help="Use a running app at this URL instead of spawning")
    args = parser.parse_args()

    targets = [s for s in SURFACES if not args.name or args.name in s[0]]
    if not targets:
        print(f"No surfaces match --name {args.name!r}. Available:")
        for s in SURFACES:
            print(f"  {s[0]}")
        return 1

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    proc = None
    try:
        if args.reuse:
            base = args.reuse.rstrip("/")
            print(f"Reusing app at {base}")
        else:
            port = args.port or free_port()
            env = {"FLASK_RUN_PORT": str(port), "PYTHONUNBUFFERED": "1"}
            import os
            env = {**os.environ, **env}
            proc = subprocess.Popen(
                [sys.executable, "web_server.py"],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            base = f"http://127.0.0.1:{port}"
            print(f"Booting app at {base} ...")
            wait_ready(base)
            print("Ready.")

        # Lazy import — keeps the script importable even if Playwright missing
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("ERROR: playwright not installed. Run:")
            print("  pip install -r requirements-test.txt && playwright install chromium")
            return 2

        with sync_playwright() as p:
            browser = p.chromium.launch()
            for test_id, url, viewport, scheme in targets:
                ctx = browser.new_context(viewport=viewport, color_scheme=scheme, locale="zh-CN")
                page = ctx.new_page()
                page.goto(f"{base}{url}")
                # inline minimum stabilize (avoid circular import via conftest)
                page.add_style_tag(content="*, *::before, *::after{animation-duration:0s!important;transition-duration:0s!important;caret-color:transparent!important}")
                page.wait_for_load_state("networkidle")
                try:
                    page.evaluate("document.fonts.ready")
                except Exception:
                    pass
                out = GOLDEN_DIR / f"{test_id}.png"
                page.screenshot(path=str(out), full_page=False)
                ctx.close()
                print(f"  ✓ {test_id} → {out.relative_to(ROOT)}")
            browser.close()

    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    print(f"\nDone. {len(targets)} golden(s) written to tests/visual/golden/.")
    print("Review with: open tests/visual/golden/")
    print("Then: git add tests/visual/golden/ && git commit -m 'test(visual): regenerate goldens'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
