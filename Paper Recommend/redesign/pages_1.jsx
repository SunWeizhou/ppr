// Inbox + Queue pages.

function InboxPage() {
  const t = useT();
  const [selected, setSelected] = useState(DEMO.papers[0].id);
  const [filter, setFilter] = useState("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const paper = DEMO.papers.find(p => p.id === selected);

  return (
    <>
      <PageHeader
        eyebrow={t("inbox.eyebrow")}
        title={t("inbox.title")}
        context={<>
          <span>{DEMO.meta.today} · Sun</span>
          <span className="dot"></span>
          <span>{t("inbox.context_count", { n: 32 })}</span>
          <span className="dot"></span>
          <span>{t("inbox.context_ranked")}</span>
        </>}>
        <button className="btn btn-tertiary">{t("inbox.jump_to_date")}</button>
        <button className="btn btn-secondary" onClick={() => setDrawerOpen(true)}>
          {t("inbox.brief_button")}
        </button>
        <button className="btn btn-primary">{t("inbox.start_triage")} →</button>
      </PageHeader>

      <div className="split">
        <div>
          <Toolbar>
            {DEMO.inboxFilters.map(f => (
              <Chip key={f.id} active={filter === f.id} count={f.count}
                onClick={() => setFilter(f.id)}>{t(`inbox.filters.${f.id}`)}</Chip>
            ))}
            <ToolbarSep/>
            <Chip>{t("inbox.sort_score")}</Chip>
            <div className="spacer"></div>
            <InlineSearch scope={t("inbox.scope_today")} placeholder={t("inbox.find_in_today")} />
          </Toolbar>

          {/* Small timeline strip — inline, compact. */}
          <div className="card card--inset" style={{ padding: "10px 14px", marginBottom: 12 }}>
            <div className="row-h" style={{ justifyContent: "space-between" }}>
              <span className="t-eyebrow">{t("inbox.recent_days")}</span>
              <div className="row-h" style={{ gap: 4 }}>
                {DEMO.inboxDates.map(d => (
                  <button key={d.key}
                    className={`filter-chip ${d.active ? "is-active" : ""}`}
                    style={{ padding: "2px 8px", height: 26 }}>
                    <span style={{ fontWeight: 500 }}>{d.d}</span>
                    <span className="count">{d.count}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="card card--flush">
            {DEMO.papers.map(p => (
              <PaperRow
                key={p.id}
                paper={p}
                selected={selected === p.id}
                onClick={() => setSelected(p.id)}
              />
            ))}
          </div>

          <div className="row-h" style={{ justifyContent: "center", padding: "16px 0" }}>
            <span className="t-meta">
              {t("inbox.showing", { shown: 8, total: 32 })} · <Kbd>J</Kbd>/<Kbd>K</Kbd> {window.I18N.lang === "cn" ? "导航" : "to navigate"}
            </span>
          </div>
        </div>

        <DetailPanel paper={paper} />
      </div>

      {drawerOpen && <DailyBriefDrawer onClose={() => setDrawerOpen(false)}/>}
    </>
  );
}

function DailyBriefDrawer({ onClose }) {
  const t = useT();
  return (
    <>
      <div className="drawer-scrim" onClick={onClose}></div>
      <aside className="drawer">
        <div className="drawer-head">
          <div className="stack stack-1">
            <span className="t-eyebrow">{t("inbox.brief_eyebrow")} · {DEMO.meta.today}</span>
            <h2 className="h-section">{t("inbox.brief_title")}</h2>
          </div>
          <IconBtn title={t("common.close")} onClick={onClose}>×</IconBtn>
        </div>
        <div className="drawer-body">
          <div className="stack stack-3">
            <span className="detail-label">{t("inbox.brief_themes")}</span>
            <div className="row-h">
              {DEMO.inboxThemes.map(th => <Tag key={th}>{th}</Tag>)}
            </div>
          </div>

          <div className="stack stack-3">
            <span className="detail-label">{t("inbox.brief_inputs")}</span>
            <div className="card card--inset">
              <div className="stack stack-3">
                <div className="row-h" style={{ justifyContent: "space-between" }}>
                  <span>{t("inbox.brief_match")}</span>
                  <span className="t-mono">+4.2 {t("inbox.brief_avg")}</span>
                </div>
                <hr className="hr"/>
                <div className="row-h" style={{ justifyContent: "space-between" }}>
                  <span>{t("inbox.brief_authors")}</span>
                  <span className="t-mono">9 {t("inbox.brief_papers")}</span>
                </div>
                <hr className="hr"/>
                <div className="row-h" style={{ justifyContent: "space-between" }}>
                  <span>{t("inbox.brief_hits")}</span>
                  <span className="t-mono">7 / 32</span>
                </div>
                <hr className="hr"/>
                <div className="row-h" style={{ justifyContent: "space-between" }}>
                  <span>{t("inbox.brief_cocite")}</span>
                  <span className="t-mono">+1.6 {t("inbox.brief_avg")}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="stack stack-3">
            <span className="detail-label">{t("inbox.brief_log")}</span>
            <p className="t-meta">{t("inbox.brief_log_text")}</p>
            <button className="btn btn-tertiary" style={{ alignSelf: "flex-start" }}>{t("inbox.brief_rerun")}</button>
          </div>
        </div>
      </aside>
    </>
  );
}

// ---------- Queue page ----------
function QueuePage() {
  const t = useT();
  const [tab, setTab] = useState("deep");
  const [selected, setSelected] = useState(DEMO.papers[5].id);
  const paper = DEMO.papers.find(p => p.id === selected);
  const section = DEMO.queueSections.find(s => s.id === tab);

  // pretend-partition papers across tabs
  const byTab = {
    skim:     DEMO.papers.filter(p => p.status === "skim" || p.rank === 1 || p.rank === 3),
    deep:     DEMO.papers.filter(p => p.status === "deep" || p.rank === 2 || p.rank === 6),
    reading:  [DEMO.papers[1], DEMO.papers[4]],
    archived: [DEMO.papers[7]],
  };
  const items = byTab[tab] || [];

  return (
    <>
      <PageHeader
        eyebrow={t("queue.eyebrow")}
        title={t("queue.title")}
        context={<>
          <span>{t("queue.context_totals")}</span>
          <span className="dot"></span>
          <span>{t("queue.context_open")}</span>
        </>}>
        <button className="btn btn-tertiary">{t("queue.export_list")}</button>
        <button className="btn btn-secondary">{t("queue.start_session")} →</button>
      </PageHeader>

      {/* Tabs act as stage — primary navigation within Queue */}
      <div className="tabs">
        {DEMO.queueSections.map(s => (
          <a href="#" key={s.id}
            className={`tab ${tab === s.id ? "is-active" : ""}`}
            onClick={e => { e.preventDefault(); setTab(s.id); }}>
            {t(`queue.group.${s.id}`, s.label)}
            <span className="count">{s.count}</span>
          </a>
        ))}
      </div>

      <div className="split">
        <div>
          <div className="row-h" style={{ justifyContent: "space-between", padding: "0 4px 12px" }}>
            <p className="t-lede" style={{ margin: 0, maxWidth: 520 }}>{section.desc}</p>
            <div className="row-h">
              <Chip>{t("queue.sort_added")}</Chip>
              <Chip>{t("queue.age_any")}</Chip>
              <Chip>{t("queue.my_note")}</Chip>
            </div>
          </div>

          <div className="card card--flush">
            {items.length ? items.map(p => (
              <PaperRow key={p.id} paper={p}
                selected={selected === p.id}
                onClick={() => setSelected(p.id)} />
            )) : (
              <div className="empty">
                <div className="empty-glyph">∅</div>
                <div className="empty-title">{t("queue.empty_title")}</div>
                <div className="t-meta">{t("queue.empty_hint")}</div>
              </div>
            )}
          </div>
        </div>

        <DetailPanel paper={paper}/>
      </div>
    </>
  );
}

Object.assign(window, { InboxPage, QueuePage });
