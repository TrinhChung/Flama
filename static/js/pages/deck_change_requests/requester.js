import {
  createDraft,
  fetchActiveRequest,
  fetchDeckDetail,
  fetchLocalChanges,
  resolveConflict,
  submitRequest,
  syncRequest,
} from "./api.js";
import {
  escapeHtml,
  renderChangeItems,
  renderConflicts,
  renderRequestSummary,
} from "./ui.js";

const root = document.getElementById("shared-deck-change-request-root");

if (root) {
  const deckItemId = root.getAttribute("data-deck-item-id") || "";
  const requestDetailUrlTemplate = root.getAttribute("data-request-detail-url-template") || "";

  const titleEl = document.getElementById("change-request-title-input");
  const descriptionEl = document.getElementById("change-request-description-input");
  const metaEl = document.getElementById("change-request-page-meta");
  const errorEl = document.getElementById("change-request-error");
  const statusEl = document.getElementById("change-request-status");
  const summaryEl = document.getElementById("change-request-summary");
  const itemsEl = document.getElementById("change-request-items");
  const conflictsEl = document.getElementById("change-request-conflicts");
  const buildBtn = document.getElementById("change-request-build-btn");
  const syncBtn = document.getElementById("change-request-sync-btn");
  const submitBtn = document.getElementById("change-request-submit-btn");
  const refreshBtn = document.getElementById("change-request-refresh-btn");
  const openDetailLink = document.getElementById("change-request-open-detail");

  const state = {
    deckDetail: null,
    localPreview: null,
    request: null,
    busy: false,
  };

  function buildRequestDetailUrl(requestId) {
    return requestDetailUrlTemplate.replace("__REQUEST_ID__", encodeURIComponent(requestId || ""));
  }

  function setBusy(isBusy) {
    state.busy = Boolean(isBusy);
    [buildBtn, syncBtn, submitBtn, refreshBtn].forEach((button) => {
      if (button) {
        button.disabled = state.busy;
      }
    });
  }

  function showError(message) {
    errorEl.textContent = message || "Khong the hoan tat yeu cau.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function showStatus(message) {
    statusEl.textContent = message || "";
    statusEl.classList.toggle("d-none", !message);
  }

  function renderPreviewSummary(preview) {
    if (!preview || !preview.item_count) {
      summaryEl.innerHTML = "<div class='market-empty-state'>Clone nay chua co local change de gui len upstream.</div>";
      return;
    }
    const changeCounts = Object.entries(preview.change_counts || {})
      .map(([key, value]) => `${escapeHtml(key)}: ${escapeHtml(String(value))}`)
      .join(" | ");
    summaryEl.innerHTML = `
      <div class="row g-3">
        <div class="col-lg-8">
          <div class="fw-semibold">Local clone changes</div>
          <div class="small text-muted mt-1">Overlay fingerprint: ${escapeHtml(preview.overlay_fingerprint || "N/A")}</div>
          <div class="small text-muted mt-1">Item count: ${escapeHtml(String(preview.item_count || 0))}</div>
          ${changeCounts ? `<div class="small text-muted mt-1">${changeCounts}</div>` : ""}
        </div>
        <div class="col-lg-4">
          <div class="small text-muted">Deck</div>
          <div>${escapeHtml(state.deckDetail?.title || "Unknown deck")}</div>
        </div>
      </div>
    `;
  }

  function render() {
    const deckTitle = state.deckDetail?.title || "Deck";
    if (state.request) {
      metaEl.textContent = `${deckTitle} | status: ${state.request.status || "unknown"}`;
      titleEl.value = state.request.title || "";
      descriptionEl.value = state.request.description || "";
      renderRequestSummary(summaryEl, state.request);
      renderChangeItems(itemsEl, state.request.items || []);
      renderConflicts(conflictsEl, state.request.conflicts || [], {
        interactive: Boolean(state.request.can_resolve),
      });
      openDetailLink.classList.remove("d-none");
      openDetailLink.href = buildRequestDetailUrl(state.request.id);
    } else {
      metaEl.textContent = `${deckTitle} | local clone changes`;
      renderPreviewSummary(state.localPreview);
      renderChangeItems(itemsEl, state.localPreview?.items || []);
      renderConflicts(conflictsEl, []);
      openDetailLink.classList.add("d-none");
      openDetailLink.href = "#";
    }

    const requestStatus = state.request?.status || "";
    syncBtn.disabled = state.busy || !state.request || requestStatus === "pending_review";
    submitBtn.disabled = state.busy || !state.request;
  }

  async function loadState({ preserveInputs = false } = {}) {
    setBusy(true);
    clearError();
    try {
      const [deckDetail, activePayload] = await Promise.all([
        fetchDeckDetail(deckItemId),
        fetchActiveRequest(deckItemId),
      ]);
      state.deckDetail = deckDetail;
      state.request = activePayload?.request || null;
      state.localPreview = state.request ? null : await fetchLocalChanges(deckItemId);
      if (!preserveInputs && !state.request) {
        titleEl.value = "";
        descriptionEl.value = "";
      }
      render();
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action, successMessage) {
    setBusy(true);
    clearError();
    showStatus("");
    try {
      state.request = await action();
      state.localPreview = null;
      render();
      showStatus(successMessage);
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
    }
  }

  buildBtn?.addEventListener("click", async () => {
    await runAction(
      () => createDraft(deckItemId, {
        title: titleEl.value,
        description: descriptionEl.value,
      }),
      "Draft change request da duoc cap nhat.",
    );
  });

  syncBtn?.addEventListener("click", async () => {
    if (!state.request?.id) {
      showError("Hay tao draft truoc khi sync.");
      return;
    }
    await runAction(
      () => syncRequest(deckItemId, state.request.id),
      "Sync voi upstream da hoan tat.",
    );
  });

  submitBtn?.addEventListener("click", async () => {
    if (!state.request?.id) {
      showError("Hay tao draft truoc khi gui review.");
      return;
    }
    await runAction(
      () => submitRequest(deckItemId, state.request.id),
      "Change request da duoc gui cho owner review.",
    );
  });

  refreshBtn?.addEventListener("click", async () => {
    showStatus("");
    await loadState({ preserveInputs: true });
  });

  conflictsEl?.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !state.request?.id) {
      return;
    }

    const conflictId = target.getAttribute("data-resolve-conflict-id");
    const resolutionMode = target.getAttribute("data-resolution-mode");
    if (conflictId && resolutionMode) {
      await runAction(
        () => resolveConflict(deckItemId, state.request.id, conflictId, {
          resolution_mode: resolutionMode,
        }),
        "Conflict da duoc cap nhat.",
      );
      return;
    }

    const manualConflictId = target.getAttribute("data-manual-submit-conflict-id");
    if (!manualConflictId) {
      return;
    }
    const field = conflictsEl.querySelector(`[data-manual-conflict-id="${manualConflictId}"]`);
    const rawValue = field instanceof HTMLTextAreaElement ? field.value.trim() : "";
    let resolvedValue = rawValue;
    if (rawValue) {
      try {
        resolvedValue = JSON.parse(rawValue);
      } catch (_error) {
        resolvedValue = rawValue;
      }
    }
    await runAction(
      () => resolveConflict(deckItemId, state.request.id, manualConflictId, {
        resolution_mode: "manual",
        resolved_value: resolvedValue,
      }),
      "Conflict da duoc resolve bang gia tri thu cong.",
    );
  });

  loadState();
}
