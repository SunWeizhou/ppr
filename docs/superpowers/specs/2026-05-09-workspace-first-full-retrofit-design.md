# Workspace-First Full Retrofit: Agent Literature Research Assistant

> **Status:** Design spec (pre-implementation).
> **Target:** Transform the current arXiv paper recommender into a workspace-first
> Agent Literature Research Assistant.
> **Constraint:** Keep existing Flask/Jinja2/SQLite architecture. Do not introduce
> a new frontend framework or database layer.

---

## 1. Product Goal

The product is a **local-first workspace** that helps a researcher turn a question
into a verified set of papers, evidence, reading decisions, and durable assets.

The defining shift from the current product is **workspace-first** instead of
**feed-first**:

| Current (feed-first) | Target (workspace-first) |
|---|---|
| Daily recommendation run is the primary entry point | The user's research workspace is the primary entry point |
| Papers arrive in a daily batch, user triages | Papers accumulate across sessions; user works through them |
| "Today" is the temporal anchor | "What needs my decision now" is the logical anchor |
| Search is a separate parallel feature | Search feeds into the same workspace as daily discovery |
| Agent analysis is optional enrichment | Agent analysis is structured with evidence links |
| Reading decisions are lightweight tags | Reading decisions include intent context and evidence |
| User profile is a config file | User profile is part of the workspace: questions, sources, subscriptions |

The workspace replaces the concept of a "daily run" with a **continuous
accumulation surface**. Papers arrive from multiple sources (daily pulls, search,
subscription hits) and converge into a single decision workflow.

---

## 2. Core Entity Model

```
ResearchQuestion
  ├─ query_text: str          — the canonical searchable form
  ├─ intent_statement: str    — the user's original question in natural language
  ├─ status: active|paused|archived
  ├─ source: manual|profile|subscription
  └─ created_at, updated_at

PaperCandidate
  ├─ paper_id: str            — canonical arXiv ID (no version suffix)
  ├─ title, authors, abstract, categories, published_at
  ├─ source_url: str          — link to the paper on arXiv
  ├─ source: daily|search|subscription|import
  ├─ source_run_id: uuid      — which pipeline run or search session brought it in
  └─ first_seen_at: datetime

AgentAnalysis
  ├─ paper_id: str            — FK to PaperCandidate
  ├─ analysis_type: rule|llm|hybrid
  ├─ problem: str
  ├─ method: str
  ├─ contribution: str
  ├─ limitations: str | null
  ├─ why_it_matters: str | null
  ├─ recommended_reading_level: ignore|skim|deep_read
  ├─ confidence: float | null  — 0.0 to 1.0, null for rule-based
  ├─ evidence_claim_ids: json  — list of UUIDs pointing to EvidenceClaim rows
  ├─ generated_at: datetime
  ├─ provider: str | null      — model name or "rule"
  └─ status: pending|ok|failed

EvidenceClaim
  ├─ id: uuid
  ├─ paper_id: str
  ├─ claim: str               — the specific claim the analysis makes
  ├─ evidence_text: str        — verbatim excerpt from the paper or metadata
  ├─ evidence_source: abstract|metadata|citation|user_note|other
  ├─ claim_type: factual|interpretive|caveat|gap
  └─ analyst: rule|llm|user

ReadingDecision
  ├─ paper_id: str
  ├─ decision: ignore|skim|deep_read|save
  ├─ context: str | null       — free-text reason for the decision
  ├─ research_question_id: uuid | null  — which question this decision serves
  ├─ decided_at: datetime
  └─ reverted_at: datetime | null

ResearchAsset
  ├─ asset_type: collection|note|export|digest
  ├─ name: str
  ├─ description: str | null
  ├─ asset_data: json          — type-specific payload
  └─ created_at, updated_at

Subscription
  ├─ name, type: question|author|venue|keyword
  ├─ query_text: str
  ├─ enabled: bool
  ├─ last_checked_at: datetime | null
  ├─ latest_hit_count: int
  └─ payload_json: json        — type-specific configuration
```

