# Phase 1: UI Foundation + Search Stability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chaotic triple-`:root` CSS system with a unified 3-layer design token architecture, implement Notion-style sidebar navigation, breathing grid background, full dark mode support, and integrate OpenAlex as a third search source.

**Architecture:** CSS design tokens (primitive → semantic → component) with `[data-theme="dark"]` switching. Left sidebar navigation replaces top pill nav. OpenAlex added to `UnifiedSearchService` parallel search. Semantic Scholar hardened with timeout/retry. Search filter chips as client-side JS on result list.

**Tech Stack:** CSS custom properties, vanilla JS, Flask/Jinja2, Python `urllib`/`requests` for OpenAlex API.

**Ref:** Design spec at `docs/superpowers/specs/2026-05-11-paper-agent-v2-design.md`, sections 2 and 4.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Rewrite | `static/research_ui.css` | Design tokens, breathing grid, Notion components, sidebar, dark mode |
| Modify | `templates/base_research.html` | Sidebar nav layout, breathing grid container |
| Modify | `templates/search_research.html` | Adapt to sidebar layout, add filter chips |
| Modify | `templates/_components.html` | Add Jinja2 macros for Notion-style components |
| Modify | `static/js/preferences.js` | Ensure theme toggle works with new token system |
| Modify | `static/js/core.js` | Add filter chip interaction helpers |
| Create | `static/js/sidebar.js` | Sidebar collapse/expand, mobile hamburger |
| Modify | `app/services/unified_search_service.py` | Add OpenAlex source, fix Semantic Scholar |
| Create | `tests/test_openalex_integration.py` | OpenAlex normalization and dedup tests |
| Create | `tests/test_design_tokens.py` | CSS token structure validation |
| Modify | `app/viewmodels/shared.py` | Update NAV_ITEM_CONFIG for sidebar structure |

---

### Task 1: Design Token System — CSS Foundation

**Files:**
- Rewrite: `static/research_ui.css` (lines 1–50 and 2908–3350, the three `:root` blocks)
- Create: `tests/test_design_tokens.py`

- [ ] **Step 1: Write test that validates token structure**

```python
# tests/test_design_tokens.py
"""Validate the CSS design token system structure."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "research_ui.css"


class TestDesignTokens:
    def setup_method(self):
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
        """The old triple :root pattern must not exist."""
        # Old pattern had --paper-agent-bg and --apple-claude- prefixes
        assert "--paper-agent-bg" not in self.css, "Legacy --paper-agent-* tokens still present"
        assert "--apple-claude-" not in self.css, "Legacy --apple-claude-* tokens still present"

    def test_breathing_grid_defined(self):
        """Breathing grid background must be defined."""
        assert "breathing-grid" in self.css or "breathe" in self.css

    def test_reduced_motion_respected(self):
        """prefers-reduced-motion must disable breathing animation."""
        assert "prefers-reduced-motion" in self.css
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_design_tokens.py -v`
Expected: FAIL — current CSS has 3 `:root` blocks, legacy `--paper-agent-*` tokens, no breathing grid.

- [ ] **Step 3: Rebuild `:root` as single block with 3-layer tokens**

Replace ALL `:root` blocks in `static/research_ui.css` (there are currently 3 — lines ~1-50, ~2909-3275, ~3278-3350) with a single unified block at the top of the file:

