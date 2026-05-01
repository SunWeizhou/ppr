# Visual Regression Tests

Anchored to the **`ui-v1.0`** tag — the favorite UI baseline (`7ead51c`,
"ui: restore old topbar layout (no sidenav) on pr-recommender-redesign").

These tests catch UI regressions by screenshotting each surface and
diffing pixel-by-pixel against a golden PNG.

## Quick start

```bash
# 1. Install dev deps
pip install -r requirements-test.txt
python -m playwright install chromium

# 2. Generate goldens against the favorite UI
git checkout ui-v1.0
python tests/visual/regenerate_goldens.py
git checkout main
git add tests/visual/golden/
git commit -m "test(visual): seed goldens from ui-v1.0"

# 3. Run tests
pytest tests/visual/ -v
```

## Layout

```
tests/visual/
├── README.md                   # this file
├── conftest.py                 # boots the app on a test port; provides fixtures
├── test_ui_anchor.py           # parametrized tests over SURFACES
├── regenerate_goldens.py       # CLI to (re)create goldens
├── golden/                     # committed; the baseline PNGs
│   ├── today-desktop-light.png
│   ├── today-desktop-dark.png
│   ├── reading-desktop-dark.png
│   ├── watch-desktop-dark.png
│   └── settings-desktop-dark.png
├── fixtures/                   # for future SQLite-fixture isolation
├── diff/                       # gitignored; written on test failure
│   ├── <name>-actual.png
│   ├── <name>-golden.png
│   └── <name>-diff.png         # amplified diff visualization
└── _anchors/                   # historical reference screenshots
```

## When a test fails

PR CI uploads `tests/visual/diff/` as a build artifact. Open the three
images side-by-side:

- `*-golden.png` — what we anchored to
- `*-actual.png` — what your branch renders
- `*-diff.png`   — pixel deltas amplified 4×; black means identical

If the change is **intentional** (you meant to redesign the surface),
regenerate the golden:

```bash
python tests/visual/regenerate_goldens.py --name today-desktop-dark
git add tests/visual/golden/today-desktop-dark.png
git commit -m "test(visual): update golden — intentional redesign"
```

If the change is **unintentional**, that's the regression — fix the code.

## Why mobile (375px) is NOT a golden

The repo had a screenshot `today-mobile-375.png` from a Phase-3 audit. That
screenshot captured a **known broken state** (4 actions stacked vertically,
top bar overflow). Pinning it as a golden would freeze those bugs in place.

Mobile goldens should only be added **after** the responsive layout is
fixed. Track that work separately; do not add mobile to `SURFACES` in
`test_ui_anchor.py` until then.

## Threshold

Default: 1% of pixels allowed to differ. Override with:

```bash
STATDESK_VISUAL_THRESHOLD=0.005 pytest tests/visual/
```

Why 1%:
- tighter (e.g. 0.1%) trips on font antialiasing differences between OS
  and Chromium minor versions
- looser (e.g. 5%) misses real layout regressions like "sidenav came back"

## Limitations (TODO)

1. **No data isolation.** Tests run against the live `cache/app_state.db`.
   If your DB content changes (new papers fetched, you mark something
   relevant), the goldens drift and tests fail. Workarounds today:
   - Run tests against a stable checkout (e.g. `ui-v1.0` for both golden
     and test) by using `--reuse` in the regen script
   - Manually freeze: copy `cache/app_state.db` to `fixtures/seed.sqlite`
     and document what's in it

   Long-term fix: add `STATDESK_STATE_DIR` env var to `app_paths.py` so
   tests can point at `tests/visual/fixtures/`.

2. **Date sensitivity.** The "Today" page hero shows the current date,
   so goldens captured on 2026-04-29 will diff vs renders on later
   dates. Long-term fix: add `STATDESK_FROZEN_DATE` env var the app
   respects.

3. **AI provider calls.** If the AI Analysis tab tries to hit DeepSeek
   during a screenshot, the test will be flaky. The `app_url` fixture
   doesn't set `DEEPSEEK_API_KEY`, so the no-provider fallback path
   should kick in — but if you have it set globally, unset before
   running visual tests.