The workspace replaces the implicit "today" container. A workspace is **the set of
all PaperCandidate rows that have no terminal ReadingDecision** (ignore), plus
those the user has explicitly saved. The Inbox surface is a filtered view of this
workspace: papers that arrived recently and need a decision.

---

## 3. SQLite Schema Design Draft

### New tables (add to existing schema without breaking migration):

```sql
CREATE TABLE IF NOT EXISTS research_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    intent_statement TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'paused', 'archived')),
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK(source IN ('manual', 'profile', 'subscription')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence_claims (
    id TEXT PRIMARY KEY,  -- uuid string
    paper_id TEXT NOT NULL,
    claim TEXT NOT NULL,
    evidence_text TEXT NOT NULL DEFAULT '',
    evidence_source TEXT NOT NULL DEFAULT 'abstract'
        CHECK(evidence_source IN ('abstract','metadata','citation','user_note','other')),
    claim_type TEXT NOT NULL DEFAULT 'factual'
        CHECK(claim_type IN ('factual','interpretive','caveat','gap')),
    analyst TEXT NOT NULL DEFAULT 'rule'
        CHECK(analyst IN ('rule','llm','user')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (paper_id) REFERENCES paper_metadata(paper_id)
);

-- Enrich existing paper_metadata with workspace tracking fields
-- (ALTER TABLE additions, not a new table):
--   ALTER TABLE paper_metadata ADD COLUMN source TEXT DEFAULT '';
--   ALTER TABLE paper_metadata ADD COLUMN source_run_id TEXT DEFAULT '';
--   ALTER TABLE paper_metadata ADD COLUMN first_seen_at TEXT DEFAULT '';
--   ALTER TABLE paper_metadata ADD COLUMN workspace_status TEXT
--       DEFAULT 'active' CHECK(workspace_status IN ('active','archived'));

-- Enrich existing reading_queue_items with decision context:
--   ALTER TABLE reading_queue_items ADD COLUMN research_question_id INTEGER REFERENCES research_questions(id);
--   ALTER TABLE reading_queue_items ADD COLUMN decision_context TEXT DEFAULT '';

-- Enrich existing paper_ai_analyses with evidence links:
--   ALTER TABLE paper_ai_analyses ADD COLUMN evidence_claim_ids TEXT DEFAULT '[]';
--   ALTER TABLE paper_ai_analyses ADD COLUMN confidence REAL;
```

### Migration strategy:

1. Run all `ALTER TABLE` statements silently (they add nullable columns with
   defaults, safe for existing data).
2. Create new tables with `CREATE TABLE IF NOT EXISTS`.
3. Populate `research_questions` from the current user profile keywords on first
   migration (one question per active keyword).
4. Set `first_seen_at` for existing paper_metadata rows from their earliest
   recommendation_run or interaction_event date.
5. Development schema changes ship with backward-compatible reads: new code reads
   the new columns but existing UI paths that read the old columns continue to
   work until the UI migration completes.

### Rationale for ALTER TABLE over full schema rewrite:

- The current schema has ~15 tables with production data. A full migration is
  risky and time-consuming.
- Adding nullable columns is reversible (remove them after the migration window
  if needed).
- New tables (research_questions, evidence_claims) are pure additions with no
  migration cost.

---

## 4. Bounded Autonomous Planner (BAP) Mechanism

The current daily pipeline (`daily_pipeline.py`) runs a monolithic sequence:
fetch → score → rank → output. The BAP replaces this with a **scheduler +
planner** model that adapts to what the workspace needs.

### Design

