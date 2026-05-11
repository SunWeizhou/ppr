# Paper Agent — Product Requirements Document

## 1. Product Definition

Paper Agent is a local-first paper discovery and research workspace. It helps
researchers move from a topic or research question to a useful set of papers,
reading decisions, watches, collections, notes, and optional AI analysis.

The interaction model is search-first: results stay on the same workspace, the
selected paper opens in a right-side preview, and deeper reading happens only
when the user explicitly asks for it. A local AI Agent drawer can execute common
research actions (save, search, watch, summarize) through natural language
instead of clicking.

All user data stays on disk in SQLite. The product works without a network
connection for local operations and without any AI provider configured.

## 2. Target Users

- **Graduate students** building a thesis or project literature base. Needs
  efficient search across sources and persistent tracking of reading progress.
- **Independent researchers** tracking fast-moving methods or domains. Needs
  watch subscriptions and periodic discovery without manual search repetition.
- **Applied scientists** comparing methods before implementation. Needs
  structured evidence and reading-level recommendations for quick triage.
- **Engineers and founders** using papers as evidence for product or model
  choices. Needs collections, BibTeX export, and shareable reading lists.

## 3. Positioning & Non-Goals

### Positioning

Paper Agent is a search-first research workspace with durable local state. It is
not a daily feed, a citation graph clone, or a generic chat UI.

Core promise:

1. Search across arXiv, Semantic Scholar, and OpenAlex from a single bar.
2. Inspect results without losing context (preview in same page).
3. Generate recommendation candidate sets with visible "why recommended" context.
4. Route papers into reading decisions, collections, or watches.
5. Use an Agent drawer to chat, render Markdown, and run common local tools.
6. Keep everything local, exportable, and usable without AI.
7. Browse and subscribe to journals, conferences, scholars, and research fields as structured entities.
8. Maintain persistent Agent sessions with multi-turn conversation context.

### Non-Goals

- Cloud account system, team collaboration, or permissions.
- Full PDF annotation or inline PDF reading.
- Full citation graph exploration (may be considered in future).
- Full React/Vite frontend rewrite. React is allowed only as an embedded Agent
  island while Flask + Jinja2 remain the application shell.
- Hosted autonomous agent that acts outside the local app or without user-visible
  tool results.
- Real-time collaboration or multiplayer features.
- Fully automatic literature review that replaces researcher judgment.
- Required AI provider (AI is enhancement only).

## 4. Design Principles

### Local-First

User data stays on disk in SQLite. No accounts, cloud sync, or hosted state
required for core workflow. Export and backup are first-class operations.

### Optional AI

AI analysis is an enhancement, not a dependency. The product must remain fully
usable with no provider configured. Secrets are never rendered in full, exported,
or logged.

### Explainable Ranking

Ranking remains interpretable. Keyword, topic, feedback, subscription, and
semantic signals should be visible enough for the user to understand why a paper
was surfaced.

### Thin Routes, Testable Services

Routes validate input, call services, build viewmodels, and render responses.
Business logic belongs in services and state adapters where it can be tested
without a browser or network.

### Visual Design

- Notion-style design language: generous whitespace, clean hierarchy, precise micro-interactions.
- Claude/Apple color palette with unified design tokens (3-layer: primitive → semantic → component).
- Breathing grid background inspired by Claude Cowork (animated opacity cycling, static on prefers-reduced-motion).
- Dark mode as first-class citizen via `[data-theme="dark"]` semantic token switching.
- Left sidebar navigation (Notion-style), replacing top pill navigation.
- English and Chinese supported as first-class UI languages.

## 5. Core Objects

