/**
 * Shared Browse modal (Anki-like 3-pane browser).
 * Uses server pagination for large datasets and dynamic editor by note type fields.
 */

(() => {
  const modalEl = document.getElementById("browseModal");
  if (!modalEl || typeof window.bootstrap === "undefined") {
    return;
  }

  const unsavedModalEl = document.getElementById("browseUnsavedModal");
  const bulkDeleteModalEl = document.getElementById("browseBulkDeleteModal");
  if (!unsavedModalEl || !bulkDeleteModalEl) {
    return;
  }

  const modalInstance = window.bootstrap.Modal.getOrCreateInstance(modalEl);
  const unsavedModalInstance = window.bootstrap.Modal.getOrCreateInstance(unsavedModalEl);
  const bulkDeleteModalInstance = window.bootstrap.Modal.getOrCreateInstance(bulkDeleteModalEl);

  const els = {
    contextLabel: document.getElementById("browseContextLabel"),
    refreshBtn: document.getElementById("browseRefreshBtn"),
    deckSearch: document.getElementById("browseDeckSearch"),
    includeSubdecks: document.getElementById("browseIncludeSubdecks"),
    treeLoading: document.getElementById("browseTreeLoading"),
    deckTree: document.getElementById("browseDeckTree"),
    shortcutAll: document.querySelector('.browse-shortcut[data-shortcut="all"]'),
    shortcutCurrent: document.getElementById("browseCurrentDeckShortcut"),
    keyword: document.getElementById("browseKeyword"),
    status: document.getElementById("browseStatusFilter"),
    tag: document.getElementById("browseTagFilter"),
    sortBy: document.getElementById("browseSortBy"),
    toggleCheckboxModeBtn: document.getElementById("browseToggleCheckboxMode"),
    bulkDeleteBtn: document.getElementById("browseBulkDeleteBtn"),
    sortDirBtn: document.getElementById("browseSortDirBtn"),
    selectAllHead: document.getElementById("browseSelectAllHead"),
    selectAllCheckbox: document.getElementById("browseSelectAllCheckbox"),
    tableWrap: document.getElementById("browseTableWrap"),
    tableBody: document.getElementById("browseTableBody"),
    rowsLoading: document.getElementById("browseRowsLoading"),
    tableMeta: document.getElementById("browseTableMeta"),
    editorEmpty: document.getElementById("browseEditorEmpty"),
    editorForm: document.getElementById("browseEditorForm"),
    editorDeck: document.getElementById("browseEditorDeck"),
    editorTags: document.getElementById("browseEditorTags"),
    editorFields: document.getElementById("browseEditorFields"),
    saveBtn: document.getElementById("browseSaveBtn"),
    revertBtn: document.getElementById("browseRevertBtn"),
    deleteBtn: document.getElementById("browseDeleteBtn"),
    unsavedCancelBtn: document.getElementById("browseUnsavedCancelBtn"),
    unsavedDiscardBtn: document.getElementById("browseUnsavedDiscardBtn"),
    unsavedSaveBtn: document.getElementById("browseUnsavedSaveBtn"),
    bulkDeleteMessage: document.getElementById("browseBulkDeleteMessage"),
    bulkDeleteCancelBtn: document.getElementById("browseBulkDeleteCancelBtn"),
    bulkDeleteConfirmBtn: document.getElementById("browseBulkDeleteConfirmBtn"),
  };

  const state = {
    openContext: "dashboard",
    currentDeckId: null,
    selectedDeckId: null,
    selectedShortcut: "all",
    includeSubdecks: true,
    deckTree: [],
    deckLookup: new Map(),
    expandedDeckIds: new Set(),
    deckSearch: "",
    rows: [],
    page: 1,
    perPage: 100,
    hasNext: false,
    total: 0,
    loadingTree: false,
    loadingRows: false,
    loadingDetail: false,
    query: {
      keyword: "",
      status: "all",
      tag: "",
    },
    sort: {
      by: "due",
      dir: "asc",
    },
    checkboxMode: false,
    selectedCardIds: new Set(),
    selectedCardId: null,
    detail: null,
    draft: null,
    isDirty: false,
    dirtyFields: new Set(),
    controllers: {},
    bypassHideGuard: false,
    unsavedResolver: null,
    preferredWord: "",
    preferredReading: "",
    preferredSelectionPending: false,
  };

  function escapeHtml(value) {
    const text = value == null ? "" : String(value);
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function debounce(fn, delay = 250) {
    let timerId;
    return (...args) => {
      clearTimeout(timerId);
      timerId = window.setTimeout(() => fn(...args), delay);
    };
  }

  function toNullableInt(rawValue) {
    const value = Number(rawValue);
    if (!Number.isFinite(value) || value <= 0) {
      return null;
    }
    return value;
  }

  function isModalShown() {
    return modalEl.classList.contains("show");
  }

  function parseTagInput(rawValue) {
    if (!rawValue) {
      return [];
    }
    return String(rawValue)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function normalizeSearchText(value) {
    return String(value == null ? "" : value).trim().toLowerCase();
  }

  function truncateDisplay(value, maxLength = 180) {
    const text = String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    if (!text) {
      return "";
    }
    if (text.length <= maxLength) {
      return text;
    }
    return `${text.slice(0, maxLength - 1)}...`;
  }

  function findPreferredRowInLoadedRows() {
    const preferredWord = normalizeSearchText(state.preferredWord);
    const preferredReading = normalizeSearchText(state.preferredReading);
    if (!preferredWord || !state.rows.length) {
      return null;
    }

    const exactWordAndReading = state.rows.find((row) => {
      const rowWord = normalizeSearchText(row.word);
      const rowReading = normalizeSearchText(row.reading);
      if (rowWord !== preferredWord) {
        return false;
      }
      if (!preferredReading) {
        return true;
      }
      return rowReading === preferredReading;
    });
    if (exactWordAndReading) {
      return exactWordAndReading;
    }

    const exactWord = state.rows.find((row) => normalizeSearchText(row.word) === preferredWord);
    if (exactWord) {
      return exactWord;
    }

    if (preferredReading) {
      const exactReading = state.rows.find((row) => normalizeSearchText(row.reading) === preferredReading);
      if (exactReading) {
        return exactReading;
      }
    }

    return state.rows.find((row) => normalizeSearchText(row.word).includes(preferredWord)) || null;
  }

  function updateContextLabel() {
    const contextText = state.selectedShortcut === "current" ? "Current deck" : "All decks";
    const selectedDeckName =
      state.selectedDeckId != null
        ? (state.deckLookup.get(state.selectedDeckId)?.name || "Deck")
        : "All Decks";
    if (els.contextLabel) {
      els.contextLabel.textContent = `${contextText} | ${selectedDeckName}`;
    }
  }

  function setTreeLoading(loading) {
    state.loadingTree = Boolean(loading);
    if (!els.treeLoading) {
      return;
    }
    els.treeLoading.classList.toggle("d-none", !state.loadingTree);
  }

  function setRowsLoading(loading) {
    state.loadingRows = Boolean(loading);
    if (!els.rowsLoading) {
      return;
    }
    els.rowsLoading.classList.toggle("d-none", !state.loadingRows);
  }

  function setSaveButtons() {
    const canEdit = Boolean(state.detail);
    if (els.revertBtn) {
      els.revertBtn.disabled = !canEdit || !state.isDirty;
    }
    if (els.saveBtn) {
      els.saveBtn.disabled = !canEdit || !state.isDirty;
    }
    if (els.deleteBtn) {
      els.deleteBtn.disabled = !canEdit;
    }
  }

  function setShortcutState(shortcut) {
    state.selectedShortcut = shortcut === "current" ? "current" : "all";
    if (els.shortcutAll) {
      els.shortcutAll.classList.toggle("is-active", state.selectedShortcut === "all");
    }
    if (els.shortcutCurrent) {
      els.shortcutCurrent.classList.toggle("is-active", state.selectedShortcut === "current");
      const disabled = state.currentDeckId == null;
      els.shortcutCurrent.disabled = disabled;
      els.shortcutCurrent.title = disabled ? "No current deck in this screen context" : "Jump to current deck";
    }
  }

  function findDeckNodeById(deckId, nodes = state.deckTree) {
    for (const node of nodes) {
      if (Number(node.id) === Number(deckId)) {
        return node;
      }
      const found = findDeckNodeById(deckId, node.children || []);
      if (found) {
        return found;
      }
    }
    return null;
  }

  function ensureExpandedTo(deckId) {
    if (deckId == null) {
      return;
    }
    let currentId = Number(deckId);
    while (currentId) {
      const node = state.deckLookup.get(currentId);
      if (!node) {
        break;
      }
      state.expandedDeckIds.add(currentId);
      currentId = node.parent_id ? Number(node.parent_id) : 0;
    }
  }

  function normalizeDeckLookup() {
    state.deckLookup.clear();
    const walk = (nodes) => {
      for (const node of nodes) {
        state.deckLookup.set(Number(node.id), node);
        if (Array.isArray(node.children) && node.children.length) {
          walk(node.children);
        }
      }
    };
    walk(state.deckTree);
  }

  function nodeMatchesFilter(node, filterText) {
    if (!filterText) {
      return true;
    }
    const nodeName = String(node.name || "").toLowerCase();
    if (nodeName.includes(filterText)) {
      return true;
    }
    const children = Array.isArray(node.children) ? node.children : [];
    return children.some((child) => nodeMatchesFilter(child, filterText));
  }

  function renderTreeRows(nodes, depth, filterText) {
    let html = "";
    for (const node of nodes) {
      if (!nodeMatchesFilter(node, filterText)) {
        continue;
      }
      const nodeId = Number(node.id);
      const children = Array.isArray(node.children) ? node.children : [];
      const hasChildren = children.length > 0;
      const isExpanded = state.expandedDeckIds.has(nodeId) || filterText.length > 0;
      const isActive = state.selectedDeckId === nodeId;
      const counts = node.counts || {};
      const countText = `${counts.total || 0} (${counts.new || 0}/${counts.learn || 0}/${counts.due || 0})`;
      html += `
        <button
          type="button"
          class="browse-tree-row ${isActive ? "is-active" : ""}"
          data-action="select-deck"
          data-deck-id="${nodeId}"
          style="padding-left: ${8 + depth * 14}px;"
          title="${escapeHtml(node.name || "")}"
        >
          <span class="browse-tree-toggle" data-action="${hasChildren ? "toggle-deck" : ""}" data-deck-id="${nodeId}">
            ${hasChildren ? (isExpanded ? "-" : "+") : ""}
          </span>
          <span class="browse-tree-name">${escapeHtml(node.name || "(Unnamed deck)")}</span>
          <span class="browse-tree-count">${escapeHtml(countText)}</span>
        </button>
      `;

      if (hasChildren && isExpanded) {
        html += renderTreeRows(children, depth + 1, filterText);
      }
    }
    return html;
  }

  function renderDeckTree() {
    if (!els.deckTree) {
      return;
    }
    const filterText = String(state.deckSearch || "").trim().toLowerCase();
    const html = renderTreeRows(state.deckTree, 0, filterText);
    if (!html) {
      els.deckTree.innerHTML = '<div class="browse-loading">No decks found.</div>';
      return;
    }
    els.deckTree.innerHTML = html;
    updateContextLabel();
  }

  function renderTable() {
    if (!els.tableBody) {
      return;
    }
    if (els.selectAllHead) {
      els.selectAllHead.classList.toggle("d-none", !state.checkboxMode);
    }
    if (!state.rows.length) {
      if (els.selectAllCheckbox) {
        els.selectAllCheckbox.checked = false;
        els.selectAllCheckbox.indeterminate = false;
      }
      els.tableBody.innerHTML = `
        <tr>
          <td colspan="${state.checkboxMode ? "8" : "7"}" class="browse-empty-cell">No cards match current deck/filters.</td>
        </tr>
      `;
      return;
    }

    const loadedSelectedCount = state.rows.filter((row) => state.selectedCardIds.has(row.card_id)).length;
    if (els.selectAllCheckbox) {
      els.selectAllCheckbox.checked = loadedSelectedCount > 0 && loadedSelectedCount === state.rows.length;
      els.selectAllCheckbox.indeterminate = loadedSelectedCount > 0 && loadedSelectedCount < state.rows.length;
    }

    const rowsHtml = state.rows
      .map((row) => {
        const selected = state.selectedCardIds.has(row.card_id);
        const tags = Array.isArray(row.tags) ? row.tags.join(", ") : "";
        return `
          <tr class="${selected ? "is-selected" : ""}" data-card-id="${escapeHtml(row.card_id)}">
            ${
              state.checkboxMode
                ? `<td class="browse-select-col"><input type="checkbox" class="form-check-input browse-row-checkbox" data-card-id="${escapeHtml(row.card_id)}" ${selected ? "checked" : ""}></td>`
                : ""
            }
            <td title="${escapeHtml(row.card_type || "")}">${escapeHtml(row.card_type || "")}</td>
            <td title="${escapeHtml(row.due_label || "")}">${escapeHtml(row.due_label || "")}</td>
            <td title="${escapeHtml(row.deck_name || "")}">${escapeHtml(row.deck_name || "")}</td>
            <td title="${escapeHtml(row.word || "")}">${escapeHtml(truncateDisplay(row.word || "", 120))}</td>
            <td title="${escapeHtml(row.reading || "")}">${escapeHtml(truncateDisplay(row.reading || "", 120))}</td>
            <td title="${escapeHtml(row.meaning || "")}">${escapeHtml(truncateDisplay(row.meaning || "", 200))}</td>
            <td title="${escapeHtml(tags)}">${escapeHtml(truncateDisplay(tags, 120))}</td>
          </tr>
        `;
      })
      .join("");

    els.tableBody.innerHTML = rowsHtml;
  }

  function renderTableMeta() {
    if (!els.tableMeta) {
      return;
    }
    const loaded = state.rows.length;
    const total = state.total || 0;
    const suffix = state.hasNext ? " | more..." : "";
    const selectedCount = state.selectedCardIds.size;
    const selectedText = selectedCount ? ` | selected: ${selectedCount}` : "";
    els.tableMeta.textContent = `${loaded}/${total} cards${selectedText}${suffix}`;
    if (els.bulkDeleteBtn) {
      els.bulkDeleteBtn.disabled = selectedCount === 0;
    }
  }

  function setCheckboxMode(enabled) {
    state.checkboxMode = Boolean(enabled);
    if (els.toggleCheckboxModeBtn) {
      els.toggleCheckboxModeBtn.classList.toggle("active", state.checkboxMode);
    }
    renderTable();
    renderTableMeta();
  }

  function selectAllLoadedRows() {
    for (const row of state.rows) {
      state.selectedCardIds.add(row.card_id);
    }
    renderTable();
    renderTableMeta();
  }

  function clearLoadedRowSelection() {
    for (const row of state.rows) {
      state.selectedCardIds.delete(row.card_id);
    }
    renderTable();
    renderTableMeta();
  }

  function renderEditor() {
    const hasDetail = Boolean(state.detail && state.draft);
    if (els.editorEmpty) {
      els.editorEmpty.classList.toggle("d-none", hasDetail);
    }
    if (els.editorForm) {
      els.editorForm.classList.toggle("d-none", !hasDetail);
    }
    if (!hasDetail) {
      setSaveButtons();
      return;
    }

    const detail = state.detail;
    const draft = state.draft;

    if (els.editorDeck) {
      const options = ['<option value="">(No deck)</option>'];
      const appendOptions = (nodes, depth) => {
        for (const node of nodes) {
          const prefix = depth > 0 ? `${" ".repeat(depth * 2)}-> ` : "";
          options.push(
            `<option value="${Number(node.id)}"${Number(draft.deck_id) === Number(node.id) ? " selected" : ""}>${escapeHtml(prefix + (node.name || ""))}</option>`
          );
          if (Array.isArray(node.children) && node.children.length) {
            appendOptions(node.children, depth + 1);
          }
        }
      };
      appendOptions(state.deckTree, 0);
      els.editorDeck.innerHTML = options.join("");
    }

    if (els.editorTags) {
      els.editorTags.value = Array.isArray(draft.tags) ? draft.tags.join(", ") : "";
    }

    if (els.editorFields) {
      const mediaByField = new Map();
      for (const asset of detail.media_assets || []) {
        mediaByField.set(asset.field_name, asset);
      }

      const fieldsHtml = (detail.fields || [])
        .map((field) => {
          const name = field.name;
          const type = field.field_type || "text";
          const value = draft.field_values[name] == null ? "" : String(draft.field_values[name]);
          const media = mediaByField.get(name);
          const requiredBadge = field.required ? '<span class="text-danger">*</span>' : "";
          const commonAttrs = `data-browse-field="${escapeHtml(name)}" data-browse-type="${escapeHtml(type)}"`;
          if (type === "image" || type === "audio" || type === "diagram") {
            const mediaMeta = media
              ? `File: ${escapeHtml(media.filename || media.id || "")}`
              : "No media attached yet.";
            const previewBtn = media
              ? `<a class="btn btn-sm btn-outline-secondary browse-editor-media-preview" href="${escapeHtml(media.url || "#")}" target="_blank" rel="noopener">Preview</a>`
              : "";
            return `
              <div class="browse-editor-field">
                <label>${escapeHtml(name)} ${requiredBadge}</label>
                <input type="text" ${commonAttrs} class="form-control form-control-sm" value="${escapeHtml(value)}" placeholder="Media asset id or URL">
                <div class="browse-editor-media-meta">${mediaMeta}</div>
                <div class="browse-editor-media-actions">
                  ${previewBtn}
                  <input type="file" class="form-control form-control-sm" data-upload-field="${escapeHtml(name)}" />
                </div>
              </div>
            `;
          }

          return `
            <div class="browse-editor-field">
              <label>${escapeHtml(name)} ${requiredBadge}</label>
              <textarea rows="2" ${commonAttrs}>${escapeHtml(value)}</textarea>
            </div>
          `;
        })
        .join("");

      els.editorFields.innerHTML = fieldsHtml;
    }

    setSaveButtons();
  }

  function resetDraftFromDetail() {
    if (!state.detail) {
      state.draft = null;
      state.isDirty = false;
      state.dirtyFields.clear();
      setSaveButtons();
      return;
    }

    const note = state.detail.note || {};
    state.draft = {
      deck_id: note.deck_id == null ? "" : String(note.deck_id),
      tags: Array.isArray(note.tags) ? [...note.tags] : [],
      field_values: { ...(note.field_values || {}) },
    };
    state.isDirty = false;
    state.dirtyFields.clear();
    setSaveButtons();
  }

  function markDirty(fieldName) {
    state.isDirty = true;
    if (fieldName) {
      state.dirtyFields.add(fieldName);
    }
    setSaveButtons();
  }

  function updateDraftField(fieldName, value) {
    if (!state.draft || !state.draft.field_values) {
      return;
    }
    const oldValue = state.draft.field_values[fieldName] == null ? "" : String(state.draft.field_values[fieldName]);
    const newValue = value == null ? "" : String(value);
    if (oldValue === newValue) {
      return;
    }
    state.draft.field_values[fieldName] = newValue;
    markDirty(fieldName);
  }

  function updateDraftDeck(value) {
    if (!state.draft) {
      return;
    }
    const normalized = value == null ? "" : String(value);
    if (String(state.draft.deck_id || "") === normalized) {
      return;
    }
    state.draft.deck_id = normalized;
    markDirty("__deck__");
  }

  function updateDraftTags(rawValue) {
    if (!state.draft) {
      return;
    }
    const tags = parseTagInput(rawValue);
    const old = JSON.stringify(state.draft.tags || []);
    const next = JSON.stringify(tags);
    if (old === next) {
      return;
    }
    state.draft.tags = tags;
    markDirty("__tags__");
  }

  function withAbortController(key) {
    if (state.controllers[key]) {
      state.controllers[key].abort();
    }
    const controller = new AbortController();
    state.controllers[key] = controller;
    return controller;
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = payload.message || payload.error || "Request failed.";
      throw new Error(message);
    }
    return payload;
  }

  async function loadDeckTree() {
    setTreeLoading(true);
    try {
      const controller = withAbortController("tree");
      const payload = await requestJson("/vocabulary/api/browse/decks/tree", {
        signal: controller.signal,
      });
      state.deckTree = Array.isArray(payload.tree) ? payload.tree : [];
      normalizeDeckLookup();

      if (!state.expandedDeckIds.size) {
        for (const node of state.deckTree) {
          state.expandedDeckIds.add(Number(node.id));
        }
      }
      if (state.currentDeckId != null) {
        ensureExpandedTo(state.currentDeckId);
      }
      renderDeckTree();
      updateContextLabel();
    } catch (error) {
      if (error.name !== "AbortError" && els.deckTree) {
        els.deckTree.innerHTML = `<div class="browse-loading text-danger">${escapeHtml(error.message)}</div>`;
      }
    } finally {
      setTreeLoading(false);
    }
  }

  function selectedDeckParams(params) {
    if (state.selectedDeckId != null) {
      params.set("deck_id", String(state.selectedDeckId));
      params.set("include_subdecks", state.includeSubdecks ? "1" : "0");
    }
  }

  async function loadCards({ reset = false, keepSelection = false } = {}) {
    if (state.loadingRows) {
      return;
    }
    if (reset) {
      state.page = 1;
      state.rows = [];
      state.total = 0;
      state.hasNext = false;
      renderTable();
      renderTableMeta();
    }

    setRowsLoading(true);
    try {
      const controller = withAbortController("rows");
      const params = new URLSearchParams();
      params.set("page", String(state.page));
      params.set("per_page", String(state.perPage));
      params.set("status", state.query.status || "all");
      params.set("sort_by", state.sort.by || "due");
      params.set("sort_dir", state.sort.dir || "asc");
      if (state.query.keyword.trim()) {
        params.set("q", state.query.keyword.trim());
      }
      if (state.query.tag.trim()) {
        params.set("tag", state.query.tag.trim());
      }
      selectedDeckParams(params);

      const payload = await requestJson(`/vocabulary/api/browse/cards?${params.toString()}`, {
        signal: controller.signal,
      });
      const incomingRows = Array.isArray(payload.items) ? payload.items : [];
      if (reset) {
        state.rows = incomingRows;
      } else {
        state.rows = state.rows.concat(incomingRows);
      }

      state.total = Number(payload.total || state.rows.length || 0);
      state.hasNext = Boolean(payload.has_next);

      renderTable();
      renderTableMeta();

      if (reset) {
        if (keepSelection && state.selectedCardId) {
          const stillExists = state.rows.some((row) => row.card_id === state.selectedCardId);
          if (!stillExists) {
            state.selectedCardId = null;
            state.detail = null;
            state.draft = null;
            state.isDirty = false;
            state.dirtyFields.clear();
            renderEditor();
          }
        } else {
          state.selectedCardId = null;
          state.selectedCardIds.clear();
          state.detail = null;
          state.draft = null;
          state.isDirty = false;
          state.dirtyFields.clear();
          renderEditor();
        }
        if (state.selectedShortcut === "current" && state.currentDeckId != null) {
          selectAllLoadedRows();
        }
      } else if (state.selectedShortcut === "current" && state.currentDeckId != null) {
        for (const row of incomingRows) {
          state.selectedCardIds.add(row.card_id);
        }
        renderTable();
        renderTableMeta();
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        els.tableBody.innerHTML = `
          <tr>
            <td colspan="${state.checkboxMode ? "8" : "7"}" class="browse-empty-cell text-danger">${escapeHtml(error.message)}</td>
          </tr>
        `;
        renderTableMeta();
      }
    } finally {
      setRowsLoading(false);
    }
  }

  async function loadCardDetail(cardId) {
    if (!cardId) {
      return;
    }
    state.loadingDetail = true;
    try {
      const controller = withAbortController("detail");
      const payload = await requestJson(`/vocabulary/api/browse/cards/${encodeURIComponent(cardId)}`, {
        signal: controller.signal,
      });
      state.detail = payload;
      resetDraftFromDetail();
      renderEditor();
    } catch (error) {
      if (error.name !== "AbortError") {
        state.detail = null;
        state.draft = null;
        state.isDirty = false;
        state.dirtyFields.clear();
        renderEditor();
        window.alert(`Cannot load card detail: ${error.message}`);
      }
    } finally {
      state.loadingDetail = false;
    }
  }

  function updateRowInState(rowPayload) {
    if (!rowPayload || !rowPayload.card_id) {
      return;
    }
    const index = state.rows.findIndex((item) => item.card_id === rowPayload.card_id);
    if (index === -1) {
      return;
    }
    state.rows[index] = rowPayload;
  }

  async function saveCurrentCard() {
    if (!state.detail || !state.draft || !state.selectedCardId) {
      return false;
    }
    if (!state.isDirty) {
      return true;
    }

    if (els.saveBtn) {
      els.saveBtn.disabled = true;
      els.saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';
    }

    try {
      const payload = {
        deck_id: state.draft.deck_id === "" ? null : Number(state.draft.deck_id),
        tags: Array.isArray(state.draft.tags) ? state.draft.tags : [],
        field_values: state.draft.field_values || {},
      };

      const response = await requestJson(`/vocabulary/api/browse/cards/${encodeURIComponent(state.selectedCardId)}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.row) {
        updateRowInState(response.row);
      }
      if (response.detail) {
        state.detail = response.detail;
      }
      resetDraftFromDetail();
      renderTable();
      renderEditor();
      renderTableMeta();
      await loadCards({ reset: true, keepSelection: true });
      return true;
    } catch (error) {
      window.alert(`Save failed: ${error.message}`);
      return false;
    } finally {
      if (els.saveBtn) {
        els.saveBtn.innerHTML = "Save";
      }
      setSaveButtons();
    }
  }

  async function deleteCurrentCard() {
    if (!state.selectedCardId) {
      return;
    }
    if (!window.confirm("Delete this card permanently?")) {
      return;
    }

    try {
      await requestJson(`/vocabulary/api/browse/cards/${encodeURIComponent(state.selectedCardId)}`, {
        method: "DELETE",
      });

      state.rows = state.rows.filter((row) => row.card_id !== state.selectedCardId);
      state.total = Math.max(0, state.total - 1);
      const nextRow = state.rows[0] || null;
      state.selectedCardId = nextRow ? nextRow.card_id : null;
      state.detail = null;
      state.draft = null;
      state.isDirty = false;
      state.dirtyFields.clear();
      renderTable();
      renderEditor();
      renderTableMeta();

      if (nextRow) {
        await selectCard(nextRow.card_id);
      }
    } catch (error) {
      window.alert(`Delete failed: ${error.message}`);
    }
  }

  async function deleteSelectedCards() {
    const selectedIds = Array.from(state.selectedCardIds);
    if (!selectedIds.length) {
      return;
    }
    if (els.bulkDeleteConfirmBtn) {
      els.bulkDeleteConfirmBtn.disabled = true;
      els.bulkDeleteConfirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';
    }
    try {
      for (const cardId of selectedIds) {
        await requestJson(`/vocabulary/api/browse/cards/${encodeURIComponent(cardId)}`, {
          method: "DELETE",
        });
      }
      state.selectedCardIds.clear();
      if (state.selectedCardId && selectedIds.includes(state.selectedCardId)) {
        state.selectedCardId = null;
        state.detail = null;
        state.draft = null;
        state.isDirty = false;
        state.dirtyFields.clear();
      }
      bulkDeleteModalInstance.hide();
      await loadCards({ reset: true, keepSelection: false });
      renderEditor();
    } catch (error) {
      window.alert(`Bulk delete failed: ${error.message}`);
    } finally {
      if (els.bulkDeleteConfirmBtn) {
        els.bulkDeleteConfirmBtn.disabled = false;
        els.bulkDeleteConfirmBtn.innerHTML = "Delete";
      }
      renderTableMeta();
    }
  }

  async function uploadMedia(fieldName, file) {
    if (!state.detail || !state.detail.note || !state.detail.note.id || !file) {
      return;
    }
    const noteId = state.detail.note.id;
    const formData = new FormData();
    formData.append("field_name", fieldName);
    formData.append("file", file);

    try {
      await requestJson(`/api/notes/${encodeURIComponent(noteId)}/media`, {
        method: "POST",
        body: formData,
      });
      await loadCardDetail(state.selectedCardId);
      await loadCards({ reset: true, keepSelection: true });
    } catch (error) {
      window.alert(`Media upload failed: ${error.message}`);
    }
  }

  function resolveUnsaved(choice) {
    if (!state.unsavedResolver) {
      return;
    }
    const resolver = state.unsavedResolver;
    state.unsavedResolver = null;
    resolver(choice);
  }

  function askUnsavedChoice() {
    return new Promise((resolve) => {
      state.unsavedResolver = resolve;
      unsavedModalInstance.show();
    });
  }

  async function runWithDirtyGuard(nextAction) {
    if (!state.isDirty) {
      await nextAction();
      return true;
    }

    const choice = await askUnsavedChoice();
    if (choice === "cancel") {
      return false;
    }
    if (choice === "save") {
      const saved = await saveCurrentCard();
      if (!saved) {
        return false;
      }
    } else if (choice === "discard") {
      resetDraftFromDetail();
      renderEditor();
    }

    await nextAction();
    return true;
  }

  async function selectDeck(deckId, shortcut = "all") {
    const normalized = deckId == null ? null : Number(deckId);
    await runWithDirtyGuard(async () => {
      state.selectedDeckId = normalized;
      setShortcutState(shortcut);
      renderDeckTree();
      updateContextLabel();
      await loadCards({ reset: true, keepSelection: false });
    });
  }

  async function selectCard(cardId) {
    if (!cardId) {
      return;
    }
    await runWithDirtyGuard(async () => {
      state.selectedCardId = cardId;
      state.selectedCardIds.add(cardId);
      renderTable();
      await loadCardDetail(cardId);
    });
  }

  function toggleSortDirection() {
    state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
    if (els.sortDirBtn) {
      els.sortDirBtn.dataset.dir = state.sort.dir;
      els.sortDirBtn.innerHTML =
        state.sort.dir === "asc"
          ? '<i class="bi bi-sort-down"></i>'
          : '<i class="bi bi-sort-up"></i>';
    }
  }

  async function openBrowseFromTrigger(trigger) {
    const context = trigger?.dataset?.browseContext || "dashboard";
    let deckId = toNullableInt(trigger?.dataset?.currentDeckId || "");
    if (deckId == null && context === "dashboard") {
      const selectedRow = document.querySelector(".deck-row.is-selected[data-node-id]");
      deckId = toNullableInt(selectedRow?.dataset?.nodeId || "");
      if (deckId != null && trigger?.dataset) {
        trigger.dataset.currentDeckId = String(deckId);
      }
    }
    const preferredWord = String(trigger?.dataset?.currentWord || "").trim();
    const preferredReading = String(trigger?.dataset?.currentReading || "").trim();
    state.openContext = context;
    state.currentDeckId = deckId;
    state.includeSubdecks = true;
    state.preferredWord = preferredWord;
    state.preferredReading = preferredReading;
    state.preferredSelectionPending = Boolean(preferredWord);
    // Keep broad browse results; only prefer selecting current card/word when present.
    if (state.preferredSelectionPending && context === "study") {
      state.query.keyword = "";
      state.query.tag = "";
      state.query.status = "all";
    }
    if (els.includeSubdecks) {
      els.includeSubdecks.checked = true;
    }
    setShortcutState(deckId != null ? "current" : "all");
    modalInstance.show();
  }

  async function handleModalShown() {
    if (els.keyword) {
      els.keyword.value = state.query.keyword;
    }
    if (els.status) {
      els.status.value = state.query.status;
    }
    if (els.tag) {
      els.tag.value = state.query.tag;
    }
    if (els.sortBy) {
      els.sortBy.value = state.sort.by;
    }
    setCheckboxMode(false);
    updateContextLabel();
    await loadDeckTree();
    if (state.selectedShortcut === "current" && state.currentDeckId != null) {
      if (!findDeckNodeById(state.currentDeckId)) {
        state.selectedDeckId = null;
        setShortcutState("all");
      } else {
        state.selectedDeckId = state.currentDeckId;
        ensureExpandedTo(state.currentDeckId);
      }
    } else {
      state.selectedDeckId = null;
      setShortcutState("all");
    }
    renderDeckTree();
    await loadCards({ reset: true, keepSelection: false });

    if (state.preferredSelectionPending && state.rows.length) {
      const preferredRow = findPreferredRowInLoadedRows() || state.rows[0];
      state.preferredSelectionPending = false;
      state.preferredWord = "";
      state.preferredReading = "";
      if (preferredRow?.card_id) {
        await selectCard(preferredRow.card_id);
      }
    }
  }

  function setupEvents() {
    document.addEventListener("click", (event) => {
      const trigger = event.target.closest('[data-browse-open="1"]');
      if (!trigger) {
        return;
      }
      event.preventDefault();
      openBrowseFromTrigger(trigger);
    });

    modalEl.addEventListener("shown.bs.modal", () => {
      handleModalShown().catch(() => undefined);
    });

    modalEl.addEventListener("hide.bs.modal", (event) => {
      if (state.bypassHideGuard || !state.isDirty) {
        return;
      }
      event.preventDefault();
      runWithDirtyGuard(async () => {
        state.bypassHideGuard = true;
        modalInstance.hide();
        state.bypassHideGuard = false;
      }).catch(() => undefined);
    });

    if (els.refreshBtn) {
      els.refreshBtn.addEventListener("click", async () => {
        await loadDeckTree();
        await loadCards({ reset: true, keepSelection: true });
        if (state.selectedCardId) {
          await loadCardDetail(state.selectedCardId);
        }
      });
    }

    if (els.deckSearch) {
      els.deckSearch.addEventListener("input", () => {
        state.deckSearch = String(els.deckSearch.value || "");
        renderDeckTree();
      });
    }

    if (els.includeSubdecks) {
      els.includeSubdecks.addEventListener("change", async () => {
        state.includeSubdecks = Boolean(els.includeSubdecks.checked);
        await loadCards({ reset: true, keepSelection: true });
      });
    }

    if (els.shortcutAll) {
      els.shortcutAll.addEventListener("click", () => {
        selectDeck(null, "all").catch(() => undefined);
      });
    }

    if (els.shortcutCurrent) {
      els.shortcutCurrent.addEventListener("click", () => {
        if (state.currentDeckId == null) {
          return;
        }
        selectDeck(state.currentDeckId, "current").catch(() => undefined);
      });
    }

    if (els.deckTree) {
      els.deckTree.addEventListener("click", (event) => {
        const toggleEl = event.target.closest('[data-action="toggle-deck"]');
        if (toggleEl?.dataset.deckId) {
          const deckId = Number(toggleEl.dataset.deckId);
          if (state.expandedDeckIds.has(deckId)) {
            state.expandedDeckIds.delete(deckId);
          } else {
            state.expandedDeckIds.add(deckId);
          }
          renderDeckTree();
          return;
        }

        const row = event.target.closest('[data-action="select-deck"]');
        if (!row?.dataset.deckId) {
          return;
        }
        const deckId = Number(row.dataset.deckId);
        selectDeck(deckId, "all").catch(() => undefined);
      });
    }

    const debouncedFilterReload = debounce(() => {
      loadCards({ reset: true, keepSelection: true }).catch(() => undefined);
    }, 280);

    if (els.keyword) {
      els.keyword.addEventListener("input", () => {
        state.query.keyword = String(els.keyword.value || "");
        debouncedFilterReload();
      });
    }

    if (els.status) {
      els.status.addEventListener("change", () => {
        state.query.status = String(els.status.value || "all");
        loadCards({ reset: true, keepSelection: true }).catch(() => undefined);
      });
    }

    if (els.tag) {
      els.tag.addEventListener("input", () => {
        state.query.tag = String(els.tag.value || "");
        debouncedFilterReload();
      });
    }

    if (els.sortBy) {
      els.sortBy.addEventListener("change", () => {
        state.sort.by = String(els.sortBy.value || "due");
        loadCards({ reset: true, keepSelection: true }).catch(() => undefined);
      });
    }

    if (els.sortDirBtn) {
      els.sortDirBtn.addEventListener("click", () => {
        toggleSortDirection();
        loadCards({ reset: true, keepSelection: true }).catch(() => undefined);
      });
    }

    if (els.toggleCheckboxModeBtn) {
      els.toggleCheckboxModeBtn.addEventListener("click", () => {
        setCheckboxMode(!state.checkboxMode);
      });
    }

    if (els.bulkDeleteBtn) {
      els.bulkDeleteBtn.addEventListener("click", () => {
        const selectedCount = state.selectedCardIds.size;
        if (!selectedCount) {
          return;
        }
        if (els.bulkDeleteMessage) {
          els.bulkDeleteMessage.textContent = `Delete ${selectedCount} selected card(s) permanently?`;
        }
        bulkDeleteModalInstance.show();
      });
    }

    if (els.selectAllCheckbox) {
      els.selectAllCheckbox.addEventListener("change", () => {
        if (els.selectAllCheckbox.checked) {
          selectAllLoadedRows();
          return;
        }
        clearLoadedRowSelection();
      });
    }

    if (els.tableBody) {
      els.tableBody.addEventListener("click", (event) => {
        const checkbox = event.target.closest(".browse-row-checkbox");
        if (checkbox?.dataset.cardId) {
          if (checkbox.checked) {
            state.selectedCardIds.add(checkbox.dataset.cardId);
          } else {
            state.selectedCardIds.delete(checkbox.dataset.cardId);
          }
          selectCard(checkbox.dataset.cardId).catch(() => undefined);
          renderTableMeta();
          return;
        }
        const row = event.target.closest("tr[data-card-id]");
        if (!row?.dataset.cardId) {
          return;
        }
        if (!state.checkboxMode) {
          state.selectedCardIds.clear();
        }
        state.selectedCardIds.add(row.dataset.cardId);
        selectCard(row.dataset.cardId).catch(() => undefined);
      });
    }

    if (els.tableWrap) {
      els.tableWrap.addEventListener("scroll", () => {
        if (state.loadingRows || !state.hasNext) {
          return;
        }
        const distance = els.tableWrap.scrollHeight - els.tableWrap.scrollTop - els.tableWrap.clientHeight;
        if (distance > 260) {
          return;
        }
        state.page += 1;
        loadCards({ reset: false, keepSelection: true }).catch(() => undefined);
      });
    }

    if (els.editorForm) {
      els.editorForm.addEventListener("input", (event) => {
        const fieldTarget = event.target.closest("[data-browse-field]");
        if (fieldTarget?.dataset.browseField) {
          updateDraftField(fieldTarget.dataset.browseField, fieldTarget.value);
          return;
        }
        if (event.target === els.editorTags) {
          updateDraftTags(els.editorTags.value);
        }
      });

      els.editorForm.addEventListener("change", (event) => {
        if (event.target === els.editorDeck) {
          updateDraftDeck(els.editorDeck.value);
          return;
        }
        if (event.target === els.editorTags) {
          updateDraftTags(els.editorTags.value);
          return;
        }
        const uploadFieldInput = event.target.closest("[data-upload-field]");
        if (uploadFieldInput?.dataset.uploadField && uploadFieldInput.files && uploadFieldInput.files[0]) {
          uploadMedia(uploadFieldInput.dataset.uploadField, uploadFieldInput.files[0]).catch(() => undefined);
          uploadFieldInput.value = "";
        }
      });
    }

    if (els.revertBtn) {
      els.revertBtn.addEventListener("click", () => {
        resetDraftFromDetail();
        renderEditor();
      });
    }

    if (els.saveBtn) {
      els.saveBtn.addEventListener("click", () => {
        saveCurrentCard().catch(() => undefined);
      });
    }

    if (els.deleteBtn) {
      els.deleteBtn.addEventListener("click", () => {
        runWithDirtyGuard(async () => {
          await deleteCurrentCard();
        }).catch(() => undefined);
      });
    }

    if (els.unsavedCancelBtn) {
      els.unsavedCancelBtn.addEventListener("click", () => {
        resolveUnsaved("cancel");
      });
    }
    if (els.unsavedDiscardBtn) {
      els.unsavedDiscardBtn.addEventListener("click", () => {
        resolveUnsaved("discard");
        unsavedModalInstance.hide();
      });
    }
    if (els.unsavedSaveBtn) {
      els.unsavedSaveBtn.addEventListener("click", () => {
        resolveUnsaved("save");
        unsavedModalInstance.hide();
      });
    }

    if (els.bulkDeleteConfirmBtn) {
      els.bulkDeleteConfirmBtn.addEventListener("click", () => {
        runWithDirtyGuard(async () => {
          await deleteSelectedCards();
        }).catch(() => undefined);
      });
    }

    unsavedModalEl.addEventListener("hidden.bs.modal", () => {
      if (state.unsavedResolver) {
        resolveUnsaved("cancel");
      }
    });

    document.addEventListener("keydown", (event) => {
      if (!isModalShown()) {
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveCurrentCard().catch(() => undefined);
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
        event.preventDefault();
        selectAllLoadedRows();
        return;
      }

      const tag = String(event.target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") {
        return;
      }

      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (!state.rows.length) {
          return;
        }
        event.preventDefault();
        const currentIndex = state.rows.findIndex((row) => row.card_id === state.selectedCardId);
        const delta = event.key === "ArrowDown" ? 1 : -1;
        const baseIndex = currentIndex === -1 ? 0 : currentIndex;
        const nextIndex = Math.max(0, Math.min(state.rows.length - 1, baseIndex + delta));
        const nextRow = state.rows[nextIndex];
        if (nextRow && nextRow.card_id !== state.selectedCardId) {
          selectCard(nextRow.card_id).catch(() => undefined);
        }
      }
    });
  }

  setupEvents();
})();
