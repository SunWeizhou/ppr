# Product Stability & Launch Readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the functional arXiv paper recommendation prototype into a stable, installable, backupable, distributable local research workflow product.

**Architecture:** Phase-by-phase execution with 3-4 parallel agents per phase. Each agent handles a self-contained task with no file conflicts. Validation gate (unit tests + ruff) runs after every phase.

**Tech Stack:** Python/Flask, SQLite (primary state), Jinja2 templates, vanilla JS, CSS custom properties

---

## Phase 0 — Blocking Fixes (3 parallel tasks)

### Task 0.1: Fix AI Analysis context completion

**Files:**
- Modify: `app/routes/api/ai.py:16-49`

- [ ] **Step 1: Rewrite `generate_paper_analysis` to auto-resolve paper context**

Replace the entire `generate_paper_analysis` function in `app/routes/api/ai.py`:

```python
@bp.post("/api/papers/<paper_id>/analysis/generate")
def generate_paper_analysis(paper_id):
    from state_store import _canonical_paper_id

    canonical_id = _canonical_paper_id(paper_id)
    service = _ai_analysis_service()
    data = request.get_json() or {}

    # Resolve full paper context from SQLite (primary) or Markdown history (fallback)
    paper = _resolve_paper_context(canonical_id)

    if not paper:
        return jsonify({"success": False, "error": "Paper not found"}), 404

    # Merge any frontend-provided overrides (user_profile, recommendation_context)
    user_profile = data.get("user_profile")

    # Build structured recommendation reason
    recommendation_reason = None
    try:
        from app.services.scoring_service import build_recommendation_reason

        recommendation_reason = build_recommendation_reason(
            paper,
            user_profile=user_profile,
        )
    except Exception:
        pass

    try:
        analysis = service.get_or_create_analysis(
            paper,
            user_profile=user_profile,
            recommendation_context=data.get("recommendation_context"),
            force=bool(data.get("force", False)),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    result = {"success": True, "analysis": analysis}
    if recommendation_reason:
        result["recommendation_reason"] = recommendation_reason
    return jsonify(result)


def _resolve_paper_context(paper_id: str) -> dict | None:
    """Resolve full paper context from SQLite recommendation_items or Markdown history fallback."""
    from state_store import get_state_store

    store = get_state_store()

    # 1) Search SQLite recommendation_items (primary)
    try:
        runs = store.list_recommendation_runs(limit=10)
        for run in runs:
            items = store.get_recommendation_items(run["run_id"])
            for item in items:
                if item.get("paper_id") == paper_id:
                    return _build_paper_dict(item)
    except Exception:
        pass

    # 2) Fallback to Markdown history
    import os
    from app_paths import HISTORY_DIR

    if os.path.exists(str(HISTORY_DIR)):
        for fname in sorted(os.listdir(str(HISTORY_DIR)), reverse=True):
            if not fname.startswith("digest_") or not fname.endswith(".md"):
                continue
            filepath = os.path.join(str(HISTORY_DIR), fname)
            try:
                from app.viewmodels.inbox_viewmodel import InboxViewModel

                papers, _ = InboxViewModel.parse_digest(filepath, use_cache=False)
                for p in papers:
                    if (p.get("id") or "") == paper_id:
                        return _build_paper_dict(p)
            except Exception:
                continue

    return None


def _build_paper_dict(item: dict) -> dict:
    """Normalize a paper record into a dict with expected keys for AI analysis."""
    import json

    paper = dict(item)
    paper["id"] = paper.get("paper_id") or paper.get("id") or ""

    # Parse JSON fields
    for field in ("authors_json", "categories_json"):
        raw = paper.pop(field, None)
        if isinstance(raw, str):
            try:
                paper[field.replace("_json", "s")] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                paper[field.replace("_json", "s")] = []
        elif isinstance(raw, list):
            paper[field.replace("_json", "s")] = raw

    # Ensure title, abstract, authors are present
    paper.setdefault("title", "")
    paper.setdefault("abstract", "")
    paper.setdefault("authors", paper.get("authors_json") or [])
    paper.setdefault("categories", [])

    # Parse score_details
    sd = paper.get("score_details_json") or paper.get("score_details") or {}
    if isinstance(sd, str):
        try:
            sd = json.loads(sd)
        except (TypeError, json.JSONDecodeError):
            sd = {}
    paper["score_details"] = sd

    return paper
```

- [ ] **Step 2: Verify existing tests pass**

```bash
python -m unittest discover -s tests -v
```