| Object | Description |
| --- | --- |
| **Paper Candidate** | A normalized result from arXiv, Semantic Scholar, Watch, planner runs, imports, or future connectors. Stored in SQLite paper_metadata. |
| **Search Query** | A user-entered topic, author, paper title, or research question that drives discovery. |
| **Research Question** | A workspace-level research intent that scopes planner runs, evidence collection, and subscription routing. |
| **Reading Decision** | The user's state for a paper: Ignore, Skim Later, Deep Read, Saved, or Archived. Persisted in queue_items. |
| **Collection** | A local research asset that groups papers. Supports BibTeX/JSON export. |
| **Note** | A user-authored observation attached to a paper or collection. |
| **Watch (Subscription)** | A long-running query, author, or venue subscription that produces hits over time. Types: query, author, venue. |
| **Subscription Hit** | A paper discovered by a subscription run. Can be sent to inbox, ignored, or previewed. |
| **Agent Action** | A locally executed tool call from the Agent drawer (search, save, mark, watch, collection, summarize). |
| **Job** | A background task (daily pipeline, subscription run, evaluation). Lifecycle: queued → running → succeeded/failed. |
| **AI Analysis** | A structured 7-field analysis of a paper generated by an OpenAI-compatible provider. Cached in SQLite. |
| **Entity** | A structured representation of a journal, conference, scholar, or research field. Browsable with profile pages and subscribable for tracking updates. |
| **Entity Relation** | A typed link between entities (publishes_in, affiliated_with, researches, subfield_of). Used for profile page "related entities" display. |
| **Agent Session** | A persistent conversation thread with the AI Agent. Contains message history, auto-generated title, pin/archive state. |
| **Agent Message** | A single message within an Agent session. Roles: user, assistant, system, tool. Includes metadata for tool results and actions. |
| **Search History** | A record of past search queries with result counts, source breakdown, and clicked papers. Powers search suggestions. |
| **User Profile** | Aggregated user interest model built from reading behavior, subscriptions, and search history. Drives personalized recommendations. |

## 6. Primary Workflow

1. **Search** — User opens `/` and searches papers, authors, or topics. Results
   appear in-page from arXiv and Semantic Scholar simultaneously.

2. **Preview** — User clicks a result. The right preview updates without
   navigation. Preview exposes Save, Mark Skim, Deep Read, Create Watch, and
   Open full detail.

3. **Decide** — User routes papers into Reading (with status), collections, or
   watches. Decisions are consistent across Search, Detail, Reading, and Watch.

4. **Deep Read** — `/papers/<id>` shows full abstract, structured AI analysis
   (when available), rule-based evidence claims, notes, and action rail.

5. **Continue** — Reading keeps active papers and saved assets. Watch monitors
   topics and routes hits back into the same decision flow. Settings makes
   sources, AI provider, diagnostics, and local state transparent.

## 7. Product Surfaces

### 7.1 Search (`/`)

Search is the default home surface and primary entry point.

Required behavior:
- Single top search bar with placeholder `Search papers, authors, topics...`.
- Left result list with author/year, title, venue/source, and abstract excerpt.
- Right preview panel with Article and Notes tabs.
- Preview actions: Save to Reading, Mark Skim, Deep Read, Create Watch, Open
  full detail.
- arXiv and Semantic Scholar status shown independently (ok/failed per source).
- Result deduplication across sources (by DOI, arXiv ID, or normalized title).
- Mobile layout avoids horizontal overflow; preview collapses on narrow screens.
- Research question context shown when entered from a workspace.
- OpenAlex as third search source alongside arXiv and Semantic Scholar.
- Query rewriting: optional LLM-powered query enhancement with visible explanation and one-click revert. Skipped when no AI provider is configured.
- Search history: recent searches dropdown on focus, suggested search tags on empty state.
- Result filter chips: by year, by source (arXiv/S2/OpenAlex), by venue type (conference/journal/preprint).
- Entity auto-extraction: search results asynchronously create/update venue and author entities.

### 7.2 Paper Detail (`/papers/<id>`)

Paper Detail is the deep reading page for a single paper.

Required behavior:
- Preserve return query when entered from Search (`?return_q=`).
- Show title, authors, source metadata, full abstract, AI analysis, evidence
  claims, notes, and action rail.
- Abstract is never replaced by `summary_short` — always show full abstract.
- Without AI provider: show rule-based evidence fallback, not a settings detour.
- AI analysis displays 7 structured fields: one_sentence_summary, problem,
  method, contribution, limitations, why_it_matters, recommended_reading_level.
- Notes can be added and edited per paper.

### 7.3 Reading (`/reading`)

Reading is the lightweight local library for managing paper states.

Required behavior:
- Tabs: Active, Skim Later, Deep Read, Saved, Archived, Collections.
- Every paper row has consistent quick actions (change status, open detail).
- Collections can be created from Search, Detail, Watch, or Agent.
- Collection detail shows member papers with notes.
- Export BibTeX and JSON for collections.
- Search/filter within reading list.

### 7.4 Watch (`/watch`)

