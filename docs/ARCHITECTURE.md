# Architecture

This project is Paper Agent, a local-first paper discovery and research
workspace. The runtime architecture supports search, selected-paper preview,
paper analysis, reading decisions, saved assets, watches, background jobs, and
local Agent actions.

## Product Overview

The application:

- Fetches papers from arXiv, Semantic Scholar, OpenAlex, profile keywords,
  explicit search queries, and watch subscriptions.
- Scores candidates using interpretable heuristic ranking, optional Zotero
  similarity, and feedback signals.
- Persists recommendations, paper metadata, reading state, collections,
  subscriptions, interaction events, and AI analysis cache in SQLite.
- Renders Search, Paper Detail, Reading, Watch, Settings, Evaluation,
  Onboarding, and compatibility queue surfaces through Flask templates.
- Provides optional OpenAI-compatible AI analysis. DeepSeek is a preset for that
  provider shape, and the core product must still work when no AI key is
  configured.
- Manages structured entities (journals, conferences, scholars, fields) with
  browsable profile pages and subscription tracking.
- Maintains persistent Agent conversation sessions with multi-turn context and
  multi-step action execution.
- Generates Markdown, HTML, and cache artifacts as derived outputs rather than
  primary state.

## Directory Structure

- `web_server.py` — thin Flask entrypoint: app initialization, middleware,
  blueprint registration, and server startup.
- `arxiv_recommender_v5.py` — backward-compatible re-export hub for service
  imports.
- `config_manager.py` — user profile adapter for `user_profile.json`, with
  compatibility migration from older local config files.
- `state_store.py` — SQLite adapter for workflow and recommendation state.
- `app/services/` — business logic, external sources, unified search,
  scoring, queue/library operations, monitoring, AI provider integration,
  Agent support, entity management, digest generation, subscription running,
  workspace planning, and evaluation support.
- `frontend/agent/` — Preact-based Agent panel (sessions, message flow, Markdown
  rendering). Built to `static/dist/`.
- `app/routes/` — Flask blueprints for Search/Detail, Reading, Library
  compatibility, Watch, Settings, API (agent, collections, subscriptions,
  feedback, state, evaluation), and Onboarding.
- `app/viewmodels/` — template-ready context builders for page surfaces.
- `templates/` and `static/` — Jinja2 templates, CSS, and JavaScript.
- `evaluation/` — offline evaluation support for ranking metrics and reports.
- `tests/` — unit, integration, productization, and visual regression tests.

## Data Flow

1. **Search intent**
   - Explicit search queries, profile keywords, research questions, and saved
     watches define what the system should discover or monitor.

2. **Candidate discovery**
   - `app/services/unified_search_service.py` searches arXiv, Semantic Scholar,
     and OpenAlex in parallel, normalizes results, and deduplicates by DOI,
     arXiv ID, or normalized title.

2.5. **Entity extraction**
   - After search results return, `app/services/entity_service.py` asynchronously
     extracts venue and author information to create or update entity records.
     Entities accumulate naturally from search activity.

3. **Ranking**
   - `app/services/scoring_service.py` ranks papers using keyword relevance,
     configured weights, feedback penalties or boosts, and optional similarity
     signals.
   - `app/services/ranker.py` combines multiple signals (keyword, author,
     semantic, feedback, subscription match) via geometric mean blending.

4. **Persistence**
   - `state_store.py` stores recommendation runs, paper metadata, queue items,
     collections, subscriptions, hits, interaction events, jobs, research
     questions, and AI analyses in SQLite.

5. **Analysis**
   - `app/services/ai_analysis_service.py` optionally requests structured paper
     analysis and caches the result. Without a provider, the app falls back to
     metadata, abstracts, and rule-based evidence claims.

6. **Rendering**
   - Routes call services and viewmodels, then render templates. Search results
     are saved to metadata so previews and detail pages stay available after
     discovery.

7. **User decisions**
   - Ignore, Skim, Deep Read, Save, collection actions, and subscription routing
     persist as state and become future ranking or monitoring signals.

8. **Workspace planning**
   - Research questions drive bounded planner runs that discover, rank, and
     optionally analyze papers scoped to a specific research intent.

## Runtime Surfaces

- **Search** (`/`): home workspace with result list, selected-paper preview,
  source status, and quick actions.
- **Recommendations** (`/recommendations`): profile and research-context
  candidate-set workspace with why-recommended explanations.
- **Paper Detail** (`/papers/<id>`): structured paper context, analysis,
  evidence, notes, and actions.
- **Reading** (`/reading`): lightweight library for skim, deep-read, saved,
  archived, and collection states.
- **Watch** (`/watch`): research question, author, and venue monitors with
  recent hits and source health.
- **Entity Profiles** (`/entities/<id>`): browsable pages for journals,
  conferences, scholars, and research fields with metadata, related papers,
  and subscribe actions.
- **Settings** (`/settings`): profile, OpenAI-compatible provider, source health,
  backup, restore, and diagnostics.
