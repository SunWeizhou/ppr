# Architecture

This project is a local-first arXiv research triage desk. The product goal is not to show more papers; it is to help a researcher triage today's papers, manage a reading queue, preserve long-lived research assets, and monitor authors, venues, and queries.

## Product Overview

A personalized daily recommendation service that:

- Fetches papers from the arXiv API matching a user's keyword profile.
- Scores them using keyword relevance scoring, with optional Zotero-based semantic similarity boosts and feedback learning adjustments.
- Presents an inbox (daily digest view), reading queue, library (collections/favorites), and monitor dashboard (subscriptions/health).
- Provides controls for feedback (likes, dislikes, demotes) and settings (keywords, AI analysis provider).
- Generates Markdown and HTML digests as export/cache artifacts.
- Offers an optional AI analysis layer (OpenAI or DeepSeek) for paper summarization and relevance explanation.

## Directory Structure

- `web_server.py` — Thin Flask entrypoint (92 lines). Responsibilities: Flask app init, CORS, request logging middleware, waitress production server, blueprint registration. No route handlers, no page rendering, no background job management.
- `arxiv_recommender_v5.py` — Pure re-export hub (60 lines). All classes and functions moved to `app/services/`. Backward-compatible aliases maintained for existing imports.
- `config_manager.py` — User profile adapter for `user_profile.json`, with compatibility migration from legacy local `keywords_config.json` and `user_config.json`.
- `state_store.py` — SQLite adapter. Tables: schema_meta, job_runs, research_collections, collection_papers, saved_searches, reading_queue_items, interaction_events, paper_ai_analyses, subscriptions, subscription_hits, recommendation_runs, recommendation_items.
- `app/services/` — 16 service modules: arxiv_source, scoring_service, semantic_similarity, citation_service, zotero_service, settings_service, feedback_service, feedback_learning_service, queue_service, library_service, monitor_service, paper_utils, recommendation_service, daily_pipeline, html_digest_service, digest_writer, ai_providers, ai_analysis_service, errors.
- `app/routes/` — 7 Flask blueprints: inbox, queue, library, monitor, settings, api, onboarding.
- `app/viewmodels/` — 7 viewmodel modules: inbox_viewmodel, queue_viewmodel, library_viewmodel, monitor_viewmodel, settings_viewmodel, search_viewmodel, shared.
- `templates/` and `static/` — Runtime UI assets (Jinja2 templates, CSS, JavaScript).
- `evaluation/` — Offline evaluation module: weak labels, NDCG/MRR/Precision@K metrics, ablation by signal type, CLI report generation.
- `tests/` — 106 tests across 13 test files. All passing.

## Data Flow

1. **Pipeline** (`app/services/daily_pipeline.py:run_pipeline()`): Fetches papers from the arXiv API using the user's configured keywords via `arxiv_source.py`.
2. **Scoring** (`app/services/scoring_service.py`): Scores fetched papers using keyword matching (title matches stronger than abstract, secondary topic boosts, demote/dislike penalties, theory keyword bonus). Optionally enriches scores via Zotero semantic similarity and feedback learning signals.
3. **Persistence**: Saves scored results to SQLite (`recommendation_runs` + `recommendation_items` tables) as the primary state.
4. **Digest generation**: Produces a Markdown digest and an HTML summary as export/cache artifacts.
5. **Page rendering**: The inbox route reads from SQLite first (fast path for the most recent run), falling back to parsing the Markdown digest file.
6. **User actions**: Feedback (likes, dislikes, demote), queue management, and library operations flow through their respective services (feedback_service, queue_service, library_service) and persist to SQLite plus the JSON feedback file.
7. **AI analysis** (optional): When configured, the pipeline additionally queries OpenAI or DeepSeek for paper summaries and relevance explanations. Results are cached to `paper_ai_analyses` table in SQLite to avoid redundant API calls.

## Current Architecture

### Entry Point

`web_server.py` is 92 lines and is deliberately kept thin. It initializes the Flask app, configures CORS, registers request logging middleware, registers all 7 blueprints, and starts the waitress production server (or Flask dev server when `USE_DEV_SERVER=1` is set). No route handlers, no page rendering logic, no background job orchestration.

### Route Layer (`app/routes/`)

7 blueprints, each thin: validate input, call service methods, assemble viewmodel, render template or return JSON.

- `inbox.py` — Home page, date-based digest view, search.
- `queue.py` — Reading queue CRUD and status management.
- `library.py` — Collections, favorites, paper metadata browsing.
- `monitor.py` — Subscriptions management, subscription hits, health checks.
- `settings.py` — User profile editing, keyword configuration, AI provider/API key settings.
- `api.py` — REST API endpoints for external integration.
- `onboarding.py` — First-run wizard for new users.

