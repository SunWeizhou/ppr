# Paper Agent UI / Functional Consolidation Plan

> **Target repository:** `https://github.com/SunWeizhou/ppr.git`  
> **Target branch:** `codex/apple-claude-workspace-redesign`  
> **Task type:** Product consolidation + frontend/backend bug fixing + design-system cleanup  
> **Product direction:** Apple / Claude-like minimal, calm, precise, warm, premium research workspace  
> **Primary user request:**  
> 1. Restore and improve the lower-right Agent launcher  
> 2. Switch display typography toward **Anthropic Serif**  
> 3. Add a branded **alpaca sketch mascot** Agent launcher, ideally based on a licensed open-source asset  
> 4. Fix card/module visual misalignment  
> 5. Fix buttons that appear interactive but do not perform real actions  
> 6. Reorganize the crowded subscription experience  
> 7. Audit and fix remaining small bugs  
> 8. Simplify the Paper Detail page, show full abstracts, reduce right-rail actions, and clarify/remove confusing “Matches” and “History”

---

## 0. Executive Summary

Paper Agent already has a promising product skeleton:

- Home workspace for initiating research questions
- Search workspace with preview and triage
- Recommendations
- Reading queue
- Watch / subscriptions
- Paper detail page with AI analysis and evidence
- Settings / diagnostics
- A Preact-based Agent drawer

However, the current branch still feels closer to a **feature-complete prototype** than a **coherent product**. The main issues are:

1. **Agent launcher is not visible** because frontend build filenames and template asset references are inconsistent, and static build artifacts are not reliably available.
2. **Typography is not actually unified**. `tokens.css` and `research_ui.css` define/override font families in conflicting ways. Changing one token alone will not reliably affect the interface.
3. **The Agent launcher lacks brand personality**. A small alpaca mascot could become a distinctive product identity.
4. **The component system is fragmented**. `.card`, `.btn`, `.chip`, and typography are defined in multiple CSS layers, causing inconsistent spacing, alignment, and visual hierarchy.
5. **Several buttons are misleading or non-functional**:
   - Search preview `Cited By` / `Refs` buttons are inert.
   - Venue subscription `New` button only shows “coming soon”.
   - Subscription `Edit` routes to a settings tab that does not exist.
   - Some page actions only show a toast without making state changes visually clear.
6. **Watch / subscription information architecture is overloaded**. Research questions, authors, venues, and fields are all stacked on one long page, while their backing implementations are not fully unified.
7. **Paper Detail is too busy** and does not match the premium minimal product direction:
   - Abstracts may be incomplete when only summarized fallback metadata is available.
   - The right rail contains too many equal-weight actions.
   - `Skim Later` and `Deep Read` are too fine-grained for the detail-page primary action layer.
   - `Matches` and `History` are unclear to users.

This plan is deliberately **not** a feature-expansion sprint. It is a **stabilization and product coherence pass**.

---

# 1. Product Principles for This Pass

The implementation agent should use the following principles when making decisions.

## 1.1 Calm over crowded
A page should expose only the actions that fit the user’s immediate intent. Less important actions should be moved into:

- Secondary rows
- Overflow menus
- Collapsed details
- Context-specific pages

## 1.2 Real actions only
Do not display a button that looks actionable unless it truly performs a meaningful action. If a feature is not implemented:

- Hide it, or
- Disable it with honest copy, or
- Implement it fully

Avoid “button → toast saying coming soon” on production-feeling pages.

## 1.3 Design system over local patches
Avoid solving visual problems by adding one-off inline styles. Prefer:

- Tokens
- Shared component classes
- Page-level layout classes

## 1.4 Brandable but restrained
The alpaca Agent mascot should feel:

- Minimal
- Friendly
- Quiet
- Distinctive
- Not childish or cartoon-heavy

Think “Notion small face icon” more than “illustrated mascot”.

## 1.5 Full metadata where detail matters
The Paper Detail page should prefer authoritative/full paper metadata over stale summaries or abbreviated cached snippets.

---

# 2. Scope and Non-Scope

