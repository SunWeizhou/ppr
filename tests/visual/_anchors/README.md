# `_anchors/` — Historical Reference Screenshots

This directory is not part of the visual regression suite. It holds screenshots
captured during product development for reference, discussion, and debugging.

Do not add files here to `SURFACES` in `_surfaces.py`.

If a screenshot here corresponds to a UI state that should become the active
baseline:

1. Recreate that state from the relevant commit.
2. Run `python tests/visual/regenerate_goldens.py`.
3. Commit the generated files under `tests/visual/golden/`.

## Index

### `today-dark-2026-04-29.png` (1440x900)

Historical Today page dark-mode screenshot captured on 2026-04-29 during a
product audit. It remains useful as design context but is not itself a test
golden.

Visible traits:
- Top navigation with Today, Reading, and Watch.
- Dark-mode daily triage surface.
- Date strip and paper cards with decision actions.

### `today-mobile-375-broken.png` (375x812)

Mobile viewport from the same audit. Not a golden. It captures an old responsive
layout problem and should not be used as a regression target.
