// Shared UI components for redesign.
// Global scope — exported to window for cross-file use.

const { useState, useMemo, useEffect, useRef, useSyncExternalStore } = React;

// ---------- i18n + theme hooks ----------
// Re-render subscribers when the store changes. useSyncExternalStore is the
// React-approved way to bind external mutable state.
function useLang() {
  const lang = useSyncExternalStore(
    (cb) => window.I18N.subscribe(cb),
    () => window.I18N.lang,
    () => "cn"
  );
  return [lang, (v) => { window.I18N.lang = v; }];
}
function useTheme() {
  const mode = useSyncExternalStore(
    (cb) => window.THEME.subscribe(cb),
    () => window.THEME.mode,
    () => "dark"
  );
  return [mode, (v) => { window.THEME.mode = v; }, () => window.THEME.toggle()];
}
// Shorthand — components call `t("inbox.title")`. The component re-renders
// whenever the language changes (via useLang above).
function useT() {
  const [lang] = useLang();
  // Return a function that closes over the current lang so t() is stable per render.
  return useMemo(() => (key, fallback) => window.I18N.t(key, fallback), [lang]);
}

// ---------- Primitives ----------
function Chip({ variant = "filter", active = false, count, children, onClick }) {
  const cls = ["filter-chip", active && "is-active"].filter(Boolean).join(" ");
  return (
    <button className={cls} onClick={onClick}>
      {children}
      {count !== undefined && <span className="count">{count}</span>}
    </button>
  );
}

function Status({ kind, children }) {
  return <span className={`status status--${kind}`}>{children}</span>;
}

function Tag({ mono, children }) {
  return <span className={`tag${mono ? " tag--mono" : ""}`}>{children}</span>;
}

function Kbd({ children }) { return <span className="kbd">{children}</span>; }

function IconBtn({ onClick, title, children }) {
  return <button className="icon-btn" title={title} onClick={onClick}>{children}</button>;
}

function More() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="2.5" cy="7" r="1.1" fill="currentColor"/>
      <circle cx="7"   cy="7" r="1.1" fill="currentColor"/>
      <circle cx="11.5" cy="7" r="1.1" fill="currentColor"/>
    </svg>
  );
}

