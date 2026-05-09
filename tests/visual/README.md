# Visual Regression Tests

Visual tests screenshot selected product surfaces and compare them
pixel-by-pixel against committed golden PNGs.

## Quick Start

```bash
pip install -r requirements-test.txt
python -m playwright install chromium
python tests/visual/regenerate_goldens.py
pytest tests/visual/ -v
```

When a product redesign intentionally changes a surface, regenerate only the
affected golden and commit it with the implementation change:

```bash
python tests/visual/regenerate_goldens.py --name today-desktop-dark
git add tests/visual/golden/today-desktop-dark.png
git commit -m "test(visual): update golden for intentional redesign"
```

## Layout

```text
tests/visual/
├── README.md
├── conftest.py
├── test_ui_anchor.py
├── regenerate_goldens.py
├── golden/
├── fixtures/
├── diff/
└── _anchors/
```

## When a Test Fails

CI uploads `tests/visual/diff/` as a build artifact. Compare:

- `*-golden.png` — committed baseline
- `*-actual.png` — current render
- `*-diff.png` — amplified pixel delta

If the change is intentional, update the relevant golden. If it is not
intentional, fix the implementation.

## Threshold

Default: 1% of pixels may differ. Override with:

```bash
STATDESK_VISUAL_THRESHOLD=0.005 pytest tests/visual/
```

## Limitations

1. Tests currently run against local app state. A stable fixture database should
   replace live runtime state.
2. Date-sensitive copy can change screenshots over time.
3. AI provider calls should stay disabled during screenshot tests.
