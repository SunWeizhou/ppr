# Deployment Guide

arXiv Recommender is a local-first application. Three deployment options:

## Option 1: Source Run (recommended for daily use)

### Install & Start
```bash
git clone <repo-url> && cd arxiv_recommender
bash scripts/start_local.sh
```

### Usage
- Open http://localhost:5555
- Complete onboarding wizard
- Generate your first recommendations

### Stop
Press `Ctrl+C` in the terminal.

### Backup
Settings → System tab → Backup Now

### Restore
Settings → System tab → Restore from Backup

---

## Option 2: pip install

```bash
pip install .
arxiv-recommender
```

Open http://localhost:5555.

---

## Option 3: Docker

```bash
docker compose up
```

Open http://localhost:5555.

### Stop
```bash
docker compose down
```

---

## Configuration

### DeepSeek AI Analysis
1. Go to Settings → System tab → AI Analysis section
2. Select "DeepSeek" as provider
3. Enter your API key, base URL (`https://api.deepseek.com`), and model (`deepseek-chat`)
4. Click "Save" then "Test Connection"

The app works fully without AI analysis — this feature is optional.

### Data Locations
| File / Directory | Purpose |
|-----------------|---------|
| `user_profile.json` | Keywords and preferences |
| `user_config.json` | App configuration |
| `keywords_config.json` | Keyword weights |
| `cache/app_state.db` | SQLite primary state (recommendations, queue, collections, subscriptions) |
| `reports/` | Evaluation reports |
| `history/` | Digest markdown history |

## Troubleshooting

### "No recommendations generated"
1. Check Settings → Profile tab — ensure core keywords are configured
2. Verify your network can reach arxiv.org
3. Try: Settings → Profile → Save and Regenerate

### "AI Analysis not working"
1. Verify API key in Settings → System → AI Analysis
2. Use the "Test Connection" button to verify
3. The app works fine without AI — this is optional

### Database errors
1. Go to Settings → System
2. Click "Vacuum Database"
3. If still broken, delete `cache/app_state.db` (it will be recreated — you'll lose recommendation history but keep keyword profiles)
