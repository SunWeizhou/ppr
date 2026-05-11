# Release Checklist

Run before every release.

## 1. Tests

- [ ] `python -m pytest -q` passes.
- [ ] `npm ci`, `npm run lint`, and `npm run build` pass for the Agent drawer island.
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

## 4. Paper Agent Acceptance

- [ ] Onboarding completes without editing local JSON by hand.
- [ ] `/` renders the Search workspace with a single search bar, result list, and right preview.
- [ ] Search accepts a paper, author, or topic query and returns persisted paper candidates.
- [ ] arXiv and Semantic Scholar degraded states are shown independently.
- [ ] Clicking a result updates the right preview without navigation.
- [ ] Preview actions support Save, Mark Skim, Deep Read, Create Watch, and Open full detail.
- [ ] `/recommendations` renders candidate sets with why-recommended context and decision actions.
- [ ] Paper Detail opens for a searched or watched paper and preserves return query context.
- [ ] Paper Detail shows the full abstract by default, never a truncated fetch preview.
- [ ] Detail analysis distinguishes metadata, AI analysis, evidence, and user
  actions.
- [ ] Reading actions support Skim Later, Deep Read, Saved, Archived, Collections, and notes.
- [ ] Watch shows only real subscriptions and real hits, with source health.
- [ ] Settings supports profile edits, OpenAI-compatible provider configuration,
  source diagnostics, backup, restore, and local DB health.
- [ ] Agent drawer renders Markdown safely, can chat, search, save, mark reading
  decisions, create watches, create collections, open recommendations, and
  summarize selected papers.
- [ ] Agent with no selected paper returns a helpful fallback (not an error or crash).
- [ ] The app works with no AI provider configured.
- [ ] API keys and secrets are never rendered in full, exported, or logged.
- [ ] Left sidebar navigation renders with all sections (Search, Library, Recommendations, Watch, Reading, Subscriptions, Settings, Agent Sessions).
- [ ] Light/dark mode toggle works on all pages with consistent design tokens.
- [ ] Breathing grid background animates in light and dark modes, and is static with prefers-reduced-motion.

## 5. Settings, AI Provider, and Diagnostics

- [ ] `/settings?tab=profile` edits research topics without breaking existing workspace state.
- [ ] `/settings?tab=ai` never renders raw API keys in the HTML.
- [ ] AI provider can be disabled; disabling clears stored keys and leaves rule-based evidence available.
- [ ] AI provider can use `OPENAI_COMPATIBLE_API_KEY`, `DEEPSEEK_API_KEY`, or backward-compatible `STATDESK_AI_API_KEY`.
- [ ] `/settings?tab=diagnostics` shows profile, AI, source health, workspace, queue, local DB identity, and latest job readiness.
- [ ] Onboarding first query creates a `ResearchQuestion` and a query subscription bound to it.

## 6. Background Jobs and Subscriptions

- [ ] `POST /api/refresh` creates a background job that transitions to succeeded or failed.
- [ ] `POST /api/subscriptions/run-all` runs active subscriptions and produces hits.
- [ ] Stale jobs are recovered on server startup (no job blocks future runs).
- [ ] `GET /api/job/status` returns the latest job with correct status.

## 7. Evaluation and Workspaces

- [ ] `/evaluation` renders the evaluation dashboard and can list reports.
- [ ] Creating a research question via onboarding or API succeeds.
- [ ] Running the workspace planner (`POST /api/workspaces/questions/<id>/planner-runs`) produces a recommendation run.
- [ ] `evaluation/run_evaluation.py` produces reports without timeout.

## 8. Entity System

- [ ] `/entities/<id>` renders profile pages for all 4 types (journal, conference, scholar, field).
- [ ] Creating a subscription linked to an entity populates `entity_id` in the subscriptions table.
- [ ] Entity profile shows metadata, related papers, and related entities.
- [ ] Search results auto-extract venue/author entities (check entities table after a search).
- [ ] `POST /api/entities/sync` updates metadata for subscribed entities.
- [ ] Entity auto-creation from search does not block or slow search response.

## 9. Agent Sessions

- [ ] `POST /api/agent/sessions` creates a new session with UUID.
- [ ] `GET /api/agent/sessions` lists sessions (default excludes archived).
- [ ] `POST /api/agent/sessions/<id>/messages` sends a message and returns assistant reply with tool results.
- [ ] Multi-turn conversation context is maintained (Agent references earlier messages in session).
- [ ] Session auto-title generates a meaningful title after first message.
- [ ] Agent panel opens from floating button, displays session list and message flow.
- [ ] Agent panel closes with Escape key.
- [ ] Agent executes multi-step chains (e.g., "search X and create watch" runs both actions).
- [ ] Sessions persist across page navigation and server restarts.
- [ ] Agent works with no AI provider (keyword intent classification, rule-based titles).

## 10. Search Enhancement

- [ ] Search returns results from arXiv, Semantic Scholar, and OpenAlex.
- [ ] OpenAlex results are normalized and deduplicated with other sources.
- [ ] Semantic Scholar failures are handled gracefully (timeout, retry, cache failure state).
- [ ] Search history dropdown appears on search input focus with recent queries.
- [ ] Filter chips (year, source, venue type) filter the result list client-side.
- [ ] Query rewriting shows explanation below search bar when active.
- [ ] Query rewriting is silently skipped when no AI provider is configured.

## 11. Browser and Visual QA

- [ ] Browser smoke covers `/`, `/?q=federated%20learning`, `/recommendations`, `/papers/<id>?return_q=federated%20learning`, `/reading`, `/watch`, `/settings?tab=ai`, and `/settings?tab=diagnostics`.
- [ ] Desktop viewport has no console errors, no external CDN failures, and preview updates without navigation.
- [ ] Mobile viewport has no horizontal overflow.
- [ ] No stale legacy product names, navigation labels, or fixture copy appears in active UI.
- [ ] Visual tests are either passing against committed goldens or explicitly skipped because no goldens are committed.

## 12. Data and Packaging

- [ ] Data export produces valid JSON.
- [ ] Data import restores state.
- [ ] Package includes templates, static files, and JavaScript modules.
- [ ] CSS and JS load correctly in browser.
- [ ] Chinese and English UI text is consistent within each language context.
