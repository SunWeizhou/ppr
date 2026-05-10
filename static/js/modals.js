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
    document.getElementById('dangerConfirmTitle').textContent = options.title || '确认危险操作';
    document.getElementById('dangerConfirmBody').textContent = options.message || '这个操作无法自动恢复，请确认后继续。';
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
      title: '刷新 Inbox 候选',
      objectName: 'Today scoring cache',
      message: '这会重新运行候选生成，可能更新当前 Inbox 排序。Queue、Reading 和反馈状态会保留。',
      confirmLabel: 'Refresh today'
    });
    if (ok) {
      try {
        const resp = await fetch('/api/refresh?force=1', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
          showToast('刷新任务已提交');
          setTimeout(() => window.location.reload(), 1500);
        } else {
          showToast(data.error || '刷新失败', 'error');
        }
      } catch (err) {
        showToast('刷新失败: ' + err.message, 'error');
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