```
┌─────────────────────────────────────────────────────────┐
│                    BAP Scheduler                         │
│  Run every N hours (configurable: 6/12/24)               │
│                                                          │
│  1. Snapshot workspace state:                            │
│     - Active research questions                          │
│     - Papers needing analysis                            │
│     - Subscription hits pending review                    │
│     - Last run time and results                          │
│                                                          │
│  2. Build a plan for this cycle:                         │
│     - How many papers to fetch per question              │
│     - Which papers need agent analysis                   │
│     - Which subscription sources to refresh              │
│     - Time budget for each phase                         │
│                                                          │
│  3. Execute plan phases:                                 │
│     Phase A: Fetch new candidates (time-boxed)           │
│     Phase B: Rank by relevance                          │
│     Phase C: Agent analysis (if configured)              │
│     Phase D: Route into workspace                        │
│     Phase E: Check subscriptions                         │
│                                                          │
│  4. Log execution results:                               │
│     - Candidates fetched per source                      │
│     - Analyses completed / skipped                       │
│     - New papers added to workspace                      │
│     - Errors and fallback actions                         │
└─────────────────────────────────────────────────────────┘
```

### Key differences from current pipeline:

| Current | BAP |
|---|---|
| Fixed daily run with hardcoded max results | Adaptive fetch count based on question count and backlog |
| Single monolithic `run_pipeline()` | Decomposed phases, each with own time budget |
| Pipeline owns the entire schedule | Scheduler decides what to run and when |
| Errors abort the entire run | Phase failures degrade gracefully; partial results are still routed |
| All papers get the same analysis treatment | Analysis scope adapts: rule-only for bulk, LLM for top-K |

### Phase execution contract:

```python
class BAPPhase:
    """Base contract for a BAP execution phase."""
    name: str
    time_budget_seconds: int

    def execute(self, context: BAPContext) -> BAPPhaseResult:
        """Execute this phase. Must raise BAPTimeout on time budget exceeded.
        Must return BAPPhaseResult even on failure (degrade, don't crash)."""
        ...
```

The scheduler runs phases sequentially. Each phase operates independently: if
Phase C (LLM analysis) fails because no API key is configured, Phases A, B, D,
and E still produce useful results for the workspace.

### Scheduler plan document (stored as JSON in job_runs table):

```json
{
  "plan_id": "uuid",
  "trigger": "scheduled|manual",
  "questions_queries": ["conformal prediction", ...],
  "phase_budget_seconds": {"fetch": 30, "rank": 10, "analyze": 60, "route": 5, "subscribe": 20},
  "max_candidates_per_question": 10,
  "analysis_llm_top_k": 5
}
```

---

## 5. Evidence-Linked Claims Schema

Agent analysis is only useful when the user can verify it. The Evidence-Linked
Claims system attaches every substantive claim in an analysis to a specific
piece of evidence the user can inspect.

### Data model (see also §3 `evidence_claims` table):

```python
@dataclass
class EvidenceClaim:
    id: str                    # uuid
    paper_id: str
    claim: str                 # e.g. "This paper proves an O(log n) regret bound"
    evidence_text: str         # e.g. "Theorem 3.1: Under Assumptions A1-A3, algorithm X achieves..."
    evidence_source: str       # "abstract" | "metadata" | "citation" | "user_note" | "other"
    claim_type: str            # "factual" | "interpretive" | "caveat" | "gap"
    analyst: str               # "rule" | "llm" | "user"
```

### How analysis produces evidence-linked claims:

```
User query: "minimax rates for nonparametric regression"
    │
    ▼
[1] Fetch candidates from arXiv
    │
    ▼
[2] For each top-K candidate, invoke analysis service
    │
    ├─ Rule-based path (no LLM):
    │   Extract abstract sentences, category metadata
    │   → Generate EvidenceClaim for each factual snippet
    │   → Aggregate into basic AgentAnalysis
    │
    └─ LLM path (configured):
        Send structured prompt: paper context + abstract
        → Parse response into claims with evidence_text
        → Store each claim as EvidenceClaim
        → Store AgentAnalysis with evidence_claim_ids list
    │
    ▼
[3] Paper Detail page renders claims with evidence source labels
    Each claim shows:
    • The claim text
    • The verbatim evidence (expandable)
    • The source badge (Abstract | Metadata | Generated)
    • The analyst badge (Rule | AI | User)
```

### Rendering contract (Paper Detail page):