Watch monitors real subscriptions and their hits over time.

Required behavior:
- Display active research watches, author watches, venue watches.
- Each watch shows: query/author/venue, status, last checked, hit count, health.
- Recent hits section with preview, Send to Reading, Ignore, Create collection.
- Paused watches section for disabled subscriptions.
- Source health indicators (arXiv, Semantic Scholar availability).
- Fixture or test data must never leak into the runtime Watch page.
- Manual and auto-scheduled subscription runs supported.
- Entity-based subscriptions: subscribe to journal, conference, scholar, or field entities with optional filters (min citations, date range, keywords).
- Each subscription can link to a structured entity with its own profile page.

### 7.5 Settings (`/settings`)

Settings is for trustworthy local configuration and diagnostics.

Required behavior:
- Tabs: Profile, Keywords, AI, Scholars, Diagnostics.
- AI provider: `none` or OpenAI-compatible. DeepSeek is a preset, not a separate
  provider type.
- Key precedence: `OPENAI_COMPATIBLE_API_KEY` > `DEEPSEEK_API_KEY` >
  `STATDESK_AI_API_KEY`.
- UI shows provider, model, key source, masked key, and connection test status.
- Diagnostics show: source health, Semantic Scholar availability, arXiv
  availability, AI readiness, local DB identity, latest job state, queue counts.
- Backup and restore for full state export/import.
- API keys never rendered in full in HTML or exported.

### 7.6 Evaluation (`/evaluation`)

Evaluation provides offline quality measurement for the recommendation system.

Required behavior:
- Run evaluation experiments against current ranking configuration.
- Display evaluation reports with metrics (precision, recall, nDCG when
  applicable).
- List historical evaluation runs with timestamps and parameters.
- Subprocess-based execution with timeout (120s).

### 7.7 Onboarding (`/onboarding`)

Onboarding guides first-time users through initial setup.

Required behavior:
- Collect research topics, priority keywords, and optional scholar profiles.
- Create initial Research Question from user's first query.
- Create initial query subscription bound to the research question.
- Skip gracefully if user navigates away (no broken state).
- Redirect to Search workspace on completion.

### 7.8 AI Agent Panel

The Agent is a persistent conversation assistant accessed via a Notion AI-style floating button. It provides natural-language access to all local actions with multi-turn context within sessions.

Required behavior:
- Floating "Ask Agent" button (bottom-right), click to expand side panel (360px).
- Persistent sessions: create, switch, pin, archive, delete conversations.
- Multi-turn context: Agent retains last 20 messages within a session.
- Multi-step execution: Agent can chain multiple actions in a single response (e.g., search → filter → create collection).
- Session auto-title via LLM (fallback: first 30 chars of user message).
- Preact-based panel (~50KB gzip budget) communicating via REST API.
- Markdown rendering in messages with action chips for executed tools.
- Page context awareness: reads current route, query, selected paper from host page.
- Panel resizable via edge drag, closeable via Escape.
- Mobile: full-width overlay panel.
- All features degrade gracefully without AI provider (keyword intent classification, rule-based titles).

### 7.9 Entity Profiles (`/entities/<id>`)

Entity Profiles provide browsable pages for journals, conferences, scholars, and research fields.

Required behavior:
- Four entity types: journal, conference, scholar, field — each with type-specific metadata display.
- Journal profile: publisher, ISSN, impact factor, H-index, recent papers, related scholars/fields.
- Conference profile: series info, acceptance rate, tier, recent papers, related fields.
- Scholar profile: affiliations, H-index, citation count, paper list, co-authors, research interests.
- Field profile: arXiv categories, description, key venues, key scholars, recent papers.
- Subscribe action available on every profile page.
- Entity data populated on-demand from search results and OpenAlex/Semantic Scholar metadata.
- Related entities section powered by entity_relations table.

## 8. Agent Interaction Specification

### 8.1 Interaction Model

The Agent operates as a local tool dispatcher with a Preact chat surface. The
front-end keeps the visible session thread; each backend request includes the
current page context and returns structured tool results. Backend persists
conversation sessions in SQLite. Each session maintains message history for
multi-turn context.

**Input:**
```json
{
  "message": "save this paper",
  "session_id": "uuid",
  "page_context": {
    "route": "/",
    "query": "federated learning",
    "selected_paper_id": "arxiv:2604.12345",
    "selected_paper_title": "Paper Title"
  }
}
```