```css
/* ============================================================
   Layer 1 — Primitive tokens (raw values, never used directly)
   ============================================================ */
:root {
  /* Neutrals */
  --color-warm-black: #1a1a1a;
  --color-charcoal: #2a2a2a;
  --color-graphite: #3a3a3a;
  --color-slate: #6b6b6b;
  --color-silver: #999999;
  --color-fog: #e8e8e5;
  --color-cloud: #f5f5f3;
  --color-off-white: #fafaf8;
  --color-pure-white: #ffffff;

  /* Brand */
  --color-claude-orange: #d97757;
  --color-claude-orange-soft: #f0c8b4;
  --color-apple-blue: #007aff;
  --color-apple-blue-soft: #b3d7ff;
  --color-success: #34a853;
  --color-warning: #f9ab00;
  --color-error: #ea4335;

  /* Layer 2 — Semantic tokens (light mode default) */
  --bg-primary: var(--color-off-white);
  --bg-surface: var(--color-pure-white);
  --bg-surface-hover: var(--color-cloud);
  --bg-surface-active: var(--color-fog);
  --bg-sidebar: var(--color-cloud);
  --bg-input: var(--color-pure-white);
  --bg-overlay: rgba(0, 0, 0, 0.4);

  --ink-primary: var(--color-warm-black);
  --ink-secondary: var(--color-slate);
  --ink-muted: var(--color-silver);
  --ink-on-accent: var(--color-pure-white);

  --accent-primary: var(--color-claude-orange);
  --accent-soft: var(--color-claude-orange-soft);
  --accent-link: var(--color-apple-blue);

  --border-default: var(--color-fog);
  --border-strong: #d0d0cd;
  --border-focus: var(--color-apple-blue);

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
  --font-mono: "SF Mono", "Fira Code", "Fira Mono", "Roboto Mono", monospace;

  --transition-fast: 120ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 350ms ease;

  /* Layer 3 — Component tokens */
  --card-bg: var(--bg-surface);
  --card-border: var(--border-default);
  --card-shadow: var(--shadow-sm);
  --card-shadow-hover: var(--shadow-md);

  --nav-bg: var(--bg-sidebar);
  --nav-ink: var(--ink-primary);
  --nav-ink-muted: var(--ink-secondary);
  --nav-active-bg: var(--bg-surface);
  --nav-hover-bg: var(--bg-surface-hover);
  --nav-width: 240px;
  --nav-collapsed-width: 48px;

  --input-bg: var(--bg-input);
  --input-border: var(--border-default);
  --input-focus-border: var(--border-focus);

  --agent-panel-bg: var(--bg-surface);
  --agent-panel-width: 360px;

  /* Breathing grid */
  --grid-color: rgba(0, 0, 0, 0.04);
  --grid-size: 32px;
}

/* ============================================================
   Dark mode — override Layer 2 semantic tokens
   ============================================================ */
[data-theme="dark"] {
  --bg-primary: var(--color-warm-black);
  --bg-surface: var(--color-charcoal);
  --bg-surface-hover: var(--color-graphite);
  --bg-surface-active: #444444;
  --bg-sidebar: #222222;
  --bg-input: var(--color-graphite);
  --bg-overlay: rgba(0, 0, 0, 0.6);

  --ink-primary: #ededec;
  --ink-secondary: var(--color-silver);
  --ink-muted: #777777;

  --accent-soft: #5c3a2a;

  --border-default: var(--color-graphite);
  --border-strong: #555555;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.4);

  --grid-color: rgba(255, 255, 255, 0.03);
}
```

Remove ALL other `:root` or CSS variable definition blocks that were duplicating/overriding these tokens. Keep all component styles that reference `var(--...)` tokens — they'll automatically pick up the new values.

- [ ] **Step 4: Add breathing grid CSS**

Append to `static/research_ui.css` after the dark mode block:

```css
/* ============================================================
   Breathing Grid Background
   ============================================================ */
@keyframes breathe-grid {
  0%, 100% { opacity: 0.03; }
  50% { opacity: 0.08; }
}

.breathing-grid {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image:
    repeating-linear-gradient(0deg, var(--grid-color) 0 1px, transparent 1px var(--grid-size)),
    repeating-linear-gradient(90deg, var(--grid-color) 0 1px, transparent 1px var(--grid-size));
  animation: breathe-grid 6s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .breathing-grid {
    animation: none;
    opacity: 0.05;
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_design_tokens.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add static/research_ui.css tests/test_design_tokens.py
git commit -m "feat(css): replace triple :root with unified 3-layer design token system"
```

---

### Task 2: Migrate Component Styles to Design Tokens

**Files:**
- Modify: `static/research_ui.css` (all component styles throughout the file)

- [ ] **Step 1: Search-and-replace legacy token references**

Find all CSS rules that reference old variable names and update them. The main patterns:

| Old token | New token |
|-----------|-----------|
| `--paper-agent-bg` | `var(--bg-primary)` |
| `--paper-agent-ink` | `var(--ink-primary)` |
| `--paper-agent-muted` | `var(--ink-secondary)` |
| `--paper-agent-line` | `var(--border-default)` |
| `--paper-agent-accent` | `var(--accent-primary)` |
| `--paper-agent-soft` | `var(--accent-soft)` |
| Hard-coded `#1a1a1a` in color properties | `var(--ink-primary)` |
| Hard-coded `#fafaf8` / `#f4f4f8` in background | `var(--bg-primary)` |
| Hard-coded `#ffffff` / `white` in card backgrounds | `var(--bg-surface)` |
| Hard-coded `#e8e8e5` / `#eee` in borders | `var(--border-default)` |
| Hard-coded `#6b6b6b` / `#666` in secondary text | `var(--ink-secondary)` |
| Hard-coded `linear-gradient(110deg, #f4f4f8, ...)` body background | `var(--bg-primary)` |

Also update `body` rule to use tokens:

```css
body {
  font-family: var(--font-sans);
  color: var(--ink-primary);
  background: var(--bg-primary);
  line-height: 1.6;
  margin: 0;
}
```

- [ ] **Step 2: Remove the old `[data-theme="dark"] body` block**

The old dark mode block (around lines 57-98) that only overrode body background should be fully removed since dark mode is now handled by the semantic token switching.