Expected: All tests pass (existing tests should not break since we're only changing the route handler).

- [ ] **Step 3: Commit**

```bash
git add app/routes/api/ai.py
git commit -m "fix: auto-resolve paper context in AI analysis generation endpoint"
```

---

### Task 0.2: Add Paper Detail tests

**Files:**
- Create: `tests/test_paper_detail.py`

- [ ] **Step 1: Create `tests/test_paper_detail.py`**

```python
"""Tests for Paper Detail page — canonicalization, loading, and context assembly."""
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from state_store import _canonical_paper_id, StateStore


class TestPaperIdCanonicalization(unittest.TestCase):
    def test_canonicalize_strips_version(self):
        self.assertEqual(_canonical_paper_id("2604.12345v2"), "2604.12345")

    def test_canonicalize_preserves_base_id(self):
        self.assertEqual(_canonical_paper_id("2604.12345"), "2604.12345")

    def test_canonicalize_handles_empty(self):
        result = _canonical_paper_id("")
        self.assertEqual(result, "")


class TestPaperViewModel(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.store = StateStore(db_path=self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_recommendation_run(self, paper_id, title, abstract, authors, categories, score_details):
        import uuid
        run_id = str(uuid.uuid4())
        self.store._connect = self.store._connect  # keep real connection
        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                "INSERT INTO recommendation_runs(run_id, run_date, trigger_source, status, paper_count, created_at) "
                "VALUES (?, date('now'), 'test', 'completed', 1, datetime('now'))",
                (run_id,),
            )
            conn.execute(
                "INSERT INTO recommendation_items(run_id, paper_id, rank, score, score_details_json, title, authors_json, abstract, categories_json) "
                "VALUES (?, ?, 1, 4.5, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    paper_id,
                    json.dumps(score_details),
                    title,
                    json.dumps(authors),
                    abstract,
                    json.dumps(categories),
                ),
            )
        return run_id

    def test_viewmodel_loads_paper_from_sqlite(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Test Paper Title",
            abstract="This is a test abstract.",
            authors=["Alice Smith", "Bob Jones"],
            categories=["cs.LG", "stat.ML"],
            score_details={"relevance": 3.0, "semantic": 1.5, "affinity": 0.8},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345")

        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["id"], "2604.12345")
        self.assertEqual(ctx["paper"]["title"], "Test Paper Title")
        self.assertIn("author_text", ctx["paper"])
        self.assertIn("category_labels", ctx["paper"])

    def test_viewmodel_canonicalizes_with_version_suffix(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Versioned Paper",
            abstract="Abstract here.",
            authors=["Author One"],
            categories=["cs.AI"],
            score_details={"relevance": 2.0},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345v2")

        self.assertNotIn("error", ctx)
        self.assertEqual(ctx["paper"]["title"], "Versioned Paper")

    def test_paper_not_found_returns_404_context(self):
        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("9999.99999")

        self.assertIn("error", ctx)
        self.assertEqual(ctx["paper_id"], "9999.99999")

    def test_score_details_affinity_in_context(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Affinity Test",
            abstract="Testing affinity in score details.",
            authors=["Author"],
            categories=["cs.LG"],
            score_details={"relevance": 2.0, "semantic": 1.0, "affinity": 0.8},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345")

        sd = ctx["paper"].get("score_details", {})
        self.assertIn("affinity", sd)
        self.assertEqual(sd["affinity"], 0.8)

    def test_collections_only_containing_paper(self):
        paper_id = "2604.12345"
        self._seed_recommendation_run(
            paper_id=paper_id,
            title="Collection Test",
            abstract="Testing collection filtering.",
            authors=["Author"],
            categories=["cs.LG"],
            score_details={"relevance": 1.0},
        )

        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                "INSERT INTO research_collections(name, description, created_at, updated_at) "
                "VALUES ('Test Col', 'desc', datetime('now'), datetime('now'))"
            )
            col_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO collection_papers(collection_id, paper_id, note, added_at) "
                "VALUES (?, ?, '', datetime('now'))",
                (col_id, paper_id),
            )
            conn.execute(
                "INSERT INTO research_collections(name, description, created_at, updated_at) "
                "VALUES ('Empty Col', 'desc', datetime('now'), datetime('now'))"
            )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context(paper_id)

        collections = ctx["paper"].get("collections", [])
        self.assertEqual(len(collections), 1)
        self.assertEqual(collections[0].get("name"), "Test Col")

    def test_viewmodel_fallback_to_markdown_history(self):
        import tempfile

        with tempfile.TemporaryDirectory() as hist_dir:
            digest_path = os.path.join(hist_dir, "digest_2026-04-27.md")
            with open(digest_path, "w") as f:
                f.write("## 1. Markdown Paper Title\n\n")
                f.write("- **ID:** 2604.99999\n")
                f.write("- **Authors:** Markdown Author\n")
                f.write("- **Abstract:** Markdown abstract text.\n")
                f.write("- **Score:** 3.2\n")

            with patch("app_paths.HISTORY_DIR", hist_dir):
                from app.viewmodels.paper_viewmodel import PaperViewModel

                vm = PaperViewModel(self.store)
                ctx = vm.to_detail_context("2604.99999")

                self.assertNotIn("error", ctx)
                self.assertIn("Markdown Paper Title", ctx["paper"].get("title", ""))

    def test_paper_detail_page_contains_key_modules(self):
        self._seed_recommendation_run(
            paper_id="2604.12345",
            title="Module Test Paper",
            abstract="Testing page modules.",
            authors=["Author Name"],
            categories=["cs.LG"],
            score_details={"relevance": 3.0, "semantic": 1.0, "author": 0.5, "depth": 1.0, "affinity": 0.8},
        )

        from app.viewmodels.paper_viewmodel import PaperViewModel

        vm = PaperViewModel(self.store)
        ctx = vm.to_detail_context("2604.12345")

        paper = ctx["paper"]
        # Abstract must be present
        self.assertTrue(paper.get("abstract") or paper.get("summary"))
        # Score details must be present
        self.assertIn("score_details", paper)
        # AI analysis key must exist (may be None)
        self.assertIn("ai_analysis", paper)


class TestPaperDetailRoute(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        os.environ["USE_DEV_SERVER"] = "1"

        from web_server import app
        app.config["TESTING"] = True
        app.config["STATE_STORE"] = StateStore(db_path=self.db_path)
        self.app = app.test_client()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_paper_detail_404_does_not_crash(self):
        resp = self.app.get("/papers/9999.99999")
        self.assertIn(resp.status_code, (200, 404))
        # The page should render an error message, not a 500
        if resp.status_code == 200:
            self.assertIn(b"not found", resp.data.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests**

```bash
python -m unittest tests.test_paper_detail -v
```

Expected: 10 tests pass.

- [ ] **Step 3: Run all tests to ensure no regressions**

```bash
python -m unittest discover -s tests -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_paper_detail.py
git commit -m "test: add Paper Detail page tests covering canonicalize, SQLite, fallback, and modules"
```

---

### Task 0.3: Fix setup.py packaging + restrict CORS

**Files:**
- Modify: `setup.py:1-47`
- Modify: `web_server.py:27`

- [ ] **Step 1: Fix `setup.py` — add waitress and recursive static includes**

Edit `setup.py`:

```python
from glob import glob

from setuptools import find_packages, setup


setup(
    name="arxiv-recommender-local",
    version="0.1.0",
    description="Local-first arXiv paper recommendation and triage desk",
    py_modules=[
        "app_paths",
        "arxiv_recommender_v5",
        "backup_user_data",
        "config_manager",
        "journal_tracker",
        "journal_update",
        "logger_config",
        "state_store",
        "utils",
        "web_server",
    ],
    packages=find_packages(include=["app", "app.*", "evaluation", "evaluation.*", "installer", "installer.*"]),
    include_package_data=True,
    data_files=[
        ("", ["user_profile.example.json"]),
        ("templates", glob("templates/*.html")),
        ("static", glob("static/*")),
        ("static/js", glob("static/js/*.js")),
    ],
    install_requires=[
        "Flask>=3.0.0",
        "flask-cors>=4.0.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
        "feedparser>=6.0.0",
        "sentence-transformers>=2.2.0",
        "transformers>=4.30.0",
        "torch>=2.0.0",
        "python-dateutil>=2.8.0",
        "waitress>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "arxiv-recommender=web_server:main",
        ],
    },
    python_requires=">=3.9",
)
```

- [ ] **Step 2: Fix `web_server.py` — restrict CORS**

Edit line 27 of `web_server.py`. Replace:

```python
CORS(app)
```

With:

```python
if os.getenv("USE_DEV_SERVER"):
    CORS(app)
