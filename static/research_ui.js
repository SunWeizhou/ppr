(function () {
  const stateNode = document.getElementById('appStateJson');
  let initialState = {};
  try {
    initialState = stateNode ? JSON.parse(stateNode.textContent || '{}') : {};
  } catch (error) {
    console.debug('Failed to parse app state', error);
  }

  window.AppState = {
    collections: initialState.collections || [],
    savedSearches: initialState.savedSearches || [],
    queueStatuses: initialState.queueStatuses || [],
    latestJob: initialState.latestJob || {},
    modalState: {
      collectionPickerResolver: null,
      collectionEditorResolver: null,
      querySubscriptionResolver: null,
      authorSubscriptionResolver: null,
      dangerResolver: null,
      collectionEditTarget: null,
      collectionPickerOptions: {},
      querySubscriptionTarget: null,
      authorSubscriptionTarget: null,
      paperActionTarget: null
    }
  };

  const I18N = {
    zh: {
      'brand.sub': '统计研究者的本地 arXiv 工作台',
      'nav.workflow': '工作流',
      'nav.inbox': 'Inbox',
      'nav.queue': 'Queue',
      'nav.library': 'Library',
      'nav.monitor': 'Monitor',
      'nav.settings': 'Settings',
      'state.relevant': 'Relevant',
      'asset.collections': 'collections',
      'asset.queries': 'queries',
      'footer.quote': '“好的研究不是读得更多，而是更早看清什么值得读。”'
    },
    en: {
      'brand.sub': 'local-first arXiv workflow for statistics researchers',
      'nav.workflow': 'Workflow',
      'nav.inbox': 'Inbox',
      'nav.queue': 'Queue',
      'nav.library': 'Library',
      'nav.monitor': 'Monitor',
      'nav.settings': 'Settings',
      'state.relevant': 'Relevant',
      'asset.collections': 'collections',
      'asset.queries': 'queries',
      'footer.quote': '“The art of doing research is the art of making hard choices visible.”'
    }
  };

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getFieldValue(id, defaultValue) {
    const el = document.getElementById(id);
    return el != null ? el.value : defaultValue;
  }

  function getFieldChecked(id, defaultValue) {
    const el = document.getElementById(id);
    return el != null ? el.checked : defaultValue;
  }

  function showToast(message, kind = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = kind === 'error' ? 'toast visible error' : 'toast visible';
    window.clearTimeout(window.__toastTimer);
    window.__toastTimer = window.setTimeout(() => {
      toast.className = kind === 'error' ? 'toast error' : 'toast';
    }, 2200);
  }

  function escapeAttrValue(value) {
    return String(value || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.success === false) {
      throw new Error(result.error || result.message || 'request failed');
    }
    return result;
  }

  function updateCollectionCache(collection) {
    if (!collection || !collection.id) return;
    const current = Array.isArray(window.AppState.collections) ? window.AppState.collections : [];
    const next = current.filter((item) => item.id !== collection.id);
    next.push(collection);
    next.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
    window.AppState.collections = next;
  }

  function removeCollectionCache(collectionId) {
    window.AppState.collections = (window.AppState.collections || []).filter((item) => item.id !== collectionId);
  }

  function updateSavedSearchCache(savedSearch) {
    if (!savedSearch || !savedSearch.id) return;
    const current = Array.isArray(window.AppState.savedSearches) ? window.AppState.savedSearches : [];
    const next = current.filter((item) => item.id !== savedSearch.id);
    next.push(savedSearch);
    next.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
    window.AppState.savedSearches = next;
  }

  function removeSavedSearchCache(searchId) {
    window.AppState.savedSearches = (window.AppState.savedSearches || []).filter((item) => item.id !== searchId);
  }

  function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.hidden = true;
    if (!document.querySelector('.modal-shell:not([hidden])')) {
      document.body.classList.remove('modal-open');
    }
  }

  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.hidden = false;
    document.body.classList.add('modal-open');
  }

  function closeModal(modalId) {
    hideModal(modalId);
    const state = window.AppState.modalState;
    if (modalId === 'collectionPickerModal' && typeof state.collectionPickerResolver === 'function') {
      state.collectionPickerResolver(null);
      state.collectionPickerResolver = null;
    }
    if (modalId === 'collectionEditorModal' && typeof state.collectionEditorResolver === 'function') {
      state.collectionEditorResolver(null);
      state.collectionEditorResolver = null;
    }
    if (modalId === 'querySubscriptionModal' && typeof state.querySubscriptionResolver === 'function') {
      state.querySubscriptionResolver(null);
      state.querySubscriptionResolver = null;
    }
    if (modalId === 'authorSubscriptionModal' && typeof state.authorSubscriptionResolver === 'function') {
      state.authorSubscriptionResolver(null);
      state.authorSubscriptionResolver = null;
    }
    if (modalId === 'dangerConfirmModal' && typeof state.dangerResolver === 'function') {
      state.dangerResolver(false);
      state.dangerResolver = null;
    }
  }

  function renderCollectionPickerList() {
    const container = document.getElementById('collectionPickerList');
    if (!container) return;
    container.innerHTML = '';
    const collections = window.AppState.collections || [];
    if (!collections.length) {
      container.innerHTML = '<div class="empty-state compact-empty"><p class="muted-copy">还没有 Collection，直接新建一个。</p></div>';
      return;
    }
    collections.forEach((collection, index) => {
      const label = document.createElement('label');
      label.className = 'list-item list-item-selectable';
      label.innerHTML = `
        <span class="selection-check">
          <input type="radio" name="collectionPickerExisting" value="${escapeHtml(collection.id)}" ${index === 0 ? 'checked' : ''}>
          <span>
            <span class="list-item-title">${escapeHtml(collection.name)}</span>
            <span class="list-item-subtitle">${escapeHtml(collection.description || collection.seed_query || 'No description yet')}</span>
          </span>
        </span>
        <span class="list-item-trailing">${Number(collection.paper_count || 0)}</span>
      `;
      container.appendChild(label);
    });
  }

  function toggleCollectionCreateNew() {
    const checked = Boolean(document.getElementById('collectionCreateNewToggle')?.checked);
    const fieldset = document.getElementById('collectionPickerNewFields');
    if (fieldset) fieldset.hidden = !checked;
    document.querySelectorAll('input[name="collectionPickerExisting"]').forEach((input) => {
      input.disabled = checked;
    });
  }

  function openCollectionPicker(options = {}) {
    const state = window.AppState.modalState;
    state.collectionPickerOptions = options;
    renderCollectionPickerList();
    document.getElementById('collectionCreateNewToggle').checked = !(window.AppState.collections || []).length;
    document.getElementById('collectionPickerName').value = options.defaultName || '';
    document.getElementById('collectionPickerDescription').value = options.description || '';
    document.getElementById('collectionPickerSeedQuery').value = options.queryText || '';
    toggleCollectionCreateNew();
    openModal('collectionPickerModal');
    return new Promise((resolve) => {
      state.collectionPickerResolver = resolve;
    });
  }

  async function submitCollectionPicker() {
    const state = window.AppState.modalState;
    const resolver = state.collectionPickerResolver;
    if (typeof resolver !== 'function') return;

    const creatingNew = Boolean(document.getElementById('collectionCreateNewToggle')?.checked);
    let collection = null;

    if (creatingNew) {
      const name = document.getElementById('collectionPickerName').value.trim();
      const description = document.getElementById('collectionPickerDescription').value.trim();
      const seedQuery = document.getElementById('collectionPickerSeedQuery').value.trim();
      if (!name) {
        showToast('请填写 Collection 名称', 'error');
        return;
      }
      const result = await requestJson('/api/collections', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, description, seed_query: seedQuery})
      });
      collection = result.collection;
      updateCollectionCache(collection);
      showToast('Collection 已创建');
    } else {
      const selected = document.querySelector('input[name="collectionPickerExisting"]:checked');
      if (!selected) {
        showToast('请选择一个 Collection', 'error');
        return;
      }
      collection = (window.AppState.collections || []).find((item) => String(item.id) === String(selected.value));
    }

    state.collectionPickerResolver = null;
    hideModal('collectionPickerModal');
    resolver(collection || null);
  }

  async function ensureCollection(options = {}) {
    return openCollectionPicker(options);
  }

  function openCollectionEditor(options = {}) {
    const state = window.AppState.modalState;
    state.collectionEditTarget = options.collection || null;
    document.getElementById('collectionEditorTitle').textContent = options.collection ? '编辑 Collection' : '新建 Collection';
    document.getElementById('collectionEditorName').value = options.collection?.name || options.defaultName || '';
    document.getElementById('collectionEditorDescription').value = options.collection?.description || options.description || '';
    document.getElementById('collectionEditorSeedQuery').value = options.collection?.seed_query || options.collection?.query_text || options.seedQuery || '';
    const dangerZone = document.getElementById('collectionEditorDanger');
    if (dangerZone) dangerZone.hidden = !options.collection?.id;
    openModal('collectionEditorModal');
    return new Promise((resolve) => {
      state.collectionEditorResolver = resolve;
    });
  }

  async function submitCollectionEditor() {
    const state = window.AppState.modalState;
    const resolver = state.collectionEditorResolver;
    if (typeof resolver !== 'function') return;

    const name = document.getElementById('collectionEditorName').value.trim();
    const description = document.getElementById('collectionEditorDescription').value.trim();
    const seedQuery = document.getElementById('collectionEditorSeedQuery').value.trim();
    if (!name) {
      showToast('请填写 Collection 名称', 'error');
      return;
    }

    const payload = {name, description, seed_query: seedQuery};
    let result;
    if (state.collectionEditTarget?.id) {
      result = await requestJson('/api/collections', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({collection_id: state.collectionEditTarget.id, ...payload})
      });
      showToast('Collection 已更新');
    } else {
      result = await requestJson('/api/collections', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      showToast('Collection 已创建');
    }
    const collection = result.collection;
    updateCollectionCache(collection);
    state.collectionEditorResolver = null;
    hideModal('collectionEditorModal');
    resolver(collection);
  }

  async function deleteCollectionFromEditor() {
    const state = window.AppState.modalState;
    const target = state.collectionEditTarget;
    if (!target?.id) return;
    const ok = await confirmDangerAction({
      title: '删除 Collection',
      objectName: target.name,
      message: '这会删除这个研究容器及其中的收纳关系，但不会删除论文、Queue 状态或历史记录。',
      confirmLabel: 'Delete collection'
    });
    if (!ok) return;
    await requestJson('/api/collections', {
      method: 'DELETE',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({collection_id: target.id})
    });
    removeCollectionCache(target.id);
    showToast('Collection 已删除');
    const resolver = state.collectionEditorResolver;
    state.collectionEditorResolver = null;
    hideModal('collectionEditorModal');
    if (typeof resolver === 'function') resolver({deleted: true, id: target.id});
  }

  async function addPaperToCollection(paperId, options = {}) {
    const collection = await ensureCollection(options);
    if (!collection) return null;
    await requestJson('/api/collections/' + collection.id + '/papers', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        paper_id: paperId,
        note: options.note || '',
        source: options.source || 'research_ui'
      })
    });
    showToast('已加入 Collection: ' + collection.name);
    return collection;
  }

  function openQuerySubscriptionModal(options = {}) {
    const state = window.AppState.modalState;
    state.querySubscriptionTarget = options.savedSearch || null;
    document.getElementById('querySubscriptionTitle').textContent = options.savedSearch ? '编辑问题订阅' : '保存问题订阅';
    document.getElementById('querySubscriptionName').value = options.savedSearch?.name || options.defaultName || '';
    document.getElementById('querySubscriptionQuery').value = options.savedSearch?.query_text || options.queryText || '';
    document.getElementById('querySubscriptionDescription').value = options.savedSearch?.description || options.description || '';
    const dangerZone = document.getElementById('querySubscriptionDanger');
    if (dangerZone) dangerZone.hidden = !options.savedSearch?.id;
    openModal('querySubscriptionModal');
    return new Promise((resolve) => {
      state.querySubscriptionResolver = resolve;
    });
  }

  async function submitQuerySubscription() {
    const state = window.AppState.modalState;
    const resolver = state.querySubscriptionResolver;
    if (typeof resolver !== 'function') return;
    const name = document.getElementById('querySubscriptionName').value.trim();
    const queryText = document.getElementById('querySubscriptionQuery').value.trim();
    const description = document.getElementById('querySubscriptionDescription').value.trim();
    if (!name || !queryText) {
      showToast('请填写名称和 Query', 'error');
      return;
    }

    const existingFilters = state.querySubscriptionTarget?.filters_json;
    const safeFilters = existingFilters && typeof existingFilters === 'object' && !Array.isArray(existingFilters)
      ? existingFilters
      : {};
    let result;
    if (state.querySubscriptionTarget?.id) {
      result = await requestJson('/api/saved-searches', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          search_id: state.querySubscriptionTarget.id,
          name,
          query_text: queryText,
          description,
          filters: {
            ...safeFilters,
            source: 'query_subscription_modal'
          }
        })
      });
      showToast('问题订阅已更新');
    } else {
      result = await requestJson('/api/saved-searches', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name,
          query_text: queryText,
          description,
          filters: {source: 'query_subscription_modal'}
        })
      });
      showToast('问题订阅已创建');
    }
    const savedSearch = result.saved_search;
    updateSavedSearchCache(savedSearch);
    state.querySubscriptionResolver = null;
    hideModal('querySubscriptionModal');
    resolver(savedSearch);
  }

  async function deleteQuerySubscriptionFromEditor() {
    const state = window.AppState.modalState;
    const target = state.querySubscriptionTarget;
    if (!target?.id) return;
    const ok = await confirmDangerAction({
      title: '删除 Query Subscription',
      objectName: target.name,
      message: '这会停止这个问题的长期命中追踪，但不会删除已经加入 Queue 或 Collection 的论文。',
      confirmLabel: 'Delete subscription'
    });
    if (!ok) return;
    await requestJson('/api/saved-searches', {
      method: 'DELETE',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({search_id: target.id})
    });
    removeSavedSearchCache(target.id);
    showToast('问题订阅已删除');
    const resolver = state.querySubscriptionResolver;
    state.querySubscriptionResolver = null;
    hideModal('querySubscriptionModal');
    if (typeof resolver === 'function') resolver({deleted: true, id: target.id});
  }

  function openAuthorSubscriptionModal(options = {}) {
    const state = window.AppState.modalState;
    const author = options.author || null;
    state.authorSubscriptionTarget = author;
    document.getElementById('authorSubscriptionTitle').textContent = author ? '编辑关注学者' : '关注学者';
    document.getElementById('authorSubscriptionName').value = author?.name || options.defaultName || '';
    document.getElementById('authorSubscriptionAffiliation').value = author?.affiliation || '';
    document.getElementById('authorSubscriptionFocus').value = author?.focus || '';
    document.getElementById('authorSubscriptionArxiv').value = author?.arxiv || author?.arxiv_query || '';
    document.getElementById('authorSubscriptionScholar').value = author?.google_scholar || '';
    document.getElementById('authorSubscriptionWebsite').value = author?.website || '';
    const dangerZone = document.getElementById('authorSubscriptionDanger');
    if (dangerZone) dangerZone.hidden = !author?.name;
    openModal('authorSubscriptionModal');
    return new Promise((resolve) => {
      state.authorSubscriptionResolver = resolve;
    });
  }

  async function submitAuthorSubscription() {
    const state = window.AppState.modalState;
    const resolver = state.authorSubscriptionResolver;
    if (typeof resolver !== 'function') return;

    const payload = {
      original_name: state.authorSubscriptionTarget?.name || '',
      name: document.getElementById('authorSubscriptionName').value.trim(),
      affiliation: document.getElementById('authorSubscriptionAffiliation').value.trim(),
      focus: document.getElementById('authorSubscriptionFocus').value.trim(),
      arxiv_query: document.getElementById('authorSubscriptionArxiv').value.trim(),
      google_scholar: document.getElementById('authorSubscriptionScholar').value.trim(),
      website: document.getElementById('authorSubscriptionWebsite').value.trim()
    };
    if (!payload.name) {
      showToast('请填写学者姓名', 'error');
      return;
    }

    const endpoint = state.authorSubscriptionTarget?.name ? '/api/scholars/update' : '/api/scholars/add';
    const result = await requestJson(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    showToast(state.authorSubscriptionTarget?.name ? '关注学者已更新' : '关注学者已添加');
    state.authorSubscriptionResolver = null;
    hideModal('authorSubscriptionModal');
    resolver(result.scholar || result.result || payload);
  }

  async function deleteAuthorSubscriptionFromEditor() {
    const state = window.AppState.modalState;
    const target = state.authorSubscriptionTarget;
    if (!target?.name) return;
    const ok = await confirmDangerAction({
      title: '移除关注学者',
      objectName: target.name,
      message: '这会停止在 Monitor 中追踪该学者，但不会删除已保存论文、Queue 状态或历史记录。',
      confirmLabel: 'Remove author'
    });
    if (!ok) return;
    await requestJson('/api/scholars/remove', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: target.name})
    });
    showToast('关注学者已移除');
    const resolver = state.authorSubscriptionResolver;
    state.authorSubscriptionResolver = null;
    hideModal('authorSubscriptionModal');
    if (typeof resolver === 'function') resolver({deleted: true, name: target.name});
  }

  async function queuePaperStatus(paperId, status, options = {}) {
    const result = await requestJson('/api/queue', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        paper_id: paperId,
        status,
        source: options.source || 'research_ui',
        note: options.note,
        tags: options.tags
      })
    });
    syncPaperState(paperId, status, result.item?.note || '');
    showToast('已加入队列: ' + status);
    return result.item;
  }

  function syncPaperState(paperId, status, note = null) {
    const selector = '[data-paper-id="' + escapeAttrValue(paperId) + '"]';
    document.querySelectorAll(selector).forEach((node) => {
      node.dataset.queueStatus = status || '';
      if (note !== null) node.dataset.queueNote = note || '';
      node.querySelectorAll('[data-queue-state]').forEach((chip) => {
        chip.textContent = status || '';
        chip.hidden = !status;
        const normalized = String(status || '')
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-+|-+$/g, '');
        chip.className = normalized ? 'state-chip status-' + normalized : 'state-chip';
      });
    });
  }

  async function followAuthor(author, options = {}) {
    if (!author) {
      showToast('缺少作者名', 'error');
      return null;
    }
    const result = await requestJson('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        paper_id: options.paperId || author,
        action: 'follow_author',
        author,
        title: options.title || '',
        source: options.source || 'research_ui'
      })
    });
    showToast(result.followed ? ('已关注作者: ' + author) : result.result || '作者已存在');
    return result;
  }

  function downloadBibtex(paperId) {
    window.open('/api/export/bibtex/' + encodeURIComponent(paperId), '_blank');
  }

  async function trackPaperOpen(paperId, source = 'research_ui') {
    try {
      await requestJson('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper_id: paperId, action: 'open_paper', source})
      });
    } catch (error) {
      console.debug(error);
    }
  }

  function confirmDangerAction(options = {}) {
    const state = window.AppState.modalState;
    document.getElementById('dangerConfirmTitle').textContent = options.title || '确认危险操作';
    document.getElementById('dangerConfirmBody').textContent = options.message || '这个操作无法自动恢复，请确认后继续。';
    document.getElementById('dangerConfirmObject').textContent = options.objectName || '';
    document.getElementById('dangerConfirmObject').hidden = !options.objectName;
    document.getElementById('dangerConfirmButton').textContent = options.confirmLabel || 'Confirm';
    openModal('dangerConfirmModal');
    return new Promise((resolve) => {
      state.dangerResolver = resolve;
    });
  }

  function submitDangerConfirm() {
    const state = window.AppState.modalState;
    const resolver = state.dangerResolver;
    state.dangerResolver = null;
    hideModal('dangerConfirmModal');
    if (typeof resolver === 'function') resolver(true);
  }

  async function confirmRefreshToday() {
    const ok = await confirmDangerAction({
      title: '刷新今日推荐',
      objectName: 'Today scoring cache',
      message: '这会重新运行今日推荐生成，可能覆盖当前今日排序快照。Queue、Collection 和反馈状态会保留。',
      confirmLabel: 'Refresh today'
    });
    if (ok) window.location.href = '/api/refresh?force=1';
  }

  function getPaperNode(element) {
    return element?.closest ? element.closest('[data-paper-id]') : null;
  }

  function openPaperActions(trigger, source = 'research_ui') {
    const card = getPaperNode(trigger);
    if (!card) return;
    const target = {
      paperId: card.dataset.paperId,
      title: card.dataset.paperTitle || '',
      authors: card.dataset.paperAuthors || '',
      link: card.dataset.paperLink || '',
      firstAuthor: card.dataset.paperFirstAuthor || '',
      collectionId: card.dataset.collectionId || '',
      source
    };
    window.AppState.modalState.paperActionTarget = target;
    document.getElementById('paperActionsTitle').textContent = target.title || 'Paper actions';
    document.getElementById('paperActionsMeta').textContent = target.authors || 'Choose the next operation for this paper.';
    const openLink = document.getElementById('paperActionOpenLink');
    if (openLink) openLink.href = target.link || '#';
    const removeButton = document.getElementById('paperActionRemoveCollection');
    if (removeButton) removeButton.hidden = !target.collectionId;
    openModal('paperActionsModal');
  }

  function paperActionOpen(event) {
    if (event) event.preventDefault();
    const target = window.AppState.modalState.paperActionTarget;
    if (!target) return;
    if (target.link) window.open(target.link, '_blank');
    trackPaperOpen(target.paperId, target.source || 'paper_actions');
  }

  async function paperActionQueue(status) {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target) return;
    try {
      await queuePaperStatus(target.paperId, status, {source: target.source || 'paper_actions'});
    } catch (error) {
      showToast('队列更新失败: ' + error.message, 'error');
    }
  }

  async function paperActionCollect() {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target) return;
    try {
      await addPaperToCollection(target.paperId, {
        defaultName: target.title.slice(0, 48),
        source: target.source || 'paper_actions'
      });
    } catch (error) {
      showToast('加入 Collection 失败: ' + error.message, 'error');
    }
  }

  function paperActionPdf() {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target) return;
    window.open('/api/pdf/' + encodeURIComponent(target.paperId), '_blank');
  }

  function paperActionBibtex() {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target) return;
    downloadBibtex(target.paperId);
  }

  async function paperActionFollow() {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target) return;
    try {
      await followAuthor(target.firstAuthor, {
        paperId: target.paperId,
        title: target.title,
        source: target.source || 'paper_actions'
      });
    } catch (error) {
      showToast('关注失败: ' + error.message, 'error');
    }
  }

  async function paperActionRemoveFromCollection() {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target?.collectionId) return;
    const ok = await confirmDangerAction({
      title: '移出 Collection',
      objectName: target.title,
      message: '这只会移除当前论文与这个 Collection 的关系，不会删除论文或其他状态。',
      confirmLabel: 'Remove paper'
    });
    if (!ok) return;
    try {
      await requestJson('/api/collections/' + target.collectionId + '/papers', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper_id: target.paperId, source: target.source || 'paper_actions'})
      });
      showToast('已移出 Collection');
      document.querySelectorAll('[data-paper-id="' + escapeAttrValue(target.paperId) + '"][data-collection-id="' + escapeAttrValue(target.collectionId) + '"]').forEach((node) => node.remove());
      hideModal('paperActionsModal');
    } catch (error) {
      showToast('移除失败: ' + error.message, 'error');
    }
  }

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    ['collectionPickerModal', 'collectionEditorModal', 'querySubscriptionModal', 'authorSubscriptionModal', 'dangerConfirmModal', 'paperActionsModal'].forEach((modalId) => {
      const modal = document.getElementById(modalId);
      if (modal && !modal.hidden) closeModal(modalId);
    });
  });

  function applyLanguage(language) {
    const lang = I18N[language] ? language : 'zh';
    document.documentElement.dataset.language = lang;
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    const i18nMap = I18N[lang] || {};
    document.querySelectorAll('[data-i18n], [data-i18n-quote]').forEach((node) => {
      const key = node.dataset.i18n || node.dataset.i18nQuote;
      if (i18nMap[key]) node.textContent = i18nMap[key];
    });
    const languageToggle = document.querySelector('[data-action="toggle-language"]');
    if (languageToggle) languageToggle.textContent = lang === 'zh' ? '中 / EN' : 'EN / 中';
    localStorage.setItem('statdesk.language', lang);
  }

  function applyTheme(theme) {
    const nextTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = nextTheme;
    const themeToggle = document.querySelector('[data-action="toggle-theme"]');
    if (themeToggle) themeToggle.textContent = nextTheme === 'dark' ? 'Light' : 'Dark';
    localStorage.setItem('statdesk.theme', nextTheme);
  }

  function initPreferences() {
    const storedLanguage = localStorage.getItem('statdesk.language') || 'zh';
    const storedTheme = localStorage.getItem('statdesk.theme') || 'light';
    applyLanguage(storedLanguage);
    applyTheme(storedTheme);
    document.querySelector('[data-action="toggle-language"]')?.addEventListener('click', () => {
      applyLanguage(document.documentElement.dataset.language === 'zh' ? 'en' : 'zh');
    });
    document.querySelector('[data-action="toggle-theme"]')?.addEventListener('click', () => {
      applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPreferences);
  } else {
    initPreferences();
  }

  Object.assign(window, {
    showToast,
    escapeAttrValue,
    requestJson,
    getFieldValue,
    getFieldChecked,
    updateCollectionCache,
    removeCollectionCache,
    updateSavedSearchCache,
    removeSavedSearchCache,
    openModal,
    closeModal,
    renderCollectionPickerList,
    toggleCollectionCreateNew,
    openCollectionPicker,
    submitCollectionPicker,
    ensureCollection,
    openCollectionEditor,
    submitCollectionEditor,
    deleteCollectionFromEditor,
    addPaperToCollection,
    openQuerySubscriptionModal,
    submitQuerySubscription,
    deleteQuerySubscriptionFromEditor,
    openAuthorSubscriptionModal,
    submitAuthorSubscription,
    deleteAuthorSubscriptionFromEditor,
    queuePaperStatus,
    syncPaperState,
    followAuthor,
    downloadBibtex,
    trackPaperOpen,
    confirmDangerAction,
    submitDangerConfirm,
    confirmRefreshToday,
    openPaperActions,
    paperActionOpen,
    paperActionQueue,
    paperActionCollect,
    paperActionPdf,
    paperActionBibtex,
    paperActionFollow,
    paperActionRemoveFromCollection
  });
})();
