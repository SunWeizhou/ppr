# Phase 1: Workflow Simplification — Information Architecture

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten each page's responsibility so users immediately understand what each page does, eliminate overlapping semantics between pages, and establish a clear Inbox → Queue → Library forward flow.

**Architecture:** Pure frontend + ViewModel refactor. Five independent page groups (no shared state) that can execute in parallel. No backend API changes, no DB schema changes.

**Tech Stack:** Jinja2 templates, vanilla JS, Python 3.11 viewmodels, CSS (research_ui.css)

---

## File Structure

```
templates/
├── home_research.html      — Inbox page (modify)
├── queue_research.html     — Queue page (modify)
├── library_research.html   — Library page (modify)
├── monitor_research.html   — Monitor page (modify)
├── settings_research.html  — Settings page (modify)
app/viewmodels/
├── inbox_viewmodel.py      — Inbox context builder (modify)
├── queue_viewmodel.py      — Queue context builder (modify)
├── library_viewmodel.py    — Library context builder (modify)
├── monitor_viewmodel.py    — Monitor context builder (modify)
├── settings_viewmodel.py   — Settings context builder (modify)
app/routes/
├── queue.py                — Queue route (modify — active statuses only)
├── monitor.py              — Monitor route (modify — default tab)
static/
├── js/inbox.js             — Inbox interactions (modify)
├── research_ui.css         — Shared styles (modify — light additions)
```

---

### Task 1: Inbox — Action Hierarchy + Post-Triage CTA

**Files:**
- Modify: `templates/home_research.html`
- Modify: `static/js/inbox.js`
- Modify: `static/research_ui.css`

**Current state:** All paper actions (Relevant, Ignore, Skim Later, Deep Read, Saved, Add to Collection, Follow Author) are presented at the same visual level in the detail panel.

**Target state:** Primary actions (Relevant, Ignore, Skim Later, Deep Read) are prominent. Secondary actions (Saved, Add to Collection, Follow Author) are collapsed under a "More actions" dropdown. After today's papers are all triaged, the empty state shows "Go to Queue" as the primary CTA instead of generic messaging.

- [ ] **Step 1: Read current inbox detail panel actions**

Read `templates/home_research.html` from line 130 to end, and `static/js/inbox.js` lines 109-310 to understand current action button layout and feedback submission.

- [ ] **Step 2: Add secondary actions dropdown to home template**

In `templates/home_research.html`, find the detail panel action buttons section. Add a "More..." dropdown button after the primary action buttons. The dropdown should contain: "Save to Library", "Add to Collection", "Follow Author".

Add this HTML structure right after the existing primary action buttons (`#detailPrimaryActions` or equivalent container):

```html
<div class="detail-secondary-actions" style="margin-top: 8px; position: relative;">
    <button type="button" id="moreActionsBtn" class="btn btn-tertiary btn-sm" onclick="toggleMoreActions(event)" aria-expanded="false">
        More actions ▾
    </button>
    <div id="moreActionsMenu" class="reason-menu" role="menu" hidden style="position: absolute; bottom: 100%; left: 0; min-width: 180px;">
        <button type="button" class="btn btn-tertiary btn-sm" role="menuitem" onclick="collectInboxPaper(); closeMoreActions();">Add to Collection</button>
        <button type="button" class="btn btn-tertiary btn-sm" role="menuitem" onclick="saveInboxPaper(); closeMoreActions();">Save to Library</button>
        <button type="button" class="btn btn-tertiary btn-sm" role="menuitem" onclick="followInboxAuthor(); closeMoreActions();">Follow Author</button>
    </div>
</div>
```

- [ ] **Step 3: Add toggleMoreActions/closeMoreActions to inbox.js**

In `static/js/inbox.js`, add:

```js
function toggleMoreActions(e) {
    e.stopPropagation();
    var menu = document.getElementById('moreActionsMenu');
    var btn = document.getElementById('moreActionsBtn');
    if (menu.hidden) {
        menu.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        setTimeout(function () {
            document.addEventListener('click', function handler(ev) {
                if (!menu.contains(ev.target) && ev.target !== btn) {
                    closeMoreActions();
                    document.removeEventListener('click', handler);
                }
            });
        }, 0);
    } else {
        closeMoreActions();
    }
}

function closeMoreActions() {
    var menu = document.getElementById('moreActionsMenu');
    var btn = document.getElementById('moreActionsBtn');
    if (menu) menu.hidden = true;
    if (btn) btn.setAttribute('aria-expanded', 'false');
}
```