else:
    CORS(app, origins=["http://localhost:5555", "http://127.0.0.1:5555"])
```

- [ ] **Step 3: Verify ruff check**

```bash
ruff check setup.py web_server.py
```

Expected: No errors.

- [ ] **Step 4: Run tests**

```bash
python -m unittest discover -s tests -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add setup.py web_server.py
git commit -m "fix: add waitress to setup.py, fix static packaging, restrict CORS to localhost"
```

---

### Phase 0 Verification Gate

After all three Phase 0 tasks are complete:

```bash
python -m unittest discover -s tests -v
ruff check app/ state_store.py config_manager.py web_server.py utils.py --ignore=F401,F841
```

Expected: All tests pass, no ruff errors.

---

## Phase 1 — Product Experience (4 parallel tasks)

### Task 1.1: Add "View Full Detail" entry points

**Files:**
- Modify: `templates/home_research.html` — already has `/papers/{{ paper.id }}` link in Inbox detail panel (line 102). Add to paper card hover area.
- Modify: `templates/queue_research.html` — add `View Detail` link on reading plan cards
- Modify: `templates/library_research.html` — add `View Detail` link on collection paper cards
- Modify: `templates/monitor_research.html` — add `View Detail` link on recent hits cards
- Modify: `templates/search_research.html` — add `View Detail` link on search result rows

- [ ] **Step 1: Queue template — add View Detail to reading plan cards**

In `templates/queue_research.html`, the reading plan paper cards currently have a "Start Reading" link. Add a "View Detail" link next to it. Find the pattern:

```html
<a href="{{ paper.link or 'https://arxiv.org/abs/' + paper.id }}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary" onclick="trackPaperOpen('{{ paper.id }}', 'reading_plan')">Start Reading</a>
```

Add after it:

```html
<a href="/papers/{{ paper.id }}" class="btn btn-sm btn-tertiary">View Detail</a>
```

This applies in both the Deep Read and Skim Later sections. Use `replace_all` to add after every "Start Reading" link.

- [ ] **Step 2: Library template — add View Detail to paper cards**

Read `templates/library_research.html` to find the paper card pattern, then add:

```html
<a href="/papers/{{ paper.id }}" class="btn btn-tertiary btn-xs">View Detail</a>
```

- [ ] **Step 3: Monitor template — add View Detail to recent hits**

In `templates/monitor_research.html`, find the recent hits paper listing and add:

```html
<a href="/papers/{{ hit.paper_id }}" class="btn btn-tertiary btn-xs">View Detail</a>
```

- [ ] **Step 4: Search template — add View Detail to result rows**

In `templates/search_research.html`, find the search result rows and add:

```html
<a href="/papers/{{ paper.id }}" class="btn btn-tertiary btn-xs">View Detail</a>
```

- [ ] **Step 5: Verify — check all pages load without error**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 6: Commit**

```bash
git add templates/
git commit -m "feat: add View Full Detail links across Inbox, Queue, Library, Monitor, Search"
```

---

### Task 1.2: Paper Detail action closure

**Files:**
- Modify: `templates/paper_detail.html:156-228` (the Actions rail section)

- [ ] **Step 1: Replace the Actions card in `paper_detail.html`**

Replace the current Actions card (lines 158-179 of the right rail) with a full action set:

```html
<!-- Actions -->
<div class="card card-spaced">
    <h2 class="panel-title">Actions</h2>
    <div class="action-buttons">
        <button class="btn btn-primary btn-sm" onclick="paperDetailAction('relevant', '{{ paper.get('id') }}')">Relevant</button>
        <button class="btn btn-danger btn-sm" onclick="paperDetailAction('ignore', '{{ paper.get('id') }}')">Ignore</button>
        <button class="btn btn-warm btn-sm" onclick="paperDetailAction('skim', '{{ paper.get('id') }}')">Skim Later</button>
        <button class="btn btn-sage btn-sm" onclick="paperDetailAction('deepread', '{{ paper.get('id') }}')">Deep Read</button>
        <button class="btn btn-secondary btn-sm" onclick="paperDetailAction('save', '{{ paper.get('id') }}')">Saved</button>
        <button class="btn btn-tertiary btn-sm" onclick="paperDetailAction('collect', '{{ paper.get('id') }}')">Add to Collection</button>
        {% if paper.get('first_author') %}
        <button class="btn btn-tertiary btn-sm" onclick="paperDetailAction('follow', '{{ paper.get('id') }}', '{{ paper.get('first_author') }}')">Follow {{ paper.get('first_author') }}</button>
        {% endif %}
        {% if paper.get('link') %}
        <a href="{{ paper.get('link', 'https://arxiv.org/abs/' + paper.get('id', '')) }}" target="_blank" class="btn btn-secondary btn-sm">Open arXiv</a>
        <a href="/api/pdf/{{ paper.get('id') }}" target="_blank" class="btn btn-primary btn-sm">Download PDF</a>
        <a href="/api/export/bibtex/{{ paper.get('id') }}" target="_blank" class="btn btn-secondary btn-sm">Export BibTeX</a>
        {% endif %}
    </div>
    {% if paper.get('id') %}
    <div class="action-buttons" style="margin-top:8px;">
        <button class="btn btn-primary btn-sm" id="generateAIBtn" onclick="generateAnalysis('{{ paper.get('id') }}')">
            {% if paper.get('ai_analysis') and paper.get('ai_analysis').get('status') == 'ok' %}
            Regenerate AI Analysis
            {% else %}
            Generate AI Analysis
            {% endif %}
        </button>
    </div>
    {% endif %}