## 2.1 In scope
- Agent launcher visibility and mascot redesign
- Agent frontend asset pipeline cleanup
- Typography refactor toward Anthropic Serif
- Card/button/chip visual alignment cleanup
- Fixing misleading/inert buttons
- Watch/subscription information architecture and interaction refactor
- Paper Detail simplification and abstract completeness
- Small bug audit across the branch
- Tests / build verification

## 2.2 Out of scope
- Rewriting the entire app in React/Next.js
- Replacing Flask/Jinja architecture
- Rebuilding recommendation algorithms from scratch
- Creating a full design system package outside the repo
- Adding a large suite of new research features unrelated to the reported issues

---

# 3. Required Initial Audit by the Implementation Agent

Before coding, inspect at least:

## 3.1 Frontend shell / Agent
- `templates/base_research.html`
- `frontend/agent-panel/index.tsx`
- `frontend/agent-panel/styles/agent-panel.css`
- `vite.config.ts`
- `.gitignore`
- `package.json`

## 3.2 Typography and components
- `static/css/tokens.css`
- `static/css/typography.css`
- `static/css/components.css`
- `static/css/pages.css`
- `static/research_ui.css`

## 3.3 Search and detail pages
- `templates/search_research.html`
- `templates/paper_detail.html`
- `app/viewmodels/paper_viewmodel.py`
- metadata normalization / persistence paths for search results and paper metadata

## 3.4 Watch / subscriptions
- `templates/watch.html`
- `static/js/subscriptions.js`
- subscriptions-related API routes and state-store methods
- entity/subscription integration if already present

## 3.5 Agent / feedback / event state
- `app/routes/api/agent.py`
- `app/services/agent_service.py`
- `static/js/paper_actions.js`
- `app/routes/api/feedback.py`
- `app/services/feedback_service.py`

---

# 4. Priority P0 — Restore the Lower-Right Agent Launcher

## 4.1 Problem

The lower-right Agent floating icon does not appear in the UI.

### Observed likely root cause
`base_research.html` references:

- `/static/dist/agent-panel.css`
- `/static/dist/agent-panel.js`

But `vite.config.ts` builds:

- `agent-drawer.css`
- `agent-drawer.js`

This mismatch prevents the bundle from loading. In addition, static output files are not present in the repository snapshot and the `.gitignore` includes a broad `dist/` pattern, which can interfere with generated assets under `static/dist/`.

## 4.2 Required fix
Choose one canonical naming strategy and apply it consistently.

### Preferred option
Use **agent-panel** naming everywhere:

- Vite output:
  - `agent-panel.js`
  - `agent-panel.css`
- Template references:
  - `/static/dist/agent-panel.js`
  - `/static/dist/agent-panel.css`

This preserves current semantic naming in the template.

## 4.3 Asset deployment strategy
The agent must decide and document one of these strategies:

### Strategy A — Generated assets are committed
- `static/dist/agent-panel.js`
- `static/dist/agent-panel.css`

Then adjust `.gitignore` so `static/dist/` is not accidentally ignored.

### Strategy B — Generated assets are built as part of installation / runtime
Keep generated assets untracked, but guarantee that:
- README startup instructions build the assets
- Tests or startup diagnostics can warn clearly if assets are absent
- Local dev flow is obvious

### Recommendation
For this repo’s current local-first packaging and branch-level development workflow, **Strategy B is acceptable**, but the UI should fail clearly in development rather than silently hiding the Agent.

## 4.4 Add a small runtime diagnostic in development if reasonable
Optional but recommended:
- If the root `#paper-agent-root` exists but the bundle does not load, surface a console error or small non-production diagnostic.
- Do not show an ugly visible production error unless desired.

## 4.5 Acceptance criteria
- `npm ci && npm run build` succeeds.
- The browser loads the Agent CSS and JS without 404.
- The lower-right floating launcher appears on pages extending `base_research.html`.
- Clicking it opens the Agent panel.
- Closing the panel restores the launcher.
- Mobile behavior remains sensible.

---

# 5. Priority P0/P1 — Replace the Agent Launcher Icon with a Branded Alpaca Sketch