function ChevR() {
  return <svg width="10" height="10" viewBox="0 0 10 10"><path d="M3.5 2l3 3-3 3" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

// ---------- Layout: PageHeader ----------
function PageHeader({ eyebrow, title, context, children }) {
  return (
    <header className="page-header">
      <div className="lead">
        {eyebrow && <span className="t-eyebrow">{eyebrow}</span>}
        <h1 className="h-page">{title}</h1>
        {context && <div className="context">{context}</div>}
      </div>
      <div className="actions">{children}</div>
    </header>
  );
}

// ---------- Layout: SideNav ----------
function SideNav({ active, onNav }) {
  const t = useT();
  const [lang, setLang] = useLang();
  const [mode, , toggleTheme] = useTheme();

  const items = [
    { id: "inbox",    labelKey: "nav.inbox",    count: 32, icon: "inbox" },
    { id: "queue",    labelKey: "nav.queue",    count: DEMO.meta.queueTotal, icon: "queue" },
    { id: "library",  labelKey: "nav.library",  count: DEMO.collections.length, icon: "library" },
    { id: "monitor",  labelKey: "nav.monitor",  count: 9, icon: "monitor" },
    { id: "settings", labelKey: "nav.settings", icon: "settings" },
  ];

  return (
    <aside className="sidenav">
      <div className="brand">
        <span className="brand-mark">{t("brand.name")}</span>
        <span className="brand-sub">{t("brand.tag")}</span>
      </div>

      <div className="sidenav-group-label">{t("nav.workflow")}</div>
      <nav className="stack stack-1">
        {items.map(it => (
          <a key={it.id} href="#" onClick={e => { e.preventDefault(); onNav(it.id); }}
             className={`nav-item ${active === it.id ? "is-active" : ""}`}>
            <span className={`nav-icon nav-icon--${it.icon}`}></span>
            <span>{t(it.labelKey)}</span>
            {it.count !== undefined && <span className="count">{it.count}</span>}
          </a>
        ))}
      </nav>

      <div className="sidenav-group-label" style={{ marginTop: 8 }}>{t("nav.spec_group")}</div>
      <nav className="stack stack-1">
        <a href="#" className={`nav-item ${active === "spec" ? "is-active" : ""}`}
           onClick={e => { e.preventDefault(); onNav("spec"); }}>
          <span className="nav-icon"></span>
          <span>{t("nav.spec")}</span>
        </a>
      </nav>

      <div className="sidenav-foot">
        {/* Environment controls — low-contrast, no primary affordance */}
        <div className="env-controls">
          <button
            type="button"
            className="env-toggle"
            onClick={toggleTheme}
            aria-label={mode === "dark" ? t("theme.aria_light") : t("theme.aria_dark")}
            title={mode === "dark" ? t("theme.aria_light") : t("theme.aria_dark")}
          >
            {mode === "dark" ? <IconSun/> : <IconMoon/>}
            <span className="env-toggle-label">{mode === "dark" ? t("theme.light") : t("theme.dark")}</span>
          </button>

          <div className="env-seg" role="tablist" aria-label={t("locale.aria")}>
            <button
              role="tab"
              aria-selected={lang === "cn"}
              className={`env-seg-btn ${lang === "cn" ? "is-active" : ""}`}
              onClick={() => setLang("cn")}
            >{t("locale.cn")}</button>
            <button
              role="tab"
              aria-selected={lang === "en"}
              className={`env-seg-btn ${lang === "en" ? "is-active" : ""}`}
              onClick={() => setLang("en")}
            >{t("locale.en")}</button>
          </div>
        </div>

        <div className="row">
          <span className={`status-dot ${DEMO.meta.jobStatus === "idle" ? "is-idle" : ""}`}></span>
          <span>{t("foot.job_prefix")} · {t(`status.${DEMO.meta.jobStatus}`, DEMO.meta.jobStatus)}</span>
        </div>
        <div className="row t-mono" style={{ fontSize: 11 }}>{t("foot.last_run")} {DEMO.meta.jobRun}</div>
        <div className="row">
          <Kbd>⌘K</Kbd>
          <span className="t-muted">{t("foot.search_hint")}</span>
        </div>
      </div>
    </aside>
  );
}

// Sun / moon glyphs — simple, outline, same stroke weight as other icons
function IconSun() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="2.6" stroke="currentColor" strokeWidth="1.3"/>
      <g stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
        <path d="M7 1.2v1.6"/><path d="M7 11.2v1.6"/>
        <path d="M1.2 7h1.6"/><path d="M11.2 7h1.6"/>
        <path d="M2.9 2.9l1.1 1.1"/><path d="M10 10l1.1 1.1"/>
        <path d="M11.1 2.9L10 4"/><path d="M4 10l-1.1 1.1"/>
      </g>
    </svg>
  );
}
function IconMoon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M11.3 8.4a4.4 4.4 0 01-5.7-5.7 4.6 4.6 0 105.7 5.7z"
            stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" fill="none"/>
    </svg>
  );
}

// ---------- PaperRow (the unified ListItem for papers) ----------
function PaperRow({ paper, selected, onClick, showRank = true, compact = false }) {
  const t = useT();
  const kind = paper.status || "inbox";
  const label = t(`status.${kind}`);
  return (
    <div className={`row ${selected ? "is-selected" : ""}`} onClick={onClick}>
      <div className="row-lead">
        {showRank && <span className="row-rank">{String(paper.rank).padStart(2, "0")}</span>}
        <span className="row-score">{paper.score.toFixed(1)}</span>
      </div>
      <div className="row-body">
        <div className="row-title">{paper.title}</div>
        <div className="row-meta">
          <span>{paper.authors}</span>
        </div>
        {!compact && <div className="row-summary">{paper.summary}</div>}
        <div className="row-tags">
          <Status kind={kind}>{label}</Status>
          <span className="tag tag--mono">{paper.venue}</span>
          {paper.tags.slice(0, 3).map(t => <Tag key={t}>{t}</Tag>)}
        </div>
      </div>
      <div className="row-trail">
        <span className="when">{paper.date}</span>
        <div className="row-actions">
          <IconBtn title="More"><More/></IconBtn>
        </div>
      </div>
    </div>
  );
}

