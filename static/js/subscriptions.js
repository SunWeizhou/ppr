(function () {
  function openQuerySubscriptionModal(options) {
    if (options === undefined) options = {};
    const state = window.AppState.modalState;
    state.querySubscriptionTarget = options.savedSearch || null;
    document.getElementById('querySubscriptionTitle').textContent = options.savedSearch ? 'Edit topic watch' : 'Save topic watch';
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
      showToast('Enter a name and query', 'error');
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
      showToast('Topic watch updated');
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
      showToast('Topic watch created');
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
      title: 'Delete topic watch',
      objectName: target.name,
      message: 'This stops long-term tracking for the topic, but does not delete papers already sent to the queue or collections.',
      confirmLabel: 'Delete subscription'
    });
    if (!ok) return;
    await requestJson('/api/saved-searches', {
      method: 'DELETE',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({search_id: target.id})
    });
    removeSavedSearchCache(target.id);
    showToast('Topic watch deleted');
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
    document.getElementById('authorSubscriptionTitle').textContent = author ? 'Edit followed author' : 'Follow author';
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
      showToast('Enter an author name', 'error');
      return;
    }

    const endpoint = state.authorSubscriptionTarget?.name ? '/api/scholars/update' : '/api/scholars/add';
    const result = await requestJson(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    showToast(state.authorSubscriptionTarget?.name ? 'Followed author updated' : 'Author followed');
    state.authorSubscriptionResolver = null;
    hideModal('authorSubscriptionModal');
    resolver(result.scholar || result.result || payload);
  }

  async function deleteAuthorSubscriptionFromEditor() {
    const state = window.AppState.modalState;
    const target = state.authorSubscriptionTarget;
    if (!target?.name) return;
    const ok = await confirmDangerAction({
      title: 'Remove followed author',
      objectName: target.name,
      message: 'This stops tracking the author in Watch, but does not delete saved papers, queue state, or history.',
      confirmLabel: 'Remove author'
    });
    if (!ok) return;
    await requestJson('/api/scholars/remove', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: target.name})
    });
    showToast('Followed author removed');
    const resolver = state.authorSubscriptionResolver;
    state.authorSubscriptionResolver = null;
    hideModal('authorSubscriptionModal');
    if (typeof resolver === 'function') resolver({deleted: true, name: target.name});
  }

  function openVenueSubscriptionModal(options) {
    if (typeof window.showToast === 'function') {
      window.showToast('Venue watches are coming soon', 'info');
    }
  }

  async function runSubscription(subId) {
    try {
      var resp = await fetch('/api/subscriptions/' + subId + '/run', {method: 'POST'});
      var data = await resp.json();
      if (data.success) {
        if (typeof window.showToast === 'function') window.showToast('Refresh complete');
        setTimeout(function(){ location.reload(); }, 1500);
      } else {
        if (typeof window.showToast === 'function') window.showToast('Refresh failed: ' + (data.error || 'unknown'), 'error');
      }
    } catch(e) {
      if (typeof window.showToast === 'function') window.showToast('Refresh failed', 'error');
    }
  }

  async function runAllSubscriptions() {
    try {
      var resp = await fetch('/api/subscriptions/run-all', {method: 'POST'});
      var data = await resp.json();
      if (data.success) {
        if (typeof window.showToast === 'function') window.showToast('All refresh jobs started');
        setTimeout(function(){ location.reload(); }, 1500);
      } else {
        if (typeof window.showToast === 'function') window.showToast('Refresh failed: ' + (data.error || 'unknown'), 'error');
      }
    } catch(e) {
      if (typeof window.showToast === 'function') window.showToast('Refresh failed', 'error');
    }
  }

  function updateHitRow(button, statusLabel) {
    var row = button && button.closest ? button.closest('[data-hit-id]') : null;
    if (!row) return;
    row.setAttribute('data-hit-status', statusLabel);
    var chip = row.querySelector('.js-hit-status');
    if (chip) chip.textContent = statusLabel;
    // Disable the clicked button; for sent_to_inbox also disable Inbox
    var inboxBtns = row.querySelectorAll('button');
    inboxBtns.forEach(function(btn) {
      if (statusLabel === 'sent_to_inbox' && btn.textContent.trim() === 'Inbox') {
        btn.disabled = true;
      } else if (btn === button) {
        btn.disabled = true;
      }
    });
    // Update subscription card stats (search sibling cards)
    var subCard = row.closest('.watch-sub-card');
    if (subCard && statusLabel === 'sent_to_inbox') {
      var undecidedChip = subCard.querySelector('.chip:first-child');
      if (undecidedChip && undecidedChip.textContent.indexOf('Inbox') > -1) {
        var match = undecidedChip.textContent.match(/(\d+)/);
        if (match) {
          var val = parseInt(match[1], 10);
          if (val > 0) undecidedChip.textContent = (val - 1) + ' Inbox';
        }
      }
    }
  }

  async function sendHitToInbox(hitId, button) {
    try {
      var resp = await fetch('/api/subscription-hits/' + hitId + '/send-to-inbox', {
        method: 'POST'
      });
      var data = await resp.json();
      if (data.success) {
        updateHitRow(button, 'sent_to_inbox');
        if (typeof window.showToast === 'function') window.showToast('Added to Inbox');
      } else if (typeof window.showToast === 'function') {
        window.showToast('Failed to add to Inbox', 'error');
      }
    } catch(e) {
      if (typeof window.showToast === 'function') window.showToast('Failed to add to Inbox', 'error');
    }
  }

  async function ignoreSubscriptionHit(hitId, button) {
    try {
      var resp = await fetch('/api/subscription-hits/' + hitId + '/ignore', {
        method: 'POST'
      });
      var data = await resp.json();
      if (data.success) {
        updateHitRow(button, 'ignored');
        if (typeof window.showToast === 'function') window.showToast('Ignored');
      } else if (typeof window.showToast === 'function') {
        window.showToast('Ignore failed', 'error');
      }
    } catch(e) {
      if (typeof window.showToast === 'function') window.showToast('Ignore failed', 'error');
    }
  }

  async function createCollectionFromHit(paperId, title) {
    var safeTitle = title || paperId || 'Watch hit';
    try {
      var created = await fetch('/api/collections', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: safeTitle.slice(0, 72),
          description: 'Created from Watch',
          query_text: safeTitle
        })
      });
      var data = await created.json();
      if (!data.success) throw new Error(data.error || 'Collection creation failed');
      var collectionId = data.collection.id;
      var added = await fetch('/api/collections/' + collectionId + '/papers', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper_id: paperId, source: 'watch'})
      });
      var addData = await added.json();
      if (!addData.success) throw new Error(addData.error || 'Add paper failed');
      if (typeof window.showToast === 'function') window.showToast('Collection created');
    } catch (e) {
      if (typeof window.showToast === 'function') window.showToast('Collection failed: ' + e.message, 'error');
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
    editSubscription: editSubscription,
    sendHitToInbox: sendHitToInbox,
    ignoreSubscriptionHit: ignoreSubscriptionHit,
    createCollectionFromHit: createCollectionFromHit
  });
})();