```
[Heading] Agent Analysis
─────────────────────────────────────────────
▸ Problem: [claim text]
  📖 Evidence: [expandable evidence_text]
  🔖 Source: Abstract   🤖 Analyst: AI

▸ Method: [claim text]
  📖 Evidence: ...
  🔖 Source: Abstract   🤖 Analyst: AI

▸ Contribution: [claim text]
  📖 Evidence: ...
  🔖 Source: Citation   🤖 Analyst: AI

▸ Limitations: [claim text]
  📖 Evidence: ...
  🔖 Source: Generated  🤖 Analyst: AI
─────────────────────────────────────────────
[Generate Analysis] button (when no LLM)
```

The evidence is **always visible** but **de-emphasized by default** (expandable).
The claim text is the primary content; evidence confirms or contextualizes it.
This is the core difference from the current flat "AI Analysis" dump.

---

## 6. Surfaced Redesign

### 6.1 Inbox (workspace entry point)

**Current:** `today.html` — single-day paper list with triage actions.
**Target:** `inbox.html` — workspace-wide decision queue.

The Inbox becomes a **smart queue** that shows papers needing decisions, ranked
by arrival recency and urgency:

- **Default view:** All undecided papers from the last N days, grouped by source
  (Daily Run | Search | Subscription Hit), sorted by recency.
- **Filterable:** By source, by research question, by recency window.
- **Each card shows:** title, authors, short abstract, agent summary (1-2
  sentences), why-line (why surfaced), decision buttons.
- **Batch action:** "Skim all from yesterday", "Ignore outdated".
- **Empty state:** "No papers need decisions. [Search for something] or
  [Check subscriptions]."
- **Key behavioral change:** Papers persist across days. The user is not
  pressured to triage everything in one session.

### 6.2 Search / Explore

**Current:** `search_research.html` — keyword search, saved queries sidebar.
**Target:** `search.html` — research question entry point with session-based
results.

- **Search bar prominently** accepts research questions, not just keywords.
- **Results display:** Title, authors, short abstract, agent summary (inline,
  not hidden behind a detail link), relevance score.
- **Post-search actions:** Queue for decision, Save to collection, Create
  subscription from query, Save paper metadata for detail lookup.
- **Search-to-workspace:** Every paper viewed in search results is added to the
  workspace if the user clicks "Queue" or "View Detail".
- **Session persistence:** Search results are cached for the session so back
  navigation preserves context.

### 6.3 Paper Detail

**Current:** `paper_detail.html` — flat page with abstract, AI analysis block,
actions sidebar.
**Target:** `paper_detail.html` — evidence and action center with structured
sections.

- **Hero:** Title, authors, arXiv link, PDF, BibTeX.
- **Agent Analysis section:** Structured claims with evidence links (see §5).
  Section is present even without LLM (rule-based analysis from abstract).
- **Evidence tab (new):** Expandable claims with evidence source badges.
- **Decision section:** Ignore / Skim / Deep Read / Save buttons, active status
  badge, optional context textarea ("Why this decision?").
- **Research question context:** Which question(s) this paper relates to.
- **History:** Interaction events with timestamps (liked, queued, opened).
- **Collections:** Which collections contain this paper.
- **No more "Paper not found":** The graceful shell from the stability repair
  ensures every linked paper renders something useful.

### 6.4 Reading

**Current:** `reading.html` — queue items with Skim Later / Deep Read / Saved /
Archived tabs.
**Target:** `reading.html` — active reading workbench.

- **Tab structure stays** (Skim Later, Deep Read, Saved, Archived).
- **Enhanced card:** Each card shows decision context ("Why Deep Read?"), agent
  summary, evidence snippet.
- **Decision advancement:** Move from Skim → Deep Read → Saved as user works
  through papers.
- **Note capture (new):** Brief free-text notes per paper, stored as
  ResearchAsset with asset_type="note".
- **Research question filtering:** Filter reading items by the research question
  that prompted them.

### 6.5 Watch

**Current:** `watch.html` (also `track_research.html`) — subscriptions by type,
recent hits.
**Target:** `watch.html` — subscription cockpit with hit triage.

- **Stays as subscription management surface.**
- **Hit triage (new):** Each hit now has a "Route to Inbox" action that adds the
  paper to the user's workspace for decision.
