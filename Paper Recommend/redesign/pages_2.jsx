// Library + Monitor + Settings pages.

function LibraryPage() {
  const t = useT();
  const [selId, setSelId] = useState(DEMO.collections[0].id);
  const col = DEMO.collections.find(c => c.id === selId);
  return (
    <>
      <PageHeader
        eyebrow={t("library.eyebrow")}
        title={t("library.title")}
        context={<>
          <span>{t("library.context_collections", { n: DEMO.collections.length })}</span>
          <span className="dot"></span>
          <span>{t("library.context_saved")}</span>
          <span className="dot"></span>
          <span>{t("library.context_notes")}</span>
        </>}>
        <button className="btn btn-tertiary">{t("library.export_bib")}</button>
        <button className="btn btn-secondary">{t("library.import")}</button>
        <button className="btn btn-primary">{t("library.new_collection")}</button>
      </PageHeader>

      <div className="split split--triple">
        {/* Left rail: organize by collection — compact, no card chrome */}
        <div className="rail">
          <div className="rail-group">
            <span className="rail-group-label">{t("library.rail_collections")}</span>
            {DEMO.collections.map(c => (
              <a href="#" key={c.id}
                className={`rail-item ${selId === c.id ? "is-active" : ""}`}
                onClick={e => { e.preventDefault(); setSelId(c.id); }}>
                <span>{c.name}</span>
                <span className="count">{c.papers}</span>
              </a>
            ))}
          </div>
          <div className="rail-group">
            <span className="rail-group-label">{t("library.rail_smart")}</span>
            <a className="rail-item" href="#"><span>{t("library.smart_review")}</span><span className="count">8</span></a>
            <a className="rail-item" href="#"><span>{t("library.smart_untagged")}</span><span className="count">12</span></a>
            <a className="rail-item" href="#"><span>{t("library.smart_recent")}</span><span className="count">22</span></a>
          </div>
        </div>

        {/* Center: focused collection */}
        <div>
          <div className="stack stack-3" style={{ marginBottom: 14 }}>
            <span className="t-eyebrow">{t("library.col_updated", { when: col.updated })}</span>
            <h2 className="h-section">{col.name}</h2>
            <p className="t-lede" style={{ margin: 0, maxWidth: 600 }}>{col.desc}</p>
            <div className="row-h">
              <Tag mono>{t("library.col_seed")}: {col.seed}</Tag>
              <Tag>{t("library.col_papers", { n: col.papers })}</Tag>
              <Tag>{t("library.col_notes", { n: 12 })}</Tag>
            </div>
          </div>

          <Toolbar>
            <Chip active count={col.papers}>{t("library.chip_all")}</Chip>
            <Chip count={12}>{t("library.chip_notes")}</Chip>
            <Chip count={6}>{t("library.chip_read")}</Chip>
            <Chip count={4}>{t("library.chip_reread")}</Chip>
            <ToolbarSep/>
            <Chip>{t("library.chip_added")}</Chip>
            <div className="spacer"></div>
            <InlineSearch placeholder={t("library.find_in_coll")} scope={col.name}/>
          </Toolbar>

          <div className="card card--flush">
            {DEMO.papers.slice(0, 5).map(p => (
              <PaperRow key={p.id} paper={{ ...p, status: "archived" }} showRank={false} compact/>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ---------- Monitor page ----------
function MonitorPage() {
  const t = useT();
  const [tab, setTab] = useState("authors");
  return (
    <>
      <PageHeader
        eyebrow={t("monitor.eyebrow")}
        title={t("monitor.title")}
        context={<>
          <span>{t("monitor.context_authors", { n: DEMO.authors.length })}</span>
          <span className="dot"></span>
          <span>{t("monitor.context_venues", { n: DEMO.venues.length })}</span>
          <span className="dot"></span>
          <span>{t("monitor.context_queries", { n: DEMO.subscriptions.length })}</span>
          <span className="dot"></span>
          <span style={{ color: "var(--accent)" }}>{t("monitor.context_new_today", { n: 17 })}</span>
        </>}>
        <button className="btn btn-tertiary">{t("monitor.history")}</button>
        <button className="btn btn-primary">{t("monitor.new_sub")}</button>
      </PageHeader>

      <div className="tabs">
        {[
          ["authors", DEMO.authors.length],
          ["venues",  DEMO.venues.length],
          ["queries", DEMO.subscriptions.length],
          ["hits",    17],
        ].map(([id, n]) => (
          <a href="#" key={id} className={`tab ${tab===id?"is-active":""}`}
            onClick={e=>{e.preventDefault(); setTab(id);}}>
            {t(`monitor.tabs.${id}`)}<span className="count">{n}</span>
          </a>
        ))}
      </div>

      {tab === "authors" && <AuthorList/>}
      {tab === "venues"  && <VenueList/>}
      {tab === "queries" && <QueryList/>}
      {tab === "hits"    && <HitsList/>}
    </>
  );
}

function AuthorList() {
  const t = useT();
  return (
    <>
      <Toolbar>
        <Chip active count={DEMO.authors.length}>{t("monitor.all")}</Chip>
        <Chip count={DEMO.authors.filter(a=>a.newHits>0).length}>{t("monitor.with_new")}</Chip>
        <Chip count={0}>{t("monitor.paused")}</Chip>
        <div className="spacer"></div>
        <InlineSearch placeholder={t("monitor.find_author")}/>
        <button className="btn btn-secondary btn-sm">{t("monitor.follow_author")}</button>
      </Toolbar>
      <div className="card card--flush">
        {DEMO.authors.map(a => (
          <div className="row" key={a.name}>
            <div className="row-lead">
              <span className="row-rank">{a.name.split(" ").map(w=>w[0]).slice(0,2).join("")}</span>
            </div>
            <div className="row-body">
              <div className="row-title" style={{ fontFamily: "var(--ff-sans)", fontSize: 15 }}>{a.name}</div>
              <div className="row-meta">
                <span>{a.aff}</span>
                <span className="sep">·</span>
                <span className="t-mono">{t("monitor.activity_12m")}</span>
              </div>
              <div className="row-tags">
                {a.newHits > 0 && <Status kind="new">{t(a.newHits>1 ? "monitor.new_hits_n_plural" : "monitor.new_hits_n", { n: a.newHits })}</Status>}
                <Tag mono>arXiv · Google Scholar</Tag>
              </div>
            </div>
            <div className="row-trail">
              <span className="spark">
                {a.spark.map((v,i)=> <span key={i} style={{ height: `${Math.max(3, v*3)}px` }}></span>)}
              </span>
              <div className="row-actions">
                <IconBtn title={t("common.more")}><More/></IconBtn>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function VenueList() {
  const t = useT();
  return (
    <>
      <Toolbar>
        <Chip active count={DEMO.venues.length}>{t("monitor.all")}</Chip>
        <Chip count={3}>{t("monitor.new_issue")}</Chip>
        <Chip count={2}>{t("monitor.stable")}</Chip>
        <div className="spacer"></div>
        <button className="btn btn-secondary btn-sm">{t("monitor.track_venue")}</button>
      </Toolbar>
      <div className="card card--flush">
        {DEMO.venues.map(v => (
          <div className="row" key={v.name}>
            <div className="row-lead"><span className="row-rank">§</span></div>
            <div className="row-body">
              <div className="row-title" style={{ fontFamily: "var(--ff-serif)", fontSize: 16 }}>{v.name}</div>
              <div className="row-meta"><span className="t-mono">{v.issue}</span></div>
              <div className="row-tags">
                {v.newHits>0
                  ? <Status kind="new">{t(v.newHits>1 ? "monitor.new_hits_n_plural" : "monitor.new_hits_n", { n: v.newHits })}</Status>
                  : <Status kind="archived">{t("monitor.stable").toLowerCase()}</Status>}
                <Tag>{t("monitor.check_weekly")}</Tag>
              </div>
            </div>
            <div className="row-trail">
              <div className="row-actions"><IconBtn title={t("common.more")}><More/></IconBtn></div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function QueryList() {
  const t = useT();
  return (
    <>
      <Toolbar>
        <Chip active count={DEMO.subscriptions.length}>{t("monitor.all")}</Chip>
        <Chip count={4}>{t("monitor.hits_today")}</Chip>
        <Chip count={0}>{t("monitor.no_hits_7d")}</Chip>
        <div className="spacer"></div>
        <button className="btn btn-secondary btn-sm">{t("monitor.new_sub_plus")}</button>
      </Toolbar>
      <div className="card card--flush">
        {DEMO.subscriptions.map(s => (
          <div className="row" key={s.name}>
            <div className="row-lead"><span className="row-rank" style={{fontSize:11}}>Q</span></div>
            <div className="row-body">
              <div className="row-title" style={{ fontFamily: "var(--ff-mono)", fontSize: 13.5 }}>{s.name}</div>
              <div className="row-meta"><span>{t("monitor.last_hit", { when: s.lastHit })}</span></div>
              <div className="row-tags">
                <Status kind={s.hits > 0 ? "new" : "archived"}>{t("monitor.hits_week", { n: s.hits })}</Status>
              </div>
            </div>
            <div className="row-trail">
              <div className="row-actions"><IconBtn title={t("common.more")}><More/></IconBtn></div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function HitsList() {
  return (
    <div className="card card--flush">
      {DEMO.papers.slice(0,6).map(p => (
        <PaperRow key={p.id} paper={p} showRank={false} compact/>
      ))}
    </div>
  );
}

// ---------- Settings page ----------
function SettingsPage() {
  const t = useT();
  const [sec, setSec] = useState("profile");
  return (
    <>
      <PageHeader eyebrow={t("settings.eyebrow")} title={t("settings.title")}
        context={<><span>{t("settings.context_local")}</span></>}>
        <button className="btn btn-tertiary">{t("settings.export_data")}</button>
        <button className="btn btn-secondary">{t("settings.backup_now")}</button>
      </PageHeader>

      <div className="split split--rail-left">
        <div className="rail">
          <div className="rail-group">
            <span className="rail-group-label">{t("settings.sec_group")}</span>
            {["profile","ranking","sources","appearance","storage","about"].map(id => (
              <a href="#" key={id} className={`rail-item ${sec===id?"is-active":""}`}
                onClick={e=>{e.preventDefault(); setSec(id);}}>{t(`settings.sec.${id}`)}</a>
            ))}
          </div>
        </div>

        <div className="stack stack-4">
          {sec === "profile"    && <SettingsProfile/>}
          {sec === "ranking"    && <SettingsRanking/>}
          {sec === "sources"    && <SettingsSources/>}
          {sec === "appearance" && <SettingsAppearance/>}
          {sec === "storage"    && <SettingsStorage/>}
          {sec === "about"      && <SettingsAbout/>}
        </div>
      </div>
    </>
  );
}

function SetCard({ title, desc, children }) {
  return (
    <section className="card">
      <div className="card-head">
        <div className="lead">
          <h3 className="h-card">{title}</h3>
          {desc && <p className="t-meta" style={{ margin: 0, maxWidth: 640 }}>{desc}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function SettingsProfile() {
  const t = useT();
  return (
    <>
      <SetCard title={t("settings.profile_title")} desc={t("settings.profile_desc")}>
        <div className="field">
          <label className="field-label">{t("settings.profile_statement")}</label>
          <textarea className="textarea" rows={5} defaultValue={t("settings.profile_statement_text")}/>
          <span className="field-help">{t("settings.profile_help")}</span>
        </div>
      </SetCard>

      <SetCard title={t("settings.keywords_title")} desc={t("settings.keywords_desc")}>
        <div className="row-h">
          {["conformal","covariate shift","post-selection","e-values","double descent","minimax","selective inference"].map(k =>
            <Tag key={k}>{k} <span style={{opacity:0.5, marginLeft: 4}}>×</span></Tag>
          )}
          <button className="btn btn-tertiary btn-sm">{t("settings.keywords_add")}</button>
        </div>
      </SetCard>
    </>
  );
}

function SettingsRanking() {
  const t = useT();
  const weights = [
    ["keyword", 0.35],
    ["author",  0.22],
    ["profile", 0.18],
    ["cocite",  0.12],
    ["venue",   0.08],
    ["recency", 0.05],
  ];
  return (
    <SetCard title={t("settings.ranking_title")} desc={t("settings.ranking_desc")}>
      <div className="stack stack-3">
        {weights.map(([id, v]) => (
          <div key={id} className="stack stack-1">
            <div className="row-h" style={{ justifyContent: "space-between" }}>
              <span>{t(`settings.ranking_signals.${id}`)}</span>
              <span className="t-mono">{v.toFixed(2)}</span>
            </div>
            <div style={{ height: 6, background: "var(--paper-2)", borderRadius: 3 }}>
              <div style={{ height: "100%", width: `${v*100}%`, background: "var(--brand)", borderRadius: 3 }}></div>
            </div>
          </div>
        ))}
      </div>
      <div className="action-bar">
        <button className="btn btn-tertiary">{t("settings.ranking_reset")}</button>
        <div style={{flex:1}}></div>
        <button className="btn btn-secondary">{t("settings.ranking_preview")}</button>
        <button className="btn btn-primary">{t("settings.ranking_apply")}</button>
      </div>
    </SetCard>
  );
}

function SettingsSources() {
  const t = useT();
  return (
    <>
      <SetCard title={t("settings.sources_title")} desc={t("settings.sources_desc")}>
        <div className="stack stack-2">
          {[["arXiv · stat.ML/ME/TH", true],["OpenReview: NeurIPS, ICML, ICLR", true],["JMLR rolling feed", true],["Semantic Scholar (co-citation)", false]].map(([l,on]) => (
            <div key={l} className="row-h" style={{ justifyContent: "space-between" }}>
              <span>{l}</span>
              <div className={`switch${on?" is-on":""}`}></div>
            </div>
          ))}
        </div>
      </SetCard>
      <SetCard title={t("settings.schedule_title")} desc={t("settings.schedule_desc")}>
        <div className="row-h">
          <Tag mono>{t("settings.schedule_daily")}</Tag>
          <Tag mono>{t("settings.schedule_wake")}</Tag>
          <button className="btn btn-tertiary btn-sm">{t("settings.schedule_edit")}</button>
        </div>
      </SetCard>
    </>
  );
}

function SettingsAppearance() {
  const t = useT();
  const [mode, setMode, toggleTheme] = useTheme();
  const [lang, setLang] = useLang();
  return (
    <SetCard title={t("settings.appearance_title")} desc={t("settings.appearance_desc")}>
      <div className="stack stack-3">
        <div className="row-h" style={{ justifyContent:"space-between" }}>
          <span>{t("settings.density")}</span>
          <div className="row-h">
            <Chip>{t("settings.density_compact")}</Chip>
            <Chip active>{t("settings.density_comfy")}</Chip>
            <Chip>{t("settings.density_relaxed")}</Chip>
          </div>
        </div>
        <hr className="hr"/>
        <div className="row-h" style={{ justifyContent:"space-between" }}>
          <span>{t("settings.theme_label")}</span>
          <div className="row-h">
            <Chip active={mode==="light"} onClick={() => setMode("light")}>{t("settings.theme_paper")}</Chip>
            <Chip active={mode==="dark"}  onClick={() => setMode("dark")}>{t("settings.theme_night")}</Chip>
          </div>
        </div>
        <hr className="hr"/>
        <div className="row-h" style={{ justifyContent:"space-between" }}>
          <span>{t("settings.language")}</span>
          <div className="row-h">
            <Chip active={lang==="cn"} onClick={() => setLang("cn")}>简体中文</Chip>
            <Chip active={lang==="en"} onClick={() => setLang("en")}>English</Chip>
          </div>
        </div>
      </div>
    </SetCard>
  );
}

function SettingsStorage() {
  const t = useT();
  return (
    <SetCard title={t("settings.storage_title")} desc={t("settings.storage_desc")}>
      <div className="stack stack-2">
        <div className="row-h" style={{ justifyContent: "space-between" }}>
          <span>{t("settings.storage_folder")}</span><span className="t-mono">~/.statdesk/</span>
        </div>
        <div className="row-h" style={{ justifyContent: "space-between" }}>
          <span>{t("settings.storage_cache")}</span><span className="t-mono">412 MB</span>
        </div>
        <div className="row-h" style={{ justifyContent: "space-between" }}>
          <span>{t("settings.storage_papers")}</span><span className="t-mono">12,480</span>
        </div>
        <div className="row-h" style={{ justifyContent: "space-between" }}>
          <span>{t("settings.storage_backup")}</span><span className="t-mono">2026-04-19 22:40</span>
        </div>
      </div>
      <div className="action-bar">
        <button className="btn btn-tertiary">{t("settings.storage_open")}</button>
        <div style={{flex:1}}></div>
        <button className="btn btn-secondary">{t("settings.storage_export_all")}</button>
        <button className="btn btn-secondary">{t("settings.backup_now")}</button>
      </div>
    </SetCard>
  );
}

function SettingsAbout() {
  const t = useT();
  return (
    <SetCard title={t("settings.about_title")} desc={t("settings.about_desc")}>
      <div className="stack stack-2 t-mono" style={{ fontSize: 12 }}>
        <div>StatDesk v2.0.0 (redesign preview)</div>
        <div>python 3.12.1 · flask 3.0.2 · state_store.py ok</div>
        <div>build 2026-04-20</div>
      </div>
    </SetCard>
  );
}

Object.assign(window, { LibraryPage, MonitorPage, SettingsPage });
