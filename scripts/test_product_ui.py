#!/usr/bin/env python3
"""Smoke checks for product UI affordances.

This intentionally tests rendered HTML/static assets instead of browser clicks so it
can run when Computer Use is unavailable.
"""

from __future__ import annotations

import re
import sys
import urllib.request


BASE = "http://localhost:5555"


def fetch(path: str) -> str:
    with urllib.request.urlopen(BASE + path, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def assert_contains(name: str, haystack: str, needle: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"{name}: missing {needle!r}")


def assert_not_contains(name: str, haystack: str, needle: str) -> None:
    if needle in haystack:
        raise AssertionError(f"{name}: unexpected {needle!r}")


def main() -> int:
    home = fetch("/")
    monitor_authors = fetch("/monitor?tab=authors")
    monitor_queries = fetch("/monitor?tab=queries")
    css = fetch("/static/research_ui.css")
    js = fetch("/static/research_ui.js")

    assert_not_contains("footer", home, "数据保存在本地，界面按统计研究工作流重排。")
    assert_contains("footer quote", home, "data-i18n-quote")
    assert_contains("language toggle", home, 'data-action="toggle-language"')
    assert_contains("theme toggle", home, 'data-action="toggle-theme"')
    assert_contains("app language attr", home, "data-language")
    assert_contains("app theme attr", home, "data-theme")

    assert_contains("dark theme css", css, '[data-theme="dark"]')
    assert_contains("dark active nav contrast", css, '[data-theme="dark"] .nav-item.is-active')
    assert_contains("language dictionary", js, "const I18N")
    assert_contains("theme storage", js, "statdesk.theme")
    assert_contains("language storage", js, "statdesk.language")

    assert_contains("monitor author add", monitor_authors, "createAuthorSubscription")
    assert_contains("monitor author editor", monitor_authors, "authorSubscriptionModal")
    assert_contains("monitor author delete", monitor_authors, "deleteAuthorSubscriptionFromEditor")
    assert_contains("monitor query add", monitor_queries, "createQuerySubscription")
    assert_contains("monitor query delete", monitor_queries, "deleteQuerySubscriptionFromEditor")

    main_inner = re.search(r"\.main-inner\s*\{(?P<body>.*?)\}", css, re.S)
    if not main_inner or "max-width: 1280px" not in main_inner.group("body"):
        raise AssertionError("layout: main-inner should be tightened to max-width 1280px")

    split = re.search(r"\.split\s*\{(?P<body>.*?)\}", css, re.S)
    if not split or "minmax(300px, 400px)" not in split.group("body"):
        raise AssertionError("layout: split detail column should be tightened")

    assert_contains("inbox workspace fixed viewport", css, ".page-inbox .main-inner")
    assert_contains("inbox content grid", css, ".page-inbox .main-inner > section")
    assert_contains("inbox narrow viewport fallback", css, ".page-inbox .inbox-workspace")
    assert_contains("footer hidden on inbox", css, ".page-inbox .footer-note")
    if home.count("date-card-link") > 7:
        raise AssertionError("inbox date strip should render at most seven date cards")

    print("product UI smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