- **Match explanation:** Show why the hit matched (which query terms, author
  match, venue match).
- **Subscription health:** Last checked timestamp, hit count trend, next check
  time.
- **Unified subscription creation:** One dialog for all types (question/author/
  venue/keyword), with type-specific fields.

### 6.6 Settings

**Current:** `settings_research.html` — profile, sources, AI provider, diagnostics.
**Target:** `settings.html` — workspace configuration.

- **Keep current structure** (tabs for Profile, Sources, AI, Diagnostics, Data).
- **New tab: Research Questions** — manage the active research questions that
  drive the BAP scheduler. Add, pause, archive, reorder.
- **New tab: Workspace** — workspace statistics: total papers, undecided count,
  decisions made, subscription coverage.
- **Keep masked API key behavior** from stability repair.
- **Keep backup/restore/export** functionality.

---

## 7. Claude.ai-like Design Principles

These principles guide the product's interaction design without copying any
specific UI. Apply them to the surfaces described in §6.

### 7.1 Start from intent, not features

The product should not present itself as a set of features ("This is the search
page, this is the reading page"). It should present itself as a research
assistant that asks "What do you want to do?" and then shows the tools needed.

Concrete implications:
- Onboarding asks "What are you researching?" not "Enter your keywords."
- The Inbox is titled "Papers needing your review" not "Today's Recommendations."
- Empty states guide toward the next useful action, not toward a feature.

### 7.2 Show reasoning, not just output

Every recommendation, analysis, or decision should be explainable. The user
should never wonder "Why was this paper surfaced?" or "Why did the system say
this?"

Concrete implications:
- Every paper card in Inbox has a visible why-line.
- Every Agent Analysis claim has an evidence source.
- Subscription hit cards show the matching rule.
- Pipeline execution logs are accessible from Settings → Diagnostics.

### 7.3 Reduce to the decision

Each surface should minimize cognitive overhead. If a page shows 30 options, the
user has to decide what to do. If it shows 2-3 primary actions, the user can
decide quickly.

Concrete implications:
- Inbox paper cards show 4 decision buttons (Ignore / Skim / Deep Read / Save)
  and a detail link. No secondary actions compete for attention.
- Search results default to showing the agent summary, not all metadata.
- Settings pages group related fields; the save button is the primary action.

### 7.4 Degrade gracefully, never fail silently

Every feature should work without an AI provider, without a network connection,
and without pre-existing data. Optional features are clearly optional.

Concrete implications:
- No LLM → rule-based analysis still produces structured evidence.
- No network → cached papers and decisions are fully accessible.
- No recommendations yet → empty state guides to search or onboarding.
- API errors → show what failed and what still works, don't hide the failure.

### 7.5 Work offline-first

All core workflows must function without internet. Online features (arXiv search,
subscription checks) are additive.

Concrete implications:
- All pages render from local SQLite.
- Search results are cached locally for the session.
- Reading decisions and notes are saved immediately, not batched.
- When online, sync is invisible (the user doesn't click "sync").

---

## 8. Phased Implementation Plan

### Phase 1: Workspace Backend (estimated 2-3 weeks)

Goal: Ship the new schema and BAP scheduler without changing the UI.

- [ ] Add new tables: `research_questions`, `evidence_claims`.
- [ ] Run ALTER TABLE migrations on existing tables.
- [ ] Implement BAP scheduler with phase decomposition.
- [ ] Implement `EvidenceClaim` creation in analysis service.
- [ ] Seed `research_questions` from current profile keywords.
- [ ] Add workspace stats endpoint.
- [ ] Write migration tests (no data loss, rollback capability).
- **UI changes:** None. Old UI continues to read old columns.
- **Test target:** `python -m pytest tests/ -q` → all existing pass, new migration
  tests pass.

### Phase 2: Inbox + Search Surface Update (estimated 2 weeks)

Goal: Update the two highest-traffic surfaces.

- [ ] Create `templates/inbox.html` with workspace-aware viewmodel.
- [ ] Add filter by source, research question, recency.
- [ ] Add batch action support.
- [ ] Update search results to save paper metadata and render agent summaries.
- [ ] Wire search-to-workspace (click adds paper to workspace).
- **Test target:** New Inbox and Search viewmodel tests; Playwright smoke test
  for the two surfaces.

### Phase 3: Paper Detail with Evidence (estimated 2 weeks)

Goal: Replace flat AI Analysis with structured evidence-linked claims.

- [ ] Render EvidenceClaims in paper_detail.html with expandable evidence.
- [ ] Wire rule-based analysis as fallback (no LLM needed).
- [ ] Add evidence source badges (Abstract / Metadata / Generated).
- [ ] Keep LLM path as optional upgrade.
- **Test target:** Unit tests for evidence claim creation; detail page route test
  with and without LLM.

### Phase 4: Reading + Watch Enhancement (estimated 1 week)

Goal: Add decision context, note capture, hit triage.

- [ ] Add decision context textarea to reading items.
- [ ] Add free-text notes per paper (ResearchAsset).
- [ ] Add "Route to Inbox" action on subscription hits.
- [ ] Show hit match explanations in Watch.
- **Test target:** Reading and Watch viewmodel tests; route availability.

### Phase 5: Settings + Docs + Polish (estimated 1 week)

Goal: Research question management, workspace stats, cleanup.

- [ ] Add "Research Questions" tab to Settings.
- [ ] Add "Workspace" stats tab to Settings.
- [ ] Remove old daily-run-references from remaining UI text.
- [ ] Update inline docs for new workflow.
- **Test target:** Settings page tests; full regression suite.

---

## 9. Test Plan

### 9.1 Unit tests

| Area | What to test |
|---|---|
| BAP scheduler | Phase execution, timeout handling, partial failure, plan generation |
| EvidenceClaim | Creation from abstract, from LLM response, from user note |
| ResearchQuestion | CRUD, status transitions (active→paused→archived) |
| Workspace view | Filtering by source, question, recency; batch operations |
| Schema migration | ALTER TABLE idempotency, backward compatibility, rollback |

### 9.2 Integration tests

- BAP scheduler with mocked arXiv source (no network).
- Search → workspace pipeline: search, save metadata, verify detail page.
- Evidence claim rendering with and without LLM.
- Subscription hit → route to Inbox → decision flow.

### 9.3 Migration safety tests

- `test_schema_migration_adds_columns_without_data_loss`: Run ALTER TABLE on a
  copy of the current schema, verify old rows are untouched.
- `test_schema_migration_is_idempotent`: Running the migration twice produces
  the same result.
- `test_new_tables_created_if_not_exists`: CREATE TABLE IF NOT EXISTS is
  idempotent.

### 9.4 Visual regression

- Skip this round. Goldens are not seeded. Visual changes will be validated by
  manual browser review until goldens are available.

---

## 10. Non-Goals (Explicit)

The following are explicitly out of scope for this retrofit:

- **Full PDF annotation:** The product will not support in-browser PDF annotation,
  highlighting, or margin notes. External PDF viewing is fine.
- **Cloud sync or hosted accounts:** All state stays local. No auth, no accounts,
  no sync.
- **Team collaboration:** No shared workspaces, permissions, comments, or
  multi-user features.
- **Mandatory AI provider:** All analysis must work without an external AI
  provider. LLM features are additive.
- **Frontend framework rewrite:** Keep Flask/Jinja2/vanilla JS. Do not introduce
  React, Vue, or similar.
- **Full citation graph exploration:** No citation network visualization, graph
  DB, or large-scale citation traversal in this phase.
- **Automatic literature review:** The product supports researcher judgment, it
  does not replace it.
- **Mobile app or responsive redesign:** Keep desktop-first. Responsive
  improvements are not a goal of this phase.
- **Removal of existing services:** The retrofit adds to the existing codebase;
  it does not delete or rewrite `scoring_service.py`, `recall.py`, `ranker.py`,
  or `learner.py`. Those continue to work until a future deprecation phase.
