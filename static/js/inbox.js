(function () {
  var inboxList = document.getElementById('inboxPaperList');
  var currentInboxItem = document.querySelector('.paper-list-item.active');
  var aiAnalysisRequestToken = 0;

  var aiAnalysisLabels = {
    one_sentence_summary: '一句话总结',
    problem: '研究问题',
    method: '方法思路',
    contribution: '主要贡献',
    limitations: '局限性',
    why_it_matters: '为什么重要',
    recommended_reading_level: '阅读建议'
  };

  // ---- Safe element helpers (guard against missing detail-panel DOM) ----

  function el(id) { return document.getElementById(id); }

  function setText(id, text) { var e = el(id); if (e) e.textContent = text; }

  function setHtml(id, html) { var e = el(id); if (e) e.innerHTML = html; }

  function setHref(id, href) { var e = el(id); if (e) e.href = href || '#'; }

  function visibleInboxItems() {
    return Array.from(document.querySelectorAll('.paper-list-item')).filter(function (item) { return !item.hidden; });
  }

  function setAiAnalysisMessage(message) {
    setText('detailAiAnalysis', message);
  }

  function selectedPaperPayload() {
    if (!currentInboxItem) return null;
    return {
      id: currentInboxItem.dataset.paperId,
      title: currentInboxItem.dataset.paperTitle,
      abstract: currentInboxItem.dataset.paperAbstract || currentInboxItem.dataset.paperSummary || '',
      authors: currentInboxItem.dataset.paperAuthors
    };
  }

  var _metadataRequestId = 0;

  async function loadSelectedPaperMetadata(item) {
    if (item.dataset.paperAbstract) return;

    var requestId = ++_metadataRequestId;
    var paperId = item.dataset.paperId;
    try {
      var resp = await fetch('/api/fetch_paper/' + encodeURIComponent(paperId));
      var data = await resp.json();
      if (!data.success || requestId !== _metadataRequestId) return;

      if (data.abstract) {
        item.dataset.paperAbstract = data.abstract;
        var hiddenAbstract = item.querySelector('[data-detail-abstract]');
        if (hiddenAbstract) hiddenAbstract.textContent = data.abstract;
        if (currentInboxItem === item) setText('detailSummary', data.abstract);
      }
    } catch (e) {}
  }

  function escapeAiHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderAiAnalysis(analysis) {
    var output = el('detailAiAnalysis');
    if (!output || !analysis) return;
    while (output.firstChild) output.removeChild(output.firstChild);
    if (analysis.status === 'not_configured') {
      output.textContent = 'AI provider 未配置。当前显示原始摘要和规则推荐原因。';
      return;
    }
    if (analysis.status === 'failed') {
      output.textContent = 'AI 分析生成失败。你仍然可以根据摘要和推荐原因判断。';
      return;
    }
    var rows = Object.entries(aiAnalysisLabels)
      .map(function (_ref) {
        var key = _ref[0], label = _ref[1], value = analysis[key] || '';
        return value ? {label: label, value: escapeAiHtml(value)} : null;
      })
      .filter(function (s) { return s; });
    if (rows.length) {
      rows.forEach(function(row) {
        var div = document.createElement('div');
        div.className = 'analysis-row';
        var strong = document.createElement('strong');
        strong.textContent = row.label;
        div.appendChild(strong);
        var span = document.createElement('span');
        span.textContent = row.value;
        div.appendChild(span);
        output.appendChild(div);
      });
    } else {
      output.textContent = '暂无 AI 分析。你可以生成分析，或继续根据摘要和推荐原因判断。';
    }
  }

  async function loadSelectedAiAnalysis() {
    var paper = selectedPaperPayload();
    if (!paper || !paper.id) return;
    var token = ++aiAnalysisRequestToken;
    setAiAnalysisMessage('暂无 AI 分析。你可以生成分析，或继续根据摘要和推荐原因判断。');
    try {
      var payload = await requestJson('/api/papers/' + encodeURIComponent(paper.id) + '/analysis');
      if (token === aiAnalysisRequestToken) renderAiAnalysis(payload.analysis);
    } catch (error) {
      if (token === aiAnalysisRequestToken && !String(error.message || '').includes('analysis_not_found')) {
        setAiAnalysisMessage('AI 分析暂时不可用。你仍然可以根据摘要和推荐原因判断。');
      }
    }
  }

  async function generateSelectedAiAnalysis() {
    var paper = selectedPaperPayload();
    if (!paper || !paper.id) return;
    var token = ++aiAnalysisRequestToken;
    setAiAnalysisMessage('正在生成 AI 分析...');
    try {
      var payload = await requestJson('/api/papers/' + encodeURIComponent(paper.id) + '/analysis/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper: paper, force: false})
      });
      if (token === aiAnalysisRequestToken) renderAiAnalysis(payload.analysis);
    } catch (error) {
      if (token === aiAnalysisRequestToken) {
        setAiAnalysisMessage('AI 分析生成失败。你仍然可以根据摘要和推荐原因判断。');
      }
    }
  }

  function setActiveInboxItem(item, options) {
    if (options === undefined) options = {};
    if (!item) return;
    document.querySelectorAll('.paper-list-item').forEach(function (node) { node.classList.remove('active'); });
    item.classList.add('active');
    currentInboxItem = item;

    // Guard: only update detail-panel elements when they exist in the DOM
    setText('detailTitle', item.dataset.paperTitle || '');
    setText('detailAuthors', item.dataset.paperAuthors || '');
    setText('detailScore', 'Score ' + Number(item.dataset.paperScore || '0').toFixed(1));
    setText('detailSummary',
      (item.querySelector('[data-detail-abstract]')?.textContent ||
       item.querySelector('[data-detail-summary]')?.textContent || ''));
    setHtml('detailRelevance', item.querySelector('[data-detail-relevance]')?.innerHTML || '');
    setHtml('detailCategories', item.querySelector('[data-detail-categories]')?.innerHTML || '');
    setHref('detailLink', item.dataset.paperLink || '#');
    setHref('detailPageLink', '/papers/' + (item.dataset.paperId || ''));

    var detailQueueState = el('detailQueueState');
    var queueStatus = item.dataset.queueStatus || '';
    if (detailQueueState) {
      detailQueueState.textContent = queueStatus;
      detailQueueState.hidden = !queueStatus;
      var normalized = String(queueStatus || '').trim().toLowerCase()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
      detailQueueState.className = normalized ? 'state-chip status-' + normalized : 'state-chip';
    }

    if (options.scroll !== false) {
      item.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    }
    loadSelectedAiAnalysis();
    loadSelectedPaperMetadata(item);
  }

  function applyInboxFilter(filterName) {
    var items = Array.from(document.querySelectorAll('.paper-list-item'));
    var visibleCount = 0;

    items.forEach(function (item) {
      var feedbackState = item.dataset.feedbackState || 'none';
      var queueStatus = item.dataset.queueStatus || '';
      var match = true;

      if (filterName === 'untriaged') {
        match = feedbackState === 'none' && !queueStatus;
      } else if (filterName === 'queued') {
        match = Boolean(queueStatus);
      } else if (filterName === 'relevant') {
        match = feedbackState === 'liked';
      } else if (filterName === 'ignored') {
        match = feedbackState === 'disliked';
      }

      item.hidden = !match;
      if (match) visibleCount += 1;
    });

    setText('visiblePaperCount', visibleCount + ' visible');
    var firstVisible = visibleInboxItems()[0];
    if (firstVisible) {
      setActiveInboxItem(firstVisible, {scroll: false});
    } else {
      currentInboxItem = null;
      setText('detailTitle', 'No papers match this filter');
      setText('detailAuthors', '');
      setText('detailScore', '');
      setText('detailSummary', '');
      setHtml('detailRelevance', '');
      setHtml('detailCategories', '');
      setText('detailAiAnalysis', '');
      setHref('detailLink', '#');
      setHref('detailPageLink', '#');
      var dqs = el('detailQueueState');
      if (dqs) { dqs.textContent = ''; dqs.hidden = true; }
    }
  }

  inboxList?.addEventListener('click', function (event) {
    var item = event.target.closest('.paper-list-item');
    if (item) setActiveInboxItem(item);
  });

  inboxList?.addEventListener('keydown', function (event) {
    var item = event.target.closest('.paper-list-item');
    if (!item) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setActiveInboxItem(item);
    }
  });

  // ---- Inbox Progress ----

  function updateProgressUI(data) {
    var pct = data.total > 0 ? Math.round((data.handled / data.total) * 100) : 0;
    var bar = el('progressBarFill');
    if (bar) bar.style.width = pct + '%';
    setText('progressHandled', data.handled);
    setText('progressLiked', data.liked || 0);
    setText('progressDisliked', data.disliked || 0);
    setText('progressQueued', data.queued || 0);
  }

  async function refreshInboxProgress() {
    if (!el('inboxProgressCard')) return;
    try {
      var total = window.__inboxTotal || 0;
      var result = await requestJson('/api/inbox/progress?total=' + total);
      if (result.success) updateProgressUI(result.data);
    } catch (error) {
      console.debug('Failed to refresh inbox progress', error);
    }
  }

  // ---- Triage action with visual feedback ----

  function _getPaperIdFromTrigger(trigger) {
    var card = trigger.closest('[data-paper-id]');
    return card ? card.dataset.paperId : null;
  }

  function _getCardFromTrigger(trigger) {
    return trigger.closest('.paper-list-item');
  }

  function _disableButtons(card) {
    if (!card) return;
    card.querySelectorAll('[data-action]').forEach(function (btn) { btn.disabled = true; });
  }

  function _enableButtons(card) {
    if (!card) return;
    card.querySelectorAll('[data-action]').forEach(function (btn) { btn.disabled = false; });
  }

  // Exposed for inline onclick handlers in today.html
  async function triageAction(paperId, action, status) {
    var card = document.querySelector('[data-paper-id="' + escapeAttrValue(paperId) + '"]');
    if (!card) return;

    var btn = card.querySelector('[data-action="' + action + '"]');
    if (btn) btn.disabled = true;

    try {
      if (status) {
        // Skim Later, Deep Read, Save — queue action
        await queuePaperStatus(paperId, status, {source: 'home_research'});
        var label = status;
        showToast('已加入队列: ' + label);
      } else {
        // Pass — feedback dislike
        await submitPaperFeedback(paperId, 'dislike');
        showToast('已忽略该论文');
      }

      // Visual feedback: dim the card or remove it
      card.style.opacity = '0.4';
      card.style.pointerEvents = 'none';
      if (card.dataset.queueStatus === undefined) card.dataset.queueStatus = '';
      if (status) card.dataset.queueStatus = status;

      // Add a status chip for queue actions
      if (status) {
        var chipRow = card.querySelector('.chip-row');
        if (chipRow) {
          var chip = document.createElement('span');
          chip.className = 'chip brand';
          chip.textContent = status;
          chipRow.appendChild(chip);
        }
      }

      refreshInboxProgress();
    } catch (error) {
      if (btn) btn.disabled = false;
      showToast('操作失败: ' + error.message, 'error');
      card.style.opacity = '1';
      card.style.pointerEvents = '';
    }
  }

  // ---- Cleanup: remove unused legacy code ----
  // The following functions are retained for backward compatibility
  // but their detail-panel dependencies are now guarded.

  async function submitPaperFeedback(paperId, action) {
    try {
      var resp = await fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper_id: paperId, action: action, source: 'research_ui'})
      });
      var data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.error || 'feedback failed');
    } catch (e) {
      console.error('submitPaperFeedback:', e);
      throw e;
    }
  }

  // ---- Expose public API ----

  Object.assign(window, {
    submitPaperFeedback: submitPaperFeedback,
    triageAction: triageAction,
    visibleInboxItems: visibleInboxItems,
    setAiAnalysisMessage: setAiAnalysisMessage,
    renderAiAnalysis: renderAiAnalysis,
    selectedPaperPayload: selectedPaperPayload,
    loadSelectedAiAnalysis: loadSelectedAiAnalysis,
    generateSelectedAiAnalysis: generateSelectedAiAnalysis,
    setActiveInboxItem: setActiveInboxItem,
    applyInboxFilter: applyInboxFilter,
    updateProgressUI: updateProgressUI,
    refreshInboxProgress: refreshInboxProgress,
  });
})();
