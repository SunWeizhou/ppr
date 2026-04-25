// Design spec section — the "交付给工程师" part of the deliverable.
// Rendered as the /spec route; written in prose with inline tokens.

function SpecPage() {
  return (
    <div className="spec">
      <span className="t-eyebrow">Deliverable · v2.0 redesign</span>
      <h1>Research Triage Desk — redesign spec</h1>
      <p className="lede">
        This redesign keeps the existing palette (paper / ink / brand blue / accent rust /
        sage / gold), the IBM Plex Sans + Serif type pairing, and the five-page information
        architecture. What changes is how the interface carries weight: one calm chrome,
        one grammar of containers, and a strict three-tier action hierarchy so the
        <i> main task is always visible without competing surfaces</i>.
      </p>

      <div className="spec-callout">
        <b>One-line direction:</b> stop treating every page like a dashboard.
        Treat it like a reading room. The chrome is quiet, the list is
        dense, the detail is the room you actually work in.
      </div>

      {/* -------- 1. Principles -------- */}
      <h2>1 · Design principles</h2>
      <div className="spec-grid-3">
        <div className="spec-card"><b>One task per screen.</b> Every page answers a single question; everything else is secondary or hidden.</div>
        <div className="spec-card"><b>Three action tiers.</b> Primary · Secondary · Tertiary. Only one Primary per page area.</div>
        <div className="spec-card"><b>One container grammar.</b> A flat card with 1px line. No glass blur, no gradient shadows, no nested cards-in-cards.</div>
        <div className="spec-card"><b>Chrome fades.</b> Nav becomes a quiet rail. No stacked status bars above the page.</div>
        <div className="spec-card"><b>Dense but legible.</b> 15px body, 14px list, 13px meta. 1.55 line-height. Row is 72–88px, not a card.</div>
        <div className="spec-card"><b>Search is contextual.</b> Never a top-level page; lives in each page's toolbar, scoped to that page.</div>
      </div>

      {/* -------- 2. What’s wrong today -------- */}
      <h2>2 · What’s wrong in the current build</h2>
      <h3>Layout / hierarchy</h3>
      <ul>
        <li><b>Three stacked chromes</b> before content: <code>.app-chrome</code> pill nav + <code>.app-statusbar</code> + the per-page <code>.command-deck</code> hero. The user sees ~320 px of chrome before a paper. <i>Keep only the side nav; remove the statusbar; shrink the hero to a 1-line PageHeader.</i></li>
        <li><b>Hero panels are overbuilt.</b> Inbox hero has 2 metric rows, a 4-chip keyword row, 2 action buttons, and a summary strip — all above the first paper. Kill the metric strip from Home; put it in the Daily Brief drawer.</li>
        <li><b>Inbox sidebar overloads</b>: Timeline + Filters + Daily Themes + Job Status in 4 disclosures. Competes with the paper list. <i>Collapse to a single thin horizontal date strip + a toolbar of filter chips. Move Themes + Job Status into the Daily Brief drawer (triggered from header).</i></li>
        <li><b>Queue / Monitor / Library all use the same hero + tab-strip + card grid.</b> Each page feels identical. Replace with: PageHeader → Tabs (where relevant) → List. No hero-panel.</li>
        <li><b>Radii inconsistent:</b> 12/16/20/28 px across containers. Standardize to 6 / 10 / 14.</li>
        <li><b>Every action is a 999 px pill.</b> No rhythm between Primary, Secondary, Destructive, Link. Use rectangular 6 px radius buttons; reserve pills only for <code>FilterChip</code>.</li>
        <li><b>Shadow + blur stack</b> on every surface (<code>.hero-panel</code>, <code>.paper-card</code>, <code>.detail-panel</code>). Flatten; one subtle <code>shadow-1</code> on raised surfaces only.</li>
      </ul>

      <h3>Density / height rules</h3>
      <ul>
        <li><code>.paper-list-item</code> has <code>min-height: 232px</code>. Too tall. New <code>.row</code> target is ~84 px (title clamp-2 + 1 line meta + 1 line summary + tag strip). Gives ~6 papers per fold.</li>
        <li><code>.scholar-card</code>, <code>.track-card</code>, <code>.paper-card</code> all have different paddings (20 / 18 / 22–24). Normalize to 14 px × 18 px for rows, 20 px for section cards.</li>
        <li><code>min-height: 116 px</code> on <code>.sidebar-panel .section-head</code> is padding for no reason. Remove.</li>
      </ul>

      <h3>Actions exposed that shouldn't be first-class</h3>
      <ul>
        <li><code>重新生成今日结果</code> (regenerate today's results) — currently a button in Inbox hero. <b>Move to Daily Brief drawer.</b></li>
        <li><code>Reset / Delete</code> on collections and query subs — currently inline. <b>Move to Collection / Sub edit modal under a "Danger zone" footer.</b></li>
        <li>Export BibTeX per-row — it's on every row's action cluster. <b>Move to the detail-panel secondary actions group only. Keep bulk export at the collection level.</b></li>
        <li><code>Follow author</code> — currently a primary-weight button on every Inbox paper. <b>Move into detail panel "Save & export" group, weight as tertiary.</b></li>
        <li><code>Send to learn_paper.py</code> — developer-only action currently on paper cards. <b>Hide behind <i>More actions</i> disclosure in the detail panel.</b></li>
        <li>Bulk bar on Inbox (<code>bulk-bar</code>) currently always visible with 4 actions. <b>Make it appear only when ≥ 1 paper is selected, sticky at the top of the list region.</b></li>
      </ul>

      <h3>Things that should change container type</h3>
      <table className="spec-table">
        <thead><tr><th>Today</th><th>Problem</th><th>Become</th></tr></thead>
        <tbody>
          <tr><td>Inbox sidebar (4 disclosures)</td><td>Competes with list</td><td>Toolbar + compact date strip + <b>Drawer</b> for themes/job</td></tr>
          <tr><td>Collection editor (full modal + danger zone inline)</td><td>Ops hidden in main view</td><td><b>Drawer</b> with tabbed sections</td></tr>
          <tr><td>Monitor → Authors / Venues / Queries / Hits tabs</td><td>Same card renderer for all 4</td><td>Keep <b>tabs</b>, change per-tab list renderer (AuthorRow ≠ VenueRow ≠ QueryRow)</td></tr>
          <tr><td>Queue subtab counts + active filter</td><td>Looks like buttons</td><td>Stage-style <b>tabs</b> with underline indicator</td></tr>
          <tr><td>Queue detail (right column, fixed card)</td><td>Clogs on mobile</td><td>DetailPanel on desktop, <b>modal/drawer</b> on narrow screens</td></tr>
          <tr><td>Sort / density / view options (Inbox, Queue, Library)</td><td>Spread across page</td><td>Single <b>dropdown</b> in toolbar: "Sort · Density · Group"</td></tr>
          <tr><td>Home "metric pills" strip</td><td>Dashboard noise</td><td>Remove. One line of plain text in PageHeader context line.</td></tr>
          <tr><td>"关注作者 / BibTeX / 加入 Collection" inline row</td><td>Flat, same weight</td><td>Grouped into DetailPanel with Primary / Secondary / Tertiary rhythm</td></tr>
        </tbody>
      </table>

      {/* -------- 3. IA -------- */}
      <h2>3 · Information architecture (unchanged top level)</h2>
      <p>Five pages, in order. Search is not a top-level nav — it's a contextual input in every page's toolbar, scoped to that page's dataset.</p>
      <table className="spec-table">
        <thead><tr><th>Page</th><th>Main task</th><th>Secondary</th><th>Deep / folded</th></tr></thead>
        <tbody>
          <tr>
            <td><b>Inbox</b></td>
            <td>Today's triage: decide keep / skim / deep / ignore per paper</td>
            <td>Switch date · Filter · Scan reasons</td>
            <td>Daily brief · Job log · Re-run scoring · Bulk triage</td>
          </tr>
          <tr>
            <td><b>Queue</b></td>
            <td>Pick what to read next in current session</td>
            <td>Move between Skim / Deep / Reading / Archived</td>
            <td>Notes · Reading session stats · Export list</td>
          </tr>
          <tr>
            <td><b>Library</b></td>
            <td>Browse / write up a specific research problem</td>
            <td>Move papers between collections · Tag · Note</td>
            <td>Export BibTeX · Merge collections · Seed query edit</td>
          </tr>
          <tr>
            <td><b>Monitor</b></td>
            <td>See what's new from followed authors / venues / queries</td>
            <td>Add / pause a subscription target · Jump to hit</td>
            <td>History per target · Edit target metadata</td>
          </tr>
          <tr>
            <td><b>Settings</b></td>
            <td>Adjust profile, ranking weights, schedule</td>
            <td>Source toggles · Density / theme</td>
            <td>Storage · Backup · Diagnostics · About</td>
          </tr>
        </tbody>
      </table>

      {/* -------- 4. Component system -------- */}
      <h2>4 · Component system</h2>
      <p>The whole UI is buildable from these ten components. Nothing else. If a view needs something outside this list, push back before inventing.</p>

      <table className="spec-table">
        <thead><tr><th>Component</th><th>Purpose</th><th>Key rules</th></tr></thead>
        <tbody>
          <tr><td><b>PageHeader</b></td><td>Page title + 1 line of context + right-aligned page actions</td><td>Max 1 Primary button. Height fixed ~72 px. Always separated by 1 px line, never a card.</td></tr>
          <tr><td><b>SectionCard</b></td><td>Standard container for a subsection</td><td>Flat, 1 px line, radius 14. No shadow unless raised-on-hover.</td></tr>
          <tr><td><b>ListItem / Row</b></td><td>The unified paper / author / venue / query renderer</td><td>Grid: lead (rank+score) · body (title + meta + summary + tags) · trail (when + overflow). Height ~84 px. Hover = background tint; selected = left 2 px brand bar + tint.</td></tr>
          <tr><td><b>DetailPanel</b></td><td>Right-hand reading / action surface</td><td>Sticky at 20 px from top, sections separated by 1 px line, primary action bar at top.</td></tr>
          <tr><td><b>ActionBar</b></td><td>Group of 2–4 buttons with explicit tier rhythm</td><td>Always Primary · Secondary · Tertiary, left-to-right. Destructive variant gets a line above.</td></tr>
          <tr><td><b>FilterChip</b></td><td>Togglable scope in toolbars</td><td>Pill (the ONLY pill in the system). Inactive = transparent; active = raised surface + line.</td></tr>
          <tr><td><b>StatusChip</b></td><td>Semantic state on a paper / target</td><td>Small rectangle, 20 px tall, dot prefix. Colors map to status enum only. Never clickable.</td></tr>
          <tr><td><b>Modal</b></td><td>Committed creates / edits requiring focus</td><td>Used for Collection create/edit, Subscription create/edit.</td></tr>
          <tr><td><b>Drawer</b></td><td>Contextual deep view that doesn't interrupt list</td><td>Right-side. Used for Daily Brief, Paper detail on mobile, Collection settings.</td></tr>
          <tr><td><b>EmptyState</b></td><td>When a tab / filter / collection has no data</td><td>Single glyph + 1 line of title + 1 line of hint. No graphic.</td></tr>
          <tr><td><b>Toast</b></td><td>Transient confirmation</td><td>Bottom-right, 2.2 s, single line.</td></tr>
        </tbody>
      </table>

      <h3>Action hierarchy (enforce globally)</h3>
      <div className="spec-grid-3">
        <div className="spec-card"><b>Primary</b><br/>Solid brand fill. <b>One per page region.</b> E.g. "Start triage", "New collection", "Apply".</div>
        <div className="spec-card"><b>Secondary</b><br/>White fill, 1 px line. For the other common action. E.g. "New subscription", "Backup now".</div>
        <div className="spec-card"><b>Tertiary</b><br/>Looks like text, subtle hover. Weekly-use and link-ish. E.g. "Export data", "History".</div>
      </div>

      {/* -------- 5. Spacing / type / density rules -------- */}
      <h2>5 · Spacing, type, density rules</h2>
      <h3>Spacing</h3>
      <ul>
        <li>Base unit 4 px. Allowed values: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56. Anything else is a bug.</li>
        <li>Page outer padding: 20 px top / 32 px sides / 64 px bottom (desktop). 16 px all-around (&lt;820 px).</li>
        <li>Section-to-section gap: 20 px. Inside a card: 14–20 px. Inside a row: 6–8 px between title / meta / summary.</li>
        <li>Between PageHeader and content: always 20 px + 1 px hr line.</li>
      </ul>

      <h3>Typography</h3>
      <table className="spec-table">
        <thead><tr><th>Role</th><th>Font</th><th>Size</th><th>Weight</th></tr></thead>
        <tbody>
          <tr><td>Page title</td><td>Plex Serif</td><td>26</td><td>600</td></tr>
          <tr><td>Section title</td><td>Plex Serif</td><td>20</td><td>600</td></tr>
          <tr><td>Row title (paper)</td><td>Plex Serif</td><td>15.5</td><td>500</td></tr>
          <tr><td>Body / UI</td><td>Plex Sans</td><td>15</td><td>400</td></tr>
          <tr><td>Meta / list meta</td><td>Plex Sans</td><td>13</td><td>400</td></tr>
          <tr><td>Eyebrow / label</td><td>Plex Sans</td><td>11</td><td>600, upper, tracked</td></tr>
          <tr><td>Mono (score, ID, time)</td><td>Plex Mono</td><td>11–13</td><td>500, tabular</td></tr>
        </tbody>
      </table>

      <h3>Card / row density</h3>
      <ul>
        <li><b>Row</b>: 14 px top/bottom × 18 px sides. Title clamp 2, summary clamp 2. Default hover tint, selected 2 px brand bar on the left.</li>
        <li><b>SectionCard</b>: 20 px all sides, 14 px radius, no shadow. Raised variant only for DetailPanel and Drawer.</li>
        <li><b>Density toggle</b>: Compact (10/14 px), Comfortable (14/18 px, default), Relaxed (18/22 px).</li>
      </ul>

      {/* -------- 6. Page-by-page layout -------- */}
      <h2>6 · Page-by-page layout</h2>

      <h3>Inbox — today's triage</h3>
      <p>Layout: <code>PageHeader · Toolbar · DateStrip · List | DetailPanel</code>. Two columns on desktop (list + detail). Daily Brief is a drawer triggered from the header.</p>
      <ul>
        <li><b>Remove</b>: the <code>command-deck</code> hero, the <code>summary-pill</code> strip, the big sidebar with themes/job, the always-visible bulk bar.</li>
        <li><b>Keep in drawer</b>: scoring inputs, themes, job log, "Re-run today's scoring" button.</li>
        <li>First fold on 1440 px should show <b>6 papers</b>. Today it shows 1–2.</li>
      </ul>

      <h3>Queue — reading flow</h3>
      <p>Layout: <code>PageHeader · Tabs(Skim / Deep / Reading / Archived) · Sort-row · List | DetailPanel</code>.</p>
      <ul>
        <li>Tabs replace the current <code>.tab-strip</code> buttons — underline not pill.</li>
        <li>Notes field belongs in the DetailPanel, not inline on every row.</li>
        <li>"Start session" is the one Primary — opens the first paper in a focused reader state (future).</li>
      </ul>

      <h3>Library — long-term assets</h3>
      <p><b>New layout — triple split.</b> Rail (collections + smart views) · Collection focus (header + toolbar + list) · (detail panel shown on row click; modal on mobile).</p>
      <ul>
        <li>Removes the card-grid of collections. Instead a left rail acts as navigation, right side is the <i>selected</i> collection.</li>
        <li>Seed query, description, actions live in a slim collection header — not a card.</li>
        <li><b>Merge</b>: <code>favorites_research.html</code>, <code>liked.html</code> views become a "Smart views → Liked" rail item. No separate page.</li>
        <li><b>Merge</b>: <code>stats_research.html</code> (library stats) → Library header context line + Settings → Storage.</li>
      </ul>

      <h3>Monitor — long-term tracking</h3>
      <p>Layout: <code>PageHeader · Tabs(Authors · Venues · Queries · Recent hits) · Per-tab toolbar · List</code>.</p>
      <ul>
        <li>Each tab uses a <b>different row renderer</b>, not the current shared <code>.paper-card</code>. Today every tab looks the same.</li>
        <li>Author row: avatar-initials · name · affiliation · sparkline of 12-month posting frequency · new-hit count.</li>
        <li>Venue row: § mark · name · issue · new-hit count · "stable / fresh" status chip.</li>
        <li>Query row: <code>Q</code> mark · query text in mono · hits/week · last-hit time.</li>
        <li>Recent hits: uses the standard PaperRow, filterable by source (author / venue / query).</li>
        <li><b>Merge</b>: <code>scholars_research.html</code>, <code>journal_research.html</code>, <code>track_research.html</code> all fold into Monitor tabs. Remove the standalone pages.</li>
      </ul>

      <h3>Settings — system</h3>
      <p>Layout: <code>PageHeader · Rail-left (section nav) · SectionCards</code>. Classic preferences pattern.</p>
      <ul>
        <li>Sections: Research profile · Ranking weights · Sources &amp; schedule · Appearance · Storage &amp; backup · About.</li>
        <li><b>Ranking weights</b>: one card with bars + numeric inputs, single "Preview / Apply" action bar. Today they're scattered.</li>
        <li>Diagnostics pane becomes a bottom "About" card; not a main-nav item.</li>
      </ul>

      {/* -------- 7. What to delete / merge -------- */}
      <h2>7 · Delete / merge / fold list (by filename)</h2>
      <table className="spec-table">
        <thead><tr><th>File</th><th>Fate</th><th>Reason</th></tr></thead>
        <tbody>
          <tr><td><code>templates/favorites_research.html</code></td><td><b>Delete</b></td><td>Becomes "Smart views → Relevant" inside Library rail.</td></tr>
          <tr><td><code>templates/scholars_research.html</code></td><td><b>Fold</b> into Monitor/Authors</td><td>Duplicate IA; adds a nav slot for one dataset.</td></tr>
          <tr><td><code>templates/journal_research.html</code></td><td><b>Fold</b> into Monitor/Venues</td><td>Same.</td></tr>
          <tr><td><code>templates/track_research.html</code></td><td><b>Fold</b> into Monitor/Queries</td><td>Same.</td></tr>
          <tr><td><code>templates/stats_research.html</code></td><td><b>Delete</b></td><td>Aggregated metrics become Settings → Storage + Library header context.</td></tr>
          <tr><td><code>templates/search_research.html</code></td><td><b>Delete as a page</b>, keep as /search JSON handler</td><td>Search is a toolbar input; a dedicated page violates the "search is contextual" rule.</td></tr>
          <tr><td><code>.app-statusbar</code> (base template)</td><td><b>Delete</b></td><td>Moved into Sidenav foot + per-page PageHeader context.</td></tr>
          <tr><td><code>.command-deck</code> hero block</td><td><b>Delete</b></td><td>Replaced by PageHeader.</td></tr>
          <tr><td><code>.hero-panel</code> on Queue/Library/Monitor/Settings</td><td><b>Delete</b></td><td>Same.</td></tr>
          <tr><td><code>.metric-grid</code> / <code>.summary-pill</code> / <code>.queue-tape</code></td><td><b>Delete</b></td><td>Dashboard-style padding; info moved to context line or Daily Brief.</td></tr>
          <tr><td><code>.inbox-workspace</code> (3-col with sidebar disclosures)</td><td><b>Replace</b> with <code>.split</code></td><td>2-column list + detail; timeline becomes a horizontal strip.</td></tr>
        </tbody>
      </table>

      {/* -------- 8. Engineering hand-off -------- */}
      <h2>8 · Engineering hand-off (how to apply in Flask / Jinja)</h2>
      <ul>
        <li>Replace <code>static/research_ui.css</code> with a slimmer file organized in this order: tokens → reset → layout (<code>.app</code>, <code>.sidenav</code>, <code>.main</code>, <code>.page-header</code>) → components (<code>.btn</code>, <code>.status</code>, <code>.filter-chip</code>, <code>.tag</code>, <code>.card</code>, <code>.row</code>, <code>.detail</code>, <code>.tabs</code>, <code>.toolbar</code>, <code>.rail</code>, <code>.drawer</code>, <code>.modal</code>) → utilities. Target &lt; 900 lines.</li>
        <li>In <code>base_research.html</code>: keep the <code>&lt;head&gt;</code> and modal definitions, replace <code>&lt;body&gt;</code> outer markup with <code>.app &gt; .sidenav + .main</code>. Move the current statusbar info into the sidenav footer; drop the <code>.app-chrome</code> + <code>.app-statusbar</code> blocks.</li>
        <li>Each page template extends base and renders: <code>PageHeader macro → (optional tabs) → Toolbar → list/split → DetailPanel</code>. Provide Jinja macros <code>{"{% macro page_header(title, eyebrow, context, actions) %}{% endmacro %}"}</code>, <code>paper_row(paper)</code>, <code>detail_panel(paper)</code>, <code>filter_chip(...)</code>, <code>status_chip(status)</code>, <code>tag(label)</code>, <code>card(title, desc, content)</code>. Keeps templates small.</li>
        <li>All modals stay (they already work); restyle only. Add Drawer container with the same open/close API as modals (<code>.drawer-scrim</code> + <code>.drawer</code>); reuse <code>openModal/closeModal</code> code path with a <code>.drawer-shell</code> class.</li>
        <li>Breakpoints: 1100 px collapses split to single column (detail becomes a drawer). 820 px collapses sidenav into top horizontal scroller.</li>
      </ul>

      <div className="spec-callout warn">
        <b>Non-goals for this pass.</b> Dark mode, new icons, a new color system, anything that touches <code>arxiv_recommender_v5.py</code>, schema changes in <code>state_store.py</code>. If the redesign makes something harder on the backend, it's wrong.
      </div>

      <div style={{ height: 80 }}></div>
    </div>
  );
}

Object.assign(window, { SpecPage });
