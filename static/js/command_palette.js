/* Command palette — ⌘K quick navigation */
/* Groups: 通用 (always), 当前论文 (when a paper is active) */

(function() {
  'use strict';

  var palette = null;
  var backdrop = null;
  var input = null;
  var results = null;
  var uidCounter = 0;

  var COMMAND_GROUPS = [
    {
      label: '通用',
      items: [
        { label: '前往 Inbox', href: '/queue?status=Inbox' },
        { label: '前往搜索', href: '/search' },
        { label: '前往阅读', href: '/reading' },
        { label: '前往关注', href: '/watch' },
        { label: '打开设置', href: '/settings' },
        { label: '切换暗色模式', action: 'toggle-dark' },
        { label: '切换语言', action: 'toggle-lang' },
        { label: '刷新订阅', action: 'refresh-subs' },
        { label: '跳转收藏', action: 'jump-to-collection' },
        { label: '新建作者订阅', action: 'new-author-sub' },
        { label: '新建查询订阅', action: 'new-query-sub' },
        { label: '新建期刊订阅', action: 'new-venue-sub' },
        { label: '为当前 workspace 运行 planner', action: 'run-planner' },
        { label: '导出全部收藏 BibTeX', action: 'export-favs' },
      ]
    },
    {
      label: '当前论文',
      items: [
        { label: '标为相关', action: 'mark-relevant' },
        { label: '忽略', action: 'mark-ignore' },
        { label: '稍后浏览', action: 'mark-skim' },
        { label: '精读', action: 'mark-deepread' },
        { label: '标为保存', action: 'mark-saved' },
        { label: '生成 AI 分析', action: 'generate-ai' },
        { label: '打开 arXiv', action: 'open-arxiv' },
      ]
    }
  ];

  /** Flatten all groups into a single array of {label, action/href, groupIndex}. */
  function flattenGroups(groups, q) {
    var result = [];
    var ql = q ? q.toLowerCase() : '';
    var hasActivePaper = document.querySelector('.paper-list-item.active') !== null;

    groups.forEach(function(group, gi) {
      if (group.label === '当前论文' && !hasActivePaper) return;

      var matched = [];
      group.items.forEach(function(item) {
        if (!ql || item.label.toLowerCase().indexOf(ql) !== -1) {
          matched.push(item);
        }
      });
      if (matched.length === 0) return;

      // Push a header sentinel with groupIndex
      result.push({_header: true, _groupIndex: gi, label: group.label});

      matched.forEach(function(item) {
        result.push(item);
      });
    });

    return result;
  }

  function nextUid() {
    uidCounter += 1;
    return 'cp-opt-' + uidCounter;
  }

  function build() {
    palette = document.createElement('div');
    palette.id = 'commandPalette';
    palette.className = 'cmd-palette';
    palette.setAttribute('role', 'dialog');
    palette.setAttribute('aria-label', 'Command palette');

    backdrop = document.createElement('div');
    backdrop.className = 'cmd-palette-backdrop';
    backdrop.onclick = close;

    var card = document.createElement('div');
    card.className = 'cmd-palette-card';

    input = document.createElement('input');
    input.type = 'text';
    input.className = 'cmd-palette-input';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'true');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', 'cp-results');
    input.setAttribute('aria-activedescendant', '');
    input.placeholder = '搜索命令…';
    input.oninput = filter;
    input.onkeydown = function(e) {
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowDown') { e.preventDefault(); moveSel(1); }
      if (e.key === 'ArrowUp') { e.preventDefault(); moveSel(-1); }
      if (e.key === 'Enter') { e.preventDefault(); activate(); }
    };

    results = document.createElement('div');
    results.id = 'cp-results';
    results.className = 'cmd-palette-list';
    results.setAttribute('role', 'listbox');
    results.setAttribute('aria-label', 'Commands');

    card.appendChild(input);
    card.appendChild(results);
    palette.appendChild(backdrop);
    palette.appendChild(card);
    document.body.appendChild(palette);
    render();
  }

  /** Return true if el is a header row (not a real option). */
  function isHeader(el) {
    return el && el.classList.contains('cmd-palette-header');
  }

  /** Skip header rows when counting selectable items. */
  function selectableItems(container) {
    var all = [].slice.call(container.querySelectorAll('[role="option"]'));
    return all.filter(function(el) { return !isHeader(el); });
  }

  function render() {
    var q = (input.value || '').toLowerCase();
    var flat = flattenGroups(COMMAND_GROUPS, q);
    results.innerHTML = '';

    if (flat.length === 0) {
      // No command matches — show search suggestions if query >= 3 chars
      if (q.length >= 3) {
        var arxivRow = createSearchRow(q, 'arxiv');
        var scholarRow = createSearchRow(q, 'scholar');
        results.appendChild(arxivRow);
        results.appendChild(scholarRow);
        selectItem(arxivRow);
      } else {
        var empty = document.createElement('div');
        empty.className = 'cmd-palette-empty';
        empty.textContent = '没有匹配命令';
        results.appendChild(empty);
        input.setAttribute('aria-activedescendant', '');
      }
      return;
    }

    flat.forEach(function(item, idx) {
      if (item._header) {
        // Render header row (not selectable, role=presentation)
        var hdr = document.createElement('div');
        hdr.className = 'cmd-palette-header';
        hdr.setAttribute('role', 'presentation');
        hdr.textContent = '▸ ' + item.label;
        results.appendChild(hdr);
      } else {
        var el = document.createElement('div');
        el.tabIndex = -1;
        el.className = 'cmd-palette-item';
        el.id = nextUid();
        el.setAttribute('role', 'option');
        el.setAttribute('aria-selected', 'false');
        el.textContent = item.label;
        el.onmouseenter = function() { selectItem(el); };
        el.onclick = function() { exec(item); };
        results.appendChild(el);
      }
    });

    // Select first non-header item
    var first = results.querySelector('[role="option"]:not(.cmd-palette-header)');
    selectItem(first);
  }

  function createSearchRow(q, source) {
    var el = document.createElement('div');
    el.tabIndex = -1;
    el.className = 'cmd-palette-item cmd-palette-search';
    el.id = nextUid();
    el.setAttribute('role', 'option');
    el.setAttribute('aria-selected', 'false');
    el.dataset.searchSource = source;
    el.textContent = '🔍 在 ' + (source === 'arxiv' ? 'arXiv' : 'Google Scholar') + " 搜索 '" + q + "'";
    el.onclick = function() {
      close();
      if (source === 'arxiv') {
        showSearchResultsModal(q);
      } else {
        // Scholar: open external link (internal API requires scholarly library)
        window.open('https://scholar.google.com/scholar?q=' + encodeURIComponent(q), '_blank');
      }
    };
    return el;
  }

  /* ── Search Results Modal ─────────────────────────────────────────── */

  var searchModalBackdrop = null;
  var searchModalEl = null;

  function showSearchResultsModal(query) {
    if (!searchModalBackdrop) {
      searchModalBackdrop = document.createElement('div');
      searchModalBackdrop.className = 'search-modal-backdrop';
      searchModalBackdrop.onclick = closeSearchResultsModal;
      searchModalEl = document.createElement('div');
      searchModalEl.className = 'search-modal';
      searchModalEl.innerHTML =
        '<div class="search-modal-header">' +
          '<h2>在 arXiv 搜索: ' + escapeHtml(query) + '</h2>' +
          '<button type="button" class="search-modal-close" onclick="window.closeSearchResultsModal()">&times;</button>' +
        '</div>' +
        '<div class="search-modal-body">' +
          '<div class="search-modal-loading">搜索中…</div>' +
        '</div>';
      document.body.appendChild(searchModalBackdrop);
      document.body.appendChild(searchModalEl);
    } else {
      searchModalEl.querySelector('h2').textContent = '在 arXiv 搜索: ' + query;
      searchModalEl.querySelector('.search-modal-body').innerHTML = '<div class="search-modal-loading">搜索中…</div>';
      searchModalBackdrop.hidden = false;
      searchModalEl.hidden = false;
    }

    // Fetch results from internal API
    fetch('/api/search?q=' + encodeURIComponent(query) + '&source=arxiv&n=10')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var body = searchModalEl.querySelector('.search-modal-body');
        if (!data.success || !data.results || data.results.length === 0) {
          body.innerHTML = '<div class="search-modal-empty">没有找到相关论文</div>';
          return;
        }
        body.innerHTML = '';
        data.results.forEach(function(paper) {
          var item = document.createElement('a');
          item.className = 'search-result-item';
          item.href = '/papers/' + encodeURIComponent(paper.paper_id);
          item.target = '_self';
          var authorText = (paper.authors && paper.authors.length > 0)
            ? (paper.authors.slice(0, 3).join(', ') + (paper.authors.length > 3 ? ' 等' : ''))
            : '';
          var abstractSnippet = paper.abstract
            ? paper.abstract.replace(/<[^>]+>/g, '').substring(0, 200) + (paper.abstract.length > 200 ? '…' : '')
            : '';
          var yearText = paper.published ? paper.published.substring(0, 4) : '';
          item.innerHTML =
            '<div class="search-result-title">' + escapeHtml(paper.title) + '</div>' +
            (authorText ? '<div class="search-result-authors">' + escapeHtml(authorText) + '</div>' : '') +
            (abstractSnippet ? '<div class="search-result-abstract">' + escapeHtml(abstractSnippet) + '</div>' : '') +
            '<div class="search-result-meta">' +
              (yearText ? '<span class="search-result-year">' + yearText + '</span>' : '') +
              '<span class="search-result-action">查看详情 →</span>' +
            '</div>';
          body.appendChild(item);
        });
      })
      .catch(function(err) {
        var body = searchModalEl.querySelector('.search-modal-body');
        body.innerHTML = '<div class="search-modal-empty">搜索失败: ' + escapeHtml(err.message) + '</div>';
      });
  }

  function closeSearchResultsModal() {
    if (searchModalBackdrop) searchModalBackdrop.hidden = true;
    if (searchModalEl) searchModalEl.hidden = true;
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Expose close function globally for onclick
  window.closeSearchResultsModal = closeSearchResultsModal;

  function filter() { render(); }

  function selectItem(el) {
    var prev = results.querySelector('[aria-selected="true"]');
    if (prev) prev.setAttribute('aria-selected', 'false');
    if (el) {
      el.setAttribute('aria-selected', 'true');
      input.setAttribute('aria-activedescendant', el.id);
    } else {
      input.setAttribute('aria-activedescendant', '');
    }
  }

  function moveSel(dir) {
    var items = selectableItems(results);
    if (items.length === 0) return;
    var idx = -1;
    for (var i = 0; i < items.length; i++) {
      if (items[i].getAttribute('aria-selected') === 'true') { idx = i; break; }
    }
    var next = Math.max(0, Math.min(items.length - 1, (idx === -1 ? 0 : idx + dir)));
    selectItem(items[next]);
    items[next].scrollIntoView({block: 'nearest'});
  }

  function activate() {
    var sel = results.querySelector('[aria-selected="true"]');
    if (!sel) return;

    // Check if this is a search row
    if (sel.dataset && sel.dataset.searchSource) {
      sel.click();
      return;
    }

    var items = selectableItems(results);
    var idx = items.indexOf(sel);
    if (idx < 0) return;

    var q = (input.value || '').toLowerCase();
    var flat = flattenGroups(COMMAND_GROUPS, q);
    // Filter out headers to get only real commands
    var flatCommands = flat.filter(function(f) { return !f._header; });
    if (flatCommands[idx]) exec(flatCommands[idx]);
  }

  function exec(cmd) {
    close();
    if (cmd.href) { window.location.href = cmd.href; }
    else if (cmd.action === 'new-author-sub' && window.createAuthorSubscription) {
      window.createAuthorSubscription();
    } else if (cmd.action === 'new-query-sub' && window.createQuerySubscription) {
      window.createQuerySubscription();
    } else if (cmd.action === 'mark-relevant' || cmd.action === 'mark-ignore' || cmd.action === 'mark-skim' || cmd.action === 'mark-deepread') {
      var active = document.querySelector('.paper-list-item.active');
      if (!active) { window.showToast('先选中一篇论文再使用此命令'); return; }
      var paperId = active.dataset.paperId;
      if (!paperId) return;
      if (cmd.action === 'mark-relevant' && window.submitPaperFeedback) {
        window.submitPaperFeedback(paperId, 'like');
      } else if (cmd.action === 'mark-ignore' && window.submitPaperFeedback) {
        window.submitPaperFeedback(paperId, 'dislike');
      } else if (cmd.action === 'mark-skim' && window.queuePaper) {
        window.queuePaper(paperId, 'Skim Later');
      } else if (cmd.action === 'mark-deepread' && window.queuePaper) {
        window.queuePaper(paperId, 'Deep Read');
      }
      window.showToast(cmd.label);
    } else if (cmd.action === 'toggle-dark') {
      var theme = document.documentElement.dataset.theme;
      var btn = document.querySelector('[data-action="toggle-theme"]');
      if (btn) {
        btn.click();
      } else {
        document.documentElement.dataset.theme = (theme === 'dark') ? 'light' : 'dark';
      }
      window.showToast('主题已切换');
    } else if (cmd.action === 'toggle-lang') {
      if (window.applyLanguage) {
        var current = document.documentElement.dataset.language || 'zh';
        window.applyLanguage(current === 'zh' ? 'en' : 'zh');
        window.showToast('语言已切换');
      }
    } else if (cmd.action === 'refresh-subs') {
      fetch('/api/subscriptions/run-all', {method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){
          window.showToast(d.success ? '订阅刷新已启动' : '失败: '+(d.error||'unknown'));
        })
        .catch(function(e){ window.showToast('刷新失败: '+e.message); });
    } else if (cmd.action === 'open-arxiv') {
      var active = document.querySelector('.paper-list-item.active');
      if (!active) { window.showToast('先选中一篇论文再使用此命令'); return; }
      if (active) {
        var paperId = active.dataset.paperId;
        if (paperId) {
          var link = active.querySelector('a[href*="/papers/"]');
          if (link) {
            fetch('/api/papers/'+encodeURIComponent(paperId))
              .then(function(r){return r.json();})
              .then(function(p) {
                if (p.link) window.open(p.link, '_blank');
                else window.open('https://arxiv.org/abs/'+paperId, '_blank');
              })
              .catch(function(){ window.open('https://arxiv.org/abs/'+paperId, '_blank'); });
          }
        }
      }
      window.showToast('正在打开 arXiv…');
    } else if (cmd.action === 'finish-today') {
      if (window.finishToday) { window.finishToday(); }
      else { window.showToast('不在今日页面'); }
    } else if (cmd.action === 'generate-ai') {
      var active = document.querySelector('.paper-list-item.active');
      if (!active) { window.showToast('先选中一篇论文再使用此命令'); return; }
      if (window.generateSelectedAiAnalysis) {
        window.generateSelectedAiAnalysis();
        window.showToast('正在生成 AI 分析…');
      }
    } else if (cmd.action === 'new-venue-sub') {
      window.location.href = '/watch';
    } else if (cmd.action === 'mark-saved' && window.queuePaper) {
      var active = document.querySelector('.paper-list-item.active');
      if (!active) { window.showToast('先选中一篇论文再使用此命令'); return; }
      var paperId = active.dataset.paperId;
      if (paperId) {
        window.queuePaper(paperId, 'Saved');
        window.showToast('已标为保存');
      }
    } else if (cmd.action === 'jump-to-collection') {
      window.location.href = '/reading?tab=collections';
    } else if (cmd.action === 'regenerate') {
      if (typeof confirmRefreshToday === 'function') confirmRefreshToday();
      else window.showToast('在今日页面使用此命令');
    } else if (cmd.action === 'export-favs') {
      window.location.href = '/api/export/bibtex/all';
    } else if (cmd.action === 'run-planner') {
      var questionIdEl = document.getElementById('researchQuestionId');
      var questionId = questionIdEl ? questionIdEl.value : '';
      if (!questionId) {
        window.showToast('请先打开一个 Research Question workspace', 'error');
        return;
      }
      fetch('/api/workspaces/questions/' + encodeURIComponent(questionId) + '/planner-runs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({trigger: 'manual'})
      }).then(function(r){return r.json();}).then(function(d){
        var q = (d.result || {}).queued_count || 0;
        window.showToast('Planner added ' + q + ' candidates to Inbox');
        if (q > 0) window.location.href = '/queue?status=Inbox';
      }).catch(function(e){
        window.showToast('Planner run failed: ' + e.message, 'error');
      });
    }
  }

  function open() {
    if (!palette) build();
    palette.hidden = false;
    input.value = '';
    input.focus();
    render();
  }

  function close() {
    if (palette) palette.hidden = true;
  }

  // Button click handler for data-action="command-palette"
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-action="command-palette"]');
    if (btn) {
      e.preventDefault();
      if (palette && !palette.hidden) { close(); } else { open(); }
    }
  });

  // Global keyboard listener
  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (palette && !palette.hidden) { close(); } else { open(); }
    }
    if (e.key === 'Escape' && palette && !palette.hidden) {
      close();
    }
  });

})();
