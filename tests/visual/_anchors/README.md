# `_anchors/` — historical reference screenshots

This directory is **NOT** part of the test suite. It holds screenshots
captured during product development for reference / discussion / archaeology.

**Do not add files here to `SURFACES` in `test_ui_anchor.py`.**

If a screenshot here corresponds to a UI state the team wants to anchor
on, the workflow is:

1. Recreate that state (e.g. `git checkout ui-v1.0`)
2. Run `python tests/visual/regenerate_goldens.py`
3. The output goes to `tests/visual/golden/`, which IS part of the suite

## Index

(empty — original session screenshots `today-dark.png` and
`today-mobile-375.png` were lost when the worktree they lived on was
deleted. The UI state they captured is preserved in commit `7ead51c`,
tag `ui-v1.0`. Re-render via `regenerate_goldens.py` against that tag
to materialize them.)
