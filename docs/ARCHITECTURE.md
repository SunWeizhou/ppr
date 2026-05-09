# Architecture

This project is a local-first Agent literature research assistant. The runtime
architecture supports a research loop from intent definition to candidate
discovery, paper analysis, reading decisions, saved assets, and long-term
monitoring.

## Product Overview

The application:

- Fetches arXiv papers from user profile keywords and explicit search queries.
- Scores candidates using interpretable heuristic ranking, optional Zotero
  similarity, and feedback signals.
- Persists recommendations, paper metadata, reading state, collections,
  subscriptions, interaction events, and AI analysis cache in SQLite.
- Renders Inbox, Search, Paper Detail, Reading, Watch, Settings, Evaluation,
  and Onboarding surfaces through Flask templates.
- Provides optional OpenAI-compatible or DeepSeek AI analysis. The core product
  must still work when no AI key is configured.
- Generates Markdown, HTML, and cache artifacts as derived outputs rather than
  primary state.

## Directory Structure

- `web_server.py` — thin Flask entrypoint: app initialization, middleware,
  blueprint registration, and server startup.
- `arxiv_recommender_v5.py` — backward-compatible re-export hub for service
  imports.
- `config_manager.py` — user profile adapter for `user_profile.json`, with
  compatibility migration from older local config files.
- `state_store.py` — SQLite adapter for workflow and recommendation state.
- `app/services/` — business logic, external sources, scoring, queue/library
  operations, monitoring, AI provider integration, digest generation, and
  evaluation support.
- `app/routes/` — Flask blueprints for Inbox/Search/Detail, Reading, Library
  compatibility, Watch, Settings, API, and Onboarding.
- `app/viewmodels/` — template-ready context builders for page surfaces.
- `templates/` and `static/` — Jinja2 templates, CSS, and JavaScript.
- `evaluation/` — offline evaluation support for ranking metrics and reports.
- `tests/` — unit, integration, productization, and visual regression tests.

## Data Flow

1. **Research intent**
   - User profile keywords, explicit search queries, and saved subscriptions
     define what the system should discover or monitor.

2. **Candidate discovery**
   - `app/services/arxiv_source.py` and compatibility exports fetch papers from
     arXiv by profile or query.

3. **Ranking**
   - `app/services/scoring_service.py` ranks papers using keyword relevance,
     configured weights, feedback penalties or boosts, and optional similarity
     signals.

4. **Persistence**
   - `state_store.py` stores recommendation runs, paper metadata, queue items,
     collections, subscriptions, hits, interaction events, and AI analyses in
     SQLite.

5. **Analysis**
   - `app/services/ai_analysis_service.py` optionally requests structured paper
     analysis and caches the result. Without a provider, the app falls back to
     metadata, abstracts, and rule-based explanations.

6. **Rendering**
   - Routes call services and viewmodels, then render templates. Search results
     are saved to metadata so detail pages can open after discovery.

7. **User decisions**
   - Ignore, Skim, Deep Read, Save, collection actions, and subscription routing
     persist as state and become future ranking or monitoring signals.

## Runtime Surfaces

- **Inbox**: daily decision queue generated from recommendation runs.
- **Search / Explore**: ad hoc research-question discovery and saved query
  creation.
- **Paper Detail**: structured paper context, analysis, evidence, and actions.
- **Reading**: active reading workbench for skim and deep-read states.
- **Watch**: subscription management and recent hits.
- **Settings**: profile, source, AI provider, backup, restore, and diagnostics.
- **Evaluation**: offline ranking reports and quality checks.

## State Management

- **SQLite** (`cache/app_state.db` by default): primary durable workflow state.
- **Profile JSON** (`user_profile.json`): local user preferences and keywords.
- **Derived artifacts** (`cache/`, `history/`, `reports/`): regenerated outputs,
  exports, or diagnostics. They are not primary state.

SQLite is the source of truth for product workflow state. Markdown digests,
HTML files, and search caches should not become competing state sources.

## Key Design Decisions

### Local First

User data stays on disk. The product should not require accounts, cloud sync, or
hosted state to complete its core workflow.

### Explainable Ranking

Ranking remains interpretable. Keyword, topic, feedback, and subscription
signals should be visible enough for the user to understand why a paper was
surfaced.

### Optional AI

AI analysis is an enhancement, not a hard dependency. The product should remain
usable with no provider configured, and secrets must never be rendered in full
or exported unintentionally.

### Thin Routes, Testable Services

Routes should validate request input, call services, build viewmodels, and
render responses. Business behavior belongs in services and state adapters where
it can be tested without a browser.