### Service Layer (`app/services/`)

16 modules containing all business logic, data fetching, and state manipulation:

- **Data ingestion**: `arxiv_source.py` (MultiSourceFetcher, PaperCache, search, metadata fetch).
- **Scoring and ranking**: `scoring_service.py` (EnhancedScorer, recommendation reason builder), `semantic_similarity.py` (embedding-based similarity).
- **External integrations**: `citation_service.py` (Semantic Scholar API), `zotero_service.py` (Zotero library path), `ai_providers.py` / `ai_analysis_service.py` (OpenAI/DeepSeek).
- **User state**: `settings_service.py` (profile load/save), `feedback_service.py` / `feedback_learning_service.py` (feedback persistence and heuristic learning).
- **Product features**: `queue_service.py`, `library_service.py`, `monitor_service.py`.
- **Pipeline and output**: `daily_pipeline.py` (orchestration), `recommendation_service.py` (state export/import), `html_digest_service.py`, `digest_writer.py`, `paper_utils.py`.
- **Error types**: `errors.py` (AppError hierarchy).

### ViewModel Layer (`app/viewmodels/`)

7 modules that transform service-layer data into template-ready structures. Each route blueprint delegates to its corresponding viewmodel module.

### State Management

- **SQLite** (`state_store.py`): Primary state store for durable workflow state: reading queue items, collections and their papers, saved searches, interaction events, subscription configurations and hits, recommendation runs and items, AI analysis cache, job run history. The `recommendation_items` table stores scored paper results per pipeline run.
- **JSON files**: `user_profile.json` stores user preferences and keyword profile. Not tracked in git. New installs start from `user_profile.example.json`.
- **Cache artifacts**: Markdown digests, HTML output, PDF downloads, pickle caches under `cache/`. These are derived artifacts, not primary state.

## Key Design Decisions

### SQLite as Primary State

All durable product workflow state (queue, library, subscriptions, recommendations, interactions) lives in a single SQLite database. The Markdown digest and HTML output are purely export/cache artifacts — the application reads from SQLite first. This eliminates the dual-source-of-truth problem that existed when JSON files and Markdown parsing were the primary read paths.

### Service Splitting

All behavior has been extracted from the monolithic files (`web_server.py` and `arxiv_recommender_v5.py`) into dedicated service modules under `app/services/`. Each service has a single responsibility. The original files now serve as re-export hubs for backward compatibility.

### Heuristic Ranking

Recommendation scoring remains heuristic: core keyword matches dominate, secondary topics add smaller boosts, demote/dislike topics apply penalties (softer when a core topic also matches), theory keywords add a bonus when enabled. This is simple, interpretable, and requires no training data.

### Optional AI Analysis

AI-powered paper analysis (OpenAI or DeepSeek) is optional and cached aggressively to SQLite. It runs as a post-scoring enrichment step, not as part of core ranking. This keeps the ranking deterministic and fast while allowing enhanced summaries when the user provides API keys.

### Evaluation Module

A standalone `evaluation/` module provides offline evaluation using weak labels, supporting NDCG, MRR, and Precision@K metrics with signal-type ablation. It generates CLI reports and does not affect production ranking.

## Completed Milestones

1. Service split — All business logic extracted from monoliths into `app/services/` with backward-compatible re-exports.
2. Route layer — All route handlers moved from `web_server.py` into 7 dedicated blueprint modules under `app/routes/`.
3. SQLite as primary state — Recommendation runs and items migrated to SQLite tables, read from SQLite first with Markdown fallback.
4. ViewModel layer — 7 viewmodel modules decoupling service output from template rendering.
5. Blueprint registration — All blueprints registered in `web_server.py` via factory pattern.
6. Pipeline isolation — `run_pipeline()` operates independently of Flask request cycle, callable from CLI or scheduler.
7. AI analysis support — Optional DeepSeek provider added alongside OpenAI, results cached in SQLite.
8. Evaluation infrastructure — Offline evaluation module with metrics, ablation, and CLI reporting.
9. CI/CD — GitHub Actions with ruff, mypy, bandit, pip-audit checks.
10. Production server — Waitress on localhost:5555 (Flask dev server fallback with `USE_DEV_SERVER=1`).
11. Onboarding wizard — First-run setup flow for new users.
12. 106 passing tests — Covering architecture integrity, service vertical slices, UI routes, AI analysis, onboarding, subscriptions, evaluation, digest, SQLite recommendation, and submission/repository hygiene.
