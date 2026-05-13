"""Acceptance guards for the Paper Agent search workspace redesign."""

from __future__ import annotations

from pathlib import Path


def test_root_renders_paper_agent_search_workspace():
    import web_server

    response = web_server.app.test_client().get("/?skip_onboarding=1")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Paper Agent" in html
    assert "Research Desk" in html
    assert "Continue a workspace, review today's papers, or start something new" in html
    assert "/queue?status=Inbox" not in (response.location or "")


def test_top_navigation_uses_workspace_information_architecture():
    import web_server

    keys = [item["key"] for item in web_server.NAV_ITEM_CONFIG]
    labels = [item["label"] for item in web_server.NAV_ITEM_CONFIG]

    assert "home" in keys
    assert "search" in keys
    assert "workspaces" in keys
    assert "recommendations" in keys
    assert "subscriptions" in keys
    assert "reading" in keys
    assert "settings" in keys
    assert labels[0:3] == ["Home", "Search", "Workspaces"]


def test_base_shell_defaults_to_english_and_loads_local_alpine():
    template = Path("templates/base_research.html").read_text(encoding="utf-8")

    assert '<html lang="en" data-language="en"' in template
    assert "static/vendor/alpine-3.15.0.min.js" in template
    assert "cdn.jsdelivr.net/npm/alpinejs" not in template
    assert "cdn.jsdelivr.net" not in template
    assert "Keyboard Shortcuts" in template
    assert "键盘快捷键" not in template


def test_active_product_surfaces_remove_engineering_copy():
    paths = [
        Path("templates/home.html"),
        Path("templates/search_research.html"),
        Path("templates/queue_research.html"),
        Path("templates/reading.html"),
        Path("templates/watch.html"),
        Path("templates/settings_research.html"),
    ]
    forbidden = [
        "Cockpit",
        "Workbench",
        "Candidate Decision Workbench",
        "Reading Queue",
        "Queue is Empty",
        "好的研究",
        "暂无",
        "刷新全部",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{needle!r} remains in {path}"


def test_visual_system_uses_quiet_tokens_and_no_radial_body_background():
    css = Path("static/research_ui.css").read_text(encoding="utf-8")

    assert "--app-bg:" in css
    assert "--surface:" in css
    assert "--text-primary:" in css
    assert "--radius-card: var(--radius-lg)" in css
    assert "body {" in css
    body_block = css.split("body {", 1)[1].split("}", 1)[0]
    assert "radial-gradient" not in body_block
    assert ".paper-agent-searchbar" in css
    assert ".paper-preview-pane" in css
    assert "min-height: 380px" not in css


def test_search_template_limits_first_view_to_one_primary_searchbar():
    template = Path("templates/search_research.html").read_text(encoding="utf-8")

    assert template.count("paper-agent-searchbar") == 1
    assert template.count("Search papers, authors, topics...") == 1
    assert "Open full detail" in template
    assert template.count('class="card') <= 4
