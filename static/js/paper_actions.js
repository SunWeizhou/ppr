(function () {
  async function queuePaperStatus(paperId, status, options) {
    if (options === undefined) options = {};
    const result = await requestJson('/api/queue', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        paper_id: paperId,
        status: status,
        source: options.source || 'research_ui',
        note: options.note,
        tags: options.tags,
        research_question_id: options.research_question_id,
        decision_context: options.decision_context
      })
    });
    syncPaperState(paperId, status, result.item?.note || '');
    showToast('Added to queue: ' + status);
    return result.item;
  }

  function syncPaperState(paperId, status, note) {
    if (note === undefined) note = null;
    const selector = '[data-paper-id="' + escapeAttrValue(paperId) + '"]';
    document.querySelectorAll(selector).forEach(function (node) {
      node.dataset.queueStatus = status || '';
      if (note !== null) node.dataset.queueNote = note || '';
      node.querySelectorAll('[data-queue-state]').forEach(function (chip) {
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

  async function followAuthor(author, options) {
    if (options === undefined) options = {};
    if (!author) {
      showToast('Missing author name', 'error');
      return null;
    }
    const result = await requestJson('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        paper_id: options.paperId || author,
        action: 'follow_author',
        author: author,
        title: options.title || '',
        source: options.source || 'research_ui'
      })
    });
    showToast(result.followed ? ('Following author: ' + author) : result.result || 'Author already exists');
    return result;
  }

  function downloadBibtex(paperId) {
    window.open('/api/export/bibtex/' + encodeURIComponent(paperId), '_blank');
  }

  async function trackPaperOpen(paperId, source) {
    if (source === undefined) source = 'research_ui';
    try {
      await requestJson('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper_id: paperId, action: 'open_paper', source: source})
      });
    } catch (error) {
      console.debug(error);
    }
  }

  function getPaperNode(element) {
    return element?.closest ? element.closest('[data-paper-id]') : null;
  }

  function openPaperActions(trigger, source) {
    if (source === undefined) source = 'research_ui';
    const card = getPaperNode(trigger);
    if (!card) return;
    const target = {
      paperId: card.dataset.paperId,
      title: card.dataset.paperTitle || '',
      authors: card.dataset.paperAuthors || '',
      link: card.dataset.paperLink || '',
      firstAuthor: card.dataset.paperFirstAuthor || '',
      collectionId: card.dataset.collectionId || '',
      source: source
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
      showToast('Queue update failed: ' + error.message, 'error');
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
      showToast('Add to collection failed: ' + error.message, 'error');
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
      showToast('Follow failed: ' + error.message, 'error');
    }
  }

  async function paperActionRemoveFromCollection() {
    const target = window.AppState.modalState.paperActionTarget;
    if (!target?.collectionId) return;
    const ok = await confirmDangerAction({
      title: 'Remove from collection',
      objectName: target.title,
      message: 'This only removes the link between this paper and the collection. It does not delete the paper or other state.',
      confirmLabel: 'Remove paper'
    });
    if (!ok) return;
    try {
      await requestJson('/api/collections/' + target.collectionId + '/papers', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({paper_id: target.paperId, source: target.source || 'paper_actions'})
      });
      showToast('Removed from collection');
      document.querySelectorAll('[data-paper-id="' + escapeAttrValue(target.paperId) + '"][data-collection-id="' + escapeAttrValue(target.collectionId) + '"]').forEach(function (node) { return node.remove(); });
      hideModal('paperActionsModal');
    } catch (error) {
      showToast('Remove failed: ' + error.message, 'error');
    }
  }

  Object.assign(window, {
    queuePaper: queuePaperStatus,
    queuePaperStatus: queuePaperStatus,
    syncPaperState: syncPaperState,
    followAuthor: followAuthor,
    downloadBibtex: downloadBibtex,
    trackPaperOpen: trackPaperOpen,
    openPaperActions: openPaperActions,
    paperActionOpen: paperActionOpen,
    paperActionQueue: paperActionQueue,
    paperActionCollect: paperActionCollect,
    paperActionPdf: paperActionPdf,
    paperActionBibtex: paperActionBibtex,
    paperActionFollow: paperActionFollow,
    paperActionRemoveFromCollection: paperActionRemoveFromCollection
  });
})();
