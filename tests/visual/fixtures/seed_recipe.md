# Visual test SQLite fixture (TODO)

This directory will hold a **frozen SQLite snapshot** that visual tests
load before each run, so goldens stay stable as live data evolves.

This is not yet wired up — it requires a small change to `app_paths.py`:

```python
# app_paths.py
import os
CACHE_DIR = Path(os.getenv("STATDESK_STATE_DIR") or PROJECT_ROOT / "cache")
STATE_DB_PATH = CACHE_DIR / "app_state.db"
```

Once that lands:

1. Capture a snapshot from your live state at the moment goldens were taken:
   ```bash
   cp cache/app_state.db tests/visual/fixtures/seed.sqlite
   ```
2. In `tests/visual/conftest.py`, set `STATDESK_STATE_DIR=tests/visual/fixtures`
   in the subprocess env before booting the app.
3. Document in `seed.sqlite.md` what data it contains (date, paper count, etc.).

Until that's done, visual tests use the live `cache/`. See `../README.md`
"Limitations".