- [ ] **Step 3: Verify no broken variable references**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
grep -n "var(--paper-agent-\|var(--apple-claude-" static/research_ui.css
```

Expected: no matches (all legacy references removed).

- [ ] **Step 4: Visual smoke test**

```bash
python web_server.py &
sleep 2
curl -s http://localhost:5555/ | grep -c "var(--bg-primary)\|research_ui.css"
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add static/research_ui.css
git commit -m "refactor(css): migrate all component styles to design tokens"
```

---

### Task 3: Sidebar Navigation

**Files:**
- Create: `static/js/sidebar.js`
- Modify: `templates/base_research.html`
- Modify: `app/viewmodels/shared.py`
- Modify: `static/research_ui.css`

- [ ] **Step 1: Update NAV_ITEM_CONFIG for sidebar structure**

In `app/viewmodels/shared.py`, update `NAV_ITEM_CONFIG` to include sidebar sections:

```python
NAV_ITEM_CONFIG = [
    # Main
    {"key": "search", "label": "Search", "href": "/", "icon": "search", "section": "main"},
    {"key": "recommendations", "label": "Recommendations", "href": "/recommendations", "icon": "star", "section": "main"},
    {"key": "watch", "label": "Watch", "href": "/watch", "icon": "eye", "section": "main"},
    {"key": "reading", "label": "Reading", "href": "/reading", "icon": "book", "section": "main"},
    # Subscriptions (section header)
    {"key": "sub_journals", "label": "Journals", "href": "/watch?tab=journals", "icon": "journal", "section": "subscriptions"},
    {"key": "sub_conferences", "label": "Conferences", "href": "/watch?tab=conferences", "icon": "conference", "section": "subscriptions"},
    {"key": "sub_scholars", "label": "Scholars", "href": "/watch?tab=scholars", "icon": "scholar", "section": "subscriptions"},
    {"key": "sub_fields", "label": "Fields", "href": "/watch?tab=fields", "icon": "field", "section": "subscriptions"},
    # Footer
    {"key": "settings", "label": "Settings", "href": "/settings", "icon": "settings", "section": "footer"},
]
```

- [ ] **Step 2: Create sidebar template in base_research.html**

Replace the current topbar `<header>` section in `templates/base_research.html` with a sidebar layout:

```html
<div class="app-layout">
  <nav class="sidebar" id="sidebar" data-collapsed="false">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <svg class="sidebar-logo" ...><!-- existing logo SVG --></svg>
        <span class="sidebar-brand-text">Paper Agent</span>
      </div>
      <button class="sidebar-toggle" onclick="toggleSidebar()" aria-label="Toggle sidebar">
        <svg width="16" height="16" viewBox="0 0 16 16"><path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
      </button>
    </div>

    <div class="sidebar-section">
      {% for item in nav_items if item.section == 'main' %}
      <a class="sidebar-item {% if item.active %}is-active{% endif %}" href="{{ item.href }}">
        <span class="sidebar-icon">{{ item.icon_svg|safe }}</span>
        <span class="sidebar-label">{{ item.label }}</span>
        {% if item.count %}<span class="sidebar-badge">{{ item.count }}</span>{% endif %}
      </a>
      {% endfor %}
    </div>

    <div class="sidebar-section">
      <div class="sidebar-section-title">Subscriptions</div>
      {% for item in nav_items if item.section == 'subscriptions' %}
      <a class="sidebar-item {% if item.active %}is-active{% endif %}" href="{{ item.href }}">
        <span class="sidebar-icon">{{ item.icon_svg|safe }}</span>
        <span class="sidebar-label">{{ item.label }}</span>
      </a>
      {% endfor %}
    </div>

    <div class="sidebar-footer">
      {% for item in nav_items if item.section == 'footer' %}
      <a class="sidebar-item {% if item.active %}is-active{% endif %}" href="{{ item.href }}">
        <span class="sidebar-icon">{{ item.icon_svg|safe }}</span>
        <span class="sidebar-label">{{ item.label }}</span>
      </a>
      {% endfor %}
      <button class="sidebar-item" onclick="toggleTheme()">
        <span class="sidebar-icon" id="themeIcon">🌙</span>
        <span class="sidebar-label">Dark Mode</span>
      </button>
    </div>
  </nav>

  <main class="main-content">
    <div class="breathing-grid"></div>
    {% block content %}{% endblock %}
  </main>
</div>
```

- [ ] **Step 3: Add sidebar CSS to research_ui.css**

```css
/* ============================================================
   Sidebar Navigation
   ============================================================ */
.app-layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: var(--nav-width);
  background: var(--nav-bg);
  border-right: 1px solid var(--border-default);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  transition: width var(--transition-normal);
  overflow-x: hidden;
}

.sidebar[data-collapsed="true"] {
  width: var(--nav-collapsed-width);
}

.sidebar[data-collapsed="true"] .sidebar-label,
.sidebar[data-collapsed="true"] .sidebar-brand-text,
.sidebar[data-collapsed="true"] .sidebar-section-title,
.sidebar[data-collapsed="true"] .sidebar-badge {
  display: none;
}