</div>
```

- [ ] **Step 2: Add the `paperDetailAction` JS function to `paper_detail.html` scripts block**

Add before the existing `generateAnalysis` function:

```javascript
async function paperDetailAction(action, paperId, extra) {
    try {
        switch (action) {
            case 'relevant':
                await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({paper_id: paperId, action: 'like', source: 'paper_detail'})
                });
                showToast('Marked as Relevant');
                break;
            case 'ignore':
                await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({paper_id: paperId, action: 'dislike', source: 'paper_detail'})
                });
                showToast('Ignored');
                break;
            case 'skim':
                await queuePaperStatus(paperId, 'Skim Later', {source: 'paper_detail'});
                break;
            case 'deepread':
                await queuePaperStatus(paperId, 'Deep Read', {source: 'paper_detail'});
                break;
            case 'save':
                await queuePaperStatus(paperId, 'Saved', {source: 'paper_detail'});
                break;
            case 'collect':
                await addPaperToCollection(paperId, {source: 'paper_detail'});
                break;
            case 'follow':
                await followAuthor(extra, {paperId: paperId, source: 'paper_detail'});
                break;
        }
    } catch (err) {
        alert('Action failed: ' + err.message);
    }
}
```

- [ ] **Step 3: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 4: Commit**

```bash
git add templates/paper_detail.html
git commit -m "feat: add full action closure to Paper Detail page"
```

---

### Task 1.3: Score Breakdown completion

**Files:**
- Modify: `app/services/scoring_service.py` — add subscription, penalty, recency to `compute_score` details
- Modify: `templates/paper_detail.html` — show all non-zero score items

- [ ] **Step 1: Add subscription, penalty, recency fields to `compute_score` in `scoring_service.py`**

In the `compute_score` method of `EnhancedScorer`, modify the `details` dict (around line 73-81):

```python
# After computing the main score components, add:
penalty = 0.0
# Check for dislike topics match as penalty
for topic in get_dislike_topics():
    if self._count_keyword((paper.get('title','') + ' ' + paper.get('abstract','')).lower(), topic) > 0:
        penalty -= 1.0

# Subscription match bonus
subscription_bonus = 0.0
try:
    from state_store import get_state_store
    store = get_state_store()
    subs = store.list_subscriptions()
    title_lower = (paper.get('title', '') or '').lower()
    abstract_lower = (paper.get('abstract', '') or '').lower()
    for sub in subs:
        if not sub.get('enabled', True):
            continue
        sub_text = (sub.get('query_text') or '').lower()
        if sub_text and (sub_text in title_lower or sub_text in abstract_lower):
            subscription_bonus += 1.0
except Exception:
    subscription_bonus = 0.0

# Recency bonus
recency_bonus = 0.0
published = paper.get('published', '')
if published:
    try:
        pub_date = datetime.strptime(published[:10], '%Y-%m-%d')
        days_old = (datetime.now() - pub_date).days
        if days_old <= 7:
            recency_bonus = 0.3
        elif days_old <= 30:
            recency_bonus = 0.1
    except Exception:
        pass

details = {
    'relevance': relevance,
    'semantic': semantic_sim,
    'author': author,
    'depth': depth,
    'affinity': round(affinity_bonus, 2),
    'subscription': round(subscription_bonus, 2),
    'recency': round(recency_bonus, 2),
    'penalty': round(penalty, 2),
    'breakdown': self._get_breakdown(paper, semantic_sim)
}
```

And update the total to include subscription/recency/penalty:

```python
total = relevance * 0.50 + author * 0.10 + depth * 0.10 + semantic_sim * 0.30
total += subscription_bonus + recency_bonus + penalty + affinity_bonus
```

- [ ] **Step 2: Update `paper_detail.html` score breakdown to show all non-zero items**

In the Score Breakdown card (around line 77-107), add the new score fields:

```html
{% if sd.get('subscription', 0) != 0 %}
<div class="score-item">
    <div class="value">{{ "%+.1f"|format(sd.get('subscription', 0)) }}</div>
    <div class="label">Subscription</div>
</div>
{% endif %}
{% if sd.get('recency', 0) != 0 %}
<div class="score-item">
    <div class="value">{{ "%+.1f"|format(sd.get('recency', 0)) }}</div>
    <div class="label">Recency</div>
</div>
{% endif %}
{% if sd.get('penalty', 0) != 0 %}
<div class="score-item">
    <div class="value">{{ "%+.1f"|format(sd.get('penalty', 0)) }}</div>
    <div class="label">Penalty</div>
</div>
{% endif %}
```

Add these after the existing "Preference" score item.

- [ ] **Step 3: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 4: Commit**

```bash
git add app/services/scoring_service.py templates/paper_detail.html
git commit -m "feat: add subscription, recency, penalty to score breakdown and Paper Detail"
```

---

### Task 1.4: Evaluation affinity ablation

**Files:**
- Modify: `evaluation/ablation.py:12-17` — add `WITHOUT_AFFINITY` variant
- Modify: `evaluation/__init__.py` — export new variant if needed

- [ ] **Step 1: Add `without_affinity` variant to ablation runner**

In `evaluation/ablation.py`, update VARIANTS:

```python
VARIANTS = [
    ScoringVariant.KEYWORDS_ONLY,
    ScoringVariant.KEYWORDS_SEMANTIC,
    ScoringVariant.KEYWORDS_SEMANTIC_FEEDBACK,
    ScoringVariant.FULL_SCORER,
    ScoringVariant.WITHOUT_AFFINITY,
]
```

- [ ] **Step 2: Add `without_affinity` to `ScoringVariant` enum**

In `app/services/scoring_service.py`, add to `ScoringVariant`:

```python
class ScoringVariant(str, Enum):
    KEYWORDS_ONLY = "keywords_only"
    KEYWORDS_SEMANTIC = "keywords_semantic"
    KEYWORDS_SEMANTIC_FEEDBACK = "keywords_semantic_feedback"
    FULL_SCORER = "full_scorer"
    WITHOUT_AFFINITY = "without_affinity"
```

- [ ] **Step 3: Handle `without_affinity` in `score_papers_for_evaluation`**

In `app/services/scoring_service.py`, in `score_papers_for_evaluation`, add:

```python
elif variant == ScoringVariant.WITHOUT_AFFINITY:
    score = _base_score(item) - _component(item, "affinity")
