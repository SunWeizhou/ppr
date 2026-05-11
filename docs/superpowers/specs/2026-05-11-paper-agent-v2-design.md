# Paper Agent V2 — Major Version Design Spec

**Date**: 2026-05-11
**Branch**: `codex/apple-claude-workspace-redesign`
**Status**: Approved, pending implementation

## 1. Overview

A major version update to the Paper Agent system covering five subsystems:

1. **UI Foundation** — Unified design system with Notion-style components, Claude/Apple color palette, breathing grid background, dark mode as first-class citizen
2. **Structured Entity Subscriptions** — Journals, conferences, scholars, and research fields as browsable, subscribable first-class objects with profile pages
3. **Search Enhancement** — OpenAlex as third data source, query rewriting, search history, result filtering
4. **Agent Session System** — Persistent conversation sessions with multi-turn context, multi-step execution, Preact-based panel modeled after open-source Claude Code implementations
5. **Recommendation Engine** — Multi-strategy recommendations, multi-dimensional scoring, user profile for personalization

### Strategic Direction

**B → C → A** (Information Network → Smart Workflow → Personalization):
- First build a solid structured information network (entities, multi-source search)
- Then build intelligent workflows on top (session-based Agent, query rewriting)
- Finally leverage accumulated data for personalization (user profile, adaptive recommendations)

### Architecture Decision

**Approach: Partial Frontend Upgrade** — Backend stays Flask + Jinja2 + SQLite. Agent panel is replaced with a standalone Preact application communicating through REST APIs. All other pages remain server-rendered with a unified CSS design system (design tokens) bridging both worlds.

---

## 2. Design System & UI Foundation

### 2.1 Design Tokens

Three-layer token system replacing the current triple `:root` override mess:

**Layer 1 — Primitive Tokens** (~30 raw color values):
```css
--color-warm-black: #1a1a1a;
--color-off-white: #fafaf8;
--color-claude-orange: #d97757;
--color-apple-blue: #007aff;
/* ... */
```

**Layer 2 — Semantic Tokens** (light/dark variants):
```css
/* Light (default) */
:root {
  --bg-primary: var(--color-off-white);
  --bg-surface: #ffffff;
  --bg-surface-hover: #f5f5f3;
  --ink-primary: #1a1a1a;
  --ink-secondary: #6b6b6b;
  --accent-primary: var(--color-claude-orange);
  --border-default: #e8e8e5;
  /* ... ~20 semantic tokens */
}

/* Dark */
[data-theme="dark"] {
  --bg-primary: var(--color-warm-black);
  --bg-surface: #2a2a2a;
  --bg-surface-hover: #333333;
  --ink-primary: #ededec;
  --ink-secondary: #999999;
  --accent-primary: var(--color-claude-orange);
  --border-default: #3a3a3a;
}
```

**Layer 3 — Component Tokens** (reference semantic tokens):
```css
--card-bg: var(--bg-surface);
--card-border: var(--border-default);
--nav-bg: var(--bg-primary);
--agent-panel-bg: var(--bg-surface);
```

Dark mode toggles Layer 2 mappings via `[data-theme="dark"]`; Layer 3 follows automatically.

### 2.2 Notion-Style Component Library

Core components (Jinja2 macros + CSS):

| Component | Description |
|-----------|-------------|
| **Page Header** | Large title + emoji/icon + description, Notion page-top style |
| **Table/List View** | Inline property tags (chips), hover-reveal action buttons |
| **Card** | Borderless or ultra-thin border, hover micro-lift (1px shadow shift) |
| **Button** | Ghost default, primary uses accent fill, no heavy borders |
| **Sidebar Nav** | Left collapsible navigation (icon + label), active item background highlight |
| **Command Input** | Unified search/Agent input as top command-bar style |
| **Toast** | Bottom-right slide-in, Notion-style minimal notification |

### 2.3 Breathing Grid Background

Animated grid background inspired by Claude Cowork:

