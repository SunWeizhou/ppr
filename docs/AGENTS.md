# Agent Operating Guide

This repository is developed as a small product team. Keep PRs narrow and
product-led.

## Roles

- Product Manager Agent: owns the product line, IA, user flows, and acceptance
  criteria. Enforces Inbox First.
- Architect Agent: owns backend layering, directory structure, data model,
  migrations, and the gradual split of `web_server.py` and
  `arxiv_recommender_v5.py`.
- Backend Engineer Agent: owns Flask routes, services, SQLite state, APIs, task
  status, and import/export behavior.
- Frontend Engineer Agent: owns `templates/` and `static/`, shared UI
  components, and the Inbox / Queue / Library / Monitor / Settings navigation.
- ML / Recommendation Engineer Agent: owns scoring, Zotero similarity, feedback
  learning, and evaluation metrics.
- QA Engineer Agent: owns tests, CI, regression checks, local startup checks,
  configuration migration, state import/export, queue transitions, collection
  creation, and feedback normalization.

## PR Rules

Every PR must include:

- Goal
- Modified files
- Design notes
- Test notes
- Rollback risk
- Acceptance criteria

Prefer small PRs that preserve behavior. Add or update tests for every behavior
change or productization guard.

## Product Rules

- Inbox First: the home page only serves today's paper triage.
- Top-level navigation is Inbox / Queue / Library / Monitor / Settings.
- Search is contextual, not a top-level product destination.
- Do not add new top-level features before the existing workflow is stable.
- Collection creation must use a modal or drawer, not `window.prompt`.

## Architecture Rules

- SQLite is the target primary source for durable workflow state.
- JSON and Markdown files are caches, import/export artifacts, or display
  outputs unless explicitly documented otherwise.
- Keep the app local-first and easy to run.
- Do not introduce accounts, cloud sync, large frameworks, LLM summaries,
  citation graph rewrites, or a separate frontend application before the product
  skeleton is stable.
- Split large files gradually through services, repositories, models, and
  viewmodels. Do not do one large rewrite.
