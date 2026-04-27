# Release Checklist

Run before every release.

## 1. Tests
- [ ] `python -m unittest discover -s tests -v` — all pass

## 2. Lint & Security
- [ ] `ruff check app/ state_store.py config_manager.py web_server.py utils.py`
- [ ] `bandit -r app/ -ll -x tests/`
- [ ] `pip-audit -r requirements.txt`

## 3. Install & Start
- [ ] `pip install .` succeeds
- [ ] `arxiv-recommender` starts and serves at http://localhost:5555
- [ ] `USE_DEV_SERVER=1 python web_server.py` starts dev server

## 4. Functional Checks
- [ ] Onboarding completes without error
- [ ] Today's recommendations generate without crash
- [ ] Inbox triage actions (Relevant/Ignore/Queue) record in interaction_events
- [ ] Paper Detail page opens for any recommended paper
- [ ] AI Analysis generates with configured provider, or graceful fallback without key
- [ ] Data export produces valid JSON
- [ ] Data import restores state
- [ ] `evaluation/run_evaluation.py` produces reports

## 5. Packaging
- [ ] `pip install .` includes all templates, static files, JS modules
- [ ] `arxiv-recommender` CLI entry point works
- [ ] CSS and JS load correctly in browser