## 5.1 Product goal
The lower-right Agent launcher should feel like a branded assistant entry point, not a generic document icon.

### Desired direction
A **minimal alpaca / llama line-art face**:
- Simple monochrome outline
- Recognizable at 20–24 px
- Friendly but restrained
- Suitable inside a 48–56 px circular button
- Visually compatible with a warm Claude-like UI

## 5.2 Asset sourcing requirement
The implementation agent should search for a suitable open-source SVG asset, preferably on GitHub, using terms such as:

- `alpaca svg icon`
- `llama svg icon`
- `minimal alpaca icon`
- `alpaca line icon`
- `llama outline svg`

## 5.3 Licensing rule
Only use assets with clear licensing appropriate for inclusion in an MIT project, such as:
- MIT
- Apache-2.0
- CC0
- Other clearly permissive licenses after verification

Do **not** use random unlicensed SVGs.

## 5.4 If no suitable asset exists
Create a compact custom SVG manually only if necessary:
- Avoid large illustration complexity
- Prefer fewer paths
- Keep optical balance at 20–24 px
- Store SVG source in the repo in a maintainable way

## 5.5 UI design requirement
Launcher should likely become:

- Circular or softly rounded floating button
- Warm paper / raised background rather than loud saturated fill
- Hairline border
- Subtle shadow
- Alpaca icon in dark ink
- Hover lift + gentle scale
- Optional accent dot for “active / attention / ready”

## 5.6 Component implementation recommendation
Refactor the launcher icon into a dedicated component:

- `frontend/agent-panel/components/AgentLauncherIcon.tsx`
or
- `frontend/agent-panel/components/AlpacaMark.tsx`

Then use it in the launcher button.

## 5.7 Acceptance criteria
- The launcher has a distinctive alpaca sketch icon.
- It remains crisp at small sizes.
- It works in light and dark themes.
- Hover/focus states are visible and tasteful.
- The asset’s license is documented in code comments or docs if third-party.

---

# 6. Priority P1 — Switch Typography Toward Anthropic Serif and Unify the Font System

## 6.1 Problem

The user wants the interface modified to **Anthropic Serif**.

However, the current font system is inconsistent:

- `tokens.css` uses `Source Serif 4` as display serif.
- `research_ui.css` defines another token layer and maps `--ff-serif` to a sans family, which can override intended serif usage.
- Fonts are not consistently applied across page titles, panel titles, list titles, and branding.
- No font files or `@font-face` declarations are currently present for Anthropic Serif.

## 6.2 Legal / technical requirement
Before embedding **Anthropic Serif**, verify:
1. Whether there is an official or licensed webfont distribution.
2. Whether self-hosting is allowed.
3. Whether inclusion in this project is legally acceptable.

### If legal font files are available
- Add them under a proper assets directory, e.g.:
  - `static/fonts/anthropic-serif/...`
- Add `@font-face` declarations.
- Use `font-display: swap`.

### If legal font files are not available
- Implement the token-level design so the app prefers:
  - `"Anthropic Serif"`
  - then fallback serif fonts
- Document that the exact font requires a locally provided licensed file.
- Do not ship pirated or unclear font files.

## 6.3 Token target

Recommended canonical tokens:

```css
--ff-display: "Anthropic Serif", "Source Serif 4", "Iowan Old Style", Georgia, "Songti SC", serif;
--ff-body: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", system-ui, sans-serif;
--ff-mono: "SF Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
```

## 6.4 Required fix in `research_ui.css`
Replace mappings like:

```css
--ff-serif: var(--font-sans);
```

with:

```css
--ff-serif: var(--ff-display);
```

or remove duplicated aliases after consolidating design tokens.

## 6.5 Typography rules
### Use display serif sparingly
Use Anthropic Serif for:
- Home hero titles
- Page titles
- Paper detail title
- Section titles where editorial feel is desired

### Use sans for interface utility
Use sans-serif for:
- Nav
- Buttons
- Metadata
- Tables
- Agent drawer UI
- Form labels
- Badges
- Dense cards