- [ ] **Step 4: Update post-triage empty state for "Go to Queue" CTA**

In `templates/home_research.html`, find the empty state shown when all papers are triaged. Replace the generic "You've reviewed all papers" message and CTA with a Queue-forward CTA:

```html
<div class="card empty-state-card" id="triageComplete" hidden>
    <div class="empty-state-icon">✓</div>
    <h2 class="empty-state-title">Today's papers reviewed</h2>
    <p class="empty-state-desc">All papers have been triaged. Head to Queue to start reading.</p>
    <a href="/queue" class="btn btn-primary">Go to Queue →</a>
</div>
```

- [ ] **Step 5: Show triage-complete state in inbox.js after last paper action**

In `static/js/inbox.js`, inside `submitSelectedFeedback` (around line 309-326), after successfully submitting feedback and calling `refreshInboxProgress()`, add a check:

```js
// After refreshInboxProgress() — if no visible items remain, show triage complete
var remaining = visibleInboxItems();
if (!remaining.length) {
    var triageBanner = document.getElementById('triageComplete');
    if (triageBanner) triageBanner.hidden = false;
    // Also collapse the paper list area
    var paperList = document.querySelector('.paper-list');
    if (paperList) paperList.hidden = true;
}
```

- [ ] **Step 6: Add CSS for secondary actions dropdown**

In `static/research_ui.css`, add:

```css
.detail-secondary-actions {
    position: relative;
}
.detail-secondary-actions .reason-menu {
    bottom: 100%;
    left: 0;
    margin-bottom: 4px;
}
```

- [ ] **Step 7: Verify Inbox changes visually**

Run the app and confirm:
1. Primary actions (Relevant, Ignore, Skim Later, Deep Read) are prominent
2. "More actions" dropdown shows Save/Collection/Follow
3. After triaging all papers, "Go to Queue" CTA appears
4. Dropdown closes on outside click

Run: `python web_server.py` and visit `http://localhost:5555/`

- [ ] **Step 8: Commit Inbox changes**

```bash
git add templates/home_research.html static/js/inbox.js static/research_ui.css
git commit -m "feat(inbox): action hierarchy + post-triage Queue CTA"
```

---

### Task 2: Queue — Active Reading States Only

**Files:**
- Modify: `templates/queue_research.html`
- Modify: `app/viewmodels/queue_viewmodel.py`
- Modify: `app/routes/queue.py`

**Current state:** Queue shows 5 tabs: Inbox, Skim Later, Deep Read, Saved, Archived — mixing reading states with asset states.

**Target state:** Tabs reduced to 3 active reading states: Skim Later, Deep Read, In Progress. "Saved" and "Archived" migrate to Library. "Inbox" removed from Queue (Inbox is the Inbox page). Top Reading Plan area merged with the list below into a single workbench.

- [ ] **Step 1: Define active reading statuses in viewmodel**

In `app/viewmodels/queue_viewmodel.py`, find where `queue_status_values` is passed to the template (look for `QUEUE_STATUS_VALUES` import or `queue_status_values` variable). Add a filtered list:

```python
ACTIVE_READING_STATUSES = ("Skim Later", "Deep Read", "In Progress")
```

Pass `active_statuses=ACTIVE_READING_STATUSES` to the template context.

- [ ] **Step 2: Update queue route to use active statuses only**

In `app/routes/queue.py`, find the route handler. Update the template context to include `active_statuses` and default `active_status` to `"Skim Later"` if the current status is not in the active set. Add a `queue_counts` that only counts active statuses, and pass `all_status_counts` separately for the reading plan summary.

- [ ] **Step 3: Replace queue tabs with active-only set**

In `templates/queue_research.html` lines 79-86, replace the `queue_status_values` loop:

```html
<div class="tabs">
    {% for status in active_statuses %}
        <a href="/queue?status={{ status|urlencode }}" class="tab-button {% if active_status == status %}active{% endif %}">
            {{ status }}
            <span class="count">{{ queue_counts.get(status, 0) }}</span>
        </a>
    {% endfor %}
</div>
```

Remove the toolbar hint that says `"Canonical states: Inbox / Skim Later / Deep Read / Saved / Archived"`.

- [ ] **Step 4: Merge Reading Plan into the list as a workbench header**

