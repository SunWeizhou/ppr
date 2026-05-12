(function () {
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

  function confirmDangerAction(options) {
    if (options === undefined) options = {};
    const state = window.AppState.modalState;
    document.getElementById('dangerConfirmTitle').textContent = options.title || 'Confirm action';
    document.getElementById('dangerConfirmBody').textContent = options.message || 'This action cannot be automatically undone. Confirm to continue.';
    document.getElementById('dangerConfirmObject').textContent = options.objectName || '';
    document.getElementById('dangerConfirmObject').hidden = !options.objectName;
    document.getElementById('dangerConfirmButton').textContent = options.confirmLabel || 'Confirm';
    openModal('dangerConfirmModal');
    return new Promise(function (resolve) {
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
      title: 'Refresh Inbox candidates',
      objectName: 'Today scoring cache',
      message: 'This reruns candidate generation and may update Inbox ordering. Queue, reading, and feedback state are preserved.',
      confirmLabel: 'Refresh today'
    });
    if (ok) {
      try {
        const resp = await fetch('/api/refresh?force=1', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
          showToast('Refresh started');
          setTimeout(() => window.location.reload(), 1500);
        } else {
          showToast(data.error || 'Refresh failed', 'error');
        }
      } catch (err) {
        showToast('Refresh failed: ' + err.message, 'error');
      }
    }
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    ['collectionPickerModal', 'collectionEditorModal', 'querySubscriptionModal', 'authorSubscriptionModal', 'dangerConfirmModal', 'paperActionsModal'].forEach(function (modalId) {
      const modal = document.getElementById(modalId);
      if (modal && !modal.hidden) closeModal(modalId);
    });
  });

  Object.assign(window, {
    hideModal: hideModal,
    openModal: openModal,
    closeModal: closeModal,
    confirmDangerAction: confirmDangerAction,
    submitDangerConfirm: submitDangerConfirm,
    confirmRefreshToday: confirmRefreshToday
  });
})();