- **Evaluation** (`/evaluation`): offline ranking reports and quality checks.
- **Onboarding** (`/onboarding`): first-time setup wizard for profile, keywords,
  and initial research question.
- **Agent Panel**: Preact-based side panel with persistent conversation
  sessions, multi-turn context, multi-step execution, Markdown rendering,
  and action chips. Accessed via Notion AI-style floating button from any page.
- **Queue** (`/queue`): compatibility route for internal Inbox state and existing
  tests.

## Agent Subsystem

The Agent is split into a Flask API layer, a session-aware service dispatcher,
and a Preact-based panel.

- `app/routes/api/agent.py` validates requests, manages session lifecycle
  (CRUD), and delegates message handling.
- `app/services/agent_service.py` loads session history (last 20 messages),
  plans intent (keyword fallback -> LLM classification), executes multi-step
  action chains, and persists messages to SQLite.
- `frontend/agent/` renders the panel: session list, message flow with Markdown
  and action chips, typing indicators, and input. Built as a Preact app
  (~50KB gzip) served from `static/dist/`.

Session data model:
- `agent_sessions`: id, title (auto-generated), summary, pin/archive state,
  message count, timestamps.
- `agent_messages`: session_id, role (user/assistant/system/tool), content,
  metadata (tool_results, actions), timestamp.

Clear local tool commands execute deterministically without AI provider.
Ambiguous chat/planning uses the configured OpenAI-compatible provider with
deterministic fallback. Session titles use LLM when available, otherwise
truncate first user message.

## Entity System

Structured entities represent journals, conferences, scholars, and research
fields as first-class objects in the system.

- `app/services/entity_service.py` handles CRUD, metadata fetching from
  OpenAlex/Semantic Scholar, and stats updates.
- `entities` table stores type, name, aliases, external IDs, type-specific
  metadata, and cached statistics.
- `entity_relations` table stores typed links between entities (publishes_in,
  affiliated_with, researches, subfield_of).
- Entity profiles render at `/entities/<id>` with type-specific templates.
- Entities are created on-demand: automatically from search results, or
  manually when users create subscriptions.
- Subscriptions can link to entities via `entity_id` for structured tracking.
- Daily pipeline includes entity sync step for subscribed entities.

## Background Job System

The application uses a lightweight job lifecycle for long-running operations:

- **Job table** in SQLite: `run_id`, `job_type`, `status`, `trigger_source`,
  `payload_json`, `result_json`, `error_text`, timestamps.
- **Lifecycle**: `queued` → `running` → `succeeded` | `failed`.
- **Execution**: Daily pipeline runs in a daemon thread. Subscription runs and
  evaluation runs are synchronous (blocking the request).
- **Recovery**: On server startup, jobs stuck in `running` for >120 minutes are
  marked `failed` (stale recovery). This prevents one failed run from blocking
  all future runs.
- **API**: `GET /api/job/status` returns the latest job state for UI polling.

## State Management

- **SQLite** (`cache/app_state.db` by default): primary durable workflow state.
- **Profile JSON** (`user_profile.json`): local user preferences and keywords.
- **Derived artifacts** (`cache/`, `history/`, `reports/`): regenerated outputs,
  exports, or diagnostics. They are not primary state.

SQLite is the source of truth for product workflow state. Markdown digests,
HTML files, and search caches should not become competing state sources.

## Design System

The UI uses a three-layer design token architecture:

- **Primitive tokens**: raw color values (~30), defined once.
- **Semantic tokens**: purpose-mapped values (~20), with light/dark variants
  switched via `[data-theme="dark"]`.
- **Component tokens**: reference semantic tokens for specific UI components.

Visual language follows Notion-style design: generous whitespace, clean
hierarchy, micro-interactions. Color palette draws from Claude (warm orange
accent) and Apple (system blues, neutral grays). Background uses an animated
breathing grid (CSS opacity cycling, static on `prefers-reduced-motion`).

Navigation is a left sidebar (Notion-style collapsible), replacing the
previous top pill navigation. Mobile collapses to hamburger menu.

The Agent panel is a standalone Preact application; all other pages use
Flask/Jinja2 server rendering with shared CSS design tokens.

## Key Design Decisions

### Local First

User data stays on disk. The product should not require accounts, cloud sync, or
hosted state to complete its core workflow.

### Explainable Ranking

Ranking remains interpretable. Keyword, topic, feedback, and subscription
signals should be visible enough for the user to understand why a paper was
surfaced.

### Optional AI

AI analysis is an enhancement, not a hard dependency. The product should remain
usable with no provider configured, and secrets must never be rendered in full
or exported unintentionally.

### Thin Routes, Testable Services

Routes should validate request input, call services, build viewmodels, and
render responses. Business behavior belongs in services and state adapters where
it can be tested without a browser.

### Agent as Session-Aware Tool Dispatcher

The Agent persists conversation sessions but does not own durable domain state.
It is a session-aware tool dispatcher over Search, Reading, Watch, Collections,
Entities, Recommendations, and Paper Detail services. Session history enables
multi-turn context; SQLite remains the source of truth for product state.