**Output:**
```json
{
  "success": true,
  "reply": "Saved \"Paper Title\" to Reading.",
  "messages": [{"role": "assistant", "content": "Saved \"Paper Title\" to Reading."}],
  "actions": [{"type": "queue", "paper_id": "arxiv:2604.12345", "status": "Saved"}],
  "state_updates": {},
  "requires_confirmation": false,
  "confirmation_token": "",
  "tool_results": [{"tool": "mark_reading_decision", "status": "succeeded", "paper_id": "arxiv:2604.12345", "decision": "Saved"}]
}
```

### 8.2 Intent Classification

The Agent first handles clear local tool commands deterministically so common
actions stay fast and offline. For ambiguous chat/planning, it may ask the
OpenAI-compatible provider for a JSON intent plan and falls back to deterministic
help if provider planning is unavailable.

| Intent | Trigger Keywords | Action |
| --- | --- | --- |
| `confirm_required` | delete, remove all, overwrite api key, bulk archive | Block with confirmation message |
| `collection` | collection, collect this | Create collection + add paper |
| `summarize` | summarize, summary, what is this paper | Return Markdown summary from stored metadata |
| `analysis` | analysis, analyze, analyse | Navigate to detail page |
| `save` | save, saved, keep | Mark paper as Saved |
| `deep_read` | deep read, deepread | Mark paper for Deep Read |
| `skim` | skim, later | Mark paper as Skim Later |
| `watch` | watch, subscribe, monitor | Create query subscription |
| `planner` | planner, plan | Report planner needs research question |
| `search` | search, find, look for | Navigate to search with query |
| `recommendations` | recommend, 推荐 | Navigate to Recommendations |
| `answer` | (fallback) | Return help message |

Clear local tool commands always win over provider planning. This prevents
simple actions such as "save this paper" from waiting on a remote model.

### 8.3 Capability Boundaries

**CAN do (currently implemented):**
- Search papers (via navigation to `/?q=`)
- Open Recommendations
- Save paper to Reading queue
- Mark reading decisions (Skim Later, Deep Read, Saved)
- Create collections and add selected paper
- Create watch subscriptions from current query
- Navigate to paper detail for AI analysis
- Return Markdown-rendered summaries from stored metadata
- Report tool execution results
- Maintain persistent conversation sessions with message history
- Execute multi-step action chains in a single response
- Operate on structured entities (subscribe, browse profiles)

**CANNOT do (explicit limitations):**
- Cross-session context sharing (sessions are independent)
- Full paper summarization beyond locally stored abstract/metadata unless a
  provider-backed tool is explicitly added
- Execute planner without an active research question
- Perform inline AI analysis (navigates to detail page instead)
- Delete papers, collections, or subscriptions
- Bulk operations
- Stream responses
- Access papers not currently selected in the UI

### 8.4 Confirmation & Error Recovery

**Confirmation flow:**
- Destructive intents (delete, overwrite, bulk) set `requires_confirmation: true`
  and return a blocking message.
- Current limitation: front-end displays the confirmation message but has no
  confirm/cancel dialog — the user must rephrase or act manually.

**Error recovery:**
- Missing `selected_paper_id` when required: returns generic help message.
- Duplicate collection name: retries with suffix (up to 3 attempts), then
  reports failure.
- Store operation failure: no retry, error propagates as failed tool_result.

### 8.5 Degradation Without AI Provider

The Agent does **not** require an AI provider. All intent classification and
action execution is deterministic and local. Without an AI provider:
- "summarize" returns the first 420 characters of the stored abstract.
- "analysis" navigates to the detail page where rule-based evidence is shown.
- Auto-title uses the first 30 characters of the user message when no LLM is available.
- All other intents work identically.

## 9. Background Services

### 9.1 Daily Pipeline

The daily recommendation pipeline fetches, scores, and persists paper candidates.

- **Trigger**: `POST /api/refresh` (manual) or scheduled externally.
- **Execution**: Background daemon thread; job lifecycle tracked in SQLite.
- **Steps**: Fetch from arXiv categories → score with EnhancedScorer → persist
  paper metadata and recommendation run → generate digest artifacts.
- **Configuration**: arXiv categories, lookback days, papers per day, embedding
  model toggle.
- **Recovery**: Stale jobs recovered after 120 minutes on server startup.