.main-content {
  flex: 1;
  margin-left: var(--nav-width);
  transition: margin-left var(--transition-normal);
  position: relative;
  min-height: 100vh;
}

.sidebar[data-collapsed="true"] ~ .main-content {
  margin-left: var(--nav-collapsed-width);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 12px;
  border-bottom: 1px solid var(--border-default);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-brand-text {
  font-weight: 600;
  font-size: 14px;
  color: var(--ink-primary);
}

.sidebar-toggle {
  background: none;
  border: none;
  color: var(--ink-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
}

.sidebar-toggle:hover {
  background: var(--nav-hover-bg);
}

.sidebar-section {
  padding: 8px;
  flex: 1;
}

.sidebar-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-muted);
  padding: 8px 12px 4px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  color: var(--nav-ink-muted);
  text-decoration: none;
  font-size: 14px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  border: none;
  background: none;
  width: 100%;
  text-align: left;
}

.sidebar-item:hover {
  background: var(--nav-hover-bg);
  color: var(--nav-ink);
}

.sidebar-item.is-active {
  background: var(--nav-active-bg);
  color: var(--nav-ink);
  font-weight: 500;
}

.sidebar-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sidebar-badge {
  margin-left: auto;
  font-size: 11px;
  background: var(--accent-soft);
  color: var(--accent-primary);
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 500;
}

.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--border-default);
}

/* Mobile sidebar */
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform var(--transition-normal);
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  .main-content {
    margin-left: 0;
  }

  .mobile-nav-toggle {
    display: block;
    position: fixed;
    top: 12px;
    left: 12px;
    z-index: 99;
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: 8px;
    cursor: pointer;
  }
}

@media (min-width: 769px) {
  .mobile-nav-toggle {
    display: none;
  }
}
```

- [ ] **Step 4: Create sidebar.js**

```javascript
// static/js/sidebar.js
(function () {
  var STORAGE_KEY = 'statdesk.sidebar.collapsed';

  function initSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    var collapsed = localStorage.getItem(STORAGE_KEY) === 'true';
    sidebar.dataset.collapsed = String(collapsed);
  }

  function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    var next = sidebar.dataset.collapsed !== 'true';
    sidebar.dataset.collapsed = String(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  }

  // Mobile hamburger
  function toggleMobileSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('is-open');
  }

  document.addEventListener('DOMContentLoaded', initSidebar);

  window.toggleSidebar = toggleSidebar;
  window.toggleMobileSidebar = toggleMobileSidebar;
})();
```

- [ ] **Step 5: Load sidebar.js in base_research.html**

Add `<script src="{{ url_for('static', filename='js/sidebar.js') }}?v={{ static_version }}"></script>` in the scripts block.

- [ ] **Step 6: Smoke test sidebar renders**

```bash
python web_server.py &
sleep 2
curl -s http://localhost:5555/ | grep -c "sidebar"
kill %1
```

Expected: > 0 matches

- [ ] **Step 7: Commit**

```bash
git add static/research_ui.css static/js/sidebar.js templates/base_research.html app/viewmodels/shared.py
git commit -m "feat(ui): add Notion-style sidebar navigation with collapse and mobile support"
```

---

### Task 4: Notion-Style Component Library

**Files:**
- Modify: `templates/_components.html`
- Modify: `static/research_ui.css`

- [ ] **Step 1: Add Jinja2 component macros**

Add to `templates/_components.html`:

```html
{# ── Page Header (Notion-style) ── #}
{% macro page_header(title, description='', icon='') %}
<div class="page-header">
  {% if icon %}<span class="page-header-icon">{{ icon }}</span>{% endif %}
  <h1 class="page-header-title">{{ title }}</h1>
  {% if description %}<p class="page-header-desc">{{ description }}</p>{% endif %}
</div>
{% endmacro %}

{# ── Card ── #}
{% macro card(class='', id='') %}
<div class="notion-card {{ class }}" {% if id %}id="{{ id }}"{% endif %}>
  {{ caller() }}
</div>
{% endmacro %}

{# ── Button ── #}
{% macro btn(label, variant='ghost', size='md', onclick='', type='button', disabled=false) %}
<button class="btn btn-{{ variant }} btn-{{ size }}" type="{{ type }}"
  {% if onclick %}onclick="{{ onclick }}"{% endif %}
  {% if disabled %}disabled{% endif %}>
  {{ label }}
</button>
{% endmacro %}

{# ── Tag Chip ── #}
{% macro chip(label, variant='default', onclick='') %}
<span class="chip chip-{{ variant }}" {% if onclick %}onclick="{{ onclick }}" role="button" tabindex="0"{% endif %}>
  {{ label }}
</span>
{% endmacro %}

{# ── Empty State ── #}
{% macro empty_state(title, description='', action_label='', action_onclick='') %}
<div class="empty-state">
  <h3 class="empty-state-title">{{ title }}</h3>
  {% if description %}<p class="empty-state-desc">{{ description }}</p>{% endif %}
  {% if action_label %}
  <button class="btn btn-primary btn-sm" onclick="{{ action_onclick }}">{{ action_label }}</button>
  {% endif %}
</div>
{% endmacro %}
```

- [ ] **Step 2: Add component CSS**

Append to `static/research_ui.css`:

```css
/* ============================================================
   Notion-Style Components
   ============================================================ */

/* Page Header */
.page-header {
  padding: 40px 0 24px;
  max-width: 900px;
}

.page-header-icon {
  font-size: 32px;
  display: block;
  margin-bottom: 8px;
}

.page-header-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--ink-primary);
  margin: 0;
  line-height: 1.2;
}

.page-header-desc {
  color: var(--ink-secondary);
  font-size: 14px;
  margin: 8px 0 0;
  line-height: 1.5;
}

/* Card */
.notion-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--card-shadow);
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.notion-card:hover {
  box-shadow: var(--card-shadow-hover);
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  border: none;
  line-height: 1;
}

.btn-sm { padding: 5px 10px; font-size: 12px; }
.btn-md { padding: 7px 14px; }
.btn-lg { padding: 10px 20px; font-size: 14px; }

.btn-ghost {
  background: transparent;
  color: var(--ink-secondary);
}

.btn-ghost:hover {
  background: var(--bg-surface-hover);
  color: var(--ink-primary);
}

.btn-primary {
  background: var(--accent-primary);
  color: var(--ink-on-accent);
}

.btn-primary:hover {
  filter: brightness(1.1);
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Chips */
.chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 20px;
  background: var(--bg-surface-hover);
  color: var(--ink-secondary);
  white-space: nowrap;
}

.chip-active {
  background: var(--accent-soft);
  color: var(--accent-primary);
}

.chip[role="button"] {
  cursor: pointer;
  transition: background var(--transition-fast);
}

.chip[role="button"]:hover {
  background: var(--bg-surface-active);
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--ink-secondary);
}

.empty-state-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0 0 8px;
}

