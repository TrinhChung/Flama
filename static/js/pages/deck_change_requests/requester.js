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
  getRequestStatusMeta,
  renderChangeItems,
  renderConflicts,
  renderLocalPreviewSummary,
  renderRequestSummary,
} from "./ui.js";

const root = document.getElementById("shared-deck-change-request-root");

if (root) {
  const deckItemId = root.getAttribute("data-deck-item-id") || "";
  const requestDetailUrlTemplate = root.getAttribute("data-request-detail-url-template") || "";

  const pageTitleEl = document.getElementById("change-request-page-title");
  const titleEl = document.getElementById("change-request-title-input");
  const descriptionEl = document.getElementById("change-request-description-input");
  const metaEl = document.getElementById("change-request-page-meta");
  const actionNoteEl = document.getElementById("change-request-action-note");
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

  function setButtonContent(button, html) {
    if (button) {
      button.innerHTML = html;
    }
  }

  function clearBanner(bannerEl, tone = "info") {
    if (!bannerEl) return;
    bannerEl.textContent = "";
    bannerEl.classList.add("d-none");
    bannerEl.classList.remove("change-request-banner--info", "change-request-banner--success", "change-request-banner--error");
    bannerEl.classList.add(`change-request-banner--${tone}`);
  }

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message || "Không thể hoàn tất yêu cầu.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    clearBanner(errorEl, "error");
  }

  function showStatus(message, tone = "info") {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.remove("d-none");
    statusEl.classList.remove("change-request-banner--info", "change-request-banner--success", "change-request-banner--error");
    statusEl.classList.add(`change-request-banner--${tone}`);
  }

  function clearStatus() {
    clearBanner(statusEl, "info");
  }

  function setBusy(isBusy) {
    state.busy = Boolean(isBusy);
    render();
  }

  function getRequesterHeadline() {
    return "Chuẩn bị change request";
  }

  function getRequesterMeta(deckTitle) {
    if (state.request) {
      const statusMeta = getRequestStatusMeta(state.request.status);
      return `${deckTitle} · ${statusMeta.description}`;
    }

    const itemCount = Number(state.localPreview?.item_count || 0);
    if (itemCount > 0) {
      return `${deckTitle} · Có ${itemCount} local change đang chờ tạo draft.`;
    }
    return `${deckTitle} · Clone hiện chưa có local change để gửi request.`;
  }

  function getActionNote() {
    if (!state.request) {
      if (Number(state.localPreview?.item_count || 0) > 0) {
        return "Tạo draft để snapshot local overlay hiện tại, sau đó sync với upstream trước khi submit.";
      }
      return "Hãy tạo local edits trong clone trước. Màn này chỉ gửi được những thay đổi đang nằm trên overlay.";
    }

    switch (state.request.status) {
      case "needs_sync":
        return "Draft đang tồn tại nhưng chưa đủ mới. Chạy sync để kiểm tra upstream drift trước khi submit.";
      case "has_conflict":
        return "Cần resolve toàn bộ conflict bên dưới. Khi mọi conflict đã sạch, request sẽ quay lại trạng thái draft.";
      case "draft":
        return "Draft đã sạch conflict. Kiểm tra mô tả, review lại diff và bấm gửi review khi sẵn sàng.";
      case "pending_review":
        return "Request đã được submit. Bạn chỉ còn theo dõi detail cho đến khi owner review xong.";
      case "merged":
        return "Request đã được merge vào source deck.";
      case "rejected":
        return "Request đã bị reject. Overlay edits vẫn còn trên local install của bạn.";
      default:
        return "Theo dõi panel trạng thái để biết bước tiếp theo của request.";
    }
  }

  function render() {
    const deckTitle = state.deckDetail?.title || "Deck";
    const requestStatus = state.request?.status || "";

    if (pageTitleEl) {
      pageTitleEl.textContent = getRequesterHeadline();
    }
    if (metaEl) {
      metaEl.textContent = getRequesterMeta(deckTitle);
    }
    if (actionNoteEl) {
      actionNoteEl.textContent = getActionNote();
    }

    if (state.request) {
      if (titleEl) {
        titleEl.value = state.request.title || "";
      }
      if (descriptionEl) {
        descriptionEl.value = state.request.description || "";
      }
      renderRequestSummary(summaryEl, state.request);
      renderChangeItems(itemsEl, state.request.items || []);
      renderConflicts(conflictsEl, state.request.conflicts || [], {
        interactive: Boolean(state.request.can_resolve),
      });

      if (openDetailLink) {
        openDetailLink.classList.remove("d-none");
        openDetailLink.href = buildRequestDetailUrl(state.request.id);
      }
    } else {
      renderLocalPreviewSummary(summaryEl, state.localPreview, { deckTitle });
      renderChangeItems(itemsEl, state.localPreview?.items || [], {
        emptyText: "Clone này chưa có local changes để dựng request.",
      });
      renderConflicts(conflictsEl, []);

      if (titleEl && !state.busy) {
        titleEl.value = titleEl.value || "";
      }
      if (descriptionEl && !state.busy) {
        descriptionEl.value = descriptionEl.value || "";
      }
      if (openDetailLink) {
        openDetailLink.classList.add("d-none");
        openDetailLink.href = "#";
      }
    }

    setButtonContent(
      buildBtn,
      state.request
        ? '<i class="bi bi-arrow-repeat"></i> Làm mới draft'
        : '<i class="bi bi-stars"></i> Tạo draft',
    );
    setButtonContent(syncBtn, '<i class="bi bi-arrow-repeat"></i> Sync upstream');
    setButtonContent(
      submitBtn,
      requestStatus === "pending_review"
        ? '<i class="bi bi-hourglass-split"></i> Đang chờ review'
        : '<i class="bi bi-send"></i> Gửi review',
    );
    setButtonContent(refreshBtn, '<i class="bi bi-arrow-clockwise"></i> Tải lại');

    if (buildBtn) {
      buildBtn.disabled = state.busy || requestStatus === "pending_review";
    }
    if (syncBtn) {
      syncBtn.disabled = state.busy || !state.request || requestStatus === "pending_review";
    }
    if (submitBtn) {
      submitBtn.disabled = state.busy || !state.request?.can_submit;
    }
    if (refreshBtn) {
      refreshBtn.disabled = state.busy;
    }

    document.title = `${getRequesterHeadline()} | ${deckTitle}`;
  }

  async function loadState({ preserveInputs = false } = {}) {
    setBusy(true);
    clearError();
    if (!preserveInputs) {
      clearStatus();
    }

    try {
      const [deckDetail, activePayload] = await Promise.all([
        fetchDeckDetail(deckItemId),
        fetchActiveRequest(deckItemId),
      ]);
      state.deckDetail = deckDetail;
      state.request = activePayload?.request || null;
      state.localPreview = state.request ? null : await fetchLocalChanges(deckItemId);

      if (!preserveInputs && !state.request) {
        if (titleEl) {
          titleEl.value = "";
        }
        if (descriptionEl) {
          descriptionEl.value = "";
        }
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
    clearStatus();

    try {
      state.request = await action();
      state.localPreview = null;
      render();
      showStatus(successMessage, "success");
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
    }
  }

  buildBtn?.addEventListener("click", async () => {
    await runAction(
      () => createDraft(deckItemId, {
        title: titleEl?.value || "",
        description: descriptionEl?.value || "",
      }),
      "Draft change request đã được cập nhật.",
    );
  });

  syncBtn?.addEventListener("click", async () => {
    if (!state.request?.id) {
      showError("Hãy tạo draft trước khi sync.");
      return;
    }

    await runAction(
      () => syncRequest(deckItemId, state.request.id),
      "Sync với upstream đã hoàn tất.",
    );
  });

  submitBtn?.addEventListener("click", async () => {
    if (!state.request?.id) {
      showError("Hãy tạo draft trước khi gửi review.");
      return;
    }

    await runAction(
      () => submitRequest(deckItemId, state.request.id),
      "Change request đã được gửi cho owner review.",
    );
  });

  refreshBtn?.addEventListener("click", async () => {
    clearStatus();
    await loadState({ preserveInputs: true });
  });

  conflictsEl?.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !state.request?.id) {
      return;
    }

    const actionTarget = target.closest("[data-resolve-conflict-id], [data-manual-submit-conflict-id]");
    if (!(actionTarget instanceof HTMLElement)) {
      return;
    }

    const conflictId = actionTarget.getAttribute("data-resolve-conflict-id");
    const resolutionMode = actionTarget.getAttribute("data-resolution-mode");
    if (conflictId && resolutionMode) {
      await runAction(
        () => resolveConflict(deckItemId, state.request.id, conflictId, {
          resolution_mode: resolutionMode,
        }),
        "Conflict đã được cập nhật.",
      );
      return;
    }

    const manualConflictId = actionTarget.getAttribute("data-manual-submit-conflict-id");
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
      "Conflict đã được resolve bằng giá trị thủ công.",
    );
  });

  loadState();
}