### 9.2 Subscription Runner

Runs subscriptions to discover new papers matching saved watches.

- **Types**: query (keyword search), author (scholar tracking), venue (journal
  monitoring).
- **Execution**: Synchronous per-subscription or batch via `POST
  /api/subscriptions/run-all`.
- **Sources**: Local recommendation data + arXiv API search.
- **Deduplication**: Hits are deduped against existing hits before persistence.
- **Result**: New hits persisted with subscription_id, paper metadata stored.

### 9.3 Workspace Planner

Bounded planner for research-question-driven discovery.

- **Phases**: plan → discover → rank → analyze → route.
- **Budget**: max_query_rewrites=3, max_candidates=25, max_analyses=10,
  days_back=60, per-phase time budgets.
- **Output**: Creates a recommendation run scoped to the research question,
  routes discovered papers into the inbox.
- **Current state**: Phase 1 implemented (deterministic plan recording and
  search). Adaptive query rewrites and AI-driven phases are future work.

### 9.4 Feedback Learner

Trains a personalization model from user interactions.

- **Input**: Like/dislike feedback events, reading decisions, queue status
  changes.
- **Model**: Logistic regression over paper embeddings + interaction features.
- **Training**: Triggered when sufficient new feedback accumulates (`POST
  /api/feedback/learn`).
- **Output**: Learned weights used as a signal in the scoring pipeline.

### 9.5 Entity Sync

Keeps subscribed entity metadata current.

- **Trigger**: Part of daily pipeline or `POST /api/entities/sync`.
- **Scope**: Only entities with active subscriptions.
- **Sources**: OpenAlex API (primary), Semantic Scholar API (secondary).
- **Updates**: Stats (citation counts, paper counts), metadata (impact factor, H-index).
- **Creation**: Entities auto-created from search results; manual creation via subscription flow.

## 10. AI Provider Integration

### Provider Types

| Provider | Class | When Used |
| --- | --- | --- |
| None | `NoProvider` | Default. Returns empty analysis fields. Product fully functional. |
| Fake | `FakeProvider` | Test only. Returns deterministic placeholder analysis. |
| OpenAI-compatible | `OpenAICompatibleProvider` | Production. Calls any OpenAI-compatible API endpoint. |

DeepSeek is a **preset** for OpenAI-compatible (base_url=`https://api.deepseek.com`,
model=`deepseek-chat`), not a separate provider type.

### Key Precedence

Environment variables checked in order:
1. `OPENAI_COMPATIBLE_API_KEY` (explicit OpenAI-compatible configuration)
2. `DEEPSEEK_API_KEY` (DeepSeek preset shorthand)
3. `STATDESK_AI_API_KEY` (legacy backward-compatible key)

### Analysis Output Schema

```json
{
  "one_sentence_summary": "...",
  "problem": "...",
  "method": "...",
  "contribution": "...",
  "limitations": "...",
  "why_it_matters": "...",
  "recommended_reading_level": "skim|deep_read|save|ignore"
}
```

### Fallback Behavior

Without a provider: all analysis fields are empty strings,
`recommended_reading_level` defaults to `"skim"`. Rule-based evidence claims
(from `EvidenceClaimService`) remain available on the detail page.

## 11. Performance & Reliability Constraints

| Operation | Target | Timeout | Notes |
| --- | --- | --- | --- |
| Agent message | < 200ms | None (all local) | No network, no AI |
| Search (dual-source) | < 5s | 20s per source | arXiv + Semantic Scholar in parallel |
| AI analysis generation | < 30s | 60s | Single provider API call |
| Daily pipeline | < 5min | 120min stale recovery | Background thread |
| Subscription run (single) | < 10s | 20s | arXiv API + local data |
| Evaluation run | < 2min | 120s subprocess | Terminates on timeout |
| Page render (all surfaces) | < 500ms | None | Local data only |
| Entity profile render | < 500ms | None | Local data + cached stats |
| Agent session message | < 3s | None | Excluding LLM latency |
| OpenAlex search | < 5s | 10s | Part of unified search parallel |

### Degradation Model

Each external dependency degrades independently:
- **arXiv unavailable**: Search shows Semantic Scholar results only + warning.
- **Semantic Scholar unavailable**: Search shows arXiv results only + warning.
- **Both unavailable**: Search shows error, local library remains accessible.
- **AI provider unavailable**: Rule-based evidence shown, analysis fields empty.
- **No internet**: Local library, reading, collections, and notes fully
  functional. Search and watch disabled.