## 6.6 Avoid overuse
If every card title becomes a serif headline, the app may feel like an editorial magazine rather than a premium productivity tool. Maintain restraint.

## 6.7 Acceptance criteria
- Page-level titles consistently use the display font.
- Functional UI remains sans.
- No CSS file re-maps serif back to sans unexpectedly.
- Light/dark modes remain legible.
- The typography system is documented in comments or a short docs section.

---

# 7. Priority P1 — Consolidate the Component System and Fix Card Alignment

## 7.1 Problem

Many cards and modules visually do not align. Root cause is architectural:

- `.card`, `.btn`, `.chip`, and related primitives are defined in multiple CSS files.
- `research_ui.css` overrides definitions from `components.css`.
- Some templates still contain inline style patches.
- Border radius, padding, min-height, and margin conventions vary by page.

## 7.2 Goal
Make the UI feel like one design system rather than a stitched-together collection of iteration layers.

## 7.3 Required CSS architecture
Target structure:

### `tokens.css`
Only design tokens:
- colors
- radii
- spacing
- typography
- shadows
- motion timing if desired

### `typography.css`
Global textual conventions:
- page title
- panel title
- body copy
- meta copy
- prose / abstract text
- links

### `components.css`
Reusable components:
- buttons
- cards
- chips
- tags
- list rows
- empty states
- toast
- modal base components

### `layout.css`
Sidebar, main layout, split panes, responsive shells.

### `pages.css`
Only page-specific layout and exceptions.

### `research_ui.css`
Either:
- Remove over time, or
- Convert into a backward-compatibility layer with aliases only

Do not keep it as a second competing source of truth.

## 7.4 Card normalization
Define a canonical card standard:
- background
- border
- radius
- padding
- gap between sibling cards
- header spacing
- subhead spacing

Suggested baseline:
- `.card`: standard container
- `.card--compact`
- `.card--flush`
- `.card--subtle`

Avoid one-off card paddings in templates.

## 7.5 Button normalization
Define only a small, meaningful vocabulary:
- `.btn-primary`
- `.btn-secondary`
- `.btn-ghost`
- `.btn-danger`

Optional:
- `.btn-sm`
- `.btn-xs`

Avoid too many semantic color button classes unless they carry strong meaning.

## 7.6 Page-level visual QA targets
Audit and visually align at least:
- Home
- Search
- Recommendations
- Reading
- Watch
- Paper Detail
- Settings

For each:
- left edges align
- card widths align
- sections use a consistent rhythm
- action rows align
- right rails maintain consistent spacing
- headings have coherent vertical rhythm

## 7.7 Acceptance criteria
- Same-level cards have visibly consistent padding and radii.
- Button heights and chip heights are consistent.
- Search and Paper Detail no longer look like they use a different component library from Watch.
- Inline style usage is reduced in touched templates.
- The UI feels calmer and more intentional.

---

# 8. Priority P1 — Remove or Implement Misleading / Inert Buttons

## 8.1 Search Preview: `Cited By` / `Refs`
### Current issue
They are rendered as `<button>` elements but do not have any behavior.

### Preferred action
Either:
1. Implement them fully, or
2. Render as static metadata chips / labels, or
3. Hide them until a real interaction exists.

### Recommendation
For this pass, **do not overbuild citation exploration**. Convert to passive metadata or hide them.

## 8.2 Venue Subscription: `New`
### Current issue
The button exists, but JS only shows a toast saying “Venue watches are coming soon”.

### Required action
Choose one:
- Implement venue subscription creation fully, or
- Disable/remove the button and clearly mark venue watch creation as unavailable

### Recommendation
Implement it if the underlying API and subscription model already support venue type. If not, reduce UI honesty problems first.

## 8.3 Subscription `Edit`
### Current issue
`editSubscription(subId)` navigates to:
```js
/settings?tab=subscriptions&edit=...
```
but the settings page does not expose a subscriptions tab.

### Required action
Choose one:
- Open a proper edit modal on Watch page, or
- Create the missing subscription management route/page

