(function () {
  function openQuerySubscriptionModal(options) {
    if (options === undefined) options = {};
    const state = window.AppState.modalState;
    state.querySubscriptionTarget = options.savedSearch || null;
    document.getElementById('querySubscriptionTitle').textContent = options.savedSearch ? '编辑问题订阅' : '保存问题订阅';
    document.getElementById('querySubscriptionName').value = options.savedSearch?.name || options.defaultName || '';
    document.getElementById('querySubscriptionQuery').value = options.savedSearch?.query_text || options.queryText || '';
    document.getElementById('querySubscriptionDescription').value = options.savedSearch?.description || options.description || '';
    const dangerZone = document.getElementById('querySubscriptionDanger');
    if (dangerZone) dangerZone.hidden = !options.savedSearch?.id;
    openModal('querySubscriptionModal');
    return new Promise(function (resolve) {
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
          name: name,
          query_text: queryText,
          description: description,
          filters: Object.assign({}, safeFilters, {source: 'query_subscription_modal'})
        })
      });
      showToast('问题订阅已更新');
    } else {
      result = await requestJson('/api/saved-searches', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: name,
          query_text: queryText,
          description: description,
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

  function openAuthorSubscriptionModal(options) {
    if (options === undefined) options = {};
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
    return new Promise(function (resolve) {
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

  function openVenueSubscriptionModal(options) {
    if (typeof window.showToast === 'function') {
      window.showToast('期刊/会议订阅功能即将上线', 'info');
    }
  }

  async function runSubscription(subId) {
    try {
      var resp = await fetch('/api/subscriptions/' + subId + '/run', {method: 'POST'});
      var data = await resp.json();
      if (data.success) {
        if (typeof window.showToast === 'function') window.showToast('刷新完成');
        setTimeout(function(){ location.reload(); }, 1500);
      } else {
        if (typeof window.showToast === 'function') window.showToast('刷新失败: ' + (data.error || 'unknown'), 'error');
      }
    } catch(e) {
      if (typeof window.showToast === 'function') window.showToast('刷新失败', 'error');
    }
  }

  async function runAllSubscriptions() {
    try {
      var resp = await fetch('/api/subscriptions/run-all', {method: 'POST'});
      var data = await resp.json();
      if (data.success) {
        if (typeof window.showToast === 'function') window.showToast('全部刷新任务已启动');
        setTimeout(function(){ location.reload(); }, 1500);
      } else {
        if (typeof window.showToast === 'function') window.showToast('刷新失败: ' + (data.error || 'unknown'), 'error');
      }
    } catch(e) {
      if (typeof window.showToast === 'function') window.showToast('刷新失败', 'error');
    }
  }

  function editSubscription(subId) {
    window.location.href = '/settings?tab=subscriptions&edit=' + subId;
  }

  Object.assign(window, {
    openQuerySubscriptionModal: openQuerySubscriptionModal,
    createQuerySubscription: openQuerySubscriptionModal,
    submitQuerySubscription: submitQuerySubscription,
    deleteQuerySubscriptionFromEditor: deleteQuerySubscriptionFromEditor,
    openAuthorSubscriptionModal: openAuthorSubscriptionModal,
    createAuthorSubscription: openAuthorSubscriptionModal,
    submitAuthorSubscription: submitAuthorSubscription,
    deleteAuthorSubscriptionFromEditor: deleteAuthorSubscriptionFromEditor,
    openVenueSubscriptionModal: openVenueSubscriptionModal,
    createVenueSubscription: openVenueSubscriptionModal,
    runSubscription: runSubscription,
    runAllSubscriptions: runAllSubscriptions,
    editSubscription: editSubscription
  });
})();