In `templates/queue_research.html`, remove the standalone Reading Plan card (lines 24-67) and replace with a compact status bar above the tab list that summarizes all queue states including Saved/Archived:

```html
<div class="reading-workbench-header" style="display: flex; gap: 16px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line); margin-bottom: 16px;">
    <span class="section-kicker" style="margin: 0;">Reading Workbench</span>
    <span class="chip">Deep Read: {{ all_status_counts.get('Deep Read', 0)|default(0) }}</span>
    <span class="chip">Skim Later: {{ all_status_counts.get('Skim Later', 0)|default(0) }}</span>
    <span class="chip">In Progress: {{ all_status_counts.get('In Progress', 0)|default(0) }}</span>
    <span class="chip chip-muted">Saved: {{ all_status_counts.get('Saved', 0)|default(0) }}</span>
    <span class="chip chip-muted">Archived: {{ all_status_counts.get('Archived', 0)|default(0) }}</span>
    <span class="spacer"></span>
    <a href="/library?tab=saved" class="btn btn-tertiary btn-sm">View Saved in Library</a>
</div>
```

- [ ] **Step 5: Copy Saved/Archived papers in reading plan to Library saved**

In `app/viewmodels/queue_viewmodel.py`, add a migration path: when building the Queue context, papers with status `Saved` or `Archived` should be surfaced to the Library's saved list. Add a helper or ensure `list_queue_items` for those statuses is accessible from the Library viewmodel.

- [ ] **Step 6: Update "Move To" actions in detail panel**

In `templates/queue_research.html` (around line 169), update the "Move To" button group to show only active statuses, with a secondary divider for Saved/Archived:

```html
{% for status in active_statuses %}
    <button type="button" class="btn {% if status == 'Skim Later' %}btn-warm{% elif status == 'Deep Read' %}btn-sage{% elif status == 'In Progress' %}btn-primary{% endif %}" onclick="moveQueuePaper('{{ status }}')">{{ status }}</button>
{% endfor %}
<div style="flex-basis: 100%; height: 1px; background: var(--line); margin: 4px 0;"></div>
<button type="button" class="btn btn-secondary" onclick="moveQueuePaper('Saved')">Save to Library</button>
<button type="button" class="btn btn-tertiary" onclick="moveQueuePaper('Archived')">Archive</button>
```

- [ ] **Step 7: Verify Queue changes visually**

Run the app and confirm:
1. Only 3 tabs: Skim Later / Deep Read / In Progress
2. Reading workbench header shows all counts with Saved/Archived as muted
3. "Move To" shows active states first, then Save/Archive separated
4. "View Saved in Library" link works

Run: `python web_server.py` and visit `http://localhost:5555/queue`

- [ ] **Step 8: Commit Queue changes**

```bash
git add templates/queue_research.html app/viewmodels/queue_viewmodel.py app/routes/queue.py
git commit -m "feat(queue): active reading states only, Saved/Archived → Library"
```

---

### Task 3: Library — Collections-First, History Demoted

**Files:**
- Modify: `templates/library_research.html`
- Modify: `app/viewmodels/library_viewmodel.py`

**Current state:** Three equal tabs: Collections, Saved Papers, History. History competes with Collections for primary visual space.

**Target state:** Collections as the primary view. Saved Papers as a secondary section accessible from the Collections sidebar. History demoted to a footer link or subtle secondary entry.

- [ ] **Step 1: Remove History from main tabs, add as rail link**

In `templates/library_research.html` lines 23-27, replace the 3-tab bar:

```html
<div class="tabs">
    <a href="/library?tab=collections{% if selected_collection %}&collection_id={{ selected_collection.id }}{% endif %}" class="tab-button {% if tab == 'collections' or not tab %}active{% endif %}">Collections</a>
    <a href="/library?tab=saved" class="tab-button {% if tab == 'saved' %}active{% endif %}">Saved Papers <span class="count">{{ saved_papers_count }}</span></a>
</div>
```

History is now only accessible from the sidebar rail "Smart Views" section — keep the existing rail link (line 48).

- [ ] **Step 2: Default tab to 'collections' when no tab specified**

In `app/viewmodels/library_viewmodel.py`, ensure the default tab is `"collections"` when not specified in query params. The viewmodel's `build_context()` or equivalent method should set `tab = tab or "collections"`.