### Recommendation
For a cleaner product, use **per-type edit modals** or a dedicated Watch edit path, not a hidden settings tab.

## 8.4 Search page “workspace question / planner” stubs
Look for toast-only functions such as:
- `createWorkspaceQuestion()`
- `runWorkspacePlanner()`

If these are connected to visible UI:
- Implement properly, or
- Remove/hide the trigger

## 8.5 Relevant / Ignore user feedback
Current feedback may execute server-side, but visual confirmation is weak.

### Required improvement
After clicking:
- Relevant
- Ignore

Update visible state:
- Toggle selected style
- Change label to `Relevant ✓` or `Ignored`
- Or show a state chip / inline status

Do not rely solely on a toast for important state actions.

## 8.6 Acceptance criteria
- No visible button is fake.
- All visible actions either:
  - perform their stated function, or
  - are honestly disabled/hidden.
- Users can perceive state changes after important actions.

---

# 9. Priority P1/P2 — Reorganize Watch / Subscribe Experience

## 9.1 Problem

The current Watch page places:
- Research questions
- Authors
- Venues
- Fields

on one long page.

This is visually noisy and cognitively heavy. It also exposes the fact that not all subscription types are equally mature in implementation.

## 9.2 Product target
Convert Watch into a cleaner subscription management experience.

### Recommended information architecture

#### `/watch`
Overview dashboard:
- Active watches count
- Recent hits summary
- Latest refresh status
- Source health
- Quick create entry points

#### `/watch/questions`
Research question watches

#### `/watch/authors`
Author watches

#### `/watch/venues`
Venue watches

#### `/watch/fields`
Field watches

If routing refactor is too large for one pass, use a tabbed layout as an intermediate step:
- Questions
- Authors
- Venues
- Fields

But avoid a long vertical stack of all four simultaneously.

## 9.3 Data model cleanup
The Watch domain should converge toward:

```txt
subscriptions(type = query | author | venue | field | entity)
```

Avoid maintaining disconnected systems:
- query → saved searches
- author → scholars JSON/service
- field → subscriptions
- venue → half-supported path

### Required design question
Decide whether “saved searches” remain a distinct product concept or become a façade over query subscriptions.

## 9.4 Recommended implementation path
### Step 1 — UX split
Restructure page into separate tabs/routes while preserving current data retrieval.

### Step 2 — Action correctness
Make create/edit/run/disable/delete actions real and type-appropriate.

### Step 3 — Gradual data unification
Refactor author/query flows toward the unified subscriptions backend where practical.

## 9.5 Watch card simplification
Each Watch card should clearly show:
- Name
- Type
- Query/entity target
- Last checked
- Health
- New hits count
- Primary actions:
  - Refresh
  - Edit
  - View hits / Open profile
- Secondary actions:
  - Disable
  - Delete

Do not overload hit cards with too many one-off CTA buttons.

## 9.6 Acceptance criteria
- Users can understand and manage one watch type at a time.
- Watch page no longer feels like four full apps stacked into one.
- New / Edit actions are valid.
- The code is moving toward a unified subscriptions model.

---

# 10. Priority P1 — Paper Detail Page Simplification

## 10.1 Main issues
- Abstract may be incomplete or degraded because fallback metadata can be a summary instead of a full abstract.
- The action rail has too many visible buttons.
- `Skim Later` vs `Deep Read` is too fine-grained as a primary detail-page choice.
- `Matches` and `History` are unclear.
- The page risks feeling like a dashboard instead of an elegant article detail view.

---

## 10.2 Abstract completeness

### Current likely behavior
The template renders:
```jinja
paper.abstract or paper.summary
```

If `abstract` is missing, it falls back to `summary`, which may be abbreviated.

### Required improvement
Implement **metadata enrichment / recovery** on detail pages.

#### Suggested rule
If:
- `abstract` is missing, or
- `abstract` appears suspiciously short, or
- the source came from recommendation/history/cache fallback

then:
1. Try to retrieve fuller metadata using available source identifiers.
2. Persist the recovered full abstract into `paper_metadata`.
3. Render the enriched version.