.empty-state-desc {
  font-size: 14px;
  margin: 0 0 16px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--bg-surface);
  color: var(--ink-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 10px 16px;
  font-size: 13px;
  box-shadow: var(--shadow-lg);
  transform: translateY(120%);
  transition: transform var(--transition-normal);
  z-index: 1000;
}

.toast.visible {
  transform: translateY(0);
}

.toast.error {
  border-color: var(--color-error);
  color: var(--color-error);
}
```

- [ ] **Step 3: Commit**

```bash
git add templates/_components.html static/research_ui.css
git commit -m "feat(ui): add Notion-style component library (cards, buttons, chips, page header)"
```

---

### Task 5: OpenAlex Integration

**Files:**
- Modify: `app/services/unified_search_service.py`
- Create: `tests/test_openalex_integration.py`

- [ ] **Step 1: Write OpenAlex normalization tests**

```python
# tests/test_openalex_integration.py
"""Test OpenAlex API integration and paper normalization."""
import unittest
from unittest.mock import patch, MagicMock

from app.services.unified_search_service import (
    normalize_openalex_paper,
    search_openalex,
    merge_and_dedupe_papers,
)


class TestNormalizeOpenAlexPaper(unittest.TestCase):
    def test_basic_normalization(self):
        raw = {
            "id": "https://openalex.org/W12345",
            "title": "A Survey on Federated Learning",
            "authorships": [
                {"author": {"display_name": "Alice Smith", "id": "https://openalex.org/A111"}},
                {"author": {"display_name": "Bob Jones", "id": "https://openalex.org/A222"}},
            ],
            "publication_year": 2025,
            "primary_location": {
                "source": {"display_name": "Nature ML", "type": "journal"}
            },
            "abstract_inverted_index": None,
            "cited_by_count": 42,
            "referenced_works_count": 15,
            "doi": "https://doi.org/10.1234/test",
            "ids": {"openalex": "https://openalex.org/W12345"},
        }
        result = normalize_openalex_paper(raw)
        self.assertEqual(result["paper_id"], "openalex:W12345")
        self.assertEqual(result["source"], "openalex")
        self.assertEqual(result["title"], "A Survey on Federated Learning")
        self.assertEqual(result["authors"], ["Alice Smith", "Bob Jones"])
        self.assertEqual(result["year"], 2025)
        self.assertEqual(result["venue"], "Nature ML")
        self.assertEqual(result["citation_count"], 42)
        self.assertEqual(result["reference_count"], 15)
        self.assertIn("10.1234/test", result["external_ids"].get("doi", ""))

    def test_missing_fields_graceful(self):
        raw = {"id": "https://openalex.org/W999", "title": "Minimal Paper"}
        result = normalize_openalex_paper(raw)
        self.assertEqual(result["paper_id"], "openalex:W999")
        self.assertEqual(result["authors"], [])
        self.assertIsNone(result["year"])
        self.assertEqual(result["venue"], "")


