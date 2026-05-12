# Paper Agent Improvement Roadmap — May 2026

This roadmap supersedes `2026-05-01-optimization.md` and carries forward
remaining items from `2026-05-01-audit-fixes.md`.

---

## P0: Merge-Blocking

Items that must be resolved before the `codex/apple-claude-workspace-redesign`
branch merges to main.

### 1. Agent intent classifier ambiguity

**Deliverable**: Add priority ordering or longest-match logic to
`_message_intent()` so overlapping keywords do not silently misclassify.

**Files**: `app/routes/api/agent.py`

**Acceptance**: "save my analysis" triggers `analysis` (not `save`); "look for
papers later" triggers `search` (not `skim`). Unit tests cover all ambiguous
cases.

### 2. Watch fixture/test data leak prevention

**Deliverable**: Final audit of Watch page to ensure no fixture, test, or stale
local data can appear in the production runtime Watch surface.

**Files**: `app/viewmodels/monitor_viewmodel.py`, `app/routes/watch.py`,
`templates/watch.html`

**Acceptance**: Fresh database + real subscription run produces only real hits.
No hardcoded sample data in template or viewmodel.

### 3. Remove residual Chinese strings from API responses

**Deliverable**: Audit all API response strings and template copy for Chinese
text. Replace with English equivalents.

**Files**: `app/services/daily_pipeline.py`, `app/routes/api/`, `templates/`

**Acceptance**: `grep -rn "[\x{4e00}-\x{9fff}]" app/ templates/ static/`
returns no hits (excluding comments referencing Chinese user profile data).

### 4. Security hardening spec completion

**Deliverable**: Verify that all 5 items from `docs/superpowers/specs/
2026-04-27-security-hardening-design.md` are implemented: XSS escaping, CSRF
origin check, concurrent pipeline guard, force-refresh cache bypass, defusedxml.

**Files**: `web_server.py`, `app/services/daily_pipeline.py`, requirements

**Acceptance**: Each item has a corresponding test or code path. Bandit scan
clean.

### 5. PRD/Architecture doc sync

**Deliverable**: PRD.md and ARCHITECTURE.md accurately reflect current system.
(This work — completed as part of this roadmap creation.)

**Files**: `docs/PRD.md`, `docs/ARCHITECTURE.md`

**Acceptance**: Every route in `web_server.py` has a corresponding surface in
PRD. Every service in `app/services/` is referenced in Architecture.

---

## P1: Quality & Reliability (post-merge, next sprint)

### 1. Agent V2: LLM-backed intent classification

**Deliverable**: When an AI provider is configured, use it for intent
classification with confidence scoring. Fall back to keyword matching when no
provider or when confidence is below threshold.

**Files**: `app/routes/api/agent.py`, `app/services/ai_providers.py`

**Acceptance**: With provider: ambiguous message "save my analysis for later"
correctly routes to the most contextually appropriate intent. Without provider:
identical behavior to current keyword matcher.

### 2. Real AI summarization for "summarize" intent

**Deliverable**: Agent "summarize" calls AI provider for a structured summary
instead of truncating the abstract. Falls back to abstract excerpt without
provider.

**Files**: `app/routes/api/agent.py`, `app/services/ai_analysis_service.py`

**Acceptance**: With provider: "summarize this paper" returns a 2-3 sentence
AI-generated summary. Without provider: returns first 420 chars of abstract
(current behavior).

### 3. Subscription runner auto-scheduling

**Deliverable**: Configurable interval for automatic subscription runs (e.g.,
every 6 hours) without requiring manual API call.

**Files**: `app/services/subscription_runner.py`, `web_server.py`

**Acceptance**: Server startup launches a background scheduler. Subscriptions
run at configured interval. Manual trigger still works.

### 4. Settings provider connection test improvements

**Deliverable**: Connection test button shows clear success/failure with
response time, model name echo, and actionable error messages.

**Files**: `app/routes/api/keywords.py`, `templates/settings_research.html`,
`static/js/preferences.js`

**Acceptance**: Test button shows "Connected: deepseek-chat (340ms)" on success
or "Failed: 401 Unauthorized — check your API key" on failure.

### 5. Reading notes and collection management polish

**Deliverable**: Notes can be created, edited, and deleted from Reading page.
Collection membership can be managed (add/remove papers) without navigating to
detail.

