# Release Checklist

Run before every release.

## 1. Tests

- [ ] `python -m pytest -q` passes.
- [ ] Focused product regression tests pass for repository hygiene, web
  productization, information architecture, paper detail, and paper viewmodels.

## 2. Lint and Security

- [ ] `ruff check app/ state_store.py config_manager.py web_server.py utils.py`
- [ ] `bandit -r app/ -ll -x tests/`
- [ ] `pip-audit -r requirements.txt`

## 3. Install and Start

- [ ] `pip install .` succeeds.
- [ ] `arxiv-recommender` starts and serves at http://localhost:5555.
- [ ] `USE_DEV_SERVER=1 python web_server.py` starts the dev server.

## 4. Agent Literature Assistant Acceptance

- [ ] Onboarding completes without editing local JSON by hand.
- [ ] Inbox loads a daily decision queue or a clear generation state.
- [ ] Search accepts a research question and returns persisted paper candidates.
- [ ] Paper Detail opens for a searched or recommended paper.
- [ ] Detail analysis distinguishes metadata, AI analysis, evidence, and user
  actions.
- [ ] Reading actions support Skim and Deep Read workflows.
- [ ] Watch shows subscriptions and recent hits.
- [ ] Settings supports profile edits, source/provider configuration, backup,
  restore, and diagnostics.
- [ ] The app works with no AI provider configured.
- [ ] API keys and secrets are never rendered in full, exported, or logged.

## 5. Data and Packaging

- [ ] Data export produces valid JSON.
- [ ] Data import restores state.
- [ ] `evaluation/run_evaluation.py` produces reports.
- [ ] Package includes templates, static files, and JavaScript modules.
- [ ] CSS and JS load correctly in browser.
