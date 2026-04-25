# Architecture

This project is a local-first arXiv research triage desk. The product goal is
not to show more papers; it is to help a researcher triage today's papers,
manage a reading queue, preserve long-lived research assets, and monitor
authors, venues, and queries.

## Current Architecture

- `web_server.py` is the Flask entrypoint and currently owns too many
  responsibilities: route handlers, API handlers, page view-model assembly,
  JSON file persistence, background recommendation jobs, import/export, search,
  settings, scholars, journals, and stats.
- `arxiv_recommender_v5.py` currently owns most recommendation engine behavior:
  arXiv identity parsing, source fetching, Zotero path detection, semantic
  similarity, paper caches, scoring, feedback learning, HTML/Markdown generation,
  search, and daily pipeline execution.
- `state_store.py` is the SQLite adapter for product state such as jobs,
  collections, saved searches, reading queue items, and interaction events.
- `config_manager.py` is the user profile adapter for `user_profile.json`, with
  compatibility migration from legacy local `keywords_config.json` and
  `user_config.json`.
- `templates/` and `static/` are the canonical runtime UI assets. Legacy
  generated root HTML files are not the target UI architecture.

## Target Architecture

The target structure should be introduced gradually under `app/` or
`src/paper_recommender/` without changing visible behavior in a single large PR:

```text
routes/
  inbox.py
  queue.py
  library.py
  monitor.py
  settings.py
  api.py
services/
  recommendation_service.py
  queue_service.py
  library_service.py
  monitor_service.py
  settings_service.py
  feedback_service.py
repositories/
  state_repository.py
  config_repository.py
models/
viewmodels/
  inbox_viewmodel.py
  queue_viewmodel.py
  library_viewmodel.py
```

Flask routes should stay thin: validate input, call services, and return JSON or
render templates. Product decisions and state transitions belong in services.
SQLite access belongs behind repositories or the existing `StateStore` adapter.

## State and Data Sources

SQLite is the target primary state source for durable product workflow state:
reading queue, collections, saved searches, interaction events, job state, and
future evaluation labels.

Local files have narrower roles:

- `user_profile.json`: private local user settings and ranking profile. It is
  not tracked in git. New installs start from `user_profile.example.json`.
- `cache/`: runtime cache only. JSON, pickle, SQLite temp files, PDFs, and
  recommendation runs are generated artifacts.
- `history/` and `daily_arxiv_digest.md`: generated display/export artifacts,
  not source data.
- Markdown and JSON exports may be used for import/export, reports, or human
  review, but they must not become competing primary state sources.

External sources are read-through inputs: arXiv, Zotero, journal pages, scholar
queries, and saved query subscriptions.

## Recommendation Behavior to Preserve

Before the evaluation module exists, keep the current ranking behavior stable:

- Core keyword matches dominate, with title matches stronger than abstract
  matches.
- Secondary topics add smaller boosts.
- Demote and dislike topics penalize results, with softer penalties when a core
  topic also matches.
- Theory keywords add a bonus when theory ranking is enabled.
- Zotero semantic similarity is optional and only applies when Zotero papers and
  embeddings are available.
- Feedback learning is heuristic signal extraction from local cached papers and
  stable arXiv IDs. It is not a trained recommender model.

## Service Split Plan

1. Extract pure identity and normalization helpers first.
2. Extract feedback and queue operations behind services while keeping existing
   JSON and SQLite backing stores.
3. Move recommendation run orchestration out of Flask into
   `RecommendationService`.
4. Move search and saved-search execution into a search or monitor service.
5. Move settings/profile writes into `SettingsService`.
6. After behavior parity, decide which remaining JSON caches become SQLite
   tables and which remain explicit caches or exports.

Each split must be small, tested, and behavior-preserving.