```

- [ ] **Step 4: Run tests**

```bash
python -m unittest tests.test_phase3_evaluation -v
python -m unittest discover -s tests -v
```

- [ ] **Step 5: Commit**

```bash
git add evaluation/ablation.py app/services/scoring_service.py
git commit -m "feat: add without_affinity ablation variant to evaluation"
```

---

### Phase 1 Verification Gate

```bash
python -m unittest discover -s tests -v
ruff check app/ evaluation/ --ignore=F401,F841
```

---

## Phase 2 — Production Engineering (3 parallel tasks)

### Task 2.1: CI hardening + Release Checklist

**Files:**
- Modify: `.github/workflows/tests.yml:30-31,68-69`
- Create: `docs/RELEASE_CHECKLIST.md`

- [ ] **Step 1: CI — make lint and security blocking**

In `.github/workflows/tests.yml`, change:
- Line 31: `continue-on-error: true` → `continue-on-error: false`
- Line 70: `continue-on-error: true` → `continue-on-error: false`

- [ ] **Step 2: Create `docs/RELEASE_CHECKLIST.md`**

```markdown
# Release Checklist

Run before every release.

## 1. Tests
- [ ] `python -m unittest discover -s tests -v` — all pass

## 2. Lint & Security
- [ ] `ruff check app/ state_store.py config_manager.py web_server.py utils.py`
- [ ] `bandit -r app/ -ll -x tests/`
- [ ] `pip-audit -r requirements.txt`

## 3. Install & Start
- [ ] `pip install .` succeeds
- [ ] `arxiv-recommender` starts and serves at http://localhost:5555
- [ ] `USE_DEV_SERVER=1 python web_server.py` starts dev server

## 4. Functional Checks
- [ ] Onboarding completes without error
- [ ] Today's recommendations generate without crash
- [ ] Inbox triage actions (Relevant/Ignore/Queue) record in interaction_events
- [ ] Paper Detail page opens for any recommended paper
- [ ] AI Analysis generates with configured provider, or graceful fallback without key
- [ ] Data export produces valid JSON
- [ ] Data import restores state
- [ ] `evaluation/run_evaluation.py` produces reports

## 5. Packaging
- [ ] `pip install .` includes all templates, static files, JS modules
- [ ] `arxiv-recommender` CLI entry point works
- [ ] CSS and JS load correctly in browser
```

- [ ] **Step 3: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/tests.yml docs/RELEASE_CHECKLIST.md
git commit -m "ci: make lint and security blocking, add release checklist"
```

---

### Task 2.2: Backup/Restore + System Health page

**Files:**
- Modify: `app/routes/settings.py` — add `/settings/system` route, backup/restore endpoints
- Modify: `templates/settings_research.html` — enhance tab=system with health info and backup UI
- Modify: `app/routes/api/state.py` — add backup/restore API endpoints

- [ ] **Step 1: Read current state API routes**

Read `app/routes/api/state.py` to understand existing export/import patterns.

- [ ] **Step 2: Add backup/restore API endpoints**

In `app/routes/api/state.py`, add:

```python
import zipfile
import io
import os
from datetime import datetime
from flask import send_file


@bp.post("/api/state/backup")
def backup_state():
    """Create a full backup zip containing all state files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # user config files
        for fname in ['user_profile.json', 'user_config.json', 'keywords_config.json', 'my_scholars.json']:
            path = os.path.join(str(PROJECT_ROOT), fname)
            if os.path.exists(path):
                zf.write(path, fname)

        # SQLite database
        db_path = str(STATE_DB_PATH)
        if os.path.exists(db_path):
            zf.write(db_path, 'cache/app_state.db')

        # reports
        reports_dir = os.path.join(str(PROJECT_ROOT), 'reports')
        if os.path.exists(reports_dir):
            for root, _, files in os.walk(reports_dir):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.join('reports', os.path.relpath(full, reports_dir))
                    zf.write(full, arcname)

        # history
        history_dir = os.path.join(str(PROJECT_ROOT), 'history')
        if os.path.exists(history_dir):
            for root, _, files in os.walk(history_dir):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.join('history', os.path.relpath(full, history_dir))
                    zf.write(full, arcname)

    buf.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'ppr_backup_{timestamp}.zip'
    )


@bp.post("/api/state/restore")
def restore_state():
    """Restore state from a backup zip file."""
    if 'backup' not in request.files:
        return jsonify({"success": False, "error": "No backup file provided"}), 400

    file = request.files['backup']
    try:
        with zipfile.ZipFile(io.BytesIO(file.read())) as zf:
            for member in zf.namelist():
                target = os.path.join(str(PROJECT_ROOT), member)
                if member.startswith('cache/'):
                    target = os.path.join(str(PROJECT_ROOT), member)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, 'wb') as dst:
                    dst.write(src.read())
    except zipfile.BadZipFile:
        return jsonify({"success": False, "error": "Invalid backup file"}), 400

    return jsonify({"success": True, "message": "State restored. Please restart the application."})
```

- [ ] **Step 3: Add system health endpoint**

In `app/routes/api/state.py`, add:

```python
@bp.get("/api/state/health")
def system_health():
    """Return system health information."""
    import os
    from state_store import get_state_store

    store = get_state_store()
    db_path = str(STATE_DB_PATH)
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    # Table counts
    counts = {}
    with store._lock, store._connect() as conn:
        for table in ['recommendation_runs', 'recommendation_items', 'reading_queue_items',
                       'research_collections', 'subscriptions', 'interaction_events',
                       'paper_ai_analyses']:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            counts[table] = row['cnt'] if row else 0

        schema_row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        schema_version = schema_row['value'] if schema_row else 'unknown'

    # Last run
    last_run = store.get_latest_job("daily_recommendation")
    last_run_time = last_run.get('created_at') if last_run else None

    return jsonify({
        "success": True,
        "health": {
            "db_path": db_path,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "schema_version": schema_version,
            "table_counts": counts,
            "last_recommendation_run": last_run_time,
        }
    })


@bp.post("/api/state/vacuum")
def vacuum_database():
    """Run VACUUM on the SQLite database."""
    from state_store import get_state_store
    store = get_state_store()
    with store._lock, store._connect() as conn:
        conn.execute("VACUUM")
    return jsonify({"success": True, "message": "Database vacuumed successfully."})
```