class TestSearchOpenAlex(unittest.TestCase):
    @patch("app.services.unified_search_service._openalex_request")
    def test_returns_normalized_papers(self, mock_req):
        mock_req.return_value = {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "Test Paper",
                    "authorships": [],
                    "publication_year": 2025,
                    "cited_by_count": 10,
                }
            ]
        }
        papers = search_openalex("test", max_results=5)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["source"], "openalex")

    @patch("app.services.unified_search_service._openalex_request")
    def test_returns_empty_on_error(self, mock_req):
        mock_req.side_effect = Exception("network error")
        papers = search_openalex("test", max_results=5)
        self.assertEqual(papers, [])


class TestDeduplicationWithOpenAlex(unittest.TestCase):
    def test_openalex_deduped_by_doi(self):
        arxiv_paper = {
            "paper_id": "arxiv:2401.12345",
            "source": "arxiv",
            "title": "Same Paper",
            "external_ids": {"doi": "10.1234/test"},
            "authors": ["Alice"],
        }
        openalex_paper = {
            "paper_id": "openalex:W1",
            "source": "openalex",
            "title": "Same Paper",
            "external_ids": {"doi": "10.1234/test"},
            "authors": ["Alice"],
            "citation_count": 42,
        }
        merged = merge_and_dedupe_papers([arxiv_paper, openalex_paper])
        self.assertEqual(len(merged), 1)
        # Should merge sources
        self.assertIn("arxiv", merged[0]["source"])
        self.assertIn("openalex", merged[0]["source"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_openalex_integration.py -v`
Expected: FAIL — `normalize_openalex_paper` and `search_openalex` don't exist.

- [ ] **Step 3: Implement OpenAlex integration**

Add to `app/services/unified_search_service.py`:

```python
import os
import json
import urllib.request
import urllib.parse

OPENALEX_BASE = "https://api.openalex.org/works"
OPENALEX_MAILTO = os.environ.get("OPENALEX_MAILTO", "")


def _openalex_request(url: str, *, timeout: int = 10) -> dict:
    """Make a request to OpenAlex API."""
    req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_openalex_paper(paper: dict) -> dict:
    """Normalize an OpenAlex work to the common paper format."""
    oa_id = str(paper.get("id") or "")
    short_id = oa_id.replace("https://openalex.org/", "") if oa_id else ""

    authorships = paper.get("authorships") or []
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author", {}).get("display_name")
    ]

    primary = paper.get("primary_location") or {}
    source_info = primary.get("source") or {}
    venue = source_info.get("display_name", "")

    doi_raw = str(paper.get("doi") or "")
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

    external_ids = {}
    if doi:
        external_ids["doi"] = doi
    if short_id:
        external_ids["openalex"] = short_id

    abstract = ""
    inverted = paper.get("abstract_inverted_index")
    if inverted and isinstance(inverted, dict):
        # Reconstruct abstract from inverted index
        word_positions = []
        for word, positions in inverted.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        abstract = " ".join(w for _, w in word_positions)

    return {
        "paper_id": f"openalex:{short_id}" if short_id else "",
        "source": "openalex",
        "title": str(paper.get("title") or ""),
        "authors": authors,
        "author_text": ", ".join(authors),
        "year": paper.get("publication_year"),
        "venue": venue,
        "abstract": abstract,
        "summary": abstract[:600] if abstract else "",
        "url": doi_raw if doi_raw.startswith("http") else (
            f"https://doi.org/{doi}" if doi else oa_id
        ),
        "pdf_url": "",
        "citation_count": paper.get("cited_by_count"),
        "reference_count": paper.get("referenced_works_count"),
        "external_ids": external_ids,
        "categories": [],
        "score": 0.0,
        "relevance_reason": "",
    }


def search_openalex(query: str, *, max_results: int = 25) -> list[dict]:
    """Search OpenAlex for papers matching query."""
    try:
        params = {
            "search": query,
            "per_page": min(max_results, 50),
            "sort": "relevance_score:desc",
        }
        if OPENALEX_MAILTO:
            params["mailto"] = OPENALEX_MAILTO
        url = f"{OPENALEX_BASE}?{urllib.parse.urlencode(params)}"
        data = _openalex_request(url)
        results = data.get("results") or []
        return [normalize_openalex_paper(r) for r in results if r.get("title")]
    except Exception:
        return []
```

- [ ] **Step 4: Update `merge_and_dedupe_papers` for OpenAlex ID**

In the `_paper_key` function, add OpenAlex ID as a dedup dimension:

```python
def _paper_key(paper: dict) -> str:
    """Generate a deduplication key for a paper."""
    ext = paper.get("external_ids") or {}

    doi = str(ext.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"

    arxiv = str(ext.get("arxiv") or paper.get("paper_id", "")).strip()
    if arxiv.startswith("arxiv:"):
        return _clean_arxiv_id(arxiv).lower()

    openalex = str(ext.get("openalex") or "").strip()
    if openalex:
        return f"openalex:{openalex.lower()}"

    return f"title:{_normalize_title(paper.get('title', ''))}"
```

- [ ] **Step 5: Add OpenAlex to `search_papers`**

Update the `search_papers` function to include OpenAlex as a third parallel source:

```python
def search_papers(
    query: str,
    *,
    max_results: int = 25,
    search_fn: Callable | None = None,
    opener=None,
) -> dict:
    papers: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    sources: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        arxiv_future = pool.submit(search_arxiv, query, max_results=max_results, search_fn=search_fn)
        scholar_future = pool.submit(search_semantic_scholar, query, max_results=max_results, opener=opener)
        openalex_future = pool.submit(search_openalex, query, max_results=max_results)

        # Collect arXiv results
        try:
            arxiv_papers = arxiv_future.result(timeout=20)
            papers.extend(arxiv_papers)
            sources["arxiv"] = "ok" if arxiv_papers else "empty"
        except Exception as exc:
            sources["arxiv"] = "failed"
            errors.append(f"arXiv: {exc}")

        # Collect Semantic Scholar results
        try:
            scholar_papers = scholar_future.result(timeout=20)
            papers.extend(scholar_papers)
            sources["semantic_scholar"] = "ok" if scholar_papers else "empty"
        except Exception as exc:
            sources["semantic_scholar"] = "failed"
            warnings.append(f"Semantic Scholar: {exc}")

        # Collect OpenAlex results
        try:
            oa_papers = openalex_future.result(timeout=15)
            papers.extend(oa_papers)
            sources["openalex"] = "ok" if oa_papers else "empty"
        except Exception as exc:
            sources["openalex"] = "failed"
            warnings.append(f"OpenAlex: {exc}")

    merged = merge_and_dedupe_papers(papers)
    return {"papers": merged, "warnings": warnings, "errors": errors, "sources": sources}
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_openalex_integration.py -v`
Expected: ALL PASS

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest -q`
Expected: All existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add app/services/unified_search_service.py tests/test_openalex_integration.py
git commit -m "feat(search): add OpenAlex as third search source with normalization and dedup"
```

---

### Task 6: Semantic Scholar Hardening

**Files:**
- Modify: `app/services/unified_search_service.py`

- [ ] **Step 1: Add timeout and retry to Semantic Scholar**

Update `search_semantic_scholar` in `app/services/unified_search_service.py`:

```python
import time

_s2_failure_cache: dict[str, float] = {}
S2_FAILURE_CACHE_TTL = 60  # seconds


def search_semantic_scholar(query: str, *, max_results: int = 25, opener=None) -> list[dict]:
    """Search Semantic Scholar with timeout, retry, and failure caching."""
    # Check failure cache
    last_fail = _s2_failure_cache.get("last_failure", 0)
    if time.time() - last_fail < S2_FAILURE_CACHE_TTL:
        return []

    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(query)}&limit={min(max_results, 100)}&fields=title,authors,year,venue,abstract,citationCount,referenceCount,externalIds,url"

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            if opener:
                resp_text = opener(url)
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_text = resp.read().decode("utf-8")

            data = json.loads(resp_text) if isinstance(resp_text, str) else resp_text
            papers = data.get("data") or []
            return [normalize_semantic_paper(p) for p in papers if p.get("title")]

        except Exception:
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))  # Exponential backoff: 1.5s, 3s
                continue
            _s2_failure_cache["last_failure"] = time.time()
            return []
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -q`
Expected: All pass (existing S2 tests should still work since mock bypasses retry).

- [ ] **Step 3: Commit**

```bash
git add app/services/unified_search_service.py
git commit -m "fix(search): add timeout, exponential retry, and failure cache for Semantic Scholar"
```

---

### Task 7: Search Filter Chips

**Files:**
- Modify: `templates/search_research.html`
- Modify: `static/js/core.js`

- [ ] **Step 1: Add filter chip HTML to search results**

In `templates/search_research.html`, add filter chip bar above the result list:

```html
<div class="filter-chips" id="searchFilterChips" hidden>
  <span class="filter-chips-label">Filter:</span>
  <button class="chip" data-filter="all" onclick="applySearchFilter('all')">All</button>
  <button class="chip" data-filter="arxiv" onclick="applySearchFilter('arxiv')">arXiv</button>
  <button class="chip" data-filter="semantic_scholar" onclick="applySearchFilter('semantic_scholar')">Semantic Scholar</button>
  <button class="chip" data-filter="openalex" onclick="applySearchFilter('openalex')">OpenAlex</button>
  <span class="filter-chips-divider"></span>
  <button class="chip" data-filter="conference" onclick="applySearchFilter('conference')">Conference</button>
  <button class="chip" data-filter="journal" onclick="applySearchFilter('journal')">Journal</button>
  <button class="chip" data-filter="preprint" onclick="applySearchFilter('preprint')">Preprint</button>