- Grid lines via CSS `repeating-linear-gradient`
- Breathing animation: grid node opacity cycles 0.03 → 0.08 via CSS `animation` or lightweight Canvas
- Light mode: light gray grid on off-white
- Dark mode: dark gray grid on warm-black
- Performance: CSS-first, Canvas as enhancement; static grid when `prefers-reduced-motion` is active

### 2.4 Navigation Restructure

Replace top pill navigation with **Notion-style left sidebar**:

```
Sidebar                          Main Content
─────────────────────────────    ────────────────────────
Search                           (page content)
Library
Recommendations
Watch
Reading
───────────────
Subscriptions
  Journals
  Conferences
  Scholars
  Fields
───────────────
Settings
Agent Sessions
```

Mobile: sidebar collapsed by default, hamburger menu trigger.

---

## 3. Structured Entity & Subscription System

### 3.1 Entity Data Model

Four entity types, each a browsable, subscribable first-class object:

```sql
CREATE TABLE entities (
    id            TEXT PRIMARY KEY,  -- e.g. "journal:nature_ml", "scholar:s2:12345"
    type          TEXT NOT NULL CHECK(type IN ('journal','conference','scholar','field')),
    name          TEXT NOT NULL,
    aliases       TEXT DEFAULT '[]',
    external_ids  TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}',
    stats_json    TEXT DEFAULT '{}',
    last_synced   TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_name ON entities(name);
```

Type-specific `metadata_json`:

- **Journal**: `{publisher, issn, impact_factor, h_index, homepage_url, scope_description}`
- **Conference**: `{series_name, frequency, next_date, location, acceptance_rate, homepage_url, tier}`
- **Scholar**: `{affiliations: [], h_index, citation_count, homepage_url, research_interests: []}`
- **Field**: `{arxiv_categories: [], parent_field_id, description, key_venues: [], key_scholars: []}`

### 3.2 Entity Relations

```sql
CREATE TABLE entity_relations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type  TEXT NOT NULL CHECK(relation_type IN (
        'publishes_in','affiliated_with','researches','subfield_of','co_located'
    )),
    weight         REAL DEFAULT 1.0,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, target_id, relation_type)
);
```

Used for "Related entities" on profile pages. No full graph traversal.

### 3.3 Subscription Upgrade

Existing `subscriptions` table extended:

```sql
ALTER TABLE subscriptions ADD COLUMN entity_id TEXT REFERENCES entities(id);
ALTER TABLE subscriptions ADD COLUMN filters_json TEXT DEFAULT '{}';
```

`filters_json` example: `{"min_citations": 5, "since": "2025-01", "keywords": ["LLM"]}`

Subscription type mapping:
- `query` — retained, pure keyword (backward compatible)
- `author` → linked to scholar entity via `entity_id`
- `venue` → linked to journal or conference entity
- **New** `field` → linked to field entity, matches by arXiv category
- **New** `entity` → generic entity subscription with `filters_json` customization (use when a subscription needs cross-type filtering, e.g. "papers by Scholar X in Journal Y")

New runner methods: `run_journal_subscription()`, `run_conference_subscription()`, `run_field_subscription()`. All use `filters_json` for secondary filtering.

### 3.4 Entity Profile Pages

Route: `/entities/<entity_id>`, Jinja2 template with type-specific rendering.

Content per type:
- **Journal**: publisher, ISSN, impact factor, H-index, recent papers, related scholars/fields
- **Conference**: series info, acceptance rate, tier, recent papers, related fields
- **Scholar**: affiliations, H-index, citation count, paper list, co-authors, research interests
- **Field**: arXiv categories, description, key venues, key scholars, recent papers

Actions on every profile: [Subscribe] [View in OpenAlex/S2]

### 3.5 Entity Data Population

On-demand creation (no pre-seeded data):
- Search results automatically extract venue/author → create/update entities
- Manual subscription creation triggers metadata fetch from OpenAlex/Semantic Scholar
- `daily_pipeline` adds entity sync step for subscribed entities

---