- [ ] **Step 3: Add History link as subtle footer in Collections view**

In `templates/library_research.html`, at the bottom of the Collections tab content (before the closing `{% endif %}`), add a subtle history link:

```html
<div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--line); text-align: center;">
    <a href="/library?tab=history" class="btn btn-tertiary btn-sm" style="color: var(--ink-3);">
        Browse history ({{ history_dates|length }} days)
    </a>
</div>
```

- [ ] **Step 4: Keep History template section but render only when explicitly navigated**

The existing History tab template content (`{% if tab == 'history' %}`) stays intact — it still works when navigated to directly. No changes to the History rendering logic itself.

- [ ] **Step 5: Verify Library changes visually**

Run the app and confirm:
1. Only 2 main tabs: Collections and Saved Papers
2. History is accessible via sidebar rail link
3. History footer link appears at bottom of Collections view
4. Direct navigation to `/library?tab=history` still works

Run: `python web_server.py` and visit `http://localhost:5555/library`

- [ ] **Step 6: Commit Library changes**

```bash
git add templates/library_research.html app/viewmodels/library_viewmodel.py
git commit -m "feat(library): Collections-first layout, History demoted to secondary entry"
```

---

### Task 4: Monitor — Recent Hits Default, Filter Pills

**Files:**
- Modify: `templates/monitor_research.html`
- Modify: `app/viewmodels/monitor_viewmodel.py`
- Modify: `app/routes/monitor.py`

**Current state:** 5 equal-weight tabs: Authors, Venues, Queries, All, Hits. Users land on Authors by default.

**Target state:** Recent Hits as the default landing view. Subscription type (Authors/Venues/Queries) selectable via filter pills above the hits list — not as primary navigation tabs.

- [ ] **Step 1: Change default tab in monitor route**

In `app/routes/monitor.py`, change the default tab from whatever it currently is to `"recent-hits"`:

```python
tab = request.args.get("tab", "recent-hits")
```

- [ ] **Step 2: Replace 5-tab bar with Hits-first + filter pills**

In `templates/monitor_research.html` lines 32-37, replace the tab bar:

```html
<div class="tabs" style="align-items: center;">
    <span class="section-kicker" style="margin: 0 12px 0 0;">Recent Hits</span>
    <span class="chip brand">{{ recent_hits|length if recent_hits else 0 }} new</span>
    <span class="spacer"></span>
    <span style="font-size: 12px; color: var(--ink-3); margin-right: 8px;">Filter by type:</span>
    <a href="/monitor?tab=recent-hits" class="tab-button tab-button--pill {% if tab == 'recent-hits' %}active{% endif %}">All Hits</a>
    <a href="/monitor?tab=authors" class="tab-button tab-button--pill {% if tab == 'authors' %}active{% endif %}">Authors</a>
    <a href="/monitor?tab=venues" class="tab-button tab-button--pill {% if tab == 'venues' %}active{% endif %}">Venues</a>
    <a href="/monitor?tab=queries" class="tab-button tab-button--pill {% if tab == 'queries' %}active{% endif %}">Queries</a>
</div>
```

- [ ] **Step 3: Make the Recent Hits view the default shown content**

Ensure that when `tab == 'recent-hits'` (the new default), the Recent Hits content block renders. Reorder the `{% if %}` blocks so `recent-hits` comes first.

- [ ] **Step 4: Add "Send to Inbox/Queue" actions to hit items**

In the `recent-hits` tab content block (around line 225), add action buttons to each hit paper:

```html
<div class="row-actions" style="display: flex; gap: 6px; margin-top: 6px;">
    <button type="button" class="btn btn-tertiary btn-sm" onclick="sendToInbox('{{ hit.id }}')">Send to Inbox</button>
    <button type="button" class="btn btn-tertiary btn-sm" onclick="sendToQueue('{{ hit.id }}')">Send to Queue</button>
    <button type="button" class="btn btn-tertiary btn-sm" onclick="addToCollection('{{ hit.id }}')">Add to Collection</button>
    <button type="button" class="btn btn-tertiary btn-sm" onclick="dismissHit('{{ hit.id }}')">Dismiss</button>
</div>
```

- [ ] **Step 5: Add pill-style CSS for filter tabs**

In `static/research_ui.css`, add:

```css
.tab-button--pill {
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    border: 1px solid var(--line);
    background: transparent;
}
.tab-button--pill.active {
    background: var(--brand);
    color: #fff;
    border-color: var(--brand);
}
```