## 12. Success Criteria

### Core Workflow
- [ ] `/` renders the Search workspace within 500ms of server start.
- [ ] Search returns results from at least one source within 5 seconds.
- [ ] Clicking a result updates the preview without full page navigation.
- [ ] Preview Save/Skim/Deep Read actions persist to SQLite immediately.
- [ ] Paper Detail shows full abstract (never truncated to summary_short).
- [ ] A paper can be searched, previewed, saved, and opened in detail without
  losing context (return_q preserved).

### Data Integrity
- [ ] Reading decisions persist across server restarts.
- [ ] Collections and their paper memberships survive export/import cycle.
- [ ] Watch subscriptions produce real hits (not fixture data) after a run.
- [ ] Daily pipeline creates a job, transitions to succeeded, and persists papers.

### Agent
- [ ] Agent responds to all 10 intents with appropriate actions.
- [ ] Agent works with no AI provider configured.
- [ ] Agent with no selected paper returns a helpful fallback (not an error).
- [ ] Agent "save" persists the paper to queue_items in SQLite.
- [ ] Agent sessions persist across page navigation and server restarts.
- [ ] Multi-turn conversation maintains context within a session.
- [ ] Agent can execute multi-step action chains (search + create watch in one response).
- [ ] Session auto-title generates meaningful titles from conversation content.

### Entity & Subscriptions
- [ ] Entity profile pages render for all 4 types (journal, conference, scholar, field).
- [ ] Subscribing to an entity creates a subscription linked via entity_id.
- [ ] Search results auto-extract and create venue/author entities.
- [ ] `run_all_subscriptions()` executes entity-linked subscriptions and produces hits.

### Search Enhancement
- [ ] Search returns results from 3 sources (arXiv required, others graceful degradation).
- [ ] Search history dropdown shows recent queries on input focus.
- [ ] Query rewriting displays explanation when active, skips silently when no LLM.
- [ ] Filter chips filter results by year, source, and venue type.

### Background Services
- [ ] `POST /api/refresh` creates a job and transitions to succeeded/failed.
- [ ] `POST /api/subscriptions/run-all` produces hits for active subscriptions.
- [ ] Stale jobs are recovered on server startup (not blocking future runs).

### Security & Privacy
- [ ] API keys are never rendered in full in any HTML response.
- [ ] Cross-origin POST/PUT/DELETE requests are rejected (CSRF guard).
- [ ] Data export produces valid JSON without secrets.
- [ ] App starts and serves `/` with no AI key configured (no crash, no redirect
  to settings).

## 13. Current Implementation Gaps

| Area | Gap | Impact |
| --- | --- | --- |
| Agent | "Summarize" uses stored metadata unless a provider-specific summarizer is added | Weak when abstract is empty |
| Agent | Front-end confirmation has no rich confirm/cancel dialog | Destructive action flow is incomplete |
| Agent | No streaming responses | Full message returned at once |
| Entity | Entity relation graph is not traversable beyond direct connections | Discovery limited to one hop |
| Recommendations | Candidate sets exist, but ranking is still heuristic | Needs quality tuning from user feedback |
| Recommendations | User profile model not yet actively trained | Phase 4 deliverable |
| Reading | Notes and collection management polish incomplete | Basic functionality works, UX rough |
| Settings | Provider health indicators basic | Connection test exists but UX is minimal |
| Planner | Phase 1 only (deterministic search, no adaptive rewrites) | Limited discovery power |
| Evaluation | Dashboard exists but metrics display is limited | Reports generated but visualization basic |

## 14. Release Priorities

1. **Phase 1: UI Foundation + Search Stability** — Design tokens, breathing grid,
   Notion components, sidebar nav, OpenAlex integration, Semantic Scholar fixes,
   CSS restructure.
2. **Phase 2: Entity Subscription System** — Entity data model, profile pages,
   subscription upgrades, Watch restructure, entity auto-extraction.
3. **Phase 3: Agent Session System** — Persistent sessions, multi-turn context,
   multi-step execution, Preact panel, search history, query rewriting.
4. **Phase 4: Recommendation Intelligence** — Multi-strategy engine, multi-dimensional
   scoring, sectioned recommendation page, user profile activation.
