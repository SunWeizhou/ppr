# `_anchors/` — historical reference screenshots

This directory is **NOT** part of the test suite. It holds screenshots
captured during product development for reference / discussion / archaeology.

**Do not add files here to `SURFACES` in `_surfaces.py`.**

If a screenshot here corresponds to a UI state we want to anchor on, the
workflow is:

1. Recreate that state (e.g. `git checkout ui-v1.0`)
2. Run `python tests/visual/regenerate_goldens.py`
3. The output goes to `tests/visual/golden/`, which IS part of the suite

## Index

### `today-dark-2026-04-29.png` (1440×900)

The favorite UI — Today page, dark mode, captured 2026-04-29 during the
Phase 3 audit. This screenshot is what motivated tag `ui-v1.0`. The
exact source code that rendered it is preserved at commit `7ead51c`,
which `ui-v1.0` points to.

Distinguishing features visible:
- Top bar: StatDesk wordmark + Today / Reading / Watch nav, no sidenav
- Top right: EN/中, 亮色 (light mode toggle), ⌘K, ⚙
- "Daily Triage" kicker + serif date heading, "Regenerate" button right
- 11-day date strip (24 APR — 04 MAY) with selected date highlighted
- Per-paper card: category chips, serif title, muted authors,
  abstract excerpt, italic Why-line, 5 ghost actions
  (Relevant / Skim Later / Deep Read / Ignore / Detail)

### `today-mobile-375-broken.png` (375×812)

Mobile viewport from the same audit. **NOT a golden** — captures a
known-broken state where:
- top bar overflows horizontally (lang/dark/⌘K/⚙ all cut off)
- 4 actions stack vertically, eating most of the viewport per card

Kept here as evidence for the responsive-layout work that should
eventually fix this. Do not pin it as a regression target — when mobile
is fixed, regenerate a fresh mobile golden in `golden/`.

## Why these are here

Both screenshots were originally written to the project root by the
Phase 3 audit. When the worktree they lived in was deleted, they
appeared to be lost — but git auto-stashed them before the worktree
purge (`stash@{0}^3`, commit `8fe27d2`). They were resurrected from
that stash and committed here so they're never lost again.