- [ ] **Step 6: Verify Monitor changes visually**

Run the app and confirm:
1. Landing on `/monitor` shows Recent Hits as default
2. Filter pills show All Hits / Authors / Venues / Queries
3. Hit items have action buttons (Send to Inbox, etc.)
4. Clicking a pill filters to that subscription type

Run: `python web_server.py` and visit `http://localhost:5555/monitor`

- [ ] **Step 7: Commit Monitor changes**

```bash
git add templates/monitor_research.html app/viewmodels/monitor_viewmodel.py app/routes/monitor.py static/research_ui.css
git commit -m "feat(monitor): Recent Hits default view, filter pills for subscription types"
```

---

### Task 5: Settings — Diagnostics Separation

**Files:**
- Modify: `templates/settings_research.html`

**Current state:** 4 tabs: Profile, Sources, Ranking, System. System tab contains: health overview, AI config, data import/export, backup/restore, database health, job repair — all intermixed.

**Target state:** Rename "System" to "Diagnostics". Move backup/restore, DB health, job repair from other sections into Diagnostics. Keep AI config under Profile. Keep data import/export under a compact "Data" section in Diagnostics.

- [ ] **Step 1: Rename "System" tab to "Diagnostics"**

In `templates/settings_research.html` line 29, change:

```html
<a href="/settings?tab=diagnostics" class="settings-nav-link {% if tab == 'diagnostics' %}is-active{% endif %}"><span>Diagnostics</span></a>
```

- [ ] **Step 2: Default tab handling**

In `app/viewmodels/settings_viewmodel.py`, map `tab == "system"` to `tab = "diagnostics"` for backward compatibility with existing bookmarks. Default tab remains `"profile"`.

- [ ] **Step 3: Move AI config from System to Profile**

In `templates/settings_research.html`, move the AI Analysis section (lines 223-253) from the `system` tab block into the `profile` tab block — place it after the Demotion Rules section (after line 85).

- [ ] **Step 4: Reorganize Diagnostics section**

The `diagnostics` tab (formerly `system`) should contain, in order:
1. **System Health** — the overview list-stack (lines 160-221, the job status/queue total/collections/Zotero section)
2. **Backup & Restore** — lines 267-277
3. **Database Health** — lines 279-290
4. **Data Management** — lines 255-265 (compact, bottom of page)

Remove the "How To Use" / education blocks from Diagnostics if present.

- [ ] **Step 5: Update tab conditionals**

Change `{% if tab == 'system' %}` to `{% if tab == 'diagnostics' %}` throughout `settings_research.html`.

- [ ] **Step 6: Add "Inbox → Queue" link to Back to Inbox across pages**

In `templates/queue_research.html` line 16, the existing "Back to Inbox" link is fine. No changes needed for cross-navigation — Phase 1 doesn't add new nav entries.

- [ ] **Step 7: Verify Settings changes visually**

Run the app and confirm:
1. Tab nav shows: Profile / Sources / Ranking / Diagnostics
2. AI config is under Profile tab
3. Diagnostics shows: System Health → Backup & Restore → Database Health → Data Management
4. Old `/settings?tab=system` redirects to diagnostics

Run: `python web_server.py` and visit `http://localhost:5555/settings`

- [ ] **Step 8: Commit Settings changes**

```bash
git add templates/settings_research.html app/viewmodels/settings_viewmodel.py
git commit -m "feat(settings): Diagnostics tab, AI config → Profile, clean separation"
```

---

## Execution Order

Tasks 1-5 are **fully independent** — no file is modified by more than one task (exception: `static/research_ui.css` gets append-only additions from Task 1 and Task 4, which won't conflict). They can run in parallel via 5 subagents.

## Verification Checklist

After all 5 tasks complete:
- [ ] Inbox: primary/secondary action split, Go to Queue CTA on triage complete
- [ ] Queue: 3 active tabs only, Saved/Archived accessible from Library
- [ ] Library: 2 main tabs (Collections, Saved), History via sidebar/footer
- [ ] Monitor: Recent Hits default, filter pill navigation
- [ ] Settings: Diagnostics tab, AI in Profile, Backup/DB/Repair grouped
- [ ] No 500 errors on any page
- [ ] All existing navigation links still work
- [ ] Backward compat: old URLs with legacy tab params still resolve correctly