## 4. Search Enhancement

### 4.1 Data Source Architecture

Three parallel sources via `ThreadPoolExecutor`:

| Source | Status | Notes |
|--------|--------|-------|
| arXiv API | Existing, stable | No changes needed |
| Semantic Scholar | Existing, unreliable | Fix: 5s connect / 10s read timeout, exponential backoff (max 2 retries), 60s failure cache |
| OpenAlex API | **New** | Free, no API key, `mailto` parameter for rate limits |

OpenAlex integration:
- Endpoint: `https://api.openalex.org/works?search=...&per_page=...`
- New `normalize_openalex_paper()` mapping to common schema
- Dedup order: DOI → arXiv ID → OpenAlex ID → normalized title

### 4.2 Query Rewriting

Optional LLM-powered query enhancement:

```python
class QueryRewriter:
    def rewrite(self, raw_query: str, context: dict) -> RewriteResult:
        # Returns: original, rewritten, explanation, expanded_terms
```

Strategies:
- Natural language → academic keywords
- Abbreviation expansion (RL → reinforcement learning)
- Synonym addition (GNN → "graph neural network OR GNN")
- **No LLM = no rewrite** (local-first fallback)

UI: subtle hint below search bar showing rewritten query, click to expand reasoning, one-click revert to original.

### 4.3 Search History

```sql
CREATE TABLE search_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    query          TEXT NOT NULL,
    rewritten      TEXT,
    result_count   INTEGER DEFAULT 0,
    sources        TEXT DEFAULT '[]',
    clicked_papers TEXT DEFAULT '[]',
    created_at     TEXT DEFAULT (datetime('now'))
);
```

Features:
- Search box focus → dropdown with recent 10 searches (deduped)
- High-frequency terms → "Suggested searches" tags on empty state
- Result page footer: "Related searches" based on query + history intersection

### 4.4 Search Result Filtering

Lightweight client-side grouping (no LLM):
- **By year**: timeline view toggle
- **By source**: arXiv / Semantic Scholar / OpenAlex badges
- **By venue type**: Conference / Journal / Preprint filter chips

Default: unified relevance sort. Filters appear as chips above result list.

### 4.5 Entity Auto-Extraction

Post-search async extraction:

```python
def extract_entities_from_results(papers: list[dict]) -> list[dict]:
    # Extract venue → create/update journal/conference entities
    # Extract authors → create/update scholar entities (if S2/OpenAlex author ID exists)
    # Non-blocking, does not affect search response time
```

---

## 5. Agent Session System

### 5.1 Data Model

```sql
CREATE TABLE agent_sessions (
    id            TEXT PRIMARY KEY,
    title         TEXT DEFAULT 'New Session',
    summary       TEXT DEFAULT '',
    is_pinned     INTEGER DEFAULT 0,
    is_archived   INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    last_active   TEXT DEFAULT (datetime('now')),
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE agent_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
    content       TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_agent_messages_session ON agent_messages(session_id, created_at);
```

### 5.2 AgentService Upgrade

Session-aware with multi-step execution:

```python
class AgentService:
    def handle_message(self, message, session_id, page_context):
        history = self.state_store.get_session_messages(session_id, limit=20)
        messages = self._build_context(history, message, page_context)
        plan = self._plan(messages, page_context)  # Returns AgentPlan with steps[]
        result = self._execute(plan, page_context)
        self.state_store.add_session_message(session_id, 'user', message)
        self.state_store.add_session_message(session_id, 'assistant', result['reply'], result.get('metadata'))
        if len(history) == 0:
            self._auto_title(session_id, message)
        return result
```

`AgentPlan.steps` supports chained actions: search → filter → create_collection → create_watch in a single response.

### 5.3 API Endpoints

```
POST   /api/agent/sessions                  — Create new session
GET    /api/agent/sessions                  — List sessions (?archived=0&limit=20)
GET    /api/agent/sessions/<id>             — Session detail + message history
PUT    /api/agent/sessions/<id>             — Update title/pin/archive
DELETE /api/agent/sessions/<id>             — Delete session
POST   /api/agent/sessions/<id>/messages    — Send message (core interaction)
```