**Files**: `templates/reading.html`, `app/routes/api/collections.py`,
`static/js/collections.js`

**Acceptance**: Create note on paper from Reading tab. Edit note inline. Remove
paper from collection via Reading collections tab.

### 6. Front-end confirmation dialog for Agent destructive actions

**Deliverable**: When Agent returns `requires_confirmation: true`, show a
confirm/cancel dialog. On confirm, re-send with `confirmed: true` flag.

**Files**: `frontend/agent/`, `static/dist/agent-drawer.js`, `app/routes/api/agent.py`

**Acceptance**: "delete all papers" shows confirmation dialog. Cancel does
nothing. Confirm sends second request that executes the action.

---

## P2: Enhancement (next quarter)

### 1. Agent multi-turn capability

**Deliverable**: Agent maintains conversation history within a session. Can
reference prior messages ("save that one too", "the second paper").

**Files**: `app/routes/api/agent.py`, `frontend/agent/`

**Dependencies**: P1.1 (LLM intent classification needed for context resolution)

### 2. Agent streaming responses

**Deliverable**: Long Agent responses (AI summary, analysis) stream tokens to
the drawer UI as they arrive.

**Files**: `app/routes/api/agent.py`, `frontend/agent/`

**Dependencies**: P1.2 (real AI summarization)

### 3. Workspace planner phase 2 (adaptive query rewrites)

**Deliverable**: Planner uses AI to generate alternative query formulations,
expanding discovery beyond the literal user query.

**Files**: `app/services/workspace_planner.py`

**Dependencies**: AI provider configured, P1.1 baseline

### 4. Evaluation dashboard richer metrics

**Deliverable**: Display precision@k, recall@k, nDCG charts. Compare evaluation
runs side-by-side.

**Files**: `templates/eval_dashboard.html`, `app/viewmodels/eval_viewmodel.py`

### 5. Collection BibTeX export from Reading page

**Deliverable**: Export button on Reading collections tab generates BibTeX for
all papers in collection.

**Files**: `templates/reading.html`, `app/routes/api/collections.py`

### 6. Mobile responsive polish

**Deliverable**: All surfaces pass mobile viewport QA. Preview collapses, nav
adapts, no horizontal overflow.

**Files**: `static/research_ui.css`, `templates/`

### 7. Skeleton loading states

**Deliverable**: Search results and detail page show skeleton placeholders
during loading instead of blank space.

**Files**: `static/research_ui.css`, `static/js/inbox.js`

### 8. Dark mode CSS

**Deliverable**: CSS variables support dark mode. Toggle in Settings or system
preference detection.

**Files**: `static/research_ui.css`, `templates/settings_research.html`

### 9. Optimistic UI updates

**Deliverable**: Save/Skim/Deep Read actions update UI immediately, then confirm
with server. Rollback on failure.

**Files**: `static/js/paper_actions.js`, `frontend/agent/`

### 10. Command palette enhancement

**Deliverable**: Cmd+K palette supports all Agent actions + page navigation +
recent searches.

**Files**: `static/js/command_palette.js`

---

## P3: Future Consideration

These are not planned but may be explored based on user feedback.

1. **Citation graph exploration** — visualize paper citation networks.
2. **Journal trends analysis** — track keyword/author trends over time (spec
   exists at `docs/superpowers/specs/2026-04-08-journal-trends-analysis-design.md`).
3. **Full PDF inline reading** — render PDFs in-app with annotation support.
4. **Multi-user / team features** — shared collections, team libraries.
5. **Plugin system** — extensible connectors for additional paper sources.

---

## Carried Forward from Previous Plans

From `2026-05-01-audit-fixes.md` (remaining items):
- Replace pickle with JSON in daily_pipeline → captured in P0.3 audit
- Harden import_state validation → captured in P1 quality work
- Consolidate digest parsing → completed (utils.py version is canonical)

From `2026-05-01-optimization.md` (remaining items):
- Skeleton loading → P2.7
- Dark mode → P2.8
- Optimistic UI → P2.9
- Command palette → P2.10
- Collection BibTeX export → P2.5
- Mobile responsive → P2.6
- SQLite connection reuse → evaluated; current `check_same_thread=False`
  approach is sufficient for waitress thread pool
