/* ==========================================================================
   StatDesk — i18n + theme store
   Single plain-JS module that loads before any component.
   Exposes: window.I18N = { get lang, set lang, t, subscribe }
            window.THEME = { get mode, set mode, toggle, subscribe }
   Strategy:
     - EN keys are the source of truth. CN translations live here.
     - Paper titles / abstracts / author names stay bilingual-by-reality
       (i.e. English — that's what CN-PRC academic workflows actually use).
     - Chrome, labels, nav, settings, empty states, buttons → fully translated.
   ========================================================================== */

(function () {
  // ---------------------------------------------------------------
  // Translations. Nested objects, dot-path lookup via t("nav.inbox")
  // ---------------------------------------------------------------
  const dict = {
    en: {
      brand: { name: "StatDesk", tag: "Research triage · local-first" },
      nav: {
        workflow: "Workflow",
        inbox: "Inbox",
        queue: "Queue",
        library: "Library",
        monitor: "Monitor",
        settings: "Settings",
        spec_group: "Jump to design spec",
        spec: "Design spec",
      },
      foot: {
        job_prefix: "Job",
        last_run: "last run",
        search_hint: "search anywhere",
      },
      theme: {
        light: "Light",
        dark:  "Dark",
        aria_light: "Switch to light theme",
        aria_dark:  "Switch to dark theme",
      },
      locale: {
        en: "EN", cn: "中",
        aria: "Change language",
      },
      common: {
        all: "All", today: "Today", yesterday: "Yesterday",
        search: "Search",
        save: "Save", cancel: "Cancel", done: "Done",
        more: "More", close: "Close",
        loading: "Loading…", empty: "Nothing here",
      },
      status: {
        inbox: "New", skim: "Skim", deep: "Deep",
        reading: "Reading", archived: "Archived", ignored: "Ignored",
        fresh: "fresh", idle: "idle", running: "running",
      },

      // ---- Inbox ----
      inbox: {
        eyebrow: "Today's triage",
        title: "Inbox",
        context_count: "{n} candidates",
        context_ranked: "ranked against your profile",
        brief_button: "Why today looks this way",
        start_triage: "Start triage",
        select_prompt: "Select a paper",
        select_hint: "Click any row to review reasons, decide, and route to your queue.",
        filters: { all: "All", untriaged: "Untriaged", relevant: "Relevant", queued: "Queued", ignored: "Ignored" },
        themes_label: "Daily themes",
        recent_days: "Recent days",
        showing: "Showing {shown} of {total}",
        navigate_hint: "use {j}/{k} to navigate",
        sort_score: "Score ↓",
        find_in_today: "Find in today…",
        scope_today: "today",
        jump_to_date: "Jump to date",
        job_label: "Job status",
        why_ranked: "Why this ranked here",
        abstract: "Abstract",
        save_export: "Save & export",
        more_actions: "More actions",
        primary_deep: "Deep Read",
        primary_skim: "Skim Later",
        primary_ignore: "Ignore",
        add_to_coll: "Add to Collection",
        follow_author: "Follow author",
        bibtex: "BibTeX",
        open_arxiv: "Open arXiv",
        mark_dupe: "Mark as duplicate",
        send_learn: "Send to learn_paper.py",
        download_pdf: "Download PDF",
        block_source: "Block this subscription source",
      },

      // ---- Queue ----
      queue: {
        eyebrow: "Active reading queue",
        title: "Queue",
        context_a: "papers · routed from inbox",
        group: { skim: "Skim Later", deep: "Deep Read", reading: "Reading", archived: "Archived" },
        promote: "Promote to Deep",
        demote: "Demote to Skim",
        start: "Start reading",
        archive: "Archive",
        empty_title: "No papers in this lane",
        empty_hint: "Route papers from the Inbox to start building your queue.",
      },

      // ---- Library ----
      library: {
        eyebrow: "Long-term assets",
        title: "Library",
        context_collections: "{n} collections",
        context_saved: "114 saved papers",
        context_notes: "38 with notes",
        export_bib: "Export BibTeX",
        import: "Import…",
        new_collection: "New collection",
        rail_collections: "Collections",
        rail_smart: "Smart views",
        smart_review: "Needs review",
        smart_untagged: "Untagged",
        smart_recent: "Recently added",
        col_updated: "Collection · updated {when} ago",
        col_seed: "seed",
        col_papers: "{n} papers",
        col_notes: "{n} with notes",
        chip_all: "All",
        chip_notes: "With notes",
        chip_read: "Read",
        chip_reread: "To re-read",
        chip_added: "Added ↓",
        find_in_coll: "Find in collection…",
      },

      // ---- Monitor ----
      monitor: {
        eyebrow: "Long-term tracking",
        title: "Monitor",
        context_authors: "{n} authors",
        context_venues: "{n} venues",
        context_queries: "{n} query subscriptions",
        context_new_today: "{n} new hits today",
        history: "History",
        new_sub: "New subscription",
        tabs: { authors: "Authors", venues: "Venues", queries: "Query subscriptions", hits: "Recent hits" },
        all: "All",
        with_new: "With new hits",
        paused: "Paused",
        new_issue: "New issue",
        stable: "Stable",
        hits_today: "Hits today",
        no_hits_7d: "No hits 7d",
        find_author: "Find author…",
        follow_author: "+ Follow author",
        track_venue: "+ Track venue",
        new_sub_plus: "+ New subscription",
        new_hits_n: "{n} new hit",
        new_hits_n_plural: "{n} new hits",
        hits_week: "{n} hits this week",
        last_hit: "last hit {when}",
        check_weekly: "check weekly",
        activity_12m: "12-month activity",
      },

      // ---- Settings ----
      settings: {
        eyebrow: "System",
        title: "Settings",
        context_local: "local-first · data in ~/.statdesk",
        export_data: "Export data",
        backup_now: "Backup now",
        sec_group: "Settings",
        sec: {
          profile: "Research profile",
          ranking: "Ranking weights",
          sources: "Sources & schedule",
          appearance: "Appearance",
          storage: "Storage & backup",
          about: "About & diagnostics",
        },
        profile_title: "Research profile",
        profile_desc: "This is the narrative used to score papers. Written prose works better than a keyword list.",
        profile_statement: "Profile statement",
        profile_statement_text: "I work on distribution-free uncertainty quantification and post-selection inference. Strong interest in conformal methods under covariate / label shift, and e-value constructions for anytime-valid testing. Secondary interest in generalization theory of overparametrized estimators.",
        profile_help: "Used as a soft prompt for scoring; not sent anywhere — local only.",
        keywords_title: "Keywords",
        keywords_desc: "Explicit overrides. Anything matched here gets a hard score boost.",
        keywords_add: "+ Add keyword",
        ranking_title: "Ranking weights",
        ranking_desc: "How much each signal influences today's score. Changes re-rank existing candidates immediately.",
        ranking_reset: "Reset to defaults",
        ranking_preview: "Preview changes",
        ranking_apply: "Apply",
        ranking_signals: {
          keyword: "Keyword match",
          author: "Followed authors",
          profile: "Profile similarity",
          cocite: "Library co-citation",
          venue: "Venue prior",
          recency: "Recency",
        },
        sources_title: "Sources",
        sources_desc: "Which catalogs are polled daily.",
        schedule_title: "Schedule",
        schedule_desc: "Local job that fetches and scores candidates.",
        schedule_daily: "daily · 06:00",
        schedule_wake: "also on wake after 08:00",
        schedule_edit: "Edit schedule",
        appearance_title: "Appearance",
        appearance_desc: "Density and typography. Kept minimal on purpose.",
        density: "Row density",
        density_compact: "Compact",
        density_comfy: "Comfortable",
        density_relaxed: "Relaxed",
        theme_label: "Theme",
        theme_paper: "Paper (light)",
        theme_night: "Night",
        theme_system: "System",
        language: "Language",
        storage_title: "Storage & backup",
        storage_desc: "All data stays on this machine unless you export.",
        storage_folder: "Data folder",
        storage_cache: "Cache size",
        storage_papers: "Papers indexed",
        storage_backup: "Last backup",
        storage_open: "Open folder",
        storage_export_all: "Export all",
        about_title: "About",
        about_desc: "Local-first build information.",
      },

      spec: {
        eyebrow: "Design system",
        title: "Design spec",
        context: "Tokens, components, and the reasoning behind them",
      },
    },

    // -------------------------------------------------------------
    // 简体中文 — academic research tone, not consumer copy.
    // -------------------------------------------------------------
    cn: {
      brand: { name: "StatDesk", tag: "文献初筛 · 本地优先" },
      nav: {
        workflow: "工作流",
        inbox: "收件",
        queue: "阅读队列",
        library: "文献库",
        monitor: "监听",
        settings: "设置",
        spec_group: "设计规范",
        spec: "设计规范",
      },
      foot: {
        job_prefix: "任务",
        last_run: "最近运行",
        search_hint: "全局检索",
      },
      theme: {
        light: "浅色",
        dark:  "深色",
        aria_light: "切换到浅色模式",
        aria_dark:  "切换到深色模式",
      },
      locale: {
        en: "EN", cn: "中",
        aria: "切换语言",
      },
      common: {
        all: "全部", today: "今天", yesterday: "昨天",
        search: "搜索",
        save: "保存", cancel: "取消", done: "完成",
        more: "更多", close: "关闭",
        loading: "加载中…", empty: "暂无内容",
      },
      status: {
        inbox: "新", skim: "略读", deep: "精读",
        reading: "在读", archived: "已归档", ignored: "忽略",
        fresh: "就绪", idle: "空闲", running: "运行中",
      },

      inbox: {
        eyebrow: "今日初筛",
        title: "收件",
        context_count: "{n} 条候选",
        context_ranked: "按你的画像排序",
        brief_button: "今日排序概览",
        start_triage: "开始初筛",
        select_prompt: "选一篇文章",
        select_hint: "点击任一行查看排序依据、决定去向,并分流至阅读队列。",
        filters: { all: "全部", untriaged: "未处理", relevant: "相关", queued: "已入队", ignored: "已忽略" },
        themes_label: "今日主题",
        recent_days: "最近几天",
        showing: "显示 {shown} / {total}",
        navigate_hint: "按 {j}/{k} 导航",
        sort_score: "得分 ↓",
        find_in_today: "在今天中查找…",
        scope_today: "今日",
        jump_to_date: "跳至日期",
        job_label: "任务状态",
        why_ranked: "排序依据",
        abstract: "摘要",
        save_export: "保存与导出",
        more_actions: "更多操作",
        primary_deep: "精读",
        primary_skim: "加入略读",
        primary_ignore: "忽略",
        add_to_coll: "加入收藏集",
        follow_author: "关注作者",
        bibtex: "BibTeX",
        open_arxiv: "打开 arXiv",
        mark_dupe: "标记为重复",
        send_learn: "发送到 learn_paper.py",
        download_pdf: "下载 PDF",
        block_source: "屏蔽此订阅源",
      },

      queue: {
        eyebrow: "待读与在读",
        title: "阅读队列",
        context_a: "篇 · 来自收件分流",
        context_totals: "共 14 篇 · 四种状态",
        context_open: "2 篇在读",
        export_list: "导出阅读清单",
        start_session: "开始阅读",
        sort_added: "添加时间 ↓",
        age_any: "不限日期",
        my_note: "含我的批注",
        group: { skim: "略读", deep: "精读", reading: "在读", archived: "已归档" },
        promote: "升为精读",
        demote: "降为略读",
        start: "开始阅读",
        archive: "归档",
        empty_title: "此分组暂无文章",
        empty_hint: "从「收件」或其他队列标签页分流文章。",
      },

      library: {
        eyebrow: "长期资产",
        title: "文献库",
        context_collections: "{n} 个收藏集",
        context_saved: "114 篇已收藏",
        context_notes: "38 篇含批注",
        export_bib: "导出 BibTeX",
        import: "导入…",
        new_collection: "新建收藏集",
        rail_collections: "收藏集",
        rail_smart: "智能视图",
        smart_review: "待复查",
        smart_untagged: "未标注",
        smart_recent: "最近加入",
        col_updated: "收藏集 · {when}前更新",
        col_seed: "种子",
        col_papers: "{n} 篇",
        col_notes: "{n} 篇含批注",
        chip_all: "全部",
        chip_notes: "含批注",
        chip_read: "已读",
        chip_reread: "待重读",
        chip_added: "添加时间 ↓",
        find_in_coll: "在收藏集中查找…",
      },

      monitor: {
        eyebrow: "长期跟踪",
        title: "监听",
        context_authors: "{n} 位作者",
        context_venues: "{n} 个期刊/会议",
        context_queries: "{n} 条检索订阅",
        context_new_today: "今日新增 {n} 条",
        history: "历史",
        new_sub: "新建订阅",
        tabs: { authors: "作者", venues: "期刊/会议", queries: "检索订阅", hits: "最近命中" },
        all: "全部",
        with_new: "含新命中",
        paused: "已暂停",
        new_issue: "新一期",
        stable: "稳定",
        hits_today: "今日命中",
        no_hits_7d: "7 天无命中",
        find_author: "查找作者…",
        follow_author: "+ 关注作者",
        track_venue: "+ 跟踪期刊",
        new_sub_plus: "+ 新建订阅",
        new_hits_n: "新命中 {n}",
        new_hits_n_plural: "新命中 {n}",
        hits_week: "本周命中 {n}",
        last_hit: "最近命中 {when}",
        check_weekly: "每周检查",
        activity_12m: "12 个月活跃度",
      },

      settings: {
        eyebrow: "系统",
        title: "设置",
        context_local: "本地优先 · 数据位于 ~/.statdesk",
        export_data: "导出数据",
        backup_now: "立即备份",
        sec_group: "设置",
        sec: {
          profile: "科研画像",
          ranking: "排序权重",
          sources: "数据源与调度",
          appearance: "外观",
          storage: "存储与备份",
          about: "关于与诊断",
        },
        profile_title: "科研画像",
        profile_desc: "评分模型使用的叙述。整段文字比关键词列表更有效。",
        profile_statement: "画像陈述",
        profile_statement_text: "I work on distribution-free uncertainty quantification and post-selection inference. Strong interest in conformal methods under covariate / label shift, and e-value constructions for anytime-valid testing. Secondary interest in generalization theory of overparametrized estimators.",
        profile_help: "仅作为评分的软提示；不上传，仅本地使用。",
        keywords_title: "关键词",
        keywords_desc: "显式覆盖。此处命中的关键词获得硬加分。",
        keywords_add: "+ 添加关键词",
        ranking_title: "排序权重",
        ranking_desc: "每种信号对今日评分的影响程度。更改后现有候选将立即重新排序。",
        ranking_reset: "恢复默认",
        ranking_preview: "预览更改",
        ranking_apply: "应用",
        ranking_signals: {
          keyword: "关键词匹配",
          author: "已关注作者",
          profile: "画像相似度",
          cocite: "文献库共引",
          venue: "期刊先验",
          recency: "新近度",
        },
        sources_title: "数据源",
        sources_desc: "每日拉取的编目。",
        schedule_title: "调度",
        schedule_desc: "本地拉取与评分任务。",
        schedule_daily: "每日 · 06:00",
        schedule_wake: "08:00 后唤醒时也会运行",
        schedule_edit: "编辑调度",
        appearance_title: "外观",
        appearance_desc: "密度与排版。故意保持简约。",
        density: "行密度",
        density_compact: "紧凑",
        density_comfy: "常规",
        density_relaxed: "宽松",
        theme_label: "主题",
        theme_paper: "纸面(浅色)",
        theme_night: "夜间",
        theme_system: "跟随系统",
        language: "语言",
        storage_title: "存储与备份",
        storage_desc: "除非导出,否则所有数据仅在本机。",
        storage_folder: "数据目录",
        storage_cache: "缓存大小",
        storage_papers: "索引文章数",
        storage_backup: "最近备份",
        storage_open: "打开目录",
        storage_export_all: "全部导出",
        about_title: "关于",
        about_desc: "本地优先版本信息。",
      },

      spec: {
        eyebrow: "设计系统",
        title: "设计规范",
        context: "Tokens、组件,以及背后的设计理由",
      },
    },
  };

  // ---------------------------------------------------------------
  // Tiny pub/sub store
  // ---------------------------------------------------------------
  function makeStore(initial) {
    let value = initial;
    const subs = new Set();
    return {
      get: () => value,
      set: (next) => {
        if (next === value) return;
        value = next;
        subs.forEach(fn => fn(value));
      },
      subscribe: (fn) => { subs.add(fn); return () => subs.delete(fn); },
    };
  }

  // ---------------------------------------------------------------
  // Language store
  // ---------------------------------------------------------------
  const savedLang = (() => {
    try { return localStorage.getItem("sd_lang"); } catch { return null; }
  })();
  const langStore = makeStore(savedLang === "en" || savedLang === "cn" ? savedLang : "cn"); // CN default

  langStore.subscribe((l) => {
    try { localStorage.setItem("sd_lang", l); } catch {}
    document.documentElement.setAttribute("lang", l === "cn" ? "zh-Hans" : "en");
  });
  // Apply initial html[lang]
  document.documentElement.setAttribute("lang", langStore.get() === "cn" ? "zh-Hans" : "en");

  // t("inbox.title") → "收件" | "Inbox"
  // Optional `vars` interpolates {name} placeholders.
  function t(path, vars) {
    const parts = path.split(".");
    const root = dict[langStore.get()] || dict.en;
    let cur = root;
    for (const p of parts) {
      if (cur && typeof cur === "object" && p in cur) { cur = cur[p]; }
      else { cur = undefined; break; }
    }
    let str;
    if (typeof cur === "string") { str = cur; }
    else {
      // fallback to English
      let en = dict.en;
      for (const p of parts) {
        if (en && typeof en === "object" && p in en) { en = en[p]; }
        else { en = undefined; break; }
      }
      str = typeof en === "string" ? en : path;
    }
    if (vars && typeof vars === "object") {
      return str.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
    }
    return str;
  }

  window.I18N = {
    get lang() { return langStore.get(); },
    set lang(v) { langStore.set(v); },
    t,
    subscribe: langStore.subscribe,
    dict,
  };

  // ---------------------------------------------------------------
  // Theme store
  // ---------------------------------------------------------------
  const savedTheme = (() => {
    try { return localStorage.getItem("sd_theme"); } catch { return null; }
  })();
  // Default: DARK (the user requested dark mode as the headline feature)
  const themeStore = makeStore(savedTheme === "light" || savedTheme === "dark" ? savedTheme : "dark");

  function applyTheme(mode) {
    document.documentElement.setAttribute("data-theme", mode);
    document.documentElement.style.colorScheme = mode;
  }
  applyTheme(themeStore.get());
  themeStore.subscribe((m) => {
    applyTheme(m);
    try { localStorage.setItem("sd_theme", m); } catch {}
  });

  window.THEME = {
    get mode() { return themeStore.get(); },
    set mode(v) { themeStore.set(v); },
    toggle: () => themeStore.set(themeStore.get() === "dark" ? "light" : "dark"),
    subscribe: themeStore.subscribe,
  };
})();