Message response shape:
```json
{
  "success": true,
  "message": {
    "id": 42,
    "role": "assistant",
    "content": "Markdown content...",
    "metadata": {"tool_results": [], "actions": [], "state_updates": {}}
  },
  "session": {"id": "uuid", "title": "...", "message_count": 2}
}
```

### 5.4 Preact Agent Panel

Replaces current `frontend/agent/` and `agent-drawer.js`.

**Technology:**
- Preact (~3KB gzip) as component framework
- `marked` (~7KB gzip) for Markdown rendering
- Single JS + CSS build artifact, loaded by Jinja2 templates
- Communication with host page via `window.AppState` and CustomEvent

**Interaction model (Notion AI pattern):**
- Floating button (bottom-right): "Ask Agent"
- Click → side panel slides in (360px width), main content shrinks
- Panel top: session list (collapsible), [+ New] button
- Panel body: message flow with Markdown, action chips, typing indicator
- Panel bottom: input box (Enter send, Shift+Enter newline)
- Panel edge: drag to resize width
- Escape: close panel

**Session management:**
- Session list shows title, last active time, pin icon, message count
- Swipe/right-click: archive, delete
- Click session: load its message history

### 5.5 Auto-Title & Summary

- After first message: LLM generates title (fallback: first 30 chars of user message)
- Every 10 messages: update session summary for list preview
- No LLM: pure rule-based (message truncation)

---

## 6. Recommendation Engine Upgrade

### 6.1 Multi-Strategy Architecture

```python
class RecommendationEngine:
    strategies = [
        ForYouStrategy,       # User profile (reading history + subscriptions + feedback)
        EntityStrategy,       # Aggregated updates from subscribed entities
        ReadingStrategy,      # Similar papers to current reading queue
        TrendingStrategy,     # Citation velocity + freshness
        QuestionStrategy,     # Research question targeted (existing)
    ]
```

Each strategy returns unified `Candidate` objects:
```python
@dataclass
class Candidate:
    paper_id: str
    score: float
    source_strategy: str
    reason: str                # Human-readable recommendation reason
    score_breakdown: dict      # {relevance, citation, freshness, ...}
```

### 6.2 Multi-Dimensional Scoring

```python
class RecommendationScorer:
    weights = {
        'relevance':       0.35,  # Query/profile match
        'citation':        0.20,  # Citation count (log-scaled)
        'freshness':       0.15,  # Publication recency decay
        'entity_affinity': 0.15,  # Subscribed entity match count
        'feedback':        0.15,  # Historical signals (save/skim/ignore)
    }
```

- `entity_affinity`: paper venue/author hits against subscribed entities
- `feedback`: learned from `interaction_events` + `reading_queue_items`
- All dimensions normalized to 0-1, weighted sum

### 6.3 Recommendation Page

Section-based layout replacing single list:

| Section | Strategy | Layout |
|---------|----------|--------|
| For You | ForYouStrategy | Horizontal scrolling cards |
| From Your Subscriptions | EntityStrategy | Horizontal scrolling cards |
| Trending in {field} | TrendingStrategy | Horizontal scrolling cards |
| Based on Your Reading | ReadingStrategy | Horizontal scrolling cards |