// ---------- DetailPanel ----------
function DetailPanel({ paper, onClose }) {
  const t = useT();
  if (!paper) {
    return (
      <aside className="detail">
        <div className="empty">
          <div className="empty-glyph">·</div>
          <div className="empty-title">{t("inbox.select_prompt")}</div>
          <div className="t-meta">{t("inbox.select_hint")}</div>
        </div>
      </aside>
    );
  }
  return (
    <aside className="detail">
      <div className="detail-head">
        <div className="row-h" style={{ justifyContent: "space-between" }}>
          <span className="t-eyebrow">#{String(paper.rank).padStart(2, "0")} · score {paper.score.toFixed(1)}</span>
          {onClose && <IconBtn title={t("common.close")} onClick={onClose}>×</IconBtn>}
        </div>
        <div className="detail-title">{paper.title}</div>
        <div className="detail-authors">{paper.authors}</div>
        <div className="row-h">
          <Tag mono>{paper.venue}</Tag>
          <Tag mono>{paper.date}</Tag>
        </div>
      </div>

      {/* Primary actions — the only prominent group */}
      <div className="action-bar action-bar--primary">
        <button className="btn btn-primary">{t("inbox.primary_deep")}</button>
        <button className="btn btn-secondary">{t("inbox.primary_skim")}</button>
        <button className="btn btn-tertiary">{t("inbox.primary_ignore")}</button>
      </div>

      <div className="detail-section">
        <span className="detail-label">{t("inbox.why_ranked")}</span>
        <div className="stack stack-2">
          {paper.reasons.map((r, i) => (
            <div key={i} className="row-h" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
              <span className="t-meta" style={{ flex: 1 }}>{r.text}</span>
              <Tag mono>{r.where}</Tag>
              <span className="t-mono" style={{ color: "var(--sage)" }}>{r.impact}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="detail-section">
        <span className="detail-label">{t("inbox.abstract")}</span>
        <p className="detail-body">{paper.summary}</p>
      </div>

      {/* Secondary actions — grouped + less prominent */}
      <div className="detail-section">
        <span className="detail-label">{t("inbox.save_export")}</span>
        <div className="row-h">
          <button className="btn btn-secondary btn-sm">{t("inbox.add_to_coll")}</button>
          <button className="btn btn-secondary btn-sm">{t("inbox.follow_author")}</button>
          <button className="btn btn-tertiary btn-sm">{t("inbox.bibtex")}</button>
          <button className="btn btn-tertiary btn-sm">{t("inbox.open_arxiv")}</button>
        </div>
      </div>

      {/* Deep / uncommon — collapsed */}
      <details className="detail-section">
        <summary style={{ cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="detail-label">{t("inbox.more_actions")}</span>
          <ChevR/>
        </summary>
        <div className="stack stack-2" style={{ marginTop: 10 }}>
          <button className="btn btn-tertiary btn-sm" style={{ justifyContent: "flex-start" }}>{t("inbox.mark_dupe")}</button>
          <button className="btn btn-tertiary btn-sm" style={{ justifyContent: "flex-start" }}>{t("inbox.send_learn")}</button>
          <button className="btn btn-tertiary btn-sm" style={{ justifyContent: "flex-start" }}>{t("inbox.download_pdf")}</button>
          <button className="btn btn-tertiary btn-sm" style={{ justifyContent: "flex-start", color: "var(--danger)" }}>{t("inbox.block_source")}</button>
        </div>
      </details>
    </aside>
  );
}

// ---------- Toolbar ----------
function Toolbar({ children }) { return <div className="toolbar">{children}</div>; }
function ToolbarSep() { return <span className="sep"/>; }

function InlineSearch({ placeholder = "Search within this page", scope }) {
  return (
    <label className="search-inline">
      <span className="iconish"></span>
      <input placeholder={placeholder} />
      {scope && <span className="tag tag--mono" style={{ height: 18 }}>{scope}</span>}
      <kbd>/</kbd>
    </label>
  );
}

// Export
Object.assign(window, {
  useLang, useTheme, useT,
  Chip, Status, Tag, Kbd, IconBtn, More, ChevR,
  IconSun, IconMoon,
  PageHeader, SideNav,
  PaperRow, DetailPanel,
  Toolbar, ToolbarSep, InlineSearch,
});
