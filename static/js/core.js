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

  window.I18N = {
    zh: {
      'brand.sub': 'Local-first research workspace',
      'nav.workflow': 'Workflow',
      'nav.search': 'Search',
      'nav.recommendations': 'Recommendations',
      'nav.reading': 'Reading',
      'nav.watch': 'Watch',
      'state.relevant': 'Relevant',
      'asset.collections': 'collections',
      'asset.queries': 'queries',
      'footer.quote': ''
    },
    en: {
      'brand.sub': 'local-first paper workflow for researchers',
      'nav.workflow': 'Workflow',
      'nav.search': 'Search',
      'nav.reading': 'Reading',
      'nav.watch': 'Watch',
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

  function escapeAttrValue(value) {
    return String(value || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function getFieldValue(id, defaultValue) {
    const el = document.getElementById(id);
    return el != null ? el.value : defaultValue;
  }

  function getFieldChecked(id, defaultValue) {
    const el = document.getElementById(id);
    return el != null ? el.checked : defaultValue;
  }

  function showToast(message, kind) {
    if (kind === undefined) kind = 'success';
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = kind === 'error' ? 'toast visible error' : 'toast visible';
    window.clearTimeout(window.__toastTimer);
    window.__toastTimer = window.setTimeout(function () {
      toast.className = kind === 'error' ? 'toast error' : 'toast';
    }, 2200);
  }

  async function requestJson(url, options) {
    if (options === undefined) options = {};
    const response = await fetch(url, options);
    const result = await response.json().catch(function () { return {}; });
    if (!response.ok || result.success === false) {
      throw new Error(result.error || result.message || 'request failed');
    }
    return result;
  }

  function updateCollectionCache(collection) {
    if (!collection || !collection.id) return;
    const current = Array.isArray(window.AppState.collections) ? window.AppState.collections : [];
    const next = current.filter(function (item) { return item.id !== collection.id; });
    next.push(collection);
    next.sort(function (a, b) { return String(b.updated_at || '').localeCompare(String(a.updated_at || '')); });
    window.AppState.collections = next;
  }

  function removeCollectionCache(collectionId) {
    window.AppState.collections = (window.AppState.collections || []).filter(function (item) { return item.id !== collectionId; });
  }

  function updateSavedSearchCache(savedSearch) {
    if (!savedSearch || !savedSearch.id) return;
    const current = Array.isArray(window.AppState.savedSearches) ? window.AppState.savedSearches : [];
    const next = current.filter(function (item) { return item.id !== savedSearch.id; });
    next.push(savedSearch);
    next.sort(function (a, b) { return String(b.updated_at || '').localeCompare(String(a.updated_at || '')); });
    window.AppState.savedSearches = next;
  }

  function removeSavedSearchCache(searchId) {
    window.AppState.savedSearches = (window.AppState.savedSearches || []).filter(function (item) { return item.id !== searchId; });
  }

  Object.assign(window, {
    escapeHtml: escapeHtml,
    showToast: showToast,
    escapeAttrValue: escapeAttrValue,
    requestJson: requestJson,
    getFieldValue: getFieldValue,
    getFieldChecked: getFieldChecked,
    updateCollectionCache: updateCollectionCache,
    removeCollectionCache: removeCollectionCache,
    updateSavedSearchCache: updateSavedSearchCache,
    removeSavedSearchCache: removeSavedSearchCache
  });
})();
