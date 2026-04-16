# -*- coding: utf-8 -*-
"""
Playwright Demo Script - Test arXiv Recommender Interface
Run: python playwright_demo.py
"""

from playwright.sync_api import sync_playwright
import time
import os
from pathlib import Path

# 使用相对路径
_PROJECT_ROOT = Path(__file__).parent.resolve()
_CACHE_DIR = _PROJECT_ROOT / 'cache'
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def test_arxiv_recommender():
    """Test various features of arXiv recommender"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})

        print("[INFO] Visiting http://localhost:5555 ...")
        page.goto("http://localhost:5555", wait_until="networkidle")

        # 1. Screenshot - Homepage
        screenshot_path = _CACHE_DIR / "screenshot_homepage.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"[OK] Homepage screenshot saved: {screenshot_path}")

        # 2. Get page title
        title = page.title()
        print(f"[INFO] Page title: {title}")

        # 3. Get paper count
        try:
            stat_number = page.locator(".stat-number").first.text_content()
            print(f"[INFO] Papers today: {stat_number}")
        except Exception:
            print("[WARN] Could not get paper count")

        # 4. Get theme tags
        try:
            themes = page.locator(".theme-tag").all_text_contents()
            print(f"[INFO] Today's themes: {', '.join(themes[:5])}...")
        except Exception:
            pass

        # 5. Get paper card count
        try:
            paper_count = len(page.locator(".paper-card").all())
            print(f"[INFO] Paper cards found: {paper_count}")
        except Exception:
            pass

        # 6. Test search page
        print("\n[INFO] Testing search page...")
        try:
            page.goto("http://localhost:5555/search.html", wait_until="networkidle")
            time.sleep(1)

            search_screenshot = _CACHE_DIR / "screenshot_search.png"
            page.screenshot(path=str(search_screenshot), full_page=True)
            print(f"[OK] Search page screenshot: {search_screenshot}")

            # Test search input
            search_input = page.locator("input[type='text'], input.search-input, #search-input").first
            if search_input:
                search_input.fill("in-context learning")
                print("[OK] Search input test passed")
        except Exception as e:
            print(f"[WARN] Search page test: {e}")

        # 7. Test scholars page
        print("\n[INFO] Testing scholars page...")
        try:
            page.goto("http://localhost:5555/scholars.html", wait_until="networkidle")
            time.sleep(1)

            scholars_screenshot = _CACHE_DIR / "screenshot_scholars.png"
            page.screenshot(path=str(scholars_screenshot), full_page=True)
            print(f"[OK] Scholars page screenshot: {scholars_screenshot}")
        except Exception as e:
            print(f"[WARN] Scholars page test: {e}")

        # 8. Test liked page
        print("\n[INFO] Testing liked/favorites page...")
        try:
            page.goto("http://localhost:5555/liked.html", wait_until="networkidle")
            time.sleep(1)

            liked_screenshot = _CACHE_DIR / "screenshot_liked.png"
            page.screenshot(path=str(liked_screenshot), full_page=True)
            print(f"[OK] Liked page screenshot: {liked_screenshot}")
        except Exception as e:
            print(f"[WARN] Liked page test: {e}")

        # 9. Test paper card interaction
        print("\n[INFO] Testing paper card interaction...")
        try:
            page.goto("http://localhost:5555", wait_until="networkidle")

            first_paper = page.locator(".paper-card").first
            if first_paper:
                paper_title = first_paper.locator(".paper-title").text_content()
                paper_score = first_paper.locator(".score-badge").text_content()
                print(f"[INFO] First paper: {paper_title[:60]}...")
                print(f"[INFO] Score: {paper_score}")
        except Exception as e:
            print(f"[WARN] Paper interaction test: {e}")

        browser.close()

        print("\n" + "="*50)
        print("[SUCCESS] Playwright test completed!")
        print("="*50)
        print("\nGenerated screenshots:")
        for f in ["screenshot_homepage.png", "screenshot_search.png",
                  "screenshot_scholars.png", "screenshot_liked.png"]:
            path = _CACHE_DIR / f
            if path.exists():
                size = path.stat().st_size / 1024
                print(f"  - {f} ({size:.1f} KB)")

if __name__ == "__main__":
    test_arxiv_recommender()
