# Product Stability & Launch Readiness

**Date:** 2026-04-27
**Status:** Approved
**Scope:** Local-first arXiv research triage desk — prototype → stable product

## Goal

Transform the functional local paper recommendation prototype into a stable, installable, backupable, distributable local research workflow product. The focus is NOT adding features but hardening: stability, install experience, data safety, error recovery, test coverage, UI polish, recommendation explainability, and long-term usability.

## Constraints

- local-first — no cloud accounts, no multi-user, no sync
- SQLite is primary state; Markdown/HTML/JSON are export/cache/fallback only
- No React/Vue rewrite
- No complex neural ranking models
- Every behavior change must have tests
- `python -m unittest discover -s tests -v` must stay green

---

## Phase 0 — Blocking Fixes (P0)

### 0.1 AI Analysis context completion
- **File:** `app/routes/api/ai.py`
- `POST /api/papers/<paper_id>/analysis/generate` must auto-resolve paper context from SQLite `recommendation_items` (primary) → Markdown history (fallback)
- Populate `title`, `abstract`, `authors`, `categories`, `score_details`, `recommendation_reason` before calling `AIAnalysisService`
- Return 404 if paper not found in any source

### 0.2 Paper Detail tests
- **File:** `tests/test_paper_detail.py` (new)
- Cover: canonicalize, 404, SQLite load, Markdown fallback, collection filtering, affinity in context, page modules present

### 0.3 setup.py packaging
- **File:** `setup.py`
- Add `waitress>=3.0.0` to `install_requires`
- Recursively include `static/js/*.js` in `data_files`

### 0.4 CORS restriction
- **File:** `web_server.py`
- Default: `CORS(app, origins=["http://localhost:5555", "http://127.0.0.1:5555"])`
- Dev mode (`USE_DEV_SERVER=1`): keep open CORS

---

## Phase 1 — Product Experience (P1)

### 1.1 View Full Detail entry points
- Add `/papers/<paper_id>` links to: Inbox detail panel, Inbox paper cards, Queue cards, Library collection cards, Monitor recent hits cards, Search result cards
- **Files:** `templates/home_research.html`, `templates/queue_research.html`, `templates/library_research.html`, `templates/monitor_research.html`, `templates/search_research.html`

### 1.2 Paper Detail action closure
- **File:** `templates/paper_detail.html`, `static/js/paper_actions.js`
- Add to right rail: Relevant, Ignore, Skim Later, Deep Read, Saved, Add to Collection, Follow first author
- Reuse existing APIs — no new backend logic

### 1.3 Score Breakdown completion
- **File:** `app/services/scoring_service.py`, `templates/paper_detail.html`
- New score_details fields: `subscription`, `penalty`, `recency`
- Paper Detail shows ALL non-zero score items
- Why Recommended explains primary positive & negative signals

### 1.4 Evaluation affinity ablation
- **File:** `evaluation/ablation.py`
- Add `without_affinity` variant alongside existing `full_scorer`, `keywords_only`, `keywords_semantic`, `keywords_semantic_feedback`

---

## Phase 2 — Production Engineering (P2)

### 2.1 CI hardening
- **File:** `.github/workflows/tests.yml`
- lint: `continue-on-error: false`
- security: `continue-on-error: false`
- typecheck, audit: keep `continue-on-error: true`

### 2.2 Release Checklist
- **File:** `docs/RELEASE_CHECKLIST.md` (new)

### 2.3 Backup & Restore
- **Files:** `app/routes/settings.py`, `templates/settings_research.html`
- Backup Now → `ppr_backup_YYYYMMDD_HHMMSS.zip`
- Restore from Backup
- Open Data Folder
- Contents: user_profile.json, user_config.json, keywords_config.json, cache/app_state.db, reports/, history/

### 2.4 System Health page
- **File:** `app/routes/settings.py` (new `/settings/system` route), `templates/` (new template)
- Display: SQLite path, DB size, schema_version, table counts, last backup, last run, last eval
- Actions: Run Health Check, Vacuum Database, Export State, Backup Now

### 2.5 One-click start scripts
- **Files:** `scripts/start_local.sh`, `scripts/start_local.ps1` (new)

### 2.6 Docker deployment
- **Files:** `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docs/DEPLOYMENT.md` (new)
- Bind 127.0.0.1:5555 only, volume mount ./runtime, never bake API keys

---

## Phase 3 — UI Polish (P3)

### 3.1 Inline style extraction
- **Files:** `static/research_ui.css` + `home_research.html`, `paper_detail.html`, `eval_dashboard.html`, `monitor_research.html`
- New CSS components: `.progress-card`, `.progress-bar`, `.score-breakdown-grid`, `.paper-detail-layout`, `.paper-detail-rail`, `.triage-summary-grid`, `.stat-card`

### 3.2 Narrow-screen adaptation
- **File:** `static/research_ui.css`
- < 900px: sidebar collapse, Inbox single-column, Paper Detail rail moves down, Monitor tabs horizontal scroll
- Test at: 390px, 768px, 1024px

### 3.3 Empty & error states
- **Files:** various templates
- States: no recommendations, generating, generation failed, no AI provider, AI generation failed, no subscriptions, subscription run failed, no related papers, no evaluation reports, DB not writable
- Each state gives a next-action button

---

## Execution Strategy

**Per-phase parallel agents:**
- Phase 0: 3 agents (0.1 AI context, 0.2 Paper Detail tests, 0.3+0.4 setup+CORS)
- Phase 1: 4 agents (1.1 View Full Detail, 1.2 Paper Detail actions, 1.3 Score Breakdown, 1.4 Eval ablation)
- Phase 2: 3 agents (2.1+2.2 CI+Checklist, 2.3+2.4 Backup+System Health, 2.5+2.6 Scripts+Docker)
- Phase 3: 3 agents (3.1 CSS extraction, 3.2 Narrow screen, 3.3 Empty states)

**Validation gate after each phase:**
1. `python -m unittest discover -s tests -v`
2. `ruff check`
3. Manual review of all changed files