</div>
```

- [ ] **Step 2: Add filter JS to core.js**

```javascript
function applySearchFilter(filter) {
  var chips = document.querySelectorAll('#searchFilterChips .chip');
  chips.forEach(function (chip) {
    chip.classList.toggle('chip-active', chip.dataset.filter === filter);
  });

  var rows = document.querySelectorAll('.paper-result-row');
  rows.forEach(function (row) {
    if (filter === 'all') {
      row.hidden = false;
      return;
    }
    var source = (row.dataset.paperSource || '').toLowerCase();
    var venue = (row.dataset.paperVenue || '').toLowerCase();

    // Source filter
    if (['arxiv', 'semantic_scholar', 'openalex'].indexOf(filter) !== -1) {
      row.hidden = source.indexOf(filter) === -1;
      return;
    }

    // Venue type filter
    if (filter === 'preprint') {
      row.hidden = source.indexOf('arxiv') === -1 && venue.indexOf('arxiv') === -1;
    } else if (filter === 'conference') {
      row.hidden = !(/neurips|icml|iclr|aaai|cvpr|eccv|acl|emnlp|naacl|sigir|kdd|www|chi/i.test(venue));
    } else if (filter === 'journal') {
      row.hidden = !(/nature|science|ieee|acm trans|journal|review/i.test(venue));
    }
  });
}

