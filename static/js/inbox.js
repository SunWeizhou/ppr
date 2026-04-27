(function () {
  var inboxList = document.getElementById('inboxPaperList');
  var filterButtons = Array.from(document.querySelectorAll('[data-filter-chip]'));
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

  function visibleInboxItems() {
    return Array.from(document.querySelectorAll('.paper-list-item')).filter(function (item) { return !item.hidden; });
  }

  function setAiAnalysisMessage(message) {
    var output = document.getElementById('detailAiAnalysis');
    if (output) output.textContent = message;
  }

  function selectedPaperPayload() {
    if (!currentInboxItem) return null;
    return {
      id: currentInboxItem.dataset.paperId,
      title: currentInboxItem.dataset.paperTitle,
      abstract: currentInboxItem.dataset.paperSummary,
      authors: currentInboxItem.dataset.paperAuthors
    };
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
    var output = document.getElementById('detailAiAnalysis');
    if (!output || !analysis) return;
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
        var key = _ref[0];
        var label = _ref[1];
        var value = analysis[key] || '';
        return value ? '<div class="analysis-row"><strong>' + label + '</strong><span>' + escapeAiHtml(value) + '</span></div>' : '';
      })
      .filter(function (s) { return s; });
    output.innerHTML = rows.length ? rows.join('') : '暂无 AI 分析。你可以生成分析，或继续根据摘要和推荐原因判断。';
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
    document.querySelectorAll('.paper-list-item').forEach(function (node) { return node.classList.remove('active'); });
    item.classList.add('active');
    currentInboxItem = item;

    document.getElementById('detailTitle').textContent = item.dataset.paperTitle || '';
    document.getElementById('detailAuthors').textContent = item.dataset.paperAuthors || '';
    document.getElementById('detailScore').textContent = 'Score ' + Number(item.dataset.paperScore || '0').toFixed(1);
    document.getElementById('detailSummary').textContent = item.querySelector('[data-detail-summary]')?.textContent || '';
    document.getElementById('detailRelevance').innerHTML = item.querySelector('[data-detail-relevance]')?.innerHTML || '';
    document.getElementById('detailCategories').innerHTML = item.querySelector('[data-detail-categories]')?.innerHTML || '';
    document.getElementById('detailLink').href = item.dataset.paperLink || '#';
    document.getElementById('detailPageLink').href = '/papers/' + (item.dataset.paperId || '');
    var detailQueueState = document.getElementById('detailQueueState');
    var queueStatus = item.dataset.queueStatus || '';
    detailQueueState.textContent = queueStatus;
    detailQueueState.hidden = !queueStatus;
    var normalized = String(queueStatus || '')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    detailQueueState.className = normalized ? 'state-chip status-' + normalized : 'state-chip';

    if (options.scroll !== false) {
      item.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    }
    loadSelectedAiAnalysis();
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

    document.getElementById('visiblePaperCount').textContent = visibleCount + ' visible';
    var firstVisible = visibleInboxItems()[0];
    if (firstVisible) {
      setActiveInboxItem(firstVisible, {scroll: false});
    }
  }

  function handleFilterChipClick(chip) {
    filterButtons.forEach(function (item) {
      item.classList.remove('active');
      item.setAttribute('aria-pressed', 'false');
    });
    chip.classList.add('active');
    chip.setAttribute('aria-pressed', 'true');
    applyInboxFilter(chip.dataset.filter || 'all');
  }

  document.querySelector('.toolbar')?.addEventListener('click', function (event) {
    var chip = event.target.closest('[data-filter-chip]');
    if (chip) handleFilterChipClick(chip);
  });

  document.querySelector('.toolbar')?.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' || event.key === ' ') {
      var chip = event.target.closest('[data-filter-chip]');
      if (chip) {
        event.preventDefault();
        handleFilterChipClick(chip);
      }
    }
  });

  inboxList?.addEventListener('click', function (event) {
    var item = event.target.closest('.paper-list-item');
    if (item) {
      setActiveInboxItem(item);
    }
  });

  inboxList?.addEventListener('keydown', function (event) {
    var item = event.target.closest('.paper-list-item');
    if (!item) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setActiveInboxItem(item);
    }
  });

  async function submitSelectedFeedback(action) {
    if (!currentInboxItem) return;
    try {
      await requestJson('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          paper_id: currentInboxItem.dataset.paperId,
          action: action,
          title: currentInboxItem.dataset.paperTitle,
          abstract: currentInboxItem.dataset.paperSummary,
          authors: currentInboxItem.dataset.paperAuthors,
          score: Number(currentInboxItem.dataset.paperScore || '0'),
          relevance: currentInboxItem.dataset.paperRelevance,
          source: 'home_research'
        })
      });
      currentInboxItem.dataset.feedbackState = action === 'like' ? 'liked' : 'disliked';
      currentInboxItem.classList.toggle('state-liked', action === 'like');
      currentInboxItem.classList.toggle('state-disliked', action === 'dislike');
      showToast(action === 'like' ? '已标为 Relevant' : '已忽略该论文');
      refreshInboxProgress();
    } catch (error) {
      showToast('操作失败: ' + error.message, 'error');
    }
  }

  async function queueSelectedPaper(status) {
    if (!currentInboxItem) return;
    try {
      await queuePaperStatus(currentInboxItem.dataset.paperId, status, {source: 'home_research'});
      refreshInboxProgress();
    } catch (error) {
      showToast('加入队列失败: ' + error.message, 'error');
    }
  }

  async function collectSelectedPaper() {
    if (!currentInboxItem) return;
    try {
      await addPaperToCollection(currentInboxItem.dataset.paperId, {
        defaultName: currentInboxItem.dataset.paperTitle.slice(0, 48),
        source: 'home_research'
      });
    } catch (error) {
      showToast('加入 Collection 失败: ' + error.message, 'error');
    }
  }

  function openSelectedPaper(event) {
    if (!currentInboxItem) return;
    if (event) {
      event.preventDefault();
      window.open(currentInboxItem.dataset.paperLink || '#', '_blank');
    }
    trackPaperOpen(currentInboxItem.dataset.paperId, 'home_research');
  }

  function toggleMoreActions() {
    var menu = document.getElementById('moreActionsMenu');
    if (menu) menu.hidden = !menu.hidden;
  }

  function closeMoreActions() {
    var menu = document.getElementById('moreActionsMenu');
    if (menu) menu.hidden = true;
  }

  function toggleFullExplanation() {
    if (currentInboxItem) openPaperActions(currentInboxItem, 'home_research');
  }

  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-more-actions-toggle]')) return;
    var dropdown = event.target.closest('.more-actions-dropdown');
    if (!dropdown) closeMoreActions();
  });

  if (currentInboxItem) {
    setActiveInboxItem(currentInboxItem, {scroll: false});
  }

  function focusRelativeInboxItem(direction) {
    var items = visibleInboxItems();
    if (!items.length || !currentInboxItem) return;
    var currentIndex = Math.max(items.indexOf(currentInboxItem), 0);
    var nextIndex = Math.min(Math.max(currentIndex + direction, 0), items.length - 1);
    setActiveInboxItem(items[nextIndex]);
    items[nextIndex].focus();
  }

  document.addEventListener('keydown', function (event) {
    var tag = event.target?.tagName;
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      focusRelativeInboxItem(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusRelativeInboxItem(-1);
    } else if (event.key.toLowerCase() === 'r') {
      event.preventDefault();
      submitSelectedFeedback('like');
    } else if (event.key.toLowerCase() === 'i') {
      event.preventDefault();
      submitSelectedFeedback('dislike');
    } else if (event.key.toLowerCase() === 's') {
      event.preventDefault();
      queueSelectedPaper('Skim Later');
    } else if (event.key.toLowerCase() === 'd') {
      event.preventDefault();
      queueSelectedPaper('Deep Read');
    } else if (event.key.toLowerCase() === 'o') {
      event.preventDefault();
      openSelectedPaper();
    }
  });

  // ---- Inbox Progress Tracking ----

  function updateProgressUI(data) {
    var pct = data.total > 0 ? Math.round((data.handled / data.total) * 100) : 0;
    var bar = document.getElementById('progressBarFill');
    if (bar) bar.style.width = pct + '%';
    var handledEl = document.getElementById('progressHandled');
    if (handledEl) handledEl.textContent = data.handled;
    var likedEl = document.getElementById('progressLiked');
    if (likedEl) likedEl.textContent = data.liked || 0;
    var dislikedEl = document.getElementById('progressDisliked');
    if (dislikedEl) dislikedEl.textContent = data.disliked || 0;
    var queuedEl = document.getElementById('progressQueued');
    if (queuedEl) queuedEl.textContent = data.queued || 0;
  }

  async function refreshInboxProgress() {
    var progressCard = document.getElementById('inboxProgressCard');
    if (!progressCard) return;
    try {
      var total = window.__inboxTotal || 0;
      var result = await requestJson('/api/inbox/progress?total=' + total);
      if (result.success) updateProgressUI(result.data);
    } catch (error) {
      console.debug('Failed to refresh inbox progress', error);
    }
  }

  async function finishToday() {
    var total = window.__inboxTotal || 0;
    var progress = { handled: 0, liked: 0, disliked: 0, skimmed: 0, deep_read: 0, queued: 0 };

    try {
      var result = await requestJson('/api/inbox/progress?total=' + total);
      if (result.success) progress = result.data;
    } catch (error) {
      console.debug('Failed to fetch progress for summary', error);
    }

    var dateStr = window.__inboxDate || '';
    document.getElementById('triageSummaryDate').textContent = dateStr;
    document.getElementById('summaryTotal').textContent = progress.total;
    document.getElementById('summaryHandled').textContent = progress.handled;
    document.getElementById('summaryLiked').textContent = progress.liked || 0;
    document.getElementById('summaryDisliked').textContent = progress.disliked || 0;
    document.getElementById('summarySkimmed').textContent = progress.skimmed || 0;
    document.getElementById('summaryDeepRead').textContent = progress.deep_read || 0;

    openModal('triageCompleteModal');
  }

  async function confirmTriageComplete() {
    var total = window.__inboxTotal || 0;
    try {
      var dateStr = window.__inboxDate || '';
      var result = await requestJson('/api/inbox/triage-complete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ date: dateStr, total: total })
      });
      closeModal('triageCompleteModal');
      showToast('今日筛选完成！');
      var progressContent = document.getElementById('inboxProgressContent');
      var progressComplete = document.getElementById('inboxProgressComplete');
      var finishBtn = document.getElementById('finishTodayBtn');
      if (progressContent) progressContent.hidden = true;
      if (progressComplete) progressComplete.hidden = false;
      if (finishBtn) finishBtn.hidden = true;
      var summary = result.summary || {};
      var summaryEl = document.getElementById('completeSummaryText');
      if (summaryEl) {
        summaryEl.textContent = 'You handled ' + (summary.papers_processed || 0) + ' papers: '
          + (summary.papers_liked || 0) + ' liked, '
          + (summary.papers_skimmed || 0) + ' skimmed later, '
          + (summary.papers_deep_read || 0) + ' deep read, '
          + (summary.papers_disliked || 0) + ' ignored.';
      }
    } catch (error) {
      showToast('记录失败: ' + error.message, 'error');
    }
  }

  // Initialize
  applyInboxFilter(window.__inboxFilter || 'all');
  refreshInboxProgress();

  Object.assign(window, {
    visibleInboxItems: visibleInboxItems,
    escapeAiHtml: escapeAiHtml,
    renderAiAnalysis: renderAiAnalysis,
    setAiAnalysisMessage: setAiAnalysisMessage,
    selectedPaperPayload: selectedPaperPayload,
    loadSelectedAiAnalysis: loadSelectedAiAnalysis,
    generateSelectedAiAnalysis: generateSelectedAiAnalysis,
    setActiveInboxItem: setActiveInboxItem,
    applyInboxFilter: applyInboxFilter,
    handleFilterChipClick: handleFilterChipClick,
    submitSelectedFeedback: submitSelectedFeedback,
    queueSelectedPaper: queueSelectedPaper,
    collectSelectedPaper: collectSelectedPaper,
    openSelectedPaper: openSelectedPaper,
    toggleMoreActions: toggleMoreActions,
    closeMoreActions: closeMoreActions,
    toggleFullExplanation: toggleFullExplanation,
    focusRelativeInboxItem: focusRelativeInboxItem,
    updateProgressUI: updateProgressUI,
    refreshInboxProgress: refreshInboxProgress,
    finishToday: finishToday,
    confirmTriageComplete: confirmTriageComplete
  });
})();