### Avoid
Do not block the page for too long; if enrichment is async or partial, degrade gracefully.

## 10.3 Detail-page action redesign

### Current issue
Actions are still too numerous and too equal in weight.

### Recommended action hierarchy

#### Primary
- `Save`
- `Add to Reading`

#### Secondary
- `Relevant`
- `Ignore`
- `Add to Collection`
- `Follow Author`

#### Analysis
- `Generate AI Analysis` / `Regenerate AI Analysis`

#### External
- `Open arXiv`
- `PDF`
- `BibTeX`

## 10.4 Reading decision simplification
The user explicitly feels:
- `Skim Later`
- `Deep Read`

are unnecessarily granular on detail page.

### Recommended change
Do not expose both as equal primary buttons on Paper Detail.

#### Preferred behavior
- Primary detail-page action:
  - `Add to Reading`
- Then reading prioritization occurs later in the Reading workspace.

#### Backend compatibility
If backend statuses must remain:
- Map `Add to Reading` to a neutral queue status such as `Inbox` or a chosen standard status.
- Keep advanced statuses available elsewhere if still useful.

The agent should make a product decision and apply it consistently.

## 10.5 Rename or demote `Matches`
### Current meaning
Likely: subscription/query matches that explain why a paper surfaced.

### Better UX name
- `Matched Watches`
or
- `Why this appeared`

Only show when meaningful.

## 10.6 Rename or demote `History`
### Current meaning
User interaction history / state-change timeline.

### Better UX name
- `Activity`

Recommended UI:
- Collapsed by default
- Smaller visual emphasis
- Only shown when events exist

## 10.7 Suggested content hierarchy for detail page
Left main column:
1. Back nav
2. Paper title
3. Authors / venue / year / external links
4. Full abstract
5. AI analysis
6. Evidence-linked claims
7. Related papers

Right rail:
1. Compact key actions
2. Current state / reading status
3. Why this appeared / matched watches (if applicable)
4. Activity (collapsed, if applicable)

## 10.8 Acceptance criteria
- Full abstract is displayed when source data supports it.
- Detail page has fewer and clearer primary actions.
- `Matches` and `History` no longer feel mysterious.
- The right rail visually feels curated rather than overcrowded.
- Detail page better matches Apple / Claude-style editorial calm.

---

# 11. Priority P2 — Additional Bug Audit and Small Fixes

The agent should explicitly audit for and fix the following known issues.

## 11.1 Paper Detail back-link bug
There is a path where detail returns to:
```txt
/?research_question_id=...
```
even though Search now lives at:
```txt
/search?research_question_id=...
```

Fix route semantics.

## 11.2 Agent fallback location wording
If fallback chat logic still treats `/` as “Search”, update it to reflect:
- `/` = Home
- `/search` = Search

## 11.3 Watch hit button-state bug
Some row-update logic checks button text like:
```txt
Inbox
```
but the rendered button text is:
```txt
Send to Reading
```
This may prevent expected disable/update behavior.

Fix by selecting via data attributes instead of fragile button text if possible.

## 11.4 Agent panel resize / content margin mismatch
Panel width can resize, but the main content’s right margin may continue to assume a fixed width.

Fix by:
- synchronizing a CSS variable such as `--agent-panel-width`
- or adopting a layout approach that reads the actual panel width

## 11.5 Legacy comments/docs
If comments or docs say:
- endpoint creates a transient Agent session
but it actually persists, update the docs or implementation.

## 11.6 Search filter and preview regression scan
Validate:
- Search result selection
- Preview pane updates
- Save/Add to Reading still work
- Clear preview works
- Responsive behavior is intact

## 11.7 Console error audit
Open key pages and eliminate obvious:
- JS console errors
- 404 static assets
- undefined function calls
- missing element selectors

---

# 12. Testing and Validation Requirements

## 12.1 Required command checks

Run:

```bash
python -m py_compile state_store.py
python -m pytest tests/ -q
npm ci
npm run build
npm run lint
```

If the repo does not currently have a working lint target, report that clearly.

## 12.2 Recommended manual QA matrix