- Each section loads independently (one strategy failure doesn't block others)
- Card click → right-side preview pane (reuses search split-pane pattern)
- Card shows: title, first author + year, one-line reason, venue tag
- Card hover: quick actions (Save / Skim / Deep Read)

### 6.4 User Profile (Phase 4)

Table created in Phase 2 but populated in Phase 4:

```sql
CREATE TABLE user_profile (
    id                INTEGER PRIMARY KEY DEFAULT 1,
    interest_vector   TEXT DEFAULT '[]',
    topic_weights     TEXT DEFAULT '{}',
    entity_affinities TEXT DEFAULT '{}',
    reading_pace      TEXT DEFAULT '{}',
    updated_at        TEXT DEFAULT (datetime('now'))
);
```

Accumulated from reading behavior, subscription operations, and search history during Phases 2-3. Activated for recommendation driving in Phase 4.

---

## 7. Phase Breakdown

### Phase 1: UI Foundation + Search Stability

**Scope:** Design tokens, breathing grid, Notion components, sidebar nav, OpenAlex integration, Semantic Scholar fixes, search filters, CSS restructure.

**Dependencies:** None (foundation for all subsequent phases).

**Acceptance criteria:**
- Light/dark mode toggle, all pages visually consistent
- Search returns 3-source results (arXiv required, others graceful degradation)
- Lighthouse Performance > 85, no layout shift

### Phase 2: Entity Subscription System

**Scope:** Entity tables + relations, subscription extension, EntityService, entity profile pages (4 types), auto-extraction from search, subscription runner new strategies, Watch page restructure, sidebar subscription items, `user_profile` table (created but not active).

**Dependencies:** Phase 1 design tokens and components, OpenAlex integration.

**Acceptance criteria:**
- Create subscriptions for all 4 entity types
- Entity profile pages display metadata and related papers
- `run_all_subscriptions()` executes new types and produces hits
- Search results auto-create relevant entities

### Phase 3: Agent Session System

**Scope:** Session/message tables, AgentService rewrite, Agent REST API, Preact panel (session list, message flow, Notion AI button), auto-title, `search_history` table, search history dropdown, query rewriting.

**Dependencies:** Phase 1 UI, Phase 2 entities (Agent operates on entities/subscriptions).

**Acceptance criteria:**
- Create session, multi-turn conversation, switch sessions, restore history
- Agent chains multiple actions in single response
- Panel open/close smooth, mobile usable
- All features degrade gracefully without LLM provider

### Phase 4: Recommendation Intelligence + Personalization

**Scope:** Recommendation engine refactor (4 strategies), multi-dimensional scorer, recommendation page redesign (sectioned cards), user profile activation, recommendation reasons, daily_pipeline adaptation.

**Dependencies:** Phase 2 entity data, Phase 3 search history and interaction data.

**Acceptance criteria:**
- Recommendation page shows 3+ strategy sections
- Each paper has human-readable recommendation reason
- Users with subscriptions/history get different results than empty-profile users
- Score breakdown visible per paper

### File Impact Matrix

```
File/Module                       P1     P2     P3     P4
───────────────────────────────────────────────────────────
static/research_ui.css           REWRITE incr   incr   incr
static/js/core.js                MODIFY  MODIFY MODIFY  —
templates/base_research.html     REWRITE MODIFY MODIFY  —
templates/search_research.html   REWRITE MODIFY MODIFY  —
templates/watch.html             MODIFY  REWRITE —      —
templates/recommendations.html   MODIFY   —      —     REWRITE
app/services/unified_search.py   MODIFY  MODIFY  —      —
app/services/agent_service.py     —       —     REWRITE  —
app/services/subscription_*       —      REWRITE —      —
app/services/recommendation_*     —       —      —     REWRITE
app/data/state_store.py           —      MODIFY MODIFY MODIFY
frontend/agent/                   —       —     REWRITE  —
NEW: entity_service.py            —      NEW     —      —
NEW: query_rewriter.py            —       —     NEW     —
NEW: recommendation_engine.py     —       —      —     NEW
```

---

## 8. Technical Constraints

- **Local-first**: all features must work without network (degraded but functional)
- **No LLM fallback**: query rewriting skipped, agent uses keyword planning, titles use truncation
- **SQLite WAL mode**: concurrent reads safe, write serialization via thread-local lock
- **Performance**: search response < 5s, agent response < 3s (excluding LLM latency), page load < 2s
- **Bundle size**: Agent panel Preact build < 50KB gzip total
- **Chinese support**: UI and Agent support Chinese input/output as a first-class language