- [ ] **Step 4: Enhance settings_research.html system tab**

Add to the system tab section in `templates/settings_research.html` (after the existing Data Management card):

```html
<section class="form-card">
    <div class="section-kicker">Backup & Restore</div>
    <h2 class="panel-title">数据备份与恢复</h2>
    <p class="field-help">定期备份你的所有数据：关键词、订阅、推荐历史、队列、Collections。</p>
    <div class="button-row">
        <button type="button" class="btn btn-primary" onclick="backupNow()">Backup Now</button>
        <button type="button" class="btn btn-secondary" onclick="triggerRestore()">Restore from Backup</button>
        <button type="button" class="btn btn-tertiary" onclick="openDataFolder()">Open Data Folder</button>
    </div>
    <input type="file" id="restoreFile" accept=".zip" hidden onchange="handleRestore(event)">
</section>

<section class="form-card">
    <div class="section-kicker">Database Health</div>
    <h2 class="panel-title">数据库状态</h2>
    <div id="dbHealthInfo" class="list-stack">
        <div class="list-item"><span>Loading...</span></div>
    </div>
    <div class="button-row mt-4">
        <button type="button" class="btn btn-secondary" onclick="loadSystemHealth()">Refresh</button>
        <button type="button" class="btn btn-tertiary" onclick="vacuumDb()">Vacuum Database</button>
    </div>
</section>
```

- [ ] **Step 5: Add JS functions for backup/restore/health**

Add to the scripts block:

```javascript
function backupNow() {
    window.location.href = '/api/state/backup';
}

function triggerRestore() {
    document.getElementById('restoreFile').click();
}

async function handleRestore(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ok = await confirmDangerAction({
        title: '恢复备份',
        objectName: file.name,
        message: '这将会覆盖当前所有数据。建议先备份当前状态。',
        confirmLabel: 'Restore'
    });
    if (!ok) { event.target.value = ''; return; }
    const formData = new FormData();
    formData.append('backup', file);
    try {
        const resp = await fetch('/api/state/restore', {method: 'POST', body: formData});
        const data = await resp.json();
        if (data.success) {
            showToast('状态已恢复，应用将刷新');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showToast('恢复失败: ' + (data.error || 'unknown'), 'error');
        }
    } catch (err) {
        showToast('恢复失败: ' + err.message, 'error');
    }
    event.target.value = '';
}

function openDataFolder() {
    fetch('/api/state/data-folder').then(r => r.json()).then(d => {
        if (d.path) showToast('数据目录: ' + d.path);
    });
}

async function loadSystemHealth() {
    try {
        const resp = await fetch('/api/state/health');
        const data = await resp.json();
        if (!data.success) return;
        const h = data.health;
        const el = document.getElementById('dbHealthInfo');
        el.innerHTML = [
            '<div class="list-item"><div><span class="list-item-title">SQLite Path</span><span class="list-item-subtitle">' + h.db_path + '</span></div><span class="list-item-trailing">' + h.db_size_mb + ' MB</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Schema Version</span></div><span class="list-item-trailing">' + h.schema_version + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Recommendation Runs</span></div><span class="list-item-trailing">' + (h.table_counts.recommendation_runs || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Recommendation Items</span></div><span class="list-item-trailing">' + (h.table_counts.recommendation_items || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Queue Items</span></div><span class="list-item-trailing">' + (h.table_counts.reading_queue_items || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Collections</span></div><span class="list-item-trailing">' + (h.table_counts.research_collections || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Subscriptions</span></div><span class="list-item-trailing">' + (h.table_counts.subscriptions || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Interaction Events</span></div><span class="list-item-trailing">' + (h.table_counts.interaction_events || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">AI Analyses</span></div><span class="list-item-trailing">' + (h.table_counts.paper_ai_analyses || 0) + '</span></div>',
            '<div class="list-item"><div><span class="list-item-title">Last Run</span></div><span class="list-item-trailing">' + (h.last_recommendation_run || 'N/A') + '</span></div>',
        ].join('');
    } catch (err) {
        console.error('Health check failed:', err);
    }
}

async function vacuumDb() {
    try {
        const resp = await fetch('/api/state/vacuum', {method: 'POST'});
        const data = await resp.json();
        showToast(data.message || 'Done');
        loadSystemHealth();
    } catch (err) {
        showToast('Vacuum failed: ' + err.message, 'error');
    }
}

// Load health on system tab open
if (document.querySelector('.settings-nav-link[href*="tab=system"].is-active')) {
    loadSystemHealth();
}
```

- [ ] **Step 6: Add data-folder endpoint**

In `app/routes/api/state.py`:

```python
@bp.get("/api/state/data-folder")
def get_data_folder():
    return jsonify({"success": True, "path": str(PROJECT_ROOT)})
```

- [ ] **Step 7: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 8: Commit**

```bash
git add app/routes/settings.py app/routes/api/state.py templates/settings_research.html
git commit -m "feat: add backup/restore, system health page, database vacuum"
```

---

### Task 2.3: Start scripts + Docker + Deployment docs

**Files:**
- Create: `scripts/start_local.sh`
- Create: `scripts/start_local.ps1`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `docs/DEPLOYMENT.md`

- [ ] **Step 1: Create `scripts/start_local.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt -c constraints.txt --quiet

echo ""
echo "Starting arXiv Recommender at http://localhost:5555"
echo "Press Ctrl+C to stop."
echo ""

python web_server.py
```

Make executable: `chmod +x scripts/start_local.sh`

- [ ] **Step 2: Create `scripts/start_local.ps1`**

```powershell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
Write-Host "Installing dependencies..."
pip install -r requirements.txt -c constraints.txt --quiet

Write-Host ""
Write-Host "Starting arXiv Recommender at http://localhost:5555"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

python web_server.py
```

- [ ] **Step 3: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Copy application
COPY . .

# Create runtime directory for volume mount
RUN mkdir -p /app/runtime

ENV USE_DEV_SERVER=0
EXPOSE 5555

CMD ["python", "web_server.py"]
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  app:
    build: .
    ports:
      - "127.0.0.1:5555:5555"
    volumes:
      - ./runtime:/app/runtime
      - ./user_profile.json:/app/user_profile.json
      - ./user_config.json:/app/user_config.json
      - ./keywords_config.json:/app/keywords_config.json
    environment:
      - USE_DEV_SERVER=0
    restart: unless-stopped
