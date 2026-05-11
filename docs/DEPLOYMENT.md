# Deployment Guide

Paper Agent is a local-first paper discovery and research workspace. Three
deployment options are supported.

## Option 1: Source Run

Recommended for daily local use.

```bash
git clone <repo-url> && cd arxiv_recommender
python -m pip install -r requirements.txt -c constraints.txt
cd frontend/agent && npm ci && npm run build && cd ../..
bash scripts/start_local.sh
```

Open http://localhost:5555, complete onboarding, then search from the Paper
Agent workspace.

Stop with `Ctrl+C`.

## Option 2: pip Install

```bash
pip install .
cd frontend/agent && npm ci && npm run build && cd ../..
arxiv-recommender
```

Open http://localhost:5555.

## Option 3: Docker

```bash
docker compose up
```

Open http://localhost:5555.

Stop with:

```bash
docker compose down
```

## First Run

On first launch, the onboarding wizard at `/onboarding` guides you through:

1. Research topics and priority keywords.
2. Optional scholar profiles (Google Scholar author IDs).
3. First research question — creates an initial query subscription.

After onboarding, you land on the Search workspace (`/`). All configuration can
be changed later in Settings.

## Frontend Assets

The main app uses Flask/Jinja2 server rendering with a unified CSS design
token system. The Agent panel is a standalone Preact application compiled
into `static/dist/agent-panel.js` and `static/dist/agent-panel.css`.

Build the Agent panel after cloning or updating:

```bash
cd frontend/agent && npm ci && npm run build
```

The build produces a single JS + CSS bundle (~50KB gzip). Jinja2 templates
load these assets automatically. Rebuild whenever files under `frontend/agent/`
change.

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_COMPATIBLE_API_KEY` | API key for OpenAI-compatible provider | (none) |
| `DEEPSEEK_API_KEY` | Shorthand for DeepSeek preset | (none) |
| `STATDESK_AI_API_KEY` | Legacy backward-compatible key | (none) |
| `USE_DEV_SERVER` | Use Flask dev server instead of waitress | (unset = waitress) |
| `PORT` or `FLASK_RUN_PORT` | Server port | 5555 |
| `OPENALEX_MAILTO` | Email for OpenAlex polite pool (higher rate limits) | (none) |

All environment variables are optional. The product works without any of them
configured.

## Configuration

### AI Provider

AI is optional. The core workflow functions without an API key.

1. Go to Settings.
2. Open the AI Provider tab.
3. Select `none` or OpenAI-compatible.
4. Enter the API key (or set via environment variable).
5. Save and test the connection.

Key precedence (first found wins):

1. `OPENAI_COMPATIBLE_API_KEY`
2. `DEEPSEEK_API_KEY`
3. `STATDESK_AI_API_KEY`

DeepSeek is a preset for OpenAI-compatible (base_url: `https://api.deepseek.com`,
model: `deepseek-chat`).

### Search Sources

Search queries arXiv, Semantic Scholar, and OpenAlex in parallel. All sources
are optional — the system degrades gracefully if any source is unavailable.
Set `OPENALEX_MAILTO` to your email for higher OpenAlex rate limits (polite
pool).

### Backup and Restore

- Backup: Settings → Diagnostics → Backup.
- Restore: Settings → Diagnostics → Restore.
- Database maintenance: Settings → Diagnostics → Vacuum Database.
- Full export: `GET /api/state/export` returns JSON snapshot.
- Full import: `POST /api/state/import` restores from snapshot.

### Data Locations

| File / Directory | Purpose |
| --- | --- |
| `user_profile.json` | Keywords, preferences, and local profile |
| `cache/app_state.db` | SQLite primary state (all workflow data) |
| `cache/daily_recommendation.json` | Today's cached recommendation |
| `reports/` | Evaluation reports |
| `history/` | Digest markdown history |
| `static/dist/` | Built Agent panel assets (Preact) |

## Troubleshooting

### Search or preview returns no candidates

1. Try a shorter query with concrete method, task, author, or paper keywords.
2. Check network access to arxiv.org and semanticscholar.org.
3. Inspect `/settings?tab=diagnostics` for source health.

### Entity profiles show no data

1. Entities are created on-demand from search results. Search for papers first.
2. Check `/api/entities?type=journal` to verify entities exist.
3. For manually created subscriptions, entity metadata is fetched from OpenAlex.
4. Run `POST /api/entities/sync` to refresh metadata for subscribed entities.

### AI analysis not working

1. Verify the OpenAI-compatible base URL, model, and API key in Settings.
2. Use the connection test button.
3. Continue without AI if needed; the app falls back to abstracts and rule-based
   evidence.

### Background job stuck

1. Check `/api/job/status` for latest job state.
2. If status is `running` for over 2 hours, restart the server — stale recovery
   will mark it as failed.
3. Re-trigger with `POST /api/refresh`.

### Database errors

1. Use Settings → Diagnostics → Vacuum Database.
2. Back up local files before manual repair.
3. If needed, remove `cache/app_state.db`; it will be recreated, but local
   workflow history in that database will be lost.
