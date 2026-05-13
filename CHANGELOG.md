# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Apple/Claude-inspired warm minimalist design system (design tokens in `css/tokens.css`,
  Apple/Claude components in `css/apple-claude.css`)
- Brand logo: simple line-drawn alpaca SVG (`static/img/alpaca-logo.svg`)
- Home page ("Research Desk") with quick-start bar, workspace cards, and today's papers section
- Workspace overview page with stats grid, workspace memory, suggestions, key papers, and actions
- Research Memo and Weekly Review page templates
- Reading page redesigned with modern tabs, workspace filter, and collection browsing
- Watch page redesigned with modern tabs (Journals/Conferences/Scholars/Fields) and saved searches
- Settings page redesigned with dual-pane layout (nav + content), modern form inputs
- Paper Detail page redesigned with Apple/Claude styling
- Recommendations page redesigned with consistent card system
- Alpaca logo in sidebar brand and favicon
- RAG retrieval service (`app/services/rag_service.py`) for workspace-level semantic paper retrieval

### Changed

- Renamed `home_workspace.html` → `home.html` for clarity; updated route reference
- Consolidated sidebar navigation into main/subscriptions/footer sections
- Onboarding now redirects to home (`/`) instead of legacy queue page (`/queue?status=Inbox`)
- Search page now includes hero section for consistent page height with other pages
- Flattened project root: removed obsolete extract scripts, deprecation shims, stale plans

### Removed

- `arxiv_recommender_v5.py` (deprecation shim)
- `extract_clean.py`, `extract_phase4.py`, `extract_task6.py`, `extract_task7.py` (one-off extraction scripts)
- `index.html` (legacy static daily digest)
- `prd (1).md` (duplicate PRD)
- `optimization_plan.md`, `update-plan.md`, `修改计划.md` (stale planning documents)
- `Paper_Agent_UI_Functional_Consolidation_Plan.md`, `arxiv_recommender_action_plan.md` (stale plans)
- `audit0501.md` (stale audit doc)
- `*_snapshot.md` (Playwright browser snapshots)
- `daily_arxiv_digest.md` (generated digest)
- `reports/ui_audit_report.txt` (single-use audit output)
- Runtime artifacts: `cache/`, `logs/`, `.playwright-mcp/`, `.venv/`, `node_modules/`

## [0.1.0] — 2026-04-30

### Added

- Flask web server with Inbox / Queue / Library / Monitor / Settings navigation
- 3-stage recommendation pipeline (Recall → Rank → Learn) behind `STATDESK_RANKER=v2`
- AI paper analysis via DeepSeek-compatible API (optional, with no-provider fallback)
- SQLite-backed workflow state for queue, collections, and subscriptions
- Local offline recommendation evaluator
- Docker and Docker Compose deployment support

[Unreleased]: https://github.com/SunWeizhou/ppr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SunWeizhou/ppr/releases/tag/v0.1.0