```

- [ ] **Step 5: Create `.dockerignore`**

```
.venv/
__pycache__/
*.pyc
.git/
.env
*.egg-info/
dist/
logs/
cache/
.DS_Store
```

- [ ] **Step 6: Create `docs/DEPLOYMENT.md`**

```markdown
# Deployment Guide

arXiv Recommender is a local-first application. Three deployment options:

## Option 1: Source Run (recommended for daily use)

### Install
```bash
git clone <repo-url> && cd arxiv_recommender
bash scripts/start_local.sh
```

### Usage
- Open http://localhost:5555
- Complete onboarding
- Generate first recommendations

### Stop
Press Ctrl+C in terminal.

### Backup
Settings → System tab → Backup Now

### Restore
Settings → System tab → Restore from Backup

## Option 2: pip install

```bash
pip install .
arxiv-recommender
```

## Option 3: Docker

```bash
docker compose up
```

Open http://localhost:5555.

### Stop
```bash
docker compose down
```

## Configuration

### DeepSeek AI Analysis
Settings → System tab → AI Analysis section
Enter API key, base URL, model name. Or skip — the app works fully without AI.

### Data locations
- `user_profile.json` — keywords and preferences
- `cache/app_state.db` — SQLite state (recommendations, queue, collections, subscriptions)
- `reports/` — evaluation reports
- `history/` — digest markdown history

## Troubleshooting

### "No recommendations generated"
1. Check Settings → Profile tab — ensure core keywords are configured
2. Check network can reach arxiv.org
3. Try: Settings → Profile → Save and Regenerate

### "AI Analysis not working"
1. Verify API key in Settings → System → AI Analysis
2. Test connection button
3. The app works fine without AI — this is optional

### Database errors
Settings → System → Vacuum Database
Or delete `cache/app_state.db` (will be recreated — you lose history)
```

- [ ] **Step 7: Commit**

```bash
git add scripts/start_local.sh scripts/start_local.ps1 Dockerfile docker-compose.yml .dockerignore docs/DEPLOYMENT.md
git commit -m "feat: add one-click start scripts, Docker deployment, and deployment docs"
```

---

### Phase 2 Verification Gate

```bash
python -m unittest discover -s tests -v
ruff check app/ scripts/ --ignore=F401,F841
```

---

## Phase 3 — UI Polish (3 parallel tasks)

### Task 3.1: Extract inline styles to research_ui.css

**Files:**
- Modify: `static/research_ui.css` — add new CSS component classes
- Modify: `templates/home_research.html` — replace inline styles with classes
- Modify: `templates/paper_detail.html` — replace inline styles with classes
- Modify: `templates/eval_dashboard.html` — replace inline styles with classes
- Modify: `templates/monitor_research.html` — replace inline styles with classes

- [ ] **Step 1: Add CSS component classes to `research_ui.css`**

Append to `static/research_ui.css`:

```css
/* ---- Progress Components (from home_research.html) ---- */
.progress-card { margin-bottom: 16px; }
.progress-content { /* container */ }
.progress-stats { display: flex; flex-direction: column; gap: var(--s-3); }
.progress-metric { display: flex; align-items: baseline; gap: var(--s-1); }
.progress-number { font-size: 1.5rem; font-weight: 700; color: var(--brand); }
.progress-total { font-size: 0.85rem; color: var(--ink-muted); }
.progress-track {
    height: 6px; background: var(--line); border-radius: var(--r-xs);
    overflow: hidden;
}
.progress-fill {
    height: 100%; background: var(--brand); border-radius: var(--r-xs);
    transition: width 0.3s ease;
}
.progress-breakdown { display: flex; gap: var(--s-3); font-size: 0.8rem; }
.progress-stat { font-weight: 600; }
.progress-stat--liked { color: var(--sage); }
.progress-stat--disliked { color: var(--danger); }
.progress-stat--queued { color: var(--brand); }

.progress-complete { text-align: center; padding: var(--s-5) 0; }
.progress-checkmark { font-size: 2rem; color: var(--sage); }
.progress-complete-title { font-size: 1.1rem; font-weight: 600; margin: var(--s-2) 0; }
.progress-complete-summary { font-size: 0.85rem; color: var(--ink-muted); }

/* ---- Score Breakdown Grid (from paper_detail.html) ---- */
.score-breakdown-grid {
    display: flex; gap: var(--s-3); flex-wrap: wrap;
}

/* ---- Paper Detail Layout (from paper_detail.html) ---- */
.paper-detail-layout {
    display: grid;
    grid-template-columns: 1fr 260px;
    gap: var(--s-5);
    align-items: start;
}
@media (max-width: 900px) {
    .paper-detail-layout {
        grid-template-columns: 1fr;
    }
}

.paper-detail-rail {
    position: sticky; top: 20px;
    display: flex; flex-direction: column; gap: var(--s-3);
}
@media (max-width: 900px) {
    .paper-detail-rail {
        position: static;
    }
}

/* ---- Triage Summary Grid (from home_research.html) ---- */
.triage-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: var(--s-3);
}

