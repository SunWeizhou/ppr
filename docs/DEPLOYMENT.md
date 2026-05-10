# Deployment Guide

Agent Literature Research Assistant is a local-first application. Three
deployment options are supported.

## Option 1: Source Run

Recommended for daily local use.

```bash
git clone <repo-url> && cd arxiv_recommender
bash scripts/start_local.sh
```

Open http://localhost:5555, complete onboarding, then run a search or generate
recommendations.

Stop with `Ctrl+C`.

## Option 2: pip Install

```bash
pip install .
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

## Configuration

### AI Analysis

AI analysis is optional. The core workflow should function without an API key.

1. Go to Settings.
2. Open the AI provider or diagnostics section.
3. Select the provider, base URL, and model.
4. Enter the API key.
5. Save and test the connection.

### Backup and Restore

- Backup: Settings -> diagnostics or system tools -> Backup.
- Restore: Settings -> diagnostics or system tools -> Restore.
- Database maintenance: Settings -> diagnostics or system tools -> Vacuum
  Database.

### Data Locations

| File / Directory | Purpose |
| --- | --- |
| `user_profile.json` | Keywords, preferences, and local profile |
| `user_config.json` | Compatibility app configuration |
| `keywords_config.json` | Compatibility keyword weights |
| `cache/app_state.db` | SQLite primary state |
| `reports/` | Evaluation reports |
| `history/` | Digest markdown history |

## Troubleshooting

### No recommendations generated

1. Check Settings -> Profile and confirm core keywords exist.
2. Verify the machine can reach arxiv.org.
3. Use Settings -> Profile to save changes and regenerate recommendations.

### Search returns no candidates

1. Try a shorter query with concrete method or task keywords.
2. Check network access to arxiv.org.
3. Inspect logs for arXiv API errors.

### AI analysis not working

1. Verify the provider, base URL, model, and API key in Settings.
2. Use the connection test.
3. Continue without AI if needed; the app should fall back to abstracts and
   rule-based explanations.

### Database errors

1. Use Settings -> diagnostics or system tools -> Vacuum Database.
2. Back up local files before manual repair.
3. If needed, remove `cache/app_state.db`; it will be recreated, but local
   workflow history in that database will be lost.
