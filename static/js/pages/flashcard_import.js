/**
 * Flashcard Bulk Import Page Module
 * Manages file upload & parsing, field mapping, uniqueness keys, dry-run estimation, and execution.
 */
(() => {
  const configEl = document.getElementById("importPageConfig");
  if (!configEl) return;

  const config = JSON.parse(configEl.textContent || "{}");
  const PARSE_BUTTON_LABEL = "Parse lại";
  const ESTIMATE_BUTTON_LABEL = "1. Ước lượng";
  const EXECUTE_BUTTON_LABEL = "2. Thực thi import";
  const SUPPORTED_IMPORT_EXTENSIONS = new Set(["csv", "tsv", "txt"]);
  const DECK_COLUMN_HINTS = new Set(["deck", "deckname", "deckpath", "decks", "sourcedeck", "targetdeck"]);

  const state = {
    token: null,
    columns: [],
    selectedColumnIndexes: [],
    autoExcludedColumnIndexes: [],
    previewRows: [],
    hasHeader: true,
    warnings: [],
    mapping: {},
    parseMetaInfo: null,
    lastSummary: null,
    parsed: false,
    running: false,
    estimating: false,
    isParsing: false,
    queuedParse: null,
    parseFailed: false,
    hasEstimated: false,
    executionDone: false,
  };

  const els = {
    targetDeckSelect: document.getElementById("targetDeckSelect"),
    noteTypeSelect: document.getElementById("noteTypeSelect"),
    importFileInput: document.getElementById("importFileInput"),
    importDropzone: document.getElementById("importDropzone"),
    delimiterModeSelect: document.getElementById("delimiterModeSelect"),
    customDelimiterInput: document.getElementById("customDelimiterInput"),
    parseBtn: document.getElementById("parseBtn"),
    parseStateBadge: document.getElementById("parseStateBadge"),
    parseWarningBox: document.getElementById("parseWarningBox"),
    parseMeta: document.getElementById("parseMeta"),
    previewWrap: document.getElementById("previewWrap"),
    previewCaption: document.getElementById("previewCaption"),
    previewSelectAllInput: document.getElementById("previewSelectAllInput"),
    previewTable: document.getElementById("previewTable"),
    previewHeaderRow: document.getElementById("previewHeaderRow"),
    previewBody: document.getElementById("previewBody"),
    previewHeaderOn: document.getElementById("previewHeaderOn"),
    previewHeaderOff: document.getElementById("previewHeaderOff"),
    mappingWrap: document.getElementById("mappingWrap"),
    mappingBody: document.getElementById("mappingBody"),
    mappingWarnings: document.getElementById("mappingWarnings"),
    uniquenessFieldsWrap: document.getElementById("uniquenessFieldsWrap"),
    columnMismatchConfirmWrap: document.getElementById("columnMismatchConfirmWrap"),
    columnMismatchConfirmInput: document.getElementById("columnMismatchConfirmInput"),
    estimateBtn: document.getElementById("estimateBtn"),
    executeBtn: document.getElementById("executeBtn"),
    stepDStateBadge: document.getElementById("stepDStateBadge"),
    stepDHint: document.getElementById("stepDHint"),
    progressWrap: document.getElementById("progressWrap"),
    progressBar: document.getElementById("progressBar"),
    summaryBox: document.getElementById("summaryBox"),
    summaryGrid: document.getElementById("summaryGrid"),
    issuesWrap: document.getElementById("issuesWrap"),
    issuesBody: document.getElementById("issuesBody"),
    dontOverwriteEmptyInput: document.getElementById("dontOverwriteEmptyInput"),
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

  function getNoteTypeOptions() {
    return Array.isArray(config.note_type_options) ? config.note_type_options : [];
  }

  function getDeckOptions() {
    return Array.isArray(config.deck_options) ? config.deck_options : [];
  }

  /**
   * Infers a note type ID from sibling decks (decks with same parent_id).
   */
  function inferNoteTypeFromSiblings(deckIdRaw) {
    const deckId = String(deckIdRaw || "");
    if (!deckId) return null;

    const allDecks = getDeckOptions();
    const selectedDeck = allDecks.find((d) => String(d.id) === deckId);
    if (!selectedDeck) return null;

    const parentId = selectedDeck.parent_id != null ? String(selectedDeck.parent_id) : null;
    const siblings = allDecks.filter(
      (d) => String(d.id) !== deckId && (d.parent_id != null ? String(d.parent_id) : null) === parentId
    );

    if (!siblings.length) return null;

    const siblingNoteTypeIds = siblings
      .map((d) => (d.note_type_id != null ? String(d.note_type_id) : null))
      .filter(Boolean);

    if (!siblingNoteTypeIds.length) return null;

    const uniqueIds = new Set(siblingNoteTypeIds);
    if (uniqueIds.size !== 1) return null;

    const suggested = siblingNoteTypeIds[0];
    const available = getNoteTypeOptions().find((nt) => String(nt.id) === suggested);
    return available ? suggested : null;
  }

  function setNoteTypeAutoSelectBadge(visible) {
    const badge = document.getElementById("noteTypeAutoSelectBadge");
    if (!badge) return;
    badge.classList.toggle("d-none", !visible);
  }

  function getSelectedNoteType() {
    const noteTypeId = String(els.noteTypeSelect.value || "");
    return getNoteTypeOptions().find((item) => String(item.id) === noteTypeId) || null;
  }

  function getFields() {
    const noteType = getSelectedNoteType();
    return Array.isArray(noteType?.fields) ? noteType.fields : [];
  }

  function normalizeImportName(value) {
    return String(value == null ? "" : value).trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
  }

  function normalizeColumnIndexes(indexes) {
    const available = new Set(
      (Array.isArray(state.columns) ? state.columns : [])
        .map((col) => Number(col.index))
        .filter((value) => Number.isInteger(value) && value >= 0)
    );
    const normalized = (Array.isArray(indexes) ? indexes : [])
      .map((value) => Number(value))
      .filter((value, position, list) => (
        Number.isInteger(value)
        && value >= 0
        && available.has(value)
        && list.indexOf(value) === position
      ))
      .sort((left, right) => left - right);
    return normalized;
  }

  function getSelectedColumnIndexes() {
    return normalizeColumnIndexes(state.selectedColumnIndexes);
  }

  function getSelectedColumns() {
    const selected = new Set(getSelectedColumnIndexes());
    const columns = Array.isArray(state.columns) ? state.columns : [];
    return columns
      .filter((column) => selected.has(Number(column.index)))
      .map((column, effectiveIndex) => ({
        ...column,
        effectiveIndex,
      }));
  }

  function isLikelyDeckColumn(column) {
    if (!column || !state.hasHeader) {
      return false;
    }
    return DECK_COLUMN_HINTS.has(normalizeImportName(column.name || column.display || ""));
  }

  function initializeColumnSelection() {
    const allIndexes = normalizeColumnIndexes(
      (Array.isArray(state.columns) ? state.columns : []).map((column) => column.index)
    );
    state.selectedColumnIndexes = allIndexes.slice();
    state.autoExcludedColumnIndexes = [];

    const firstColumn = Array.isArray(state.columns) && state.columns.length ? state.columns[0] : null;
    if (allIndexes.length > 1 && isLikelyDeckColumn(firstColumn)) {
      const firstIndex = Number(firstColumn.index);
      state.selectedColumnIndexes = allIndexes.filter((value) => value !== firstIndex);
      state.autoExcludedColumnIndexes = [firstIndex];
    }
    syncPreviewSelectAll();
  }

  function buildSuggestedMappingForSelection() {
    const fields = getFields();
    const selectedColumns = getSelectedColumns();
    const headerMap = new Map();
    const suggestions = {};

    if (state.hasHeader) {
      selectedColumns.forEach((column) => {
        const normalized = normalizeImportName(column.name || "");
        if (normalized && !headerMap.has(normalized)) {
          headerMap.set(normalized, Number(column.index));
        }
      });
    }

    fields.forEach((field, position) => {
      let mappedIndex = null;
      if (state.hasHeader) {
        mappedIndex = headerMap.get(normalizeImportName(field.name)) ?? null;
      }
      if (mappedIndex == null && position < selectedColumns.length) {
        mappedIndex = Number(selectedColumns[position].index);
      }

      suggestions[field.name] = mappedIndex == null
        ? { source_type: "ignore", column_index: null, constant_value: "" }
        : { source_type: "column", column_index: mappedIndex, constant_value: "" };
    });

    return suggestions;
  }

  function getColumnMismatchWarning() {
    if (!state.parsed) {
      return null;
    }

    const selectedCount = getSelectedColumns().length;
    const fieldCount = getFields().length;
    if (selectedCount < fieldCount) {
      return {
        severity: "danger",
        message: `Bạn đang chọn ${selectedCount} cột, nhưng loại note hiện có ${fieldCount} trường.`,
      };
    }
    if (selectedCount > fieldCount) {
      return {
        severity: "warning",
        message: `Bạn đang chọn ${selectedCount} cột, nhưng loại note hiện có ${fieldCount} trường.`,
      };
    }
    return null;
  }

  function syncPreviewSelectAll() {
    if (!els.previewSelectAllInput) {
      return;
    }
    const totalColumns = Array.isArray(state.columns) ? state.columns.length : 0;
    const selectedCount = getSelectedColumnIndexes().length;
    els.previewSelectAllInput.indeterminate = selectedCount > 0 && selectedCount < totalColumns;
    els.previewSelectAllInput.checked = totalColumns > 0 && selectedCount === totalColumns;
    els.previewSelectAllInput.disabled = totalColumns === 0;
  }

  function resetReviewState() {
    state.lastSummary = null;
    state.hasEstimated = false;
    state.executionDone = false;
    els.progressWrap.classList.add("d-none");
    els.progressBar.classList.add("progress-bar-animated");
    els.progressBar.textContent = "Đang chạy...";
    els.summaryBox.classList.add("d-none");
    els.issuesWrap.classList.add("d-none");
    refreshImportUiState();
  }

  function renderParseMeta() {
    if (!state.parseMetaInfo) {
      els.parseMeta.textContent = "";
      return;
    }

    const selectedColumnCount = getSelectedColumns().length;
    els.parseMeta.innerHTML = `
      <span class="import-help-pill"><i class="bi bi-file-earmark-text"></i> ${escapeHtml(state.parseMetaInfo.filename || "")}</span>
      <span class="import-help-pill"><i class="bi bi-table"></i> Dòng: ${escapeHtml(state.parseMetaInfo.totalRows || 0)}</span>
      <span class="import-help-pill"><i class="bi bi-columns-gap"></i> Cột: ${escapeHtml(selectedColumnCount)}/${escapeHtml(state.parseMetaInfo.columnCount || 0)}</span>
      <span class="import-help-pill"><i class="bi bi-filter"></i> Ký tự phân tách: ${escapeHtml(state.parseMetaInfo.delimiterLabel || "")}</span>
    `;
  }

  function applyColumnSelection(indexes, { keepAutoExcluded = false } = {}) {
    state.selectedColumnIndexes = normalizeColumnIndexes(indexes);
    if (keepAutoExcluded) {
      state.autoExcludedColumnIndexes = normalizeColumnIndexes(state.autoExcludedColumnIndexes)
        .filter((index) => !state.selectedColumnIndexes.includes(index));
    } else {
      state.autoExcludedColumnIndexes = [];
    }

    syncPreviewSelectAll();

    if (!state.parsed) {
      return;
    }

    resetReviewState();
    applySuggestedMapping(buildSuggestedMappingForSelection());
    renderParseMeta();
    renderPreviewTable();
    renderWarnings();
    renderMappingWarnings([]);
  }

  function getSelectedImportMode() {
    const checked = document.querySelector('input[name="importMode"]:checked');
    return checked ? checked.value : "upsert";
  }

  function getHasHeaderEnabled() {
    return Boolean(els.previewHeaderOn && els.previewHeaderOn.checked);
  }

  function syncHeaderControls() {
    if (els.previewHeaderOn) {
      els.previewHeaderOn.checked = Boolean(state.hasHeader);
    }
    if (els.previewHeaderOff) {
      els.previewHeaderOff.checked = !state.hasHeader;
    }
  }

  function setAlert(message, kind = "warning") {
    if (!message) {
      els.parseWarningBox.className = "alert mt-3 d-none";
      els.parseWarningBox.textContent = "";
      return;
    }
    els.parseWarningBox.className = `alert alert-${kind} mt-3`;
    els.parseWarningBox.textContent = message;
  }

  function ensureToastContainer() {
    let container = document.getElementById("importToastContainer");
    if (container) {
      return container;
    }

    container = document.createElement("div");
    container.id = "importToastContainer";
    container.className = "toast-container position-fixed top-0 end-0 p-3 import-toast-container";
    document.body.appendChild(container);
    return container;
  }

  function showToast(message, { kind = "info", title = "Import" } = {}) {
    if (!message) return;
    const container = ensureToastContainer();
    const toastId = `import-toast-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    const classByKind = {
      success: "text-bg-success",
      danger: "text-bg-danger",
      warning: "text-bg-warning",
      info: "text-bg-primary",
    };
    const toneClass = classByKind[kind] || classByKind.info;
    const closeBtnClass = kind === "warning" ? "btn-close" : "btn-close btn-close-white";
    const autoHide = kind !== "danger";
    const delay = kind === "success" ? 3200 : 4600;

    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <div id="${toastId}" class="toast ${toneClass} border-0" role="status" aria-live="polite" aria-atomic="true">
        <div class="d-flex">
          <div class="toast-body">
            <div class="fw-semibold mb-1">${escapeHtml(title)}</div>
            <div>${escapeHtml(message)}</div>
          </div>
          <button type="button" class="${closeBtnClass} me-2 m-auto" data-bs-dismiss="toast" aria-label="Đóng"></button>
        </div>
      </div>
    `;
    const toastEl = wrapper.firstElementChild;
    if (!toastEl) return;
    container.appendChild(toastEl);

    if (typeof bootstrap !== "undefined" && bootstrap.Toast) {
      const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { autohide: autoHide, delay });
      toast.show();
      toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove(), { once: true });
    } else {
      setTimeout(() => toastEl.remove(), autoHide ? delay : 5200);
    }
  }

  function setStatusBadge(el, tone, label) {
    if (!el) return;
    el.className = `import-status-badge import-status-badge--${tone}`;
    el.textContent = label;
  }

  function setStepDHint(message, tone = "info") {
    if (!els.stepDHint) return;
    els.stepDHint.className = `import-step-hint import-step-hint--${tone} mt-3`;
    els.stepDHint.textContent = message;
  }

  function syncActionButtons() {
    if (!els.estimateBtn || !els.executeBtn) return;
    const estimateDisabled = !state.parsed || state.isParsing || state.estimating || state.running;
    const executeDisabled = !state.parsed || !state.hasEstimated || state.isParsing || state.estimating || state.running;
    els.estimateBtn.disabled = estimateDisabled;
    els.executeBtn.disabled = executeDisabled;
  }

  function updateParseStatusBadge() {
    if (state.isParsing) {
      setStatusBadge(els.parseStateBadge, "info", "Đang parse...");
      return;
    }
    if (state.parsed) {
      setStatusBadge(els.parseStateBadge, "success", "Parse thành công");
      return;
    }
    if (state.parseFailed) {
      setStatusBadge(els.parseStateBadge, "danger", "Parse thất bại");
      return;
    }
    if (hasSelectedFile()) {
      setStatusBadge(els.parseStateBadge, "warning", "Chờ parse");
      return;
    }
    setStatusBadge(els.parseStateBadge, "idle", "Chưa có file");
  }

  function updateStepDStatus() {
    if (state.running) {
      setStatusBadge(els.stepDStateBadge, "info", "Đang thực thi");
      setStepDHint("Import đang chạy. Vui lòng đợi hoàn tất để xem báo cáo cuối cùng.", "info");
      return;
    }

    if (state.estimating) {
      setStatusBadge(els.stepDStateBadge, "info", "Đang ước lượng");
      setStepDHint("Hệ thống đang tính toán số lượng bản ghi sẽ được thêm/cập nhật/bỏ qua.", "info");
      return;
    }

    if (!state.parsed) {
      setStatusBadge(els.stepDStateBadge, "idle", "Chờ parse");
      setStepDHint("Bắt đầu từ Bước A: tải file để hệ thống parse.", "info");
      return;
    }

    if (!state.hasEstimated) {
      setStatusBadge(els.stepDStateBadge, "warning", "Cần ước lượng");
      setStepDHint("Nhấn 1. Ước lượng để xem trước kết quả import trước khi chạy thật.", "warning");
      return;
    }

    const summaryErrors = Number(state.lastSummary?.summary?.errors || 0);
    if (summaryErrors > 0) {
      setStatusBadge(els.stepDStateBadge, "danger", "Có lỗi cần xử lý");
      setStepDHint("Phần ước lượng cho thấy có dòng lỗi. Hãy xem bảng lỗi theo dòng trước khi thực thi.", "danger");
      return;
    }

    if (state.executionDone) {
      setStatusBadge(els.stepDStateBadge, "success", "Import hoàn tất");
      setStepDHint("Import đã hoàn tất. Bạn có thể kiểm tra dữ liệu hoặc import file khác.", "success");
      return;
    }

    setStatusBadge(els.stepDStateBadge, "success", "Sẵn sàng thực thi");
    setStepDHint("Phần ước lượng đã ổn. Nhấn 2. Thực thi import để chạy thật.", "success");
  }

  function refreshImportUiState() {
    syncActionButtons();
    updateParseStatusBadge();
    updateStepDStatus();
  }

  function getSelectedFile() {
    return (els.importFileInput.files && els.importFileInput.files[0]) || null;
  }

  function hasSelectedFile() {
    return Boolean(getSelectedFile());
  }

  function getFileExtension(filename) {
    const name = String(filename || "").trim().toLowerCase();
    const lastDot = name.lastIndexOf(".");
    if (lastDot < 0 || lastDot === name.length - 1) {
      return "";
    }
    return name.slice(lastDot + 1);
  }

  function readCurrentDelimiterSelection() {
    const mode = String(els.delimiterModeSelect.value || "csv");
    const customDelimiter = String(els.customDelimiterInput.value || "");
    return { mode, customDelimiter };
  }

  function applyDelimiterSelection(mode, customDelimiter = "") {
    const normalizedMode = mode === "tsv" || mode === "custom" ? mode : "csv";
    els.delimiterModeSelect.value = normalizedMode;
    handleDelimiterModeChange();
    if (normalizedMode === "custom") {
      els.customDelimiterInput.value = customDelimiter;
    }
  }

  function delimiterSelectionFromChar(delimiter) {
    if (delimiter === "\t") {
      return { mode: "tsv", customDelimiter: "" };
    }
    if (delimiter === ",") {
      return { mode: "csv", customDelimiter: "" };
    }
    if (typeof delimiter === "string" && delimiter.length === 1) {
      return { mode: "custom", customDelimiter: delimiter };
    }
    return null;
  }

  function formatDelimiterLabel(delimiter) {
    if (delimiter === "\t") return "tab";
    if (delimiter === ",") return ",";
    if (typeof delimiter === "string" && delimiter.length === 1) return delimiter;
    return "";
  }

  function normalizeDirectiveKey(value) {
    return String(value == null ? "" : value).trim().toLowerCase().replace(/\s+/g, " ");
  }

  function resolveSeparatorDirective(value) {
    const token = String(value == null ? "" : value).trim();
    if (!token) return null;
    if (token.length === 1) return token;

    const normalized = token.toLowerCase();
    const aliases = {
      "\\t": "\t",
      bar: "|",
      colon: ":",
      comma: ",",
      pipe: "|",
      semicolon: ";",
      space: " ",
      tab: "\t",
    };
    return Object.prototype.hasOwnProperty.call(aliases, normalized) ? aliases[normalized] : null;
  }

  function parseTxtImportPreamble(sampleText) {
    const lines = String(sampleText == null ? "" : sampleText).split(/\r?\n/);
    const directives = {};
    let firstDataLine = "";
    let hasDirectives = false;

    for (const line of lines) {
      const trimmed = String(line || "").trim();
      if (!trimmed) continue;

      const match = trimmed.match(/^#\s*([^:]+):(.*)$/);
      if (!match) {
        firstDataLine = trimmed;
        break;
      }

      hasDirectives = true;
      directives[normalizeDirectiveKey(match[1])] = String(match[2] || "").trim();
    }

    return {
      directives,
      firstDataLine,
      hasDirectives,
    };
  }

  function setParseButtonLoading(isLoading) {
    if (!els.parseBtn) return;
    els.parseBtn.disabled = Boolean(isLoading);
    els.parseBtn.innerHTML = isLoading
      ? '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>'
      : PARSE_BUTTON_LABEL;
  }

  function countDelimiterInLine(line, delimiter) {
    if (!line || !delimiter) return 0;
    return line.split(delimiter).length - 1;
  }

  async function detectTxtDelimiter(file) {
    try {
      const sampleText = await file.slice(0, 8192).text();
      const preamble = parseTxtImportPreamble(sampleText);
      const directiveDelimiter = resolveSeparatorDirective(preamble.directives.separator);
      if (directiveDelimiter) {
        const resolved = delimiterSelectionFromChar(directiveDelimiter);
        if (resolved) {
          return { ...resolved, hasHeader: false };
        }
      }

      const firstLine = preamble.firstDataLine;
      if (!firstLine) {
        return null;
      }

      const candidates = [
        { mode: "tsv", customDelimiter: "", delimiter: "\t" },
        { mode: "csv", customDelimiter: "", delimiter: "," },
        { mode: "custom", customDelimiter: ";", delimiter: ";" },
        { mode: "custom", customDelimiter: "|", delimiter: "|" },
      ];

      let best = null;
      candidates.forEach((candidate, index) => {
        const score = countDelimiterInLine(firstLine, candidate.delimiter);
        if (score <= 0) return;
        if (!best || score > best.score || (score === best.score && index < best.index)) {
          best = { ...candidate, score, index };
        }
      });

      if (!best) return null;
      return {
        mode: best.mode,
        customDelimiter: best.customDelimiter,
        hasHeader: preamble.hasDirectives ? false : undefined,
      };
    } catch (_error) {
      return null;
    }
  }

  async function inferDelimiterFromFile(file) {
    const extension = getFileExtension(file && file.name);
    if (!SUPPORTED_IMPORT_EXTENSIONS.has(extension)) {
      return {
        ok: false,
        message: "Định dạng file chưa được hỗ trợ. Vui lòng dùng .csv, .tsv hoặc .txt.",
      };
    }

    if (extension === "csv") {
      return { ok: true, mode: "csv", customDelimiter: "" };
    }

    if (extension === "tsv") {
      return { ok: true, mode: "tsv", customDelimiter: "" };
    }

    const detectedTxtDelimiter = await detectTxtDelimiter(file);
    if (detectedTxtDelimiter) {
      return {
        ok: true,
        mode: detectedTxtDelimiter.mode,
        customDelimiter: detectedTxtDelimiter.customDelimiter,
        hasHeader: detectedTxtDelimiter.hasHeader,
      };
    }

    const current = readCurrentDelimiterSelection();
    if (current.mode === "custom" && current.customDelimiter.length !== 1) {
      return {
        ok: false,
        message: "File .txt chưa xác định được delimiter. Hãy chọn CSV/TSV hoặc nhập đúng 1 custom delimiter.",
      };
    }
    return {
      ok: true,
      mode: current.mode,
      customDelimiter: current.mode === "custom" ? current.customDelimiter : "",
    };
  }

  function queueParseRequest(options = {}) {
    if (state.running || state.estimating) {
      setAlert("Không thể parse lại khi estimate/import đang chạy.", "warning");
      return;
    }

    const normalizedOptions = {
      inferFromFile: Boolean(options.inferFromFile),
    };

    if (state.isParsing) {
      state.queuedParse = normalizedOptions;
      return;
    }

    parseFile(normalizedOptions).catch(() => undefined);
  }

  function resetParseState({ keepWarning = false } = {}) {
    state.token = null;
    state.columns = [];
    state.selectedColumnIndexes = [];
    state.autoExcludedColumnIndexes = [];
    state.previewRows = [];
    state.hasHeader = getHasHeaderEnabled();
    state.warnings = [];
    state.mapping = {};
    state.parseMetaInfo = null;
    state.lastSummary = null;
    state.parsed = false;
    state.parseFailed = false;
    state.hasEstimated = false;
    state.executionDone = false;
    els.previewWrap.hidden = true;
    els.mappingWrap.hidden = true;
    els.parseMeta.textContent = "";
    els.progressWrap.classList.add("d-none");
    els.progressBar.classList.add("progress-bar-animated");
    els.progressBar.textContent = "Đang chạy...";
    els.summaryBox.classList.add("d-none");
    els.issuesWrap.classList.add("d-none");
    els.columnMismatchConfirmWrap.classList.add("d-none");
    els.columnMismatchConfirmInput.checked = false;
    syncPreviewSelectAll();
    if (!keepWarning) {
      setAlert("");
    }
    renderMappingWarnings([]);
    renderUniquenessFields();
    refreshImportUiState();
  }

  function populateDeckOptions() {
    const initial = String(config.initial_deck_id ?? "");
    const options = getDeckOptions().map((item) => {
      const selected = String(item.id) === initial ? " selected" : "";
      const label = item.path || item.name || `Deck ${item.id}`;
      return `<option value="${escapeHtml(item.id)}"${selected}>${escapeHtml(label)}</option>`;
    });
    els.targetDeckSelect.innerHTML = options.length ? options.join("") : '<option value="">(No deck)</option>';
  }

  function populateNoteTypeOptions() {
    const initial = String(config.initial_note_type_id ?? "");
    const options = getNoteTypeOptions().map((item) => {
      const selected = String(item.id) === initial ? " selected" : "";
      return `<option value="${escapeHtml(item.id)}"${selected}>${escapeHtml(item.name || "(Loại note chưa đặt tên)")}</option>`;
    });
    els.noteTypeSelect.innerHTML = options.length ? options.join("") : '<option value="">(Chưa có loại note)</option>';
  }

  function applySuggestedMapping(suggestedMapping) {
    const fields = getFields();
    const next = {};
    fields.forEach((field) => {
      const fallback = { source_type: "ignore", column_index: null, constant_value: "" };
      const incoming = suggestedMapping && suggestedMapping[field.name] ? suggestedMapping[field.name] : fallback;
      next[field.name] = {
        source_type: incoming.source_type || "ignore",
        column_index: typeof incoming.column_index === "number" ? incoming.column_index : null,
        constant_value: incoming.constant_value || "",
      };
    });
    state.mapping = next;
    renderMappingTable();
  }

  function truncatePreviewValue(value, maxWords = 8, maxChars = 70) {
    const normalized = String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    if (!normalized) {
      return "";
    }

    const words = normalized.split(" ");
    let shortened = normalized;
    let wasTrimmed = false;

    if (words.length > maxWords) {
      shortened = words.slice(0, maxWords).join(" ");
      wasTrimmed = true;
    }

    if (shortened.length > maxChars) {
      shortened = shortened.slice(0, maxChars).trimEnd();
      wasTrimmed = true;
    }

    return wasTrimmed ? `${shortened}...` : shortened;
  }

  function getSampleRowForMapping() {
    if (!Array.isArray(state.previewRows) || !state.previewRows.length) {
      return null;
    }
    const preferredIndex = state.hasHeader ? 0 : 1;
    return state.previewRows[preferredIndex] || state.previewRows[0] || null;
  }

  function renderPreviewTable() {
    if (!state.parsed || !state.columns.length) {
      els.previewWrap.hidden = true;
      syncPreviewSelectAll();
      return;
    }
    els.previewWrap.hidden = false;
    syncHeaderControls();
    syncPreviewSelectAll();

    const selectedColumns = getSelectedColumns();
    const selectedSet = new Set(selectedColumns.map((column) => Number(column.index)));
    const effectiveIndexBySource = new Map(selectedColumns.map((column) => [Number(column.index), column.effectiveIndex]));

    if (els.previewTable) {
      const minWidthPx = Math.max(760, state.columns.length * 180);
      els.previewTable.style.minWidth = `${minWidthPx}px`;
    }

    if (els.previewCaption) {
      const rowCount = Array.isArray(state.previewRows) ? state.previewRows.length : 0;
      const totalColumns = Array.isArray(state.columns) ? state.columns.length : 0;
      const selectionSummary = `Đang chọn ${selectedColumns.length}/${totalColumns} cột.`;
      const autoExcludedNote = state.autoExcludedColumnIndexes.length
        ? " Cột đầu tiên được bỏ chọn tự động vì dòng tiêu đề trùng tên deck."
        : "";
      els.previewCaption.textContent = state.hasHeader
        ? `Đang dùng dòng đầu tiên làm dòng tiêu đề. Xem trước ${rowCount} dòng dữ liệu đầu tiên. ${selectionSummary}${autoExcludedNote}`
        : `Đang xem dữ liệu thô. Xem trước ${rowCount} dòng đầu tiên. ${selectionSummary}${autoExcludedNote}`;
    }

    els.previewHeaderRow.innerHTML = state.columns
      .map((col) => {
        const sourceIndex = Number(col.index);
        const isSelected = selectedSet.has(sourceIndex);
        const effectiveIndex = effectiveIndexBySource.has(sourceIndex)
          ? Number(effectiveIndexBySource.get(sourceIndex))
          : -1;
        const titleLabel = isSelected
          ? `Cột ${effectiveIndex + 1}: ${escapeHtml(col.display || "")}`
          : `Bỏ qua: ${escapeHtml(col.display || "")}`;
        const metaLabel = isSelected
          ? `Cột nguồn ${sourceIndex + 1}`
          : `Đã bỏ qua cột nguồn ${sourceIndex + 1}`;
        return `
          <th class="${isSelected ? "" : "is-excluded"}">
            <label class="import-preview-column-toggle">
              <span class="import-preview-column-topline">
                <input class="form-check-input mt-0" type="checkbox" data-preview-column-index="${sourceIndex}"${isSelected ? " checked" : ""}>
                <span class="import-preview-column-title">${titleLabel}</span>
              </span>
              <span class="import-preview-column-meta">${metaLabel}</span>
            </label>
          </th>
        `;
      })
      .join("");

    if (!state.previewRows.length) {
      els.previewBody.innerHTML = `<tr><td colspan="${Math.max(state.columns.length, 1)}" class="text-muted text-center">Không tìm thấy dòng dữ liệu nào.</td></tr>`;
      return;
    }

    els.previewBody.innerHTML = state.previewRows
      .map((row) => {
        const cells = [];
        for (let idx = 0; idx < state.columns.length; idx += 1) {
          const sourceIndex = Number(state.columns[idx]?.index ?? idx);
          const fullValue = String(row[idx] || "");
          const shortValue = truncatePreviewValue(fullValue);
          const isSelected = selectedSet.has(sourceIndex);
          cells.push(
            `<td class="${isSelected ? "" : "is-excluded"}" title="${escapeHtml(fullValue)}"><div class="preview-cell-text">${escapeHtml(shortValue)}</div></td>`
          );
        }
        return `<tr>${cells.join("")}</tr>`;
      })
      .join("");
  }

  function renderWarnings() {
    const mismatch = getColumnMismatchWarning();
    if (!mismatch) {
      setAlert("");
      els.columnMismatchConfirmWrap.classList.add("d-none");
      els.columnMismatchConfirmInput.checked = false;
      return;
    }
    const kind = mismatch.severity === "danger" ? "danger" : "warning";
    setAlert(mismatch.message || "Phát hiện lệch số cột.", kind);
    els.columnMismatchConfirmWrap.classList.remove("d-none");
  }

  function mappingSelectValue(mappingValue) {
    if (!mappingValue) return "ignore";
    if (mappingValue.source_type === "constant") return "constant";
    if (mappingValue.source_type === "column" && typeof mappingValue.column_index === "number") {
      return `col:${mappingValue.column_index}`;
    }
    return "ignore";
  }

  function renderMappingTable() {
    const fields = getFields();
    if (!state.parsed || !fields.length) {
      els.mappingWrap.hidden = true;
      return;
    }
    els.mappingWrap.hidden = false;
    const sampleRow = getSampleRowForMapping();
    const selectedColumns = getSelectedColumns();

    els.mappingBody.innerHTML = fields
      .map((field) => {
        const mappingValue = state.mapping[field.name] || { source_type: "ignore", column_index: null, constant_value: "" };
        const selectValue = mappingSelectValue(mappingValue);
        const columnOptions = selectedColumns
          .map((col) => {
            const optionValue = `col:${col.index}`;
            const isSelected = selectValue === optionValue ? " selected" : "";
            return `<option value="${optionValue}"${isSelected}>Cột ${col.effectiveIndex + 1} - ${escapeHtml(col.display || "")}</option>`;
          })
          .join("");
        const requiredBadge = field.required ? '<span class="text-danger">*</span>' : "";
        const constantDisabled = mappingValue.source_type === "constant" ? "" : " disabled";
        const hasColumnMap = mappingValue.source_type === "column" && typeof mappingValue.column_index === "number";
        const sampleRaw = hasColumnMap && sampleRow ? String(sampleRow[mappingValue.column_index] || "") : "";
        const sampleDisplay = truncatePreviewValue(sampleRaw, 10, 90);
        let valueCellHtml = `<input type="text" class="form-control form-control-sm" data-map-constant="${escapeHtml(field.name)}" value="${escapeHtml(mappingValue.constant_value || "")}"${constantDisabled}>`;

        if (hasColumnMap) {
          valueCellHtml = `
            <input type="text" class="form-control form-control-sm" value="${escapeHtml(sampleDisplay)}" readonly>
          `;
        }

        return `
          <tr>
            <td>
              <div>${escapeHtml(field.name)} ${requiredBadge}</div>
              <div class="small text-muted">${escapeHtml(field.field_type || "text")}</div>
            </td>
            <td>
              <select class="form-select form-select-sm" data-map-select="${escapeHtml(field.name)}">
                <option value="ignore"${selectValue === "ignore" ? " selected" : ""}>Bỏ qua</option>
                <option value="constant"${selectValue === "constant" ? " selected" : ""}>Giá trị cố định</option>
                ${columnOptions}
              </select>
            </td>
            <td>
              ${valueCellHtml}
            </td>
          </tr>
        `;
      })
      .join("");
  }

  function renderUniquenessFields() {
    const fields = getFields();
    if (!fields.length) {
      els.uniquenessFieldsWrap.innerHTML = '<div class="text-muted small">Chưa có trường nào</div>';
      return;
    }

    const noteTypeId = String(els.noteTypeSelect.value || "");
    const defaults = (config.uniqueness_defaults && Array.isArray(config.uniqueness_defaults[noteTypeId]))
      ? config.uniqueness_defaults[noteTypeId]
      : [];

    const defaultSet = new Set(defaults.map((x) => String(x)));
    els.uniquenessFieldsWrap.innerHTML = fields
      .map((field, index) => {
        const checked = defaultSet.size ? defaultSet.has(field.name) : index === 0;
        return `
          <div class="form-check">
            <input class="form-check-input" type="checkbox" data-uniq-field="${escapeHtml(field.name)}" id="uniq-${escapeHtml(field.name)}"${checked ? " checked" : ""}>
            <label class="form-check-label" for="uniq-${escapeHtml(field.name)}">${escapeHtml(field.name)}</label>
          </div>
        `;
      })
      .join("");
  }

  function readUniquenessFields() {
    return Array.from(document.querySelectorAll("[data-uniq-field]:checked")).map((el) => el.getAttribute("data-uniq-field") || "").filter(Boolean);
  }

  function readMappingFromDom() {
    const fields = getFields();
    fields.forEach((field) => {
      const selectEl = document.querySelector(`[data-map-select="${CSS.escape(field.name)}"]`);
      const constantEl = document.querySelector(`[data-map-constant="${CSS.escape(field.name)}"]`);
      if (!selectEl) return;

      const raw = selectEl.value || "ignore";
      if (raw === "ignore") {
        state.mapping[field.name] = { source_type: "ignore", column_index: null, constant_value: "" };
      } else if (raw === "constant") {
        state.mapping[field.name] = {
          source_type: "constant",
          column_index: null,
          constant_value: constantEl ? String(constantEl.value || "") : "",
        };
      } else if (raw.startsWith("col:")) {
        const idx = Number(raw.replace("col:", ""));
        state.mapping[field.name] = {
          source_type: "column",
          column_index: Number.isFinite(idx) ? idx : null,
          constant_value: "",
        };
      }
    });
  }

  function renderMappingWarnings(messages) {
    if (!messages || !messages.length) {
      els.mappingWarnings.innerHTML = "";
      return;
    }
    els.mappingWarnings.innerHTML = messages.map((x) => `<div>${escapeHtml(x)}</div>`).join("");
  }

  function validateBeforeSubmit() {
    if (!state.parsed || !state.token) {
      return { ok: false, errors: ["Hãy tải file để hệ thống parse trước khi ước lượng hoặc thực thi."] };
    }

    readMappingFromDom();

    const fields = getFields();
    const selectedColumns = getSelectedColumns();
    const effectiveIndexBySource = new Map(selectedColumns.map((column) => [Number(column.index), column.effectiveIndex]));
    const uniq = readUniquenessFields();
    const errors = [];
    const warnings = [];

    if (!selectedColumns.length) {
      errors.push("Phải chọn ít nhất 1 cột để import.");
    }

    if (!uniq.length) {
      errors.push("Phải chọn ít nhất 1 trường khóa đối chiếu.");
    }

    const usedColumns = new Map();
    fields.forEach((field) => {
      const mapVal = state.mapping[field.name] || { source_type: "ignore" };
      if (field.required && mapVal.source_type === "ignore") {
        errors.push(`Trường bắt buộc '${field.name}' chưa được ánh xạ.`);
      }
      if (uniq.includes(field.name) && mapVal.source_type === "ignore") {
        errors.push(`Trường khóa đối chiếu '${field.name}' chưa được ánh xạ.`);
      }
      if (mapVal.source_type === "column" && typeof mapVal.column_index === "number") {
        const list = usedColumns.get(mapVal.column_index) || [];
        list.push(field.name);
        usedColumns.set(mapVal.column_index, list);
      }
    });

    Array.from(usedColumns.entries()).forEach(([columnIdx, names]) => {
      if (names.length > 1) {
        const effectiveIndex = effectiveIndexBySource.has(columnIdx)
          ? Number(effectiveIndexBySource.get(columnIdx)) + 1
          : columnIdx + 1;
        warnings.push(`Cột ${effectiveIndex} đang được ánh xạ cho nhiều trường: ${names.join(", ")}`);
      }
    });

    if (getColumnMismatchWarning() && !els.columnMismatchConfirmInput.checked) {
      errors.push("Bạn cần xác nhận lệch số cột trước khi chạy import.");
    }

    return {
      ok: errors.length === 0,
      errors,
      warnings,
    };
  }

  function renderSummary(report, title) {
    const summary = report && report.summary ? report.summary : null;
    if (!summary) {
      els.summaryBox.classList.add("d-none");
      return;
    }

    els.summaryBox.classList.remove("d-none");
    const items = [
      ["Tổng dòng", summary.total_rows],
      ["Dòng hợp lệ", summary.valid_rows],
      ["Thêm mới", summary.inserted],
      ["Cập nhật", summary.updated],
      ["Bỏ qua", summary.skipped],
      ["Không đổi", summary.unchanged],
      ["Lỗi", summary.errors],
    ];

    const heading = title ? `<div class="col-12 fw-semibold mb-1">${escapeHtml(title)}</div>` : "";
    const rowsHtml = items
      .map(([label, value]) => `<div class="col-sm-6 col-lg-3"><strong>${escapeHtml(label)}</strong>: ${escapeHtml(value)}</div>`)
      .join("");

    els.summaryGrid.innerHTML = heading + rowsHtml;
  }

  function renderIssues(report) {
    const issues = Array.isArray(report?.issues) ? report.issues : [];
    if (!issues.length) {
      els.issuesWrap.classList.add("d-none");
      return;
    }
    els.issuesWrap.classList.remove("d-none");
    els.issuesBody.innerHTML = issues
      .map((row) => {
        const kind = row.kind || "-";
        const reason = row.reason || "-";
        return `<tr><td>${escapeHtml(row.row)}</td><td>${escapeHtml(kind)}</td><td>${escapeHtml(reason)}</td><td>${escapeHtml(row.message || "")}</td></tr>`;
      })
      .join("");
  }

  function buildRequestPayload() {
    const effectiveMismatch = getColumnMismatchWarning();
    const payload = {
      token: state.token,
      note_type_id: String(els.noteTypeSelect.value || ""),
      target_deck_id: els.targetDeckSelect.value ? Number(els.targetDeckSelect.value) : null,
      import_mode: getSelectedImportMode(),
      uniqueness_fields: readUniquenessFields(),
      mapping: state.mapping,
      dont_overwrite_empty: Boolean(els.dontOverwriteEmptyInput.checked),
      confirm_column_mismatch: effectiveMismatch
        ? Boolean(els.columnMismatchConfirmInput.checked)
        : Boolean(state.warnings.length),
    };
    return payload;
  }

  async function parseFile({ inferFromFile = false } = {}) {
    const file = getSelectedFile();
    if (!file) {
      setAlert("Hãy chọn file để hệ thống tự parse.", "warning");
      state.parseFailed = false;
      resetParseState({ keepWarning: true });
      return;
    }

    const noteTypeId = String(els.noteTypeSelect.value || "").trim();
    if (!noteTypeId) {
      setAlert("Hãy chọn loại note trước khi parse.", "warning");
      state.parseFailed = false;
      resetParseState({ keepWarning: true });
      return;
    }

    let { mode, customDelimiter } = readCurrentDelimiterSelection();
    if (inferFromFile) {
      const inferred = await inferDelimiterFromFile(file);
      if (!inferred.ok) {
        resetParseState();
        state.parseFailed = true;
        refreshImportUiState();
        setAlert(inferred.message || "Không thể xác định delimiter từ file đã chọn.", "danger");
        showToast(inferred.message || "Không thể tự parse file đã chọn.", { kind: "danger", title: "Tự parse thất bại" });
        return;
      }
      mode = inferred.mode;
      customDelimiter = inferred.customDelimiter || "";
      if (typeof inferred.hasHeader === "boolean") {
        state.hasHeader = inferred.hasHeader;
        syncHeaderControls();
      }
      applyDelimiterSelection(mode, customDelimiter);
    }

    if (mode === "custom" && customDelimiter.length !== 1) {
      setAlert("Ký tự phân tách tùy chỉnh phải gồm đúng 1 ký tự.", "danger");
      resetParseState({ keepWarning: true });
      state.parseFailed = true;
      refreshImportUiState();
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("note_type_id", noteTypeId);
    formData.append("delimiter_mode", mode);
    formData.append("custom_delimiter", customDelimiter);
    formData.append("has_header", getHasHeaderEnabled() ? "1" : "0");

    state.isParsing = true;
    state.parseFailed = false;
    state.executionDone = false;
    setParseButtonLoading(true);
    resetParseState({ keepWarning: true });
    setAlert("Đang parse file...", "info");
    refreshImportUiState();

    try {
      const response = await fetch("/api/flashcards/import/parse", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.message || payload.error || "Parse thất bại");
      }

      state.token = payload.token || null;
      state.columns = Array.isArray(payload.columns) ? payload.columns : [];
      state.previewRows = Array.isArray(payload.preview_rows) ? payload.preview_rows : [];
      state.hasHeader = Boolean(payload.has_header);
      state.warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      state.parsed = true;
      state.parseFailed = false;
      state.hasEstimated = false;
      state.executionDone = false;

      const resolvedDelimiter = typeof payload.delimiter === "string" ? payload.delimiter : "";
      const resolvedSelection = delimiterSelectionFromChar(resolvedDelimiter);
      if (resolvedSelection) {
        applyDelimiterSelection(resolvedSelection.mode, resolvedSelection.customDelimiter);
      }

      initializeColumnSelection();
      applySuggestedMapping(buildSuggestedMappingForSelection());
      renderPreviewTable();
      renderWarnings();
      renderUniquenessFields();

      const columnCount = Number(payload.column_count || 0);
      const totalRows = Number(payload.total_rows || 0);
      const delimiterLabel = formatDelimiterLabel(resolvedDelimiter) || (mode === "tsv" ? "tab" : (mode === "custom" ? customDelimiter : ","));
      state.parseMetaInfo = {
        filename: file.name,
        totalRows,
        columnCount,
        delimiterLabel,
      };
      renderParseMeta();
    } catch (error) {
      state.parseFailed = true;
      setAlert(error.message || "Parse thất bại.", "danger");
      showToast(error.message || "Không thể parse file.", { kind: "danger", title: "Tự parse thất bại" });
    } finally {
      state.isParsing = false;
      setParseButtonLoading(false);
      refreshImportUiState();
      if (state.queuedParse) {
        const queued = state.queuedParse;
        state.queuedParse = null;
        queueParseRequest(queued);
      }
    }
  }

  async function estimateImport() {
    const validation = validateBeforeSubmit();
    renderMappingWarnings(validation.warnings);
    if (!validation.ok) {
      setAlert(validation.errors[0], "danger");
      showToast(validation.errors[0], { kind: "danger", title: "Ước lượng thất bại" });
      return;
    }

    const payload = buildRequestPayload();
    state.estimating = true;
    state.executionDone = false;
    refreshImportUiState();
    els.estimateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';
    setAlert("");

    try {
      const response = await fetch("/api/flashcards/import/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.message || data.error || "Ước lượng thất bại");
      }

      state.lastSummary = data;
      state.hasEstimated = true;
      state.executionDone = false;
      renderSummary(data, "Tổng kết ước lượng");
      renderIssues(data);

      const summary = data.summary || {};
      const summaryErrors = Number(summary.errors || 0);
      if (summaryErrors > 0) {
        showToast(`Ước lượng hoàn tất nhưng có ${summaryErrors} lỗi. Hãy kiểm tra bảng lỗi theo dòng.`, {
          kind: "warning",
          title: "Ước lượng hoàn tất",
        });
      } else {
        showToast("Ước lượng hoàn tất. Bạn có thể tiếp tục thực thi import.", {
          kind: "success",
          title: "Ước lượng thành công",
        });
      }
    } catch (error) {
      state.hasEstimated = false;
      setAlert(error.message || "Ước lượng thất bại", "danger");
      showToast(error.message || "Không thể ước lượng import.", { kind: "danger", title: "Ước lượng thất bại" });
    } finally {
      state.estimating = false;
      els.estimateBtn.textContent = ESTIMATE_BUTTON_LABEL;
      refreshImportUiState();
    }
  }

  async function executeImport() {
    const validation = validateBeforeSubmit();
    renderMappingWarnings(validation.warnings);
    if (!validation.ok) {
      setAlert(validation.errors[0], "danger");
      showToast(validation.errors[0], { kind: "danger", title: "Thực thi thất bại" });
      return;
    }

    const payload = buildRequestPayload();
    state.running = true;
    state.executionDone = false;
    refreshImportUiState();
    els.executeBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Đang chạy...';
    els.progressWrap.classList.remove("d-none");
    els.progressBar.classList.add("progress-bar-animated");
    els.progressBar.textContent = "Đang chạy...";
    setAlert("");

    try {
      const response = await fetch("/api/flashcards/import/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.message || data.error || "Thực thi import thất bại");
      }

      state.executionDone = true;
      renderSummary(data, "Báo cáo thực thi");
      renderIssues(data);
      els.progressBar.classList.remove("progress-bar-animated");
      els.progressBar.textContent = "Hoàn tất";

      const summary = data.summary || {};
      const inserted = Number(summary.inserted || 0);
      const updated = Number(summary.updated || 0);
      const skipped = Number(summary.skipped || 0);
      showToast(
        `Hoàn tất import. Thêm mới: ${inserted}, Cập nhật: ${updated}, Bỏ qua: ${skipped}.`,
        { kind: "success", title: "Import thành công" }
      );
    } catch (error) {
      state.executionDone = false;
      setAlert(error.message || "Thực thi import thất bại", "danger");
      showToast(error.message || "Không thể thực thi import.", { kind: "danger", title: "Import thất bại" });
    } finally {
      state.running = false;
      els.executeBtn.textContent = EXECUTE_BUTTON_LABEL;
      refreshImportUiState();
    }
  }

  function handleDelimiterModeChange() {
    const mode = String(els.delimiterModeSelect.value || "csv");
    const custom = mode === "custom";
    els.customDelimiterInput.disabled = !custom;
    if (!custom) {
      els.customDelimiterInput.value = "";
    }
  }

  function bindDragAndDropEvents() {
    if (!els.importDropzone) return;

    ["dragenter", "dragover"].forEach((eventName) => {
      els.importDropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        els.importDropzone.classList.add("is-dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      els.importDropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        els.importDropzone.classList.remove("is-dragover");
      });
    });

    els.importDropzone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (!dt || !dt.files || !dt.files.length) return;

      const file = dt.files[0];
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      els.importFileInput.files = dataTransfer.files;

      resetParseState();
      queueParseRequest({ inferFromFile: true });
    });
  }

  function bindEvents() {
    bindDragAndDropEvents();

    els.delimiterModeSelect.addEventListener("change", () => {
      handleDelimiterModeChange();
      if (!hasSelectedFile()) return;
      resetParseState({ keepWarning: true });
      queueParseRequest({ inferFromFile: false });
    });

    els.parseBtn.addEventListener("click", (event) => {
      event.preventDefault();
      queueParseRequest({ inferFromFile: false });
    });

    els.estimateBtn.addEventListener("click", estimateImport);
    els.executeBtn.addEventListener("click", executeImport);

    els.targetDeckSelect.addEventListener("change", () => {
      const suggested = inferNoteTypeFromSiblings(els.targetDeckSelect.value);
      if (suggested && String(els.noteTypeSelect.value) !== suggested) {
        els.noteTypeSelect.value = suggested;
        setNoteTypeAutoSelectBadge(true);
        renderUniquenessFields();
        if (hasSelectedFile()) {
          resetParseState();
          queueParseRequest({ inferFromFile: false });
        }
      } else {
        setNoteTypeAutoSelectBadge(false);
      }
    });

    els.importFileInput.addEventListener("change", () => {
      resetParseState();
      if (!hasSelectedFile()) {
        setAlert("");
        return;
      }
      queueParseRequest({ inferFromFile: true });
    });

    els.noteTypeSelect.addEventListener("change", () => {
      setNoteTypeAutoSelectBadge(false);
      resetParseState();
      if (hasSelectedFile()) {
        queueParseRequest({ inferFromFile: false });
      }
    });

    els.customDelimiterInput.addEventListener("change", () => {
      if (String(els.delimiterModeSelect.value || "csv") !== "custom") return;
      if (!hasSelectedFile()) return;
      resetParseState({ keepWarning: true });
      queueParseRequest({ inferFromFile: false });
    });

    [els.previewHeaderOn, els.previewHeaderOff].forEach((control) => {
      if (!control) return;
      control.addEventListener("change", () => {
        state.hasHeader = getHasHeaderEnabled();
        if (!hasSelectedFile()) {
          syncHeaderControls();
          return;
        }
        resetParseState({ keepWarning: true });
        queueParseRequest({ inferFromFile: false });
      });
    });

    if (els.previewSelectAllInput) {
      els.previewSelectAllInput.addEventListener("change", () => {
        if (state.isParsing || state.estimating || state.running) {
          syncPreviewSelectAll();
          return;
        }
        const allIndexes = (Array.isArray(state.columns) ? state.columns : []).map((column) => Number(column.index));
        const nextIndexes = els.previewSelectAllInput.checked ? allIndexes : [];
        applyColumnSelection(nextIndexes);
      });
    }

    if (els.previewTable) {
      els.previewTable.addEventListener("change", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement) || !target.hasAttribute("data-preview-column-index")) {
          return;
        }
        if (state.isParsing || state.estimating || state.running) {
          renderPreviewTable();
          return;
        }

        const rawIndex = Number(target.getAttribute("data-preview-column-index"));
        if (!Number.isInteger(rawIndex) || rawIndex < 0) {
          return;
        }

        const nextIndexes = getSelectedColumnIndexes();
        const selectedSet = new Set(nextIndexes);
        const shouldSelect = target instanceof HTMLInputElement ? Boolean(target.checked) : !selectedSet.has(rawIndex);
        if (shouldSelect) {
          selectedSet.add(rawIndex);
        } else {
          selectedSet.delete(rawIndex);
        }
        applyColumnSelection(Array.from(selectedSet));
      });
    }

    els.mappingBody.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const fieldName = target.getAttribute("data-map-select") || target.getAttribute("data-map-constant");
      if (!fieldName) return;

      if (target.hasAttribute("data-map-select")) {
        const rawValue = target.value || "ignore";
        if (rawValue === "ignore") {
          state.mapping[fieldName] = { source_type: "ignore", column_index: null, constant_value: "" };
        } else if (rawValue === "constant") {
          const current = state.mapping[fieldName] || { constant_value: "" };
          state.mapping[fieldName] = {
            source_type: "constant",
            column_index: null,
            constant_value: current.constant_value || "",
          };
        } else if (rawValue.startsWith("col:")) {
          const idx = Number(rawValue.replace("col:", ""));
          state.mapping[fieldName] = {
            source_type: "column",
            column_index: Number.isFinite(idx) ? idx : null,
            constant_value: "",
          };
        }
        renderMappingTable();
      } else if (target.hasAttribute("data-map-constant")) {
        const current = state.mapping[fieldName] || { source_type: "constant", column_index: null, constant_value: "" };
        current.constant_value = target.value || "";
        state.mapping[fieldName] = current;
      }
    });
  }

  function init() {
    populateDeckOptions();
    populateNoteTypeOptions();
    renderUniquenessFields();
    handleDelimiterModeChange();
    syncHeaderControls();
    syncPreviewSelectAll();
    els.estimateBtn.textContent = ESTIMATE_BUTTON_LABEL;
    els.executeBtn.textContent = EXECUTE_BUTTON_LABEL;
    setParseButtonLoading(false);
    refreshImportUiState();
    bindEvents();
  }

  init();
})();