/* ---- Stat Card (from eval_dashboard.html) ---- */
.stat-card {
    text-align: center;
    padding: var(--s-3);
    background: var(--surface-raised);
    border-radius: var(--r-sm);
    box-shadow: var(--shadow-1);
}
.stat-card-value {
    font-size: 1.5rem; font-weight: 700; color: var(--brand);
}
.stat-card-label {
    font-size: 0.8rem; color: var(--ink-muted); margin-top: var(--s-1);
}
```

- [ ] **Step 2: Replace inline styles in `paper_detail.html`**

- Line 23: `style="align-items:start;"` → remove (use CSS class `.paper-detail-layout`)
- Line 156: `style="position:sticky;top:20px;"` → add class `paper-detail-rail`
- Line 130: `style="font-size:0.9em;margin-top:8px;"` → add class `t-muted t-sm`

Change the split div to use the new class:
```html
<div class="split split--rail-right paper-detail-layout">
```
And the aside:
```html
<aside class="rail paper-detail-rail">
```

- [ ] **Step 3: Replace inline styles in `home_research.html`**

Replace inline style in progress card with class-based alternatives where possible. Keep `style="width: 0%"` on the progress bar fill since it's dynamic.

- [ ] **Step 4: Replace inline styles in `eval_dashboard.html`**

Read the template, identify inline styles, and extract to CSS classes.

- [ ] **Step 5: Replace inline styles in `monitor_research.html`**

Read the template, identify inline styles, and extract to CSS classes.

- [ ] **Step 6: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 7: Commit**

```bash
git add static/research_ui.css templates/home_research.html templates/paper_detail.html templates/eval_dashboard.html templates/monitor_research.html
git commit -m "style: extract inline styles to research_ui.css component classes"
```

---

### Task 3.2: Narrow-screen responsiveness

**Files:**
- Modify: `static/research_ui.css` — add media queries

- [ ] **Step 1: Add responsive media queries to `research_ui.css`**

Append:

```css
/* ---- Responsive: Tablet (< 900px) ---- */
@media (max-width: 900px) {
    /* Sidebar */
    .shell { grid-template-columns: 1fr; }
    .shell-nav { display: none; }
    .shell-nav.is-open { display: block; position: fixed; z-index: 100; }

    /* Inbox split: two-column → single-column */
    .inbox-workspace {
        grid-template-columns: 1fr !important;
    }
    .inbox-workspace .detail-panel {
        position: static;
        border-left: none;
        border-top: 1px solid var(--line);
        padding-top: var(--s-4);
    }

    /* Paper Detail rail moves below content */
    .paper-detail-layout {
        grid-template-columns: 1fr;
    }
    .paper-detail-rail {
        position: static;
    }

    /* Monitor tabs horizontal scroll */
    .tabs {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        white-space: nowrap;
    }
    .tabs .tab-button {
        flex-shrink: 0;
    }

    /* General spacing */
    .page-header { flex-direction: column; gap: var(--s-3); }
    .toolbar { flex-wrap: wrap; }
}

/* ---- Responsive: Mobile (< 480px) ---- */
@media (max-width: 480px) {
    .page-title { font-size: 1.2rem; }
    .paper-list-title { font-size: 0.95rem; }
    .detail-title { font-size: 1rem; }

    .split--rail-right, .split--rail-left {
        grid-template-columns: 1fr;
    }

    .action-buttons { flex-direction: column; }
}
```

- [ ] **Step 2: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 3: Commit**

```bash
git add static/research_ui.css
git commit -m "style: add responsive breakpoints for narrow screens and mobile"
```

---

### Task 3.3: Empty & error states

**Files:**
- Modify: `templates/home_research.html` — enhance empty states
- Modify: `templates/paper_detail.html` — add empty states
- Modify: `templates/monitor_research.html` — add subscription empty states
- Modify: `templates/eval_dashboard.html` — add no-reports state
- Modify: `templates/queue_research.html` — add empty queue state

- [ ] **Step 1: Add reusable empty state CSS to `research_ui.css`**

```css
/* ---- Empty & Error States ---- */
.empty-state-card {
    text-align: center;
    padding: var(--s-8) var(--s-4);
}
.empty-state-icon { font-size: 2rem; margin-bottom: var(--s-3); }
.empty-state-title { font-size: 1.1rem; font-weight: 600; margin-bottom: var(--s-2); }
.empty-state-desc { color: var(--ink-muted); margin-bottom: var(--s-4); max-width: 400px; margin-left: auto; margin-right: auto; }
```

- [ ] **Step 2: Enhance home_research.html empty state**

Replace the current simple empty state with:

```html
<div class="card empty-state-card">
    <div class="empty-state-icon">&#128218;</div>
    <h2 class="empty-state-title">No Recommendations Yet</h2>
    <p class="empty-state-desc">Generate your first set of paper recommendations based on your research keywords.</p>
    <a href="/settings?tab=profile" class="btn btn-primary">Configure Keywords</a>
    <button type="button" class="btn btn-secondary" onclick="window.location.reload()">Refresh</button>
</div>
```

- [ ] **Step 3: Add no-subscriptions state to `monitor_research.html`**

Add before the tab content:

```html
{% if not my_scholars and not journal_cards and not all_saved_searches %}
<div class="card empty-state-card">
    <div class="empty-state-icon">&#128269;</div>
    <h2 class="empty-state-title">No Active Subscriptions</h2>
    <p class="empty-state-desc">Create subscriptions to track authors, venues, and research queries over time.</p>
    <button type="button" class="btn btn-primary" onclick="createQuerySubscription()">Create Query Subscription</button>
    <button type="button" class="btn btn-secondary" onclick="createAuthorSubscription()">Follow Author</button>
</div>
{% endif %}
```

- [ ] **Step 4: Add no-reports state to `eval_dashboard.html`**

Add:

```html
{% if not reports %}
<div class="card empty-state-card">
    <div class="empty-state-icon">&#128202;</div>
    <h2 class="empty-state-title">No Evaluation Reports</h2>
    <p class="empty-state-desc">Run evaluations to measure recommendation quality across scoring variants.</p>
    <button type="button" class="btn btn-primary" onclick="runEvaluation()">Run Evaluation</button>
</div>
{% endif %}
```

- [ ] **Step 5: Add empty queue state to `queue_research.html`**

```html
{% if not deep_read_papers and not skim_later_papers %}
<div class="card empty-state-card">
    <div class="empty-state-icon">&#128214;</div>
    <h2 class="empty-state-title">Queue is Empty</h2>
    <p class="empty-state-desc">Papers queued from Inbox for Skim Later or Deep Read will appear here.</p>
    <a href="/" class="btn btn-primary">Go to Inbox</a>
</div>
{% endif %}
```

- [ ] **Step 6: Run tests**

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 7: Commit**

```bash
git add static/research_ui.css templates/home_research.html templates/monitor_research.html templates/eval_dashboard.html templates/queue_research.html
git commit -m "feat: add empty and error states with next-action buttons across pages"
```

---

### Phase 3 Verification Gate

```bash
python -m unittest discover -s tests -v
ruff check app/ static/ templates/ --ignore=F401,F841
```

---

## Final Verification (All Phases Complete)

```bash
python -m unittest discover -s tests -v
ruff check app/ state_store.py config_manager.py web_server.py utils.py --ignore=F401,F841
```

Expected: All tests pass, no lint errors.
