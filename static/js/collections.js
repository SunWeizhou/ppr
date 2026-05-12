(function () {
  function renderCollectionPickerList() {
    const container = document.getElementById('collectionPickerList');
    if (!container) return;
    container.innerHTML = '';
    const collections = window.AppState.collections || [];
    if (!collections.length) {
      container.innerHTML = '<div class="empty-state compact-empty"><p class="muted-copy">No collections yet. Create one when you need a durable research asset.</p></div>';
      return;
    }
    collections.forEach(function (collection, index) {
      const label = document.createElement('label');
      label.className = 'list-item list-item-selectable';
      label.innerHTML =
        '<span class="selection-check">' +
          '<input type="radio" name="collectionPickerExisting" value="' + escapeHtml(collection.id) + '" ' + (index === 0 ? 'checked' : '') + '>' +
          '<span>' +
            '<span class="list-item-title">' + escapeHtml(collection.name) + '</span>' +
            '<span class="list-item-subtitle">' + escapeHtml(collection.description || collection.seed_query || 'No description yet') + '</span>' +
          '</span>' +
        '</span>' +
        '<span class="list-item-trailing">' + Number(collection.paper_count || 0) + '</span>';
      container.appendChild(label);
    });
  }

  function toggleCollectionCreateNew() {
    const checked = Boolean(document.getElementById('collectionCreateNewToggle')?.checked);
    const fieldset = document.getElementById('collectionPickerNewFields');
    if (fieldset) fieldset.hidden = !checked;
    document.querySelectorAll('input[name="collectionPickerExisting"]').forEach(function (input) {
      input.disabled = checked;
    });
  }

  function openCollectionPicker(options) {
    if (options === undefined) options = {};
    const state = window.AppState.modalState;
    state.collectionPickerOptions = options;
    renderCollectionPickerList();
    document.getElementById('collectionCreateNewToggle').checked = !(window.AppState.collections || []).length;
    document.getElementById('collectionPickerName').value = options.defaultName || '';
    document.getElementById('collectionPickerDescription').value = options.description || '';
    document.getElementById('collectionPickerSeedQuery').value = options.queryText || '';
    toggleCollectionCreateNew();
    openModal('collectionPickerModal');
    return new Promise(function (resolve) {
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
        showToast('Enter a collection name', 'error');
        return;
      }
      const result = await requestJson('/api/collections', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, description: description, seed_query: seedQuery})
      });
      collection = result.collection;
      updateCollectionCache(collection);
      showToast('Collection created');
    } else {
      const selected = document.querySelector('input[name="collectionPickerExisting"]:checked');
      if (!selected) {
        showToast('Select a collection', 'error');
        return;
      }
      collection = (window.AppState.collections || []).find(function (item) { return String(item.id) === String(selected.value); });
    }

    state.collectionPickerResolver = null;
    hideModal('collectionPickerModal');
    resolver(collection || null);
  }

  async function ensureCollection(options) {
    if (options === undefined) options = {};
    return openCollectionPicker(options);
  }

  function openCollectionEditor(options) {
    if (options === undefined) options = {};
    const state = window.AppState.modalState;
    state.collectionEditTarget = options.collection || null;
    document.getElementById('collectionEditorTitle').textContent = options.collection ? 'Edit collection' : 'New collection';
    document.getElementById('collectionEditorName').value = options.collection?.name || options.defaultName || '';
    document.getElementById('collectionEditorDescription').value = options.collection?.description || options.description || '';
    document.getElementById('collectionEditorSeedQuery').value = options.collection?.seed_query || options.collection?.query_text || options.seedQuery || '';
    const dangerZone = document.getElementById('collectionEditorDanger');
    if (dangerZone) dangerZone.hidden = !options.collection?.id;
    openModal('collectionEditorModal');
    return new Promise(function (resolve) {
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
      showToast('Enter a collection name', 'error');
      return;
    }

    const payload = {name: name, description: description, seed_query: seedQuery};
    let result;
    if (state.collectionEditTarget?.id) {
      result = await requestJson('/api/collections', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({collection_id: state.collectionEditTarget.id, ...payload})
      });
      showToast('Collection updated');
    } else {
      result = await requestJson('/api/collections', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      showToast('Collection created');
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
      title: 'Delete collection',
      objectName: target.name,
      message: 'This removes the research container and its paper links, but does not delete papers, queue state, or history.',
      confirmLabel: 'Delete collection'
    });
    if (!ok) return;
    await requestJson('/api/collections', {
      method: 'DELETE',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({collection_id: target.id})
    });
    removeCollectionCache(target.id);
    showToast('Collection deleted');
    const resolver = state.collectionEditorResolver;
    state.collectionEditorResolver = null;
    hideModal('collectionEditorModal');
    if (typeof resolver === 'function') resolver({deleted: true, id: target.id});
  }

  async function addPaperToCollection(paperId, options) {
    if (options === undefined) options = {};
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
    showToast('Added to collection: ' + collection.name);
    return collection;
  }

  Object.assign(window, {
    renderCollectionPickerList: renderCollectionPickerList,
    toggleCollectionCreateNew: toggleCollectionCreateNew,
    openCollectionPicker: openCollectionPicker,
    submitCollectionPicker: submitCollectionPicker,
    ensureCollection: ensureCollection,
    openCollectionEditor: openCollectionEditor,
    submitCollectionEditor: submitCollectionEditor,
    deleteCollectionFromEditor: deleteCollectionFromEditor,
    addPaperToCollection: addPaperToCollection
  });
})();