### Home
- Typography
- Search entry
- Navigation
- Agent launcher present

### Search
- Search submission
- Preview update
- Save/Add to Reading
- Real vs hidden actions
- No inert buttons

### Recommendations
- Cards align
- Detail route works
- Agent launcher present

### Reading
- Saved / reading transitions work
- Card structure aligns visually

### Watch
- Route/tab redesign works
- New/Edit/Delete/Refresh are truthful
- One watch type at a time is navigable

### Paper Detail
- Full abstract
- Simplified action rail
- AI analysis button
- “Why this appeared” / “Activity” clarity
- Back navigation

### Settings
- Font changes do not damage forms
- Diagnostics still readable

### Agent
- Launcher icon visible
- Alpaca icon crisp
- Drawer opens/closes
- Session UI still works
- Panel resize does not break layout

---

# 13. Suggested Implementation Order

The implementation agent should follow this order unless a dependency requires otherwise.

## Phase 1 — Restore Agent infrastructure
1. Fix Vite/template asset filename mismatch
2. Confirm build output strategy
3. Make launcher visible again
4. Fix resize-width layout sync

## Phase 2 — Typography and design-system cleanup
5. Introduce Anthropic Serif token path with licensing-safe handling
6. Consolidate serif/sans token mapping
7. Start reducing CSS conflicts
8. Normalize core card/button/chip primitives

## Phase 3 — Alpaca Agent mascot
9. Find licensed open-source alpaca/llama SVG or create minimal fallback
10. Replace current launcher icon
11. Tune launcher visual style

## Phase 4 — Real actions only
12. Remove/implement inert Search preview actions
13. Fix Venue `New`
14. Fix Subscription `Edit`
15. Improve visible state changes for feedback buttons

## Phase 5 — Watch IA
16. Split Watch by route or tabs
17. Reduce vertical overload
18. Clarify subscription type architecture
19. Clean up actions in watch cards and hits

## Phase 6 — Paper Detail refinement
20. Add abstract enrichment/fallback recovery
21. Simplify right rail actions
22. Collapse or rename Matches / History
23. Fix detail back-link route

## Phase 7 — Bug sweep and validation
24. Fix listed small bugs
25. Run test/build commands
26. Perform manual QA matrix
27. Produce summary report

---

# 14. Definition of Done

This task is complete only when:

1. The lower-right Agent launcher reliably appears and opens the drawer.
2. The launcher uses a polished alpaca mascot treatment or an explicitly documented, licensed interim asset.
3. Typography is consistently routed through a clean token system that supports Anthropic Serif.
4. The UI’s cards/buttons/chips no longer visibly look like they come from competing style systems.
5. No visible production-feeling button is a fake interaction.
6. Watch / subscriptions are meaningfully cleaner and less crowded.
7. Paper Detail is calmer, clearer, and shows the best available abstract.
8. `Matches` and `History` are renamed, demoted, redesigned, or removed in a way that makes sense.
9. Known small bugs from this plan are fixed.
10. Build/test commands have been run and the result is reported.

---

# 15. Final Report Required from the Implementation Agent

After completing the work, the agent must provide:

## 15.1 Summary of changes
A short executive summary.

## 15.2 Files changed
Grouped by:
- Agent
- CSS/design system
- Watch/subscriptions
- Paper Detail
- Tests/docs

## 15.3 Issues fixed
Map each major issue from this plan to the implementation.

## 15.4 Trade-offs / deferred work
If something was intentionally not fully implemented, say why.

## 15.5 Validation
Report exact commands run and results.

## 15.6 Screens / UI notes
If possible, mention the visual changes page by page.

---

# 16. Suggested Commit Message

```txt
feat: consolidate Paper Agent UI, restore agent launcher, and refine watch/detail flows
```

or split into multiple commits if the agent prefers cleaner history:

1. `fix: restore agent bundle loading and launcher visibility`
2. `style: unify typography and component system`
3. `feat: redesign agent launcher with alpaca mascot`
4. `refactor: simplify watch subscriptions and paper detail actions`
5. `fix: resolve residual route and interaction bugs`