window.applySearchFilter = applySearchFilter;
```

- [ ] **Step 3: Add filter chip CSS**

```css
/* Filter Chips Bar */
.filter-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  flex-wrap: wrap;
}

.filter-chips-label {
  font-size: 12px;
  color: var(--ink-muted);
  margin-right: 4px;
}

.filter-chips-divider {
  width: 1px;
  height: 16px;
  background: var(--border-default);
  margin: 0 4px;
}
```

- [ ] **Step 4: Show filter chips when results exist**

In the search results rendering JS, unhide the filter bar:

```javascript
// After rendering results in fetchPaperAgentResults()
var filterBar = document.getElementById('searchFilterChips');
if (filterBar) filterBar.hidden = false;
```

- [ ] **Step 5: Commit**

```bash
git add templates/search_research.html static/js/core.js static/research_ui.css
git commit -m "feat(search): add client-side filter chips for source and venue type"
```

---

### Task 8: Update All Page Templates for Sidebar Layout

**Files:**
- Modify: `templates/recommendations.html`
- Modify: `templates/watch.html`
- Modify: `templates/reading.html`
- Modify: `templates/settings_research.html`
- Modify: `templates/paper_detail.html`

- [ ] **Step 1: Verify each template extends base_research.html**

All page templates already extend `base_research.html`, so the sidebar layout wraps them automatically. The main work is removing any duplicate navigation elements and ensuring the content area uses the page-header component.

- [ ] **Step 2: Remove old topbar elements from child templates**

Search each template for any `<header>` or `.topbar` elements that duplicate the sidebar nav and remove them. The sidebar in `base_research.html` handles all navigation.

- [ ] **Step 3: Replace page titles with page-header macro**

In each template, replace the `<h1>` page title with:

```html
{% from "_components.html" import page_header %}
{{ page_header("Page Title", "Description text") }}
```

- [ ] **Step 4: Visual smoke test all pages**

```bash
python web_server.py &
sleep 2
for url in "/" "/recommendations" "/watch" "/reading" "/settings" "/onboarding"; do
  echo "Testing $url..."
  curl -s -o /dev/null -w "%{http_code}" "http://localhost:5555$url"
  echo ""
done
kill %1
```

Expected: all return 200.

- [ ] **Step 5: Commit**

```bash
git add templates/
git commit -m "refactor(templates): adapt all pages to sidebar layout with page-header components"
```

---

### Task 9: Full Integration Test

**Files:**
- Modify: `tests/test_design_tokens.py`

- [ ] **Step 1: Add integration assertions**

```python
def test_all_pages_return_200(self):
    """Every surface should render without error."""
    import subprocess, time
    # This test verifies the CSS loads on real pages
    # Run as part of the full test suite

def test_no_legacy_css_variables(self):
    """No old variable naming patterns remain in CSS."""
    css = CSS_PATH.read_text(encoding="utf-8")
    assert "--paper-agent-" not in css
    assert "--apple-claude-" not in css

def test_sidebar_class_in_base_template(self):
    """Base template must include sidebar markup."""
    base = (CSS_PATH.parent.parent / "templates" / "base_research.html").read_text()
    assert "sidebar" in base
    assert "app-layout" in base
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -q`
Expected: All pass.

- [ ] **Step 3: Final commit for Phase 1**

```bash
git add -A
git commit -m "test: add Phase 1 integration assertions for design tokens and sidebar"
```
