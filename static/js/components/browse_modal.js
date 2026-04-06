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
  const VOICEVOX_BATCH_SIZE = 4;
  const VOICEVOX_GENERATE_CONTROLLER_KEY = "voicevox-generate";
  const MARKDOWN_PROXY_MEDIA_RE = /^\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

  const els = {
    contextLabel: document.getElementById("browseContextLabel"),
    audioCreateBtn: document.getElementById("browseAudioCreateBtn"),
    audioCreateMenu: document.getElementById("browseAudioCreateMenu"),
    voicevoxOptionBtn: document.getElementById("browseVoicevoxOptionBtn"),
    voicevoxModal: document.getElementById("browseVoicevoxModal"),
    voicevoxModalBackdrop: document.getElementById("browseVoicevoxModalBackdrop"),
    voicevoxModalCloseBtn: document.getElementById("browseVoicevoxModalCloseBtn"),
    voicevoxCancelBtn: document.getElementById("browseVoicevoxCancelBtn"),
    voicevoxSaveSettingsBtn: document.getElementById("browseVoicevoxSaveSettingsBtn"),
    voicevoxResetDefaultsBtn: document.getElementById("browseVoicevoxResetDefaultsBtn"),
    voicevoxRetryFailedBtn: document.getElementById("browseVoicevoxRetryFailedBtn"),
    voicevoxCancelGenerateBtn: document.getElementById("browseVoicevoxCancelGenerateBtn"),
    voicevoxGenerateBtn: document.getElementById("browseVoicevoxGenerateBtn"),
    voicevoxPreviewBtn: document.getElementById("browseVoicevoxPreviewBtn"),
    voicevoxSelectedNotes: document.getElementById("browseVoicevoxSelectedNotes"),
    voicevoxSourceField: document.getElementById("browseVoicevoxSourceField"),
    voicevoxDestinationField: document.getElementById("browseVoicevoxDestinationField"),
    voicevoxAppendAudio: document.getElementById("browseVoicevoxAppendAudio"),
    voicevoxUseOpus: document.getElementById("browseVoicevoxUseOpus"),
    voicevoxApiKey: document.getElementById("browseVoicevoxApiKey"),
    voicevoxApiKeyToggleBtn: document.getElementById("browseVoicevoxApiKeyToggleBtn"),
    voicevoxApiKeyToggleIcon: document.getElementById("browseVoicevoxApiKeyToggleIcon"),
    voicevoxPreviewPlayer: document.getElementById("browseVoicevoxPreviewPlayer"),
    voicevoxKeyStatus: document.getElementById("browseVoicevoxKeyStatus"),
    voicevoxCharacter: document.getElementById("browseVoicevoxCharacter"),
    voicevoxCharacterMeta: document.getElementById("browseVoicevoxCharacterMeta"),
    voicevoxProgressWrap: document.getElementById("browseVoicevoxProgressWrap"),
    voicevoxProgressText: document.getElementById("browseVoicevoxProgressText"),
    voicevoxProgressDetail: document.getElementById("browseVoicevoxProgressDetail"),
    voicevoxProgressBar: document.getElementById("browseVoicevoxProgressBar"),
    voicevoxFailedWrap: document.getElementById("browseVoicevoxFailedWrap"),
    voicevoxFailedCount: document.getElementById("browseVoicevoxFailedCount"),
    voicevoxFailedList: document.getElementById("browseVoicevoxFailedList"),
    voicevoxVolumeScale: document.getElementById("browseVoicevoxVolumeScale"),
    voicevoxVolumeScaleValue: document.getElementById("browseVoicevoxVolumeScaleValue"),
    voicevoxPitch: document.getElementById("browseVoicevoxPitch"),
    voicevoxIntonationScale: document.getElementById("browseVoicevoxIntonationScale"),
    voicevoxSpeed: document.getElementById("browseVoicevoxSpeed"),
    voicevoxInitialSilenceScale: document.getElementById("browseVoicevoxInitialSilenceScale"),
    voicevoxFinalSilenceLength: document.getElementById("browseVoicevoxFinalSilenceLength"),
    voicevoxInitialSilenceScaleValue: document.getElementById("browseVoicevoxInitialSilenceScaleValue"),
    voicevoxFinalSilenceLengthValue: document.getElementById("browseVoicevoxFinalSilenceLengthValue"),
    voicevoxPitchValue: document.getElementById("browseVoicevoxPitchValue"),
    voicevoxIntonationScaleValue: document.getElementById("browseVoicevoxIntonationScaleValue"),
    voicevoxSpeedValue: document.getElementById("browseVoicevoxSpeedValue"),
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
    editorMarkdownToolbar: document.getElementById("browseEditorMarkdownToolbar"),
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
    rowsRequestSeq: 0,
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
    voicevox: {
      characterId: "",
      sourceField: "",
      destinationField: "",
      volumeScale: 1.0,
      pitchScale: 0.0,
      speedScale: 1.0,
      intonationScale: 1.0,
      initialSilenceScale: 0.1,
      finalSilenceLength: 0.1,
      appendAudio: false,
      useOpus: false,
      apiKey: "",
      apiKeyVisible: false,
      maskedApiKey: "",
      sourceFieldOptions: [],
      destinationFieldOptions: [],
      outputRoot: "",
      characters: [],
      loadingCharacters: false,
      characterError: "",
      hasApiKey: false,
      keyStatus: "unknown",
      lastValidationError: "",
      loadedProfile: false,
      loadingProfile: false,
      validatingKey: false,
      savingSettings: false,
      generating: false,
      generationMode: "",
      cancelRequested: false,
      previewing: false,
      previewObjectUrl: "",
      batchSize: VOICEVOX_BATCH_SIZE,
      progressTotal: 0,
      progressProcessed: 0,
      progressGenerated: 0,
      progressFailed: 0,
      progressMessage: "",
      failedNotes: [],
      defaultSettings: {
        characterId: "",
        volumeScale: 1.0,
        pitchScale: 0.0,
        speedScale: 1.0,
        intonationScale: 1.0,
        initialSilenceScale: 0.1,
        finalSilenceLength: 0.1,
      },
      lastSavedSettingsHash: "",
      settingsDirty: false,
    },
  };

  let browseMarkdownManager = null;
  let browseMarkdownEditors = new Map();

  function escapeHtml(value) {
    const text = value == null ? "" : String(value);
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function cssEscape(value) {
    const raw = String(value == null ? "" : value);
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(raw);
    }
    return raw.replace(/["\\]/g, "\\$&");
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

  function isImageFile(file) {
    return Boolean(file && String(file.type || "").toLowerCase().startsWith("image/"));
  }

  function normalizeMarkdownAlt(raw) {
    const normalized = String(raw || "image")
      .replace(/[\[\]\(\)]/g, "")
      .trim()
      .slice(0, 80);
    return normalized || "image";
  }

  function markdownTextToPreviewHtml(rawText) {
    return escapeHtml(rawText).replace(/\n/g, "<br>");
  }

  function renderMarkdownPreviewHtml(rawMarkdown) {
    const source = String(rawMarkdown || "").replace(/\r\n?/g, "\n");
    if (!source.trim()) {
      return '<div class="browse-editor-markdown-preview-empty">Khung xem trước đang trống.</div>';
    }

    const imageRe = /!\[([^\]]*)\]\(([^)\s]+)\)/g;
    const chunks = [];
    let cursor = 0;
    let match;

    while ((match = imageRe.exec(source)) !== null) {
      const before = source.slice(cursor, match.index);
      if (before) {
        chunks.push(`<div class="browse-editor-markdown-preview-text">${markdownTextToPreviewHtml(before)}</div>`);
      }

      const alt = String(match[1] || "").trim().slice(0, 160) || "image";
      const imageUrl = String(match[2] || "").trim();
      if (MARKDOWN_PROXY_MEDIA_RE.test(imageUrl)) {
        chunks.push(
          `<figure class="browse-editor-markdown-preview-figure"><img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(alt)}" loading="lazy"></figure>`
        );
      } else {
        chunks.push(`<div class="browse-editor-markdown-preview-text">${markdownTextToPreviewHtml(match[0])}</div>`);
      }
      cursor = imageRe.lastIndex;
    }

    const tail = source.slice(cursor);
    if (tail) {
      chunks.push(`<div class="browse-editor-markdown-preview-text">${markdownTextToPreviewHtml(tail)}</div>`);
    }

    return chunks.length
      ? chunks.join("")
      : '<div class="browse-editor-markdown-preview-empty">Khung xem trước đang trống.</div>';
  }

  function syncMarkdownPreviewForTextarea(textarea) {
    if (!(textarea instanceof HTMLTextAreaElement) || !els.editorFields) {
      return;
    }
    const fieldName = String(textarea.dataset.browseField || "").trim();
    if (!fieldName) {
      return;
    }
    const previewEl = els.editorFields.querySelector(
      `[data-markdown-preview-for="${cssEscape(fieldName)}"]`
    );
    if (!(previewEl instanceof HTMLElement)) {
      return;
    }
    previewEl.innerHTML = renderMarkdownPreviewHtml(textarea.value);
  }

  function refreshMarkdownPreviewsInEditor() {
    if (!els.editorFields) {
      return;
    }
    els.editorFields
      .querySelectorAll('textarea[data-markdown-inline="1"][data-browse-field]')
      .forEach((textarea) => {
        syncMarkdownPreviewForTextarea(textarea);
      });
  }

  function resetBrowseMarkdownEditors() {
    browseMarkdownEditors.clear();
    if (browseMarkdownManager) {
      browseMarkdownManager.destroyAll();
    }
    if (!els.editorMarkdownToolbar) {
      browseMarkdownManager = null;
      return;
    }
    if (window.FlamaMarkdownEditor) {
      browseMarkdownManager = window.FlamaMarkdownEditor.createManager({
        toolbarHost: els.editorMarkdownToolbar,
      });
      els.editorMarkdownToolbar.classList.remove("d-none");
      return;
    }
    browseMarkdownManager = null;
    els.editorMarkdownToolbar.classList.add("d-none");
    els.editorMarkdownToolbar.replaceChildren();
  }

  function initBrowseMarkdownEditors(fields, values) {
    resetBrowseMarkdownEditors();
    const markdownFields = Array.isArray(fields)
      ? fields.filter((field) => String(field?.field_type || "").trim().toLowerCase() === "markdown")
      : [];
    if (!markdownFields.length) {
      if (els.editorMarkdownToolbar) {
        els.editorMarkdownToolbar.classList.add("d-none");
        els.editorMarkdownToolbar.replaceChildren();
      }
      browseMarkdownManager = null;
      return;
    }
    if (!browseMarkdownManager || !els.editorFields || !Array.isArray(fields)) {
      return;
    }
    markdownFields.forEach((field) => {
      const name = String(field?.name || "").trim();
      if (!name) {
        return;
      }
      const mount = els.editorFields.querySelector(`[data-browse-markdown-mount="${cssEscape(name)}"]`);
      if (!(mount instanceof HTMLElement)) {
        return;
      }
      const value = values && values[name] != null ? String(values[name]) : "";
      const editor = browseMarkdownManager.register({
        mount,
        fieldName: name,
        label: name,
        inputName: "",
        value,
        minHeight: "2.75rem",
        hint: "",
        uploadImage: (file, currentEditor) => uploadMarkdownInlineMedia(name, file, currentEditor),
        onChange: (nextValue) => {
          updateDraftField(name, nextValue);
        },
      });
      browseMarkdownEditors.set(name, editor);
    });
  }

  function insertMarkdownImageSyntax(textarea, imageUrl, filename) {
    if (!(textarea instanceof HTMLTextAreaElement) || !imageUrl) {
      return;
    }
    const currentValue = String(textarea.value || "");
    const start = Number(textarea.selectionStart ?? currentValue.length);
    const end = Number(textarea.selectionEnd ?? start);
    const before = currentValue.slice(0, start);
    const after = currentValue.slice(end);
    const needsLeadingBreak = before.length > 0 && !before.endsWith("\n");
    const needsTrailingBreak = after.length > 0 && !after.startsWith("\n");
    const alt = normalizeMarkdownAlt(filename || "image");
    const snippet = `${needsLeadingBreak ? "\n" : ""}![${alt}](${imageUrl})${needsTrailingBreak ? "\n" : ""}`;

    textarea.value = `${before}${snippet}${after}`;
    const cursor = before.length + snippet.length;
    textarea.focus();
    textarea.setSelectionRange(cursor, cursor);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function imageFileFromClipboardData(clipboardData) {
    if (!clipboardData || !clipboardData.items) {
      return null;
    }
    for (const item of clipboardData.items) {
      if (item.kind !== "file") {
        continue;
      }
      const file = item.getAsFile();
      if (isImageFile(file)) {
        return file;
      }
    }
    return null;
  }

  function firstImageFile(filesLike) {
    const files = Array.from(filesLike || []);
    return files.find((candidate) => isImageFile(candidate)) || null;
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
    const contextText = state.selectedShortcut === "current" ? "Deck hiện tại" : "Tất cả deck";
    const selectedDeckName =
      state.selectedDeckId != null
        ? (state.deckLookup.get(state.selectedDeckId)?.name || "Deck")
        : "Tất cả deck";
    if (els.contextLabel) {
      els.contextLabel.textContent = `${contextText} | ${selectedDeckName}`;
    }
  }

  function clampRange(value, minimum, maximum, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n)) {
      return fallback;
    }
    return Math.max(minimum, Math.min(maximum, n));
  }

  function normalizeBooleanFlag(value, fallback = false) {
    if (typeof value === "boolean") {
      return value;
    }
    if (typeof value === "number") {
      return value !== 0;
    }
    const text = String(value == null ? "" : value).trim().toLowerCase();
    if (!text) {
      return fallback;
    }
    if (text === "1" || text === "true" || text === "yes" || text === "on") {
      return true;
    }
    if (text === "0" || text === "false" || text === "no" || text === "off") {
      return false;
    }
    return fallback;
  }

  function applyInputAutofillGuard(input, { password = false } = {}) {
    if (!input) {
      return;
    }
    input.setAttribute("autocomplete", password ? "new-password" : "off");
    input.setAttribute("autocorrect", "off");
    input.setAttribute("autocapitalize", "none");
    input.setAttribute("spellcheck", "false");
    input.setAttribute("data-form-type", "other");
    input.setAttribute("data-lpignore", "true");
    input.setAttribute("data-1p-ignore", "true");
    if (!input.name) {
      const base = String(input.id || "field").replace(/[^a-z0-9_]/gi, "_");
      input.name = `manual_${base}_${Math.random().toString(36).slice(2, 8)}`;
    }
    input.readOnly = true;
    const unlock = () => {
      input.readOnly = false;
    };
    input.addEventListener("focus", unlock, { once: true });
    input.addEventListener("pointerdown", unlock, { once: true });
    input.addEventListener("keydown", unlock, { once: true });
  }

  function formatSliderValue(value) {
    return Number(value).toFixed(1);
  }

  function clearVoicevoxPreviewObjectUrl() {
    if (!state.voicevox.previewObjectUrl) {
      return;
    }
    window.URL.revokeObjectURL(state.voicevox.previewObjectUrl);
    state.voicevox.previewObjectUrl = "";
  }

  function resetVoicevoxPreviewPlayer() {
    clearVoicevoxPreviewObjectUrl();
    if (!els.voicevoxPreviewPlayer) {
      return;
    }
    try {
      els.voicevoxPreviewPlayer.pause();
    } catch (error) {
      // Ignore pause errors from detached/empty media elements.
    }
    els.voicevoxPreviewPlayer.removeAttribute("src");
    try {
      els.voicevoxPreviewPlayer.load();
    } catch (error) {
      // Ignore reload errors from empty media elements.
    }
    els.voicevoxPreviewPlayer.classList.add("d-none");
  }

  function selectedVoicevoxCardIds() {
    const cardIds = Array.from(state.selectedCardIds);
    if (!cardIds.length && state.selectedCardId) {
      cardIds.push(state.selectedCardId);
    }
    return cardIds;
  }

  function chunkArray(values, size) {
    const batchSize = Math.max(1, Number(size) || 1);
    const items = Array.isArray(values) ? values : [];
    const batches = [];
    for (let index = 0; index < items.length; index += batchSize) {
      batches.push(items.slice(index, index + batchSize));
    }
    return batches;
  }

  function voicevoxTargetKeyFromIds(noteId, cardId) {
    const safeNoteId = String(noteId || "").trim();
    if (safeNoteId) {
      return `note:${safeNoteId}`;
    }
    const safeCardId = String(cardId || "").trim();
    if (safeCardId) {
      return `card:${safeCardId}`;
    }
    return "";
  }

  function collectVoicevoxTargetsFromCardIds(cardIds) {
    const ids = Array.isArray(cardIds) ? cardIds.filter(Boolean) : [];
    const rowByCardId = new Map(state.rows.map((row) => [String(row.card_id || ""), row]));
    const targets = [];
    const seenKeys = new Set();

    for (const rawCardId of ids) {
      const cardId = String(rawCardId || "").trim();
      if (!cardId) {
        continue;
      }
      const row = rowByCardId.get(cardId);
      const noteId = String(row?.note_id || "").trim();
      const key = voicevoxTargetKeyFromIds(noteId, cardId);
      if (!key || seenKeys.has(key)) {
        continue;
      }
      seenKeys.add(key);
      targets.push(
        {
          key,
          cardId,
          noteId,
          word: String(row?.word || "").trim(),
          reading: String(row?.reading || "").trim(),
        }
      );
    }
    return targets;
  }

  function dedupeVoicevoxFailedNotes(items) {
    const rows = Array.isArray(items) ? items : [];
    const result = [];
    const keyToIndex = new Map();
    for (const rawItem of rows) {
      const item = rawItem && typeof rawItem === "object" ? rawItem : {};
      const noteId = String(item.noteId || item.note_id || "").trim();
      const cardId = String(item.cardId || item.card_id || "").trim();
      const key = String(item.key || voicevoxTargetKeyFromIds(noteId, cardId)).trim();
      if (!key) {
        continue;
      }
      const next = {
        key,
        noteId,
        cardId,
        word: String(item.word || "").trim(),
        reading: String(item.reading || "").trim(),
        reason: String(item.reason || "Không tạo được audio.").trim() || "Không tạo được audio.",
      };
      if (keyToIndex.has(key)) {
        result[keyToIndex.get(key)] = next;
      } else {
        keyToIndex.set(key, result.length);
        result.push(next);
      }
    }
    return result;
  }

  function buildVoicevoxFailedNote(target, reason) {
    const item = target && typeof target === "object" ? target : {};
    const fallbackReason = String(reason || "").trim() || "Không tạo được audio.";
    return {
      key: String(item.key || voicevoxTargetKeyFromIds(item.noteId, item.cardId)),
      noteId: String(item.noteId || "").trim(),
      cardId: String(item.cardId || "").trim(),
      word: String(item.word || "").trim(),
      reading: String(item.reading || "").trim(),
      reason: fallbackReason,
    };
  }

  function isVoicevoxKeyOrPointError(reason) {
    const text = String(reason || "").toLowerCase();
    if (!text) {
      return false;
    }
    return (
      text.includes("api key") ||
      text.includes("không hợp lệ") ||
      text.includes("hết hạn") ||
      text.includes("không đủ points") ||
      text.includes("hết points")
    );
  }

  function renderVoicevoxProgressAndFailed() {
    const total = Math.max(0, Number(state.voicevox.progressTotal || 0));
    const processed = Math.max(0, Math.min(total || Number.MAX_SAFE_INTEGER, Number(state.voicevox.progressProcessed || 0)));
    const generated = Math.max(0, Number(state.voicevox.progressGenerated || 0));
    const failed = Math.max(0, Number(state.voicevox.progressFailed || 0));
    const percent = total > 0 ? Math.max(0, Math.min(100, Math.round((processed / total) * 100))) : 0;
    const message = String(state.voicevox.progressMessage || "").trim();

    if (els.voicevoxProgressWrap) {
      const shouldShow = total > 0 || Boolean(message);
      els.voicevoxProgressWrap.classList.toggle("d-none", !shouldShow);
    }
    if (els.voicevoxProgressText) {
      els.voicevoxProgressText.textContent = `${processed}/${total}`;
    }
    if (els.voicevoxProgressDetail) {
      const detail = `Thành công ${generated} | Lỗi ${failed}`;
      els.voicevoxProgressDetail.textContent = message ? `${detail} | ${message}` : detail;
    }
    if (els.voicevoxProgressBar) {
      els.voicevoxProgressBar.style.width = `${percent}%`;
      els.voicevoxProgressBar.setAttribute("aria-valuenow", String(percent));
    }

    const failedNotes = dedupeVoicevoxFailedNotes(state.voicevox.failedNotes);
    state.voicevox.failedNotes = failedNotes;
    const failedCount = failedNotes.length;
    if (els.voicevoxFailedWrap) {
      els.voicevoxFailedWrap.classList.toggle("d-none", failedCount === 0);
    }
    if (els.voicevoxFailedCount) {
      els.voicevoxFailedCount.textContent = String(failedCount);
    }
    if (els.voicevoxFailedList) {
      const itemsHtml = failedNotes.slice(0, 8).map((item) => {
        const head = item.word
          ? (item.reading ? `${item.word} (${item.reading})` : item.word)
          : (item.noteId ? `Note ${item.noteId}` : `Card ${item.cardId}`);
        return `<div class="browse-voicevox-failed__item"><strong>${escapeHtml(head)}</strong>: ${escapeHtml(item.reason)}</div>`;
      });
      if (failedCount > 8) {
        itemsHtml.push(`<div class="browse-voicevox-failed__item">... và ${failedCount - 8} mục lỗi khác</div>`);
      }
      els.voicevoxFailedList.innerHTML = itemsHtml.join("");
    }
  }

  function updateVoicevoxSelectedNotesLabel() {
    if (!els.voicevoxSelectedNotes) {
      return;
    }
    const selectedCardIds = selectedVoicevoxCardIds();
    const noteIds = new Set();
    const rowMap = new Map(state.rows.map((row) => [row.card_id, row]));
    for (const cardId of selectedCardIds) {
      const row = rowMap.get(cardId);
      const noteId = String(row?.note_id || "");
      if (noteId) {
        noteIds.add(noteId);
      }
    }
    if (!noteIds.size && state.detail?.note?.id) {
      noteIds.add(String(state.detail.note.id));
    }
    els.voicevoxSelectedNotes.textContent = String(noteIds.size);
  }

  function updateVoicevoxValueLabels() {
    if (els.voicevoxVolumeScaleValue) {
      els.voicevoxVolumeScaleValue.textContent = formatSliderValue(state.voicevox.volumeScale);
    }
    if (els.voicevoxPitchValue) {
      els.voicevoxPitchValue.textContent = formatSliderValue(state.voicevox.pitchScale);
    }
    if (els.voicevoxSpeedValue) {
      els.voicevoxSpeedValue.textContent = formatSliderValue(state.voicevox.speedScale);
    }
    if (els.voicevoxIntonationScaleValue) {
      els.voicevoxIntonationScaleValue.textContent = formatSliderValue(state.voicevox.intonationScale);
    }
    if (els.voicevoxInitialSilenceScaleValue) {
      els.voicevoxInitialSilenceScaleValue.textContent = formatSliderValue(state.voicevox.initialSilenceScale);
    }
    if (els.voicevoxFinalSilenceLengthValue) {
      els.voicevoxFinalSilenceLengthValue.textContent = formatSliderValue(state.voicevox.finalSilenceLength);
    }
  }

  function updateVoicevoxMetaLabels() {
    updateVoicevoxSelectedNotesLabel();

    if (els.voicevoxKeyStatus) {
      const rawStatus = String(state.voicevox.keyStatus || "unknown").toLowerCase();
      const statusText = rawStatus === "valid"
        ? "Hợp lệ"
        : rawStatus === "invalid"
          ? "Không hợp lệ"
          : "Chưa kiểm tra";
      const detailText = String(state.voicevox.lastValidationError || "").trim();
      els.voicevoxKeyStatus.textContent = detailText
        ? `Trạng thái key: ${statusText} | ${detailText}`
        : `Trạng thái key: ${statusText}`;
    }

    if (els.voicevoxCharacterMeta) {
      if (state.voicevox.characterError) {
        els.voicevoxCharacterMeta.textContent = state.voicevox.characterError;
      } else {
        els.voicevoxCharacterMeta.textContent = "";
      }
    }
    renderVoicevoxProgressAndFailed();
  }

  function renderVoicevoxCharacterOptions() {
    if (!els.voicevoxCharacter) {
      return;
    }
    const selected = String(state.voicevox.characterId || "").trim();
    const options = ['<option value="">Chọn nhân vật</option>'];
    const characters = Array.isArray(state.voicevox.characters) ? state.voicevox.characters : [];
    for (const item of characters) {
      const id = String(item?.id || "").trim();
      if (!id) {
        continue;
      }
      const label = String(item?.label || id);
      options.push(`<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`);
    }
    els.voicevoxCharacter.innerHTML = options.join("");
    if (selected) {
      els.voicevoxCharacter.value = selected;
    }
    if (!selected && characters.length > 0) {
      const firstId = String(characters[0]?.id || "").trim();
      if (firstId) {
        state.voicevox.characterId = firstId;
        els.voicevoxCharacter.value = firstId;
      }
    }
    if (characters.length > 0 && selected && !els.voicevoxCharacter.value) {
      state.voicevox.characterId = "";
    }
  }

  function renderVoicevoxFieldOptions() {
    const sourceOptions = Array.isArray(state.voicevox.sourceFieldOptions) ? state.voicevox.sourceFieldOptions : [];
    const destinationOptions = Array.isArray(state.voicevox.destinationFieldOptions) ? state.voicevox.destinationFieldOptions : [];

    if (els.voicevoxSourceField) {
      const optionsHtml = sourceOptions.length
        ? sourceOptions.map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.label)}</option>`).join("")
        : '<option value="">(Không có trường nguồn)</option>';
      els.voicevoxSourceField.innerHTML = optionsHtml;
      els.voicevoxSourceField.value = String(state.voicevox.sourceField || "");
      if (sourceOptions.length > 0 && !els.voicevoxSourceField.value) {
        state.voicevox.sourceField = sourceOptions[0].name;
        els.voicevoxSourceField.value = state.voicevox.sourceField;
      }
    }

    if (els.voicevoxDestinationField) {
      const optionsHtml = destinationOptions.length
        ? destinationOptions.map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.label)}</option>`).join("")
        : '<option value="">(Không có trường đích)</option>';
      els.voicevoxDestinationField.innerHTML = optionsHtml;
      els.voicevoxDestinationField.value = String(state.voicevox.destinationField || "");
      if (destinationOptions.length > 0 && !els.voicevoxDestinationField.value) {
        state.voicevox.destinationField = destinationOptions[0].name;
        els.voicevoxDestinationField.value = state.voicevox.destinationField;
      }
    }
  }

  function syncVoicevoxInputsFromState() {
    renderVoicevoxCharacterOptions();
    renderVoicevoxFieldOptions();

    if (els.voicevoxCharacter) {
      els.voicevoxCharacter.value = String(state.voicevox.characterId || "");
    }
    if (els.voicevoxVolumeScale) {
      els.voicevoxVolumeScale.value = String(state.voicevox.volumeScale);
    }
    if (els.voicevoxPitch) {
      els.voicevoxPitch.value = String(state.voicevox.pitchScale);
    }
    if (els.voicevoxSpeed) {
      els.voicevoxSpeed.value = String(state.voicevox.speedScale);
    }
    if (els.voicevoxIntonationScale) {
      els.voicevoxIntonationScale.value = String(state.voicevox.intonationScale);
    }
    if (els.voicevoxInitialSilenceScale) {
      els.voicevoxInitialSilenceScale.value = String(state.voicevox.initialSilenceScale);
    }
    if (els.voicevoxFinalSilenceLength) {
      els.voicevoxFinalSilenceLength.value = String(state.voicevox.finalSilenceLength);
    }
    if (els.voicevoxAppendAudio) {
      els.voicevoxAppendAudio.checked = Boolean(state.voicevox.appendAudio);
    }
    if (els.voicevoxUseOpus) {
      els.voicevoxUseOpus.checked = Boolean(state.voicevox.useOpus);
    }
    if (els.voicevoxApiKey) {
      els.voicevoxApiKey.value = String(state.voicevox.apiKey || "");
    }
    syncVoicevoxApiKeyVisibility();
    updateVoicevoxValueLabels();
    updateVoicevoxMetaLabels();
    renderVoicevoxProgressAndFailed();
  }

  function syncVoicevoxApiKeyVisibility() {
    const visible = Boolean(state.voicevox.apiKeyVisible);
    if (els.voicevoxApiKey) {
      els.voicevoxApiKey.type = visible ? "text" : "password";
    }
    if (els.voicevoxApiKeyToggleIcon) {
      els.voicevoxApiKeyToggleIcon.classList.toggle("bi-eye", !visible);
      els.voicevoxApiKeyToggleIcon.classList.toggle("bi-eye-slash", visible);
    }
    if (els.voicevoxApiKeyToggleBtn) {
      const label = visible ? "Ẩn API key" : "Hiển thị API key";
      els.voicevoxApiKeyToggleBtn.setAttribute("aria-label", label);
      els.voicevoxApiKeyToggleBtn.setAttribute("title", label);
    }
  }

  function voicevoxApiKeyOverrideValue() {
    const rawValue = String(state.voicevox.apiKey || "").trim();
    if (!rawValue) {
      return undefined;
    }
    const masked = String(state.voicevox.maskedApiKey || "").trim();
    if (masked && rawValue === masked) {
      return undefined;
    }
    return rawValue;
  }

  function buildVoicevoxDefaultSettings(rawSettings) {
    const settings = rawSettings && typeof rawSettings === "object" ? rawSettings : {};
    return {
      characterId: String(settings?.character_id || "").trim(),
      sourceField: String(settings?.source_field ?? settings?.sourceField ?? "").trim(),
      destinationField: String(settings?.destination_field ?? settings?.destinationField ?? "").trim(),
      appendAudio: normalizeBooleanFlag(settings?.append_audio ?? settings?.appendAudio, false),
      useOpus: normalizeBooleanFlag(settings?.use_opus ?? settings?.useOpus, false),
      volumeScale: clampRange(settings?.volume_scale ?? settings?.volumeScale ?? settings?.volume, 0, 2, 1.0),
      pitchScale: clampRange(settings?.pitch_scale ?? settings?.pitch, -0.4, 0.4, 0.0),
      speedScale: clampRange(settings?.speed_scale ?? settings?.speed, 0.1, 4.0, 1.0),
      intonationScale: clampRange(settings?.intonation_scale ?? settings?.intonationScale, 0, 2, 1.0),
      initialSilenceScale: clampRange(
        settings?.initial_silence_scale ?? settings?.pre_phoneme_length ?? settings?.prePhonemeLength,
        0,
        2,
        0.1,
      ),
      finalSilenceLength: clampRange(
        settings?.final_silence_length ?? settings?.post_phoneme_length ?? settings?.postPhonemeLength,
        0,
        2,
        0.1,
      ),
    };
  }

  function setVoicevoxActionState() {
    const loading =
      state.voicevox.loadingProfile ||
      state.voicevox.loadingCharacters ||
      state.voicevox.validatingKey ||
      state.voicevox.savingSettings ||
      state.voicevox.generating ||
      state.voicevox.previewing;
    const generating = Boolean(state.voicevox.generating);
    const controls = [
      els.voicevoxCharacter,
      els.voicevoxSourceField,
      els.voicevoxDestinationField,
      els.voicevoxVolumeScale,
      els.voicevoxPitch,
      els.voicevoxSpeed,
      els.voicevoxIntonationScale,
      els.voicevoxInitialSilenceScale,
      els.voicevoxFinalSilenceLength,
      els.voicevoxAppendAudio,
      els.voicevoxUseOpus,
      els.voicevoxApiKey,
      els.voicevoxApiKeyToggleBtn,
      els.voicevoxCancelBtn,
      els.voicevoxSaveSettingsBtn,
      els.voicevoxResetDefaultsBtn,
    ];
    for (const control of controls) {
      if (control) {
        control.disabled = loading;
      }
    }
    if (els.voicevoxPreviewBtn) {
      els.voicevoxPreviewBtn.disabled = loading;
      els.voicevoxPreviewBtn.innerHTML = state.voicevox.previewing || state.voicevox.validatingKey
        ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>'
        : '<i class="bi bi-play-fill"></i> Nghe thử giọng đọc';
    }
    if (els.voicevoxGenerateBtn) {
      els.voicevoxGenerateBtn.disabled = loading;
      const showSpinner = state.voicevox.validatingKey || (state.voicevox.generating && state.voicevox.generationMode !== "retry");
      els.voicevoxGenerateBtn.innerHTML = showSpinner
        ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>'
        : "Tạo audio";
    }
    if (els.voicevoxRetryFailedBtn) {
      const failedCount = Array.isArray(state.voicevox.failedNotes) ? state.voicevox.failedNotes.length : 0;
      const showSpinner = state.voicevox.generating && state.voicevox.generationMode === "retry";
      els.voicevoxRetryFailedBtn.disabled = loading || failedCount === 0;
      els.voicevoxRetryFailedBtn.innerHTML = showSpinner
        ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>'
        : "Tạo lại mục lỗi";
    }
    if (els.voicevoxCancelGenerateBtn) {
      els.voicevoxCancelGenerateBtn.classList.toggle("d-none", !generating);
      if (!generating) {
        els.voicevoxCancelGenerateBtn.disabled = true;
        els.voicevoxCancelGenerateBtn.textContent = "Hủy tạo voice";
      } else {
        els.voicevoxCancelGenerateBtn.disabled = Boolean(state.voicevox.cancelRequested);
        els.voicevoxCancelGenerateBtn.textContent = state.voicevox.cancelRequested ? "Đang hủy..." : "Hủy tạo voice";
      }
    }
    if (els.voicevoxSaveSettingsBtn) {
      els.voicevoxSaveSettingsBtn.disabled = loading;
      els.voicevoxSaveSettingsBtn.innerHTML = state.voicevox.savingSettings
        ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>'
        : "Lưu thiết lập";
    }
    renderVoicevoxProgressAndFailed();
  }

  function hydrateVoicevoxFieldOptionsFromDetail() {
    const rawNoteTypeFields = Array.isArray(state.detail?.note_type_fields)
      ? state.detail.note_type_fields
      : Array.isArray(state.detail?.fields)
        ? state.detail.fields.filter((field) => Number(field?.position) < 9999)
        : [];
    if (!rawNoteTypeFields.length) {
      return;
    }

    const sourceCandidates = rawNoteTypeFields
      .filter((field) => {
        const kind = String(field?.field_type || "text").toLowerCase();
        return kind === "text" || kind === "richtext" || kind === "markdown";
      })
      .map((field) => ({
        name: String(field?.name || ""),
        label: String(field?.name || ""),
      }))
      .filter((item) => item.name);

    const destinationCandidates = rawNoteTypeFields
      .map((field) => ({
        name: String(field?.name || ""),
        label: String(field?.name || ""),
        fieldType: String(field?.field_type || "text").toLowerCase(),
      }))
      .filter((item) => item.name);

    if (sourceCandidates.length) {
      state.voicevox.sourceFieldOptions = sourceCandidates;
      const hasCurrent = sourceCandidates.some((item) => item.name === state.voicevox.sourceField);
      if (!hasCurrent) {
        const preferred = sourceCandidates.find((item) => item.name.toLowerCase() === "word");
        state.voicevox.sourceField = (preferred || sourceCandidates[0]).name;
      }
    }

    if (destinationCandidates.length) {
      state.voicevox.destinationFieldOptions = destinationCandidates;
      const hasCurrent = destinationCandidates.some((item) => item.name === state.voicevox.destinationField);
      if (!hasCurrent) {
        const preferredAudio = destinationCandidates.find((item) => item.name.toLowerCase() === "word_audio");
        const firstAudio = destinationCandidates.find((item) => item.fieldType === "audio");
        state.voicevox.destinationField = (preferredAudio || firstAudio || destinationCandidates[0]).name;
      }
    }
    renderVoicevoxFieldOptions();
  }

  function applyVoicevoxProfilePayload(payload) {
    const profile = payload?.profile || {};
    const defaults = buildVoicevoxDefaultSettings(payload?.provider?.default_settings || {});
    const settings = profile?.effective_settings || profile?.settings || {};
    state.voicevox.defaultSettings = defaults;

    state.voicevox.characterId = String(settings?.character_id || defaults.characterId || "").trim();
    state.voicevox.sourceField = String(settings?.source_field || defaults.sourceField || "").trim();
    state.voicevox.destinationField = String(settings?.destination_field || defaults.destinationField || "").trim();
    state.voicevox.appendAudio = normalizeBooleanFlag(settings?.append_audio, defaults.appendAudio);
    state.voicevox.useOpus = normalizeBooleanFlag(settings?.use_opus, defaults.useOpus);
    state.voicevox.volumeScale = clampRange(settings?.volume_scale, 0, 2, defaults.volumeScale);
    state.voicevox.pitchScale = clampRange(settings?.pitch_scale ?? settings?.pitch, -0.4, 0.4, defaults.pitchScale);
    state.voicevox.speedScale = clampRange(settings?.speed_scale ?? settings?.speed, 0.1, 4.0, defaults.speedScale);
    state.voicevox.intonationScale = clampRange(settings?.intonation_scale, 0, 2, defaults.intonationScale);
    state.voicevox.initialSilenceScale = clampRange(
      settings?.initial_silence_scale,
      0,
      2,
      defaults.initialSilenceScale,
    );
    state.voicevox.finalSilenceLength = clampRange(
      settings?.final_silence_length,
      0,
      2,
      defaults.finalSilenceLength,
    );

    state.voicevox.hasApiKey = Boolean(profile?.has_api_key);
    state.voicevox.maskedApiKey = String(profile?.masked_api_key || "").trim();
    state.voicevox.apiKey = state.voicevox.maskedApiKey;
    state.voicevox.apiKeyVisible = false;
    state.voicevox.keyStatus = String(profile?.key_status || "unknown");
    state.voicevox.lastValidationError = String(profile?.last_validation_error || "");
    state.voicevox.lastSavedSettingsHash = JSON.stringify(voicevoxProfileSettingsPayload());
    state.voicevox.settingsDirty = false;
    syncVoicevoxInputsFromState();
  }

  async function loadVoicevoxCharacters() {
    if (state.voicevox.loadingCharacters) {
      return;
    }
    state.voicevox.loadingCharacters = true;
    state.voicevox.characterError = "";
    setVoicevoxActionState();
    updateVoicevoxMetaLabels();

    try {
      const requestBody = {};
      const apiKeyOverride = voicevoxApiKeyOverrideValue();
      if (!state.voicevox.hasApiKey && !apiKeyOverride) {
        state.voicevox.characters = [];
        state.voicevox.characterError = "Vui lòng nhập API key VoiceVox trước khi tải danh sách nhân vật.";
        renderVoicevoxCharacterOptions();
        return;
      }
      if (apiKeyOverride) {
        requestBody.api_key = apiKeyOverride;
      }
      const response = await requestJson("/api/tts/providers/voicevox/voices", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });
      state.voicevox.characters = Array.isArray(response?.items) ? response.items : [];
      renderVoicevoxCharacterOptions();
    } catch (error) {
      state.voicevox.characters = [];
      state.voicevox.characterError = String(error?.message || "Không tải được danh sách nhân vật.");
      renderVoicevoxCharacterOptions();
    } finally {
      state.voicevox.loadingCharacters = false;
      setVoicevoxActionState();
      updateVoicevoxMetaLabels();
    }
  }

  async function ensureVoicevoxProfileLoaded(force = false) {
    if (state.voicevox.loadingProfile) {
      return;
    }
    if (state.voicevox.loadedProfile && !force) {
      hydrateVoicevoxFieldOptionsFromDetail();
      updateVoicevoxSelectedNotesLabel();
      return;
    }
    state.voicevox.loadingProfile = true;
    setVoicevoxActionState();

    try {
      const payload = await requestJson("/api/tts/providers/voicevox/profile");
      applyVoicevoxProfilePayload(payload);
      state.voicevox.loadedProfile = true;
      await loadVoicevoxCharacters();
      hydrateVoicevoxFieldOptionsFromDetail();
      updateVoicevoxSelectedNotesLabel();
    } catch (error) {
      state.voicevox.keyStatus = "unknown";
      state.voicevox.lastValidationError = String(error?.message || "Không thể tải cấu hình VoiceVox.");
      updateVoicevoxMetaLabels();
      window.alert(`Không thể tải cấu hình VoiceVox: ${state.voicevox.lastValidationError}`);
    } finally {
      state.voicevox.loadingProfile = false;
      setVoicevoxActionState();
    }
  }

  function voicevoxSettingsPayload() {
    return {
      volume_scale: state.voicevox.volumeScale,
      pitch_scale: state.voicevox.pitchScale,
      speed_scale: state.voicevox.speedScale,
      intonation_scale: state.voicevox.intonationScale,
      initial_silence_scale: state.voicevox.initialSilenceScale,
      final_silence_length: state.voicevox.finalSilenceLength,
    };
  }

  function voicevoxProfileSettingsPayload() {
    return {
      character_id: String(state.voicevox.characterId || "").trim(),
      source_field: String(state.voicevox.sourceField || "").trim(),
      destination_field: String(state.voicevox.destinationField || "").trim(),
      append_audio: Boolean(state.voicevox.appendAudio),
      use_opus: Boolean(state.voicevox.useOpus),
      volume_scale: state.voicevox.volumeScale,
      pitch_scale: state.voicevox.pitchScale,
      speed_scale: state.voicevox.speedScale,
      intonation_scale: state.voicevox.intonationScale,
      initial_silence_scale: state.voicevox.initialSilenceScale,
      final_silence_length: state.voicevox.finalSilenceLength,
    };
  }

  async function persistVoicevoxSettings({ notify = false } = {}) {
    if (state.voicevox.loadingProfile || !state.voicevox.loadedProfile) {
      return false;
    }
    if (state.voicevox.savingSettings) {
      return false;
    }
    const settings = voicevoxProfileSettingsPayload();
    const nextHash = JSON.stringify(settings);
    const apiKeyOverride = voicevoxApiKeyOverrideValue();
    const hasKeyMutation = Boolean(apiKeyOverride);
    const hasSettingsMutation = state.voicevox.settingsDirty || nextHash !== state.voicevox.lastSavedSettingsHash;
    if (!hasSettingsMutation && !hasKeyMutation) {
      state.voicevox.settingsDirty = false;
      if (notify) {
        window.alert("Thiết lập đã được lưu.");
      }
      return false;
    }
    state.voicevox.savingSettings = true;
    setVoicevoxActionState();
    try {
      const requestBody = {};
      if (hasSettingsMutation) {
        requestBody.settings = settings;
      }
      if (apiKeyOverride) {
        requestBody.api_key = apiKeyOverride;
      }
      const payload = await requestJson("/api/tts/providers/voicevox/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });
      applyVoicevoxProfilePayload(payload);
      if (notify) {
        window.alert("Đã lưu thiết lập VoiceVox.");
      }
      return true;
    } catch (error) {
      if (notify) {
        window.alert(`Lưu thiết lập thất bại: ${error.message}`);
      } else {
        console.warn("VoiceVox settings save failed:", error);
      }
      return false;
    } finally {
      state.voicevox.savingSettings = false;
      setVoicevoxActionState();
    }
  }

  async function ensureVoicevoxApiKeyPersistedForAction(actionLabel) {
    const apiKeyOverride = voicevoxApiKeyOverrideValue();
    if (!state.voicevox.hasApiKey && !apiKeyOverride) {
      window.alert(`Không thể ${actionLabel}: vui lòng nhập API key VoiceVox và lưu trước.`);
      return false;
    }
    if (!apiKeyOverride) {
      return true;
    }
    const saved = await persistVoicevoxSettings();
    if (!saved && !state.voicevox.hasApiKey) {
      window.alert(`Không thể ${actionLabel}: không lưu được API key VoiceVox.`);
      return false;
    }
    return true;
  }

  function resetVoicevoxSettingsToDefault() {
    const defaults = state.voicevox.defaultSettings || buildVoicevoxDefaultSettings({});
    state.voicevox.characterId = String(defaults.characterId || "").trim();
    state.voicevox.sourceField = String(defaults.sourceField || "").trim();
    state.voicevox.destinationField = String(defaults.destinationField || "").trim();
    state.voicevox.appendAudio = Boolean(defaults.appendAudio);
    state.voicevox.useOpus = Boolean(defaults.useOpus);
    state.voicevox.volumeScale = defaults.volumeScale;
    state.voicevox.pitchScale = defaults.pitchScale;
    state.voicevox.speedScale = defaults.speedScale;
    state.voicevox.intonationScale = defaults.intonationScale;
    state.voicevox.initialSilenceScale = defaults.initialSilenceScale;
    state.voicevox.finalSilenceLength = defaults.finalSilenceLength;
    state.voicevox.settingsDirty = true;
    syncVoicevoxInputsFromState();
    persistVoicevoxSettings({ notify: true }).catch(() => undefined);
  }

  async function warnIfDestinationContainsNonAudio(cardIds) {
    const ids = Array.isArray(cardIds) ? cardIds.filter(Boolean) : [];
    if (!ids.length || !state.voicevox.destinationField) {
      return true;
    }
    try {
      const payload = await requestJson("/vocabulary/api/browse/voicevox/precheck", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          card_ids: ids,
          destination_field: state.voicevox.destinationField,
        }),
      });
      if (Boolean(payload?.mixed_note_types)) {
        window.alert("Không thể generate: các từ đã chọn không cùng note_type. Vui lòng chỉ chọn các từ cùng note_type.");
        return false;
      }
      const warningCount = Number(payload?.count || 0);
      if (warningCount <= 0) {
        return true;
      }
      const samples = Array.isArray(payload?.items) ? payload.items : [];
      const sampleText = samples
        .slice(0, 3)
        .map((item) => {
          const noteId = String(item?.note_id || "").trim();
          const sample = String(item?.sample || "").replace(/\s+/g, " ").trim();
          return `- Note ${noteId}: ${sample.slice(0, 40)}${sample.length > 40 ? "..." : ""}`;
        })
        .join("\n");
      const detailText = sampleText ? `\n${sampleText}` : "";
      window.alert(
        `Cảnh báo: có ${warningCount} note đang có dữ liệu không phải âm thanh trong trường '${state.voicevox.destinationField}'.\nHệ thống sẽ tiếp tục tạo audio và ghi đè giá trị cũ.${detailText}`
      );
      return true;
    } catch (error) {
      // Precheck warning is best-effort; generation should still continue.
      console.warn("VoiceVox destination precheck failed:", error);
      return true;
    }
  }

  async function validateVoicevoxApiKeyBeforeAction(actionLabel) {
    if (state.voicevox.validatingKey) {
      return false;
    }
    const keyPersisted = await ensureVoicevoxApiKeyPersistedForAction(actionLabel);
    if (!keyPersisted) {
      return false;
    }
    state.voicevox.validatingKey = true;
    setVoicevoxActionState();
    try {
      const body = {};
      const apiKeyOverride = voicevoxApiKeyOverrideValue();
      if (apiKeyOverride) {
        body.api_key = apiKeyOverride;
      }
      const payload = await requestJson("/api/tts/providers/voicevox/validate-key", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const validation = payload?.validation || {};
      const status = String(validation?.status || "unknown").toLowerCase();
      const valid = Boolean(validation?.valid) && status === "valid";
      const message = String(validation?.message || "").trim();
      state.voicevox.keyStatus = status || "unknown";
      state.voicevox.lastValidationError = valid ? "" : (message || "API key VoiceVox không hợp lệ hoặc đã hết hạn.");
      updateVoicevoxMetaLabels();
      if (!valid) {
        window.alert(`Không thể ${actionLabel}: ${state.voicevox.lastValidationError}`);
      }
      return valid;
    } catch (error) {
      state.voicevox.keyStatus = "unknown";
      state.voicevox.lastValidationError = String(error?.message || "Không thể kiểm tra API key VoiceVox.");
      updateVoicevoxMetaLabels();
      window.alert(`Không thể ${actionLabel}: ${state.voicevox.lastValidationError}`);
      return false;
    } finally {
      state.voicevox.validatingKey = false;
      setVoicevoxActionState();
    }
  }

  function pickVoicevoxPreviewText() {
    if (!state.voicevox.sourceField) {
      return "";
    }
    const sourceField = String(state.voicevox.sourceField);
    const detailValue = String(state.detail?.note?.field_values?.[sourceField] || "").trim();
    if (detailValue) {
      return detailValue;
    }

    const selectedCardIds = selectedVoicevoxCardIds();
    if (!selectedCardIds.length) {
      return "";
    }
    const selectedCardId = selectedCardIds[0];
    const selectedRow = state.rows.find((row) => row.card_id === selectedCardId);
    if (!selectedRow) {
      return "";
    }
    return String(selectedRow.word || "").trim();
  }

  async function previewVoicevoxAudio() {
    if (
      state.voicevox.previewing ||
      state.voicevox.generating ||
      state.voicevox.savingSettings ||
      state.voicevox.loadingProfile ||
      state.voicevox.validatingKey
    ) {
      return;
    }
    const characterId = String(state.voicevox.characterId || "").trim();
    const previewText = pickVoicevoxPreviewText();
    if (!characterId) {
      window.alert("Vui lòng chọn nhân vật trước khi nghe thử.");
      return;
    }
    if (!previewText) {
      window.alert("Không có văn bản trong trường nguồn để nghe thử.");
      return;
    }
    const keyValid = await validateVoicevoxApiKeyBeforeAction("nghe thử audio");
    if (!keyValid) {
      return;
    }

    state.voicevox.previewing = true;
    setVoicevoxActionState();
    try {
      const response = await fetch("/vocabulary/api/browse/voicevox/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: previewText,
          character_id: characterId,
          settings: voicevoxSettingsPayload(),
          use_opus: Boolean(state.voicevox.useOpus),
          api_key: voicevoxApiKeyOverrideValue(),
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.error || "Preview thất bại.");
      }
      resetVoicevoxPreviewPlayer();
      const blob = await response.blob();
      if (!blob.size) {
        throw new Error("VoiceVox trả về audio rỗng.");
      }
      const blobType = String(blob.type || "").toLowerCase();
      if (blobType.includes("json") || blobType.includes("text/plain")) {
        const rawText = await blob.text().catch(() => "");
        let previewError = rawText.trim();
        if (previewError) {
          try {
            const parsed = JSON.parse(previewError);
            previewError = String(parsed?.error || parsed?.message || previewError).trim();
          } catch (parseError) {
            // Keep raw body text when response is not JSON.
          }
        }
        throw new Error(previewError || "VoiceVox không trả audio hợp lệ cho preview.");
      }
      const audioUrl = window.URL.createObjectURL(blob);
      state.voicevox.previewObjectUrl = audioUrl;

      if (!els.voicevoxPreviewPlayer) {
        throw new Error("Không tìm thấy audio preview player.");
      }

      els.voicevoxPreviewPlayer.src = audioUrl;
      els.voicevoxPreviewPlayer.loop = false;
      els.voicevoxPreviewPlayer.classList.add("d-none");
      els.voicevoxPreviewPlayer.addEventListener("ended", () => {
        resetVoicevoxPreviewPlayer();
      }, { once: true });
      try {
        await els.voicevoxPreviewPlayer.play();
      } catch (playError) {
        throw playError;
      }
    } catch (error) {
      window.alert(`Nghe thử VoiceVox thất bại: ${error.message}`);
    } finally {
      state.voicevox.previewing = false;
      setVoicevoxActionState();
    }
  }

  function selectedVoiceLabel() {
    const selectedId = String(state.voicevox.characterId || "");
    const item = state.voicevox.characters.find((voice) => String(voice?.id || "") === selectedId);
    if (!item) {
      return { speaker: selectedId, style: "" };
    }
    const label = String(item.label || selectedId);
    const [speaker, style] = label.split(" - ");
    return {
      speaker: String(speaker || selectedId).trim(),
      style: String(style || "").trim(),
    };
  }

  function collectVoicevoxTargetsFromFailedNotes() {
    const failedNotes = dedupeVoicevoxFailedNotes(state.voicevox.failedNotes);
    const rowByNoteId = new Map();
    const rowByCardId = new Map();
    for (const row of state.rows) {
      const cardId = String(row.card_id || "").trim();
      const noteId = String(row.note_id || "").trim();
      if (cardId) {
        rowByCardId.set(cardId, row);
      }
      if (noteId && !rowByNoteId.has(noteId)) {
        rowByNoteId.set(noteId, row);
      }
    }

    const targets = [];
    const seenKeys = new Set();
    for (const failed of failedNotes) {
      let cardId = String(failed.cardId || "").trim();
      const noteId = String(failed.noteId || "").trim();
      if (!cardId && noteId) {
        cardId = String(rowByNoteId.get(noteId)?.card_id || "").trim();
      }
      if (!cardId && String(failed.key || "").startsWith("card:")) {
        cardId = String(failed.key || "").slice(5).trim();
      }
      if (!cardId) {
        continue;
      }
      const row = rowByCardId.get(cardId) || rowByNoteId.get(noteId);
      const resolvedNoteId = noteId || String(row?.note_id || "").trim();
      const key = voicevoxTargetKeyFromIds(resolvedNoteId, cardId);
      if (!key || seenKeys.has(key)) {
        continue;
      }
      seenKeys.add(key);
      targets.push(
        {
          key,
          cardId,
          noteId: resolvedNoteId,
          word: String(failed.word || row?.word || "").trim(),
          reading: String(failed.reading || row?.reading || "").trim(),
        }
      );
    }
    return targets;
  }

  function resetVoicevoxProgressCounters(total, mode) {
    state.voicevox.progressTotal = Math.max(0, Number(total || 0));
    state.voicevox.progressProcessed = 0;
    state.voicevox.progressGenerated = 0;
    state.voicevox.progressFailed = 0;
    state.voicevox.progressMessage = mode === "retry" ? "Đang tạo lại mục lỗi..." : "Đang tạo audio...";
    renderVoicevoxProgressAndFailed();
  }

  function clearVoicevoxGenerateController(controller) {
    if (controller) {
      if (state.controllers[VOICEVOX_GENERATE_CONTROLLER_KEY] === controller) {
        delete state.controllers[VOICEVOX_GENERATE_CONTROLLER_KEY];
      }
      return;
    }
    if (state.controllers[VOICEVOX_GENERATE_CONTROLLER_KEY]) {
      delete state.controllers[VOICEVOX_GENERATE_CONTROLLER_KEY];
    }
  }

  function cancelVoicevoxGenerate() {
    if (!state.voicevox.generating || state.voicevox.cancelRequested) {
      return;
    }
    state.voicevox.cancelRequested = true;
    state.voicevox.progressMessage = "Đang hủy...";
    renderVoicevoxProgressAndFailed();
    const controller = state.controllers[VOICEVOX_GENERATE_CONTROLLER_KEY];
    if (controller) {
      controller.abort();
      clearVoicevoxGenerateController(controller);
    }
    setVoicevoxActionState();
  }

  async function runVoicevoxGenerateBatches(targets, mode) {
    const voiceLabel = selectedVoiceLabel();
    const safeTargets = Array.isArray(targets) ? targets : [];
    const batches = chunkArray(safeTargets, state.voicevox.batchSize || VOICEVOX_BATCH_SIZE);
    const retryKeys = new Set(safeTargets.map((item) => String(item?.key || "")));
    const failedFromRun = [];
    let fatalStopReason = "";
    let cancelledByUser = false;

    state.voicevox.cancelRequested = false;
    resetVoicevoxProgressCounters(safeTargets.length, mode);
    if (mode !== "retry") {
      state.voicevox.failedNotes = [];
    }
    renderVoicevoxProgressAndFailed();

    for (let batchIndex = 0; batchIndex < batches.length; batchIndex += 1) {
      if (state.voicevox.cancelRequested) {
        cancelledByUser = true;
        break;
      }
      const batchTargets = batches[batchIndex];
      if (!batchTargets.length) {
        continue;
      }
      const targetByNoteId = new Map();
      for (const target of batchTargets) {
        if (target.noteId) {
          targetByNoteId.set(String(target.noteId), target);
        }
      }

      let batchFailed = [];
      try {
        const controller = withAbortController(VOICEVOX_GENERATE_CONTROLLER_KEY);
        let payload;
        try {
          payload = await requestJson("/vocabulary/api/browse/voicevox/generate", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            signal: controller.signal,
            body: JSON.stringify({
              card_ids: batchTargets.map((item) => item.cardId),
              source_field: state.voicevox.sourceField,
              destination_field: state.voicevox.destinationField,
              character_id: state.voicevox.characterId,
              settings: voicevoxSettingsPayload(),
              append_audio: Boolean(state.voicevox.appendAudio),
              use_opus: Boolean(state.voicevox.useOpus),
              speaker_label: voiceLabel.speaker,
              style_label: voiceLabel.style,
              api_key: voicevoxApiKeyOverrideValue(),
            }),
          });
        } finally {
          clearVoicevoxGenerateController(controller);
        }

        if (state.voicevox.cancelRequested) {
          cancelledByUser = true;
          break;
        }

        state.voicevox.outputRoot = String(payload?.output_root || state.voicevox.outputRoot || "");
        const skipped = Array.isArray(payload?.skipped) ? payload.skipped : [];
        const usedTargetKeys = new Set();
        for (const skippedItem of skipped) {
          const noteId = String(skippedItem?.note_id || "").trim();
          const target = noteId ? targetByNoteId.get(noteId) : null;
          if (!target) {
            continue;
          }
          usedTargetKeys.add(target.key);
          batchFailed.push(buildVoicevoxFailedNote(target, skippedItem?.reason || "Không tạo được audio."));
        }
        if (batchFailed.length < skipped.length) {
          const fallbackTargets = batchTargets.filter((item) => !usedTargetKeys.has(item.key));
          for (let index = batchFailed.length; index < skipped.length && fallbackTargets.length; index += 1) {
            const target = fallbackTargets.shift();
            if (!target) {
              break;
            }
            const skippedItem = skipped[index];
            batchFailed.push(buildVoicevoxFailedNote(target, skippedItem?.reason || "Không tạo được audio."));
          }
        }
      } catch (error) {
        if (error?.name === "AbortError" || state.voicevox.cancelRequested) {
          cancelledByUser = true;
          break;
        }
        const batchReason = String(error?.message || "Generate VoiceVox thất bại.");
        batchFailed = batchTargets.map((item) => buildVoicevoxFailedNote(item, batchReason));
      }

      const normalizedBatchFailed = dedupeVoicevoxFailedNotes(batchFailed);
      failedFromRun.push(...normalizedBatchFailed);

      const batchFailedCount = Math.min(batchTargets.length, normalizedBatchFailed.length);
      const batchGeneratedCount = Math.max(0, batchTargets.length - batchFailedCount);
      state.voicevox.progressProcessed += batchTargets.length;
      state.voicevox.progressGenerated += batchGeneratedCount;
      state.voicevox.progressFailed += batchFailedCount;
      state.voicevox.progressMessage = `Batch ${batchIndex + 1}/${batches.length}`;
      renderVoicevoxProgressAndFailed();

      if (state.voicevox.cancelRequested) {
        cancelledByUser = true;
        break;
      }

      const keyErrorItem = normalizedBatchFailed.find((item) => isVoicevoxKeyOrPointError(item.reason));
      if (!keyErrorItem) {
        continue;
      }

      fatalStopReason = String(keyErrorItem.reason || "").trim();
      if (batchIndex < batches.length - 1) {
        const remainingTargets = batches.slice(batchIndex + 1).flat();
        const stopReason = fatalStopReason
          ? `Chưa xử lý do lỗi key/points: ${fatalStopReason}`
          : "Chưa xử lý do lỗi key/points.";
        for (const target of remainingTargets) {
          failedFromRun.push(buildVoicevoxFailedNote(target, stopReason));
        }
        state.voicevox.progressProcessed += remainingTargets.length;
        state.voicevox.progressFailed += remainingTargets.length;
      }
      break;
    }

    if (mode === "retry") {
      const untouched = dedupeVoicevoxFailedNotes(state.voicevox.failedNotes).filter((item) => !retryKeys.has(item.key));
      state.voicevox.failedNotes = dedupeVoicevoxFailedNotes(untouched.concat(failedFromRun));
    } else {
      state.voicevox.failedNotes = dedupeVoicevoxFailedNotes(failedFromRun);
    }

    if (cancelledByUser || state.voicevox.cancelRequested) {
      state.voicevox.progressMessage = "Đã hủy bởi người dùng.";
    } else {
      state.voicevox.progressMessage = fatalStopReason ? "Đã dừng sớm vì key/points." : "Hoàn tất.";
    }
    renderVoicevoxProgressAndFailed();

    const processed = Number(state.voicevox.progressProcessed || 0);
    const total = Number(state.voicevox.progressTotal || 0);
    const generated = Number(state.voicevox.progressGenerated || 0);
    const failed = Number(state.voicevox.progressFailed || 0);
    let summary = (cancelledByUser || state.voicevox.cancelRequested)
      ? `Đã hủy tạo audio. Đã xử lý ${processed}/${total} từ. Thành công ${generated}, lỗi ${failed}.`
      : `Đã xử lý ${processed}/${total} từ. Thành công ${generated}, lỗi ${failed}.`;
    if (failed > 0) {
      summary += '\nBạn có thể bấm "Tạo lại mục lỗi" sau khi đổi API key.';
    }
    if (fatalStopReason) {
      summary += `\nChi tiết: ${fatalStopReason}`;
    }
    window.alert(summary);

    await loadCards({ reset: true, keepSelection: true });
    if (state.selectedCardId) {
      await loadCardDetail(state.selectedCardId);
    }
    hydrateVoicevoxFieldOptionsFromDetail();
    updateVoicevoxSelectedNotesLabel();
  }

  async function generateVoicevoxAudio() {
    if (
      state.voicevox.generating ||
      state.voicevox.loadingProfile ||
      state.voicevox.previewing ||
      state.voicevox.savingSettings ||
      state.voicevox.validatingKey
    ) {
      return;
    }
    const cardIds = selectedVoicevoxCardIds();
    if (!cardIds.length) {
      window.alert("Vui lòng chọn note hoặc card trước khi tạo audio.");
      return;
    }
    if (!state.voicevox.sourceField || !state.voicevox.destinationField) {
      window.alert("Vui lòng chọn trường nguồn và trường đích.");
      return;
    }
    if (!state.voicevox.characterId) {
      window.alert("Vui lòng chọn nhân vật.");
      return;
    }
    const targets = collectVoicevoxTargetsFromCardIds(cardIds);
    if (!targets.length) {
      window.alert("Không có note hợp lệ để tạo audio.");
      return;
    }
    const keyValid = await validateVoicevoxApiKeyBeforeAction("tạo audio");
    if (!keyValid) {
      return;
    }
    const canProceed = await warnIfDestinationContainsNonAudio(targets.map((item) => item.cardId));
    if (!canProceed) {
      return;
    }

    state.voicevox.cancelRequested = false;
    state.voicevox.generating = true;
    state.voicevox.generationMode = "all";
    setVoicevoxActionState();
    try {
      await runVoicevoxGenerateBatches(targets, "all");
    } catch (error) {
      window.alert(`Tạo audio VoiceVox thất bại: ${error.message}`);
    } finally {
      clearVoicevoxGenerateController();
      state.voicevox.cancelRequested = false;
      state.voicevox.generating = false;
      state.voicevox.generationMode = "";
      setVoicevoxActionState();
    }
  }

  async function retryFailedVoicevoxAudio() {
    if (
      state.voicevox.generating ||
      state.voicevox.loadingProfile ||
      state.voicevox.previewing ||
      state.voicevox.savingSettings ||
      state.voicevox.validatingKey
    ) {
      return;
    }
    if (!state.voicevox.sourceField || !state.voicevox.destinationField) {
      window.alert("Vui lòng chọn trường nguồn và trường đích.");
      return;
    }
    if (!state.voicevox.characterId) {
      window.alert("Vui lòng chọn nhân vật.");
      return;
    }

    const targets = collectVoicevoxTargetsFromFailedNotes();
    if (!targets.length) {
      window.alert("Không có mục lỗi hợp lệ để tạo lại.");
      return;
    }

    const keyValid = await validateVoicevoxApiKeyBeforeAction("tạo lại audio bị lỗi");
    if (!keyValid) {
      return;
    }
    const canProceed = await warnIfDestinationContainsNonAudio(targets.map((item) => item.cardId));
    if (!canProceed) {
      return;
    }

    state.voicevox.cancelRequested = false;
    state.voicevox.generating = true;
    state.voicevox.generationMode = "retry";
    setVoicevoxActionState();
    try {
      await runVoicevoxGenerateBatches(targets, "retry");
    } catch (error) {
      window.alert(`Tạo lại mục lỗi thất bại: ${error.message}`);
    } finally {
      clearVoicevoxGenerateController();
      state.voicevox.cancelRequested = false;
      state.voicevox.generating = false;
      state.voicevox.generationMode = "";
      setVoicevoxActionState();
    }
  }

  function setAudioCreateMenuOpen(open) {
    if (!els.audioCreateMenu) {
      return;
    }
    els.audioCreateMenu.classList.toggle("d-none", !open);
  }

  function setVoicevoxModalOpen(open) {
    if (!els.voicevoxModal) {
      return;
    }
    if (!open && state.voicevox.generating) {
      window.alert('Đang tạo audio. Bấm "Hủy tạo voice" để dừng trước khi đóng modal.');
      return;
    }
    els.voicevoxModal.classList.toggle("d-none", !open);
    if (open) {
      const cardIds = selectedVoicevoxCardIds();
      if (!state.detail && cardIds.length) {
        loadCardDetail(cardIds[0]).catch(() => undefined);
      }
      hydrateVoicevoxFieldOptionsFromDetail();
      updateVoicevoxSelectedNotesLabel();
      renderVoicevoxProgressAndFailed();
      ensureVoicevoxProfileLoaded(false).catch(() => undefined);
      return;
    }
    persistVoicevoxSettings().catch(() => undefined);
    resetVoicevoxPreviewPlayer();
    state.voicevox.apiKeyVisible = false;
    syncVoicevoxApiKeyVisibility();
    updateVoicevoxSelectedNotesLabel();
    renderVoicevoxProgressAndFailed();
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
      els.shortcutCurrent.title = disabled ? "Không có deck hiện tại trong ngữ cảnh màn hình này" : "Chuyển nhanh về deck hiện tại";
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
          <td colspan="${state.checkboxMode ? "8" : "7"}" class="browse-empty-cell">Không có thẻ nào khớp deck hoặc bộ lọc hiện tại.</td>
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
            ${state.checkboxMode
            ? `<td class="browse-select-col" data-label="Chọn"><input type="checkbox" class="form-check-input browse-row-checkbox" data-card-id="${escapeHtml(row.card_id)}" ${selected ? "checked" : ""}></td>`
            : ""
          }
            <td data-label="Loại thẻ" title="${escapeHtml(row.card_type || "")}">${escapeHtml(row.card_type || "")}</td>
            <td data-label="Đến hạn" title="${escapeHtml(row.due_label || "")}">${escapeHtml(row.due_label || "")}</td>
            <td data-label="Deck" title="${escapeHtml(row.deck_name || "")}">${escapeHtml(row.deck_name || "")}</td>
            <td data-label="Từ" title="${escapeHtml(row.word || "")}">${escapeHtml(truncateDisplay(row.word || "", 120))}</td>
            <td data-label="Cách đọc" title="${escapeHtml(row.reading || "")}">${escapeHtml(truncateDisplay(row.reading || "", 120))}</td>
            <td data-label="Nghĩa" title="${escapeHtml(row.meaning || "")}">${escapeHtml(truncateDisplay(row.meaning || "", 200))}</td>
            <td data-label="Tags" title="${escapeHtml(tags)}">${escapeHtml(truncateDisplay(tags, 120))}</td>
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
    const suffix = state.hasNext ? " | còn nữa..." : "";
    const selectedCount = state.selectedCardIds.size;
    const selectedText = selectedCount ? ` | đã chọn: ${selectedCount}` : "";
    els.tableMeta.textContent = `${loaded}/${total} thẻ${selectedText}${suffix}`;
    if (els.bulkDeleteBtn) {
      els.bulkDeleteBtn.disabled = selectedCount === 0;
    }
    updateVoicevoxSelectedNotesLabel();
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
              ? `Tệp: ${escapeHtml(media.filename || media.id || "")}`
              : "Chưa có media đính kèm.";
            const allowPreviewBtn = type !== "audio";
            const previewBtn = media && allowPreviewBtn
              ? `<a class="btn btn-sm btn-outline-secondary browse-editor-media-preview" href="${escapeHtml(media.url || "#")}" target="_blank" rel="noopener">Xem trước</a>`
              : "";
            return `
              <div class="browse-editor-field">
                <label>${escapeHtml(name)} ${requiredBadge}</label>
                <input type="text" ${commonAttrs} class="form-control form-control-sm" value="${escapeHtml(value)}" placeholder="ID media hoặc URL">
                <div class="browse-editor-media-meta">${mediaMeta}</div>
                <div class="browse-editor-media-actions">
                  ${previewBtn}
                  <input type="file" class="form-control form-control-sm" data-upload-field="${escapeHtml(name)}" />
                </div>
              </div>
            `;
          }

          const isMarkdown = type === "markdown";
          const markdownHint = "";
          const markdownPreview = isMarkdown
            ? `<div class="browse-editor-markdown-preview" data-markdown-preview-for="${escapeHtml(name)}"></div>`
            : "";

          return `
            <div class="browse-editor-field">
              <label>${escapeHtml(name)} ${requiredBadge}</label>
              <textarea rows="${isMarkdown ? "7" : "2"}" ${commonAttrs} data-markdown-inline="${isMarkdown ? "1" : "0"}">${escapeHtml(value)}</textarea>
              ${markdownHint}
              ${markdownPreview}
            </div>
          `;
        })
        .join("");

      els.editorFields.innerHTML = fieldsHtml;
      refreshMarkdownPreviewsInEditor();
    }

    setSaveButtons();
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
      resetBrowseMarkdownEditors();
      return;
    }

    const detail = state.detail;
    const draft = state.draft;

    if (els.editorDeck) {
      const options = ['<option value="">(No deck)</option>'];
      const appendOptions = (nodes, depth) => {
        nodes.forEach((node) => {
          const indent = depth > 0 ? `${"&nbsp;".repeat(depth * 3)}&boxvr;&nbsp;` : "";
          const selected = String(draft.deck_id || "") === String(node.id) ? " selected" : "";
          options.push(`<option value="${escapeHtml(String(node.id))}"${selected}>${indent}${escapeHtml(node.name)}</option>`);
          appendOptions(node.children || [], depth + 1);
        });
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
              ? `Tệp: ${escapeHtml(media.filename || media.id || "")}`
              : "Chưa có media đính kèm.";
            const allowPreviewBtn = type !== "audio";
            const previewBtn = media && allowPreviewBtn
              ? `<a class="btn btn-sm btn-outline-secondary browse-editor-media-preview" href="${escapeHtml(media.url || "#")}" target="_blank" rel="noopener">Xem trước</a>`
              : "";
            return `
              <div class="browse-editor-field">
                <label>${escapeHtml(name)} ${requiredBadge}</label>
                <input type="text" ${commonAttrs} class="form-control form-control-sm" value="${escapeHtml(value)}" placeholder="ID media hoặc URL">
                <div class="browse-editor-media-meta">${mediaMeta}</div>
                <div class="browse-editor-media-actions">
                  ${previewBtn}
                  <input type="file" class="form-control form-control-sm" data-upload-field="${escapeHtml(name)}" />
                </div>
              </div>
            `;
          }

          if (type === "markdown") {
            return `
              <div class="browse-editor-field">
                <label>${escapeHtml(name)} ${requiredBadge}</label>
                <div data-browse-markdown-mount="${escapeHtml(name)}"></div>
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
      initBrowseMarkdownEditors(detail.fields || [], draft.field_values || {});
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
    const requestSeq = state.rowsRequestSeq + 1;
    state.rowsRequestSeq = requestSeq;
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
      if (requestSeq !== state.rowsRequestSeq) {
        return;
      }
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
      if (requestSeq !== state.rowsRequestSeq) {
        return;
      }
      if (error.name !== "AbortError") {
        els.tableBody.innerHTML = `
          <tr>
            <td colspan="${state.checkboxMode ? "8" : "7"}" class="browse-empty-cell text-danger">${escapeHtml(error.message)}</td>
          </tr>
        `;
        renderTableMeta();
      }
    } finally {
      if (requestSeq === state.rowsRequestSeq) {
        setRowsLoading(false);
      }
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
      hydrateVoicevoxFieldOptionsFromDetail();
      updateVoicevoxSelectedNotesLabel();
    } catch (error) {
      if (error.name !== "AbortError") {
        state.detail = null;
        state.draft = null;
        state.isDirty = false;
        state.dirtyFields.clear();
        renderEditor();
        updateVoicevoxSelectedNotesLabel();
        window.alert(`Không tải được chi tiết thẻ: ${error.message}`);
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
      const payload = {};
      if (state.dirtyFields.has("__deck__")) {
        payload.deck_id = state.draft.deck_id === "" ? null : Number(state.draft.deck_id);
      }
      if (state.dirtyFields.has("__tags__")) {
        payload.tags = Array.isArray(state.draft.tags) ? state.draft.tags : [];
      }
      const changedFieldValues = {};
      for (const fieldName of state.dirtyFields) {
        if (!fieldName || String(fieldName).startsWith("__")) {
          continue;
        }
        changedFieldValues[fieldName] = state.draft.field_values?.[fieldName] ?? "";
      }
      if (Object.keys(changedFieldValues).length > 0) {
        payload.field_values = changedFieldValues;
      }
      if (Object.keys(payload).length === 0) {
        return true;
      }

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
      window.alert(`Lưu thay đổi thất bại: ${error.message}`);
      return false;
    } finally {
      if (els.saveBtn) {
        els.saveBtn.innerHTML = "Lưu";
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

  async function uploadMarkdownInlineMedia(fieldName, file, textarea) {
    if (!state.detail || !state.detail.note || !state.detail.note.id || !fieldName || !isImageFile(file)) {
      return;
    }
    if (!(textarea instanceof HTMLTextAreaElement)) {
      return;
    }

    const noteId = String(state.detail.note.id || "");
    const formData = new FormData();
    formData.append("field_name", fieldName);
    formData.append("file", file);

    textarea.disabled = true;
    try {
      const payload = await requestJson(`/api/notes/${encodeURIComponent(noteId)}/markdown-media`, {
        method: "POST",
        body: formData,
      });
      insertMarkdownImageSyntax(textarea, payload.url, payload.filename || file.name);
      updateDraftField(fieldName, textarea.value);
      syncMarkdownPreviewForTextarea(textarea);
    } catch (error) {
      window.alert(`Markdown image upload failed: ${error.message}`);
    } finally {
      textarea.disabled = false;
      textarea.classList.remove("is-dragover");
    }
  }

  async function uploadMarkdownInlineMedia(fieldName, file, editor) {
    if (!state.detail || !state.detail.note || !state.detail.note.id || !fieldName || !isImageFile(file)) {
      throw new Error("Markdown upload is unavailable.");
    }

    const noteId = String(state.detail.note.id || "");
    const formData = new FormData();
    formData.append("field_name", fieldName);
    formData.append("file", file);

    const payload = await requestJson(`/api/notes/${encodeURIComponent(noteId)}/markdown-media`, {
      method: "POST",
      body: formData,
    });
    if (editor && typeof editor.getValue === "function") {
      window.setTimeout(() => {
        updateDraftField(fieldName, editor.getValue());
      }, 0);
    }
    return payload;
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
      renderTableMeta();
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
    hydrateVoicevoxFieldOptionsFromDetail();
    updateVoicevoxSelectedNotesLabel();
    renderVoicevoxProgressAndFailed();

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
    applyInputAutofillGuard(els.deckSearch);
    applyInputAutofillGuard(els.keyword);
    applyInputAutofillGuard(els.tag);
    applyInputAutofillGuard(els.voicevoxApiKey, { password: true });
    syncVoicevoxInputsFromState();
    setVoicevoxActionState();
    const debouncedVoicevoxReload = debounce(() => {
      loadVoicevoxCharacters().catch(() => undefined);
    }, 420);
    const debouncedPersistVoicevoxSettings = debounce(() => {
      persistVoicevoxSettings().catch(() => undefined);
    }, 500);

    document.addEventListener("click", (event) => {
      const trigger = event.target.closest('[data-browse-open="1"]');
      if (!trigger) {
        if (!event.target.closest(".browse-voicevox")) {
          setAudioCreateMenuOpen(false);
        }
      } else {
        event.preventDefault();
        openBrowseFromTrigger(trigger);
      }
    });

    if (els.audioCreateBtn) {
      els.audioCreateBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const willOpen = els.audioCreateMenu?.classList.contains("d-none");
        setAudioCreateMenuOpen(Boolean(willOpen));
      });
    }

    if (els.voicevoxOptionBtn) {
      els.voicevoxOptionBtn.addEventListener("click", (event) => {
        event.preventDefault();
        setAudioCreateMenuOpen(false);
        setVoicevoxModalOpen(true);
      });
    }

    if (els.voicevoxModalBackdrop) {
      els.voicevoxModalBackdrop.addEventListener("click", () => {
        setVoicevoxModalOpen(false);
      });
    }

    if (els.voicevoxModalCloseBtn) {
      els.voicevoxModalCloseBtn.addEventListener("click", () => {
        setVoicevoxModalOpen(false);
      });
    }

    if (els.voicevoxCancelBtn) {
      els.voicevoxCancelBtn.addEventListener("click", () => {
        setVoicevoxModalOpen(false);
      });
    }
    if (els.voicevoxCancelGenerateBtn) {
      els.voicevoxCancelGenerateBtn.addEventListener("click", () => {
        cancelVoicevoxGenerate();
      });
    }
    if (els.voicevoxGenerateBtn) {
      els.voicevoxGenerateBtn.addEventListener("click", () => {
        generateVoicevoxAudio().catch(() => undefined);
      });
    }
    if (els.voicevoxRetryFailedBtn) {
      els.voicevoxRetryFailedBtn.addEventListener("click", () => {
        retryFailedVoicevoxAudio().catch(() => undefined);
      });
    }
    if (els.voicevoxPreviewBtn) {
      els.voicevoxPreviewBtn.addEventListener("click", () => {
        previewVoicevoxAudio().catch(() => undefined);
      });
    }
    if (els.voicevoxSaveSettingsBtn) {
      els.voicevoxSaveSettingsBtn.addEventListener("click", () => {
        persistVoicevoxSettings({ notify: true }).catch(() => undefined);
      });
    }
    if (els.voicevoxResetDefaultsBtn) {
      els.voicevoxResetDefaultsBtn.addEventListener("click", () => {
        resetVoicevoxSettingsToDefault();
      });
    }
    if (els.voicevoxCharacter) {
      els.voicevoxCharacter.addEventListener("change", () => {
        state.voicevox.characterId = String(els.voicevoxCharacter.value || "").trim();
        state.voicevox.settingsDirty = true;
        debouncedPersistVoicevoxSettings();
      });
    }
    if (els.voicevoxSourceField) {
      els.voicevoxSourceField.addEventListener("change", () => {
        state.voicevox.sourceField = String(els.voicevoxSourceField.value || "").trim();
        state.voicevox.settingsDirty = true;
        debouncedPersistVoicevoxSettings();
      });
    }
    if (els.voicevoxDestinationField) {
      els.voicevoxDestinationField.addEventListener("change", () => {
        state.voicevox.destinationField = String(els.voicevoxDestinationField.value || "").trim();
        state.voicevox.settingsDirty = true;
        debouncedPersistVoicevoxSettings();
      });
    }
    if (els.voicevoxAppendAudio) {
      els.voicevoxAppendAudio.addEventListener("change", () => {
        state.voicevox.appendAudio = Boolean(els.voicevoxAppendAudio.checked);
        state.voicevox.settingsDirty = true;
        debouncedPersistVoicevoxSettings();
      });
    }
    if (els.voicevoxUseOpus) {
      els.voicevoxUseOpus.addEventListener("change", () => {
        state.voicevox.useOpus = Boolean(els.voicevoxUseOpus.checked);
        state.voicevox.settingsDirty = true;
        debouncedPersistVoicevoxSettings();
      });
    }
    if (els.voicevoxApiKey) {
      els.voicevoxApiKey.addEventListener("input", () => {
        if (!isModalShown()) {
          return;
        }
        state.voicevox.apiKey = String(els.voicevoxApiKey.value || "").trim();
        state.voicevox.keyStatus = "unknown";
        state.voicevox.lastValidationError = "";
        updateVoicevoxMetaLabels();
        debouncedVoicevoxReload();
      });
      els.voicevoxApiKey.addEventListener("change", () => {
        if (!isModalShown()) {
          return;
        }
        persistVoicevoxSettings().catch(() => undefined);
      });
    }
    if (els.voicevoxApiKeyToggleBtn) {
      els.voicevoxApiKeyToggleBtn.addEventListener("click", () => {
        state.voicevox.apiKeyVisible = !state.voicevox.apiKeyVisible;
        syncVoicevoxApiKeyVisibility();
      });
    }

    const bindVoicevoxRange = (el, fieldName, minimum, maximum, fallback) => {
      if (!el) {
        return;
      }
      el.addEventListener("input", () => {
        state.voicevox[fieldName] = clampRange(el.value, minimum, maximum, fallback);
        state.voicevox.settingsDirty = true;
        updateVoicevoxValueLabels();
        debouncedPersistVoicevoxSettings();
      });
    };
    bindVoicevoxRange(els.voicevoxVolumeScale, "volumeScale", 0, 2, 1.0);
    bindVoicevoxRange(els.voicevoxPitch, "pitchScale", -0.4, 0.4, 0.0);
    bindVoicevoxRange(els.voicevoxIntonationScale, "intonationScale", 0, 2, 1.0);
    bindVoicevoxRange(els.voicevoxSpeed, "speedScale", 0.1, 4.0, 1.0);
    bindVoicevoxRange(els.voicevoxInitialSilenceScale, "initialSilenceScale", 0, 2, 0.1);
    bindVoicevoxRange(els.voicevoxFinalSilenceLength, "finalSilenceLength", 0, 2, 0.1);

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

    modalEl.addEventListener("hidden.bs.modal", () => {
      resetBrowseMarkdownEditors();
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
        if (!isModalShown()) {
          return;
        }
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
      if (!isModalShown()) {
        return;
      }
      loadCards({ reset: true, keepSelection: true }).catch(() => undefined);
    }, 280);

    if (els.keyword) {
      els.keyword.addEventListener("input", () => {
        if (!isModalShown()) {
          return;
        }
        state.query.keyword = String(els.keyword.value || "");
        debouncedFilterReload();
      });
    }

    if (els.status) {
      els.status.addEventListener("change", () => {
        if (!isModalShown()) {
          return;
        }
        state.query.status = String(els.status.value || "all");
        loadCards({ reset: true, keepSelection: true }).catch(() => undefined);
      });
    }

    if (els.tag) {
      els.tag.addEventListener("input", () => {
        if (!isModalShown()) {
          return;
        }
        state.query.tag = String(els.tag.value || "");
        debouncedFilterReload();
      });
    }

    if (els.sortBy) {
      els.sortBy.addEventListener("change", () => {
        if (!isModalShown()) {
          return;
        }
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
          if (fieldTarget instanceof HTMLTextAreaElement && fieldTarget.dataset.markdownInline === "1") {
            syncMarkdownPreviewForTextarea(fieldTarget);
          }
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

      els.editorForm.addEventListener("paste", (event) => {
        const textarea = event.target.closest('textarea[data-markdown-inline="1"][data-browse-field]');
        if (!(textarea instanceof HTMLTextAreaElement)) {
          return;
        }
        const fieldName = String(textarea.dataset.browseField || "").trim();
        if (!fieldName) {
          return;
        }
        const imageFile = imageFileFromClipboardData(event.clipboardData);
        if (!imageFile) {
          return;
        }
        event.preventDefault();
        uploadMarkdownInlineMedia(fieldName, imageFile, textarea).catch(() => undefined);
      });

      els.editorForm.addEventListener("dragover", (event) => {
        const textarea = event.target.closest('textarea[data-markdown-inline="1"][data-browse-field]');
        if (!(textarea instanceof HTMLTextAreaElement)) {
          return;
        }
        const file = firstImageFile(event.dataTransfer?.files || []);
        if (!file) {
          return;
        }
        event.preventDefault();
        textarea.classList.add("is-dragover");
      });

      els.editorForm.addEventListener("dragleave", (event) => {
        const textarea = event.target.closest('textarea[data-markdown-inline="1"][data-browse-field]');
        if (!(textarea instanceof HTMLTextAreaElement)) {
          return;
        }
        textarea.classList.remove("is-dragover");
      });

      els.editorForm.addEventListener("drop", (event) => {
        const textarea = event.target.closest('textarea[data-markdown-inline="1"][data-browse-field]');
        if (!(textarea instanceof HTMLTextAreaElement)) {
          return;
        }
        const fieldName = String(textarea.dataset.browseField || "").trim();
        const imageFile = firstImageFile(event.dataTransfer?.files || []);
        textarea.classList.remove("is-dragover");
        if (!fieldName || !imageFile) {
          return;
        }
        event.preventDefault();
        uploadMarkdownInlineMedia(fieldName, imageFile, textarea).catch(() => undefined);
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
      if (event.key === "Escape") {
        setAudioCreateMenuOpen(false);
        setVoicevoxModalOpen(false);
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
